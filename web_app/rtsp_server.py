#!/usr/bin/env python3
import sys
import gi
import argparse
import os

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
            pipeline_str = (
                f'( v4l2src device="{self.source_path}" ! '
                'videoconvert ! '
                'x264enc tune=zerolatency speed-preset=ultrafast ! '
                'rtph264pay name=pay0 pt=96 )'
            )
        elif self.source_type == "network":
            pipeline_str = (
                f'( rtspsrc location="{self.source_path}" latency=0 ! '
                'rtph264depay ! h264parse ! '
                'rtph264pay name=pay0 pt=96 config-interval=1 )'
            )
            
        print(f"Pipeline: {pipeline_str}")
        self.set_launch(pipeline_str)
        self.set_shared(True)

class RTSPServer:
    def __init__(self, source_type, source_path, port=8554, mount_point="/stream"):
        self.source_type = source_type
        self.source_path = source_path
        self.port = port
        self.mount_point = mount_point

        Gst.init(None)

        self.server = GstRtspServer.RTSPServer()
        self.server.set_service(str(self.port))

        mounts = self.server.get_mount_points()
        factory = DynamicRTSPMediaFactory(self.source_type, self.source_path)
        mounts.add_factory(self.mount_point, factory)

        self.server.attach(None)

    def run(self):
        loop = GLib.MainLoop()
        print(f"Stream ready at rtsp://localhost:{self.port}{self.mount_point}")
        try:
            loop.run()
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["file", "camera", "network"], required=True)
    parser.add_argument("--path", required=True)
    parser.add_argument("--port", type=int, default=8554)
    args = parser.parse_args()
    
    server = RTSPServer(args.type, args.path, args.port)
    server.run()
