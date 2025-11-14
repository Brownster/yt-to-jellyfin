import threading

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


def test_create_music_job_enforces_track_metadata_schema():
    app = StubApp()
    track = TrackMetadata(
        title="Song A", artist="Artist", album="Album", track_number=1
    )
    job_id = create_music_job(
        app,
        "https://example.com/playlist",
        "Album",
        "Artist",
        tracks=[track, {"title": "bad"}],
        start_thread=False,
    )

    job = app.jobs[job_id]
    assert isinstance(job, DownloadJob)
    # Only the TrackMetadata instance should contribute to the remaining queue.
    assert job.remaining_files == ["Song A"]
    # The raw track list is preserved for downstream processing.
    assert job.tracks == [track, {"title": "bad"}]


def test_create_music_job_populates_expected_metadata_fields():
    app = StubApp()
    tracks = [
        TrackMetadata(
            title="Intro",
            artist="Artist",
            album="Album",
            track_number=1,
            total_tracks=2,
        )
    ]

    job_id = create_music_job(
        app,
        "https://example.com/playlist",
        "Album",
        "Artist",
        tracks=tracks,
        playlist_start=5,
        start_thread=False,
    )

    job = app.jobs[job_id]
    assert job.playlist_url == "https://example.com/playlist"
    assert job.album_name == "Album"
    assert job.artist_name == "Artist"
    assert job.media_type == "music"
    assert job.playlist_start == 5
    assert job.tracks == tracks
    assert job.detailed_status == "Music job queued"
    assert job.messages[-1]["text"] == "Music job created and queued for processing"
