import pytest

from web_app.stream_manager import StreamManager


class FakeProc:
    """Stand-in for subprocess.Popen so start_stream is testable without GStreamer."""
    def __init__(self, pid=999999999):
        self.pid = pid

    def poll(self):
        return None  # still "running"

    def wait(self, timeout=None):
        return 0


def _ready_spawn(log_path, captured):
    def spawn(cmd, **kwargs):
        captured["cmd"] = cmd
        with open(log_path, "w") as f:
            f.write("RTSP_SERVER_READY rtsp://localhost:9000/cam1\n")
        return FakeProc()
    return spawn


def _failed_spawn(log_path):
    def spawn(cmd, **kwargs):
        with open(log_path, "w") as f:
            f.write("RTSP_SERVER_FAILED RTSP port 9000 already in use\n")
        return FakeProc()
    return spawn


class TestStartStreamCustomEndpoint:
    def test_passes_custom_port_and_mount_to_cmd(self, tmp_path):
        log = tmp_path / "rtsp.log"
        captured = {}
        sm = StreamManager(
            spawn=_ready_spawn(str(log), captured),
            free_port=lambda port: None,
            log_path=str(log),
        )
        assert sm.start_stream("file", "/v.mp4", port=9000, mount="/cam1") is True
        cmd = captured["cmd"]
        assert cmd[cmd.index("--port") + 1] == "9000"
        assert cmd[cmd.index("--mount") + 1] == "/cam1"

    def test_status_url_reflects_custom_endpoint(self, tmp_path):
        log = tmp_path / "rtsp.log"
        sm = StreamManager(
            spawn=_ready_spawn(str(log), {}),
            free_port=lambda port: None,
            log_path=str(log),
        )
        sm.start_stream("file", "/v.mp4", port=9000, mount="/cam1")
        assert sm.get_status()["url"] == "rtsp://localhost:9000/cam1"

    def test_status_includes_port_and_mount(self, tmp_path):
        # UI cards need port (for stop/probe routing) and mount (for label).
        log = tmp_path / "rtsp.log"
        sm = StreamManager(
            spawn=_ready_spawn(str(log), {}),
            free_port=lambda port: None,
            log_path=str(log),
        )
        sm.start_stream("file", "/v.mp4", port=9000, mount="/cam1")
        status = sm.get_status()
        assert status["port"] == 9000
        assert status["mount"] == "/cam1"

    def test_defaults_to_8554_stream(self, tmp_path):
        log = tmp_path / "rtsp.log"
        captured = {}
        sm = StreamManager(
            spawn=_ready_spawn(str(log), captured),
            free_port=lambda port: None,
            log_path=str(log),
        )
        sm.start_stream("camera", "/dev/video0")
        cmd = captured["cmd"]
        assert cmd[cmd.index("--port") + 1] == "8554"
        assert cmd[cmd.index("--mount") + 1] == "/stream"

    def test_frees_the_chosen_port(self, tmp_path):
        log = tmp_path / "rtsp.log"
        freed = []
        sm = StreamManager(
            spawn=_ready_spawn(str(log), {}),
            free_port=lambda port: freed.append(port),
            log_path=str(log),
        )
        sm.start_stream("file", "/v.mp4", port=9000, mount="/cam1")
        assert freed == [9000]

    def test_rejects_invalid_port_before_side_effects(self, tmp_path):
        log = tmp_path / "rtsp.log"
        freed = []
        sm = StreamManager(
            spawn=_ready_spawn(str(log), {}),
            free_port=lambda port: freed.append(port),
            log_path=str(log),
        )
        with pytest.raises(ValueError):
            sm.start_stream("file", "/v.mp4", port=99999, mount="/cam1")
        assert freed == []  # validation fails loud BEFORE killing ports


class TestStartStreamFailure:
    def test_failed_sentinel_returns_false_with_error(self, tmp_path):
        log = tmp_path / "rtsp.log"
        sm = StreamManager(
            spawn=_failed_spawn(str(log)),
            free_port=lambda port: None,
            log_path=str(log),
        )
        assert sm.start_stream("file", "/v.mp4", port=9000, mount="/cam1") is False
        status = sm.get_status()
        assert status["active"] is False
        assert "already in use" in status["error"]
