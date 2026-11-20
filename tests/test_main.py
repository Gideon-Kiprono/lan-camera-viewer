
"""Unit tests for frame processing, FPS, recorder safety and reachability."""

import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import requests

import main


class ResizeTests(unittest.TestCase):
    def test_1920x1080_to_960_wide(self):
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        out = main.resize_to_width(frame, 960)
        self.assertEqual(out.shape, (540, 960, 3))  # (height, width, channels)

    def test_aspect_ratio_kept(self):
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        out = main.resize_to_width(frame, 640)
        self.assertEqual(out.shape, (360, 640, 3))

    def test_same_width_returns_same_frame(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.assertIs(main.resize_to_width(frame, 640), frame)

    def test_upscale(self):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        out = main.resize_to_width(frame, 640)
        self.assertEqual(out.shape, (480, 640, 3))


class FpsTests(unittest.TestCase):
    def test_first_update_is_zero_then_steady_rate(self):
        counter = main.FpsCounter()
        with patch.object(main.time, "perf_counter", side_effect=[0.0, 0.1, 0.2]):
            self.assertEqual(counter.update(), 0.0)
            self.assertAlmostEqual(counter.update(), 10.0)
            self.assertAlmostEqual(counter.update(), 10.0)

    def test_reset_clears_state(self):
        counter = main.FpsCounter()
        counter.fps = 25.0
        counter.reset()
        self.assertEqual(counter.fps, 0.0)


class RecorderTests(unittest.TestCase):
    def test_stop_when_not_recording_is_safe(self):
        recorder = main.Recorder()
        self.assertIsNone(recorder.stop())
        self.assertFalse(recorder.recording)

    def test_write_when_not_recording_does_nothing(self):
        recorder = main.Recorder()
        recorder.write(np.zeros((10, 10, 3), dtype=np.uint8))  # must not raise


class ScreenshotTests(unittest.TestCase):
    def test_two_screenshots_get_different_names(self):
        frame = np.zeros((90, 160, 3), dtype=np.uint8)
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(main, "SCREENSHOT_DIR", os.path.join(tmp, "shots")):
                first = main.save_screenshot(frame)
                time.sleep(0.01)
                second = main.save_screenshot(frame)
                self.assertIsNotNone(first)
                self.assertIsNotNone(second)
                self.assertNotEqual(first, second)
                self.assertTrue(os.path.exists(first))
                self.assertTrue(os.path.exists(second))


class ReachabilityTests(unittest.TestCase):
    def test_connection_error_gives_clear_message(self):
        with patch.object(main.requests, "get",
                          side_effect=requests.exceptions.ConnectionError()):
            ok, message = main.check_reachable("http://192.168.1.250:8080/video")
        self.assertFalse(ok)
        self.assertIn("Cannot reach", message)

    def test_timeout_gives_clear_message(self):
        with patch.object(main.requests, "get",
                          side_effect=requests.exceptions.Timeout()):
            ok, message = main.check_reachable("http://192.168.1.250:8080/video")
        self.assertFalse(ok)
        self.assertIn("did not answer", message)

    def test_success(self):
        response = MagicMock()
        response.__enter__.return_value = response
        with patch.object(main.requests, "get", return_value=response):
            ok, message = main.check_reachable("http://192.168.1.23:8080/video")
        self.assertTrue(ok)

    def test_rtsp_is_skipped(self):
        ok, _ = main.check_reachable("rtsp://192.168.1.23/stream")
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()