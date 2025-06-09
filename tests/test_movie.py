import os
import tempfile
import shutil
import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from tubarr.core import YTToJellyfin, DownloadJob
from tubarr import jellyfin as jellyfin_mod


class TestMovieWorkflow(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.jellyfin_dir = tempfile.mkdtemp()
        self.config = {
            "output_dir": self.temp_dir,
            "quality": "720",
            "use_h265": False,
            "crf": 28,
            "ytdlp_path": "yt-dlp",
            "cookies": "",
            "completed_jobs_limit": 3,
            "max_concurrent_jobs": 1,
            "web_enabled": False,
            "web_port": 8000,
            "web_host": "0.0.0.0",
            "jellyfin_enabled": True,
            "jellyfin_tv_path": "",
            "jellyfin_movie_path": self.jellyfin_dir,
            "jellyfin_host": "localhost",
            "jellyfin_port": "8096",
            "jellyfin_api_key": "",
            "clean_filenames": True,
            "update_checker_enabled": False,
            "update_checker_interval": 60,
        }
        with patch.object(YTToJellyfin, "_load_config", return_value=self.config), patch.object(YTToJellyfin, "_load_playlists", return_value={}):
            self.app = YTToJellyfin()
        self.job = DownloadJob("job1", "url", "", "", "", media_type="movie", movie_name="Test Movie")
        self.app.jobs["job1"] = self.job

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.jellyfin_dir, ignore_errors=True)

    def test_create_movie_job(self):
        with patch("threading.Thread") as mock_thread:
            job_id = self.app.create_movie_job("https://youtube.com/watch?v=abc", "My Movie")
            self.assertIn(job_id, self.app.jobs)
            job = self.app.jobs[job_id]
            self.assertEqual(job.media_type, "movie")
            self.assertEqual(job.movie_name, "My Movie")
            mock_thread.assert_called_once()
            mock_thread.return_value.start.assert_called_once()

    def test_process_movie_metadata_creates_nfo(self):
        folder = Path(self.temp_dir) / "Test Movie"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "video.mp4").write_text("data")
        info = {"description": "Desc", "upload_date": "20220101", "id": "abc"}
        with open(folder / "video.info.json", "w") as f:
            json.dump(info, f)
        with patch("subprocess.run") as mock_run:
            self.app.process_movie_metadata(str(folder), "Test Movie", "job1")
        nfo = folder / "movie.nfo"
        self.assertTrue(nfo.exists())
        with open(nfo) as f:
            content = f.read()
        self.assertIn("<movie>", content)
        renamed = folder / "Test Movie (2022) [abc].mp4"
        self.assertTrue(renamed.exists())
        self.assertFalse((folder / "video.mp4").exists())

    def test_copy_movie_to_jellyfin(self):
        src_folder = Path(self.temp_dir) / "Test Movie"
        src_folder.mkdir(parents=True, exist_ok=True)
        (src_folder / "Test Movie.mp4").touch()
        (src_folder / "movie.nfo").touch()
        dest_folder = Path(self.jellyfin_dir) / "Test Movie"
        with patch("os.path.exists", side_effect=lambda p: False if str(p).startswith(str(dest_folder)) else os.path.exists(p)), patch("os.makedirs") as mock_mkdir, patch("shutil.copy2") as mock_copy2, patch.object(self.app, "trigger_jellyfin_scan") as mock_scan:
            jellyfin_mod.copy_movie_to_jellyfin(self.app, "Test Movie", "job1")
            mock_mkdir.assert_called_with(dest_folder, exist_ok=True)
            expected_calls = [
                call(src_folder / "Test Movie.mp4", dest_folder / "Test Movie.mp4"),
                call(src_folder / "movie.nfo", dest_folder / "movie.nfo"),
            ]
            for c in expected_calls:
                self.assertIn(c, mock_copy2.call_args_list)
            mock_scan.assert_not_called()

    @patch("subprocess.run")
    def test_generate_movie_artwork_invokes_tools(self, mock_run):
        folder = Path(self.temp_dir) / "Test Movie"
        movie_file = folder / "Test Movie.mp4"
        frames_dir = os.path.join(self.app.temp_dir, "movie_frames")

        def glob_side_effect(self, pattern):
            p = str(self)
            if p == str(folder) and pattern == "*.mp4":
                return [movie_file]
            if p == str(folder) and pattern != "*.mp4":
                return []
            if p == frames_dir and pattern == "frame_*.jpg":
                return [Path(os.path.join(frames_dir, "frame_000.jpg"))]
            return []

        mock_run.return_value = MagicMock()

        with patch("pathlib.Path.glob", new=glob_side_effect), patch("os.makedirs"):
            self.app.generate_movie_artwork(str(folder), "job1")

        ffmpeg_calls = [c for c in mock_run.call_args_list if c.args[0][0] == "ffmpeg"]
        convert_calls = [c for c in mock_run.call_args_list if c.args[0][0] == "convert"]
        self.assertTrue(ffmpeg_calls)
        self.assertTrue(convert_calls)
        self.job.update.assert_any_call(
            status="generating_artwork", message="Generating movie artwork"
        )

    @patch("subprocess.run")
    def test_generate_movie_artwork_handles_no_movie(self, mock_run):
        folder = Path(self.temp_dir) / "Test Movie"

        def glob_side_effect(self, pattern):
            return []

        with patch("pathlib.Path.glob", new=glob_side_effect), patch("os.makedirs"):
            self.app.generate_movie_artwork(str(folder), "job1")

        mock_run.assert_not_called()
        self.job.update.assert_any_call(
            message="No movie file found for artwork generation"
        )


if __name__ == "__main__":
    unittest.main()
