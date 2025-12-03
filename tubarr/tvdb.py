import logging
from dataclasses import dataclass
from typing import Dict, Optional

import requests


logger = logging.getLogger("yt-to-jellyfin.tvdb")


class TVDBAuthenticationError(RuntimeError):
    """Raised when authentication with the TVDB API fails."""


class TVDBClient:
    """Minimal TVDB v4 client for air-date lookups.

    Only the endpoints required for mapping episode air dates to season/episode
    numbers are implemented so we can keep the dependency surface small and
    easily extend it later.
    """

    base_url = "https://api4.thetvdb.com/v4"

    def __init__(self, api_key: str, pin: Optional[str] = None):
        self.api_key = api_key
        self.pin = pin
        self._token: Optional[str] = None
        self._series_cache: Dict[str, int] = {}
        self.session = requests.Session()

    def _authenticate(self) -> None:
        if self._token:
            return
        payload = {"apikey": self.api_key}
        if self.pin:
            payload["pin"] = self.pin
        response = self.session.post(f"{self.base_url}/login", json=payload, timeout=15)
        if response.status_code != 200:
            raise TVDBAuthenticationError(
                f"TVDB authentication failed: {response.status_code}"
            )
        data = response.json()
        token = data.get("data", {}).get("token")
        if not token:
            raise TVDBAuthenticationError("TVDB authentication response missing token")
        self._token = token

    def _headers(self) -> Dict[str, str]:
        self._authenticate()
        return {"Authorization": f"Bearer {self._token}"}

    def _get_series_id(self, series_name: str) -> Optional[int]:
        cached = self._series_cache.get(series_name.lower())
        if cached:
            return cached
        params = {"query": series_name, "type": "series"}
        response = self.session.get(
            f"{self.base_url}/search", headers=self._headers(), params=params, timeout=15
        )
        if response.status_code != 200:
            logger.warning(
                "TVDB search failed for %s with status %s",
                series_name,
                response.status_code,
            )
            return None
        data = response.json().get("data") or []
        if not data:
            return None
        series_id = data[0].get("tvdb_id") or data[0].get("id")
        if series_id:
            self._series_cache[series_name.lower()] = int(series_id)
        return series_id

    @dataclass
    class EpisodeInfo:
        season: int
        episode: int
        air_date: Optional[str] = None

    def episode_by_air_date(
        self, series_name: str, air_date: str
    ) -> Optional["TVDBClient.EpisodeInfo"]:
        series_id = self._get_series_id(series_name)
        if not series_id:
            logger.warning("No TVDB series found for %s", series_name)
            return None
        params = {"airDate": air_date}
        response = self.session.get(
            f"{self.base_url}/series/{series_id}/episodes/default",
            headers=self._headers(),
            params=params,
            timeout=15,
        )
        if response.status_code != 200:
            logger.warning(
                "TVDB episode lookup failed for %s on %s with status %s",
                series_name,
                air_date,
                response.status_code,
            )
            return None
        data = response.json().get("data")
        if not data:
            return None

        # Handle both list and dict responses
        if isinstance(data, dict):
            episodes = data.get("episodes") or []
        elif isinstance(data, list):
            episodes = data
        else:
            logger.warning("Unexpected TVDB response structure for %s on %s", series_name, air_date)
            return None

        if not episodes:
            return None
        episode = episodes[0]
        try:
            season_num = int(episode.get("seasonNumber") or episode.get("season"))
            episode_num = int(episode.get("number") or episode.get("episodeNumber"))
        except (TypeError, ValueError):
            logger.warning("Invalid episode structure from TVDB for %s on %s", series_name, air_date)
            return None
        airdate = episode.get("aired") or episode.get("firstAired") or air_date
        return self.EpisodeInfo(season=season_num, episode=episode_num, air_date=airdate)


__all__ = ["TVDBClient", "TVDBAuthenticationError"]
