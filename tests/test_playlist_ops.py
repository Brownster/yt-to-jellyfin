import os
import sys
import unittest
import tempfile
import json
import subprocess
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tubarr.core import YTToJellyfin, DownloadJob


class TestPlaylistOperations(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
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
            "jellyfin_enabled": False,
            "jellyfin_tv_path": "",
            "jellyfin_host": "",
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
        self.app.playlists_file = os.path.join(self.temp_dir, "playlists.json")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_register_and_list_playlists(self):
        url = "https://youtube.com/playlist?list=TEST123"
        with patch.object(self.app, "_save_playlists") as mock_save:
            self.app._register_playlist(url, "Test Show", "01", None)
            mock_save.assert_called_once()
        pid = "TEST123"
        self.assertIn(pid, self.app.playlists)

        folder = self.app.create_folder_structure("Test Show", "01")
        Path(folder, "Test Show S01E01.mp4").touch()
        Path(folder, "Test Show S01E02.mp4").touch()
        archive = self.app.playlists[pid]["archive"]
        os.makedirs(os.path.dirname(archive), exist_ok=True)
        with open(archive, "w") as f:
            f.write("id1\n")
            f.write("id2\n")
        self.app.update_last_episode("Test Show", "01", 2)
        playlists = self.app.list_playlists()
        self.assertEqual(len(playlists), 1)
        info = playlists[0]
        self.assertEqual(info["last_episode"], 2)
        self.assertEqual(info["downloaded_videos"], 2)

    def test_get_existing_max_index(self):
        folder = self.app.create_folder_structure("Show2", "01")
        Path(folder, "Show2 S01E01.mp4").touch()
        Path(folder, "Show2 S01E03.mp4").touch()
        max_idx = self.app._get_existing_max_index(folder, "01")
        self.assertEqual(max_idx, 3)

    def test_disable_and_remove_playlist(self):
        url = "https://youtube.com/playlist?list=XYZ"
        self.app._register_playlist(url, "Show", "01", None)
        pid = "XYZ"
        self.assertIn(pid, self.app.playlists)
        self.app.set_playlist_enabled(pid, False)
        self.assertTrue(self.app.playlists[pid]["disabled"])
        self.app.set_playlist_enabled(pid, True)
        self.assertFalse(self.app.playlists[pid]["disabled"])
        self.app.remove_playlist(pid)
        self.assertNotIn(pid, self.app.playlists)

    @patch("subprocess.run")
    def test_get_playlist_videos_success(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {"entries": [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}]}
            ),
            returncode=0,
        )
        videos = self.app.get_playlist_videos("https://playlist")
        self.assertEqual(len(videos), 2)
        self.assertEqual(videos[0]["title"], "A")
        mock_run.assert_called_once()

    @patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "yt-dlp"))
    def test_get_playlist_videos_failure(self, mock_run):
        videos = self.app.get_playlist_videos("https://playlist")
        self.assertEqual(videos, [])
        mock_run.assert_called_once()

    def test_process_success_and_failure(self):
        def fake_create_job(
            url, show, season, episode_start, playlist_start=None, start_thread=True
        ):
            job = DownloadJob("job-1", url, show, season, episode_start)
            job.status = "completed"
            self.app.jobs["job-1"] = job
            return "job-1"

        with patch.object(
            self.app, "create_job", side_effect=fake_create_job
        ), patch.object(self.app, "cleanup") as mock_cleanup:
            result = self.app.process("u", "s", "01", 1)
            self.assertTrue(result)
            mock_cleanup.assert_called()

        def fake_create_job_fail(
            url, show, season, episode_start, playlist_start=None, start_thread=True
        ):
            job = DownloadJob("job-2", url, show, season, episode_start)
            job.status = "failed"
            self.app.jobs["job-2"] = job
            return "job-2"

        with patch.object(
            self.app, "create_job", side_effect=fake_create_job_fail
        ), patch.object(self.app, "cleanup"):
            result = self.app.process("u", "s", "01", 1)
            self.assertFalse(result)

    def test_start_update_checker_thread(self):
        """start_update_checker should create and start a daemon thread"""
        temp_dir = tempfile.mkdtemp()
        config = self.config.copy()
        config.update(
            {
                "output_dir": temp_dir,
                "update_checker_enabled": True,
                "update_checker_interval": 2,
            }
        )
        playlists = {
            "PID": {
                "url": "https://yt/playlist",
                "show_name": "Show",
                "season_num": "01",
            }
        }
        threads = []

        def fake_thread(target=None, daemon=None):
            thread = MagicMock()
            thread.daemon = daemon

            def start():
                try:
                    target()
                except StopIteration:
                    pass

            thread.start.side_effect = start
            threads.append(thread)
            return thread

        def fake_sleep(duration):
            raise StopIteration

        with patch.object(
            YTToJellyfin, "_load_config", return_value=config
        ), patch.object(
            YTToJellyfin, "_load_playlists", return_value=playlists
        ), patch.object(
            YTToJellyfin, "check_playlist_updates"
        ) as mock_check, patch(
            "threading.Thread", side_effect=fake_thread
        ) as mock_thread, patch(
            "time.sleep", side_effect=fake_sleep
        ) as mock_sleep:
            ytj = YTToJellyfin()

        self.assertEqual(len(threads), 1)
        thread = threads[0]
        self.assertIs(ytj.update_thread, thread)
        self.assertTrue(thread.daemon)
        thread.start.assert_called_once()
        mock_check.assert_called_once()
        mock_sleep.assert_called_once_with(
            max(1, config["update_checker_interval"]) * 60
        )


if __name__ == "__main__":
    unittest.main()
