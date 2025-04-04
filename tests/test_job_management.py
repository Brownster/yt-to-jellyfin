import os
import sys
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock, call

# Add parent directory to path to import app.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import YTToJellyfin, DownloadJob

class TestJobManagement(unittest.TestCase):
    
    def setUp(self):
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        # Create app instance with test config
        self.app = YTToJellyfin()
        self.app.config = {
            'output_dir': self.temp_dir,
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
    
    def test_download_job_creation(self):
        """Test creating a DownloadJob"""
        job = DownloadJob(
            "test-id", 
            "https://youtube.com/playlist?list=TEST",
            "Test Show",
            "01",
            "01"
        )
        
        self.assertEqual(job.job_id, "test-id")
        self.assertEqual(job.playlist_url, "https://youtube.com/playlist?list=TEST")
        self.assertEqual(job.show_name, "Test Show")
        self.assertEqual(job.season_num, "01")
        self.assertEqual(job.episode_start, "01")
        self.assertEqual(job.status, "queued")
        self.assertEqual(job.progress, 0)
        self.assertEqual(job.messages, [])
    
    def test_job_update(self):
        """Test updating job status and progress"""
        job = DownloadJob("test-id", "", "", "", "")
        
        # Update status
        job.update(status="downloading")
        self.assertEqual(job.status, "downloading")
        
        # Update progress
        job.update(progress=50)
        self.assertEqual(job.progress, 50)
        
        # Update with message
        job.update(message="Starting download")
        self.assertEqual(len(job.messages), 1)
        self.assertEqual(job.messages[0]["text"], "Starting download")
        
        # Multiple updates
        job.update(status="converting", progress=75, message="Converting video")
        self.assertEqual(job.status, "converting")
        self.assertEqual(job.progress, 75)
        self.assertEqual(len(job.messages), 2)
        self.assertEqual(job.messages[1]["text"], "Converting video")
    
    def test_job_to_dict(self):
        """Test conversion of job to dictionary"""
        job = DownloadJob("test-id", "url", "show", "01", "01")
        job.update(status="downloading", progress=30, message="Starting download")
        
        job_dict = job.to_dict()
        
        self.assertEqual(job_dict["job_id"], "test-id")
        self.assertEqual(job_dict["playlist_url"], "url")
        self.assertEqual(job_dict["show_name"], "show")
        self.assertEqual(job_dict["season_num"], "01")
        self.assertEqual(job_dict["episode_start"], "01")
        self.assertEqual(job_dict["status"], "downloading")
        self.assertEqual(job_dict["progress"], 30)
        self.assertEqual(len(job_dict["messages"]), 1)
    
    @patch('threading.Thread')
    def test_create_job(self, mock_thread):
        """Test job creation in the app"""
        job_id = self.app.create_job(
            "https://youtube.com/playlist?list=TEST",
            "Test Show",
            "01",
            "01"
        )
        
        # Verify job was created and stored
        self.assertIn(job_id, self.app.jobs)
        job = self.app.jobs[job_id]
        self.assertEqual(job.playlist_url, "https://youtube.com/playlist?list=TEST")
        self.assertEqual(job.show_name, "Test Show")
        
        # Verify thread was started to process the job
        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()
    
    def test_job_limit_enforcement(self):
        """Test that completed jobs limit is enforced"""
        # Create more jobs than the limit
        for i in range(5):
            # Create completed jobs
            job_id = f"job-{i}"
            job = DownloadJob(job_id, "url", "show", "01", "01")
            job.update(status="completed")
            self.app.jobs[job_id] = job
        
        # Add a new job, which should trigger cleanup
        with patch('uuid.uuid4', return_value="new-job"):
            self.app.create_job("url", "show", "01", "01")
        
        # Verify we only have the limit + 1 (the new job) jobs
        self.assertEqual(len(self.app.jobs), self.app.config['completed_jobs_limit'] + 1)
        # Verify the newest completed job and the new job are kept
        self.assertIn("job-4", self.app.jobs)
        self.assertIn("new-job", self.app.jobs)
        # Verify oldest completed jobs were removed
        self.assertNotIn("job-0", self.app.jobs)
        self.assertNotIn("job-1", self.app.jobs)
    
    @patch('subprocess.Popen')
    @patch('subprocess.run')
    def test_download_playlist(self, mock_run, mock_popen):
        """Test playlist download function"""
        # Mock the process
        process_mock = MagicMock()
        process_mock.stdout = ["[download] 10.0% of 100.00MB", "Done!"]
        process_mock.returncode = 0
        mock_popen.return_value = process_mock
        
        # Create a job
        job_id = "test-job"
        job = DownloadJob(job_id, "url", "show", "01", "01")
        self.app.jobs[job_id] = job
        
        # Execute download
        result = self.app.download_playlist("url", self.temp_dir, "01", job_id)
        
        # Verify success
        self.assertTrue(result)
        self.assertEqual(job.status, "downloaded")
        self.assertEqual(job.progress, 100)
        
        # Verify command was correct
        mock_popen.assert_called_once()
        cmd_args = mock_popen.call_args[0][0]
        self.assertEqual(cmd_args[0], 'yt-dlp')
        self.assertIn('--merge-output-format', cmd_args)
        self.assertIn('mp4', cmd_args)
        self.assertIn('url', cmd_args)
    
    @patch('subprocess.Popen')
    def test_download_failure(self, mock_popen):
        """Test handling of download failures"""
        # Mock the process with failure
        process_mock = MagicMock()
        process_mock.stdout = ["ERROR: Unable to download"]
        process_mock.returncode = 1
        mock_popen.return_value = process_mock
        
        # Create a job
        job_id = "test-job"
        job = DownloadJob(job_id, "url", "show", "01", "01")
        self.app.jobs[job_id] = job
        
        # Execute download
        result = self.app.download_playlist("url", self.temp_dir, "01", job_id)
        
        # Verify failure
        self.assertFalse(result)
        self.assertEqual(job.status, "failed")
    
    @patch('os.path.exists')
    @patch('json.load')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    @patch('os.remove')
    @patch('os.rename')
    def test_process_metadata(self, mock_rename, mock_remove, mock_open, mock_json_load, mock_exists):
        """Test metadata processing"""
        # Setup mocks
        mock_exists.return_value = True
        mock_json_load.side_effect = [
            # First JSON file (to get first index)
            {'playlist_index': 1},
            # Individual JSON files
            {'title': 'Video 1', 'description': 'Desc 1', 'upload_date': '20230101', 'playlist_index': 1},
            {'title': 'Video 2', 'description': 'Desc 2', 'upload_date': '20230102', 'playlist_index': 2}
        ]
        
        # Mock Path.glob to return two JSON files
        with patch('pathlib.Path.glob') as mock_glob:
            mock_glob.return_value = [
                MagicMock(__str__=lambda self: f"{self.temp_dir}/Test Show S01E01.info.json"),
                MagicMock(__str__=lambda self: f"{self.temp_dir}/Test Show S01E02.info.json")
            ]
            
            # Create a job
            job_id = "test-job"
            job = DownloadJob(job_id, "url", "Test Show", "01", "01")
            self.app.jobs[job_id] = job
            
            # Process metadata
            self.app.process_metadata(self.temp_dir, "Test Show", "01", 1, job_id)
            
            # Verify job was updated
            self.assertEqual(job.status, "processing_metadata")
            self.assertEqual(job.progress, 100)  # Should be 100% after processing two files
            
            # Verify files were processed
            self.assertEqual(mock_open.call_count, 5)  # 3 reads (first index + 2 files) + 2 NFO writes
            self.assertEqual(mock_remove.call_count, 2)  # Remove two JSON files
            self.assertEqual(mock_rename.call_count, 2)  # Rename two video files
    
    def test_get_job(self):
        """Test getting a specific job"""
        # Add test jobs
        job1 = DownloadJob("job1", "url1", "show1", "01", "01")
        job2 = DownloadJob("job2", "url2", "show2", "02", "01")
        self.app.jobs = {"job1": job1, "job2": job2}
        
        # Get existing job
        job = self.app.get_job("job1")
        self.assertEqual(job["job_id"], "job1")
        self.assertEqual(job["show_name"], "show1")
        
        # Get non-existent job
        job = self.app.get_job("job3")
        self.assertIsNone(job)
    
    def test_get_jobs(self):
        """Test getting all jobs"""
        # Add test jobs
        job1 = DownloadJob("job1", "url1", "show1", "01", "01")
        job2 = DownloadJob("job2", "url2", "show2", "02", "01")
        self.app.jobs = {"job1": job1, "job2": job2}
        
        # Get all jobs
        jobs = self.app.get_jobs()
        self.assertEqual(len(jobs), 2)
        self.assertTrue(any(j["job_id"] == "job1" for j in jobs))
        self.assertTrue(any(j["job_id"] == "job2" for j in jobs))

if __name__ == '__main__':
    unittest.main()