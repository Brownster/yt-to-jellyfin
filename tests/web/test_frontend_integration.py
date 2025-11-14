import json
import unittest
from unittest.mock import call, patch

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
            quality=None,
            use_h265=None,
            crf=None,
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

    def test_music_job_creation_with_optional_metadata(self):
        job_request = {
            "job_type": "album",
            "source_url": "https://youtube.com/playlist?list=ALBUM",
            "display_name": "Live Album",
            "collection": {
                "title": "Live Album",
                "artist": "Demo Band",
                "year": "2024",
                "genres": ["Rock", "Live"],
                "cover_url": "https://img.example/cover.jpg",
                "embed_cover": True,
            },
            "tracks": [
                {
                    "title": "Opening",
                    "artist": "Demo Band",
                    "album": "Live Album",
                    "track_number": 1,
                    "disc_number": 1,
                    "genres": ["Rock"],
                    "tags": {"mood": "energetic"},
                    "year": "2024",
                    "source_url": "https://youtu.be/track1",
                }
            ],
        }
        self.mock_ytj.create_music_job.return_value = "music-opt"

        response = self.client.post(
            "/music/jobs",
            data=json.dumps(job_request),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.data.decode())
        self.assertEqual(payload["job_id"], "music-opt")
        self.mock_ytj.create_music_job.assert_called_once_with(job_request)

    def test_music_job_creation_schema_validation_error(self):
        job_request = {"job_type": "album", "source_url": "", "tracks": []}
        self.mock_ytj.create_music_job.side_effect = ValueError(
            "Missing required field: source_url"
        )

        response = self.client.post(
            "/music/jobs",
            data=json.dumps(job_request),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        payload = json.loads(response.data.decode())
        self.assertEqual(
            payload,
            {"error": "Missing required field: source_url"},
        )
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

    def test_music_jobs_list_preserves_music_request_metadata(self):
        music_job = {
            "job_id": "m1",
            "media_type": "music",
            "music_request": {"job_type": "album", "display_name": "Sampler"},
        }
        self.mock_ytj.get_jobs.return_value = [
            music_job,
            {"job_id": "tv1", "media_type": "tv"},
        ]

        response = self.client.get("/music/jobs")

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.data.decode())
        self.assertEqual(payload, [music_job])

    def test_music_job_detail_returns_job_payload(self):
        job_detail = {
            "job_id": "music-55",
            "media_type": "music",
            "status": "queued",
            "music_request": {"display_name": "Mixtape"},
        }
        self.mock_ytj.get_job.return_value = job_detail

        response = self.client.get("/music/jobs/music-55")

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.data.decode())
        self.assertEqual(payload, job_detail)
        self.mock_ytj.get_job.assert_called_once_with("music-55")

    def test_music_job_detail_missing_returns_404(self):
        self.mock_ytj.get_job.return_value = None

        response = self.client.get("/music/jobs/not-real")

        self.assertEqual(response.status_code, 404)
        payload = json.loads(response.data.decode())
        self.assertEqual(payload, {"error": "Job not found"})
        self.mock_ytj.get_job.assert_called_once_with("not-real")

    def test_music_job_duplicate_submissions_create_unique_jobs(self):
        job_request = {
            "job_type": "single",
            "source_url": "https://youtu.be/song",
            "display_name": "Song",
            "collection": {"title": "Song"},
            "tracks": [],
        }
        self.mock_ytj.create_music_job.side_effect = ["music-100", "music-101"]

        first_response = self.client.post(
            "/music/jobs",
            data=json.dumps(job_request),
            content_type="application/json",
        )
        second_response = self.client.post(
            "/music/jobs",
            data=json.dumps(job_request),
            content_type="application/json",
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        first_payload = json.loads(first_response.data.decode())
        second_payload = json.loads(second_response.data.decode())
        self.assertEqual(first_payload, {"job_id": "music-100"})
        self.assertEqual(second_payload, {"job_id": "music-101"})
        self.assertEqual(
            self.mock_ytj.create_music_job.call_args_list,
            [call(job_request), call(job_request)],
        )


if __name__ == "__main__":
    unittest.main()
