import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable, List, Optional

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
    "EpisodeMatch",
    "EpisodeMetadata",
]
