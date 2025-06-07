#!/usr/bin/env python3
"""
YT-to-Jellyfin: Download YouTube playlists and process them for Jellyfin media server.
"""
import os
import sys
import logging
import argparse
import json
import tempfile
import shutil
import re
import time
import uuid
import yaml
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from flask import Flask, render_template, request, jsonify, redirect, url_for, abort, send_from_directory

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('yt-to-jellyfin.log')
    ]
)
logger = logging.getLogger('yt-to-jellyfin')

class DownloadJob:
    """Class to track the status of a download job."""
    
    def __init__(self, job_id, playlist_url, show_name, season_num, episode_start):
        self.job_id = job_id
        self.playlist_url = playlist_url
        self.show_name = show_name
        self.season_num = season_num
        self.episode_start = episode_start
        self.status = "queued"
        self.progress = 0
        self.messages = []
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        
        # Detailed progress tracking
        self.current_stage = "waiting"
        self.stage_progress = 0
        self.current_file = ""
        self.total_files = 0
        self.processed_files = 0
        self.detailed_status = "Job queued"
    
    def update(self, status=None, progress=None, message=None, stage=None, file_name=None, 
               stage_progress=None, total_files=None, processed_files=None, detailed_status=None):
        """Update job status information with detailed progress."""
        if status:
            self.status = status
        if progress is not None:
            self.progress = progress
        if stage:
            self.current_stage = stage
        if file_name:
            self.current_file = file_name
        if stage_progress is not None:
            self.stage_progress = stage_progress
        if total_files is not None:
            self.total_files = total_files
        if processed_files is not None:
            self.processed_files = processed_files
        if detailed_status:
            self.detailed_status = detailed_status
            
        # Add a message if provided
        if message:
            # Add stage information to the message if applicable
            if stage and not detailed_status:
                stage_desc = {
                    "waiting": "Waiting to start",
                    "downloading": "Downloading videos",
                    "processing_metadata": "Processing metadata",
                    "converting": "Converting videos to H.265",
                    "generating_artwork": "Generating artwork and thumbnails",
                    "creating_nfo": "Creating NFO files",
                    "completed": "Processing completed",
                    "failed": "Processing failed"
                }
                prefix = f"[{stage_desc.get(stage, stage)}]"
                message = f"{prefix} {message}"
            
            self.messages.append({
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "text": message
            })
        
        self.updated_at = datetime.now()
    
    def to_dict(self):
        """Convert job to dictionary for JSON response."""
        return {
            "job_id": self.job_id,
            "playlist_url": self.playlist_url,
            "show_name": self.show_name,
            "season_num": self.season_num,
            "episode_start": self.episode_start,
            "status": self.status,
            "progress": self.progress,
            "messages": self.messages,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            "current_stage": self.current_stage,
            "stage_progress": self.stage_progress,
            "current_file": self.current_file,
            "total_files": self.total_files,
            "processed_files": self.processed_files,
            "detailed_status": self.detailed_status
        }

class YTToJellyfin:
    """Main application class for YouTube to Jellyfin conversion."""
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = self._load_config()
        self.jobs = {}  # Track active and completed jobs
        self.job_lock = threading.Lock()

        # Playlist tracking
        self.playlists_file = os.path.join('config', 'playlists.json')
        self.playlists = self._load_playlists()
    
    def _load_config(self) -> Dict:
        """Load configuration from environment variables or config file."""
        # Check for a local yt-dlp in the same directory as the script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_ytdlp = os.path.join(script_dir, 'yt-dlp')
        if os.path.exists(local_ytdlp) and os.access(local_ytdlp, os.X_OK):
            ytdlp_default = local_ytdlp
        else:
            # Look for specific yt-dlp paths
            specific_paths = [
                '/home/marc/Documents/yt-dlp/yt-dlp',  # Marc's path
                '/usr/local/bin/yt-dlp',               # Common Linux path
                '/usr/bin/yt-dlp'                      # Alternative Linux path
            ]
            for path in specific_paths:
                if os.path.exists(path) and os.access(path, os.X_OK):
                    ytdlp_default = path
                    break
            else:
                ytdlp_default = 'yt-dlp'
            
        config = {
            'output_dir': os.environ.get('OUTPUT_DIR', './media'),
            'quality': os.environ.get('VIDEO_QUALITY', '1080'),
            'use_h265': os.environ.get('USE_H265', 'true').lower() == 'true',
            'crf': int(os.environ.get('CRF', '28')),
            'ytdlp_path': os.environ.get('YTDLP_PATH', ytdlp_default),
            'cookies': '',  # Will set this after checking if file exists
            'completed_jobs_limit': int(os.environ.get('COMPLETED_JOBS_LIMIT', '10')),
            'web_enabled': os.environ.get('WEB_ENABLED', 'true').lower() == 'true',
            'web_port': int(os.environ.get('WEB_PORT', '8000')),
            'web_host': os.environ.get('WEB_HOST', '0.0.0.0'),
            # Jellyfin integration settings
            'jellyfin_enabled': os.environ.get('JELLYFIN_ENABLED', 'false').lower() == 'true',
            'jellyfin_tv_path': os.environ.get('JELLYFIN_TV_PATH', ''),
            'jellyfin_host': os.environ.get('JELLYFIN_HOST', ''),
            'jellyfin_port': os.environ.get('JELLYFIN_PORT', '8096'),
            'jellyfin_api_key': os.environ.get('JELLYFIN_API_KEY', ''),
            # Filename cleaning settings
            'clean_filenames': os.environ.get('CLEAN_FILENAMES', 'true').lower() == 'true',
        }
        
        # Check if cookies file from environment variable exists
        cookies_path = os.environ.get('COOKIES_PATH', '')
        if cookies_path and os.path.exists(cookies_path):
            config['cookies'] = cookies_path
        elif cookies_path:
            logger.warning(f"Cookies file not found at {cookies_path}, ignoring")
        
        # Try to load from config file
        config_file = os.environ.get('CONFIG_FILE', 'config/config.yml')
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    file_config = yaml.safe_load(f)
                
                if file_config and isinstance(file_config, dict):
                    # Handle nested structure
                    if 'media' in file_config and isinstance(file_config['media'], dict):
                        for key, value in file_config['media'].items():
                            if key == 'output_dir':
                                config['output_dir'] = value
                            elif key == 'quality':
                                config['quality'] = value
                            elif key == 'use_h265':
                                config['use_h265'] = value
                            elif key == 'crf':
                                config['crf'] = int(value)
                            elif key == 'clean_filenames':
                                config['clean_filenames'] = value
                    
                    # Handle top-level keys
                    if 'cookies_path' in file_config:
                        cookies_path = file_config['cookies_path']
                        # Check if the cookies path exists
                        if os.path.exists(cookies_path):
                            config['cookies'] = cookies_path
                        else:
                            logger.warning(f"Cookies file not found at {cookies_path}, ignoring")
                    
                    # Handle defaults
                    if 'defaults' in file_config and isinstance(file_config['defaults'], dict):
                        config['defaults'] = file_config['defaults']
                    
                    # Handle web settings
                    if 'web' in file_config and isinstance(file_config['web'], dict):
                        for key, value in file_config['web'].items():
                            if key == 'enabled':
                                config['web_enabled'] = value
                            elif key == 'port':
                                config['web_port'] = int(value)
                            elif key == 'host':
                                config['web_host'] = value
                    
                    # Handle Jellyfin settings
                    if 'jellyfin' in file_config and isinstance(file_config['jellyfin'], dict):
                        for key, value in file_config['jellyfin'].items():
                            if key == 'enabled':
                                config['jellyfin_enabled'] = value
                            elif key == 'tv_path':
                                config['jellyfin_tv_path'] = value
                            elif key == 'host':
                                config['jellyfin_host'] = value
                            elif key == 'port':
                                config['jellyfin_port'] = str(value)
                            elif key == 'api_key':
                                config['jellyfin_api_key'] = value
            
            except (yaml.YAMLError, IOError) as e:
                logger.error(f"Error loading config file: {e}")
        
        logger.info(f"Configuration loaded: {config}")
        return config
    
    def check_dependencies(self) -> bool:
        """Check if all required dependencies are installed."""
        dependencies = ['ffmpeg', 'convert', 'montage']
        
        # Special handling for yt-dlp
        ytdlp_path = self.config['ytdlp_path']
        logger.info(f"Using yt-dlp path: {ytdlp_path}")
        
        # If full path is provided, check if file exists and is executable
        if ytdlp_path.startswith('/'):
            if not os.path.exists(ytdlp_path):
                logger.error(f"yt-dlp not found at path: {ytdlp_path}")
                return False
            if not os.access(ytdlp_path, os.X_OK):
                logger.error(f"yt-dlp is not executable: {ytdlp_path}")
                return False
            logger.info(f"Found yt-dlp at: {ytdlp_path}")
        else:
            # For non-absolute paths, add to dependencies to check in PATH
            dependencies.append(ytdlp_path)
            
        # Check other dependencies
        for cmd in dependencies:
            try:
                result = subprocess.run(['which', cmd], check=True, capture_output=True, text=True)
                logger.info(f"Found dependency {cmd} at: {result.stdout.strip()}")
            except subprocess.CalledProcessError:
                logger.error(f"Required dependency not found: {cmd}")
                return False
                
        return True
    
    def sanitize_name(self, name: str) -> str:
        """Sanitize file/directory names to be compatible with file systems."""
        # Replace illegal chars with underscore and trim whitespace
        return re.sub(r'[\\/:"*?<>|]', '_', name).strip()
        
    def clean_filename(self, name: str) -> str:
        """Clean up filename for better readability.
        Replaces underscores with spaces and fixes common formatting issues."""
        # First, preserve episode identifier pattern (S01E01)
        episode_pattern = r'(S\d+E\d+)'
        episode_match = re.search(episode_pattern, name)
        
        if not episode_match:
            # No episode pattern found, just replace underscores
            return name.replace('_', ' ')
        
        # Split name by episode identifier
        parts = re.split(episode_pattern, name, maxsplit=1)
        
        # Clean up the title part (before episode identifier)
        if len(parts) >= 1 and parts[0]:
            # Replace underscores with spaces
            parts[0] = parts[0].replace('_', ' ')
            # Fix spacing around dash
            parts[0] = re.sub(r'\s*-\s*', ' - ', parts[0])
            # Remove multiple spaces
            parts[0] = re.sub(r'\s+', ' ', parts[0])
            # Trim whitespace
            parts[0] = parts[0].strip()
        
        # Reassemble the filename with the episode identifier, ensuring proper spacing
        result = ""
        for i, part in enumerate(parts):
            if i > 0 and i % 2 == 1 and parts[i-1] and not parts[i-1].endswith(' '):
                # This is an episode identifier (S01E01) and previous part doesn't end with space
                result += " " + part
            else:
                result += part
        
        # Handle case where episode identifier is at start (unlikely but possible)
        if result.startswith("S") and re.match(r'^S\d+E\d+', result) and len(parts) > 1:
            # Add space after episode identifier if next part doesn't start with space
            if not parts[1].startswith(' '):
                episode_end = re.match(r'^S\d+E\d+', result).end()
                result = result[:episode_end] + " " + result[episode_end:]

        return result

    def _load_playlists(self) -> Dict[str, Dict[str, str]]:
        """Load stored playlist information from disk."""
        if os.path.exists(self.playlists_file):
            try:
                with open(self.playlists_file, 'r') as f:
                    return json.load(f)
            except (IOError, json.JSONDecodeError):
                logger.warning("Failed to load playlists file, starting fresh")
        return {}

    def _save_playlists(self) -> None:
        """Persist playlist information to disk."""
        os.makedirs(os.path.dirname(self.playlists_file), exist_ok=True)
        with open(self.playlists_file, 'w') as f:
            json.dump(self.playlists, f, indent=2)

    def _get_playlist_id(self, url: str) -> str:
        """Extract playlist ID from URL."""
        match = re.search(r'list=([^&]+)', url)
        if match:
            return match.group(1)
        return re.sub(r'\W+', '', url)

    def _get_archive_file(self, url: str) -> str:
        """Get the archive file path for a playlist."""
        pid = self._get_playlist_id(url)
        return os.path.join('config', 'archives', f'{pid}.txt')

    def _register_playlist(self, url: str, show_name: str, season_num: str) -> None:
        """Register playlist metadata for incremental downloads."""
        pid = self._get_playlist_id(url)
        if pid not in self.playlists:
            self.playlists[pid] = {
                'url': url,
                'show_name': show_name,
                'season_num': season_num,
                'archive': self._get_archive_file(url)
            }
            self._save_playlists()

    def _get_existing_max_index(self, folder: str, season_num: str) -> int:
        """Return the highest episode index already present in folder."""
        pattern = re.compile(rf'S{season_num}E(\d+)')
        max_idx = 0
        for file in Path(folder).glob(f'*S{season_num}E*.mp4'):
            match = pattern.search(file.name)
            if match:
                max_idx = max(max_idx, int(match.group(1)))
        return max_idx

    def check_playlist_updates(self) -> List[str]:
        """Check registered playlists for new videos and create jobs."""
        created_jobs = []
        for pid, info in self.playlists.items():
            archive = info.get('archive', self._get_archive_file(info['url']))
            try:
                result = subprocess.run(
                    [
                        self.config['ytdlp_path'],
                        '--flat-playlist',
                        '--dump-single-json',
                        info['url'],
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                data = json.loads(result.stdout)
            except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
                logger.error(f"Failed to check playlist {info['url']}: {e}")
                continue

            ids = [e.get('id') for e in data.get('entries', []) if e.get('id')]
            archived = set()
            if os.path.exists(archive):
                with open(archive, 'r') as f:
                    archived = {line.strip() for line in f if line.strip()}

            new_ids = [vid for vid in ids if vid not in archived]
            if not new_ids:
                logger.info(f"No updates found for playlist {info['url']}")
                continue

            folder = self.create_folder_structure(info['show_name'], info['season_num'])
            start = self._get_existing_max_index(folder, info['season_num']) + 1
            job_id = self.create_job(
                info['url'],
                info['show_name'],
                info['season_num'],
                str(start).zfill(2),
            )
            created_jobs.append(job_id)

        return created_jobs
    
    def create_folder_structure(self, show_name: str, season_num: str) -> str:
        """Create the folder structure for the TV show and season."""
        folder = Path(self.config['output_dir']) / self.sanitize_name(show_name) / f"Season {season_num}"
        folder.mkdir(parents=True, exist_ok=True)
        return str(folder)
    
    def download_playlist(self, playlist_url: str, folder: str, season_num: str, job_id: str) -> bool:
        """Download a YouTube playlist using yt-dlp."""
        output_template = f"{folder}/%(title)s S{season_num}E%(playlist_index)02d.%(ext)s"
        
        # Get the absolute path for yt-dlp
        ytdlp_path = self.config['ytdlp_path']
        if not os.path.isabs(ytdlp_path):
            # Check if it's in the script directory
            script_dir = os.path.dirname(os.path.abspath(__file__))
            local_ytdlp = os.path.join(script_dir, ytdlp_path)
            if os.path.exists(local_ytdlp) and os.access(local_ytdlp, os.X_OK):
                ytdlp_path = local_ytdlp
        
        logger.info(f"Using yt-dlp from: {ytdlp_path}")
        
        cmd = [
            ytdlp_path,
            '--ignore-errors',
            '--no-warnings',
            f'-f bestvideo[height<={self.config["quality"]}]+bestaudio/best[height<={self.config["quality"]}]',
            '-o', output_template,
            '--write-info-json',
            '--restrict-filenames',
            '--merge-output-format', 'mp4',
            '--progress',
            '--no-cookies-from-browser',  # Don't try to read cookies from browser
            playlist_url
        ]

        # Use download archive to avoid re-downloading existing videos
        archive_file = self._get_archive_file(playlist_url)
        os.makedirs(os.path.dirname(archive_file), exist_ok=True)
        cmd.extend(['--download-archive', archive_file])

        # If no archive exists yet, skip already downloaded episodes by index
        if not os.path.exists(archive_file):
            existing_max = self._get_existing_max_index(folder, season_num)
            if existing_max:
                cmd.extend(['--playlist-start', str(existing_max + 1)])
        
        if self.config['cookies'] and os.path.exists(self.config['cookies']):
            # Only use cookies file if it exists
            cmd.insert(1, f'--cookies={self.config["cookies"]}')
        else:
            # Add --no-cookies option to prevent trying to save cookies
            cmd.insert(1, '--no-cookies')
        
        job = self.jobs.get(job_id)
        if job:
            job.update(
                status="downloading", 
                stage="downloading",
                progress=0, 
                stage_progress=0,
                detailed_status="Starting download of playlist",
                message=f"Starting download of playlist: {playlist_url}"
            )
        
        logger.info(f"Starting download of playlist: {playlist_url}")
        current_file = ""
        total_files = 0
        processed_files = 0
        
        try:
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            for line in process.stdout:
                line = line.strip()
                logger.info(line)
                if job:
                    # Extract information about which file is being processed
                    if "[download]" in line and "Destination:" in line:
                        try:
                            file_match = re.search(r'Destination:\s+(.+)', line)
                            if file_match:
                                current_file = os.path.basename(file_match.group(1))
                                processed_files += 1
                                job.update(
                                    file_name=current_file,
                                    processed_files=processed_files,
                                    detailed_status=f"Downloading: {current_file}",
                                    message=f"Downloading file: {current_file}"
                                )
                        except (ValueError, AttributeError) as e:
                            logger.error(f"Error parsing destination: {e}")
                            
                    # Extract total files information
                    elif "[download]" in line and "of" in line and "item" in line:
                        try:
                            total_match = re.search(r'of\s+(\d+)\s+item', line)
                            if total_match:
                                total_files = int(total_match.group(1))
                                job.update(total_files=total_files)
                        except (ValueError, AttributeError) as e:
                            logger.error(f"Error parsing total files: {e}")
                    
                    # Extract progress percentage
                    elif "%" in line:
                        try:
                            progress_str = re.search(r'(\d+\.\d+)%', line)
                            if progress_str:
                                file_progress = float(progress_str.group(1))
                                # Overall progress is a combination of which file we're on and its progress
                                if total_files > 0:
                                    overall_progress = min(
                                        99, 
                                        ((processed_files - 1) / total_files * 100) + 
                                        (file_progress / total_files)
                                    )
                                else:
                                    overall_progress = file_progress
                                
                                job.update(
                                    progress=overall_progress, 
                                    stage_progress=file_progress,
                                    message=line,
                                    detailed_status=f"Downloading: {current_file} ({file_progress:.1f}%)"
                                )
                        except (ValueError, AttributeError) as e:
                            logger.error(f"Error parsing progress: {e}")
                            job.update(message=line)
                    else:
                        # For lines without progress info, just log the message
                        job.update(message=line)
            
            process.wait()
            
            if process.returncode != 0:
                if job:
                    job.update(
                        status="failed", 
                        stage="failed",
                        detailed_status="Download failed",
                        message=f"Download failed with return code {process.returncode}"
                    )
                logger.error(f"Error downloading playlist, return code: {process.returncode}")
                return False
            
            if job:
                job.update(
                    status="downloaded", 
                    stage="downloading",
                    progress=100, 
                    stage_progress=100,
                    detailed_status="Download completed successfully",
                    message="Download completed successfully"
                )
            return True
            
        except subprocess.SubprocessError as e:
            if job:
                job.update(status="failed", message=f"Download failed: {str(e)}")
            logger.error(f"Error downloading playlist: {e}")
            return False
    
    def process_metadata(self, folder: str, show_name: str, season_num: str, episode_start: int, job_id: str) -> None:
        """Process metadata from downloaded videos and create NFO files."""
        job = self.jobs.get(job_id)
        if job:
            job.update(
                status="processing_metadata", 
                stage="processing_metadata",
                progress=0,
                stage_progress=0,
                detailed_status="Processing metadata from videos",
                message="Processing metadata and creating NFO files"
            )
        
        json_files = list(Path(folder).glob('*.info.json'))
        
        if not json_files:
            if job:
                job.update(
                    message="Warning: No JSON metadata files found",
                    detailed_status="No metadata files found"
                )
            logger.warning("No JSON metadata files found")
            return
            
        # Find first index to calculate offset
        with open(json_files[0], 'r') as f:
            first_data = json.load(f)
            first_index = first_data.get('playlist_index', 1)
        
        episode_offset = episode_start - first_index
        total_files = len(json_files)
        
        if job:
            job.update(
                total_files=total_files,
                detailed_status=f"Processing metadata for {total_files} videos"
            )
            
        for i, json_file in enumerate(json_files):
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            title = data.get('title', 'Unknown Title')
            description = data.get('description', '').split('\n')[0] if data.get('description') else ''
            upload_date = data.get('upload_date', '')
            
            # Format the upload date
            if upload_date:
                try:
                    air_date = datetime.strptime(upload_date, '%Y%m%d').strftime('%Y-%m-%d')
                except ValueError:
                    air_date = ''
            else:
                air_date = ''
            
            # Calculate new episode number
            original_ep = data.get('playlist_index', 0)
            new_ep = original_ep + episode_offset
            new_ep_padded = f"{new_ep:02d}"
            
            # Create base filename for renaming
            base_file = str(json_file).replace('.info.json', '')
            # Use a lambda function for replacement to avoid issues with backslash handling
            # Match both with and without spaces before the season identifier
            new_base = re.sub(rf'(\s?)?(S{season_num}E)[0-9]+', lambda m: f"{m.group(1) or ' '}{m.group(2)}{new_ep_padded}", base_file)
            file_name = os.path.basename(new_base)
            
            if job:
                job.update(
                    file_name=file_name,
                    processed_files=i+1,
                    detailed_status=f"Processing metadata: {file_name}",
                    message=f"Processing metadata for {title}"
                )
            
            # Rename video files
            for ext in ['mp4', 'mkv', 'webm']:
                original = f"{base_file}.{ext}"
                if os.path.exists(original):
                    # Get the basename without extension
                    basename = os.path.basename(new_base)
                    
                    # Check if filename cleaning is enabled
                    if self.config.get('clean_filenames', True):
                        # Clean the filename (replace underscores with spaces)
                        basename = self.clean_filename(basename)
                        
                    # Create new path with the potentially cleaned filename
                    new_file = os.path.join(os.path.dirname(new_base), f"{basename}.{ext}")
                    
                    os.rename(original, new_file)
                    if job:
                        job.update(message=f"Renamed file to {os.path.basename(new_file)}")
            
            # Create NFO file
            nfo_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<episodedetails>
  <title>{title}</title>
  <season>{season_num}</season>
  <episode>{new_ep_padded}</episode>
  <plot>{description}</plot>
  <aired>{air_date}</aired>
  <studio>YouTube</studio>
  <showtitle>{show_name}</showtitle>
</episodedetails>
"""
            # Get the basename without extension
            basename = os.path.basename(new_base)
            
            # Check if filename cleaning is enabled
            if self.config.get('clean_filenames', True):
                # Clean the filename (replace underscores with spaces)
                basename = self.clean_filename(basename)
                
            # Create NFO path with the potentially cleaned filename
            nfo_file = os.path.join(os.path.dirname(new_base), f"{basename}.nfo")
            
            with open(nfo_file, 'w') as f:
                f.write(nfo_content)
                
            if job:
                job.update(message=f"Created NFO file for {title}")
            
            # Remove JSON file after processing
            os.remove(json_file)
            
            # Update job progress
            if job and total_files:
                progress = int((i + 1) / total_files * 100)
                job.update(
                    progress=progress, 
                    stage_progress=progress,
                    detailed_status=f"Processed {i+1} of {total_files} files"
                )
    
    def convert_video_files(self, folder: str, season_num: str, job_id: str) -> None:
        """Convert video files to H.265 format for better compression."""
        if not self.config['use_h265']:
            logger.info("H.265 conversion disabled, skipping")
            job = self.jobs.get(job_id)
            if job:
                job.update(
                    message="H.265 conversion disabled, skipping",
                    detailed_status="H.265 conversion disabled"
                )
            return
        
        job = self.jobs.get(job_id)
        if job:
            job.update(
                status="converting", 
                stage="converting",
                progress=0, 
                stage_progress=0,
                detailed_status="Preparing video conversion to H.265",
                message="Starting video conversion to H.265"
            )
            
        video_files = []
        for ext in ['webm', 'mp4']:
            video_files.extend(list(Path(folder).glob(f'*S{season_num}E*.{ext}')))
        
        total_files = len(video_files)
        if total_files == 0:
            if job:
                job.update(
                    message="No video files found for conversion",
                    detailed_status="No video files to convert"
                )
            return
        
        if job:
            job.update(
                total_files=total_files,
                detailed_status=f"Converting {total_files} video files to H.265"
            )
        
        for i, video in enumerate(video_files):
            ext = str(video).rsplit('.', 1)[1].lower()
            if ext == 'mp4':
                # Check if already H.265
                probe_cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', 
                            '-show_entries', 'stream=codec_name', '-of', 'json', str(video)]
                result = subprocess.run(probe_cmd, capture_output=True, text=True)
                codec = json.loads(result.stdout).get('streams', [{}])[0].get('codec_name', '')
                
                if codec in ['hevc', 'h265']:
                    logger.info(f"Skipping already H.265 encoded file: {video}")
                    if job:
                        job.update(
                            processed_files=i+1,
                            message=f"Skipping already H.265 encoded file: {os.path.basename(str(video))}"
                        )
                    continue
            
            base = str(video).rsplit('.', 1)[0]
            temp_file = f"{base}.temp.mp4"
            
            cmd = [
                'ffmpeg', '-i', str(video), 
                '-c:v', 'libx265', '-preset', 'medium', 
                '-crf', str(self.config['crf']), '-tag:v', 'hvc1',
                '-c:a', 'aac', '-b:a', '128k', temp_file
            ]
            
            filename = os.path.basename(str(video))
            if job:
                job.update(
                    file_name=filename,
                    processed_files=i+1,
                    detailed_status=f"Converting {filename} to H.265 (file {i+1}/{total_files})",
                    message=f"Converting {filename} to H.265 ({i+1}/{total_files})"
                )
            logger.info(f"Converting {video} to H.265")
            
            try:
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )
                
                for line in process.stdout:
                    # Log ffmpeg output for debugging
                    logger.debug(line.strip())
                    
                    if job and "time=" in line:
                        # Extract progress from ffmpeg output
                        try:
                            time_str = re.search(r'time=(\d+:\d+:\d+\.\d+)', line)
                            if time_str:
                                time_parts = time_str.group(1).split(':')
                                seconds = (
                                    float(time_parts[0]) * 3600 + 
                                    float(time_parts[1]) * 60 + 
                                    float(time_parts[2])
                                )
                                
                                # Get duration of video
                                duration_cmd = [
                                    'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                                    '-of', 'default=noprint_wrappers=1:nokey=1', str(video)
                                ]
                                duration_result = subprocess.run(
                                    duration_cmd, capture_output=True, text=True, check=True
                                )
                                duration = float(duration_result.stdout.strip())
                                
                                if duration > 0:
                                    file_progress = min(100, int(seconds / duration * 100))
                                    # Overall progress is a combination of completed files and current file progress
                                    total_progress = min(
                                        99, 
                                        ((i) / total_files * 100) + 
                                        (file_progress / total_files)
                                    )
                                    
                                    # Update job with both file and overall progress
                                    job.update(
                                        progress=total_progress,
                                        stage_progress=file_progress,
                                        detailed_status=f"Converting {filename}: {file_progress}% (file {i+1}/{total_files})"
                                    )
                                    
                                    # Add progress updates less frequently to avoid flooding the log
                                    if file_progress % 20 == 0:
                                        job.update(message=f"Converting {filename}: {file_progress}% complete")
                        except Exception as e:
                            logger.error(f"Error parsing progress: {e}")
                
                process.wait()
                
                if process.returncode == 0:
                    os.rename(temp_file, f"{base}.mp4")
                    if str(video) != f"{base}.mp4":
                        os.remove(video)
                    logger.info(f"Converted: {video} → {base}.mp4")
                    if job:
                        job.update(
                            message=f"Successfully converted {filename} to H.265",
                            detailed_status=f"Converted {i+1}/{total_files} files"
                        )
                else:
                    logger.error(f"Failed to convert {video}, return code: {process.returncode}")
                    if job:
                        job.update(
                            message=f"Failed to convert {filename}, return code: {process.returncode}",
                            detailed_status=f"Error converting {filename}"
                        )
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                
            except subprocess.SubprocessError as e:
                logger.error(f"Failed to convert {video}: {e}")
                if job:
                    job.update(
                        message=f"Failed to convert {filename}: {str(e)}",
                        detailed_status=f"Error converting {filename}"
                    )
                if os.path.exists(temp_file):
                    os.remove(temp_file)
        
        if job:
            job.update(
                progress=100,
                stage_progress=100,
                detailed_status="Video conversion completed",
                message="Video conversion completed"
            )
    
    def generate_artwork(self, folder: str, show_name: str, season_num: str, job_id: str) -> None:
        """Generate thumbnails, TV show and season artwork."""
        job = self.jobs.get(job_id)
        if job:
            job.update(status="generating_artwork", message="Generating thumbnails and artwork")
        
        show_folder = str(Path(folder).parent)
        
        # Generate episode thumbnails
        videos = list(Path(folder).glob(f'*S{season_num}E*.mp4'))
        for i, video in enumerate(videos):
            # Get the video file path without extension
            video_base = str(video).rsplit('.', 1)[0]
            
            # Get the basename without path
            basename = os.path.basename(video_base)
            
            # Check if filename cleaning is enabled
            if self.config.get('clean_filenames', True):
                # Clean the filename (replace underscores with spaces)
                basename = self.clean_filename(basename)
                
            # Create thumb path with the potentially cleaned filename
            thumb_path = os.path.join(os.path.dirname(video_base), f"{basename}-thumb.jpg")
            
            try:
                subprocess.run([
                    'ffmpeg', '-ss', '00:01:30', '-i', str(video),
                    '-vframes', '1', '-q:v', '2', thumb_path
                ], check=True, capture_output=True)
                logger.info(f"Generated thumbnail: {thumb_path}")
                
                if job and videos:
                    progress = int((i + 1) / len(videos) * 30)  # Thumbnails are 30% of artwork work
                    job.update(progress=progress, message=f"Generated thumbnail for {basename}")
                    
            except subprocess.CalledProcessError:
                logger.error(f"Failed to generate thumbnail for {video}")
                if job:
                    job.update(message=f"Failed to generate thumbnail for {os.path.basename(str(video))}")
        
        # Create TV show artwork
        try:
            episodes = list(Path(folder).glob(f'*S{season_num}E*.mp4'))
            if not episodes:
                logger.warning("No episodes found for artwork generation")
                if job:
                    job.update(message="No episodes found for artwork generation")
                return
            
            if job:
                job.update(progress=30, message="Creating show and season artwork")
                
            # Generate poster
            temp_posters = []
            for i, episode in enumerate(episodes[:1]):
                poster_file = os.path.join(self.temp_dir, f"tmp_poster_{i:03d}.jpg")
                subprocess.run([
                    'ffmpeg', '-i', str(episode), 
                    '-vf', "select='not(mod(n,1000))',scale=640:360", 
                    '-vframes', '3', poster_file
                ], check=True, capture_output=True)
                temp_posters.append(poster_file)
                
            # Create show poster
            if temp_posters:
                poster_path = os.path.join(show_folder, "poster.jpg")
                subprocess.run([
                    'convert', *temp_posters, '-gravity', 'Center', '-background', 'Black',
                    '-resize', '1000x1500^', '-extent', '1000x1500',
                    '-pointsize', '80', '-fill', 'white', '-gravity', 'south',
                    '-annotate', '+0+50', show_name, poster_path
                ], check=True)
                
                if job:
                    job.update(progress=60, message="Created show poster")
                
            # Generate season artwork
            season_frames_dir = os.path.join(self.temp_dir, "season_frames")
            os.makedirs(season_frames_dir, exist_ok=True)
            
            for i, episode in enumerate(episodes[:6]):
                frame_file = os.path.join(season_frames_dir, f"frame_{i:03d}.jpg")
                subprocess.run([
                    'ffmpeg', '-i', str(episode), '-vf', 'thumbnail',
                    '-frames:v', '1', frame_file
                ], check=True, capture_output=True)
            
            # Create season poster and landscape version
            season_frames = list(Path(season_frames_dir).glob('*.jpg'))
            if season_frames:
                montage_args = [
                    'montage', '-geometry', '400x225+5+5', '-background', 'black',
                    '-tile', '3x2', *[str(f) for f in season_frames], '-'
                ]
                
                convert_args = [
                    'convert', '-', '-resize', '1000x1500', '-',
                    '-gravity', 'south', '-background', '#00000080', '-splice', '0x60',
                    '-pointsize', '48', '-fill', 'white', '-annotate', '+0+20',
                    f"Season {season_num}", f"{folder}/season{season_num}-poster.jpg"
                ]
                
                p1 = subprocess.Popen(montage_args, stdout=subprocess.PIPE)
                p2 = subprocess.Popen(convert_args, stdin=p1.stdout)
                p2.communicate()
                
                # Create landscape version
                subprocess.run([
                    'convert', f"{folder}/season{season_num}-poster.jpg",
                    '-resize', '1000x562!', f"{folder}/season{season_num}.jpg"
                ], check=True)
                
                if job:
                    job.update(progress=100, message="Created season artwork")
                
        except (subprocess.CalledProcessError, OSError) as e:
            logger.error(f"Error generating artwork: {e}")
            if job:
                job.update(message=f"Error generating artwork: {str(e)}")
    
    def create_nfo_files(self, folder: str, show_name: str, season_num: str, job_id: str) -> None:
        """Create NFO files for TV show and season."""
        job = self.jobs.get(job_id)
        if job:
            job.update(status="creating_nfo", message="Creating NFO files")
        
        show_folder = str(Path(folder).parent)
        
        # Season NFO
        season_nfo = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<season>
  <seasonnumber>{season_num}</seasonnumber>
  <title>Season {season_num}</title>
  <plot>Season {season_num} of {show_name}</plot>
</season>
"""
        with open(f"{folder}/season.nfo", 'w') as f:
            f.write(season_nfo)
        
        # TV Show NFO
        tvshow_nfo = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<tvshow>
  <title>{show_name}</title>
  <studio>YouTube</studio>
</tvshow>
"""
        with open(f"{show_folder}/tvshow.nfo", 'w') as f:
            f.write(tvshow_nfo)
            
        if job:
            job.update(progress=100, message="Created NFO files")
    
    def copy_to_jellyfin(self, show_name: str, season_num: str, job_id: str) -> None:
        """Copy processed media files to Jellyfin TV folder."""
        if not self.config.get('jellyfin_enabled', False):
            logger.info("Jellyfin integration disabled, skipping file copy")
            return
            
        jellyfin_tv_path = self.config.get('jellyfin_tv_path', '')
        if not jellyfin_tv_path:
            logger.error("Jellyfin TV path not configured, skipping file copy")
            return
            
        job = self.jobs.get(job_id)
        if job:
            job.update(
                status="copying_to_jellyfin",
                stage="copying_to_jellyfin",
                progress=95,
                detailed_status="Copying files to Jellyfin TV folder",
                message="Starting copy to Jellyfin TV folder"
            )
        
        # Sanitize show name for folder path
        sanitized_show = self.sanitize_name(show_name)
        
        # Source folder in our media directory
        source_folder = Path(self.config['output_dir']) / sanitized_show / f"Season {season_num}"
        
        # Destination folder in Jellyfin TV directory
        dest_show_folder = Path(jellyfin_tv_path) / sanitized_show
        dest_season_folder = dest_show_folder / f"Season {season_num}"
        
        if not os.path.exists(dest_show_folder):
            try:
                os.makedirs(dest_show_folder, exist_ok=True)
                logger.info(f"Created show folder at {dest_show_folder}")
                if job:
                    job.update(message=f"Created show folder at {dest_show_folder}")
            except OSError as e:
                logger.error(f"Failed to create Jellyfin show folder: {e}")
                if job:
                    job.update(message=f"Error: Failed to create Jellyfin show folder: {e}")
                return
        
        if not os.path.exists(dest_season_folder):
            try:
                os.makedirs(dest_season_folder, exist_ok=True)
                logger.info(f"Created season folder at {dest_season_folder}")
                if job:
                    job.update(message=f"Created season folder at {dest_season_folder}")
            except OSError as e:
                logger.error(f"Failed to create Jellyfin season folder: {e}")
                if job:
                    job.update(message=f"Error: Failed to create Jellyfin season folder: {e}")
                return
        
        # Copy all media and metadata files
        try:
            # Get list of files to copy
            media_files = list(source_folder.glob("*.mp4"))
            nfo_files = list(source_folder.glob("*.nfo"))
            jpg_files = list(source_folder.glob("*.jpg"))
            all_files = media_files + nfo_files + jpg_files
            
            total_files = len(all_files)
            if job:
                job.update(
                    total_files=total_files,
                    processed_files=0,
                    detailed_status=f"Copying {total_files} files to Jellyfin"
                )
            
            # Copy each file
            for i, file_path in enumerate(all_files):
                dest_file = dest_season_folder / file_path.name
                
                # Skip if file already exists and is identical size
                if os.path.exists(dest_file) and os.path.getsize(dest_file) == os.path.getsize(file_path):
                    logger.info(f"Skipping {file_path.name} - already exists and same size")
                    if job:
                        job.update(
                            processed_files=i+1,
                            message=f"Skipped {file_path.name} - already exists"
                        )
                    continue
                
                # Copy the file
                shutil.copy2(file_path, dest_file)
                logger.info(f"Copied {file_path.name} to Jellyfin")
                
                if job:
                    job.update(
                        processed_files=i+1,
                        file_name=file_path.name,
                        stage_progress=int((i+1)/total_files*100),
                        detailed_status=f"Copying: {file_path.name} ({i+1}/{total_files})",
                        message=f"Copied {file_path.name} to Jellyfin TV folder"
                    )
            
            # Also copy show-level files (tvshow.nfo, poster.jpg, fanart.jpg)
            show_files = [
                (Path(self.config['output_dir']) / sanitized_show / "tvshow.nfo", dest_show_folder / "tvshow.nfo"),
                (Path(self.config['output_dir']) / sanitized_show / "poster.jpg", dest_show_folder / "poster.jpg"),
                (Path(self.config['output_dir']) / sanitized_show / "fanart.jpg", dest_show_folder / "fanart.jpg")
            ]
            
            for source, dest in show_files:
                if source.exists():
                    shutil.copy2(source, dest)
                    logger.info(f"Copied show file {source.name} to Jellyfin")
                    if job:
                        job.update(message=f"Copied {source.name} to Jellyfin")
            
            if job:
                job.update(
                    progress=98,
                    stage_progress=100,
                    detailed_status="Copy to Jellyfin completed",
                    message="Successfully copied all files to Jellyfin TV folder"
                )
                
            # Trigger Jellyfin library scan (if API key provided)
            if self.config.get('jellyfin_api_key') and self.config.get('jellyfin_host'):
                self.trigger_jellyfin_scan(job_id)
            
        except (IOError, shutil.Error) as e:
            logger.error(f"Error copying files to Jellyfin: {e}")
            if job:
                job.update(message=f"Error copying files to Jellyfin: {e}")
    
    def trigger_jellyfin_scan(self, job_id: str) -> None:
        """Trigger a library scan in Jellyfin using the API."""
        job = self.jobs.get(job_id)
        if job:
            job.update(
                detailed_status="Triggering Jellyfin library scan",
                message="Triggering Jellyfin library scan"
            )
            
        api_key = self.config.get('jellyfin_api_key', '')
        host = self.config.get('jellyfin_host', '')
        port = self.config.get('jellyfin_port', '8096')
        
        if not api_key or not host:
            logger.warning("Jellyfin API key or host not set, skipping library scan")
            return
            
        url = f"http://{host}:{port}/Library/Refresh?api_key={api_key}"
        
        try:
            import requests
            response = requests.post(url, timeout=10)
            
            if response.status_code in (200, 204):
                logger.info("Successfully triggered Jellyfin library scan")
                if job:
                    job.update(message="Successfully triggered Jellyfin library scan")
            else:
                logger.warning(f"Failed to trigger Jellyfin scan: {response.status_code} {response.text}")
                if job:
                    job.update(message=f"Failed to trigger Jellyfin scan: HTTP {response.status_code}")
                    
        except Exception as e:
            logger.error(f"Error triggering Jellyfin scan: {e}")
            if job:
                job.update(message=f"Error triggering Jellyfin scan: {str(e)}")
    
    def cleanup(self) -> None:
        """Clean up temporary files."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def process_job(self, job_id: str) -> None:
        """Worker function to process a job."""
        job = self.jobs.get(job_id)
        if not job:
            logger.error(f"Job {job_id} not found")
            return
        
        try:
            job.update(status="in_progress", message="Starting job processing")
            
            if not self.check_dependencies():
                job.update(status="failed", message="Missing dependencies")
                return
                
            folder = self.create_folder_structure(job.show_name, job.season_num)
            job.update(message=f"Created folder structure: {folder}")
            
            if not self.download_playlist(job.playlist_url, folder, job.season_num, job_id):
                job.update(status="failed", message="Download failed")
                return
                
            try:
                episode_start = int(job.episode_start)
            except ValueError:
                job.update(status="failed", message="Invalid episode start number")
                return
                
            self.process_metadata(folder, job.show_name, job.season_num, episode_start, job_id)
            self.convert_video_files(folder, job.season_num, job_id)
            self.generate_artwork(folder, job.show_name, job.season_num, job_id)
            self.create_nfo_files(folder, job.show_name, job.season_num, job_id)
            
            # Copy to Jellyfin if enabled
            if self.config.get('jellyfin_enabled', False) and self.config.get('jellyfin_tv_path'):
                self.copy_to_jellyfin(job.show_name, job.season_num, job_id)
            
            job.update(status="completed", progress=100, message="Job completed successfully")
            logger.info(f"Job {job_id} completed successfully")
            
        except Exception as e:
            logger.exception(f"Error processing job {job_id}: {e}")
            job.update(status="failed", message=f"Error: {str(e)}")
    
    def create_job(self, playlist_url: str, show_name: str, season_num: str, episode_start: str) -> str:
        """Create a new download job and return the job ID."""
        job_id = str(uuid.uuid4())
        job = DownloadJob(job_id, playlist_url, show_name, season_num, episode_start)

        # Track playlist for incremental downloads
        self._register_playlist(playlist_url, show_name, season_num)
        
        with self.job_lock:
            self.jobs[job_id] = job
            
            # Limit the number of completed jobs
            completed_jobs = [j for j in self.jobs.values() 
                             if j.status == "completed" or j.status == "failed"]
            completed_jobs.sort(key=lambda j: j.updated_at)
            
            while len(completed_jobs) > self.config.get('completed_jobs_limit', 10):
                old_job = completed_jobs.pop(0)
                del self.jobs[old_job.job_id]
        
        # Start job processing in a separate thread
        threading.Thread(target=self.process_job, args=(job_id,)).start()
        
        return job_id
    
    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get information about a specific job."""
        job = self.jobs.get(job_id)
        return job.to_dict() if job else None
    
    def get_jobs(self) -> List[Dict]:
        """Get a list of all jobs."""
        with self.job_lock:
            return [job.to_dict() for job in self.jobs.values()]
    
    def list_media(self) -> List[Dict]:
        """List all media in the output directory."""
        media = []
        output_dir = Path(self.config['output_dir'])
        
        if not output_dir.exists():
            return media
            
        for show_dir in output_dir.iterdir():
            if not show_dir.is_dir():
                continue
                
            show = {
                "name": show_dir.name,
                "path": str(show_dir),
                "seasons": []
            }
            
            # Get seasons
            for season_dir in show_dir.iterdir():
                if not season_dir.is_dir() or not season_dir.name.startswith("Season "):
                    continue
                    
                season = {
                    "name": season_dir.name,
                    "path": str(season_dir),
                    "episodes": []
                }
                
                # Get episodes
                for episode_file in season_dir.glob("*.mp4"):
                    episode = {
                        "name": episode_file.stem,
                        "path": str(episode_file),
                        "size": episode_file.stat().st_size,
                        "modified": datetime.fromtimestamp(episode_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                    }
                    season["episodes"].append(episode)
                    
                season["episodes"].sort(key=lambda e: e["name"])
                show["seasons"].append(season)
                
            show["seasons"].sort(key=lambda s: s["name"])
            media.append(show)
            
        return media
    
    def process(self, playlist_url: str, show_name: str, season_num: str, episode_start: int) -> bool:
        """Process the entire workflow from download to final media preparation."""
        try:
            # Create a job to track progress
            job_id = self.create_job(playlist_url, show_name, season_num, str(episode_start))
            
            # Wait for job to complete
            job = self.jobs.get(job_id)
            while job and job.status not in ("completed", "failed"):
                time.sleep(1)
                job = self.jobs.get(job_id)
                
            return job.status == "completed" if job else False
            
        except Exception as e:
            logger.exception(f"Error processing playlist: {e}")
            return False
        finally:
            self.cleanup()


# Create Flask application for web interface
app = Flask(__name__, 
            template_folder=os.path.join(os.path.dirname(__file__), 'web/templates'),
            static_folder=os.path.join(os.path.dirname(__file__), 'web/static'))

ytj = YTToJellyfin()

@app.route('/')
def index():
    """Main web interface page."""
    return render_template('index.html', 
                          jobs=ytj.get_jobs(),
                          media=ytj.list_media())

@app.route('/jobs', methods=['GET', 'POST'])
def jobs():
    """Handle job listing and creation."""
    if request.method == 'POST':
        # Create new job
        playlist_url = request.form.get('playlist_url')
        show_name = request.form.get('show_name')
        season_num = request.form.get('season_num')
        episode_start = request.form.get('episode_start')
        
        if not playlist_url or not show_name or not season_num or not episode_start:
            return jsonify({"error": "Missing required parameters"}), 400
            
        job_id = ytj.create_job(playlist_url, show_name, season_num, episode_start)
        return jsonify({"job_id": job_id})
    else:
        # Get all jobs
        return jsonify(ytj.get_jobs())

@app.route('/jobs/<job_id>', methods=['GET'])
def job_detail(job_id):
    """Get information about a specific job."""
    job = ytj.get_job(job_id)
    if job:
        return jsonify(job)
    return jsonify({"error": "Job not found"}), 404

@app.route('/media', methods=['GET'])
def media():
    """List all media files."""
    return jsonify(ytj.list_media())

@app.route('/config', methods=['GET', 'PUT'])
def config():
    """Get or update configuration."""
    if request.method == 'PUT':
        # Get updated configuration from request
        new_config = request.json
        if new_config:
            # Update allowed configuration settings
            allowed_keys = [
                'output_dir', 'quality', 'use_h265', 'crf', 'web_port', 
                'completed_jobs_limit', 'jellyfin_enabled', 'jellyfin_tv_path',
                'jellyfin_host', 'jellyfin_port', 'jellyfin_api_key', 'clean_filenames'
            ]
            
            # Update only allowed keys
            for key in allowed_keys:
                if key in new_config:
                    if key in ['jellyfin_enabled', 'use_h265', 'clean_filenames']:
                        ytj.config[key] = new_config[key] is True
                    elif key in ['crf', 'web_port', 'completed_jobs_limit']:
                        ytj.config[key] = int(new_config[key])
                    else:
                        ytj.config[key] = new_config[key]
                        
            # Special handling for cookies_path
            if 'cookies_path' in new_config:
                cookies_path = new_config['cookies_path']
                # Store the path for display purposes
                ytj.config['cookies_path'] = cookies_path
                
                # Check if the file exists and update cookies if it does
                if os.path.exists(cookies_path):
                    ytj.config['cookies'] = cookies_path
                    logger.info(f"Updated cookies file path to: {cookies_path}")
                else:
                    # Clear cookies if path is invalid
                    ytj.config['cookies'] = ''
                    logger.warning(f"Cookies file not found at {cookies_path}, not using cookies")
            
            return jsonify({"success": True, "message": "Configuration updated"})
        
        return jsonify({"error": "Invalid configuration data"}), 400
    else:
        # Get configuration
        safe_config = {k: v for k, v in ytj.config.items()}
        # Add cookies path for rendering the UI
        if 'cookies_path' not in safe_config and 'cookies' in safe_config:
            safe_config['cookies_path'] = safe_config['cookies']
        
        # For security, don't expose actual cookie file content or path
        if 'cookies' in safe_config:
            del safe_config['cookies']
            
        return jsonify(safe_config)

def main():
    """Parse command line arguments and execute the application."""
    parser = argparse.ArgumentParser(description='Download YouTube playlists as TV show episodes for Jellyfin')
    parser.add_argument('--web-only', action='store_true', help='Start only the web interface')
    parser.add_argument('--url', help='YouTube playlist URL')
    parser.add_argument('--show-name', help='TV show name')
    parser.add_argument('--season-num', help='Season number (e.g., 01)')
    parser.add_argument('--episode-start', help='Episode start number (e.g., 01)')
    parser.add_argument('--output-dir', help='Output directory')
    parser.add_argument('--quality', help='Video quality (720, 1080, etc.)')
    parser.add_argument('--no-h265', action='store_true', help='Disable H.265 conversion')
    parser.add_argument('--crf', type=int, help='CRF value for H.265 conversion')
    parser.add_argument('--config', help='Path to config file')
    parser.add_argument('--check-updates', action='store_true',
                        help='Check registered playlists for new videos')
    
    # Normal commandline usage still supported as before
    parser.add_argument('url_pos', nargs='?', help='YouTube playlist URL (positional)')
    parser.add_argument('show_name_pos', nargs='?', help='TV show name (positional)')
    parser.add_argument('season_num_pos', nargs='?', help='Season number (positional)')
    parser.add_argument('episode_start_pos', nargs='?', help='Episode start number (positional)')
    
    args = parser.parse_args()
    
    # Set environment variables from command line args if provided
    if args.output_dir:
        os.environ['OUTPUT_DIR'] = args.output_dir
    if args.quality:
        os.environ['VIDEO_QUALITY'] = args.quality
    if args.no_h265:
        os.environ['USE_H265'] = 'false'
    if args.crf:
        os.environ['CRF'] = str(args.crf)
    if args.config:
        os.environ['CONFIG_FILE'] = args.config

    if args.check_updates:
        ytj.check_playlist_updates()
        return 0
    
    # Web-only mode
    if args.web_only or ytj.config.get('web_enabled', True):
        # Start web interface
        host = ytj.config.get('web_host', '0.0.0.0')
        port = ytj.config.get('web_port', 8000)
        
        if args.web_only:
            logger.info(f"Starting web interface on {host}:{port}")
            app.run(host=host, port=port, debug=False)
            return 0
    
    # Command-line mode if URL is provided
    url = args.url or args.url_pos
    show_name = args.show_name or args.show_name_pos
    season_num = args.season_num or args.season_num_pos
    episode_start = args.episode_start or args.episode_start_pos
    
    # Use defaults from config if available
    if not url and 'defaults' in ytj.config and 'playlist_url' in ytj.config['defaults']:
        url = ytj.config['defaults']['playlist_url']
    if not show_name and 'defaults' in ytj.config and 'show_name' in ytj.config['defaults']:
        show_name = ytj.config['defaults']['show_name']
    if not season_num and 'defaults' in ytj.config and 'season_num' in ytj.config['defaults']:
        season_num = ytj.config['defaults']['season_num']
    if not episode_start and 'defaults' in ytj.config and 'episode_start' in ytj.config['defaults']:
        episode_start = ytj.config['defaults']['episode_start']
    
    if url and show_name and season_num and episode_start:
        try:
            episode_start_int = int(episode_start)
        except ValueError:
            logger.error("Episode start must be a number")
            return 1
        
        success = ytj.process(url, show_name, season_num, episode_start_int)
        
        # Always start web interface after processing if enabled
        if ytj.config.get('web_enabled', True) and not args.web_only:
            host = ytj.config.get('web_host', '0.0.0.0')
            port = ytj.config.get('web_port', 8000)
            logger.info(f"Starting web interface on {host}:{port}")
            app.run(host=host, port=port, debug=False)
            
        return 0 if success else 1
    elif ytj.config.get('web_enabled', True):
        # No command-line parameters, but web is enabled
        host = ytj.config.get('web_host', '0.0.0.0')
        port = ytj.config.get('web_port', 8000)
        logger.info(f"Starting web interface on {host}:{port}")
        app.run(host=host, port=port, debug=False)
        return 0
    else:
        parser.print_help()
        return 1

if __name__ == "__main__":
    sys.exit(main())