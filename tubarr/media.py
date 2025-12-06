import os
import json
import re
import subprocess
import logging
import requests
from pathlib import Path
from typing import List, Dict, Optional, Sequence, TYPE_CHECKING
from datetime import datetime

from mutagen.id3 import ID3, TIT2, TPE1, TPE2, TALB, TRCK, TPOS, TDRC, TCON, APIC, ID3NoHeaderError

from .config import logger
from .episode_detection import EpisodeDetectionError, EpisodeMatch, EpisodeMetadata
from .utils import (
    sanitize_name,
    clean_filename,
    run_subprocess,
    terminate_process,
    log_job,
)
from . import tmdb

if TYPE_CHECKING:
    from .jobs import TrackMetadata


def create_folder_structure(
    app, show_name: str, season_num: str, *, base_path: Optional[str] = None
) -> str:
    root = Path(base_path or app.config["output_dir"])
    folder = root / sanitize_name(show_name) / f"Season {season_num}"
    folder.mkdir(parents=True, exist_ok=True)
    return str(folder)


def create_movie_folder(app, movie_name: str, *, base_path: Optional[str] = None) -> str:
    folder = Path(base_path or app.config["output_dir"]) / sanitize_name(movie_name)
    folder.mkdir(parents=True, exist_ok=True)
    return str(folder)


def create_audiobook_folder(app, title: str, author: str) -> str:
    """Create folder structure for audiobooks: Audiobooks/[Author]/Title."""

    base_folder = Path(app.config.get("audiobook_output_dir", "./audiobooks"))
    safe_author = sanitize_name(author) or "Unknown Author"
    safe_title = sanitize_name(title) or "Untitled Book"
    folder = base_folder / safe_author / safe_title
    folder.mkdir(parents=True, exist_ok=True)
    return str(folder)


def create_music_album_folder(
    app, album_name: str, artist_name: Optional[str] = None
) -> str:
    """Create folder structure for music albums: Music/[Artist]/Album"""
    base_folder = Path(app.config["music_output_dir"])
    if artist_name:
        base_folder = base_folder / sanitize_name(artist_name)
    album_folder = base_folder / sanitize_name(album_name)
    album_folder.mkdir(parents=True, exist_ok=True)
    return str(album_folder)


def write_m3u_playlist(
    app,
    prepared_files: Sequence[Path],
    *,
    base_path: Optional[str] = None,
    playlist_name: Optional[str] = None,
) -> Path:
    """Write an M3U playlist alongside the prepared tracks."""

    files = [Path(p) for p in prepared_files if p]
    if not files:
        raise ValueError("prepared_files must contain at least one track")

    base_dir = Path(base_path or app.config["music_output_dir"]).expanduser().resolve()
    playlist_dir = files[0].parent
    playlist_dir.mkdir(parents=True, exist_ok=True)

    safe_name = sanitize_name(playlist_name) if playlist_name else playlist_dir.name
    if not safe_name:
        safe_name = "playlist"
    playlist_path = playlist_dir / f"{safe_name}.m3u"

    entries: List[str] = []
    for file_path in files:
        resolved = file_path.resolve()
        try:
            relative = resolved.relative_to(base_dir)
            entries.append(relative.as_posix())
        except ValueError:
            entries.append(resolved.as_posix())

    playlist_path.write_text("\n".join(entries) + "\n", encoding="utf-8")
    logger.info(
        "Wrote M3U playlist with %s entries to %s", len(entries), playlist_path
    )
    return playlist_path


def download_playlist(
    app,
    playlist_url: str,
    folder: str,
    season_num: str,
    job_id: str,
    playlist_start: Optional[int] = None,
) -> bool:
    output_template = f"{folder}/%(title)s S{season_num}E%(playlist_index)02d.%(ext)s"
    ytdlp_path = app.config["ytdlp_path"]
    if not os.path.isabs(ytdlp_path):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_ytdlp = os.path.join(script_dir, ytdlp_path)
        if os.path.exists(local_ytdlp) and os.access(local_ytdlp, os.X_OK):
            ytdlp_path = local_ytdlp
    log_job(job_id, logging.INFO, f"Using yt-dlp from: {ytdlp_path}")
    job = app.jobs.get(job_id)
    quality_setting = app.config["quality"]
    if job and job.quality_override is not None:
        quality_setting = job.quality_override
    cmd = [
        ytdlp_path,
        "--ignore-errors",
        "--no-warnings",
        (
            f'-f bestvideo[height<={quality_setting}]'
            f'+bestaudio/best[height<={quality_setting}]'
        ),
        "-o",
        output_template,
        "--write-info-json",
        "--restrict-filenames",
        "--merge-output-format",
        "mp4",
        "--progress",
        "--no-cookies-from-browser",
        playlist_url,
    ]
    archive_file = app._get_archive_file(playlist_url)
    os.makedirs(os.path.dirname(archive_file), exist_ok=True)
    cmd.extend(["--download-archive", archive_file])
    if playlist_start:
        cmd.extend(["--playlist-start", str(playlist_start)])
    elif not os.path.exists(archive_file):
        existing_max = app._get_existing_max_index(folder, season_num)
        if existing_max:
            cmd.extend(["--playlist-start", str(existing_max + 1)])
    if app.config["cookies"] and os.path.exists(app.config["cookies"]):
        cmd.insert(1, f'--cookies={app.config["cookies"]}')
    else:
        cmd.insert(1, "--no-cookies")
    if job:
        job.update(
            status="downloading",
            stage="downloading",
            progress=0,
            stage_progress=0,
            detailed_status="Starting download of playlist",
            message=f"Starting download of playlist: {playlist_url}",
        )
    log_job(job_id, logging.INFO, f"Starting download of playlist: {playlist_url}")
    current_file = ""
    total_files = 0
    processed_files = 0
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            start_new_session=True,
        )
        if job:
            job.process = process
        for line in process.stdout:
            if job and job.status == "cancelled":
                terminate_process(process)
                break
            line = line.strip()
            log_job(job_id, logging.INFO, line)
            if job:
                if "[download]" in line and "Destination:" in line:
                    try:
                        file_match = re.search(r"Destination:\s+(.+)", line)
                        if file_match:
                            current_file = os.path.basename(file_match.group(1))
                            processed_files += 1
                            if job.remaining_files:
                                job.remaining_files.pop(0)
                            job.update(
                                file_name=current_file,
                                processed_files=processed_files,
                                detailed_status=f"Downloading: {current_file}",
                                message=f"Downloading file: {current_file}",
                            )
                    except (ValueError, AttributeError) as e:
                        log_job(
                            job_id,
                            logging.ERROR,
                            f"Error parsing destination: {e}",
                        )
                elif "[download]" in line and "of" in line and "item" in line:
                    try:
                        total_match = re.search(r"of\s+(\d+)\s+item", line)
                        if total_match:
                            total_files = int(total_match.group(1))
                            job.update(total_files=total_files)
                    except (ValueError, AttributeError) as e:
                        log_job(
                            job_id,
                            logging.ERROR,
                            f"Error parsing total files: {e}",
                        )
                elif "%" in line:
                    try:
                        progress_str = re.search(r"(\d+\.\d+)%", line)
                        if progress_str:
                            file_progress = float(progress_str.group(1))
                            if total_files > 0:
                                overall_progress = min(
                                    99,
                                    ((processed_files - 1) / total_files * 100)
                                    + (file_progress / total_files),
                                )
                            else:
                                overall_progress = file_progress
                            job.update(
                                progress=overall_progress,
                                stage_progress=file_progress,
                                message=line,
                                detailed_status=(
                                    f"Downloading: {current_file} "
                                    f"({file_progress:.1f}%)"
                                ),
                            )
                    except (ValueError, AttributeError) as e:
                        log_job(job_id, logging.ERROR, f"Error parsing progress: {e}")
                        job.update(message=line)
                else:
                    job.update(message=line)
        process.wait()
        if job:
            job.process = None
        if process.returncode != 0:
            if job:
                job.update(
                    status="failed",
                    stage="failed",
                    detailed_status="Download failed",
                    message=f"Download failed with return code {process.returncode}",
                )
            log_job(
                job_id,
                logging.ERROR,
                f"Error downloading playlist, return code: {process.returncode}",
            )
            return False
        if job:
            job.update(
                status="downloaded",
                stage="downloading",
                progress=100,
                stage_progress=100,
                detailed_status="Download completed successfully",
                message="Download completed successfully",
            )
        return True
    except subprocess.SubprocessError as e:
        if job:
            job.process = None
            job.update(status="failed", message=f"Download failed: {str(e)}")
        log_job(job_id, logging.ERROR, f"Error downloading playlist: {e}")
        return False


def _normalize_upload_date(upload_date: str) -> str:
    """Convert various upload date formats to ``YYYY-MM-DD``.

    yt-dlp commonly returns dates as ``YYYYMMDD``. This helper also tolerates
    already-normalized values while safely falling back to an empty string when
    parsing fails.
    """

    if not upload_date:
        return ""

    date_str = str(upload_date)
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def process_metadata(
    app,
    folder: str,
    show_name: str,
    season_num: str,
    episode_start: int,
    job_id: str,
    episode_mapper=None,
) -> List[str]:
    job = app.jobs.get(job_id)
    if job:
        job.update(
            status="processing_metadata",
            stage="processing_metadata",
            progress=0,
            stage_progress=0,
            detailed_status="Processing metadata from videos",
            message="Processing metadata and creating NFO files",
        )
    json_files = list(Path(folder).glob("*.info.json"))
    if not json_files:
        if job:
            job.update(
                message="Warning: No JSON metadata files found",
                detailed_status="No metadata files found",
            )
        log_job(job_id, logging.WARNING, "No JSON metadata files found")
        return []
    with open(json_files[0], "r") as f:
        first_data = json.load(f)
        first_index = first_data.get("playlist_index", 1)
    total_files = len(json_files)
    if job:
        job.update(
            total_files=total_files,
            detailed_status=f"Processing metadata for {total_files} videos",
        )
    entries: List[EpisodeMetadata] = []
    for json_file in json_files:
        with open(json_file, "r") as f:
            data = json.load(f)
        title = data.get("title", "Unknown Title")
        description = (
            data.get("description", "").split("\n")[0]
            if data.get("description")
            else ""
        )
        upload_date = data.get("upload_date", "")
        playlist_index = data.get("playlist_index", 0)
        base_file = str(json_file).replace(".info.json", "")

        entries.append(
            EpisodeMetadata(
                title=title,
                description=description,
                upload_date=upload_date,
                playlist_index=playlist_index,
                base_path=base_file,
            )
        )

    matches: List[EpisodeMatch]
    processed_seasons = set()
    if episode_mapper:
        try:
            matches = episode_mapper.map_episodes(entries)
        except EpisodeDetectionError as exc:
            if job:
                job.update(status="failed", message=str(exc), detailed_status=str(exc))
            log_job(job_id, logging.ERROR, str(exc))
            return []
    else:
        episode_offset = episode_start - first_index
        matches = []
        for entry in entries:
            new_ep = entry.playlist_index + episode_offset
            matches.append(
                EpisodeMatch(
                    season=int(season_num),
                    episode=int(new_ep),
                    air_date=_normalize_upload_date(entry.upload_date),
                    base_path=entry.base_path,
                    title=entry.title,
                    description=entry.description,
                )
            )

    seasons_last_episode: Dict[int, int] = {}
    for i, match in enumerate(matches):
        season_padded = f"{match.season:02d}"
        processed_seasons.add(season_padded)
        show_folder = Path(app.config["output_dir"]) / sanitize_name(show_name)
        dest_folder = show_folder / f"Season {season_padded}"
        dest_folder.mkdir(parents=True, exist_ok=True)

        file_name = os.path.basename(match.base_path)
        if job:
            job.update(
                file_name=file_name,
                processed_files=i + 1,
                detailed_status=f"Processing metadata: {file_name}",
                message=f"Processing metadata for {match.title}",
            )

        new_base = dest_folder / f"{match.title} S{season_padded}E{match.episode:02d}"
        clean_base = new_base
        if app.config.get("clean_filenames", True):
            clean_base = dest_folder / clean_filename(new_base.name)

        for ext in ["mp4", "mkv", "webm"]:
            original = f"{match.base_path}.{ext}"
            if os.path.exists(original):
                new_file = f"{clean_base}.{ext}"
                os.rename(original, new_file)
                if job:
                    job.update(message=f"Renamed file to {os.path.basename(new_file)}")
                break

        nfo_content = (
            "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>\n"
            "<episodedetails>\n"
            f"  <title>{match.title}</title>\n"
            f"  <season>{season_padded}</season>\n"
            f"  <episode>{match.episode:02d}</episode>\n"
            f"  <plot>{match.description}</plot>\n"
            f"  <aired>{match.air_date or ''}</aired>\n"
            "  <studio>YouTube</studio>\n"
            f"  <showtitle>{show_name}</showtitle>\n"
            "</episodedetails>\n"
        )
        nfo_file = f"{clean_base}.nfo"
        with open(nfo_file, "w") as f:
            f.write(nfo_content)
        if job:
            job.update(message=f"Created NFO file for {match.title}")

        json_file = f"{match.base_path}.info.json"
        if os.path.exists(json_file):
            os.remove(json_file)

        seasons_last_episode[match.season] = max(
            seasons_last_episode.get(match.season, 0), match.episode
        )

        if job and total_files:
            progress = int((i + 1) / total_files * 100)
            job.update(
                progress=progress,
                stage_progress=progress,
                detailed_status=f"Processed {i+1} of {total_files} files",
            )

    for season, last_ep in seasons_last_episode.items():
        app.update_last_episode(show_name, f"{season:02d}", last_ep)

    return sorted(processed_seasons)


def convert_video_files(app, folder: str, season_num: str, job_id: str) -> None:
    job = app.jobs.get(job_id)
    use_h265 = app.config["use_h265"]
    if job and job.use_h265_override is not None:
        use_h265 = job.use_h265_override
    if not use_h265:
        log_job(job_id, logging.INFO, "H.265 conversion disabled, skipping")
        if job:
            job.update(
                message="H.265 conversion disabled, skipping",
                detailed_status="H.265 conversion disabled",
            )
        return
    crf_value = app.config["crf"]
    if job and job.crf_override is not None:
        crf_value = job.crf_override
    if job:
        job.update(
            status="converting",
            stage="converting",
            progress=0,
            stage_progress=0,
            detailed_status="Preparing video conversion to H.265",
            message="Starting video conversion to H.265",
        )
    video_files = []
    for ext in ["webm", "mp4"]:
        video_files.extend(list(Path(folder).glob(f"*S{season_num}E*.{ext}")))
    total_files = len(video_files)
    if total_files == 0:
        if job:
            job.update(
                message="No video files found for conversion",
                detailed_status="No video files to convert",
            )
        return
    if job:
        job.update(
            total_files=total_files,
            detailed_status=f"Converting {total_files} video files to H.265",
        )
    for i, video in enumerate(video_files):
        ext = str(video).rsplit(".", 1)[1].lower()
        if ext == "mp4":
            probe_cmd = [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "json",
                str(video),
            ]
            result = subprocess.run(probe_cmd, capture_output=True, text=True)
            codec = (
                json.loads(result.stdout).get("streams", [{}])[0].get("codec_name", "")
            )
            if codec in ["hevc", "h265"]:
                log_job(
                    job_id,
                    logging.INFO,
                    f"Skipping already H.265 encoded file: {video}",
                )
                if job:
                    job.update(
                        processed_files=i + 1,
                        message=(
                            "Skipping already H.265 encoded file: "
                            f"{os.path.basename(str(video))}"
                        ),
                    )
                continue
        base = str(video).rsplit(".", 1)[0]
        temp_file = f"{base}.temp.mp4"
        cmd = [
            "ffmpeg",
            "-i",
            str(video),
            "-c:v",
            "libx265",
            "-preset",
            "medium",
            "-crf",
            str(crf_value),
            "-tag:v",
            "hvc1",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            temp_file,
        ]
        filename = os.path.basename(str(video))
        if job:
            job.update(
                file_name=filename,
                processed_files=i + 1,
                detailed_status=(
                    f"Converting {filename} to H.265 (file {i+1}/{total_files})"
                ),
                message=(f"Converting {filename} to H.265 ({i+1}/{total_files})"),
            )
        log_job(job_id, logging.INFO, f"Converting {video} to H.265")
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                start_new_session=True,
            )
            if job:
                job.process = process
            for line in process.stdout:
                if job and job.status == "cancelled":
                    terminate_process(process)
                    break
                logger.debug(line.strip())
                if job and "time=" in line:
                    try:
                        time_str = re.search(r"time=(\d+:\d+:\d+\.\d+)", line)
                        if time_str:
                            time_parts = time_str.group(1).split(":")
                            seconds = (
                                float(time_parts[0]) * 3600
                                + float(time_parts[1]) * 60
                                + float(time_parts[2])
                            )
                            duration_cmd = [
                                "ffprobe",
                                "-v",
                                "error",
                                "-show_entries",
                                "format=duration",
                                "-of",
                                "default=noprint_wrappers=1:nokey=1",
                                str(video),
                            ]
                            duration_result = subprocess.run(
                                duration_cmd, capture_output=True, text=True, check=True
                            )
                            duration = float(duration_result.stdout.strip())
                            if duration > 0:
                                file_progress = min(100, int(seconds / duration * 100))
                                total_progress = min(
                                    99,
                                    ((i) / total_files * 100)
                                    + (file_progress / total_files),
                                )
                                job.update(
                                    progress=total_progress,
                                    stage_progress=file_progress,
                                    detailed_status=(
                                        f"Converting {filename}: {file_progress}% "
                                        f"(file {i+1}/{total_files})"
                                    ),
                                )
                                if file_progress % 20 == 0:
                                    job.update(
                                        message=(
                                            f"Converting {filename}: {file_progress}% "
                                            f"complete"
                                        )
                                    )
                    except Exception as e:
                        log_job(job_id, logging.ERROR, f"Error parsing progress: {e}")
            process.wait()
            if job:
                job.process = None
            if process.returncode == 0:
                os.rename(temp_file, f"{base}.mp4")
                if str(video) != f"{base}.mp4":
                    os.remove(video)
                log_job(job_id, logging.INFO, f"Converted: {video} → {base}.mp4")
                if job:
                    job.update(
                        message=f"Successfully converted {filename} to H.265",
                        detailed_status=f"Converted {i+1}/{total_files} files",
                    )
            else:
                log_job(
                    job_id,
                    logging.ERROR,
                    f"Failed to convert {video}, return code: {process.returncode}",
                )
                if job:
                    job.update(
                        message=(
                            "Failed to convert "
                            f"{filename}, return code: {process.returncode}"
                        ),
                        detailed_status=f"Error converting {filename}",
                    )
                if os.path.exists(temp_file):
                    os.remove(temp_file)
        except subprocess.SubprocessError as e:
            log_job(job_id, logging.ERROR, f"Failed to convert {video}: {e}")
            if job:
                job.process = None
                job.update(
                    message=f"Failed to convert {filename}: {str(e)}",
                    detailed_status=f"Error converting {filename}",
                )
            if os.path.exists(temp_file):
                os.remove(temp_file)
    if job:
        job.update(
            progress=100,
            stage_progress=100,
            detailed_status="Video conversion completed",
            message="Video conversion completed",
        )


def convert_movie_file(app, folder: str, job_id: str) -> None:
    """Convert a downloaded movie to H.265 if enabled."""
    job = app.jobs.get(job_id)
    use_h265 = app.config["use_h265"]
    if job and job.use_h265_override is not None:
        use_h265 = job.use_h265_override
    if not use_h265:
        log_job(job_id, logging.INFO, "H.265 conversion disabled, skipping")
        if job:
            job.update(
                message="H.265 conversion disabled, skipping",
                detailed_status="H.265 conversion disabled",
            )
        return

    crf_value = app.config["crf"]
    if job and job.crf_override is not None:
        crf_value = job.crf_override
    if job:
        job.update(
            status="converting",
            stage="converting",
            progress=0,
            stage_progress=0,
            detailed_status="Preparing movie conversion to H.265",
            message="Starting movie conversion to H.265",
        )

    video_file = None
    for ext in ["webm", "mp4", "mkv"]:
        files = list(Path(folder).glob(f"*.{ext}"))
        if files:
            video_file = files[0]
            break

    if not video_file:
        if job:
            job.update(
                message="No movie file found for conversion",
                detailed_status="No movie file to convert",
            )
        log_job(job_id, logging.WARNING, "No movie file found for conversion")
        return

    ext = video_file.suffix.lower()[1:]
    if ext == "mp4":
        probe_cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name",
            "-of",
            "json",
            str(video_file),
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        codec = json.loads(result.stdout).get("streams", [{}])[0].get("codec_name", "")
        if codec in ["hevc", "h265"]:
            log_job(
                job_id,
                logging.INFO,
                f"Skipping already H.265 encoded file: {video_file}",
            )
            if job:
                job.update(
                    processed_files=1,
                    message=f"Skipping already H.265 encoded file: {video_file.name}",
                )
            return

    base = str(video_file).rsplit(".", 1)[0]
    temp_file = f"{base}.temp.mp4"
    cmd = [
        "ffmpeg",
        "-i",
        str(video_file),
        "-c:v",
        "libx265",
        "-preset",
        "medium",
        "-crf",
        str(crf_value),
        "-tag:v",
        "hvc1",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        temp_file,
    ]
    filename = video_file.name
    if job:
        job.update(
            file_name=filename,
            processed_files=1,
            detailed_status="Converting movie to H.265",
            message=f"Converting {filename} to H.265",
        )
    log_job(job_id, logging.INFO, f"Converting {video_file} to H.265")
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            start_new_session=True,
        )
        if job:
            job.process = process
        for line in process.stdout:
            if job and job.status == "cancelled":
                terminate_process(process)
                break
            logger.debug(line.strip())
            if job and "time=" in line:
                try:
                    time_str = re.search(r"time=(\d+:\d+:\d+\.\d+)", line)
                    if time_str:
                        time_parts = time_str.group(1).split(":")
                        seconds = (
                            float(time_parts[0]) * 3600
                            + float(time_parts[1]) * 60
                            + float(time_parts[2])
                        )
                        duration_cmd = [
                            "ffprobe",
                            "-v",
                            "error",
                            "-show_entries",
                            "format=duration",
                            "-of",
                            "default=noprint_wrappers=1:nokey=1",
                            str(video_file),
                        ]
                        duration_result = subprocess.run(
                            duration_cmd, capture_output=True, text=True, check=True
                        )
                        duration = float(duration_result.stdout.strip())
                        if duration > 0:
                            file_progress = min(100, int(seconds / duration * 100))
                            if job:
                                job.update(
                                    progress=file_progress,
                                    stage_progress=file_progress,
                                    detailed_status=(
                                        f"Converting {filename}: {file_progress}%"
                                    ),
                                )
                except Exception as e:
                    log_job(job_id, logging.ERROR, f"Error parsing progress: {e}")
        process.wait()
        if job:
            job.process = None
        if process.returncode == 0:
            os.rename(temp_file, f"{base}.mp4")
            if str(video_file) != f"{base}.mp4":
                os.remove(video_file)
            log_job(job_id, logging.INFO, f"Converted: {video_file} → {base}.mp4")
            if job:
                job.update(
                    progress=100,
                    stage_progress=100,
                    message=f"Successfully converted {filename} to H.265",
                    detailed_status="Movie conversion completed",
                )
        else:
            log_job(
                job_id,
                logging.ERROR,
                f"Failed to convert {video_file}, return code: {process.returncode}",
            )
            if job:
                job.update(
                    message=(
                        "Failed to convert "
                        f"{filename}, return code: {process.returncode}"
                    ),
                    detailed_status=f"Error converting {filename}",
                )
            if os.path.exists(temp_file):
                os.remove(temp_file)
    except subprocess.SubprocessError as e:
        log_job(job_id, logging.ERROR, f"Failed to convert {video_file}: {e}")
        if job:
            job.process = None
            job.update(
                message=f"Failed to convert {filename}: {str(e)}",
                detailed_status=f"Error converting {filename}",
            )
        if os.path.exists(temp_file):
            os.remove(temp_file)


def process_movie_metadata(
    app, folder: str, movie_name: str, job_id: str, json_index: int = 0
) -> None:
    job = app.jobs.get(job_id)
    if job:
        job.update(
            status="processing_metadata",
            stage="processing_metadata",
            progress=0,
            stage_progress=0,
            detailed_status="Processing movie metadata",
            message="Processing movie metadata",
        )
    json_files = sorted(Path(folder).glob("*.info.json"))
    if not json_files:
        if job:
            job.update(message="Warning: No JSON metadata file found")
        log_job(job_id, logging.WARNING, "No JSON metadata file found")
        return
    if len(json_files) > 1:
        log_job(job_id, logging.WARNING, "Multiple JSON metadata files found")
        if job:
            job.update(message="Warning: Multiple JSON metadata files found")
    if json_index >= len(json_files) or json_index < -len(json_files):
        log_job(job_id, logging.ERROR, "JSON metadata index out of range")
        if job:
            job.update(message="Error: JSON metadata index out of range")
        return
    with open(json_files[json_index], "r") as f:
        data = json.load(f)
    description = (
        data.get("description", "").split("\n")[0] if data.get("description") else ""
    )
    upload_date = data.get("upload_date", "")
    year = upload_date[:4] if len(upload_date) >= 4 else ""
    video_id = data.get("id", "")

    tmdb_data = None
    api_key = app.config.get("tmdb_api_key")
    if api_key:
        search_title = tmdb.clean_title(movie_name)
        try:
            result = tmdb.search_movie(search_title, year, api_key)
            if result:
                tmdb_data = tmdb.fetch_movie_details(result["id"], api_key)
        except Exception as e:  # network or api errors should not fail job
            log_job(job_id, logging.ERROR, f"TMDb lookup failed: {e}")

    if tmdb_data:
        title = tmdb_data.get("title", movie_name)
        plot = tmdb_data.get("overview", description)
        year = tmdb_data.get("release_date", "")[:4]
        tmdb_id = tmdb_data.get("id")
        poster_path = tmdb_data.get("poster_path")
        genres = [g["name"] for g in tmdb_data.get("genres", [])]
        actors = [
            c.get("name") for c in tmdb_data.get("credits", {}).get("cast", [])[:5]
        ]
        base_name = f"{title}"
        if year:
            base_name += f" ({year})"
        if tmdb_id:
            base_name += f" [tmdb{tmdb_id}]"
        base_name = clean_filename(sanitize_name(base_name))
    else:
        title = movie_name
        plot = description
        tmdb_id = video_id
        genres = []
        actors = []
        base_name = movie_name
        if year:
            base_name += f" ({year})"
        if video_id:
            base_name += f" [{video_id}]"
        base_name = clean_filename(sanitize_name(base_name))
    video_file = None
    for ext in ["mp4", "mkv", "webm"]:
        files = list(Path(folder).glob(f"*.{ext}"))
        if files:
            video_file = files[0]
            break
    if video_file:
        new_file = Path(folder) / f"{base_name}{video_file.suffix}"
        os.rename(video_file, new_file)
        if job:
            job.update(message=f"Renamed movie file to {new_file.name}")
    if tmdb_data and poster_path:
        try:
            tmdb.download_poster(poster_path, str(Path(folder) / "poster.jpg"), api_key)
        except Exception as e:
            log_job(job_id, logging.ERROR, f"Failed to download poster: {e}")
    nfo_content = (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>\n"
        "<movie>\n"
        f"  <title>{title}</title>\n"
        f"  <plot>{plot}</plot>\n"
        f"  <studio>YouTube</studio>\n"
    )
    if year:
        nfo_content += f"  <year>{year}</year>\n"
    if tmdb_id:
        nfo_content += f"  <id>{tmdb_id}</id>\n"
    for g in genres:
        nfo_content += f"  <genre>{g}</genre>\n"
    for actor in actors:
        nfo_content += "  <actor>\n    <name>{}</name>\n  </actor>\n".format(actor)
    nfo_content += "</movie>\n"
    with open(Path(folder) / "movie.nfo", "w") as f:
        f.write(nfo_content)
    if job:
        job.update(progress=100, stage_progress=100, message="Movie metadata processed")
    for jf in json_files:
        os.remove(jf)


def generate_movie_artwork(app, folder: str, job_id: str) -> None:
    """Generate a simple poster for a movie from extracted frames."""
    job = app.jobs.get(job_id)
    if job:
        job.update(status="generating_artwork", message="Generating movie artwork")

    video_files = []
    for ext in ["mp4", "mkv", "webm"]:
        video_files.extend(Path(folder).glob(f"*.{ext}"))

    if not video_files:
        logger.warning("No movie file found for artwork generation")
        if job:
            job.update(message="No movie file found for artwork generation")
        return

    movie_file = video_files[0]
    try:
        frames_dir = os.path.join(app.temp_dir, "movie_frames")
        os.makedirs(frames_dir, exist_ok=True)
        frame_pattern = os.path.join(frames_dir, "frame_%03d.jpg")
        run_subprocess(
            [
                "ffmpeg",
                "-i",
                str(movie_file),
                "-vf",
                r"select=not(mod(n\,1000)),scale=640:360",
                "-vframes",
                "3",
                frame_pattern,
            ],
            check=True,
            capture_output=True,
        )
        frame_files = sorted(Path(frames_dir).glob("frame_*.jpg"))
        if frame_files:
            poster_path = Path(folder) / "poster.jpg"
            run_subprocess(
                [
                    "convert",
                    *[str(f) for f in frame_files],
                    "-append",
                    str(poster_path),
                ],
                check=True,
            )
            if job:
                job.update(progress=100, message="Created movie poster")
    except (subprocess.CalledProcessError, OSError) as e:
        log_job(job_id, logging.ERROR, f"Error generating movie artwork: {e}")
        if job:
            job.update(message=f"Error generating movie artwork: {str(e)}")


def generate_artwork(
    app, folder: str, show_name: str, season_num: str, job_id: str
) -> None:
    job = app.jobs.get(job_id)
    if job:
        job.update(
            status="generating_artwork", message="Generating thumbnails and artwork"
        )
    show_folder = str(Path(folder).parent)
    episodes = list(Path(folder).glob(f"*S{season_num}E*.mp4"))
    if not episodes:
        log_job(job_id, logging.WARNING, "No episodes found for artwork generation")
        if job:
            job.update(message="No episodes found for artwork generation")
        return
    try:
        if job:
            job.update(progress=30, message="Creating show and season artwork")
        temp_posters = []
        for i, episode in enumerate(episodes[:1]):
            poster_file = os.path.join(app.temp_dir, f"tmp_poster_{i:03d}.jpg")
            filter_str = r"select=not(mod(n\,1000)),scale=640:360"
            run_subprocess(
                [
                    "ffmpeg",
                    "-i",
                    str(episode),
                    "-vf",
                    filter_str,
                    "-vframes",
                    "3",
                    poster_file,
                ],
                check=True,
                capture_output=True,
            )
            temp_posters.append(poster_file)
        if temp_posters:
            poster_path = os.path.join(show_folder, "poster.jpg")
            run_subprocess(
                [
                    "convert",
                    *temp_posters,
                    "-gravity",
                    "Center",
                    "-background",
                    "Black",
                    "-resize",
                    "1000x1500^",
                    "-extent",
                    "1000x1500",
                    "-pointsize",
                    "80",
                    "-fill",
                    "white",
                    "-gravity",
                    "south",
                    "-annotate",
                    "+0+50",
                    show_name,
                    poster_path,
                ],
                check=True,
            )
            if job:
                job.update(progress=60, message="Created show poster")
        season_frames_dir = os.path.join(app.temp_dir, "season_frames")
        os.makedirs(season_frames_dir, exist_ok=True)
        for i, episode in enumerate(episodes[:6]):
            frame_file = os.path.join(season_frames_dir, f"frame_{i:03d}.jpg")
            run_subprocess(
                [
                    "ffmpeg",
                    "-i",
                    str(episode),
                    "-vf",
                    "thumbnail",
                    "-frames:v",
                    "1",
                    frame_file,
                ],
                check=True,
                capture_output=True,
            )
        season_frames = list(Path(season_frames_dir).glob("*.jpg"))
        if season_frames:
            montage_args = [
                "montage",
                "-geometry",
                "400x225+5+5",
                "-background",
                "black",
                "-tile",
                "3x2",
                *[str(f) for f in season_frames],
                "-",
            ]
            convert_args = [
                "convert",
                "-",
                "-resize",
                "1000x1500",
                "-",
                "-gravity",
                "south",
                "-background",
                "#00000080",
                "-splice",
                "0x60",
                "-pointsize",
                "48",
                "-fill",
                "white",
                "-annotate",
                "+0+20",
                f"Season {season_num}",
                f"{folder}/season{season_num}-poster.jpg",
            ]
            p1 = subprocess.Popen(
                montage_args,
                stdout=subprocess.PIPE,
                start_new_session=True,
            )
            p2 = subprocess.Popen(
                convert_args,
                stdin=p1.stdout,
                start_new_session=True,
            )
            p2.communicate()
            run_subprocess(
                [
                    "convert",
                    f"{folder}/season{season_num}-poster.jpg",
                    "-resize",
                    "1000x562!",
                    f"{folder}/season{season_num}.jpg",
                ],
                check=True,
            )
            if job:
                job.update(progress=100, message="Created season artwork")
        for i, video in enumerate(episodes):
            video_base = str(video).rsplit(".", 1)[0]
            basename = os.path.basename(video_base)
            if app.config.get("clean_filenames", True):
                basename = clean_filename(basename)
            thumb_path = os.path.join(
                os.path.dirname(video_base), f"{basename}-thumb.jpg"
            )
            try:
                subprocess.run(
                    [
                        "ffmpeg",
                        "-ss",
                        "00:01:30",
                        "-i",
                        str(video),
                        "-vframes",
                        "1",
                        "-q:v",
                        "2",
                        thumb_path,
                    ],
                    check=True,
                    capture_output=True,
                )
                log_job(
                    job_id,
                    logging.INFO,
                    f"Generated thumbnail: {thumb_path}",
                )
            except subprocess.CalledProcessError:
                log_job(
                    job_id,
                    logging.ERROR,
                    f"Failed to generate thumbnail for {video}",
                )
                if job:
                    job.update(
                        message=(
                            "Failed to generate thumbnail for "
                            f"{os.path.basename(str(video))}"
                        )
                    )
    except (subprocess.CalledProcessError, OSError) as e:
        log_job(job_id, logging.ERROR, f"Error generating artwork: {e}")
        if job:
            job.update(message=f"Error generating artwork: {str(e)}")


def create_nfo_files(
    app, folder: str, show_name: str, season_num: str, job_id: str
) -> None:
    job = app.jobs.get(job_id)
    if job:
        job.update(status="creating_nfo", message="Creating NFO files")
    show_folder = str(Path(folder).parent)
    season_nfo = (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>\n"
        "<season>\n"
        f"  <seasonnumber>{season_num}</seasonnumber>\n"
        f"  <title>Season {season_num}</title>\n"
        f"  <plot>Season {season_num} of {show_name}</plot>\n"
        "</season>\n"
    )
    with open(f"{folder}/season.nfo", "w") as f:
        f.write(season_nfo)
    tvshow_nfo = (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>\n"
        "<tvshow>\n"
        f"  <title>{show_name}</title>\n"
        "  <studio>YouTube</studio>\n"
        "</tvshow>\n"
    )
    with open(f"{show_folder}/tvshow.nfo", "w") as f:
        f.write(tvshow_nfo)
    if job:
        job.update(progress=100, message="Created NFO files")


def fetch_book_cover(
    app,
    title: str,
    author: str,
    folder: str,
    job_id: str,
    fallback_url: Optional[str] = None,
) -> Optional[Path]:
    """Fetch cover art for an audiobook using the Google Books API."""

    job = app.jobs.get(job_id)
    query_parts = []
    if title:
        query_parts.append(f"intitle:{title}")
    if author:
        query_parts.append(f"inauthor:{author}")
    query = "+".join(part.replace(" ", "+") for part in query_parts)
    api_url = f"https://www.googleapis.com/books/v1/volumes?q={query or title or author}".strip()

    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        image_url = None
        for item in data.get("items", []):
            links = item.get("volumeInfo", {}).get("imageLinks") or {}
            image_url = links.get("thumbnail") or links.get("smallThumbnail")
            if image_url:
                break

        if not image_url:
            image_url = fallback_url

        if not image_url:
            return None

        cover_response = requests.get(image_url, timeout=10)
        cover_response.raise_for_status()
        cover_path = Path(folder) / "cover.jpg"
        cover_path.write_bytes(cover_response.content)
        if job:
            job.update(
                message="Fetched audiobook cover art",
                detailed_status="Downloaded cover image",
            )
        log_job(job_id, logging.INFO, f"Saved audiobook cover art to {cover_path}")
        return cover_path
    except Exception as exc:  # pragma: no cover - defensive logging
        log_job(job_id, logging.WARNING, f"Unable to fetch cover art: {exc}")
        if job:
            job.update(message="Unable to fetch cover art automatically")
        return None


def download_audiobook_audio(app, url: str, folder: str, job_id: str) -> Optional[Path]:
    """Download a single audiobook audio source using yt-dlp."""

    output_template = f"{folder}/%(title)s.%(ext)s"
    ytdlp_path = app.config["ytdlp_path"]
    if not os.path.isabs(ytdlp_path):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_ytdlp = os.path.join(script_dir, ytdlp_path)
        if os.path.exists(local_ytdlp) and os.access(local_ytdlp, os.X_OK):
            ytdlp_path = local_ytdlp

    cmd = [
        ytdlp_path,
        "--ignore-errors",
        "--no-warnings",
        "-f",
        "bestaudio/best",
        "-o",
        output_template,
        "--write-info-json",
        "--restrict-filenames",
        "--progress",
        "--no-playlist",
        "--no-cookies-from-browser",
        url,
    ]

    if app.config.get("cookies") and os.path.exists(app.config["cookies"]):
        cmd.insert(1, f'--cookies={app.config["cookies"]}')
    else:
        cmd.insert(1, "--no-cookies")

    job = app.jobs.get(job_id)
    if job:
        job.update(
            status="downloading",
            stage="downloading_audio",
            progress=0,
            detailed_status="Downloading audiobook audio",
            message=f"Starting audiobook download: {url}",
        )

    log_job(job_id, logging.INFO, f"Starting audiobook download from {url}")

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            start_new_session=True,
        )
        if job:
            job.process = process

        for raw_line in process.stdout:
            if job and job.status == "cancelled":
                terminate_process(process)
                break
            line = raw_line.strip()
            log_job(job_id, logging.INFO, line)
            if job and "Destination:" in line:
                job.update(detailed_status=line)

        process.wait()
        if process.returncode not in (0, None):
            raise subprocess.CalledProcessError(process.returncode, cmd)
    except Exception as exc:
        log_job(job_id, logging.ERROR, f"Audiobook download error: {exc}")
        if job:
            job.update(status="failed", message=f"Download failed: {exc}")
        return None

    audio_exts = {".mp3", ".m4a", ".opus", ".ogg", ".webm", ".flac", ".wav", ".aac"}
    downloaded = [
        p
        for p in Path(folder).iterdir()
        if p.suffix.lower() in audio_exts and not p.name.startswith("._")
    ]
    downloaded.sort()
    if job:
        job.update(
            status="downloaded",
            stage="downloading_audio",
            stage_progress=100,
            detailed_status="Audiobook download completed",
            message="Finished downloading audiobook audio",
        )
    return downloaded[0] if downloaded else None


def build_audiobook_file(
    app,
    source_path: Path,
    folder: str,
    title: str,
    author: str,
    cover_path: Optional[Path],
    job_id: str,
) -> Optional[Path]:
    """Convert audio to an M4B with embedded metadata and cover art."""

    job = app.jobs.get(job_id)
    safe_title = sanitize_name(title) or "Audiobook"
    target = Path(folder) / f"{safe_title}.m4b"
    cmd = ["ffmpeg", "-y", "-i", str(source_path)]

    if cover_path and Path(cover_path).exists():
        cmd.extend(
            [
                "-i",
                str(cover_path),
                "-map",
                "0:a",
                "-map",
                "1",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-c:v",
                "mjpeg",
                "-disposition:v:0",
                "attached_pic",
            ]
        )
    else:
        cmd.extend(["-vn", "-c:a", "aac", "-b:a", "128k"])

    cmd.extend(
        [
            "-metadata",
            f"title={title}",
            "-metadata",
            f"album={title}",
            "-metadata",
            f"artist={author}",
            "-metadata",
            f"album_artist={author}",
            "-metadata",
            f"author={author}",
            "-movflags",
            "+faststart",
            str(target),
        ]
    )

    if job:
        job.update(
            stage="converting_audio",
            detailed_status="Building M4B audiobook",
            message=f"Creating M4B for {title}",
        )

    result = run_subprocess(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log_job(
            job_id,
            logging.ERROR,
            f"ffmpeg failed creating audiobook: {result.stderr}",
        )
        if job:
            job.update(status="failed", message="Failed to create audiobook")
        return None

    try:
        if source_path.exists():
            source_path.unlink()
    except OSError:
        pass

    if job:
        job.update(
            status="processing_metadata",
            detailed_status="Finished encoding audiobook",
        )

    return target


def download_music_tracks(
    app,
    playlist_url: str,
    folder: str,
    job_id: str,
    playlist_start: Optional[int] = None,
) -> List[Path]:
    """Download playlist audio tracks using yt-dlp bestaudio profile."""

    output_template = f"{folder}/%(playlist_index)03d - %(title)s.%(ext)s"
    ytdlp_path = app.config["ytdlp_path"]
    if not os.path.isabs(ytdlp_path):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_ytdlp = os.path.join(script_dir, ytdlp_path)
        if os.path.exists(local_ytdlp) and os.access(local_ytdlp, os.X_OK):
            ytdlp_path = local_ytdlp

    cmd = [
        ytdlp_path,
        "--ignore-errors",
        "--no-warnings",
        "-f",
        "bestaudio/best",
        "-o",
        output_template,
        "--write-info-json",
        "--restrict-filenames",
        "--progress",
        "--no-cookies-from-browser",
        playlist_url,
    ]

    archive_file = app._get_archive_file(playlist_url)
    os.makedirs(os.path.dirname(archive_file), exist_ok=True)
    cmd.extend(["--download-archive", archive_file])
    if playlist_start:
        cmd.extend(["--playlist-start", str(playlist_start)])
    if app.config["cookies"] and os.path.exists(app.config["cookies"]):
        cmd.insert(1, f'--cookies={app.config["cookies"]}')
    else:
        cmd.insert(1, "--no-cookies")

    job = app.jobs.get(job_id)
    if job:
        job.update(
            status="downloading",
            stage="downloading_audio",
            progress=0,
            stage_progress=0,
            detailed_status="Starting audio download",
            message=f"Downloading audio playlist: {playlist_url}",
        )

    log_job(job_id, logging.INFO, f"Starting audio download for playlist: {playlist_url}")

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            start_new_session=True,
        )
        if job:
            job.process = process
        total_items = 0
        processed = 0
        current_file = ""
        for raw_line in process.stdout:
            if job and job.status == "cancelled":
                terminate_process(process)
                break
            line = raw_line.strip()
            log_job(job_id, logging.INFO, line)
            if job:
                if "Destination:" in line:
                    match = re.search(r"Destination:\s+(.+)", line)
                    if match:
                        current_file = os.path.basename(match.group(1))
                        processed += 1
                        if job.remaining_files:
                            job.remaining_files.pop(0)
                        job.update(
                            processed_files=processed,
                            file_name=current_file,
                            detailed_status=f"Downloading: {current_file}",
                            message=f"Downloading {current_file}",
                        )
                elif "[download]" in line and "of" in line and "item" in line:
                    total_match = re.search(r"of\s+(\d+)\s+item", line)
                    if total_match:
                        total_items = int(total_match.group(1))
                        job.update(total_files=total_items)
                elif "%" in line:
                    progress_match = re.search(r"(\d+\.\d+)%", line)
                    if progress_match:
                        progress_value = float(progress_match.group(1))
                        overall = progress_value
                        if total_items:
                            overall = min(
                                98,
                                ((processed - 1) / max(total_items, 1) * 100)
                                + (progress_value / max(total_items, 1)),
                            )
                        job.update(
                            progress=overall,
                            stage_progress=progress_value,
                            detailed_status=(
                                f"Downloading: {current_file} ({progress_value:.1f}%)"
                            ),
                        )
                else:
                    job.update(message=line)

        process.wait()
        if job:
            job.process = None
        if process.returncode != 0:
            if job:
                job.update(
                    status="failed",
                    stage="failed",
                    detailed_status="Audio download failed",
                    message=f"yt-dlp exited with code {process.returncode}",
                )
            log_job(
                job_id,
                logging.ERROR,
                f"Audio download failed with return code {process.returncode}",
            )
            return []
    except Exception as exc:
        if job:
            job.update(
                status="failed",
                stage="failed",
                detailed_status="Audio download failed",
                message=f"Audio download error: {exc}",
            )
        log_job(job_id, logging.ERROR, f"Audio download error: {exc}")
        return []

    audio_exts = {".mp3", ".m4a", ".opus", ".ogg", ".webm", ".flac", ".wav", ".aac"}
    downloaded = [
        p
        for p in Path(folder).iterdir()
        if p.suffix.lower() in audio_exts and not p.name.startswith("._")
    ]
    downloaded.sort()

    if job:
        job.update(
            status="downloaded",
            stage="downloading_audio",
            progress=100,
            stage_progress=100,
            detailed_status="Audio download completed",
            message="Finished downloading audio tracks",
        )

    return downloaded


def _ensure_mp3(
    source: Path,
    job_id: str,
    job,
) -> Path:
    """Convert audio file to MP3 if not already MP3."""
    if source.suffix.lower() == ".mp3":
        return source

    target = source.with_suffix(".mp3")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-vn",
        "-ar",
        "44100",
        "-ac",
        "2",
        "-b:a",
        "320k",
        str(target),
    ]

    if job:
        job.update(
            stage="converting_audio",
            detailed_status=f"Converting {source.name} to MP3",
            message=f"Converting {source.name} to MP3",
        )

    log_job(job_id, logging.INFO, f"Converting {source.name} to MP3 via ffmpeg")
    result = run_subprocess(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log_job(
            job_id,
            logging.ERROR,
            f"ffmpeg failed for {source.name}: {result.stderr}",
        )
        raise RuntimeError(f"ffmpeg conversion failed for {source.name}")

    source.unlink()
    return target


def _apply_track_metadata(
    file_path: Path,
    metadata: "TrackMetadata",
    job_id: str,
) -> None:
    """Apply ID3 tags to MP3 file using mutagen."""
    try:
        tags = ID3(str(file_path))
        tags.clear()
    except ID3NoHeaderError:
        tags = ID3()

    tags.add(TIT2(encoding=3, text=metadata.title))
    tags.add(TPE1(encoding=3, text=metadata.artist))
    tags.add(TALB(encoding=3, text=metadata.album))
    album_artist = metadata.album_artist or metadata.artist
    tags.add(TPE2(encoding=3, text=album_artist))

    track_text = str(metadata.track_number)
    if metadata.total_tracks:
        track_text = f"{track_text}/{metadata.total_tracks}"
    tags.add(TRCK(encoding=3, text=track_text))
    if metadata.disc_number:
        disc_text = str(metadata.disc_number)
        if metadata.total_discs:
            disc_text = f"{disc_text}/{metadata.total_discs}"
        tags.add(TPOS(encoding=3, text=disc_text))
    if metadata.release_date:
        tags.add(TDRC(encoding=3, text=str(metadata.release_date)))
    if metadata.genres:
        tags.add(TCON(encoding=3, text=", ".join(metadata.genres) if isinstance(metadata.genres, list) else metadata.genres))

    cover_url = metadata.cover_url or (metadata.extra.get("cover_url") if metadata.extra else None)
    if cover_url:
        try:
            response = requests.get(cover_url, timeout=15)
            response.raise_for_status()
            image_data = response.content
            tags.add(
                APIC(
                    encoding=3,
                    mime="image/jpeg",
                    type=3,
                    desc="Cover",
                    data=image_data,
                )
            )
        except Exception as exc:
            log_job(job_id, logging.WARNING, f"Failed to download cover art: {exc}")

    tags.save(str(file_path))
    log_job(job_id, logging.INFO, f"Applied ID3 tags to {file_path.name}")


def prepare_music_tracks(
    app,
    folder: str,
    tracks: Sequence["TrackMetadata"],
    downloaded_files: Sequence[Path],
    job_id: str,
) -> List[Path]:
    """Process downloaded audio tracks: convert to MP3, rename, and tag."""
    job = app.jobs.get(job_id)
    prepared_files: List[Path] = []
    total = min(len(tracks), len(downloaded_files))

    if job:
        job.update(
            stage="processing_tracks",
            detailed_status=f"Processing {total} tracks",
            total_files=total,
            processed_files=0,
        )

    for index, (track_meta, source_path) in enumerate(
        zip(tracks, downloaded_files), start=1
    ):
        if job and job.status == "cancelled":
            break

        if job:
            job.update(
                current_file=source_path.name,
                detailed_status=f"Preparing track {index}/{total}: {track_meta.title}",
            )

        try:
            mp3_path = _ensure_mp3(source_path, job_id, job)
        except RuntimeError:
            return prepared_files

        clean_title = track_meta.title
        if app.config.get("clean_filenames", True):
            clean_title = clean_filename(clean_title)
        sanitized_title = sanitize_name(clean_title)
        final_name = f"{track_meta.track_number:02d} - {sanitized_title}.mp3"
        final_path = Path(folder) / final_name
        if mp3_path != final_path:
            if final_path.exists():
                final_path.unlink()
            mp3_path.rename(final_path)

        if job:
            job.update(stage="tagging", detailed_status=f"Tagging {track_meta.title}")

        _apply_track_metadata(final_path, track_meta, job_id)
        prepared_files.append(final_path)

        if job:
            remaining = list(job.remaining_files)
            if remaining:
                remaining.pop(0)
                job.remaining_files = remaining
            job.update(
                processed_files=index,
                progress=min(95, int(index / max(total, 1) * 90)),
                file_name=final_path.name,
                message=f"Processed track {track_meta.track_number}: {track_meta.title}",
            )

    return prepared_files


def list_media(app) -> List[Dict]:
    media = []
    output_dir = Path(app.config["output_dir"])
    if not output_dir.exists():
        return media
    for show_dir in output_dir.iterdir():
        if not show_dir.is_dir():
            continue
        show = {
            "name": show_dir.name,
            "path": str(show_dir),
            "seasons": [],
        }

        poster_file = show_dir / "poster.jpg"
        if poster_file.exists():
            show["poster"] = os.path.relpath(poster_file, output_dir)

        episode_total = 0

        for season_dir in show_dir.iterdir():
            if not season_dir.is_dir() or not season_dir.name.startswith("Season "):
                continue
            season = {
                "name": season_dir.name,
                "path": str(season_dir),
                "episodes": [],
            }

            match = re.search(r"(\d+)", season_dir.name)
            season_num = match.group(1) if match else ""

            season_poster = season_dir / f"season{season_num}-poster.jpg"
            if season_poster.exists():
                season["poster"] = os.path.relpath(season_poster, output_dir)
            for episode_file in season_dir.glob("*.mp4"):
                match = re.search(r"S(\d+)E(\d+)", episode_file.name)
                episode_num = int(match.group(2)) if match else None
                episode = {
                    "name": episode_file.stem,
                    "path": str(episode_file),
                    "size": episode_file.stat().st_size,
                    "modified": datetime.fromtimestamp(
                        episode_file.stat().st_mtime
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                    "episode_num": episode_num,
                }
                season["episodes"].append(episode)
                episode_total += 1

            def sort_key(e):
                ep_num = e.get("episode_num")
                return (ep_num is None, ep_num if ep_num is not None else e["name"])

            season["episodes"].sort(key=sort_key)
            show["seasons"].append(season)
        show["seasons"].sort(key=lambda s: s["name"])
        show["episode_count"] = episode_total
        media.append(show)
    return media


def list_movies(app) -> List[Dict]:
    movies = []
    output_dir = Path(app.config["output_dir"])
    if not output_dir.exists():
        return movies
    for movie_dir in output_dir.iterdir():
        if not movie_dir.is_dir():
            continue
        if any(
            sd.is_dir() and sd.name.startswith("Season ") for sd in movie_dir.iterdir()
        ):
            continue
        movie_file = None
        for ext in ["mp4", "mkv", "webm"]:
            candidate = movie_dir / f"{movie_dir.name}.{ext}"
            if candidate.exists():
                movie_file = candidate
                break
        if not movie_file:
            for ext in ["mp4", "mkv", "webm"]:
                files = list(movie_dir.glob(f"*.{ext}"))
                if files:
                    movie_file = files[0]
                    break
        if movie_file:
            poster_file = movie_dir / "poster.jpg"
            movies.append(
                {
                    "name": movie_dir.name,
                    "path": str(movie_file),
                    "size": movie_file.stat().st_size,
                    "modified": datetime.fromtimestamp(
                        movie_file.stat().st_mtime
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                    "poster": (
                        os.path.relpath(poster_file, output_dir)
                        if poster_file.exists()
                        else None
                    ),
                }
            )
    return movies


def get_playlist_videos(app, url: str) -> List[Dict]:
    try:
        result = subprocess.run(
            [
                app.config["ytdlp_path"],
                "--flat-playlist",
                "--dump-single-json",
                url,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        entries = data.get("entries", [])
        videos = []
        for idx, entry in enumerate(entries, start=1):
            videos.append(
                {"index": idx, "id": entry.get("id"), "title": entry.get("title")}
            )
        return videos
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        logger.error(f"Failed to fetch playlist info: {e}")
        return []


def get_music_playlist_details(app, url: str) -> Dict:
    """Return rich metadata for a music playlist, album or track list."""

    try:
        result = subprocess.run(
            [
                app.config["ytdlp_path"],
                "--dump-single-json",
                url,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        logger.error(f"Failed to fetch music playlist info: {exc}")
        return {"entries": []}

    entries = data.get("entries") or []
    playlist_title = data.get("title") or data.get("playlist") or ""
    uploader = data.get("uploader") or data.get("channel") or ""
    playlist_thumbs = data.get("thumbnails") or []
    cover_url = None
    if playlist_thumbs:
        cover_url = max(
            playlist_thumbs,
            key=lambda t: (t.get("width", 0) or 0) * (t.get("height", 0) or 0),
        ).get("url")

    normalized_entries: List[Dict] = []
    for idx, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            continue
        thumbs = entry.get("thumbnails") or []
        thumb_url = None
        if thumbs:
            thumb_url = max(
                thumbs,
                key=lambda t: (t.get("width", 0) or 0) * (t.get("height", 0) or 0),
            ).get("url")

        release_year = entry.get("release_year")
        if not release_year:
            release_date = entry.get("release_date")
            if release_date:
                release_year = str(release_date)[:4]

        normalized_entries.append(
            {
                "index": idx,
                "id": entry.get("id"),
                "title": entry.get("title") or f"Track {idx}",
                "duration": entry.get("duration"),
                "channel": entry.get("channel"),
                "artist": entry.get("artist") or entry.get("uploader"),
                "album": entry.get("album") or playlist_title,
                "release_year": release_year,
                "webpage_url": entry.get("webpage_url")
                or entry.get("url")
                or _entry_source_url(entry),
                "thumbnail": thumb_url,
                "track_number": entry.get("track_number") or idx,
                "disc_number": entry.get("disc_number") or 1,
                "tags": entry.get("tags") or [],
            }
        )

    return {
        "title": playlist_title,
        "uploader": uploader,
        "uploader_id": data.get("uploader_id"),
        "entries": normalized_entries,
        "webpage_url": data.get("webpage_url") or url,
        "thumbnail": cover_url,
        "description": data.get("description"),
    }


def _entry_source_url(entry: Dict) -> str:
    for key in ("original_url", "url", "webpage_url"):
        value = entry.get(key)
        if value:
            return value
    return ""


__all__ = [
    "create_folder_structure",
    "create_movie_folder",
    "create_audiobook_folder",
    "download_playlist",
    "write_m3u_playlist",
    "fetch_book_cover",
    "process_metadata",
    "process_movie_metadata",
    "convert_movie_file",
    "convert_video_files",
    "download_audiobook_audio",
    "build_audiobook_file",
    "generate_movie_artwork",
    "generate_artwork",
    "create_nfo_files",
    "list_media",
    "list_movies",
    "get_playlist_videos",
    "get_music_playlist_details",
]
