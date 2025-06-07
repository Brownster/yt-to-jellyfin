import os
import sys
import unittest
import subprocess
import json
import tempfile
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add parent directory to path to import app.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tubarr.core import YTToJellyfin, DownloadJob

class TestYTToJellyfin(unittest.TestCase):
    
    def setUp(self):
        self.app = YTToJellyfin()
        self.temp_dir = tempfile.mkdtemp()
        self.app.config['output_dir'] = self.temp_dir
    
    def tearDown(self):
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
    
    def test_sanitize_name(self):
        # Test sanitization function
        self.assertEqual(self.app.sanitize_name('Test/Name:*?'), 'TestName')
        self.assertEqual(self.app.sanitize_name('  Spaces  '), 'Spaces')
    
    @patch('subprocess.run')
    def test_check_dependencies(self, mock_run):
        # Setup mock to return successfully
        mock_run.return_value = MagicMock(returncode=0)
        
        # Test dependency checking with success
        self.assertTrue(self.app.check_dependencies())
        
        # Test dependency checking with failure by using subprocess.CalledProcessError
        mock_run.side_effect = subprocess.CalledProcessError(1, 'which')
        self.assertFalse(self.app.check_dependencies())
    
    def test_folder_creation(self):
        # Test folder structure creation
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            folder = self.app.create_folder_structure("Test Show", "01")
            self.assertTrue(mock_mkdir.called)
            self.assertTrue("Test Show/Season 01" in folder)
    
    @patch.object(YTToJellyfin, '_load_playlists', return_value={})
    def test_config_loading(self, mock_load_playlists):
        """Environment variables should override defaults."""
        with tempfile.NamedTemporaryFile() as tmp_cookie:
            env = {
                'OUTPUT_DIR': '/env/media',
                'VIDEO_QUALITY': '480',
                'USE_H265': 'false',
                'CRF': '23',
                'YTDLP_PATH': '/usr/bin/ytdlp',
                'COOKIES_PATH': tmp_cookie.name,
                'WEB_ENABLED': 'false',
                'WEB_PORT': '9001',
                'WEB_HOST': 'localhost'
            }
            with patch.dict(os.environ, env, clear=True), \
                 patch('os.path.exists', side_effect=lambda p: p in {tmp_cookie.name, '/usr/bin/ytdlp'}), \
                 patch('os.access', return_value=True):
                app = YTToJellyfin()
        config = app.config

        self.assertEqual(config['output_dir'], '/env/media')
        self.assertEqual(config['quality'], '480')
        self.assertFalse(config['use_h265'])
        self.assertEqual(config['crf'], 23)
        self.assertEqual(config['ytdlp_path'], '/usr/bin/ytdlp')
        self.assertEqual(config['cookies'], tmp_cookie.name)
        self.assertFalse(config['web_enabled'])
        self.assertEqual(config['web_port'], 9001)
        self.assertEqual(config['web_host'], 'localhost')
    
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=unittest.mock.mock_open, read_data="""
media:
  output_dir: /yaml/media
  quality: 2160
  use_h265: false
  crf: 24
web:
  port: 8080
  host: localhost
""")
    @patch('yaml.safe_load')
    def test_config_loading_from_yaml(self, mock_yaml_load, mock_open, mock_exists):
        # Test loading configuration from YAML file
        mock_exists.return_value = True
        mock_yaml_load.return_value = {
            'media': {
                'output_dir': '/yaml/media',
                'quality': 2160,
                'use_h265': False,
                'crf': 24
            },
            'web': {
                'port': 8080,
                'host': 'localhost'
            }
        }
        
        app = YTToJellyfin()
        config = app.config
        
        self.assertEqual(config['output_dir'], '/yaml/media')
        self.assertEqual(config['quality'], 2160)
        self.assertFalse(config['use_h265'])
        self.assertEqual(config['crf'], 24)
        self.assertEqual(config['web_port'], 8080)
        self.assertEqual(config['web_host'], 'localhost')
    
    def test_list_media(self):
        # Create test media structure
        media_dir = Path(self.temp_dir)
        show_dir = media_dir / "Test Show"
        season_dir = show_dir / "Season 01"
        os.makedirs(season_dir, exist_ok=True)
        
        # Create a few dummy files
        (season_dir / "Test Show S01E01.mp4").touch()
        (season_dir / "Test Show S01E02.mp4").touch()
        
        # Test the list_media function
        media_list = self.app.list_media()
        
        # Verify the results
        self.assertEqual(len(media_list), 1)
        self.assertEqual(media_list[0]['name'], 'Test Show')
        self.assertEqual(len(media_list[0]['seasons']), 1)
        self.assertEqual(media_list[0]['seasons'][0]['name'], 'Season 01')
        self.assertEqual(len(media_list[0]['seasons'][0]['episodes']), 2)
    
    def test_download_job_creation_and_updates(self):
        # Create a download job
        job = DownloadJob("test-id", "url", "Test Show", "01", "01")
        
        # Verify initial state
        self.assertEqual(job.job_id, "test-id")
        self.assertEqual(job.status, "queued")
        self.assertEqual(job.progress, 0)
        self.assertEqual(len(job.messages), 0)
        
        # Test updating the job
        job.update(status="downloading", progress=25, message="Starting download")
        self.assertEqual(job.status, "downloading")
        self.assertEqual(job.progress, 25)
        self.assertEqual(len(job.messages), 1)
        self.assertEqual(job.messages[0]["text"], "Starting download")
        
        # Test to_dict method
        job_dict = job.to_dict()
        self.assertEqual(job_dict["job_id"], "test-id")
        self.assertEqual(job_dict["status"], "downloading")
        self.assertEqual(job_dict["progress"], 25)
        self.assertEqual(len(job_dict["messages"]), 1)

if __name__ == '__main__':
    unittest.main()