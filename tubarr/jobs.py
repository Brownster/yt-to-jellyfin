import os
import copy
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
        *,
        quality_override: Optional[int] = None,
        use_h265_override: Optional[bool] = None,
        crf_override: Optional[int] = None,
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
        self.quality_override = quality_override
        self.use_h265_override = use_h265_override
        self.crf_override = crf_override
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
            "quality_override": self.quality_override,
            "use_h265_override": self.use_h265_override,
            "crf_override": self.crf_override,
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
    quality: Optional[int] = None,
    use_h265: Optional[bool] = None,
    crf: Optional[int] = None,
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
        quality_override=quality,
        use_h265_override=use_h265,
        crf_override=crf,
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


def _normalize_optional_int(value: Any) -> Optional[int]:
    if value in (None, "", "null"):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_playlist_request(job_type: str, collection: Dict[str, Any]) -> bool:
    playlist_markers = {"playlist", "mix", "standard", "channel", "artist"}
    normalized_type = (job_type or "").strip().lower()
    if not normalized_type:
        normalized_type = ""
    if normalized_type in playlist_markers or normalized_type.startswith("playlist"):
        return True
    variant = str(collection.get("variant", "")).strip().lower()
    return variant in playlist_markers


def _coerce_track_metadata(
    index: int,
    track: Any,
    album_name: str,
    default_artist: str,
) -> TrackMetadata:
    if isinstance(track, TrackMetadata):
        return track
    if not isinstance(track, dict):
        raise ValueError("Tracks must be TrackMetadata instances or dictionaries")

    title = (track.get("title") or f"Track {index}").strip()
    if not title:
        raise ValueError(f"Track {index} is missing a title")

    artist = track.get("artist") or default_artist or ""
    album = track.get("album") or album_name or ""
    track_number = _normalize_optional_int(track.get("track_number")) or index
    disc_number = _normalize_optional_int(track.get("disc_number")) or 1
    total_tracks = _normalize_optional_int(track.get("total_tracks"))
    total_discs = _normalize_optional_int(track.get("total_discs"))

    release_date = track.get("release_date") or track.get("year")
    if release_date is not None:
        release_date = str(release_date)

    genres_value = track.get("genres") or []
    if isinstance(genres_value, str):
        genres = [g.strip() for g in genres_value.split(";") if g.strip()]
    elif isinstance(genres_value, list):
        genres = [str(g) for g in genres_value]
    else:
        genres = []

    cover_url = track.get("cover_url") or track.get("cover") or track.get("thumbnail")
    album_artist = track.get("album_artist") or default_artist or ""

    extra_fields: Dict[str, Any] = {}
    for key in ("duration", "source_url", "thumbnail", "notes", "tags"):
        if key in track and track[key] not in (None, ""):
            extra_fields[key] = copy.deepcopy(track[key])
    if cover_url:
        extra_fields.setdefault("cover_url", cover_url)

    return TrackMetadata(
        title=title,
        artist=artist,
        album=album,
        track_number=track_number,
        total_tracks=total_tracks,
        disc_number=disc_number,
        total_discs=total_discs,
        release_date=release_date,
        genres=genres,
        cover_url=cover_url,
        album_artist=album_artist or None,
        extra=extra_fields,
    )


def create_music_job(
    app,
    music_request: Dict[str, Any],
    *,
    start_thread: bool = True,
) -> str:
    """Register a music download job request from a JSON payload."""

    if not isinstance(music_request, dict):
        raise ValueError("music_request must be a dictionary")

    request = copy.deepcopy(music_request)
    job_type = str(request.get("job_type") or "").strip()
    collection = request.get("collection") or {}
    source_url = request.get("source_url") or collection.get("source_url")
    if not source_url:
        raise ValueError("source_url is required for music jobs")

    display_name = request.get("display_name") or collection.get("title") or "Untitled Music"
    album_name = collection.get("title") or display_name
    artist_name = (
        collection.get("artist")
        or collection.get("owner")
        or request.get("artist_name")
        or ""
    )

    playlist_start = request.get("playlist_start")
    if playlist_start is None:
        playlist_start = collection.get("playlist_start")
    playlist_start = _normalize_optional_int(playlist_start)

    create_m3u = bool(request.get("create_m3u"))
    if create_m3u and not _is_playlist_request(job_type, collection):
        raise ValueError("create_m3u is only supported for playlist jobs")

    tracks_payload = request.get("tracks")
    if not isinstance(tracks_payload, list) or not tracks_payload:
        raise ValueError("tracks must be a non-empty list")

    converted_tracks = [
        _coerce_track_metadata(idx, track, album_name, artist_name)
        for idx, track in enumerate(tracks_payload, start=1)
    ]

    job_id = str(uuid.uuid4())
    job = DownloadJob(
        job_id,
        source_url,
        display_name,
        "",  # season_num not used for music
        "1",  # episode_start not used for music
        playlist_start,
        media_type="music",
        album_name=album_name,
        artist_name=artist_name,
        tracks=converted_tracks,
        music_request=request,
    )

    job.remaining_files = [track.title for track in converted_tracks]

    with app.job_lock:
        app.jobs[job_id] = job
        job.update(
            detailed_status="Music job queued",
            message="Music job created and queued for processing",
        )

        if len(app.active_jobs) < app.config.get("max_concurrent_jobs", 1):
            app.active_jobs.append(job_id)
            if start_thread:
                threading.Thread(target=app.process_music_job, args=(job_id,)).start()
        else:
            app.job_queue.append(job_id)
            job.update(message="Job queued - waiting for available slot")

    return job_id
