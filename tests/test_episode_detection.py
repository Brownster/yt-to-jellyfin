from pathlib import Path

import pytest

from tubarr.episode_detection import (
    AirdateEpisodeDetector,
    EpisodeDetectionError,
    FilenameEpisodeDetector,
    EpisodeMatch,
    EpisodeMetadata,
    clean_episode_title,
    parse_filename_episode,
    preview_filename_episodes,
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


@pytest.mark.parametrize(
    ("source", "season", "episode", "title"),
    [
        (
            "The Jerry Springer Show S24E28 - I Cheated With Three Strippers",
            24,
            28,
            "I Cheated With Three Strippers",
        ),
        (
            "The Jerry Springer Show S28E010 Homewreckers Move In 😡",
            28,
            10,
            "Homewreckers Move In",
        ),
        ("Show - s2 e13: A Title", 2, 13, "A Title"),
    ],
)
def test_parse_filename_episode(source, season, episode, title):
    parsed = parse_filename_episode(source)
    assert parsed == {"season": season, "episode": episode, "title": title}


def test_preview_marks_unrecognized_titles_for_manual_resolution():
    entries = preview_filename_episodes(
        [
            {"index": 1, "id": "one", "title": "Show S01E02 - Detected 💔"},
            {"index": 2, "id": "two", "title": "Unknown 😡 title"},
        ]
    )
    assert entries[0]["resolved"] is True
    assert entries[0]["title"] == "Detected"
    assert entries[1]["resolved"] is False
    assert entries[1]["title"] == "Unknown title"


def test_filename_detector_maps_by_source_id_and_uses_clean_title():
    detector = FilenameEpisodeDetector(
        [{"id": "video-id", "index": 8, "season": 24, "episode": 28, "title": "Finale 💔"}]
    )
    matches = detector.map_episodes(
        [
            EpisodeMetadata(
                title="source title",
                description="plot",
                upload_date=None,
                playlist_index=1,
                base_path="/tmp/video",
                source_id="video-id",
            )
        ]
    )
    assert matches[0].season == 24
    assert matches[0].episode == 28
    assert matches[0].title == "Finale"


def test_filename_detector_rejects_duplicate_episodes():
    with pytest.raises(EpisodeDetectionError, match="Duplicate episode mapping"):
        FilenameEpisodeDetector(
            [
                {"id": "one", "index": 1, "season": 1, "episode": 1, "title": "One"},
                {"id": "two", "index": 2, "season": 1, "episode": 1, "title": "Two"},
            ]
        )


def test_clean_episode_title_removes_emoji_and_extra_whitespace():
    assert clean_episode_title(" -  It's Over! 😡  ") == "It's Over!"
