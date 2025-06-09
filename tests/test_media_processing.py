import os
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock, mock_open, call
from pathlib import Path

from tubarr.core import YTToJellyfin


class TestMediaProcessing(unittest.TestCase):
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
        self.job_id = "job1"
        self.job = MagicMock()
        self.app.jobs[self.job_id] = self.job

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_nfo_files(self):
        folder = os.path.join(self.temp_dir, "Test Show", "Season 01")
        show_folder = os.path.dirname(folder)
        season_nfo = (
            "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>\n"
            "<season>\n"
            "  <seasonnumber>01</seasonnumber>\n"
            "  <title>Season 01</title>\n"
            "  <plot>Season 01 of Test Show</plot>\n"
            "</season>\n"
        )
        tvshow_nfo = (
            "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>\n"
            "<tvshow>\n"
            "  <title>Test Show</title>\n"
            "  <studio>YouTube</studio>\n"
            "</tvshow>\n"
        )
        m1 = mock_open()
        m2 = mock_open()
        with patch(
            "builtins.open", side_effect=[m1.return_value, m2.return_value]
        ) as m_open:
            self.app.create_nfo_files(folder, "Test Show", "01", self.job_id)

        m_open.assert_has_calls(
            [
                call(f"{folder}/season.nfo", "w"),
                call(f"{show_folder}/tvshow.nfo", "w"),
            ]
        )
        m1.return_value.write.assert_called_once_with(season_nfo)
        m2.return_value.write.assert_called_once_with(tvshow_nfo)
        self.job.update.assert_any_call(
            status="creating_nfo", message="Creating NFO files"
        )
        self.job.update.assert_any_call(progress=100, message="Created NFO files")

    @patch("subprocess.Popen")
    @patch("subprocess.run")
    def test_generate_artwork_invokes_tools(self, mock_run, mock_popen):
        folder = os.path.join(self.temp_dir, "Test Show", "Season 01")
        episodes = [Path(f"{folder}/Test_Show_S01E01.mp4")]
        season_frames_dir = os.path.join(self.app.temp_dir, "season_frames")

        def glob_side_effect(self, pattern):
            p = str(self)
            if p == folder and pattern == "*S01E*.mp4":
                return episodes
            if p == season_frames_dir and pattern == "*.jpg":
                return [Path(os.path.join(season_frames_dir, "frame_000.jpg"))]
            return []

        p1 = MagicMock()
        p1.stdout = MagicMock()
        p2 = MagicMock()
        mock_popen.side_effect = [p1, p2]
        mock_run.return_value = MagicMock()

        with patch("pathlib.Path.glob", new=glob_side_effect), patch("os.makedirs"):
            self.app.generate_artwork(folder, "Test Show", "01", self.job_id)

        self.assertEqual(mock_popen.call_count, 2)
        self.assertEqual(mock_popen.call_args_list[0].args[0][0], "montage")
        self.assertEqual(mock_popen.call_args_list[1].args[0][0], "convert")
        ffmpeg_calls = [c for c in mock_run.call_args_list if c.args[0][0] == "ffmpeg"]
        self.assertTrue(ffmpeg_calls)
        expected_filter = "select=not(mod(n\\,1000)),scale=640:360"
        self.assertIn(expected_filter, ffmpeg_calls[0].args[0])
        self.job.update.assert_any_call(
            status="generating_artwork", message="Generating thumbnails and artwork"
        )
        self.job.update.assert_any_call(progress=100, message="Created season artwork")

    @patch("subprocess.Popen")
    @patch("subprocess.run")
    def test_generate_artwork_handles_no_episodes(self, mock_run, mock_popen):
        folder = os.path.join(self.temp_dir, "Test Show", "Season 01")
        season_frames_dir = os.path.join(self.app.temp_dir, "season_frames")

        def glob_side_effect(self, pattern):
            p = str(self)
            if p == folder and pattern == "*S01E*.mp4":
                return []
            if p == season_frames_dir and pattern == "*.jpg":
                return []
            return []

        with patch("pathlib.Path.glob", new=glob_side_effect), patch("os.makedirs"):
            self.app.generate_artwork(folder, "Test Show", "01", self.job_id)

        mock_run.assert_not_called()
        mock_popen.assert_not_called()
        self.job.update.assert_any_call(
            message="No episodes found for artwork generation"
        )


if __name__ == "__main__":
    unittest.main()
