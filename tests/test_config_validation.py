import os
import unittest
from unittest.mock import patch, mock_open
import yaml

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

    def test_tmdb_api_key_env(self):
        env = {"TMDB_API_KEY": "abc"}
        with patch.dict(os.environ, env, clear=True), patch(
            "os.path.exists",
            side_effect=lambda p: False if p == "config/config.yml" else True,
        ), patch("os.access", return_value=True):
            cfg = _load_config()
        self.assertEqual(cfg["tmdb_api_key"], "abc")

    def test_tmdb_api_key_file(self):
        env = {}
        file_cfg = {"tmdb": {"api_key": "xyz"}}
        with patch.dict(os.environ, env, clear=True), patch(
            "os.path.exists",
            return_value=True,
        ), patch("builtins.open", mock_open(read_data=yaml.dump(file_cfg))), patch(
            "os.access", return_value=True
        ):
            cfg = _load_config()
        self.assertEqual(cfg["tmdb_api_key"], "xyz")


if __name__ == "__main__":
    unittest.main()
