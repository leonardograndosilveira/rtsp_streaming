import pytest

from web_app.stream_registry import StreamRegistry, PortBusyError


class FakeManager:
    """Stand-in for StreamManager so registry logic is testable without GStreamer."""
    def __init__(self, log_path=None):
        self.log_path = log_path
        self.started = None
        self.stop_called = 0
        self.fail_start = False
        self.last_error = None
        self._active = False
        self._port = None
        self._mount = None

    def start_stream(self, source_type, source_path, port, mount):
        self.started = (source_type, source_path, port, mount)
        if self.fail_start:
            self.last_error = "boom"
            return False
        self._active = True
        self._port = port
        self._mount = mount
        return True

    def stop_stream(self):
        self.stop_called += 1
        self._active = False
        return True

    def die(self):
        # Simulate the child process crashing after a healthy start.
        self._active = False

    def get_status(self):
        if self._active:
            return {
                "active": True,
                "url": f"rtsp://localhost:{self._port}{self._mount}",
                "type": "file",
                "source": "x",
            }
        return {"active": False}


def make_factory(fail=False):
    created = []

    def factory(log_path):
        m = FakeManager(log_path)
        m.fail_start = fail
        created.append(m)
        return m

    factory.created = created
    return factory


class TestStart:
    def test_returns_status_with_url(self):
        reg = StreamRegistry(make_manager=make_factory())
        status = reg.start("file", "/v.mp4", 9000, "/cam1")
        assert status["active"] is True
        assert status["url"] == "rtsp://localhost:9000/cam1"

    def test_two_ports_both_listed(self):
        reg = StreamRegistry(make_manager=make_factory())
        reg.start("file", "/a.mp4", 9000, "/a")
        reg.start("file", "/b.mp4", 9001, "/b")
        urls = {s["url"] for s in reg.list()}
        assert urls == {"rtsp://localhost:9000/a", "rtsp://localhost:9001/b"}

    def test_duplicate_port_raises(self):
        reg = StreamRegistry(make_manager=make_factory())
        reg.start("file", "/a.mp4", 9000, "/a")
        with pytest.raises(PortBusyError, match="9000"):
            reg.start("file", "/b.mp4", 9000, "/b")

    def test_duplicate_port_does_not_create_or_kill(self):
        factory = make_factory()
        reg = StreamRegistry(make_manager=factory)
        reg.start("file", "/a.mp4", 9000, "/a")
        with pytest.raises(PortBusyError):
            reg.start("file", "/b.mp4", 9000, "/b")
        # No second manager built, original never stopped.
        assert len(factory.created) == 1
        assert factory.created[0].stop_called == 0
        assert reg.list()[0]["url"] == "rtsp://localhost:9000/a"

    def test_failed_start_raises_and_not_stored(self):
        reg = StreamRegistry(make_manager=make_factory(fail=True))
        with pytest.raises(RuntimeError, match="boom"):
            reg.start("file", "/a.mp4", 9000, "/a")
        assert reg.list() == []

    def test_rejects_invalid_port(self):
        reg = StreamRegistry(make_manager=make_factory())
        with pytest.raises(ValueError):
            reg.start("file", "/a.mp4", 99999, "/a")

    def test_each_manager_gets_unique_log_path(self):
        factory = make_factory()
        reg = StreamRegistry(make_manager=factory, log_dir="/tmp/x")
        reg.start("file", "/a.mp4", 9000, "/a")
        reg.start("file", "/b.mp4", 9001, "/b")
        paths = {m.log_path for m in factory.created}
        assert paths == {"/tmp/x/rtsp_server_9000.log", "/tmp/x/rtsp_server_9001.log"}


class TestStop:
    def test_stop_removes_and_returns_true(self):
        factory = make_factory()
        reg = StreamRegistry(make_manager=factory)
        reg.start("file", "/a.mp4", 9000, "/a")
        assert reg.stop(9000) is True
        assert factory.created[0].stop_called == 1
        assert reg.list() == []

    def test_stop_unknown_returns_false(self):
        reg = StreamRegistry(make_manager=make_factory())
        assert reg.stop(9999) is False

    def test_stop_all_stops_each_and_clears(self):
        factory = make_factory()
        reg = StreamRegistry(make_manager=factory)
        reg.start("file", "/a.mp4", 9000, "/a")
        reg.start("file", "/b.mp4", 9001, "/b")
        assert reg.stop_all() == 2
        assert all(m.stop_called == 1 for m in factory.created)
        assert reg.list() == []


class TestListPruning:
    def test_list_prunes_dead_stream(self):
        factory = make_factory()
        reg = StreamRegistry(make_manager=factory)
        reg.start("file", "/a.mp4", 9000, "/a")
        reg.start("file", "/b.mp4", 9001, "/b")
        factory.created[0].die()  # 9000 crashes
        urls = {s["url"] for s in reg.list()}
        assert urls == {"rtsp://localhost:9001/b"}

    def test_dead_port_is_reusable(self):
        factory = make_factory()
        reg = StreamRegistry(make_manager=factory)
        reg.start("file", "/a.mp4", 9000, "/a")
        factory.created[0].die()
        # Port 9000 free again after death -> can restart there.
        status = reg.start("file", "/a2.mp4", 9000, "/a2")
        assert status["url"] == "rtsp://localhost:9000/a2"


class TestGet:
    def test_get_returns_status(self):
        reg = StreamRegistry(make_manager=make_factory())
        reg.start("file", "/a.mp4", 9000, "/a")
        assert reg.get(9000)["url"] == "rtsp://localhost:9000/a"

    def test_get_unknown_returns_none(self):
        reg = StreamRegistry(make_manager=make_factory())
        assert reg.get(9000) is None
