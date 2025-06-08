import os
import json
from typing import Dict

from .config import logger
from .utils import sanitize_name


def _load_episode_tracker(episodes_file: str) -> Dict[str, Dict[str, int]]:
    if os.path.exists(episodes_file):
        try:
            with open(episodes_file, "r") as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError):
            logger.warning("Failed to load episode tracker, starting fresh")
    return {}


def _save_episode_tracker(episodes_file: str, data: Dict[str, Dict[str, int]]) -> None:
    os.makedirs(os.path.dirname(episodes_file), exist_ok=True)
    with open(episodes_file, "w") as f:
        json.dump(data, f, indent=2)


def get_last_episode(tracker: Dict[str, Dict[str, int]], show_name: str, season_num: str) -> int:
    return tracker.get(sanitize_name(show_name), {}).get(season_num, 0)


def update_last_episode(
    tracker: Dict[str, Dict[str, int]],
    episodes_file: str,
    show_name: str,
    season_num: str,
    last_episode: int,
) -> None:
    key = sanitize_name(show_name)
    tracker.setdefault(key, {})[season_num] = last_episode
    _save_episode_tracker(episodes_file, tracker)


__all__ = [
    "_load_episode_tracker",
    "_save_episode_tracker",
    "get_last_episode",
    "update_last_episode",
]
