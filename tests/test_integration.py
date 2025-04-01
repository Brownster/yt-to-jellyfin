import os
import sys
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock, call

# Add parent directory to path to import app.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import YTToJellyfin, DownloadJob

class TestIntegration(unittest.TestCase):
    """
    Integration tests for the complete workflow.
    These tests simulate a full download and processing without actually downloading from YouTube.
    """
    
    def setUp(self):
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.temp_dir, 'media')
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Create app instance with test config
        self.app = YTToJellyfin()
        self.app.config = {
            'output_dir': self.output_dir,
            'quality': '720',
            'use_h265': True,
            'crf': 28,
            'ytdlp_path': 'yt-dlp',
            'cookies': '',
            'completed_jobs_limit': 3
        }
        # Clear jobs
        self.app.jobs = {}
    
    def tearDown(self):
        # Clean up temp directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('app.YTToJellyfin.download_playlist')
    @patch('app.YTToJellyfin.process_metadata')
    @patch('app.YTToJellyfin.convert_video_files')
    @patch('app.YTToJellyfin.generate_artwork')
    @patch('app.YTToJellyfin.create_nfo_files')
    def test_full_workflow(self, mock_create_nfo, mock_generate_artwork, 
                           mock_convert, mock_process_metadata, mock_download):
        """Test the full workflow from job creation to completion"""
        # Setup mocks
        mock_download.return_value = True
        
        # Create a folder structure to simulate a successful download
        show_dir = os.path.join(self.output_dir, 'Test Show')
        season_dir = os.path.join(show_dir, 'Season 01')
        os.makedirs(season_dir, exist_ok=True)
        
        # Create a sample video file
        with open(os.path.join(season_dir, 'Test Show S01E01.mp4'), 'w') as f:
            f.write('dummy video content')
        
        # Create a job
        job_id = self.app.create_job(
            "https://youtube.com/playlist?list=TEST",
            "Test Show",
            "01",
            "01"
        )
        
        # Process the job
        self.app.process_job(job_id)
        
        # Verify all steps were called in the correct order
        job = self.app.jobs[job_id]
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.progress, 100)
        
        # Check that all functions were called with correct parameters
        mock_download.assert_called_once_with(
            "https://youtube.com/playlist?list=TEST",
            os.path.join(self.output_dir, 'Test_Show', 'Season 01'),
            "01",
            job_id
        )
        
        mock_process_metadata.assert_called_once()
        mock_convert.assert_called_once()
        mock_generate_artwork.assert_called_once()
        mock_create_nfo_files.assert_called_once()
    
    @patch('app.YTToJellyfin.download_playlist')
    def test_workflow_with_download_failure(self, mock_download):
        """Test the workflow when download fails"""
        # Setup mock to simulate download failure
        mock_download.return_value = False
        
        # Create a job
        job_id = self.app.create_job(
            "https://youtube.com/playlist?list=TEST",
            "Test Show",
            "01",
            "01"
        )
        
        # Process the job
        self.app.process_job(job_id)
        
        # Verify job status is failed
        job = self.app.jobs[job_id]
        self.assertEqual(job.status, "failed")
        self.assertIn("Download failed", job.messages[-1]["text"])
    
    @patch('app.YTToJellyfin.check_dependencies')
    def test_workflow_with_missing_dependencies(self, mock_check_deps):
        """Test the workflow when dependencies are missing"""
        # Setup mock to simulate missing dependencies
        mock_check_deps.return_value = False
        
        # Create a job
        job_id = self.app.create_job(
            "https://youtube.com/playlist?list=TEST",
            "Test Show",
            "01",
            "01"
        )
        
        # Process the job
        self.app.process_job(job_id)
        
        # Verify job status is failed
        job = self.app.jobs[job_id]
        self.assertEqual(job.status, "failed")
        self.assertIn("Missing dependencies", job.messages[-1]["text"])
    
    def test_invalid_episode_start(self):
        """Test the workflow when episode_start is invalid"""
        # Create a job with invalid episode_start
        job_id = self.app.create_job(
            "https://youtube.com/playlist?list=TEST",
            "Test Show",
            "01",
            "invalid"  # Non-numeric value
        )
        
        # Process the job
        self.app.process_job(job_id)
        
        # Verify job status is failed
        job = self.app.jobs[job_id]
        self.assertEqual(job.status, "failed")
        self.assertIn("Invalid episode start", job.messages[-1]["text"])
    
    @patch('threading.Thread')
    def test_concurrent_jobs(self, mock_thread):
        """Test that multiple jobs can be created and run concurrently"""
        # Create multiple jobs
        job_ids = []
        for i in range(3):
            job_id = self.app.create_job(
                f"https://youtube.com/playlist?list=TEST{i}",
                f"Test Show {i}",
                "01",
                "01"
            )
            job_ids.append(job_id)
        
        # Verify all jobs were created
        self.assertEqual(len(self.app.jobs), 3)
        
        # Verify that threads were started for each job
        self.assertEqual(mock_thread.call_count, 3)
        for i, job_id in enumerate(job_ids):
            thread_call = mock_thread.call_args_list[i]
            self.assertEqual(thread_call[1]["target"], self.app.process_job)
            self.assertEqual(thread_call[1]["args"], (job_id,))
            mock_thread.return_value.start.assert_called()

if __name__ == '__main__':
    unittest.main()