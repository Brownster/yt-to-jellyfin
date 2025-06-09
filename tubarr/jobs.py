import os
import uuid
import threading
import subprocess
from datetime import datetime
from typing import Dict, List, Optional

from .config import logger


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
    ):
        self.job_id = job_id
        self.playlist_url = playlist_url
        self.show_name = show_name
        self.season_num = season_num
        self.episode_start = episode_start
        self.playlist_start = playlist_start
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
    *,
    start_thread: bool = True,
) -> str:
    job_id = str(uuid.uuid4())
    job = DownloadJob(
        job_id, playlist_url, show_name, season_num, episode_start, playlist_start
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

        if app.active_job_id is None:
            app.active_job_id = job_id
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
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        except Exception as e:
            logger.error(f"Failed to terminate process for job {job_id}: {e}")
    job.process = None
    job.update(status="cancelled", message="Job cancelled")
    return True


__all__ = ["DownloadJob", "create_job", "get_job", "get_jobs", "cancel_job"]
