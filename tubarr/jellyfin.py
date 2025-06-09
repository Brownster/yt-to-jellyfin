import os
import shutil
from pathlib import Path

from .config import logger


def copy_to_jellyfin(app, show_name: str, season_num: str, job_id: str) -> None:
    if not app.config.get("jellyfin_enabled", False):
        logger.info("Jellyfin integration disabled, skipping file copy")
        return
    jellyfin_tv_path = app.config.get("jellyfin_tv_path", "")
    if not jellyfin_tv_path:
        logger.error("Jellyfin TV path not configured, skipping file copy")
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
            if os.path.exists(dest_file) and os.path.getsize(
                dest_file
            ) == os.path.getsize(file_path):
                logger.info(f"Skipping {file_path.name} - already exists and same size")
                if job:
                    job.update(
                        processed_files=i + 1,
                        message=f"Skipped {file_path.name} - already exists",
                    )
                continue
            shutil.copy2(file_path, dest_file)
            logger.info(f"Copied {file_path.name} to Jellyfin")
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
                logger.info(f"Copied show file {source.name} to Jellyfin")
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
        logger.error(f"Error copying files to Jellyfin: {e}")
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
            logger.warning(
                "Failed to trigger Jellyfin scan: %s %s"
                % (response.status_code, response.text)
            )
            if job:
                job.update(
                    message=(
                        f"Failed to trigger Jellyfin scan: HTTP {response.status_code}"
                    )
                )
    except Exception as e:
        logger.error(f"Error triggering Jellyfin scan: {e}")
        if job:
            job.update(message=f"Error triggering Jellyfin scan: {str(e)}")


__all__ = ["copy_to_jellyfin", "trigger_jellyfin_scan"]
