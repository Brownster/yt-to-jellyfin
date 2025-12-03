from pathlib import Path

import pytest

from tubarr.episode_detection import (
    AirdateEpisodeDetector,
    EpisodeDetectionError,
    EpisodeMatch,
    EpisodeMetadata,
)
from tubarr.tvdb import TVDBClient


class DummyTVDB:
    def __init__(self, episode_info):
        self.episode_info = episode_info
        self.calls = []

    def episode_by_air_date(self, show_name, air_date):
        self.calls.append((show_name, air_date))
        return self.episode_info


def test_jeremy_kyle_date_parsing(monkeypatch):
    episode = TVDBClient.EpisodeInfo(season=19, episode=120, air_date="2019-05-01")
    detector = AirdateEpisodeDetector(DummyTVDB(episode), "The Jeremy Kyle Show")

    meta = EpisodeMetadata(
        title="The Jeremy Kyle Show 1st May 2019",
        description="",
        upload_date="",
        playlist_index=1,
        base_path=str(Path("/tmp/test/info")),
    )

    matches = detector.map_episodes([meta])
    assert matches[0].season == 19
    assert matches[0].episode == 120
    assert matches[0].air_date == "2019-05-01"


def test_episode_detection_errors_when_missing_dates():
    episode = TVDBClient.EpisodeInfo(season=1, episode=1, air_date="2020-01-01")
    detector = AirdateEpisodeDetector(DummyTVDB(episode), "Some Show")

    meta = EpisodeMetadata(
        title="Untitled Clip",
        description="",
        upload_date="",
        playlist_index=1,
        base_path=str(Path("/tmp/test/info")),
    )

    with pytest.raises(EpisodeDetectionError):
        detector.map_episodes([meta])
