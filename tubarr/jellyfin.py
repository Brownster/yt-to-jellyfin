import os
import shutil
from pathlib import Path
import logging

from .config import logger
from .utils import log_job


def copy_to_jellyfin(app, show_name: str, season_num: str, job_id: str) -> None:
    if not app.config.get("jellyfin_enabled", False):
        log_job(
            job_id,
            logging.INFO,
            "Jellyfin integration disabled, skipping file copy",
        )
        return
    jellyfin_tv_path = app.config.get("jellyfin_tv_path", "")
    if not jellyfin_tv_path:
        log_job(
            job_id,
            logging.ERROR,
            "Jellyfin TV path not configured, skipping file copy",
        )
        return
    job = app.jobs.get(job_id)
    if job:
        job.update(
            status="copying_to_jellyfin",
            stage="copying_to_jellyfin",
            progress=95,
            detailed_status="Copying files to Jellyfin TV folder",
            message="Starting copy to Jellyfin TV folder",
        )
    sanitized_show = app.sanitize_name(show_name)
    source_folder = (
        Path(app.config["output_dir"]) / sanitized_show / f"Season {season_num}"
    )
    dest_show_folder = Path(jellyfin_tv_path) / sanitized_show
    dest_season_folder = dest_show_folder / f"Season {season_num}"
    if not os.path.exists(dest_show_folder):
        try:
            os.makedirs(dest_show_folder, exist_ok=True)
            log_job(
                job_id,
                logging.INFO,
                f"Created show folder at {dest_show_folder}",
            )
            if job:
                job.update(message=f"Created show folder at {dest_show_folder}")
        except OSError as e:
            log_job(
                job_id,
                logging.ERROR,
                f"Failed to create Jellyfin show folder: {e}",
            )
            if job:
                job.update(message=f"Error: Failed to create Jellyfin show folder: {e}")
            return
    if not os.path.exists(dest_season_folder):
        try:
            os.makedirs(dest_season_folder, exist_ok=True)
            log_job(
                job_id,
                logging.INFO,
                f"Created season folder at {dest_season_folder}",
            )
            if job:
                job.update(message=f"Created season folder at {dest_season_folder}")
        except OSError as e:
            log_job(
                job_id,
                logging.ERROR,
                f"Failed to create Jellyfin season folder: {e}",
            )
            if job:
                job.update(
                    message=f"Error: Failed to create Jellyfin season folder: {e}"
                )
            return
    try:
        media_files = list(source_folder.glob("*.mp4"))
        nfo_files = list(source_folder.glob("*.nfo"))
        jpg_files = list(source_folder.glob("*.jpg"))
        all_files = media_files + nfo_files + jpg_files
        total_files = len(all_files)
        if job:
            job.update(
                total_files=total_files,
                processed_files=0,
                detailed_status=f"Copying {total_files} files to Jellyfin",
            )
        for i, file_path in enumerate(all_files):
            dest_file = dest_season_folder / file_path.name
            if (
                os.path.exists(dest_file)
                and os.path.getsize(dest_file) == os.path.getsize(file_path)
            ):
                log_job(
                    job_id,
                    logging.INFO,
                    f"Skipping {file_path.name} - already exists and same size",
                )
                if job:
                    job.update(
                        processed_files=i + 1,
                        message=f"Skipped {file_path.name} - already exists",
                    )
                continue
            shutil.copy2(file_path, dest_file)
            log_job(
                job_id,
                logging.INFO,
                f"Copied {file_path.name} to Jellyfin",
            )
            if job:
                job.update(
                    processed_files=i + 1,
                    file_name=file_path.name,
                    stage_progress=int((i + 1) / total_files * 100),
                    detailed_status=f"Copying: {file_path.name} ({i+1}/{total_files})",
                    message=f"Copied {file_path.name} to Jellyfin TV folder",
                )
        show_files = [
            (
                Path(app.config["output_dir"]) / sanitized_show / "tvshow.nfo",
                dest_show_folder / "tvshow.nfo",
            ),
            (
                Path(app.config["output_dir"]) / sanitized_show / "poster.jpg",
                dest_show_folder / "poster.jpg",
            ),
            (
                Path(app.config["output_dir"]) / sanitized_show / "fanart.jpg",
                dest_show_folder / "fanart.jpg",
            ),
        ]
        for source, dest in show_files:
            if source.exists():
                shutil.copy2(source, dest)
                log_job(
                    job_id,
                    logging.INFO,
                    f"Copied show file {source.name} to Jellyfin",
                )
                if job:
                    job.update(message=f"Copied {source.name} to Jellyfin")
        if job:
            job.update(
                progress=98,
                stage_progress=100,
                detailed_status="Copy to Jellyfin completed",
                message="Successfully copied all files to Jellyfin TV folder",
            )
        if app.config.get("jellyfin_api_key") and app.config.get("jellyfin_host"):
            app.trigger_jellyfin_scan(job_id)
    except (IOError, shutil.Error) as e:
        log_job(
            job_id,
            logging.ERROR,
            f"Error copying files to Jellyfin: {e}",
        )
        if job:
            job.update(message=f"Error copying files to Jellyfin: {e}")


def copy_movie_to_jellyfin(app, movie_name: str, job_id: str) -> None:
    if not app.config.get("jellyfin_enabled", False):
        logger.info("Jellyfin integration disabled, skipping file copy")
        return
    jellyfin_movie_path = app.config.get("jellyfin_movie_path", "")
    if not jellyfin_movie_path:
        logger.error("Jellyfin movie path not configured, skipping file copy")
        return
    job = app.jobs.get(job_id)
    if job:
        job.update(
            status="copying_to_jellyfin",
            stage="copying_to_jellyfin",
            progress=95,
            detailed_status="Copying files to Jellyfin movie folder",
            message="Starting copy to Jellyfin movie folder",
        )
    sanitized = app.sanitize_name(movie_name)
    source_folder = Path(app.config["output_dir"]) / sanitized
    dest_folder = Path(jellyfin_movie_path) / sanitized
    if not os.path.exists(dest_folder):
        try:
            os.makedirs(dest_folder, exist_ok=True)
            log_job(
                job_id,
                logging.INFO,
                f"Created movie folder at {dest_folder}",
            )
            if job:
                job.update(message=f"Created movie folder at {dest_folder}")
        except OSError as e:
            log_job(
                job_id,
                logging.ERROR,
                f"Failed to create Jellyfin movie folder: {e}",
            )
            if job:
                job.update(
                    message=f"Error: Failed to create Jellyfin movie folder: {e}"
                )
            return
    try:
        all_files = list(source_folder.glob("*"))
        total_files = len(all_files)
        if job:
            job.update(
                total_files=total_files,
                processed_files=0,
                detailed_status=f"Copying {total_files} files to Jellyfin",
            )
        for i, file_path in enumerate(all_files):
            dest_file = dest_folder / file_path.name
            if (
                os.path.exists(dest_file)
                and os.path.getsize(dest_file) == os.path.getsize(file_path)
            ):
                log_job(
                    job_id,
                    logging.INFO,
                    f"Skipping {file_path.name} - already exists and same size",
                )
                if job:
                    job.update(
                        processed_files=i + 1,
                        message=f"Skipped {file_path.name} - already exists",
                    )
                continue
            shutil.copy2(file_path, dest_file)
            log_job(
                job_id,
                logging.INFO,
                f"Copied {file_path.name} to Jellyfin",
            )
            if job:
                job.update(
                    processed_files=i + 1,
                    file_name=file_path.name,
                    stage_progress=int((i + 1) / total_files * 100),
                    detailed_status=f"Copying: {file_path.name} ({i+1}/{total_files})",
                    message=f"Copied {file_path.name} to Jellyfin movie folder",
                )
        if job:
            job.update(
                progress=98,
                stage_progress=100,
                detailed_status="Copy to Jellyfin completed",
                message="Successfully copied all files to Jellyfin movie folder",
            )
        if app.config.get("jellyfin_api_key") and app.config.get("jellyfin_host"):
            app.trigger_jellyfin_scan(job_id)
    except (IOError, shutil.Error) as e:
        log_job(job_id, logging.ERROR, f"Error copying files to Jellyfin: {e}")
        if job:
            job.update(message=f"Error copying files to Jellyfin: {e}")


def trigger_jellyfin_scan(app, job_id: str) -> None:
    job = app.jobs.get(job_id)
    if job:
        job.update(
            detailed_status="Triggering Jellyfin library scan",
            message="Triggering Jellyfin library scan",
        )
    api_key = app.config.get("jellyfin_api_key", "")
    host = app.config.get("jellyfin_host", "")
    port = app.config.get("jellyfin_port", "8096")
    if not api_key or not host:
        log_job(
            job_id,
            logging.WARNING,
            "Jellyfin API key or host not set, skipping library scan",
        )
        return
    url = f"http://{host}:{port}/Library/Refresh?api_key={api_key}"
    try:
        import requests

        response = requests.post(url, timeout=10)
        if response.status_code in (200, 204):
            log_job(
                job_id,
                logging.INFO,
                "Successfully triggered Jellyfin library scan",
            )
            if job:
                job.update(message="Successfully triggered Jellyfin library scan")
        else:
            log_job(
                job_id,
                logging.WARNING,
                "Failed to trigger Jellyfin scan: %s %s"
                % (response.status_code, response.text),
            )
            if job:
                job.update(
                    message=(
                        f"Failed to trigger Jellyfin scan: HTTP {response.status_code}"
                    )
                )
    except Exception as e:
        log_job(job_id, logging.ERROR, f"Error triggering Jellyfin scan: {e}")
        if job:
            job.update(message=f"Error triggering Jellyfin scan: {str(e)}")


__all__ = [
    "copy_to_jellyfin",
    "copy_movie_to_jellyfin",
    "trigger_jellyfin_scan",
]
