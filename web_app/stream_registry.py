"""Holds many concurrent RTSP streams at once, keyed by port.

Each stream is an independent StreamManager (own child process, own port,
own mount, own log file). Port is the natural unique key: two RTSP servers
cannot bind the same port, so we reject a duplicate before touching anything.
"""
import os

from .stream_manager import StreamManager, RTSP_LOG_DIR
from .rtsp_endpoint import validate_port


class PortBusyError(Exception):
    """Raised when a start targets a port that already has a live stream."""


def _default_manager(log_path):
    return StreamManager(log_path=log_path)


class StreamRegistry:
    # make_manager injected so registry logic is testable without GStreamer.
    def __init__(self, make_manager=None, log_dir=RTSP_LOG_DIR):
        self._streams = {}
        self._make_manager = make_manager or _default_manager
        self._log_dir = log_dir

    def start(self, source_type, source_path, port, mount):
        port_i = validate_port(port)
        self._prune()
        # Check dup BEFORE building a manager -- a duplicate must never run
        # free_port() and kill the stream already serving on that port.
        if port_i in self._streams:
            raise PortBusyError(f"port {port_i} already streaming; stop it first")

        manager = self._make_manager(self._log_path(port_i))
        if not manager.start_stream(source_type, source_path, port_i, mount):
            raise RuntimeError(manager.last_error or "stream failed to start")
        self._streams[port_i] = manager
        return manager.get_status()

    def stop(self, port):
        manager = self._streams.pop(validate_port(port), None)
        if not manager:
            return False
        manager.stop_stream()
        return True

    def stop_all(self):
        count = len(self._streams)
        for manager in list(self._streams.values()):
            manager.stop_stream()
        self._streams.clear()
        return count

    def list(self):
        self._prune()
        return [m.get_status() for m in self._streams.values()]

    def get(self, port):
        manager = self._streams.get(validate_port(port))
        return manager.get_status() if manager else None

    def _prune(self):
        # Drop streams whose child died so their port frees up for reuse.
        dead = [p for p, m in self._streams.items() if not m.get_status().get("active")]
        for port in dead:
            self._streams.pop(port, None)

    def _log_path(self, port):
        return os.path.join(self._log_dir, f"rtsp_server_{port}.log")
