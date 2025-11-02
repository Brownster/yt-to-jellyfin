import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tubarr.subscriptions import (
    create_subscription,
    update_subscription,
    remove_subscription,
    check_subscription_updates,
    apply_retention_policy,
)
from tubarr.utils import sanitize_name


class DummyApp:
    def __init__(self, tmpdir: str):
        self.config = {"ytdlp_path": "yt-dlp", "output_dir": tmpdir}
        self.subscriptions_file = os.path.join(tmpdir, "subscriptions.json")
        self.subscriptions = {}
        self.jobs = {}
        self.episode_tracker = {}

    def create_folder_structure(self, show_name: str, season_num: str) -> str:
        folder = (
            Path(self.config["output_dir"]) / sanitize_name(show_name) / f"Season {season_num}"
        )
        folder.mkdir(parents=True, exist_ok=True)
        return str(folder)

    def get_last_episode(self, show_name: str, season_num: str) -> int:
        return 0

    def _get_existing_max_index(self, folder: str, season_num: str) -> int:
        return 0

    def _get_archive_file(self, url: str) -> str:
        safe_name = sanitize_name(url)
        archive_dir = Path(self.config["output_dir"]) / "archives"
        archive_dir.mkdir(parents=True, exist_ok=True)
        return str(archive_dir / f"{safe_name}.txt")


class SubscriptionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = DummyApp(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("subprocess.run")
    def test_create_subscription_records_entry(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"entries": [{"id": "a"}, {"id": "b"}]})
        )

        sub_id = create_subscription(
            self.app,
            "https://youtube.com/@channel",
            "My Show",
            "keep_episodes",
            "5",
        )

        self.assertIn(sub_id, self.app.subscriptions)
        entry = self.app.subscriptions[sub_id]
        self.assertEqual(entry["season_num"], "00")
        self.assertEqual(entry["retention"], {"mode": "episodes", "value": 5})
        self.assertTrue(os.path.exists(entry["archive"]))
        with open(entry["archive"], "r") as archive:
            archived_ids = [line.strip() for line in archive.readlines() if line.strip()]
        self.assertEqual(archived_ids, ["a", "b"])

    def test_update_and_remove_subscription(self):
        sub_id = "channel1"
        archive = os.path.join(self.temp_dir.name, "archive.txt")
        self.app.subscriptions[sub_id] = {
            "id": sub_id,
            "url": "https://youtube.com/@channel",
            "show_name": "Show",
            "season_num": "00",
            "retention": {"mode": "all", "value": None},
            "archive": archive,
            "disabled": False,
        }
        Path(archive).parent.mkdir(parents=True, exist_ok=True)
        Path(archive).write_text("old\n")

        updated = update_subscription(
            self.app,
            sub_id,
            show_name="New Show",
            retention_type="keep_days",
            retention_value="3",
            enabled=False,
        )

        self.assertTrue(updated)
        info = self.app.subscriptions[sub_id]
        self.assertEqual(info["show_name"], "New Show")
        self.assertEqual(info["retention"], {"mode": "days", "value": 3})
        self.assertTrue(info["disabled"])

        removed = remove_subscription(self.app, sub_id)
        self.assertTrue(removed)
        self.assertNotIn(sub_id, self.app.subscriptions)
        self.assertFalse(os.path.exists(archive))

    @patch("subprocess.run")
    def test_check_subscription_updates_creates_job(self, mock_run):
        archive = self.app._get_archive_file("https://youtube.com/@channel")
        with open(archive, "w") as f:
            f.write("old\n")
        self.app.subscriptions["channel"] = {
            "id": "channel",
            "url": "https://youtube.com/@channel",
            "show_name": "Update Show",
            "season_num": "00",
            "retention": {"mode": "all", "value": None},
            "archive": archive,
            "disabled": False,
        }
        mock_run.return_value = MagicMock(
            stdout=json.dumps(
                {
                    "entries": [
                        {"id": "old", "playlist_index": 10},
                        {"id": "new", "playlist_index": 11},
                    ]
                }
            )
        )
        self.app.create_job = MagicMock(return_value="job-xyz")

        jobs = check_subscription_updates(self.app)

        self.assertEqual(jobs, ["job-xyz"])
        self.app.create_job.assert_called_once()
        args, kwargs = self.app.create_job.call_args
        self.assertEqual(args[2], "00")
        self.assertEqual(kwargs["playlist_start"], 11)
        self.assertEqual(kwargs["subscription_id"], "channel")
        self.assertFalse(kwargs["track_playlist"])

    def test_apply_retention_policy_removes_old_episodes(self):
        sub_id = "ret-test"
        show_folder = Path(self.app.create_folder_structure("Retention Show", "00"))
        video1 = show_folder / "Retention Show S00E01.mp4"
        video2 = show_folder / "Retention Show S00E02.mp4"
        video1.write_bytes(b"0")
        video2.write_bytes(b"0")
        (show_folder / "Retention Show S00E01.nfo").write_text("nfo1")
        (show_folder / "Retention Show S00E02.nfo").write_text("nfo2")
        self.app.subscriptions[sub_id] = {
            "id": sub_id,
            "url": "https://youtube.com/@retention",
            "show_name": "Retention Show",
            "season_num": "00",
            "retention": {"mode": "episodes", "value": 1},
        }

        apply_retention_policy(self.app, sub_id)

        remaining = sorted(p.name for p in show_folder.glob("*"))
        self.assertIn("Retention Show S00E02.mp4", remaining)
        self.assertIn("Retention Show S00E02.nfo", remaining)
        self.assertNotIn("Retention Show S00E01.mp4", remaining)
        self.assertNotIn("Retention Show S00E01.nfo", remaining)


if __name__ == "__main__":
    unittest.main()
