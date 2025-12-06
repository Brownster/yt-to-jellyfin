import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tubarr.core import YTToJellyfin
from tubarr.media import download_playlist, process_metadata


class DummyProcess:
    def __init__(self, lines, returncode=0):
        self.stdout = iter(lines)
        self.returncode = returncode

    def wait(self):
        return self.returncode


class TestDownloadCommandGeneration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.cookies_file = Path(self.temp_dir.name) / "cookies.txt"
        self.cookies_file.write_text("# Netscape cookies")
        self.output_dir = Path(self.temp_dir.name) / "output"
        self.output_dir.mkdir()
        self.config = {
            "output_dir": str(self.output_dir),
            "quality": "720",
            "use_h265": False,
            "crf": 28,
            "ytdlp_path": "/usr/bin/yt-dlp",
            "cookies": str(self.cookies_file),
            "completed_jobs_limit": 3,
            "max_concurrent_jobs": 1,
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
        with patch.object(YTToJellyfin, "_load_config", return_value=self.config), patch.object(
            YTToJellyfin, "_load_playlists", return_value={}
        ):
            self.app = YTToJellyfin()
        self.job_id = "job-123"
        self.job = MagicMock()
        self.job.remaining_files = []
        self.app.jobs[self.job_id] = self.job

    def test_download_playlist_builds_expected_command(self):
        folder = Path(self.output_dir) / "Test Show" / "Season 01"
        folder.mkdir(parents=True)
        playlist_url = "https://youtube.com/playlist?list=TEST"
        archive_path = Path(self.temp_dir.name) / "archives" / "test.txt"

        self.app._get_archive_file = MagicMock(return_value=str(archive_path))
        self.app._get_existing_max_index = MagicMock(return_value=3)

        progress_lines = [
            "[download] Downloading playlist: Example",
            "[download] Destination: /tmp/Test_Show_S01E03.mp4",
            "[download]   50.0% of 2.00MiB in 00:01",
            "[download] Finished downloading playlist: 2 of 2 items",
        ]

        with patch("subprocess.Popen", return_value=DummyProcess(progress_lines)) as mock_popen:
            result = download_playlist(
                self.app,
                playlist_url,
                str(folder),
                "01",
                self.job_id,
                playlist_start=None,
            )

        self.assertTrue(result)
        mock_popen.assert_called_once()
        invoked_cmd = mock_popen.call_args.args[0]
        expected_template = f"{folder}/%(title)s S01E%(playlist_index)02d.%(ext)s"

        self.assertIn("--cookies=" + str(self.cookies_file), invoked_cmd)
        self.assertIn("--download-archive", invoked_cmd)
        self.assertIn(str(archive_path), invoked_cmd)
        self.assertIn("--playlist-start", invoked_cmd)
        playlist_start_index = invoked_cmd.index("--playlist-start") + 1
        self.assertEqual(invoked_cmd[playlist_start_index], "4")
        self.assertIn(expected_template, invoked_cmd)
        self.assertEqual(invoked_cmd[0], self.config["ytdlp_path"])
        self.assertEqual(invoked_cmd[1], f"--cookies={self.cookies_file}")
        self.job.update.assert_any_call(status="downloaded", stage="downloading", progress=100, stage_progress=100, detailed_status="Download completed successfully", message="Download completed successfully")


class TestMetadataTagging(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.output_dir = Path(self.temp_dir.name) / "media"
        self.output_dir.mkdir()
        self.config = {
            "output_dir": str(self.output_dir),
            "quality": "720",
            "use_h265": False,
            "crf": 28,
            "ytdlp_path": "/usr/bin/yt-dlp",
            "cookies": "",
            "completed_jobs_limit": 3,
            "max_concurrent_jobs": 1,
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
        with patch.object(YTToJellyfin, "_load_config", return_value=self.config), patch.object(
            YTToJellyfin, "_load_playlists", return_value={}
        ):
            self.app = YTToJellyfin()
        self.job_id = "meta-job"
        self.job = MagicMock()
        self.app.jobs[self.job_id] = self.job
        self.app.update_last_episode = MagicMock()

    def test_process_metadata_renames_and_creates_nfo(self):
        folder = Path(self.output_dir) / "Cool Show" / "Season 01"
        folder.mkdir(parents=True)
        base_name = folder / "Cool_Show_Title S01E01"
        video_path = base_name.with_suffix(".mp4")
        video_path.write_bytes(b"fake video")
        json_path = base_name.with_suffix(".info.json")
        metadata = {
            "title": "Cool Show Title",
            "description": "Pilot episode description\nFull summary",
            "upload_date": "20240301",
            "playlist_index": 1,
        }
        json_path.write_text(json.dumps(metadata))

        process_metadata(
            self.app,
            str(folder),
            "Cool Show",
            "01",
            episode_start=5,
            job_id=self.job_id,
        )

        renamed_video = folder / "Cool Show - S01E05 - Cool Show Title.mp4"
        nfo_file = folder / "Cool Show - S01E05 - Cool Show Title.nfo"

        self.assertTrue(renamed_video.exists())
        self.assertTrue(nfo_file.exists())
        nfo_content = nfo_file.read_text()
        self.assertIn("<title>Cool Show Title</title>", nfo_content)
        self.assertIn("<episode>05</episode>", nfo_content)
        self.assertIn("<plot>Pilot episode description</plot>", nfo_content)
        self.assertIn("<aired>2024-03-01</aired>", nfo_content)
        self.assertIn("<showtitle>Cool Show</showtitle>", nfo_content)
        self.assertFalse(json_path.exists())
        self.app.update_last_episode.assert_called_once_with("Cool Show", "01", 5)
        self.job.update.assert_any_call(message="Created NFO file for Cool Show Title")


if __name__ == "__main__":
    unittest.main()
