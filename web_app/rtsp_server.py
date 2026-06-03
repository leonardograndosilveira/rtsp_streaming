#!/usr/bin/env python3
import sys
import gi
import argparse
import os
import socket

try:
    gi.require_version('Gst', '1.0')
    gi.require_version('GstRtspServer', '1.0')
except ValueError as e:
    print(f"Error: Missing GStreamer dependencies. {e}")
    sys.exit(1)

from gi.repository import Gst, GstRtspServer, GLib

class DynamicRTSPMediaFactory(GstRtspServer.RTSPMediaFactory):
    def __init__(self, source_type, source_path):
        super().__init__()
        self.source_type = source_type
        self.source_path = source_path
        
        pipeline_str = ""
        if self.source_type == "file":
             pipeline_str = (
                f'( filesrc location="{self.source_path}" ! '
                'qtdemux name=demux demux.video_0 ! queue ! h264parse ! '
                'rtph264pay name=pay0 pt=96 config-interval=1 )'
            )
        elif self.source_type == "camera":
            # Using v4l2src for webcam
            # encoding to h264 for RTSP
            # config-interval=1 resends SPS/PPS every second so RTSP clients
            # that join mid-stream can decode instead of showing a grey frame.
            pipeline_str = (
                f'( v4l2src device="{self.source_path}" ! '
                'videoconvert ! '
                'x264enc tune=zerolatency speed-preset=ultrafast ! '
                'rtph264pay name=pay0 pt=96 config-interval=1 )'
            )
        elif self.source_type == "network":
            # decodebin (not rtph264depay) so non-H264 cameras work too:
            # H.265/MJPEG/MPEG4 sources get decoded then re-encoded to H.264.
            # latency=200 gives the jitter buffer room; latency=0 dropped frames
            # on real networks. We re-encode, so the upstream codec is irrelevant.
            pipeline_str = (
                f'( rtspsrc location="{self.source_path}" latency=200 ! '
                'decodebin ! videoconvert ! '
                'x264enc tune=zerolatency speed-preset=ultrafast ! '
                'rtph264pay name=pay0 pt=96 config-interval=1 )'
            )
            
        print(f"Pipeline: {pipeline_str}", flush=True)
        self.set_launch(pipeline_str)
        self.set_shared(True)
        # Surface pipeline errors loudly. Without this, a failed media
        # (bad codec, unreadable source) silently makes the server answer
        # RTSP clients with 400 Bad Request and we never learn why.
        self.connect("media-configure", self._on_media_configure)

    def _on_media_configure(self, factory, media):
        element = media.get_element()
        bus = element.get_bus()
        bus.add_signal_watch()
        bus.connect("message::error", self._on_pipeline_error)

    def _on_pipeline_error(self, bus, message):
        err, debug = message.parse_error()
        print(f"PIPELINE_ERROR: {err.message} | {debug}", file=sys.stderr, flush=True)

def assert_port_free(port):
    """Fail loud if the RTSP port is already taken.

    GstRtspServer binds with SO_REUSEADDR, so a stale/foreign server on the
    same port does NOT raise here -- instead clients silently hit the old,
    broken listener and get '400 Bad Request'. We pre-check with a plain
    socket (no reuse) to turn that silent failure into an explicit one.
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind(("0.0.0.0", port))
    except OSError as e:
        raise RuntimeError(
            f"RTSP port {port} already in use ({e.strerror}). "
            f"A stale stream server is likely squatting it; kill it first."
        ) from e
    finally:
        probe.close()


class RTSPServer:
    def __init__(self, source_type, source_path, port=8554, mount_point="/stream"):
        self.source_type = source_type
        self.source_path = source_path
        self.port = port
        self.mount_point = mount_point

        assert_port_free(port)
        Gst.init(None)

        self.server = GstRtspServer.RTSPServer()
        self.server.set_service(str(self.port))

        mounts = self.server.get_mount_points()
        factory = DynamicRTSPMediaFactory(self.source_type, self.source_path)
        mounts.add_factory(self.mount_point, factory)

        if self.server.attach(None) == 0:
            raise RuntimeError(f"Failed to attach RTSP server on port {port}")

    def run(self):
        loop = GLib.MainLoop()
        # Sentinel line the parent (StreamManager) waits for to confirm the
        # server actually came up, instead of assuming success from a live PID.
        print(f"RTSP_SERVER_READY rtsp://localhost:{self.port}{self.mount_point}", flush=True)
        try:
            loop.run()
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["file", "camera", "network"], required=True)
    parser.add_argument("--path", required=True)
    parser.add_argument("--port", type=int, default=8554)
    parser.add_argument("--mount", default="/stream")
    args = parser.parse_args()

    try:
        server = RTSPServer(args.type, args.path, args.port, args.mount)
    except RuntimeError as e:
        print(f"RTSP_SERVER_FAILED {e}", file=sys.stderr, flush=True)
        sys.exit(1)
    server.run()
