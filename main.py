"""LAN Camera Viewer - Phase 2: live stream, Esc to exit."""

import sys

import cv2

from config import ConfigError, load_config

WINDOW_NAME = "LAN Camera Viewer"
ESC_KEY = 27


def run(cfg):
    cap = cv2.VideoCapture(cfg["camera_url"])
    try:
        if not cap.isOpened():
            print("Could not open the camera stream. Check the URL and network.")
            return 1

        print("Streaming. Press Esc in the video window to quit.")
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Failed to read a frame from the camera.")
                return 1

            cv2.imshow(WINDOW_NAME, frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ESC_KEY:
                break
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
