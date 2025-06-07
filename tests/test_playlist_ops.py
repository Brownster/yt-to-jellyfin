import os
import sys
import unittest
import tempfile
import json
import subprocess
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import YTToJellyfin, DownloadJob

class TestPlaylistOperations(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'output_dir': self.temp_dir,
            'quality': '720',
            'use_h265': False,
            'crf': 28,
            'ytdlp_path': 'yt-dlp',
            'cookies': '',
            'completed_jobs_limit': 3,
            'web_enabled': False,
            'web_port': 8000,
            'web_host': '0.0.0.0',
            'jellyfin_enabled': False,
            'jellyfin_tv_path': '',
            'jellyfin_host': '',
            'jellyfin_port': '8096',
            'jellyfin_api_key': '',
            'clean_filenames': True,
        }
        with patch.object(YTToJellyfin, '_load_config', return_value=self.config), \
             patch.object(YTToJellyfin, '_load_playlists', return_value={}):
            self.app = YTToJellyfin()
        self.app.playlists_file = os.path.join(self.temp_dir, 'playlists.json')

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_register_and_list_playlists(self):
        url = 'https://youtube.com/playlist?list=TEST123'
        with patch.object(self.app, '_save_playlists') as mock_save:
            self.app._register_playlist(url, 'Test Show', '01')
            mock_save.assert_called_once()
        pid = 'TEST123'
        self.assertIn(pid, self.app.playlists)

        folder = self.app.create_folder_structure('Test Show', '01')
        Path(folder, 'Test Show S01E01.mp4').touch()
        Path(folder, 'Test Show S01E02.mp4').touch()
        archive = self.app.playlists[pid]['archive']
        os.makedirs(os.path.dirname(archive), exist_ok=True)
        with open(archive, 'w') as f:
            f.write('id1\n')
            f.write('id2\n')
        playlists = self.app.list_playlists()
        self.assertEqual(len(playlists), 1)
        info = playlists[0]
        self.assertEqual(info['last_episode'], 2)
        self.assertEqual(info['downloaded_videos'], 2)

    def test_get_existing_max_index(self):
        folder = self.app.create_folder_structure('Show2', '01')
        Path(folder, 'Show2 S01E01.mp4').touch()
        Path(folder, 'Show2 S01E03.mp4').touch()
        max_idx = self.app._get_existing_max_index(folder, '01')
        self.assertEqual(max_idx, 3)

    @patch('subprocess.run')
    def test_get_playlist_videos_success(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps({'entries': [{'id': 'a', 'title': 'A'}, {'id': 'b', 'title': 'B'}]}),
            returncode=0,
        )
        videos = self.app.get_playlist_videos('https://playlist')
        self.assertEqual(len(videos), 2)
        self.assertEqual(videos[0]['title'], 'A')
        mock_run.assert_called_once()

    @patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'yt-dlp'))
    def test_get_playlist_videos_failure(self, mock_run):
        videos = self.app.get_playlist_videos('https://playlist')
        self.assertEqual(videos, [])
        mock_run.assert_called_once()

    def test_process_success_and_failure(self):
        def fake_create_job(url, show, season, episode_start, start_thread=True):
            job = DownloadJob('job-1', url, show, season, episode_start)
            job.status = 'completed'
            self.app.jobs['job-1'] = job
            return 'job-1'

        with patch.object(self.app, 'create_job', side_effect=fake_create_job), \
             patch.object(self.app, 'cleanup') as mock_cleanup:
            result = self.app.process('u', 's', '01', 1)
            self.assertTrue(result)
            mock_cleanup.assert_called()

        def fake_create_job_fail(url, show, season, episode_start, start_thread=True):
            job = DownloadJob('job-2', url, show, season, episode_start)
            job.status = 'failed'
            self.app.jobs['job-2'] = job
            return 'job-2'

        with patch.object(self.app, 'create_job', side_effect=fake_create_job_fail), \
             patch.object(self.app, 'cleanup'):
            result = self.app.process('u', 's', '01', 1)
            self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
