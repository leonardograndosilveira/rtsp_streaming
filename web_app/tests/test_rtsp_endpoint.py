import pytest

from web_app.rtsp_endpoint import (
    normalize_mount_path,
    validate_port,
    build_rtsp_url,
    build_rtsp_server_cmd,
)


class TestNormalizeMountPath:
    def test_default_when_none(self):
        assert normalize_mount_path(None) == "/stream"

    def test_default_when_empty(self):
        assert normalize_mount_path("") == "/stream"

    def test_default_when_whitespace(self):
        assert normalize_mount_path("   ") == "/stream"

    def test_adds_leading_slash(self):
        assert normalize_mount_path("cam1") == "/cam1"

    def test_keeps_leading_slash(self):
        assert normalize_mount_path("/cam1") == "/cam1"

    def test_strips_trailing_slash(self):
        assert normalize_mount_path("/cam1/") == "/cam1"

    def test_collapses_duplicate_leading_slashes(self):
        assert normalize_mount_path("//cam1") == "/cam1"

    def test_strips_surrounding_whitespace(self):
        assert normalize_mount_path("  /cam1  ") == "/cam1"


class TestValidatePort:
    def test_accepts_int(self):
        assert validate_port(8554) == 8554

    def test_accepts_numeric_string(self):
        assert validate_port("8554") == 8554

    def test_rejects_zero(self):
        with pytest.raises(ValueError):
            validate_port(0)

    def test_rejects_above_range(self):
        with pytest.raises(ValueError):
            validate_port(70000)

    def test_rejects_negative(self):
        with pytest.raises(ValueError):
            validate_port(-1)

    def test_rejects_non_numeric(self):
        with pytest.raises(ValueError):
            validate_port("abc")

    def test_rejects_none(self):
        with pytest.raises(ValueError):
            validate_port(None)

    def test_error_has_context(self):
        # Fail loud with the offending value in the message.
        with pytest.raises(ValueError, match="70000"):
            validate_port(70000)


class TestBuildRtspUrl:
    def test_basic(self):
        assert build_rtsp_url(8554, "/stream") == "rtsp://localhost:8554/stream"

    def test_custom_port_and_mount(self):
        assert build_rtsp_url(9000, "/cam1") == "rtsp://localhost:9000/cam1"

    def test_normalizes_mount(self):
        assert build_rtsp_url(9000, "cam1") == "rtsp://localhost:9000/cam1"

    def test_validates_port(self):
        with pytest.raises(ValueError):
            build_rtsp_url(99999, "/stream")

    def test_custom_host(self):
        assert build_rtsp_url(8554, "/s", host="0.0.0.0") == "rtsp://0.0.0.0:8554/s"


class TestBuildRtspServerCmd:
    def test_includes_all_args(self):
        cmd = build_rtsp_server_cmd(
            "python", "rtsp_server.py", "file", "/v.mp4", 9000, "/cam1"
        )
        assert cmd == [
            "python", "rtsp_server.py",
            "--type", "file",
            "--path", "/v.mp4",
            "--port", "9000",
            "--mount", "/cam1",
        ]

    def test_normalizes_mount_in_cmd(self):
        cmd = build_rtsp_server_cmd(
            "python", "rtsp_server.py", "file", "/v.mp4", 9000, "cam1"
        )
        assert "--mount" in cmd
        assert cmd[cmd.index("--mount") + 1] == "/cam1"
