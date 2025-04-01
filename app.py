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
    
    def update(self, status=None, progress=None, message=None):
        """Update job status information."""
        if status:
            self.status = status
        if progress is not None:
            self.progress = progress
        if message:
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
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S")
        }

class YTToJellyfin:
    """Main application class for YouTube to Jellyfin conversion."""
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = self._load_config()
        self.jobs = {}  # Track active and completed jobs
        self.job_lock = threading.Lock()
    
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
            'cookies': os.environ.get('COOKIES_PATH', ''),
            'completed_jobs_limit': int(os.environ.get('COMPLETED_JOBS_LIMIT', '10')),
            'web_enabled': os.environ.get('WEB_ENABLED', 'true').lower() == 'true',
            'web_port': int(os.environ.get('WEB_PORT', '8000')),
            'web_host': os.environ.get('WEB_HOST', '0.0.0.0'),
        }
        
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
                    
                    # Handle top-level keys
                    if 'cookies_path' in file_config:
                        config['cookies'] = file_config['cookies_path']
                    
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
            playlist_url
        ]
        
        if self.config['cookies']:
            cmd.insert(1, f'--cookies={self.config["cookies"]}')
        
        job = self.jobs.get(job_id)
        if job:
            job.update(status="downloading", message=f"Starting download of playlist: {playlist_url}")
        
        logger.info(f"Starting download of playlist: {playlist_url}")
        try:
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            for line in process.stdout:
                logger.info(line.strip())
                if job:
                    # Extract progress percentage if possible
                    if "%" in line:
                        try:
                            progress_str = re.search(r'(\d+\.\d+)%', line)
                            if progress_str:
                                progress = float(progress_str.group(1))
                                job.update(progress=progress, message=line.strip())
                        except (ValueError, AttributeError):
                            job.update(message=line.strip())
                    else:
                        job.update(message=line.strip())
            
            process.wait()
            
            if process.returncode != 0:
                if job:
                    job.update(status="failed", message=f"Download failed with return code {process.returncode}")
                logger.error(f"Error downloading playlist, return code: {process.returncode}")
                return False
            
            if job:
                job.update(status="downloaded", progress=100, message="Download completed successfully")
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
            job.update(status="processing_metadata", message="Processing metadata and creating NFO files")
        
        json_files = list(Path(folder).glob('*.info.json'))
        
        if not json_files:
            if job:
                job.update(message="Warning: No JSON metadata files found")
            logger.warning("No JSON metadata files found")
            return
            
        # Find first index to calculate offset
        with open(json_files[0], 'r') as f:
            first_data = json.load(f)
            first_index = first_data.get('playlist_index', 1)
        
        episode_offset = episode_start - first_index
        
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
            new_base = re.sub(rf'(S{season_num}E)[0-9]+', f'\\1{new_ep_padded}', base_file)
            
            # Rename video files
            for ext in ['mp4', 'mkv', 'webm']:
                original = f"{base_file}.{ext}"
                if os.path.exists(original):
                    os.rename(original, f"{new_base}.{ext}")
            
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
            with open(f"{new_base}.nfo", 'w') as f:
                f.write(nfo_content)
            
            # Remove JSON file after processing
            os.remove(json_file)
            
            # Update job progress
            if job and json_files:
                progress = int((i + 1) / len(json_files) * 100)
                job.update(progress=progress, message=f"Processed metadata for {title}")
    
    def convert_video_files(self, folder: str, season_num: str, job_id: str) -> None:
        """Convert video files to H.265 format for better compression."""
        if not self.config['use_h265']:
            logger.info("H.265 conversion disabled, skipping")
            job = self.jobs.get(job_id)
            if job:
                job.update(message="H.265 conversion disabled, skipping")
            return
        
        job = self.jobs.get(job_id)
        if job:
            job.update(status="converting", progress=0, message="Starting video conversion to H.265")
            
        video_files = []
        for ext in ['webm', 'mp4']:
            video_files.extend(list(Path(folder).glob(f'*S{season_num}E*.{ext}')))
        
        total_files = len(video_files)
        if total_files == 0:
            if job:
                job.update(message="No video files found for conversion")
            return
        
        for i, video in enumerate(video_files):
            if ext == 'mp4':
                # Check if already H.265
                probe_cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', 
                            '-show_entries', 'stream=codec_name', '-of', 'json', str(video)]
                result = subprocess.run(probe_cmd, capture_output=True, text=True)
                codec = json.loads(result.stdout).get('streams', [{}])[0].get('codec_name', '')
                
                if codec in ['hevc', 'h265']:
                    logger.info(f"Skipping already H.265 encoded file: {video}")
                    if job:
                        job.update(message=f"Skipping already H.265 encoded file: {os.path.basename(str(video))}")
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
                job.update(message=f"Converting {filename} to H.265 ({i+1}/{total_files})")
            logger.info(f"Converting {video} to H.265")
            
            try:
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT,
                    universal_newlines=True
                )
                
                for line in process.stdout:
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
                                    total_progress = min(100, int((i + file_progress/100) / total_files * 100))
                                    job.update(progress=total_progress)
                        except Exception as e:
                            logger.error(f"Error parsing progress: {e}")
                
                process.wait()
                
                if process.returncode == 0:
                    os.rename(temp_file, f"{base}.mp4")
                    if str(video) != f"{base}.mp4":
                        os.remove(video)
                    logger.info(f"Converted: {video} → {base}.mp4")
                    if job:
                        job.update(message=f"Successfully converted {filename} to H.265")
                else:
                    logger.error(f"Failed to convert {video}, return code: {process.returncode}")
                    if job:
                        job.update(message=f"Failed to convert {filename}, return code: {process.returncode}")
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                
            except subprocess.SubprocessError as e:
                logger.error(f"Failed to convert {video}: {e}")
                if job:
                    job.update(message=f"Failed to convert {filename}: {str(e)}")
                if os.path.exists(temp_file):
                    os.remove(temp_file)
        
        if job:
            job.update(progress=100, message="Video conversion completed")
    
    def generate_artwork(self, folder: str, show_name: str, season_num: str, job_id: str) -> None:
        """Generate thumbnails, TV show and season artwork."""
        job = self.jobs.get(job_id)
        if job:
            job.update(status="generating_artwork", message="Generating thumbnails and artwork")
        
        show_folder = str(Path(folder).parent)
        
        # Generate episode thumbnails
        videos = list(Path(folder).glob(f'*S{season_num}E*.mp4'))
        for i, video in enumerate(videos):
            thumb = f"{str(video).rsplit('.', 1)[0]}-thumb.jpg"
            
            try:
                subprocess.run([
                    'ffmpeg', '-ss', '00:01:30', '-i', str(video),
                    '-vframes', '1', '-q:v', '2', thumb
                ], check=True, capture_output=True)
                logger.info(f"Generated thumbnail: {thumb}")
                
                if job and videos:
                    progress = int((i + 1) / len(videos) * 30)  # Thumbnails are 30% of artwork work
                    job.update(progress=progress, message=f"Generated thumbnail for {os.path.basename(str(video))}")
                    
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
            
            job.update(status="completed", progress=100, message="Job completed successfully")
            logger.info(f"Job {job_id} completed successfully")
            
        except Exception as e:
            logger.exception(f"Error processing job {job_id}: {e}")
            job.update(status="failed", message=f"Error: {str(e)}")
    
    def create_job(self, playlist_url: str, show_name: str, season_num: str, episode_start: str) -> str:
        """Create a new download job and return the job ID."""
        job_id = str(uuid.uuid4())
        job = DownloadJob(job_id, playlist_url, show_name, season_num, episode_start)
        
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
        # Update configuration - implement if needed
        return jsonify({"error": "Not implemented"}), 501
    else:
        # Get configuration
        safe_config = {k: v for k, v in ytj.config.items() if k not in ('cookies')}
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