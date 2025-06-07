import os
import sys
import unittest
import json
import tempfile
from unittest.mock import patch, MagicMock

# Add parent directory to path to import app.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, ytj

class TestAPIEndpoints(unittest.TestCase):
    
    def setUp(self):
        # Configure app for testing
        app.config['TESTING'] = True
        self.client = app.test_client()
        
        # Create sample jobs for testing
        ytj.jobs = {}
    
    def tearDown(self):
        # Clean up after tests
        ytj.jobs = {}
    
    @patch('app.YTToJellyfin.create_job')
    def test_create_job(self, mock_create_job):
        """Test job creation endpoint"""
        # Mock the create_job method
        mock_create_job.return_value = "test-job-id"
        
        # Test valid job creation
        response = self.client.post('/jobs', data={
            'playlist_url': 'https://youtube.com/playlist?list=TEST',
            'show_name': 'Test Show',
            'season_num': '01',
            'episode_start': '01'
        })
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['job_id'], "test-job-id")
        
        # Verify create_job was called with correct parameters
        mock_create_job.assert_called_once_with(
            'https://youtube.com/playlist?list=TEST',
            'Test Show',
            '01',
            '01'
        )
        
        # Test missing parameters
        response = self.client.post('/jobs', data={
            'playlist_url': 'https://youtube.com/playlist?list=TEST'
        })
        
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
    
    def test_get_jobs(self):
        """Test getting list of jobs"""
        # Add test jobs
        ytj.jobs = {
            'job1': MagicMock(to_dict=lambda **kwargs: {'job_id': 'job1', 'status': 'completed'}),
            'job2': MagicMock(to_dict=lambda **kwargs: {'job_id': 'job2', 'status': 'in_progress'})
        }
        
        response = self.client.get('/jobs')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(len(data), 2)
        self.assertTrue(any(job['job_id'] == 'job1' for job in data))
        self.assertTrue(any(job['job_id'] == 'job2' for job in data))
    
    def test_get_job_detail(self):
        """Test getting details of a specific job"""
        # Add test job
        ytj.jobs = {
            'job1': MagicMock(to_dict=lambda **kwargs: {
                'job_id': 'job1',
                'status': 'completed',
                'show_name': 'Test Show'
            })
        }
        
        # Test valid job ID
        response = self.client.get('/jobs/job1')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['job_id'], 'job1')
        self.assertEqual(data['show_name'], 'Test Show')
        
        # Test invalid job ID
        response = self.client.get('/jobs/nonexistent')
        self.assertEqual(response.status_code, 404)
    
    @patch('app.YTToJellyfin.list_media')
    def test_get_media(self, mock_list_media):
        """Test media listing endpoint"""
        # Mock the list_media method
        mock_list_media.return_value = [
            {
                "name": "Test Show",
                "seasons": [
                    {
                        "name": "Season 01",
                        "episodes": [
                            {"name": "Test Show S01E01", "size": 100000000}
                        ]
                    }
                ]
            }
        ]
        
        response = self.client.get('/media')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], 'Test Show')
        self.assertEqual(len(data[0]['seasons']), 1)
        self.assertEqual(len(data[0]['seasons'][0]['episodes']), 1)
    
    def test_get_config(self):
        """Test configuration endpoint"""
        # Set some config values
        ytj.config = {
            'output_dir': '/test/media',
            'quality': '1080',
            'use_h265': True,
            'cookies': '/secret/path'  # This should be excluded from response
        }
        
        response = self.client.get('/config')
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.data)
        self.assertEqual(data['output_dir'], '/test/media')
        self.assertEqual(data['quality'], '1080')
        self.assertTrue(data['use_h265'])
        # Verify sensitive data is excluded
        self.assertNotIn('cookies', data)

if __name__ == '__main__':
    unittest.main()