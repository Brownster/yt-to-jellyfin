import os
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, call

from tubarr.core import YTToJellyfin, DownloadJob
from tubarr import jellyfin as jellyfin_mod


class TestJellyfinIntegration(unittest.TestCase):
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
            "web_enabled": False,
            "web_port": 8000,
            "web_host": "0.0.0.0",
            "jellyfin_enabled": True,
            "jellyfin_tv_path": self.jellyfin_dir,
            "jellyfin_host": "localhost",
            "jellyfin_port": "8096",
            "jellyfin_api_key": "",
            "clean_filenames": True,
            "update_checker_enabled": False,
            "update_checker_interval": 60,
        }
        with patch.object(
            YTToJellyfin, "_load_config", return_value=self.config
        ), patch.object(YTToJellyfin, "_load_playlists", return_value={}):
            self.app = YTToJellyfin()
        self.job = DownloadJob("job1", "url", "Test Show", "01", "01")
        self.app.jobs["job1"] = self.job

        self.source_folder = Path(self.temp_dir) / "Test Show" / "Season 01"
        os.makedirs(self.source_folder, exist_ok=True)
        (self.source_folder / "Test Show S01E01.mp4").touch()
        (self.source_folder / "Test Show S01E01.nfo").touch()
        (self.source_folder / "Test Show S01E01.jpg").touch()
        show_root = Path(self.temp_dir) / "Test Show"
        show_root.mkdir(exist_ok=True)
        (show_root / "tvshow.nfo").touch()
        (show_root / "poster.jpg").touch()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.jellyfin_dir, ignore_errors=True)

    def test_copy_to_jellyfin_creates_and_copies(self):
        dest_show = Path(self.jellyfin_dir) / "Test Show"
        dest_season = dest_show / "Season 01"
        original_exists = os.path.exists

        def exists_side(p):
            if str(p).startswith(str(self.jellyfin_dir)):
                return False
            return original_exists(p)

        with patch("os.path.exists", side_effect=exists_side), patch(
            "os.makedirs"
        ) as mock_makedirs, patch("shutil.copy2") as mock_copy2, patch.object(
            self.app, "trigger_jellyfin_scan"
        ) as mock_scan:
            self.app.copy_to_jellyfin("Test Show", "01", "job1")

            mock_makedirs.assert_has_calls(
                [call(dest_show, exist_ok=True), call(dest_season, exist_ok=True)]
            )
            expected_calls = [
                call(
                    self.source_folder / "Test Show S01E01.mp4",
                    dest_season / "Test Show S01E01.mp4",
                ),
                call(
                    self.source_folder / "Test Show S01E01.nfo",
                    dest_season / "Test Show S01E01.nfo",
                ),
                call(
                    self.source_folder / "Test Show S01E01.jpg",
                    dest_season / "Test Show S01E01.jpg",
                ),
                call(
                    Path(self.temp_dir) / "Test Show" / "tvshow.nfo",
                    dest_show / "tvshow.nfo",
                ),
                call(
                    Path(self.temp_dir) / "Test Show" / "poster.jpg",
                    dest_show / "poster.jpg",
                ),
            ]
            mock_copy2.assert_has_calls(expected_calls, any_order=True)
            self.assertEqual(self.job.status, "copying_to_jellyfin")
            self.assertEqual(self.job.progress, 98)
            self.assertTrue(
                any(
                    "Successfully copied all files" in m["text"]
                    for m in self.job.messages
                )
            )
            mock_scan.assert_not_called()

    def test_trigger_jellyfin_scan(self):
        self.app.config["jellyfin_api_key"] = "token"
        url = "http://localhost:8096/Library/Refresh?api_key=token"
        with patch(
            "requests.post", return_value=MagicMock(status_code=204)
        ) as mock_post:
            jellyfin_mod.trigger_jellyfin_scan(self.app, "job1")
            mock_post.assert_called_once_with(url, timeout=10)
            self.assertTrue(
                any(
                    "Successfully triggered Jellyfin library scan" in m["text"]
                    for m in self.job.messages
                )
            )


if __name__ == "__main__":
    unittest.main()
