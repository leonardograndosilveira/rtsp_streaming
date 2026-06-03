import subprocess
import os
import signal
import sys
import time

from .rtsp_endpoint import (
    build_rtsp_url,
    build_rtsp_server_cmd,
    validate_port,
    normalize_mount_path,
    DEFAULT_PORT,
    DEFAULT_MOUNT,
    DEFAULT_HOST,
)

# Where rtsp_server.py child output is captured. Errors used to go to a PIPE
# that nobody read -- that both hid failures and risked deadlocking the child
# when the pipe buffer filled. A file we can tail is simpler and honest.
# Multiple concurrent streams each get their own log file (rtsp_server_<port>.log)
# under RTSP_LOG_DIR so their output never collides.
RTSP_LOG_DIR = os.path.dirname(__file__)
RTSP_LOG_PATH = os.path.join(RTSP_LOG_DIR, "rtsp_server.log")

READY_SENTINEL = "RTSP_SERVER_READY"
FAILED_SENTINEL = "RTSP_SERVER_FAILED"
READY_TIMEOUT_S = 6.0


def free_rtsp_port(port=DEFAULT_PORT):
    """Kill any foreign process squatting the RTSP port before we bind it.

    fuser -k is preferred; falls back to lsof on systems without psmisc.
    Sleeps briefly so the OS releases the socket before our child tries to bind.
    Takes the *chosen* port so custom-port streams free the right socket.
    """
    try:
        subprocess.run(
            ["fuser", "-k", f"{port}/tcp"],
            timeout=3,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        # fuser not available; try lsof
        try:
            result = subprocess.run(
                ["lsof", "-t", f"-i:{port}"],
                capture_output=True, text=True, timeout=3,
            )
            for pid in result.stdout.split():
                os.kill(int(pid), signal.SIGTERM)
        except (FileNotFoundError, ValueError, ProcessLookupError):
            pass
    except subprocess.TimeoutExpired:
        pass
    time.sleep(0.3)


class StreamManager:
    # Dependencies injected so start_stream is testable without GStreamer:
    # spawn (process launcher) and free_port (port reclaimer) are swappable.
    def __init__(self, host=DEFAULT_HOST, spawn=subprocess.Popen,
                 free_port=free_rtsp_port, log_path=RTSP_LOG_PATH,
                 ready_timeout_s=READY_TIMEOUT_S):
        self.host = host
        self.spawn = spawn
        self.free_port = free_port
        self.log_path = log_path
        self.ready_timeout_s = ready_timeout_s

        self.process = None
        self.current_source = None
        self.current_type = None
        self.current_port = None
        self.current_mount = None
        self.rtsp_url = build_rtsp_url(DEFAULT_PORT, DEFAULT_MOUNT, host)
        self.last_error = None

    def start_stream(self, source_type, source_path, port=DEFAULT_PORT, mount=DEFAULT_MOUNT):
        # Validate BEFORE any side effect so a bad port fails loud without
        # killing whatever is currently bound to a port we never use.
        url = build_rtsp_url(port, mount, self.host)
        port = validate_port(port)
        mount = normalize_mount_path(mount)

        self.stop_stream()
        self.free_port(port)
        self.last_error = None

        script_path = os.path.join(os.path.dirname(__file__), "rtsp_server.py")
        cmd = build_rtsp_server_cmd(
            sys.executable, script_path, source_type, source_path, port, mount
        )

        log = open(self.log_path, "wb")
        self.process = self.spawn(
            cmd, stdout=log, stderr=subprocess.STDOUT, preexec_fn=os.setsid
        )
        self.current_source = source_path
        self.current_type = source_type
        self.current_port = port
        self.current_mount = mount
        self.rtsp_url = url

        # Only report success once the child confirms it actually bound the
        # RTSP port -- a live PID alone does not mean the stream is serving.
        if self._await_ready():
            return True

        self.stop_stream()
        return False

    def _await_ready(self):
        deadline = time.monotonic() + self.ready_timeout_s
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.last_error = self._log_tail() or "RTSP server exited on startup"
                return False
            log = self._read_log()
            if READY_SENTINEL in log:
                return True
            if FAILED_SENTINEL in log:
                self.last_error = self._log_tail()
                return False
            time.sleep(0.2)
        self.last_error = "RTSP server did not become ready within timeout"
        return False

    def _read_log(self):
        try:
            with open(self.log_path, "r", errors="ignore") as f:
                return f.read()
        except OSError:
            return ""

    def _log_tail(self, n=400):
        return self._read_log().strip()[-n:]

    def stop_stream(self):
        if self.process:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process.wait(timeout=2)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                pass
            self.process = None
            self.current_source = None
            self.current_type = None
            return True
        return False

    def get_status(self):
        if self.process and self.process.poll() is None:
            return {
                "active": True,
                "type": self.current_type,
                "source": self.current_source,
                "port": self.current_port,
                "mount": self.current_mount,
                "url": self.rtsp_url,
            }
        status = {"active": False}
        if self.last_error:
            status["error"] = self.last_error
        return status
