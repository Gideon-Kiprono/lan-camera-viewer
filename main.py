"""LAN Camera Viewer - Phase 4: screenshots with the S key."""

import os
import sys
import time
from datetime import datetime

import cv2

from config import ConfigError, load_config

WINDOW_NAME = "LAN Camera Viewer"
ESC_KEY = 27
SCREENSHOT_DIR = "screenshots"
MESSAGE_SECONDS = 2.0
FONT = cv2.FONT_HERSHEY_SIMPLEX
WHITE = (255, 255, 255)  # OpenCV uses BGR order, not RGB
BLACK = (0, 0, 0)
GREEN = (0, 200, 0)


def resize_to_width(frame, width):
    """Resize to a fixed width, keeping the aspect ratio."""
    h, w = frame.shape[:2]  # shape is (height, width, channels)
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


def save_screenshot(frame):
    """Save a frame to screenshots/ with a unique timestamped name.

    Returns the file path, or None if saving failed.
    """
    try:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # milliseconds
        path = os.path.join(SCREENSHOT_DIR, f"screenshot_{stamp}.png")
        if not cv2.imwrite(path, frame):
            print("Could not write the screenshot file.")
            return None
        return path
    except OSError as exc:
        print(f"Could not save screenshot: {exc}")
        return None


def run(cfg):
    cap = cv2.VideoCapture(cfg["camera_url"])
    fps_counter = FpsCounter()
    message = ""
    message_until = 0.0
    try:
        if not cap.isOpened():
            print("Could not open the camera stream. Check the URL and network.")
            return 1

        print("Streaming. Esc = quit, S = screenshot.")
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Failed to read a frame from the camera.")
                return 1

            frame = resize_to_width(frame, cfg["display_width"])
            fps = fps_counter.update()
            draw_overlay(frame, cfg["camera_name"], fps)

            # Copy taken before the confirmation text is drawn on top.
            snapshot = frame.copy()

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
                    message = f"Saved {os.path.basename(path)}"
                else:
                    message = "Screenshot FAILED"
                message_until = time.time() + MESSAGE_SECONDS
    finally:
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
    except KeyboardInterrupt:
        print("\nInterrupted by user. Shutting down.")
        return 0


if __name__ == "__main__":
    sys.exit(main())