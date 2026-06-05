# RTSP Streaming Server & Web Manager

A multi-stream RTSP server with a modern "Ops Center" web interface for managing video streams. Supports file-based sources and live webcam feeds, runs many streams at once, and advertises both LAN and Tailscale (VPN) RTSP URLs for remote access.

## Features

- **Web Interface**: Professional "Ops Center" dashboard (Dark Mode, HUD style).
- **Multi-Stream Registry**: Run multiple RTSP streams concurrently, each on its own port/mount.
- **Source Selection**: Switch between Video Files and Live Webcam.
- **File Upload**: Upload new video files directly from the browser.
- **Tailscale / VPN URLs**: Auto-detects the host Tailscale IP and publishes a remote-access `rtsp://` URL alongside the LAN URL. Header badge shows VPN connection status.
- **RTSP Server**: Low-latency H.264 streaming using GStreamer.
- **Stream Probe & Snapshot**: Test a live stream and grab a still frame per port.
- **REST API**: Control streams programmatically via FastAPI.

## Prerequisites

- Python 3.10+ (uses `str | None` type syntax)
- GStreamer 1.0 (with RTSP server and Python bindings)
  - Ubuntu: `sudo apt-get install python3-gi gir1.2-gst-rtsp-server-1.0 gstreamer1.0-plugins-ugly gstreamer1.0-plugins-bad gstreamer1.0-libav`
- *(Optional)* [Tailscale](https://tailscale.com/) for VPN URL advertisement. Without it, VPN status shows `OFFLINE` and only LAN URLs are published.

## Installation

1. **Clone the repository** (if not already done).
2. **Setup Virtual Environment**:
   ```bash
   # Create venv with access to system packages (for gi)
   python3 -m venv --system-site-packages venv

   # Install dependencies
   ./venv/bin/pip install fastapi uvicorn python-multipart jinja2
   ```

## Usage

1. **Start the Web Server**:
   ```bash
   ./venv/bin/uvicorn web_app.main:app --host 0.0.0.0 --port 8000
   ```

2. **Access the Dashboard**:
   Open `http://localhost:8000` in your browser.

3. **Stream**:
   - Select a Camera or File.
   - Click "INITIATE STREAM".
   - Copy the **LOCAL** (LAN) or **VPN** (Tailscale) RTSP URL into VLC or any RTSP player.

## Directory Structure

- `web_app/`: Main application code.
  - `main.py`: FastAPI backend and route definitions.
  - `stream_registry.py`: Multi-stream registry (start/stop/list active streams).
  - `stream_manager.py`: Single-stream lifecycle and GStreamer process control.
  - `rtsp_server.py`: Standalone GStreamer RTSP server process.
  - `rtsp_endpoint.py`: Builds `rtsp://host:port/mount` URLs.
  - `network_info.py`: Detects Tailscale and LAN IPs for URL advertisement.
  - `camera_manager.py`: Webcam device detection.
  - `upload_guard.py`: Validates uploaded files.
  - `templates/`: HTML frontend (Ops Center design).
  - `static/`: CSS and JS assets.

## API Endpoints

- `GET /api/cameras`: List available webcams.
- `GET /api/files`: List uploaded video files.
- `POST /api/upload`: Upload a video file.
- `GET /api/network/info`: Report LAN IP, Tailscale IP, and VPN connection status.
- `POST /api/streams/start`: Start an RTSP stream (returns LAN + VPN URLs).
- `GET /api/streams`: List active streams (with LAN + VPN URLs).
- `POST /api/streams/stop_all`: Stop all active streams.
- `POST /api/streams/{port}/stop`: Stop the stream on a given port.
- `GET /api/streams/{port}/probe`: Test/probe the stream on a given port.
- `GET /api/streams/{port}/snapshot`: Grab a still frame from the stream on a given port.
