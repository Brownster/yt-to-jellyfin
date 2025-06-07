import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import threading
import time
import json

# Add parent directory to path to import app.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import app, ytj

class TestFrontend(unittest.TestCase):
    """
    Frontend tests using Selenium webdriver.
    Note: These tests require a compatible webdriver to be installed
    and are marked with @unittest.skip by default.
    
    To run these tests:
    1. Install selenium: pip install selenium
    2. Install Chrome or Firefox webdriver
    3. Remove the @unittest.skip decorator
    """
    
    @classmethod
    def setUpClass(cls):
        # Start Flask app in a separate thread
        def run_app():
            app.run(port=5000, debug=False)
        
        cls.server_thread = threading.Thread(target=run_app)
        cls.server_thread.daemon = True
        cls.server_thread.start()
        time.sleep(1)  # Give the server time to start
    
    def setUp(self):
        # Configure Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Initialize the webdriver
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            print(f"Could not initialize Chrome webdriver: {e}")
            self.skipTest("Chrome webdriver not available")
        
        # Configure ytj with test data
        ytj.jobs = {
            "test-job-1": MagicMock(
                job_id="test-job-1",
                playlist_url="https://youtube.com/playlist?list=TEST1",
                show_name="Test Show 1",
                season_num="01",
                episode_start="01",
                status="completed",
                progress=100,
                messages=[],
                created_at="2023-01-01T10:00:00",
                updated_at="2023-01-01T10:30:00",
                to_dict=lambda: {
                    "job_id": "test-job-1",
                    "playlist_url": "https://youtube.com/playlist?list=TEST1",
                    "show_name": "Test Show 1",
                    "season_num": "01",
                    "episode_start": "01",
                    "status": "completed",
                    "progress": 100,
                    "messages": [],
                    "created_at": "2023-01-01T10:00:00",
                    "updated_at": "2023-01-01T10:30:00"
                }
            ),
            "test-job-2": MagicMock(
                job_id="test-job-2",
                playlist_url="https://youtube.com/playlist?list=TEST2",
                show_name="Test Show 2",
                season_num="02",
                episode_start="01",
                status="downloading",
                progress=50,
                messages=[],
                created_at="2023-01-02T10:00:00",
                updated_at="2023-01-02T10:15:00",
                to_dict=lambda: {
                    "job_id": "test-job-2",
                    "playlist_url": "https://youtube.com/playlist?list=TEST2",
                    "show_name": "Test Show 2",
                    "season_num": "02",
                    "episode_start": "01",
                    "status": "downloading",
                    "progress": 50,
                    "messages": [],
                    "created_at": "2023-01-02T10:00:00",
                    "updated_at": "2023-01-02T10:15:00"
                }
            )
        }
        
        # Mock list_media method to return test data
        ytj.list_media = MagicMock(return_value=[
            {
                "name": "Test Show 1",
                "path": "/media/Test Show 1",
                "seasons": [
                    {
                        "name": "Season 01",
                        "path": "/media/Test Show 1/Season 01",
                        "episodes": [
                            {
                                "name": "Test Show 1 S01E01",
                                "path": "/media/Test Show 1/Season 01/Test Show 1 S01E01.mp4",
                                "size": 100000000,
                                "modified": "2023-01-01T10:30:00"
                            }
                        ]
                    }
                ]
            }
        ])
    
    def tearDown(self):
        # Close the browser
        if hasattr(self, 'driver'):
            self.driver.quit()
    
    @unittest.skip("Requires webdriver to be installed and accessible")
    def test_dashboard_page(self):
        """Test that the dashboard page loads correctly"""
        self.driver.get("http://localhost:5000/")
        
        # Check page title
        self.assertEqual(self.driver.title, "Tubarr")
        
        # Check dashboard elements
        self.assertTrue(self.driver.find_element(By.ID, "dashboard").is_displayed())
        self.assertTrue(self.driver.find_element(By.ID, "total-shows").is_displayed())
        self.assertTrue(self.driver.find_element(By.ID, "total-episodes").is_displayed())
        self.assertTrue(self.driver.find_element(By.ID, "active-jobs").is_displayed())
        
        # Check recent jobs table exists
        self.assertTrue(self.driver.find_element(By.ID, "recent-jobs-table").is_displayed())
    
    @unittest.skip("Requires webdriver to be installed and accessible")
    def test_job_list_page(self):
        """Test that the jobs page displays correct job information"""
        self.driver.get("http://localhost:5000/")
        
        # Navigate to jobs page
        self.driver.find_element(By.CSS_SELECTOR, '[data-section="jobs"]').click()
        
        # Wait for the jobs table to appear
        WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.ID, "jobs-table"))
        )
        
        # Check that jobs are displayed in the table
        job_rows = self.driver.find_elements(By.CSS_SELECTOR, "#jobs-table tbody tr")
        self.assertEqual(len(job_rows), 2)
        
        # Check row content
        self.assertIn("Test Show 1", job_rows[0].text)
        self.assertIn("completed", job_rows[0].text)
        self.assertIn("Test Show 2", job_rows[1].text)
        self.assertIn("downloading", job_rows[1].text)
    
    @unittest.skip("Requires webdriver to be installed and accessible")
    def test_new_job_form(self):
        """Test the new job form submission"""
        self.driver.get("http://localhost:5000/")
        
        # Navigate to new job page
        self.driver.find_element(By.CSS_SELECTOR, '[data-section="new-job"]').click()
        
        # Wait for the form to appear
        WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.ID, "new-job-form"))
        )
        
        # Mock the API response for job creation
        with patch('app.YTToJellyfin.create_job', return_value='mock-job-id'):
            # Fill in the form
            self.driver.find_element(By.ID, "playlist_url").send_keys("https://youtube.com/playlist?list=TEST3")
            self.driver.find_element(By.ID, "show_name").send_keys("Test Show 3")
            self.driver.find_element(By.ID, "season_num").send_keys("03")
            self.driver.find_element(By.ID, "episode_start").send_keys("01")
            
            # Submit the form
            self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            
            # Wait for redirection to jobs page
            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.ID, "jobs-table"))
            )
            
            # Verify we're on the jobs page
            self.assertTrue(self.driver.find_element(By.ID, "jobs").is_displayed())
    
    @unittest.skip("Requires webdriver to be installed and accessible")
    def test_media_library_page(self):
        """Test that media library page displays correctly"""
        self.driver.get("http://localhost:5000/")
        
        # Navigate to media page
        self.driver.find_element(By.CSS_SELECTOR, '[data-section="media"]').click()
        
        # Wait for media container to appear
        WebDriverWait(self.driver, 10).until(
            EC.visibility_of_element_located((By.ID, "media-container"))
        )
        
        # Check that show and season are displayed
        show_cards = self.driver.find_elements(By.CSS_SELECTOR, ".card-header h6")
        self.assertEqual(len(show_cards), 1)
        self.assertEqual(show_cards[0].text, "Test Show 1")
        
        # Check season card is displayed
        season_cards = self.driver.find_elements(By.CSS_SELECTOR, ".card-title")
        self.assertEqual(len(season_cards), 1)
        self.assertEqual(season_cards[0].text, "Season 01")
        
        # Click on season to expand episodes
        self.driver.find_element(By.CSS_SELECTOR, ".season-card").click()
        
        # Check episode is displayed
        episode_rows = self.driver.find_elements(By.CSS_SELECTOR, ".episode-table-container tbody tr")
        self.assertEqual(len(episode_rows), 1)
        self.assertIn("Test Show 1 S01E01", episode_rows[0].text)

if __name__ == '__main__':
    unittest.main()