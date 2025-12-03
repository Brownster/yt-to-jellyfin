"""Core interface wrapping helper modules for YT-to-Jellyfin."""

import os
import tempfile
import threading
import time
import shutil
import uuid
import logging
from pathlib import Path
from typing import Dict, List, Optional
from pathlib import Path as PathType

from .config import _load_config, logger
from .jobs import (
    DownloadJob,
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
    prepare_music_tracks,
    write_m3u_playlist,
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
    get_music_playlist_details,
)
from .episode_detection import AirdateEpisodeDetector
from .jellyfin import (
    copy_to_jellyfin,
    copy_movie_to_jellyfin,
    copy_music_to_jellyfin,
    trigger_jellyfin_scan,
)
from .tvdb import TVDBAuthenticationError, TVDBClient
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
        self.tvdb_client: Optional[TVDBClient] = None
        if self.config.get("tvdb_api_key"):
            try:
                self.tvdb_client = TVDBClient(
                    self.config.get("tvdb_api_key"), self.config.get("tvdb_pin") or None
                )
            except TVDBAuthenticationError as exc:
                logger.warning("Failed to authenticate with TVDB: %s", exc)
            except Exception as exc:  # pragma: no cover - safety net
                logger.warning("Failed to initialize TVDB client: %s", exc)
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
    ) -> bool:
        added = _register_playlist(
            self.playlists,
            self.playlists_file,
            url,
            show_name,
            season_num,
            start_index,
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
        quality: Optional[int] = None,
        use_h265: Optional[bool] = None,
        crf: Optional[int] = None,
        auto_detect: bool = False,
        detection_profile: Optional[str] = None,
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
            quality=quality,
            use_h265=use_h265,
            crf=crf,
            auto_detect=auto_detect,
            detection_profile=detection_profile,
        )

    def create_movie_job(
        self,
        video_url: str,
        movie_name: str,
        *,
        start_thread: bool = True,
        quality: Optional[int] = None,
        use_h265: Optional[bool] = None,
        crf: Optional[int] = None,
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
            quality_override=quality,
            use_h265_override=use_h265,
            crf_override=crf,
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
        music_request: Dict,
        *,
        start_thread: bool = True,
    ) -> str:
        return create_music_job(self, music_request, start_thread=start_thread)

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
                episode_start = int(job.episode_start) if job.episode_start else 1
            except ValueError:
                job.update(status="failed", message="Invalid episode start")
                return
            season_for_download = job.season_num or "00"
            job.season_num = season_for_download
            folder = self.create_folder_structure(job.show_name, season_for_download)
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
            mapper = None
            if job.auto_detect_episodes:
                if not self.tvdb_client:
                    job.update(
                        status="failed",
                        message="TVDB API key required for auto-detect",
                        detailed_status="Missing TVDB API key",
                    )
                    return
                mapper = AirdateEpisodeDetector(self.tvdb_client, job.show_name)

            seasons_processed = self.process_metadata(
                folder, job.show_name, job.season_num, episode_start, job_id, mapper
            )
            job.detected_seasons = seasons_processed
            if job.status == "cancelled":
                return
            if job.status == "failed":
                return
            season_targets = seasons_processed or [job.season_num]
            for season in season_targets:
                season_folder = (
                    Path(self.config["output_dir"])
                    / self.sanitize_name(job.show_name)
                    / f"Season {season}"
                )
                self.convert_video_files(str(season_folder), season, job_id)
            if job.status == "cancelled":
                return
            for season in season_targets:
                season_folder = (
                    Path(self.config["output_dir"])
                    / self.sanitize_name(job.show_name)
                    / f"Season {season}"
                )
                self.generate_artwork(str(season_folder), job.show_name, season, job_id)
            if job.status == "cancelled":
                return
            for season in season_targets:
                season_folder = (
                    Path(self.config["output_dir"])
                    / self.sanitize_name(job.show_name)
                    / f"Season {season}"
                )
                self.create_nfo_files(str(season_folder), job.show_name, season, job_id)
            if job.status == "cancelled":
                return
            if self.config.get("jellyfin_enabled", False) and self.config.get(
                "jellyfin_tv_path"
            ):
                for season in season_targets:
                    self.copy_to_jellyfin(job.show_name, season, job_id)
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
            if self.config.get("jellyfin_enabled", False) and self.config.get(
                "jellyfin_movie_path"
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
        """Process a music download job from start to completion."""
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

            if isinstance(prepared, list):
                prepared_files = prepared
            elif isinstance(prepared, tuple):
                prepared_files = list(prepared)
            else:
                prepared_files = [prepared] if isinstance(prepared, Path) else []

            prepared_files = [Path(p) for p in prepared_files]

            playlist_request = job.music_request or {}
            collection = playlist_request.get("collection") or {}
            playlist_markers = {"playlist", "mix", "standard", "channel", "artist"}
            job_type = str(playlist_request.get("job_type") or "").strip().lower()
            variant = str(collection.get("variant") or "").strip().lower()
            is_playlist_job = (
                job_type.startswith("playlist")
                or job_type in playlist_markers
                or variant in playlist_markers
            )

            if (
                prepared_files
                and playlist_request.get("create_m3u")
                and is_playlist_job
            ):
                base_path = (
                    playlist_request.get("m3u_path")
                    or self.config.get("music_output_dir")
                )
                playlist_name = (
                    playlist_request.get("display_name")
                    or collection.get("title")
                    or job.album_name
                )
                try:
                    playlist_file = self.write_m3u_playlist(
                        prepared_files,
                        base_path=base_path,
                        playlist_name=playlist_name,
                    )
                    job.update(
                        detailed_status="Generated playlist file",
                        message=f"Created M3U playlist at {playlist_file}",
                    )
                except Exception as exc:  # pragma: no cover - defensive logging
                    log_job(
                        job_id,
                        logging.ERROR,
                        f"Failed to create M3U playlist: {exc}",
                    )
                    job.update(message=f"Failed to create M3U playlist: {exc}")

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
        except Exception as exc:
            logger.exception(f"Job {job_id}: Error processing music job: {exc}")
            job.update(status="failed", message=f"Error: {exc}")
        finally:
            self._on_job_complete(job_id)

    def _on_job_complete(self, job_id: str) -> None:
        """Start the next queued job if available."""
        with self.job_lock:
            if job_id in self.active_jobs:
                self.active_jobs.remove(job_id)
            while self.job_queue and len(self.active_jobs) < self.config.get(
                "max_concurrent_jobs", 1
            ):
                next_id = self.job_queue.pop(0)
                self.active_jobs.append(next_id)
                threading.Thread(
                    target=self.process_job,
                    args=(next_id,),
                ).start()

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

    def process_metadata(
        self,
        folder: str,
        show_name: str,
        season_num: str,
        episode_start: int,
        job_id: str,
        episode_mapper=None,
    ) -> List[str]:
        return process_metadata(
            self, folder, show_name, season_num, episode_start, job_id, episode_mapper
        )

    def process_movie_metadata(
        self, folder: str, movie_name: str, job_id: str, json_index: int = 0
    ) -> None:
        process_movie_metadata(self, folder, movie_name, job_id, json_index)

    def convert_movie_file(self, folder: str, job_id: str) -> None:
        convert_movie_file(self, folder, job_id)

    def convert_video_files(self, folder: str, season_num: str, job_id: str) -> None:
        convert_video_files(self, folder, season_num, job_id)

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

    def download_music_tracks(
        self,
        playlist_url: str,
        folder: str,
        job_id: str,
        playlist_start: Optional[int] = None,
    ) -> List[PathType]:
        return download_music_tracks(self, playlist_url, folder, job_id, playlist_start)

    def prepare_music_tracks(
        self,
        folder: str,
        tracks,
        downloaded_files,
        job_id: str,
    ) -> List[PathType]:
        return prepare_music_tracks(self, folder, tracks, downloaded_files, job_id)

    def write_m3u_playlist(
        self,
        prepared_files,
        *,
        base_path: Optional[str] = None,
        playlist_name: Optional[str] = None,
    ):
        return write_m3u_playlist(
            self,
            prepared_files,
            base_path=base_path,
            playlist_name=playlist_name,
        )

    def list_media(self) -> List[Dict]:
        return list_media(self)

    def list_movies(self) -> List[Dict]:
        return list_movies(self)

    def get_playlist_videos(self, url: str) -> List[Dict]:
        return get_playlist_videos(self, url)

    def get_music_playlist_info(self, url: str) -> Dict:
        return get_music_playlist_details(self, url)

    def copy_to_jellyfin(self, show_name: str, season_num: str, job_id: str) -> None:
        copy_to_jellyfin(self, show_name, season_num, job_id)

    def copy_movie_to_jellyfin(self, movie_name: str, job_id: str) -> None:
        copy_movie_to_jellyfin(self, movie_name, job_id)

    def copy_music_to_jellyfin(self, album_name: str, artist_name: str, job_id: str) -> None:
        copy_music_to_jellyfin(self, album_name, artist_name, job_id)

    def trigger_jellyfin_scan(self, job_id: str) -> None:
        trigger_jellyfin_scan(self, job_id)

    # public wrappers for playlist info
    def list_playlists(self) -> List[Dict]:
        playlists = []
        for pid, info in self.playlists.items():
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
