import threading
from pathlib import Path

import pytest

from tubarr.core import YTToJellyfin
from tubarr.jobs import DownloadJob, TrackMetadata
from tubarr.media import write_m3u_playlist


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
        self.prepared_files_result = []
        self.m3u_outputs = []

    def check_dependencies(self):
        return self.dependencies_ok

    def create_music_album_folder(self, album_name, artist_name=None):
        base = Path(self.config["music_output_dir"])
        if artist_name:
            base = base / artist_name
        folder_path = base / album_name
        folder_path.mkdir(parents=True, exist_ok=True)
        self.created_folder = str(folder_path)
        return self.created_folder

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
        if not self.prepared_ok:
            return []
        if self.prepared_files_result:
            return list(self.prepared_files_result)
        return [
            Path(folder) / f"{idx + 1:02d} - Track{idx + 1}.mp3"
            for idx, _ in enumerate(downloaded_files)
        ]

    def copy_music_to_jellyfin(self, album_name, artist_name, job_id):
        expected_folder = str(
            Path(self.config["music_output_dir"]) / artist_name / album_name
        )
        # Ensure the helper observes the folder created earlier.
        assert self.created_folder == expected_folder
        self.copy_calls.append((album_name, artist_name, job_id, expected_folder))

    def write_m3u_playlist(self, prepared_files, *, base_path=None, playlist_name=None):
        path = write_m3u_playlist(
            self,
            prepared_files,
            base_path=base_path,
            playlist_name=playlist_name,
        )
        self.m3u_outputs.append(path)
        return path

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


def test_process_music_job_creates_m3u_when_requested(tmp_path, music_job):
    job_id, job = music_job
    app = FakeMusicApp()
    app.config["music_output_dir"] = str(tmp_path / "music")
    app.jobs[job_id] = job
    app.active_jobs.append(job_id)

    job.music_request = {
        "job_type": "playlist",
        "display_name": "Road Trip Mix",
        "collection": {"title": "Album", "variant": "standard"},
        "create_m3u": True,
        "m3u_path": str(tmp_path / "music"),
    }

    folder_path = Path(app.create_music_album_folder(job.album_name, job.artist_name))
    prepared_files = []
    for idx, _ in enumerate(job.tracks, start=1):
        file_path = folder_path / f"{idx:02d} - Prepared{idx}.mp3"
        file_path.write_text("data")
        prepared_files.append(file_path)
    app.prepared_files_result = prepared_files

    app.process_music_job(job_id)

    playlist_file = folder_path / "Road Trip Mix.m3u"
    assert playlist_file.exists()
    base_dir = Path(app.config["music_output_dir"]).resolve()
    expected_entries = [
        file.resolve().relative_to(base_dir).as_posix() for file in prepared_files
    ]
    contents = playlist_file.read_text().strip().splitlines()
    assert contents == expected_entries
    assert any("Created M3U playlist" in msg["text"] for msg in job.messages)
    assert len(app.m3u_outputs) == 1


def test_process_music_job_ignores_m3u_for_album(tmp_path, music_job):
    job_id, job = music_job
    app = FakeMusicApp()
    app.config["music_output_dir"] = str(tmp_path / "music")
    app.jobs[job_id] = job
    app.active_jobs.append(job_id)

    job.music_request = {
        "job_type": "album",
        "collection": {"title": "Album"},
        "create_m3u": True,
        "m3u_path": str(tmp_path / "music"),
    }

    folder_path = Path(app.create_music_album_folder(job.album_name, job.artist_name))
    prepared_files = []
    for idx, _ in enumerate(job.tracks, start=1):
        file_path = folder_path / f"{idx:02d} - Prepared{idx}.mp3"
        file_path.write_text("data")
        prepared_files.append(file_path)
    app.prepared_files_result = prepared_files

    app.process_music_job(job_id)

    assert not (folder_path / "Album.m3u").exists()
    assert not app.m3u_outputs
