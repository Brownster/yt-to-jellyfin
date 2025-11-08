import os
import uuid
import threading
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config import logger
from .utils import terminate_process


@dataclass
class TrackMetadata:
    """Metadata describing a single music track."""

    title: str
    artist: str
    album: str
    track_number: int
    total_tracks: Optional[int] = None
    disc_number: Optional[int] = None
    total_discs: Optional[int] = None
    release_date: Optional[str] = None
    genres: List[str] = field(default_factory=list)
    cover_url: Optional[str] = None
    album_artist: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


class DownloadJob:
    """Class to track the status of a download job."""

    def __init__(
        self,
        job_id,
        playlist_url,
        show_name,
        season_num,
        episode_start,
        playlist_start=None,
        media_type="tv",
        movie_name="",
        album_name="",
        artist_name="",
        tracks: Optional[List[TrackMetadata]] = None,
        subscription_id=None,
        music_request=None,
    ):
        self.job_id = job_id
        self.playlist_url = playlist_url
        self.show_name = show_name
        self.season_num = season_num
        self.episode_start = episode_start
        self.playlist_start = playlist_start
        self.media_type = media_type
        self.movie_name = movie_name
        self.album_name = album_name
        self.artist_name = artist_name
        self.tracks: List[TrackMetadata] = tracks or []
        self.subscription_id = subscription_id
        self.music_request = music_request or {}
        self.status = "queued"
        self.progress = 0
        self.messages = []
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.process: Optional[subprocess.Popen] = None
        self.current_stage = "waiting"
        self.stage_progress = 0
        self.current_file = ""
        self.total_files = 0
        self.processed_files = 0
        self.detailed_status = "Job queued"
        self.remaining_files: List[str] = []

    def update(
        self,
        status=None,
        progress=None,
        message=None,
        stage=None,
        file_name=None,
        stage_progress=None,
        total_files=None,
        processed_files=None,
        detailed_status=None,
    ):
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
        if message:
            if stage and not detailed_status:
                stage_desc = {
                    "waiting": "Waiting to start",
                    "downloading": "Downloading videos",
                    "processing_metadata": "Processing metadata",
                    "converting": "Converting videos to H.265",
                    "generating_artwork": "Generating artwork and thumbnails",
                    "creating_nfo": "Creating NFO files",
                    "completed": "Processing completed",
                    "failed": "Processing failed",
                }
                prefix = f"[{stage_desc.get(stage, stage)}]"
                message = f"{prefix} {message}"
            self.messages.append(
                {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "text": message}
            )
        self.updated_at = datetime.now()

    def to_dict(
        self, include_messages: bool = True, message_limit: Optional[int] = None
    ):
        messages = []
        if include_messages:
            if message_limit is not None:
                messages = self.messages[-message_limit:]
            else:
                messages = self.messages
        return {
            "job_id": self.job_id,
            "playlist_url": self.playlist_url,
            "show_name": self.show_name,
            "season_num": self.season_num,
            "episode_start": self.episode_start,
            "playlist_start": self.playlist_start,
            "media_type": self.media_type,
            "movie_name": self.movie_name,
            "subscription_id": self.subscription_id,
            "music_request": self.music_request,
            "status": self.status,
            "progress": self.progress,
            "messages": messages,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            "current_stage": self.current_stage,
            "stage_progress": self.stage_progress,
            "current_file": self.current_file,
            "total_files": self.total_files,
            "processed_files": self.processed_files,
            "detailed_status": self.detailed_status,
            "remaining_files": self.remaining_files,
        }


# Job management helper functions


def create_job(
    app,
    playlist_url: str,
    show_name: str,
    season_num: str,
    episode_start: str,
    playlist_start: Optional[int] = None,
    track_playlist: bool = True,
    subscription_id: Optional[str] = None,
    *,
    start_thread: bool = True,
) -> str:
    job_id = str(uuid.uuid4())
    job = DownloadJob(
        job_id,
        playlist_url,
        show_name,
        season_num,
        episode_start,
        playlist_start,
        subscription_id=subscription_id,
    )

    try:
        ep_start_num = int(episode_start)
    except ValueError:
        ep_start_num = 1
    try:
        videos = app.get_playlist_videos(playlist_url)
        start_idx = playlist_start or 1
        for i, entry in enumerate(videos[start_idx - 1 :], start=ep_start_num):
            job.remaining_files.append(
                f"{entry.get('title', 'Video')} S{season_num}E{str(i).zfill(2)}"
            )
    except Exception as e:
        logger.error(f"Failed to fetch playlist queue: {e}")

    if track_playlist and app._is_playlist_url(playlist_url):
        added = app._register_playlist(
            playlist_url, show_name, season_num, playlist_start
        )
        if added and playlist_start and playlist_start > 1:
            try:
                videos = app.get_playlist_videos(playlist_url)
                ids_to_seed = [
                    v.get("id") for v in videos[: playlist_start - 1] if v.get("id")
                ]
                archive_file = app._get_archive_file(playlist_url)
                os.makedirs(os.path.dirname(archive_file), exist_ok=True)
                with open(archive_file, "a") as f:
                    for vid in ids_to_seed:
                        f.write(f"{vid}\n")
            except Exception as e:
                logger.error(f"Failed to seed archive for {playlist_url}: {e}")

    with app.job_lock:
        app.jobs[job_id] = job
        completed_jobs = [
            j for j in app.jobs.values() if j.status in {"completed", "failed"}
        ]
        completed_jobs.sort(key=lambda j: j.updated_at)
        while len(completed_jobs) > app.config.get("completed_jobs_limit", 10):
            old_job = completed_jobs.pop(0)
            del app.jobs[old_job.job_id]

        if len(app.active_jobs) < app.config.get("max_concurrent_jobs", 1):
            app.active_jobs.append(job_id)
            if start_thread:
                threading.Thread(target=app.process_job, args=(job_id,)).start()
        else:
            app.job_queue.append(job_id)
            job.update(message="Job queued")

    # If start_thread is False and there is no active job, the caller is
    # expected to process the job manually.

    return job_id


def get_job(app, job_id: str) -> Optional[Dict]:
    job = app.jobs.get(job_id)
    return job.to_dict(message_limit=200) if job else None


def get_jobs(app) -> List[Dict]:
    with app.job_lock:
        return [job.to_dict(include_messages=False) for job in app.jobs.values()]


def cancel_job(app, job_id: str) -> bool:
    job = app.jobs.get(job_id)
    if not job or job.status in {"completed", "failed", "cancelled"}:
        return False
    process = getattr(job, "process", None)
    if process and process.poll() is None:
        try:
            terminate_process(process)
        except Exception as e:  # pragma: no cover - best effort cleanup
            logger.error(f"Failed to terminate process for job {job_id}: {e}")
    job.process = None
    job.update(status="cancelled", message="Job cancelled")
    return True


__all__ = [
    "DownloadJob",
    "create_job",
    "create_music_job",
    "get_job",
    "get_jobs",
    "cancel_job",
]


def create_music_job(
    app,
    playlist_url: str,
    album_name: str,
    artist_name: str = "",
    tracks: Optional[List[TrackMetadata]] = None,
    playlist_start: Optional[int] = None,
    *,
    start_thread: bool = True,
) -> str:
    """Register a music download job request.

    Args:
        app: Application instance
        playlist_url: URL of the YouTube playlist/video to download
        album_name: Name of the album
        artist_name: Name of the artist (optional)
        tracks: List of TrackMetadata objects describing each track
        playlist_start: Starting index in playlist (1-based)
        start_thread: Whether to start processing thread immediately

    Returns:
        Job ID string
    """
    job_id = str(uuid.uuid4())

    # Use album_name as display name
    display_name = album_name or "Unknown Album"

    job = DownloadJob(
        job_id,
        playlist_url,
        display_name,
        "",  # season_num not used for music
        "1",  # episode_start not used for music
        playlist_start,
        media_type="music",
        album_name=album_name,
        artist_name=artist_name,
        tracks=tracks or [],
    )

    # Populate remaining_files from tracks
    if tracks:
        for track in tracks:
            if isinstance(track, TrackMetadata):
                job.remaining_files.append(track.title)

    with app.job_lock:
        app.jobs[job_id] = job
        job.update(
            detailed_status="Music job queued",
            message="Music job created and queued for processing",
        )

        # Handle job queue and threading
        if len(app.active_jobs) < app.config.get("max_concurrent_jobs", 1):
            app.active_jobs.append(job_id)
            if start_thread:
                threading.Thread(target=app.process_music_job, args=(job_id,)).start()
        else:
            app.job_queue.append(job_id)
            job.update(message="Job queued - waiting for available slot")

    return job_id
