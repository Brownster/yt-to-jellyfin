import threading
from pathlib import Path

import pytest

from tubarr.core import YTToJellyfin
from tubarr.jobs import DownloadJob, TrackMetadata


class FakeMusicApp:
    """Lightweight stand-in for YTToJellyfin focused on music jobs."""

    process_music_job = YTToJellyfin.process_music_job

    def __init__(self):
        self.config = {
            "jellyfin_enabled": True,
            "jellyfin_music_path": "/jellyfin/music",
            "music_output_dir": "/tmp/music-out",
            "max_concurrent_jobs": 1,
        }
        self.jobs = {}
        self.job_lock = threading.Lock()
        self.job_queue = []
        self.active_jobs = []
        self.dependencies_ok = True
        self.downloaded_files = ["track1.mp3", "track2.mp3"]
        self.prepared_ok = True
        self.cancel_during_download = False
        self.cancel_during_prepare = False
        self.created_folder = None
        self.download_calls = []
        self.prepare_calls = []
        self.copy_calls = []
        self.completed_jobs = []

    def check_dependencies(self):
        return self.dependencies_ok

    def create_music_album_folder(self, album_name, artist_name=None):
        base = Path(self.config["music_output_dir"])
        if artist_name:
            base = base / artist_name
        folder = str(base / album_name)
        self.created_folder = folder
        return folder

    def download_music_tracks(self, playlist_url, folder, job_id, playlist_start):
        self.download_calls.append((playlist_url, folder, job_id, playlist_start))
        assert folder == self.created_folder
        if self.cancel_during_download:
            self.jobs[job_id].status = "cancelled"
        return list(self.downloaded_files)

    def prepare_music_tracks(self, folder, tracks, downloaded_files, job_id):
        self.prepare_calls.append((folder, list(tracks), list(downloaded_files), job_id))
        assert folder == self.created_folder
        if self.cancel_during_prepare:
            self.jobs[job_id].status = "cancelled"
        return self.prepared_ok

    def copy_music_to_jellyfin(self, album_name, artist_name, job_id):
        expected_folder = str(
            Path(self.config["music_output_dir"]) / artist_name / album_name
        )
        # Ensure the helper observes the folder created earlier.
        assert self.created_folder == expected_folder
        self.copy_calls.append((album_name, artist_name, job_id, expected_folder))

    def _on_job_complete(self, job_id):
        self.completed_jobs.append(job_id)
        if job_id in self.active_jobs:
            self.active_jobs.remove(job_id)
        while self.job_queue:
            self.job_queue.pop(0)


@pytest.fixture
def music_job():
    job_id = "job-123"
    job = DownloadJob(
        job_id,
        "https://example.com/playlist",
        "Test Album",
        "",
        "1",
        media_type="music",
        album_name="Album",
        artist_name="Artist",
        tracks=[
            TrackMetadata(
                title="Song A",
                artist="Artist",
                album="Album",
                track_number=1,
            )
        ],
    )
    return job_id, job


def test_process_music_job_happy_path_triggers_copy_with_expected_folder(music_job):
    job_id, job = music_job
    app = FakeMusicApp()
    app.jobs[job_id] = job
    app.active_jobs.append(job_id)

    app.process_music_job(job_id)

    assert job.status == "completed"
    assert job.progress == 100
    assert app.copy_calls == [("Album", "Artist", job_id, app.created_folder)]
    assert app.completed_jobs == [job_id]


def test_process_music_job_halts_on_cancellation(music_job):
    job_id, job = music_job
    app = FakeMusicApp()
    app.cancel_during_download = True
    app.jobs[job_id] = job

    app.process_music_job(job_id)

    assert job.status == "cancelled"
    assert app.prepare_calls == []
    assert app.copy_calls == []
    assert app.completed_jobs == [job_id]


def test_process_music_job_marks_failure_on_dependency_error(music_job):
    job_id, job = music_job
    app = FakeMusicApp()
    app.dependencies_ok = False
    app.jobs[job_id] = job

    app.process_music_job(job_id)

    assert job.status == "failed"
    # When dependencies are missing, no downstream work should run.
    assert app.download_calls == []
    assert app.copy_calls == []
    assert app.completed_jobs == [job_id]
