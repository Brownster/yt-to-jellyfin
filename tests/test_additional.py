import os
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Ensure app.py can be imported
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from tubarr.core import YTToJellyfin
from tubarr.web import app, ytj
import subprocess

class TestConfigAndDependencies(unittest.TestCase):
    def setUp(self):
        # isolate environment variables
        self.env_patcher = patch.dict(os.environ, {}, clear=True)
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    def test_load_config_from_env(self):
        os.environ['OUTPUT_DIR'] = '/tmp/media'
        os.environ['VIDEO_QUALITY'] = '720'
        os.environ['USE_H265'] = 'false'
        os.environ['COOKIES_PATH'] = '/tmp/cookies.txt'
        os.environ['CONFIG_FILE'] = '/tmp/does_not_exist.yml'
        Path('/tmp/cookies.txt').write_text('cookies')

        yt = YTToJellyfin()
        self.assertEqual(yt.config['output_dir'], '/tmp/media')
        self.assertEqual(yt.config['quality'], '720')
        self.assertFalse(yt.config['use_h265'])
        self.assertEqual(yt.config['cookies'], '/tmp/cookies.txt')

    @patch('subprocess.run')
    @patch('os.access', return_value=True)
    @patch('os.path.exists', return_value=True)
    def test_check_dependencies(self, mock_exists, mock_access, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='/usr/bin/tool')
        yt = YTToJellyfin()
        yt.config['ytdlp_path'] = '/usr/bin/yt-dlp'
        self.assertTrue(yt.check_dependencies())

        mock_run.side_effect = [MagicMock(returncode=0, stdout=''), subprocess.CalledProcessError(1, ['which','ffmpeg'])]
        self.assertFalse(yt.check_dependencies())

class TestPlaylistHelpers(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.yt = YTToJellyfin()
        self.yt.config['output_dir'] = self.temp_dir

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_existing_max_index(self):
        folder = Path(self.temp_dir)
        (folder / 'Show S01E01.mp4').touch()
        (folder / 'Show S01E03.mp4').touch()
        idx = self.yt._get_existing_max_index(self.temp_dir, '01')
        self.assertEqual(idx, 3)

    def test_register_playlist(self):
        with patch.object(self.yt, '_save_playlists') as mock_save:
            self.yt._register_playlist('https://youtube.com/playlist?list=ABC', 'Show', '01')
            self.assertIn('ABC', self.yt.playlists)
            mock_save.assert_called_once()

class TestConversionWorkflow(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.yt = YTToJellyfin()
        self.yt.config['output_dir'] = self.temp_dir
        self.yt.config['use_h265'] = False
        job = MagicMock()
        self.yt.jobs['job'] = job

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_convert_video_files_disabled(self):
        self.yt.convert_video_files(self.temp_dir, '01', 'job')
        job = self.yt.jobs['job']
        job.update.assert_called()
        self.assertIn('H.265 conversion disabled', job.update.call_args.kwargs.get('message'))

class TestAPIExtensions(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()
        ytj.playlists = {}

    def test_playlist_info_missing(self):
        resp = self.client.get('/playlist_info')
        self.assertEqual(resp.status_code, 400)

    @patch.object(YTToJellyfin, 'get_playlist_videos', return_value={'entries': []})
    def test_playlist_info(self, mock_get):
        resp = self.client.get('/playlist_info?url=test')
        self.assertEqual(resp.status_code, 200)
        mock_get.assert_called_once_with('test')

    @patch.object(YTToJellyfin, 'check_playlist_updates', return_value=['job1'])
    def test_playlists_check(self, mock_check):
        resp = self.client.post('/playlists/check')
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertEqual(data['created_jobs'], ['job1'])

    def test_config_put(self):
        resp = self.client.put('/config', json={'quality': 480, 'use_h265': False})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ytj.config['quality'], 480)
        self.assertFalse(ytj.config['use_h265'])

if __name__ == '__main__':
    unittest.main()
