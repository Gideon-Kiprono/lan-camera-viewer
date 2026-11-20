# LAN Camera Viewer

A lightweight desktop viewer for IP and smartphone cameras on a local network, built with Python and OpenCV. It streams live video, overlays a timestamp, camera name, resolution and estimated FPS, saves screenshots and recordings with a single keypress, and recovers from bad URLs, unreachable cameras and dropped connections.

> **For authorised cameras only.** Use this tool only with a camera you own or have explicit permission to use. Do not record people who have not agreed to it.

![Live view with overlays](docs/live-view.png)

## Features

- Live MJPEG/HTTP stream display with OpenCV
- Frames resized to a fixed width with the aspect ratio kept
- Overlays: date and time, camera name, frame resolution, smoothed FPS estimate
- **S** saves a timestamped screenshot, with an on-screen confirmation
- **R** starts and stops a timestamped recording, with a red REC badge and elapsed time
- Reachability check with a timeout before the stream is opened, so it fails fast instead of hanging
- Bounded reconnect logic when the connection drops mid-stream
- Safe shutdown on Esc, Ctrl+C or error: any recording is finalised, the camera is released and windows are closed
- Camera address kept out of the source code (read from `.env`)

## Requirements

- Python 3.10 or newer
- A camera reachable over your local network, for example an Android phone running [IP Webcam](https://play.google.com/store/apps/details?id=com.pas.webcam)
- Dependencies (see `requirements.txt`): `opencv-python`, `numpy`, `requests`, `python-dotenv`

## Installation

```bash
git clone https://github.com/Gideon-Kiprono/lan-camera-viewer.git
cd lan-camera-viewer
python -m venv my_python_env
```

Activate the virtual environment:

```bash
# Git Bash
source my_python_env/Scripts/activate

# PowerShell
my_python_env\Scripts\Activate.ps1

# macOS / Linux
source my_python_env/bin/activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

## Configuring the camera

1. Put the phone and the computer on the **same Wi-Fi network**.
2. In IP Webcam, tap **Start server** and note the address shown, for example `http://192.168.1.23:8080`.
3. Check it in your browser: open `http://<phone-ip>:8080/video`. If you see live video, the network side works.
4. Copy the example settings file and edit it:

```bash
cp .env.example .env
```

5. Set your camera address in `.env`:

```
CAMERA_URL=http://192.168.1.23:8080/video
CAMERA_NAME=Office Camera
DISPLAY_WIDTH=960
MAX_RECONNECTS=5
RECONNECT_DELAY=3
```

`.env` is listed in `.gitignore`, so your camera address and any credentials are never committed. Only `.env.example`, which holds placeholder values, is in the repository.

| Setting | Meaning | Default |
|---|---|---|
| `CAMERA_URL` | Stream URL (required). Schemes: `http`, `https`, `rtsp` | none |
| `CAMERA_NAME` | Label shown in the overlay | `Camera` |
| `DISPLAY_WIDTH` | Display width in pixels (minimum 160) | `960` |
| `MAX_RECONNECTS` | Reconnect attempts before giving up | `5` |
| `RECONNECT_DELAY` | Seconds to wait between attempts | `3` |

## Usage

```bash
python main.py
```

| Key | Action |
|---|---|
| **Esc** | Quit |
| **S** | Save a screenshot to `screenshots/` |
| **R** | Start / stop recording to `recordings/` |

Click the video window first so it has keyboard focus. Ctrl+C in the terminal also shuts down cleanly.

Screenshots and recordings are named with a timestamp down to the millisecond, for example `screenshot_20261118_172530_123.png` and `recording_20261118_172530_123.mp4`, so a new file never overwrites an old one. Both folders are created automatically and are ignored by Git.

## How it handles failures

| Situation | Behaviour |
|---|---|
| Missing or malformed `CAMERA_URL` (e.g. `htp://camera`) | Clear configuration error, clean exit |
| Camera off, wrong IP or wrong port | Reachability check times out after 5 seconds with a clear message, clean exit |
| A single failed frame read | Ignored |
| Three failed reads in a row | Treated as a dropped connection: status screen shown, then up to `MAX_RECONNECTS` retries |
| Retry limit reached | Clear message, clean exit |
| Esc, Ctrl+C or any error during a recording | Recording is finalised so the file plays, then the camera is released |

You may see occasional `[mjpeg] overread` lines in the console. These come from FFmpeg when Wi-Fi delivers a slightly damaged frame. They are harmless.

## Project structure

```
lan-camera-viewer/
├── main.py            # Main loop, overlays, screenshots, recording, reconnect logic
├── config.py          # Loads and validates settings from .env / environment
├── requirements.txt   # Python dependencies
├── .env.example       # Template settings with placeholder values (committed)
├── .env               # Your real settings (ignored by Git)
├── .gitignore
├── docs/              # Sample screenshots
└── tests/             # Unit tests (python -m unittest discover tests)
```

## Privacy and ethics

This tool can stream and record video, so use it responsibly:

- Connect only to cameras you own or have permission to use.
- Tell anyone who may appear on camera that recording is happening.
- Store recordings securely and delete them when no longer needed.
- Never commit camera addresses, usernames, passwords or recordings to a public repository.

## Troubleshooting

- **"Cannot reach the camera"**: check that the IP Webcam server is running, the phone and computer are on the same Wi-Fi, and the IP in `.env` matches the address shown in the app. Phone IPs can change between sessions.
- **Browser works but the program does not**: re-check `CAMERA_URL` ends in `/video` and has no extra spaces.
- **Keys do nothing**: click the video window so it has focus.
- **Recording plays too fast or too slow**: the recording frame rate is taken from the measured FPS when you press R. A very unstable connection can skew it.

## Author

Gideon Kiprono. Built as an individual project in Python Programming, Computer Vision and Networking.