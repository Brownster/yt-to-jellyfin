"""Core interface wrapping helper modules for YT-to-Jellyfin."""

import os
import tempfile
import threading
import time
import shutil
import uuid
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .config import _load_config, logger
from .jobs import (
    DownloadJob,
    TrackMetadata,
    create_job,
    create_music_job,
    get_job,
    get_jobs,
    cancel_job,
)
from .playlist import (
    _load_playlists,
    _save_playlists,
    _get_playlist_id,
    _get_archive_file,
    _is_playlist_url,
    _register_playlist,
    _get_existing_max_index,
    check_playlist_updates,
    start_update_checker,
    stop_update_checker,
)
from .media import (
    create_folder_structure,
    create_movie_folder,
    create_music_album_folder,
    download_playlist,
    download_music_tracks,
    process_metadata,
    process_movie_metadata,
    convert_movie_file,
    convert_video_files,
    generate_artwork,
    generate_movie_artwork,
    create_nfo_files,
    list_media,
    list_movies,
    get_playlist_videos,
    prepare_music_tracks,
)
from .jellyfin import (
    copy_to_jellyfin,
    copy_movie_to_jellyfin,
    copy_music_to_jellyfin,
    trigger_jellyfin_scan,
)
from .utils import sanitize_name, clean_filename, check_dependencies, log_job
from .episodes import (
    _load_episode_tracker,
    _save_episode_tracker,
    get_last_episode,
    update_last_episode,
)
from .subscriptions import (
    _load_subscriptions,
    create_subscription as _create_subscription,
    update_subscription as _update_subscription,
    remove_subscription as _remove_subscription,
    list_subscriptions as _list_subscriptions,
    check_subscription_updates as _check_subscription_updates,
    apply_retention_policy,
)


class YTToJellyfin:
    """Main application class delegating work to helper modules."""

    def _load_config(self) -> Dict:
        return _load_config()

    def _load_playlists(self) -> Dict[str, Dict[str, str]]:
        return _load_playlists(self.playlists_file)

    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = self._load_config()
        self.jobs: Dict[str, DownloadJob] = {}
        self.job_lock = threading.Lock()
        self.job_queue: List[str] = []
        self.active_jobs: List[str] = []
        self.playlists_file = os.path.join("config", "playlists.json")
        self.playlists = self._load_playlists()
        self.episodes_file = os.path.join("config", "episodes.json")
        self.episode_tracker = _load_episode_tracker(self.episodes_file)
        self.subscriptions_file = os.path.join("config", "subscriptions.json")
        self.subscriptions = _load_subscriptions(self.subscriptions_file)
        self.update_thread: Optional[threading.Thread] = None
        self.update_stop_event: Optional[threading.Event] = None
        if self.config.get("update_checker_enabled"):
            start_update_checker(self)

    # expose utils
    sanitize_name = staticmethod(sanitize_name)
    clean_filename = staticmethod(clean_filename)

    # wrapper helpers
    def check_dependencies(self) -> bool:
        return check_dependencies(self.config["ytdlp_path"])

    # playlist helpers
    def _save_playlists(self) -> None:
        _save_playlists(self.playlists_file, self.playlists)

    def _get_playlist_id(self, url: str) -> str:
        return _get_playlist_id(url)

    def _get_archive_file(self, url: str) -> str:
        return _get_archive_file(url)

    def _is_playlist_url(self, url: str) -> bool:
        return _is_playlist_url(url)

    def _register_playlist(
        self,
        url: str,
        show_name: str,
        season_num: str,
        start_index: Optional[int] = None,
        *,
        media_type: str = "tv",
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        added = _register_playlist(
            self.playlists,
            self.playlists_file,
            url,
            show_name,
            season_num,
            start_index,
            media_type=media_type,
            extra_metadata=extra_metadata,
        )
        if added:
            self._save_playlists()
        return added

    def _get_existing_max_index(self, folder: str, season_num: str) -> int:
        return _get_existing_max_index(folder, season_num)

    # episode tracker helpers
    def _save_episode_tracker(self) -> None:
        _save_episode_tracker(self.episodes_file, self.episode_tracker)

    def get_last_episode(self, show_name: str, season_num: str) -> int:
        return get_last_episode(self.episode_tracker, show_name, season_num)

    def update_last_episode(
        self, show_name: str, season_num: str, last_episode: int
    ) -> None:
        update_last_episode(
            self.episode_tracker,
            self.episodes_file,
            show_name,
            season_num,
            last_episode,
        )

    def check_playlist_updates(self) -> List[str]:
        jobs = check_playlist_updates(self)
        jobs.extend(self.check_subscription_updates())
        return jobs

    def start_update_checker(self) -> None:
        start_update_checker(self)

    def stop_update_checker(self) -> None:
        stop_update_checker(self)

    def create_subscription(
        self,
        channel_url: str,
        show_name: str,
        retention_type: str,
        retention_value: Optional[str] = None,
    ) -> str:
        return _create_subscription(
            self, channel_url, show_name, retention_type, retention_value
        )

    def update_subscription(
        self,
        subscription_id: str,
        *,
        show_name: Optional[str] = None,
        retention_type: Optional[str] = None,
        retention_value: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> bool:
        updated = _update_subscription(
            self,
            subscription_id,
            show_name=show_name,
            retention_type=retention_type,
            retention_value=retention_value,
            enabled=enabled,
        )
        return updated

    def remove_subscription(self, subscription_id: str) -> bool:
        return _remove_subscription(self, subscription_id)

    def list_subscriptions(self) -> List[Dict]:
        return _list_subscriptions(self)

    def check_subscription_updates(self) -> List[str]:
        return _check_subscription_updates(self)

    def apply_subscription_retention(self, subscription_id: str) -> None:
        apply_retention_policy(self, subscription_id)

    # job helpers
    def create_job(
        self,
        playlist_url: str,
        show_name: str,
        season_num: str,
        episode_start: str,
        playlist_start: Optional[int] = None,
        track_playlist: bool = True,
        *,
        start_thread: bool = True,
    ) -> str:
        return create_job(
            self,
            playlist_url,
            show_name,
            season_num,
            episode_start,
            playlist_start,
            track_playlist,
            start_thread=start_thread,
        )

    def create_movie_job(
        self,
        video_url: str,
        movie_name: str,
        *,
        start_thread: bool = True,
    ) -> str:
        job_id = str(uuid.uuid4())
        job = DownloadJob(
            job_id,
            video_url,
            "",
            "",
            "",
            media_type="movie",
            movie_name=movie_name,
        )
        with self.job_lock:
            self.jobs[job_id] = job
            if len(self.active_jobs) < self.config.get("max_concurrent_jobs", 1):
                self.active_jobs.append(job_id)
                if start_thread:
                    threading.Thread(
                        target=self.process_movie_job,
                        args=(job_id,),
                    ).start()
            else:
                self.job_queue.append(job_id)
                job.update(message="Job queued")
        return job_id

    def create_music_job(
        self,
        playlist_url: str,
        album_name: str,
        artist_name: str,
        tracks: List[Dict[str, Any]],
        *,
        playlist_start: Optional[int] = None,
        track_playlist: bool = True,
        subscription_id: Optional[str] = None,
        start_thread: bool = True,
    ) -> str:
        return create_music_job(
            self,
            playlist_url,
            album_name,
            artist_name,
            tracks,
            playlist_start=playlist_start,
            track_playlist=track_playlist,
            subscription_id=subscription_id,
            start_thread=start_thread,
        )

    def get_job(self, job_id: str) -> Optional[Dict]:
        return get_job(self, job_id)

    def get_jobs(self) -> List[Dict]:
        return get_jobs(self)

    def cancel_job(self, job_id: str) -> bool:
        return cancel_job(self, job_id)

    def process_job(self, job_id: str) -> None:
        job = self.jobs.get(job_id)
        if not job:
            log_job(job_id, logging.ERROR, "Job not found")
            return
        try:
            job.update(status="in_progress", message="Starting job processing")
            if not self.check_dependencies():
                job.update(status="failed", message="Missing dependencies")
                return
            try:
                episode_start = int(job.episode_start)
            except ValueError:
                job.update(status="failed", message="Invalid episode start")
                return
            folder = self.create_folder_structure(job.show_name, job.season_num)
            job.update(message=f"Created folder structure: {folder}")
            if job.playlist_start is not None:
                dl_success = self.download_playlist(
                    job.playlist_url, folder, job.season_num, job_id, job.playlist_start
                )
            else:
                dl_success = self.download_playlist(
                    job.playlist_url, folder, job.season_num, job_id
                )
            if job.status == "cancelled":
                return
            if not dl_success:
                job.update(status="failed", message="Download failed")
                return
            self.process_metadata(
                folder, job.show_name, job.season_num, episode_start, job_id
            )
            if job.status == "cancelled":
                return
            self.convert_video_files(folder, job.season_num, job_id)
            if job.status == "cancelled":
                return
            self.generate_artwork(folder, job.show_name, job.season_num, job_id)
            if job.status == "cancelled":
                return
            self.create_nfo_files(folder, job.show_name, job.season_num, job_id)
            if job.status == "cancelled":
                return
            if self.config.get("jellyfin_enabled", False) and self.config.get(
                "jellyfin_tv_path"
            ):
                self.copy_to_jellyfin(job.show_name, job.season_num, job_id)
            job.update(
                status="completed", progress=100, message="Job completed successfully"
            )
            log_job(job_id, logging.INFO, "Job completed successfully")
            if job.subscription_id:
                self.apply_subscription_retention(job.subscription_id)
            try:
                pid = self._get_playlist_id(job.playlist_url)
                info = self.playlists.get(pid)
                if info:
                    archive = info.get(
                        "archive", self._get_archive_file(job.playlist_url)
                    )
                    if os.path.exists(archive):
                        with open(archive, "r") as f:
                            count = sum(1 for _ in f if _.strip())
                        info["start_index"] = count + 1
                        self._save_playlists()
            except Exception as e:
                log_job(
                    job_id,
                    logging.ERROR,
                    f"Failed to update playlist index for {job.playlist_url}: {e}",
                )
        except Exception as e:  # pragma: no cover - for unexpected errors
            logger.exception(f"Job {job_id}: Error processing job: {e}")
            job.update(status="failed", message=f"Error: {str(e)}")
        finally:
            self._on_job_complete(job_id)

    def process_movie_job(self, job_id: str) -> None:
        job = self.jobs.get(job_id)
        if not job:
            log_job(job_id, logging.ERROR, "Job not found")
            return
        try:
            job.update(status="in_progress", message="Starting job processing")
            if not self.check_dependencies():
                job.update(status="failed", message="Missing dependencies")
                return
            folder = self.create_movie_folder(job.movie_name)
            job.update(message=f"Created folder structure: {folder}")
            dl_success = self.download_playlist(job.playlist_url, folder, "01", job_id)
            if job.status == "cancelled":
                return
            if not dl_success:
                job.update(status="failed", message="Download failed")
                return
            self.process_movie_metadata(folder, job.movie_name, job_id)
            if job.status == "cancelled":
                return
            self.convert_movie_file(folder, job_id)
            if job.status == "cancelled":
                return
            self.generate_movie_artwork(folder, job_id)
            if job.status == "cancelled":
                return
            if (
                self.config.get("jellyfin_enabled", False)
                and self.config.get("jellyfin_movie_path")
            ):
                self.copy_movie_to_jellyfin(job.movie_name, job_id)
            job.update(
                status="completed",
                progress=100,
                message="Job completed successfully",
            )
            log_job(job_id, logging.INFO, "Job completed successfully")
        except Exception as e:  # pragma: no cover - for unexpected errors
            logger.exception(f"Job {job_id}: Error processing job: {e}")
            job.update(status="failed", message=f"Error: {str(e)}")
        finally:
            self._on_job_complete(job_id)

    def process_music_job(self, job_id: str) -> None:
        job = self.jobs.get(job_id)
        if not job:
            log_job(job_id, logging.ERROR, "Job not found")
            return

        try:
            job.update(status="in_progress", message="Starting music job")
            if not self.check_dependencies():
                job.update(status="failed", message="Missing dependencies")
                return

            folder = self.create_music_album_folder(job.album_name, job.artist_name)
            job.update(
                message=f"Created music folder structure at {folder}",
                detailed_status="Preparing album folder",
            )

            downloaded_files = self.download_music_tracks(
                job.playlist_url,
                folder,
                job_id,
                job.playlist_start,
            )

            if job.status == "cancelled":
                return

            if not downloaded_files:
                job.update(status="failed", message="Audio download failed")
                return

            prepared = self.prepare_music_tracks(
                folder,
                job.tracks,
                downloaded_files,
                job_id,
            )

            if job.status == "cancelled":
                return

            if not prepared:
                job.update(status="failed", message="Failed to prepare music tracks")
                return

            if (
                self.config.get("jellyfin_enabled", False)
                and self.config.get("jellyfin_music_path")
            ):
                self.copy_music_to_jellyfin(job.album_name, job.artist_name, job_id)

            job.update(
                status="completed",
                progress=100,
                stage="completed",
                detailed_status="Music job completed",
                message="Music job completed successfully",
            )
            log_job(job_id, logging.INFO, "Music job completed successfully")
        except Exception as exc:  # pragma: no cover - unexpected errors
            logger.exception(f"Job {job_id}: Error processing music job: {exc}")
            job.update(status="failed", message=f"Error: {exc}")
        finally:
            self._on_job_complete(job_id)

    def _on_job_complete(self, job_id: str) -> None:
        """Start the next queued job if available."""
        with self.job_lock:
            if job_id in self.active_jobs:
                self.active_jobs.remove(job_id)
            while (
                self.job_queue
                and len(self.active_jobs)
                < self.config.get("max_concurrent_jobs", 1)
            ):
                next_id = self.job_queue.pop(0)
                self.active_jobs.append(next_id)
                next_job = self.jobs.get(next_id)
                target = self.process_job
                if next_job:
                    if next_job.media_type == "movie":
                        target = self.process_movie_job
                    elif next_job.media_type == "music":
                        target = self.process_music_job
                threading.Thread(target=target, args=(next_id,)).start()

    # media functions
    def create_folder_structure(self, show_name: str, season_num: str) -> str:
        return create_folder_structure(self, show_name, season_num)

    def create_movie_folder(self, movie_name: str) -> str:
        return create_movie_folder(self, movie_name)

    def create_music_album_folder(
        self, album_name: str, artist_name: Optional[str] = None
    ) -> str:
        return create_music_album_folder(self, album_name, artist_name)

    def download_playlist(
        self,
        playlist_url: str,
        folder: str,
        season_num: str,
        job_id: str,
        playlist_start: Optional[int] = None,
    ) -> bool:
        return download_playlist(
            self, playlist_url, folder, season_num, job_id, playlist_start
        )

    def download_music_tracks(
        self,
        playlist_url: str,
        folder: str,
        job_id: str,
        playlist_start: Optional[int] = None,
    ) -> List[Path]:
        return download_music_tracks(
            self, playlist_url, folder, job_id, playlist_start
        )

    def process_metadata(
        self,
        folder: str,
        show_name: str,
        season_num: str,
        episode_start: int,
        job_id: str,
    ) -> None:
        process_metadata(self, folder, show_name, season_num, episode_start, job_id)

    def process_movie_metadata(
        self, folder: str, movie_name: str, job_id: str, json_index: int = 0
    ) -> None:
        process_movie_metadata(self, folder, movie_name, job_id, json_index)

    def convert_movie_file(self, folder: str, job_id: str) -> None:
        convert_movie_file(self, folder, job_id)

    def convert_video_files(self, folder: str, season_num: str, job_id: str) -> None:
        convert_video_files(self, folder, season_num, job_id)

    def prepare_music_tracks(
        self,
        folder: str,
        tracks: Sequence[TrackMetadata],
        downloaded_files: Sequence[Path],
        job_id: str,
    ) -> List[Path]:
        return prepare_music_tracks(self, folder, tracks, downloaded_files, job_id)

    def generate_artwork(
        self, folder: str, show_name: str, season_num: str, job_id: str
    ) -> None:
        generate_artwork(self, folder, show_name, season_num, job_id)

    def generate_movie_artwork(self, folder: str, job_id: str) -> None:
        generate_movie_artwork(self, folder, job_id)

    def create_nfo_files(
        self, folder: str, show_name: str, season_num: str, job_id: str
    ) -> None:
        create_nfo_files(self, folder, show_name, season_num, job_id)

    def list_media(self) -> List[Dict]:
        return list_media(self)

    def list_movies(self) -> List[Dict]:
        return list_movies(self)

    def get_playlist_videos(self, url: str) -> List[Dict]:
        return get_playlist_videos(self, url)

    def copy_to_jellyfin(self, show_name: str, season_num: str, job_id: str) -> None:
        copy_to_jellyfin(self, show_name, season_num, job_id)

    def copy_movie_to_jellyfin(self, movie_name: str, job_id: str) -> None:
        copy_movie_to_jellyfin(self, movie_name, job_id)

    def copy_music_to_jellyfin(
        self, album_name: str, artist_name: str, job_id: str
    ) -> None:
        copy_music_to_jellyfin(self, album_name, artist_name, job_id)

    def trigger_jellyfin_scan(self, job_id: str) -> None:
        trigger_jellyfin_scan(self, job_id)

    # public wrappers for playlist info
    def list_playlists(self) -> List[Dict]:
        playlists = []
        for pid, info in self.playlists.items():
            if info.get("media_type", "tv") != "tv":
                continue
            archive = info.get("archive", self._get_archive_file(info["url"]))
            last_downloaded = 0
            if os.path.exists(archive):
                with open(archive, "r") as f:
                    last_downloaded = sum(1 for _ in f)
            folder = (
                Path(self.config["output_dir"])
                / sanitize_name(info["show_name"])
                / f"Season {info['season_num']}"
            )
            last_episode = self.get_last_episode(info["show_name"], info["season_num"])
            if last_episode == 0:
                last_episode = self._get_existing_max_index(
                    str(folder), info["season_num"]
                )
            playlists.append(
                {
                    "id": pid,
                    "url": info["url"],
                    "show_name": info["show_name"],
                    "season_num": info["season_num"],
                    "last_episode": last_episode,
                    "downloaded_videos": last_downloaded,
                    "enabled": not info.get("disabled", False),
                }
            )
        return playlists

    def set_playlist_enabled(self, playlist_id: str, enabled: bool) -> bool:
        from .playlist import _set_playlist_enabled

        if _set_playlist_enabled(
            self.playlists, self.playlists_file, playlist_id, enabled
        ):
            return True
        return False

    def remove_playlist(self, playlist_id: str) -> bool:
        from .playlist import _remove_playlist

        if _remove_playlist(self.playlists, self.playlists_file, playlist_id):
            return True
        return False

    def process(
        self, playlist_url: str, show_name: str, season_num: str, episode_start: int
    ) -> bool:
        try:
            job_id = self.create_job(
                playlist_url, show_name, season_num, str(episode_start)
            )
            job = self.jobs.get(job_id)
            while job and job.status not in ("completed", "failed"):
                time.sleep(1)
                job = self.jobs.get(job_id)
            return job.status == "completed" if job else False
        except Exception as e:
            logger.exception(f"Error processing playlist {playlist_url}: {e}")
            return False
        finally:
            self.cleanup()

    def cleanup(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)


__all__ = ["YTToJellyfin", "DownloadJob", "logger"]
