import threading

import pytest

from tubarr.jobs import DownloadJob, TrackMetadata, create_music_job


class StubApp:
    """Minimal app surface needed by the music job factory."""

    def __init__(self):
        self.jobs = {}
        self.job_lock = threading.Lock()
        self.job_queue = []
        self.active_jobs = []
        self.config = {"max_concurrent_jobs": 1}
        self.processed_job_ids = []

    def process_music_job(self, job_id):  # pragma: no cover - threads disabled in tests
        self.processed_job_ids.append(job_id)


def _playlist_request(**overrides):
    request = {
        "job_type": "playlist",
        "source_url": "https://example.com/playlist",
        "display_name": "Road Trip Mix",
        "collection": {
            "title": "Album",
            "owner": "Curator",
            "variant": "standard",
        },
        "tracks": [
            {
                "title": "Song A",
                "artist": "Artist",
                "album": "Album",
                "track_number": 1,
                "genres": ["Rock"],
                "tags": {"mood": "chill"},
            }
        ],
    }
    request.update(overrides)
    return request


def test_create_music_job_converts_track_dicts_to_metadata():
    app = StubApp()
    payload = _playlist_request(create_m3u=True, m3u_path="/tmp/playlists")

    job_id = create_music_job(app, payload, start_thread=False)

    job = app.jobs[job_id]
    assert isinstance(job, DownloadJob)
    assert job.media_type == "music"
    assert job.playlist_url == payload["source_url"]
    assert job.album_name == payload["collection"]["title"]
    assert job.artist_name == payload["collection"]["owner"]
    assert job.remaining_files == ["Song A"]
    assert all(isinstance(track, TrackMetadata) for track in job.tracks)
    assert job.tracks[0].genres == ["Rock"]
    assert job.tracks[0].extra["tags"] == {"mood": "chill"}
    assert job.music_request == payload
    assert job.music_request is not payload


def test_create_music_job_rejects_m3u_for_non_playlist():
    app = StubApp()
    payload = _playlist_request(job_type="album", create_m3u=True)
    payload["collection"].pop("variant", None)
    payload["collection"]["artist"] = "Artist"

    with pytest.raises(ValueError):
        create_music_job(app, payload, start_thread=False)


def test_create_music_job_accepts_trackmetadata_instances():
    app = StubApp()
    track = TrackMetadata(
        title="Intro",
        artist="Artist",
        album="Album",
        track_number=1,
        total_tracks=2,
    )
    payload = _playlist_request(tracks=[track])

    job_id = create_music_job(app, payload, start_thread=False)

    job = app.jobs[job_id]
    assert len(job.tracks) == 1
    assert isinstance(job.tracks[0], TrackMetadata)
    assert job.tracks[0].title == "Intro"
    assert job.detailed_status == "Music job queued"
    assert job.messages[-1]["text"] == "Music job created and queued for processing"
