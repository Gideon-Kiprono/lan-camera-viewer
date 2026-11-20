"""Unit tests for config validation."""

import os
import unittest
from unittest.mock import patch

from config import ConfigError, load_config

GOOD_URL = "http://192.168.1.23:8080/video"


class ConfigTests(unittest.TestCase):
    def load(self, env):
        with patch.dict(os.environ, env, clear=True):
            return load_config()

    def test_valid_config_uses_defaults(self):
        cfg = self.load({"CAMERA_URL": GOOD_URL})
        self.assertEqual(cfg["camera_url"], GOOD_URL)
        self.assertEqual(cfg["camera_name"], "Camera")
        self.assertEqual(cfg["display_width"], 960)
        self.assertEqual(cfg["max_reconnects"], 5)
        self.assertEqual(cfg["reconnect_delay"], 3)

    def test_missing_url_raises(self):
        with self.assertRaises(ConfigError):
            self.load({})

    def test_bad_scheme_raises(self):
        with self.assertRaises(ConfigError):
            self.load({"CAMERA_URL": "htp://camera"})

    def test_missing_host_raises(self):
        with self.assertRaises(ConfigError):
            self.load({"CAMERA_URL": "http://"})

    def test_non_numeric_width_raises(self):
        with self.assertRaises(ConfigError):
            self.load({"CAMERA_URL": GOOD_URL, "DISPLAY_WIDTH": "wide"})

    def test_width_below_minimum_raises(self):
        with self.assertRaises(ConfigError):
            self.load({"CAMERA_URL": GOOD_URL, "DISPLAY_WIDTH": "100"})

    def test_zero_reconnects_allowed(self):
        cfg = self.load({"CAMERA_URL": GOOD_URL, "MAX_RECONNECTS": "0"})
        self.assertEqual(cfg["max_reconnects"], 0)


if __name__ == "__main__":
    unittest.main()

