from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import shutil
import os
import glob
import json
import subprocess
from .camera_manager import CameraManager
from .stream_registry import StreamRegistry, PortBusyError
from .upload_guard import sanitize_upload_filename

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# One registry holds every concurrent stream, keyed by port.
stream_registry = StreamRegistry()
os.makedirs(UPLOAD_DIR, exist_ok=True)

# NOTE: handlers that shell out (start/stop/probe/snapshot) are plain `def`,
# NOT `async def`. They call blocking subprocess.run(); a blocking call inside
# an async handler freezes uvicorn's whole event loop (an 8s ffmpeg snapshot
# would stall every other request, including starting a new stream). FastAPI
# runs sync `def` handlers in a threadpool, keeping concurrent streams responsive.


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/cameras")
async def get_cameras():
    return CameraManager.get_available_cameras()


@app.get("/api/files")
async def get_files():
    files = glob.glob(os.path.join(UPLOAD_DIR, "*"))
    return [
        {"name": os.path.basename(f), "path": os.path.abspath(f)}
        for f in files if f.lower().endswith(('.mp4', '.mkv', '.avi', '.mov'))
    ]


@app.post("/api/upload")
def upload_file(file: UploadFile = File(...)):
    # Reduce attacker-controlled filename to a safe basename (no path traversal).
    try:
        safe_name = sanitize_upload_filename(file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"filename": safe_name, "path": os.path.abspath(file_path)}


@app.post("/api/streams/start")
def start_stream(data: dict):
    source_type = data.get("type")
    source_path = data.get("path")
    port = data.get("port", 8554)
    mount = data.get("mount", "/stream")

    if not source_type or not source_path:
        raise HTTPException(status_code=400, detail="Missing type or path")

    try:
        return stream_registry.start(source_type, source_path, port, mount)
    except PortBusyError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/streams")
async def list_streams():
    return stream_registry.list()


@app.post("/api/streams/stop_all")
def stop_all_streams():
    return {"stopped": stream_registry.stop_all()}


@app.post("/api/streams/{port}/stop")
def stop_stream(port: int):
    if stream_registry.stop(port):
        return {"stopped": True, "port": port}
    raise HTTPException(status_code=404, detail=f"no active stream on port {port}")


def _active_stream_url(port: int) -> str:
    status = stream_registry.get(port)
    if not status or not status.get("active"):
        raise HTTPException(status_code=404, detail=f"no active stream on port {port}")
    return status["url"]


@app.get("/api/streams/{port}/probe")
def probe_stream(port: int):
    rtsp_url = _active_stream_url(port)

    # Honest probe: no simulated fallback. If ffprobe can't read the stream,
    # the source is genuinely not working and we must report that.
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "stream=width,height,codec_name,bit_rate",
        "-of", "json",
        rtsp_url,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Probe timed out: no frames from source within 8s"}
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="ffprobe not installed on server")

    if result.returncode != 0:
        return {"success": False, "error": result.stderr.strip() or "ffprobe failed to read stream"}

    probe_data = json.loads(result.stdout)
    streams = probe_data.get("streams", [])
    if not streams:
        return {"success": False, "error": "No video stream found in source"}

    s = streams[0]
    return {
        "success": True,
        "resolution": f"{s.get('width')}x{s.get('height')}",
        "codec": s.get("codec_name"),
        "bitrate": s.get("bit_rate"),
    }


@app.get("/api/streams/{port}/snapshot")
def snapshot_stream(port: int):
    rtsp_url = _active_stream_url(port)

    # Grab a single live JPEG frame. Real frame == source is truly working.
    # -rtsp_transport tcp avoids UDP packet loss on localhost relay.
    cmd = [
        "ffmpeg",
        "-rtsp_transport", "tcp",
        "-i", rtsp_url,
        "-frames:v", "1",
        "-q:v", "4",
        "-f", "image2",
        "pipe:1",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=8)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Snapshot timed out: source produced no frame")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="ffmpeg not installed on server")

    if result.returncode != 0 or not result.stdout:
        detail = result.stderr.decode(errors="ignore").strip()[-300:] or "ffmpeg produced no frame"
        raise HTTPException(status_code=502, detail=detail)

    return Response(content=result.stdout, media_type="image/jpeg")
