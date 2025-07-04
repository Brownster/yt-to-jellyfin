import os
import json
import re
import subprocess
import threading
from pathlib import Path
from typing import Dict, List, Optional

from .config import logger


def _load_playlists(playlists_file: str) -> Dict[str, Dict[str, str]]:
    if os.path.exists(playlists_file):
        try:
            with open(playlists_file, "r") as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError):
            logger.warning("Failed to load playlists file, starting fresh")
    return {}


def _save_playlists(playlists_file: str, playlists: Dict[str, Dict[str, str]]) -> None:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
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


def _register_playlist(
    playlists: Dict[str, Dict[str, str]],
    playlists_file: str,
    url: str,
    show_name: str,
    season_num: str,
    start_index: Optional[int] = None,
) -> bool:
    """Add a playlist to the tracking file if not already present."""
    pid = _get_playlist_id(url)
    if pid not in playlists:
        playlists[pid] = {
            "url": url,
            "show_name": show_name,
            "season_num": season_num,
            "archive": _get_archive_file(url),
            "disabled": False,
            "start_index": int(start_index or 1),
        }
        _save_playlists(playlists_file, playlists)
        return True
    return False


def _set_playlist_enabled(
    playlists: Dict[str, Dict[str, str]],
    playlists_file: str,
    pid: str,
    enabled: bool,
) -> bool:
    """Enable or disable a tracked playlist."""
    if pid in playlists:
        playlists[pid]["disabled"] = not enabled
        _save_playlists(playlists_file, playlists)
        return True
    return False


def _remove_playlist(
    playlists: Dict[str, Dict[str, str]], playlists_file: str, pid: str
) -> bool:
    """Remove a playlist from tracking."""
    if pid in playlists:
        playlists.pop(pid, None)
        _save_playlists(playlists_file, playlists)
        return True
    return False


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
        if info.get("disabled"):
            continue
        archive = info.get("archive", _get_archive_file(info["url"]))
        try:
            result = subprocess.run(
                [
                    app.config["ytdlp_path"],
                    "--flat-playlist",
                    "--dump-single-json",
                    info["url"],
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            data = json.loads(result.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            logger.error(f"Failed to check playlist {info['url']}: {e}")
            continue

        start_index = int(info.get("start_index", 1))
        ids = [
            e.get("id")
            for idx, e in enumerate(data.get("entries", []), start=1)
            if idx >= start_index and e.get("id")
        ]
        archived = set()
        if os.path.exists(archive):
            with open(archive, "r") as f:
                archived = {line.strip() for line in f if line.strip()}
        new_ids = [vid for vid in ids if vid not in archived]
        if not new_ids:
            logger.info(f"No updates found for playlist {info['url']}")
            continue

        folder = app.create_folder_structure(info["show_name"], info["season_num"])
        last_ep = app.get_last_episode(info["show_name"], info["season_num"])
        if last_ep == 0:
            last_ep = _get_existing_max_index(folder, info["season_num"])
        start = last_ep + 1
        if start_index != 1:
            job_id = app.create_job(
                info["url"],
                info["show_name"],
                info["season_num"],
                str(start).zfill(2),
                playlist_start=start_index,
            )
        else:
            job_id = app.create_job(
                info["url"],
                info["show_name"],
                info["season_num"],
                str(start).zfill(2),
            )
        created_jobs.append(job_id)
    return created_jobs


def start_update_checker(app) -> None:
    """Start a background thread that periodically checks for playlist updates."""

    if not getattr(app, "update_stop_event", None):
        app.update_stop_event = threading.Event()
    else:
        app.update_stop_event.clear()

    def _run() -> None:
        interval = app.config.get("update_checker_interval", 60)
        while not app.update_stop_event.is_set():
            try:
                if app.playlists:
                    app.check_playlist_updates()
            except Exception as e:
                logger.error(f"Automatic update check failed: {e}")
            app.update_stop_event.wait(max(1, interval) * 60)

    app.update_thread = threading.Thread(target=_run, daemon=True)
    app.update_thread.start()


def stop_update_checker(app) -> None:
    """Signal the background update checker thread to stop and wait for it."""
    if getattr(app, "update_stop_event", None):
        app.update_stop_event.set()
    if getattr(app, "update_thread", None):
        app.update_thread.join()


__all__ = [
    "_load_playlists",
    "_save_playlists",
    "_get_playlist_id",
    "_get_archive_file",
    "_is_playlist_url",
    "_register_playlist",
    "_set_playlist_enabled",
    "_remove_playlist",
    "_get_existing_max_index",
    "check_playlist_updates",
    "start_update_checker",
    "stop_update_checker",
]
