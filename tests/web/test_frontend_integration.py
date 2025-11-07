import json
import unittest
from unittest.mock import patch

from tubarr.web import app


class FrontendIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.patcher = patch("tubarr.web.ytj", autospec=True)
        self.mock_ytj = self.patcher.start()
        self.addCleanup(self.patcher.stop)
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_index_renders_dashboard_with_data(self):
        self.mock_ytj.get_jobs.return_value = [
            {"job_id": "abc", "show_name": "Demo Show", "status": "completed"}
        ]
        self.mock_ytj.list_media.return_value = [
            {
                "name": "Demo Show",
                "seasons": [
                    {
                        "name": "Season 01",
                        "episodes": [
                            {"name": "Demo Show S01E01", "path": "/media/demo.mp4"}
                        ],
                    }
                ],
            }
        ]

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        body = response.data.decode()
        self.assertIn("TUBARR", body)
        self.assertIn('data-section="new-music"', body)
        self.assertIn('id="jobs-table"', body)
        self.mock_ytj.get_jobs.assert_called_once()
        self.mock_ytj.list_media.assert_called_once()

    def test_create_tv_job_via_form(self):
        self.mock_ytj.create_job.return_value = "job-42"

        response = self.client.post(
            "/jobs",
            data={
                "playlist_url": "https://youtube.com/playlist?list=XYZ",
                "show_name": "Example Show",
                "season_num": "01",
                "episode_start": "01",
                "track_playlist": "true",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.data.decode())
        self.assertEqual(payload["job_id"], "job-42")
        self.mock_ytj.create_job.assert_called_once_with(
            "https://youtube.com/playlist?list=XYZ",
            "Example Show",
            "01",
            "01",
            playlist_start=None,
            track_playlist=True,
        )

    def test_music_job_creation_errors_without_payload(self):
        response = self.client.post("/music/jobs", data="", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing request payload", response.get_data(as_text=True))

    def test_music_job_creation_succeeds(self):
        job_request = {"url": "https://youtube.com/watch?v=ID", "title": "Song"}
        self.mock_ytj.create_music_job.return_value = "music-1"

        response = self.client.post(
            "/music/jobs",
            data=json.dumps(job_request),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.data.decode())
        self.assertEqual(payload["job_id"], "music-1")
        self.mock_ytj.create_music_job.assert_called_once_with(job_request)

    def test_music_jobs_list_filters_only_music(self):
        self.mock_ytj.get_jobs.return_value = [
            {"job_id": "a", "media_type": "music"},
            {"job_id": "b", "media_type": "tv"},
        ]

        response = self.client.get("/music/jobs")

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.data.decode())
        self.assertEqual(payload, [{"job_id": "a", "media_type": "music"}])


if __name__ == "__main__":
    unittest.main()
