import os
import json
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, List

from .config import logger
from .utils import sanitize_name


def _load_playlists(playlists_file: str) -> Dict[str, Dict[str, str]]:
    if os.path.exists(playlists_file):
        try:
            with open(playlists_file, "r") as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError):
            logger.warning("Failed to load playlists file, starting fresh")
    return {}


def _save_playlists(playlists_file: str, playlists: Dict[str, Dict[str, str]]) -> None:
    os.makedirs(os.path.dirname(playlists_file), exist_ok=True)
    with open(playlists_file, "w") as f:
        json.dump(playlists, f, indent=2)


def _get_playlist_id(url: str) -> str:
    match = re.search(r"list=([^&]+)", url)
    if match:
        return match.group(1)
    return re.sub(r"\W+", "", url)


def _get_archive_file(url: str) -> str:
    pid = _get_playlist_id(url)
    return os.path.join("config", "archives", f"{pid}.txt")


def _is_playlist_url(url: str) -> bool:
    return "list=" in url or "/playlist" in url


def _register_playlist(playlists: Dict[str, Dict[str, str]], playlists_file: str, url: str, show_name: str, season_num: str) -> None:
    pid = _get_playlist_id(url)
    if pid not in playlists:
        playlists[pid] = {
            "url": url,
            "show_name": show_name,
            "season_num": season_num,
            "archive": _get_archive_file(url),
        }
        _save_playlists(playlists_file, playlists)


def _get_existing_max_index(folder: str, season_num: str) -> int:
    pattern = re.compile(rf"S{season_num}E(\d+)")
    max_idx = 0
    for file in Path(folder).glob(f"*S{season_num}E*.mp4"):
        match = pattern.search(file.name)
        if match:
            max_idx = max(max_idx, int(match.group(1)))
    return max_idx


def check_playlist_updates(app) -> List[str]:
    created_jobs = []
    for pid, info in app.playlists.items():
        archive = info.get("archive", _get_archive_file(info["url"]))
        try:
            result = subprocess.run(
                [app.config["ytdlp_path"], "--flat-playlist", "--dump-single-json", info["url"]],
                capture_output=True,
                text=True,
                check=True,
            )
            data = json.loads(result.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            logger.error(f"Failed to check playlist {info['url']}: {e}")
            continue

        ids = [e.get("id") for e in data.get("entries", []) if e.get("id")]
        archived = set()
        if os.path.exists(archive):
            with open(archive, "r") as f:
                archived = {line.strip() for line in f if line.strip()}
        new_ids = [vid for vid in ids if vid not in archived]
        if not new_ids:
            logger.info(f"No updates found for playlist {info['url']}")
            continue

        folder = app.create_folder_structure(info["show_name"], info["season_num"])
        start = _get_existing_max_index(folder, info["season_num"]) + 1
        job_id = app.create_job(info["url"], info["show_name"], info["season_num"], str(start).zfill(2))
        created_jobs.append(job_id)
    return created_jobs


def start_update_checker(app) -> None:
    def _run() -> None:
        interval = app.config.get("update_checker_interval", 60)
        while True:
            try:
                if app.playlists:
                    app.check_playlist_updates()
            except Exception as e:
                logger.error(f"Automatic update check failed: {e}")
            time.sleep(max(1, interval) * 60)

    app.update_thread = threading.Thread(target=_run, daemon=True)
    app.update_thread.start()

__all__ = [
    "_load_playlists",
    "_save_playlists",
    "_get_playlist_id",
    "_get_archive_file",
    "_is_playlist_url",
    "_register_playlist",
    "_get_existing_max_index",
    "check_playlist_updates",
    "start_update_checker",
]
