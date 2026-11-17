"""Load and validate settings from environment variables / .env."""

import os
import sys
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

ALLOWED_SCHEMES = ("http", "https", "rtsp")


class ConfigError(Exception):
    """Raised when a setting is missing or invalid."""


def _get_int(name, default, minimum=1):
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a whole number, got '{raw}'.")
    if value < minimum:
        raise ConfigError(f"{name} must be at least {minimum}, got {value}.")
    return value


def _validate_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ConfigError(
            f"Invalid camera URL scheme '{parsed.scheme}'. "
            f"Use one of: {', '.join(ALLOWED_SCHEMES)}."
        )
    if not parsed.hostname:
        raise ConfigError("Camera URL has no host (expected e.g. http://192.168.1.23:8080/video).")
    return url


def load_config():
    """Return a dict of validated settings, or raise ConfigError."""
    url = os.getenv("CAMERA_URL", "").strip()
    if not url:
        raise ConfigError("CAMERA_URL is not set. Copy .env.example to .env and edit it.")

    return {
        "camera_url": _validate_url(url),
        "camera_name": os.getenv("CAMERA_NAME", "Camera").strip() or "Camera",
        "display_width": _get_int("DISPLAY_WIDTH", 960, minimum=160),
        "max_reconnects": _get_int("MAX_RECONNECTS", 5, minimum=0),
        "reconnect_delay": _get_int("RECONNECT_DELAY", 3, minimum=1),
    }


if __name__ == "__main__":
    try:
        cfg = load_config()
    except ConfigError as exc:
        print(f"Configuration error: {exc}")
        sys.exit(1)
    shown = dict(cfg, camera_url="<hidden>")
    print("Config OK:", shown)
