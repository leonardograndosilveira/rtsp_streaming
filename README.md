# RTSP Streaming Server & Web Manager

A simple RTSP server with a modern "Ops Center" web interface for managing video streams. Supports both file-based sources and live webcam feeds.

## Features

- **Web Interface**: Professional "Ops Center" dashboard (Dark Mode, HUD style).
- **Source Selection**: Switch between Video Files and Live Webcam.
- **File Upload**: Upload new video files directly from the browser.
- **RTSP Server**: Low-latency H.264 streaming using GStreamer.
- **REST API**: Control the stream programmatically via FastAPI.

## Prerequisites

- Python 3.6+
- GStreamer 1.0 (with RTSP server and Python bindings)
  - Ubuntu: `sudo apt-get install python3-gi gir1.2-gst-rtsp-server-1.0 gstreamer1.0-plugins-ugly gstreamer1.0-plugins-bad gstreamer1.0-libav`

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
   - Use the provided RTSP URL in VLC or any RTSP player.

## Directory Structure

- `web_app/`: Main application code.
  - `main.py`: FastAPI backend.
  - `rtsp_server.py`: Standalone GStreamer RTSP server process.
  - `templates/`: HTML frontend (Ops Center design).
  - `static/`: CSS and JS assets.

## API Endpoints

- `GET /api/cameras`: List available webcams.
- `GET /api/files`: List uploaded video files.
- `POST /api/upload`: Upload a video file.
- `POST /api/stream/start`: Start RTSP stream.
- `POST /api/stream/stop`: Stop RTSP stream.
