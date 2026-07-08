import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from .tvdb import TVDBClient


logger = logging.getLogger("yt-to-jellyfin.episode_detection")


@dataclass
class EpisodeMetadata:
    """Lightweight representation of metadata extracted from a video JSON file."""

    title: str
    description: str
    upload_date: Optional[str]
    playlist_index: int
    base_path: str
    source_id: Optional[str] = None


@dataclass
class EpisodeMatch:
    """Resolved season/episode information for a single video."""

    season: int
    episode: int
    air_date: Optional[str]
    base_path: str
    title: str
    description: str


class EpisodeDetectionError(RuntimeError):
    """Raised when automatic episode mapping fails."""


_EPISODE_CODE = re.compile(
    r"(?i)(?:^|\s|[-_.])S\s*(\d+)\s*[-_. ]*E\s*(\d+)(?=$|\s|[-_.:])"
)
_EMOJI = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0000FE0F"
    "\U0000200D"
    "]+",
    flags=re.UNICODE,
)


def clean_episode_title(value: str) -> str:
    """Remove emoji, control characters, separators, and excess whitespace."""

    value = _EMOJI.sub("", value or "")
    value = "".join(
        char for char in value if not unicodedata.category(char).startswith("C")
    )
    value = re.sub(r"^[\s\-_.:|]+", "", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_filename_episode(title: str) -> Optional[Dict[str, Any]]:
    """Extract an SxxExx marker and normalized episode title."""

    match = _EPISODE_CODE.search(title or "")
    if not match:
        return None
    season = int(match.group(1))
    episode = int(match.group(2))
    if season < 0 or episode < 1:
        return None
    episode_title = clean_episode_title((title or "")[match.end() :])
    if not episode_title:
        episode_title = f"Episode {episode}"
    return {"season": season, "episode": episode, "title": episode_title}


def preview_filename_episodes(videos: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build editable filename-detection results for a source item list."""

    results = []
    for position, video in enumerate(videos, start=1):
        index = int(video.get("index") or video.get("playlist_index") or position)
        source_id = str(video.get("id") or index)
        original_title = str(video.get("title") or "Unknown title")
        parsed = parse_filename_episode(original_title)
        results.append(
            {
                "id": source_id,
                "index": index,
                "original_title": original_title,
                "season": parsed["season"] if parsed else None,
                "episode": parsed["episode"] if parsed else None,
                "title": parsed["title"] if parsed else clean_episode_title(original_title),
                "resolved": parsed is not None,
            }
        )
    return results


class FilenameEpisodeDetector:
    """Map downloaded items to user-approved filename episode metadata."""

    include_episode_title = True

    def __init__(self, mappings: Sequence[Dict[str, Any]]) -> None:
        self.by_id: Dict[str, Dict[str, Any]] = {}
        self.by_index: Dict[int, Dict[str, Any]] = {}
        seen_episodes = set()
        for mapping in mappings:
            try:
                season = int(mapping["season"])
                episode = int(mapping["episode"])
                index = int(mapping["index"])
            except (KeyError, TypeError, ValueError) as exc:
                raise EpisodeDetectionError("Invalid filename episode mapping") from exc
            if season < 0 or episode < 1 or index < 1:
                raise EpisodeDetectionError(
                    "Season must be non-negative; episode and index must be positive"
                )
            episode_key = (season, episode)
            if episode_key in seen_episodes:
                raise EpisodeDetectionError(
                    f"Duplicate episode mapping S{season:02d}E{episode:02d}"
                )
            seen_episodes.add(episode_key)
            normalized = {
                "id": str(mapping.get("id") or index),
                "index": index,
                "season": season,
                "episode": episode,
                "title": clean_episode_title(str(mapping.get("title") or ""))
                or f"Episode {episode}",
            }
            self.by_id[normalized["id"]] = normalized
            self.by_index[index] = normalized

    def map_episodes(self, videos: List[EpisodeMetadata]) -> List[EpisodeMatch]:
        matches = []
        for meta in videos:
            mapping = None
            if meta.source_id:
                mapping = self.by_id.get(str(meta.source_id))
            if mapping is None:
                mapping = self.by_index.get(meta.playlist_index)
            if mapping is None:
                raise EpisodeDetectionError(
                    f"No filename episode mapping for '{meta.title}'"
                )
            matches.append(
                EpisodeMatch(
                    season=mapping["season"],
                    episode=mapping["episode"],
                    air_date=None,
                    base_path=meta.base_path,
                    title=mapping["title"],
                    description=meta.description,
                )
            )
        return matches


def _normalize_upload_date(upload_date: Optional[str]) -> Optional[str]:
    if not upload_date:
        return None
    try:
        return datetime.strptime(upload_date, "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_jeremy_kyle_date(title: str) -> Optional[str]:
    """Parse dates like "1st May 2019" or "9th_March_2018" from the title string.

    This is intentionally separated so we can easily register additional
    patterns later without touching the core mapping logic.
    """

    # Handle both spaces and underscores as separators
    match = re.search(r"(\d{1,2})(st|nd|rd|th)?[\s_]+([A-Za-z]+)[\s_]+(\d{4})", title)
    if not match:
        return None
    day = match.group(1)
    month = match.group(3)
    year = match.group(4)
    try:
        cleaned = f"{day} {month} {year}"
        parsed = datetime.strptime(cleaned, "%d %B %Y")
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        return None


class AirdateEpisodeDetector:
    """Map videos to episodes using air date lookups against TVDB."""

    def __init__(
        self,
        tvdb: TVDBClient,
        show_name: str,
        *,
        extra_date_parsers: Optional[Iterable[Callable[[str], Optional[str]]]] = None,
    ) -> None:
        self.tvdb = tvdb
        self.show_name = show_name
        self.date_parsers = [_parse_jeremy_kyle_date]
        if extra_date_parsers:
            self.date_parsers.extend(extra_date_parsers)

    def _extract_air_date(self, meta: EpisodeMetadata) -> Optional[str]:
        normalized = _normalize_upload_date(meta.upload_date)
        if normalized:
            return normalized
        for parser in self.date_parsers:
            value = parser(meta.title)
            if value:
                return value
        return None

    def map_episodes(self, videos: List[EpisodeMetadata]) -> List[EpisodeMatch]:
        matches: List[EpisodeMatch] = []
        for meta in videos:
            air_date = self._extract_air_date(meta)
            if not air_date:
                raise EpisodeDetectionError(
                    f"Could not determine air date for '{meta.title}'"
                )
            episode_info = self.tvdb.episode_by_air_date(self.show_name, air_date)
            if not episode_info:
                raise EpisodeDetectionError(
                    f"TVDB lookup failed for '{self.show_name}' on {air_date}"
                )
            matches.append(
                EpisodeMatch(
                    season=episode_info.season,
                    episode=episode_info.episode,
                    air_date=episode_info.air_date,
                    base_path=meta.base_path,
                    title=meta.title,
                    description=meta.description,
                )
            )
        return matches


__all__ = [
    "AirdateEpisodeDetector",
    "EpisodeDetectionError",
    "FilenameEpisodeDetector",
    "EpisodeMatch",
    "EpisodeMetadata",
    "clean_episode_title",
    "parse_filename_episode",
    "preview_filename_episodes",
]
