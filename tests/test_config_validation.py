import os
import unittest
from unittest.mock import patch

from tubarr.config import _load_config


class TestConfigValidation(unittest.TestCase):
    def test_invalid_web_port(self):
        env = {
            "WEB_PORT": "70000",
        }
        with patch.dict(os.environ, env, clear=True), patch(
            "os.path.exists",
            side_effect=lambda p: False if p == "config/config.yml" else True,
        ), patch("os.access", return_value=True):
            with self.assertRaises(ValueError):
                _load_config()

    def test_invalid_crf(self):
        env = {"CRF": "100"}
        with patch.dict(os.environ, env, clear=True), patch(
            "os.path.exists",
            side_effect=lambda p: False if p == "config/config.yml" else True,
        ), patch("os.access", return_value=True):
            with self.assertRaises(ValueError):
                _load_config()

    def test_missing_output_dir(self):
        env = {"OUTPUT_DIR": ""}
        with patch.dict(os.environ, env, clear=True), patch(
            "os.path.exists",
            side_effect=lambda p: False if p == "config/config.yml" else True,
        ), patch("os.access", return_value=True):
            with self.assertRaises(ValueError):
                _load_config()


if __name__ == "__main__":
    unittest.main()
