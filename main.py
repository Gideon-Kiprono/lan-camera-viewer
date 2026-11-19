"""LAN Camera Viewer - Phase 6: error handling, reconnects, safe shutdown."""

import os
import sys
import time
from datetime import datetime

import cv2
import numpy as np
import requests

from config import ConfigError, load_config

WINDOW_NAME = "LAN Camera Viewer"
ESC_KEY = 27
SCREENSHOT_DIR = "screenshots"
RECORDING_DIR = "recordings"
MESSAGE_SECONDS = 2.0
FALLBACK_FPS = 15.0
CONNECT_TIMEOUT = 5       # seconds to wait for the camera to answer
READ_TIMEOUT_MS = 5000    # how long a frame read may block before failing
MAX_READ_FAILURES = 3     # consecutive failed reads before treating it as a drop
FONT = cv2.FONT_HERSHEY_SIMPLEX
WHITE = (255, 255, 255)  # OpenCV uses BGR order, not RGB
BLACK = (0, 0, 0)
GREEN = (0, 200, 0)
RED = (0, 0, 255)
AMBER = (0, 180, 255)


class UserQuit(Exception):
    """Raised when the user presses Esc while we are not in the main loop."""


# ---------- drawing and processing ----------

def resize_to_width(frame, width):
    """Resize to a fixed width, keeping the aspect ratio."""
    h, w = frame.shape[:2]
    if w == width:
        return frame
    scale = width / w
    new_h = int(round(h * scale))
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    return cv2.resize(frame, (width, new_h), interpolation=interp)


def put_text(img, text, origin, scale=0.6, color=WHITE):
    """Draw text on a dark box so it stays readable on any background."""
    (tw, th), baseline = cv2.getTextSize(text, FONT, scale, 1)
    x, y = origin
    cv2.rectangle(img, (x - 4, y - th - 4), (x + tw + 4, y + baseline + 2), BLACK, -1)
    cv2.putText(img, text, (x, y), FONT, scale, color, 1, cv2.LINE_AA)


class FpsCounter:
    """Estimate FPS from the time between frames, smoothed over time."""

    def __init__(self, alpha=0.1):
        self.alpha = alpha
        self.fps = 0.0
        self._last = None

    def reset(self):
        self.fps = 0.0
        self._last = None

    def update(self):
        now = time.perf_counter()
        if self._last is not None:
            dt = now - self._last
            if dt > 0:
                instant = 1.0 / dt
                if self.fps == 0.0:
                    self.fps = instant
                else:
                    self.fps = self.alpha * instant + (1 - self.alpha) * self.fps
        self._last = now
        return self.fps


def draw_overlay(frame, camera_name, fps):
    h, w = frame.shape[:2]
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    put_text(frame, camera_name, (10, 25))
    put_text(frame, stamp, (10, 50))
    put_text(frame, f"{w}x{h}", (10, 75))
    put_text(frame, f"FPS: {fps:.1f}", (10, 100))


def draw_rec_status(frame, seconds):
    w = frame.shape[1]
    mins, secs = divmod(int(seconds), 60)
    cv2.circle(frame, (w - 120, 20), 7, RED, -1)
    put_text(frame, f"REC {mins:02d}:{secs:02d}", (w - 105, 26), color=RED)


# ---------- files ----------

def save_screenshot(frame):
    """Save a frame to screenshots/ with a unique timestamped name."""
    try:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        path = os.path.join(SCREENSHOT_DIR, f"screenshot_{stamp}.png")
        if not cv2.imwrite(path, frame):
            print("Could not write the screenshot file.")
            return None
        return path
    except OSError as exc:
        print(f"Could not save screenshot: {exc}")
        return None


class Recorder:
    """Wraps cv2.VideoWriter so start/stop/cleanup live in one place."""

    def __init__(self):
        self.writer = None
        self.path = None
        self.size = None
        self.started_at = 0.0

    @property
    def recording(self):
        return self.writer is not None

    def start(self, frame, fps):
        h, w = frame.shape[:2]
        fps = fps if 5.0 <= fps <= 60.0 else FALLBACK_FPS
        try:
            os.makedirs(RECORDING_DIR, exist_ok=True)
        except OSError as exc:
            print(f"Could not create recordings folder: {exc}")
            return None
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        path = os.path.join(RECORDING_DIR, f"recording_{stamp}.mp4")
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(path, fourcc, fps, (w, h))  # size is (width, height)
        if not writer.isOpened():
            print("Could not start the recording (video writer failed to open).")
            return None
        self.writer, self.path, self.size = writer, path, (w, h)
        self.started_at = time.time()
        return path

    def write(self, frame):
        if not self.writer:
            return
        h, w = frame.shape[:2]
        if (w, h) != self.size:
            frame = cv2.resize(frame, self.size)
        self.writer.write(frame)

    def elapsed(self):
        return time.time() - self.started_at if self.writer else 0.0

    def stop(self):
        """Finish the file. Safe to call when not recording."""
        path = self.path
        if self.writer:
            self.writer.release()
        self.writer = None
        self.path = None
        return path


# ---------- connection handling ----------

def check_reachable(url):
    """Ask the camera for its headers before handing the URL to OpenCV.

    Returns (ok, message). RTSP cannot be checked with HTTP, so it is skipped.
    """
    if url.lower().startswith("rtsp"):
        return True, ""
    try:
        with requests.get(url, stream=True, timeout=(CONNECT_TIMEOUT, CONNECT_TIMEOUT)) as resp:
            resp.raise_for_status()
        return True, ""
    except requests.exceptions.Timeout:
        return False, f"The camera did not answer within {CONNECT_TIMEOUT} seconds."
    except requests.exceptions.ConnectionError:
        return False, "Cannot reach the camera. Is it on, on the same Wi-Fi, with the right IP and port?"
    except requests.exceptions.HTTPError as exc:
        return False, f"The camera answered with an error: {exc}"
    except requests.exceptions.RequestException as exc:
        return False, f"Invalid or unusable camera URL: {exc}"


def open_camera(url):
    """Open the stream with timeouts, so it fails instead of hanging."""
    params = [
        cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, CONNECT_TIMEOUT * 1000,
        cv2.CAP_PROP_READ_TIMEOUT_MSEC, READ_TIMEOUT_MS,
    ]
    try:
        return cv2.VideoCapture(url, cv2.CAP_FFMPEG, params)
    except (TypeError, cv2.error, AttributeError):
        return cv2.VideoCapture(url)  # older OpenCV without timeout parameters


def connect(url):
    """Return an open capture, or None (after printing why)."""
    ok, message = check_reachable(url)
    if not ok:
        print(message)
        return None
    cap = open_camera(url)
    if not cap.isOpened():
        cap.release()
        print("The camera answered, but the video stream could not be opened.")
        return None
    return cap


def show_status_screen(width, text):
    """Show a plain screen while reconnecting; Esc still works."""
    img = np.zeros((int(width * 9 / 16), width, 3), dtype=np.uint8)
    put_text(img, text, (20, img.shape[0] // 2), scale=0.7, color=AMBER)
    cv2.imshow(WINDOW_NAME, img)


def wait_with_window(seconds, width, text):
    """Wait while keeping the window responsive. Raises UserQuit on Esc."""
    end = time.time() + seconds
    while time.time() < end:
        show_status_screen(width, text)
        if cv2.waitKey(100) & 0xFF == ESC_KEY:
            raise UserQuit()


def reconnect(cfg):
    """Try to reconnect a limited number of times. Returns a capture or None."""
    limit = cfg["max_reconnects"]
    for attempt in range(1, limit + 1):
        print(f"Connection lost. Reconnect attempt {attempt}/{limit}...")
        text = f"Connection lost - retry {attempt}/{limit}"
        wait_with_window(cfg["reconnect_delay"], cfg["display_width"], text)
        cap = connect(cfg["camera_url"])
        if cap is not None:
            print("Reconnected.")
            return cap
    print(f"Giving up after {limit} reconnect attempts.")
    return None


# ---------- main loop ----------

def run(cfg):
    cap = connect(cfg["camera_url"])
    if cap is None:
        print("Could not start streaming. Check CAMERA_URL in your .env file.")
        return 1

    fps_counter = FpsCounter()
    recorder = Recorder()
    message = ""
    message_until = 0.0
    read_failures = 0

    def notify(text):
        nonlocal message, message_until
        message = text
        message_until = time.time() + MESSAGE_SECONDS

    try:
        print("Streaming. Esc = quit, S = screenshot, R = start/stop recording.")
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                read_failures += 1
                if read_failures < MAX_READ_FAILURES:
                    continue  # a single bad read is not a dropped connection
                cap.release()
                cap = reconnect(cfg)
                if cap is None:
                    return 1
                read_failures = 0
                fps_counter.reset()
                continue
            read_failures = 0

            frame = resize_to_width(frame, cfg["display_width"])
            fps = fps_counter.update()
            draw_overlay(frame, cfg["camera_name"], fps)

            snapshot = frame.copy()  # overlays, but no REC badge or messages
            recorder.write(snapshot)

            if recorder.recording:
                draw_rec_status(frame, recorder.elapsed())
            if time.time() < message_until:
                put_text(frame, message, (10, frame.shape[0] - 15), color=GREEN)

            cv2.imshow(WINDOW_NAME, frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ESC_KEY:
                break
            if key in (ord("s"), ord("S")):
                path = save_screenshot(snapshot)
                if path:
                    print(f"Screenshot saved: {path}")
                    notify(f"Saved {os.path.basename(path)}")
                else:
                    notify("Screenshot FAILED")
            if key in (ord("r"), ord("R")):
                if recorder.recording:
                    path = recorder.stop()
                    print(f"Recording saved: {path}")
                    notify("Recording saved")
                else:
                    path = recorder.start(snapshot, fps)
                    if path:
                        print(f"Recording started: {path}")
                    else:
                        notify("Recording FAILED")
    finally:
        # Runs on Esc, Ctrl+C, giving up, and unexpected errors.
        path = recorder.stop()
        if path:
            print(f"Recording finalised: {path}")
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()
    return 0


def main():
    try:
        cfg = load_config()
    except ConfigError as exc:
        print(f"Configuration error: {exc}")
        return 1

    try:
        return run(cfg)
    except UserQuit:
        print("Quit by user.")
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted by user. Shutting down.")
        return 0
    except cv2.error as exc:
        print(f"Video error: {exc}")
        return 1
    except Exception as exc:  # last resort: a clear message instead of a traceback
        print(f"Unexpected error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())