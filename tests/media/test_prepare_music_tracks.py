import io
from types import SimpleNamespace

import pytest
from mutagen.id3 import ID3

from tubarr.media import (
    _apply_track_metadata,
    _ensure_mp3,
    download_music_tracks,
    prepare_music_tracks,
)
from tubarr.jobs import TrackMetadata


class DummyJob:
    def __init__(self):
        self.status = "queued"
        self.progress = 0
        self.current_stage = ""
        self.stage_progress = 0
        self.current_file = ""
        self.total_files = 0
        self.processed_files = 0
        self.detailed_status = ""
        self.messages = []
        self.remaining_files = []
        self.process = None
        self.updates = []

    def update(
        self,
        *,
        status=None,
        progress=None,
        message=None,
        stage=None,
        file_name=None,
        stage_progress=None,
        total_files=None,
        processed_files=None,
        detailed_status=None,
        current_file=None,
    ):
        update = {}
        if status is not None:
            self.status = status
            update["status"] = status
        if progress is not None:
            self.progress = progress
            update["progress"] = progress
        if stage is not None:
            self.current_stage = stage
            update["stage"] = stage
        if file_name is not None:
            self.current_file = file_name
            update["file_name"] = file_name
        if stage_progress is not None:
            self.stage_progress = stage_progress
            update["stage_progress"] = stage_progress
        if total_files is not None:
            self.total_files = total_files
            update["total_files"] = total_files
        if processed_files is not None:
            self.processed_files = processed_files
            update["processed_files"] = processed_files
        if detailed_status is not None:
            self.detailed_status = detailed_status
            update["detailed_status"] = detailed_status
        if current_file is not None:
            self.current_file = current_file
            update["current_file"] = current_file
        if message is not None:
            self.messages.append(message)
            update["message"] = message
        self.updates.append(update)


@pytest.fixture
def job():
    return DummyJob()


def make_app(config, job_id, job_obj):
    jobs = {job_id: job_obj}
    return SimpleNamespace(config=config, jobs=jobs)


def test_prepare_music_tracks_places_files_and_tags(tmp_path, monkeypatch, job):
    folder = tmp_path / "Album"
    folder.mkdir()
    source_file = folder / "001_-_Song_Title.mp3"
    source_file.write_bytes(b"audio")

    job_id = "job-1"
    job.remaining_files = [source_file.name]
    app = make_app({"clean_filenames": True}, job_id, job)

    captured_tags = []

    def fake_apply(path, metadata, job_id_arg):
        captured_tags.append((path, metadata, job_id_arg))

    monkeypatch.setattr("tubarr.media._apply_track_metadata", fake_apply)

    tracks = [
        TrackMetadata(
            title="Song_Title",
            artist="Artist",
            album="Album",
            track_number=1,
            total_tracks=2,
        )
    ]

    prepared = prepare_music_tracks(app, str(folder), tracks, [source_file], job_id)

    assert len(prepared) == 1
    final_path = prepared[0]
    assert final_path.name == "01 - Song Title.mp3"
    assert final_path.exists()
    assert captured_tags == [(final_path, tracks[0], job_id)]
    assert any(update.get("processed_files") == 1 for update in job.updates)


def test_prepare_music_tracks_stops_on_conversion_error(tmp_path, monkeypatch, job):
    folder = tmp_path / "Album"
    folder.mkdir()
    first = folder / "001_-_First.mp3"
    second = folder / "002_-_Second.mp3"
    first.write_bytes(b"one")
    second.write_bytes(b"two")

    job_id = "job-2"
    job.remaining_files = [first.name, second.name]
    app = make_app({"clean_filenames": True}, job_id, job)

    call_count = {"count": 0}

    def fake_ensure(path, job_id_arg, job_obj):
        call_count["count"] += 1
        if call_count["count"] == 2:
            raise RuntimeError("ffmpeg failed")
        return path

    monkeypatch.setattr("tubarr.media._ensure_mp3", fake_ensure)
    monkeypatch.setattr("tubarr.media._apply_track_metadata", lambda *args, **kwargs: None)

    tracks = [
        TrackMetadata(title="First", artist="A", album="Album", track_number=1),
        TrackMetadata(title="Second", artist="A", album="Album", track_number=2),
    ]

    prepared = prepare_music_tracks(
        app, str(folder), tracks, [first, second], job_id
    )

    assert [p.name for p in prepared] == ["01 - First.mp3"]
    assert (folder / "01 - First.mp3").exists()
    assert (folder / "002_-_Second.mp3").exists()


def test_apply_track_metadata_writes_id3_tags(tmp_path, monkeypatch, job):
    track_file = tmp_path / "track.mp3"
    track_file.write_bytes(b"")
    cover_bytes = b"fake-image"

    class FakeResponse:
        def __init__(self, content):
            self.content = content

        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        "tubarr.media.requests.get", lambda url, timeout: FakeResponse(cover_bytes)
    )

    metadata = TrackMetadata(
        title="Title",
        artist="Artist",
        album="Album",
        track_number=3,
        total_tracks=10,
        disc_number=1,
        total_discs=2,
        release_date="2024",
        genres=["Rock", "Indie"],
        cover_url="https://example.com/cover.jpg",
        album_artist="Band",
    )

    _apply_track_metadata(track_file, metadata, "job-3")

    tags = ID3(str(track_file))
    assert tags["TIT2"].text[0] == "Title"
    assert tags["TPE1"].text[0] == "Artist"
    assert tags["TALB"].text[0] == "Album"
    assert tags["TPE2"].text[0] == "Band"
    assert tags["TRCK"].text[0] == "3/10"
    assert tags["TPOS"].text[0] == "1/2"
    assert str(tags["TDRC"].text[0]) == "2024"
    assert tags["TCON"].text[0] == "Rock, Indie"
    apic_frames = tags.getall("APIC")
    assert len(apic_frames) == 1
    assert apic_frames[0].data == cover_bytes


def test_ensure_mp3_converts_and_removes_source(tmp_path, monkeypatch, job):
    source = tmp_path / "song.wav"
    source.write_bytes(b"wave")
    created = tmp_path / "song.mp3"

    class Result:
        def __init__(self, returncode=0):
            self.returncode = returncode
            self.stderr = ""

    def fake_run(cmd, capture_output, text):
        created.write_bytes(b"mp3")
        return Result(0)

    monkeypatch.setattr("tubarr.media.run_subprocess", fake_run)

    result = _ensure_mp3(source, "job-4", job)

    assert result == created
    assert created.exists()
    assert not source.exists()


def test_ensure_mp3_raises_on_failure(tmp_path, monkeypatch, job):
    source = tmp_path / "song.wav"
    source.write_bytes(b"wave")

    class Result:
        def __init__(self):
            self.returncode = 1
            self.stderr = "boom"

    monkeypatch.setattr("tubarr.media.run_subprocess", lambda *args, **kwargs: Result())

    with pytest.raises(RuntimeError):
        _ensure_mp3(source, "job-5", job)

    assert source.exists()


class FakeProcess:
    def __init__(self, cmd, lines, returncode=0):
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = io.StringIO("\n".join(lines))
        self._waited = False
        self.pid = 1234

    def wait(self):
        self._waited = True
        return self.returncode

    def poll(self):
        return self.returncode if self._waited else None


def test_download_music_tracks_collects_downloads(tmp_path, monkeypatch, job):
    audio_one = tmp_path / "002 - Second.mp3"
    audio_two = tmp_path / "001 - First.flac"
    noise = tmp_path / "info.json"
    audio_one.write_bytes(b"mp3")
    audio_two.write_bytes(b"flac")
    noise.write_text("{}")

    lines = [
        f"Destination: {tmp_path / '002 - Second.mp3'}",
        "[download] 1 of 2 items",
        "[download] 50.0% of 2 items",
        "misc status",
    ]

    factory_calls = []

    def popen_factory(cmd, stdout=None, stderr=None, universal_newlines=None, start_new_session=None):
        factory_calls.append(cmd)
        return FakeProcess(cmd, lines, returncode=0)

    monkeypatch.setattr("tubarr.media.subprocess.Popen", popen_factory)

    job_id = "job-6"
    job.remaining_files = []
    config = {"ytdlp_path": "/usr/bin/yt-dlp", "cookies": ""}

    def get_archive(_url):
        return str(tmp_path / "archives" / "archive.txt")

    app = make_app(config, job_id, job)
    app._get_archive_file = get_archive

    result = download_music_tracks(app, "https://example.com", str(tmp_path), job_id)

    assert [p.name for p in result] == ["001 - First.flac", "002 - Second.mp3"]
    assert job.status == "downloaded"
    assert job.progress == 100
    assert job.process is None
    assert any("--no-cookies" in cmd for cmd in factory_calls)


def test_download_music_tracks_returns_empty_on_failure(tmp_path, monkeypatch, job):
    lines = ["error"]

    def popen_factory(cmd, stdout=None, stderr=None, universal_newlines=None, start_new_session=None):
        return FakeProcess(cmd, lines, returncode=1)

    monkeypatch.setattr("tubarr.media.subprocess.Popen", popen_factory)

    job_id = "job-7"
    config = {"ytdlp_path": "/usr/bin/yt-dlp", "cookies": ""}

    def get_archive(_url):
        return str(tmp_path / "archives" / "archive.txt")

    app = make_app(config, job_id, job)
    app._get_archive_file = get_archive

    result = download_music_tracks(app, "https://example.com", str(tmp_path), job_id)

    assert result == []
    assert job.status == "failed"

