#!/usr/bin/env python3
import sys
import argparse
import os
import gi

# Required for GStreamer
try:
    gi.require_version("Gst", "1.0")
    gi.require_version("GstRtspServer", "1.0")
except ValueError as e:
    print(f"Error: Missing GStreamer dependencies. {e}")
    print("Please install: gir1.2-gst-rtsp-server-1.0")
    sys.exit(1)
from gi.repository import Gst, GstRtspServer, GLib


class SimpleRTSPMediaFactory(GstRtspServer.RTSPMediaFactory):
    """Simple RTSP media factory with passthrough H264 and looping."""

    def __init__(self, source_file):
        super().__init__()
        self.source_file = source_file
        # Robust looping pipeline: decode -> re-encode -> pay
        # This ensures continuous timestamps and valid headers
        pipeline_str = (
            f'( multifilesrc location="{self.source_file}" loop=true ! '
            "qtdemux ! h264parse ! avdec_h264 ! videoconvert ! "
            "x264enc tune=zerolatency speed-preset=ultrafast key-int-max=30 ! "
            "rtph264pay name=pay0 pt=96 config-interval=1 )"
        )
        print(f"Pipeline: {pipeline_str}")
        self.set_launch(pipeline_str)
        self.set_shared(True)


class RTSPServer:
    def __init__(
        self,
        source_file,
        port=8777,
        mount_point="/stream",
        user="admin",
        password="admin",
    ):
        self.source_file = source_file
        self.port = port
        self.mount_point = mount_point
        self.user = user
        self.password = password

        # Initialize GStreamer
        Gst.init(None)

        # Create Server
        self.server = GstRtspServer.RTSPServer()
        self.server.set_service(str(self.port))

        # Authentication
        auth = GstRtspServer.RTSPAuth()
        token = GstRtspServer.RTSPToken()
        token.set_string("media.factory.role", user)
        basic = GstRtspServer.RTSPAuth.make_basic(user, password)
        auth.add_basic(basic, token)
        self.server.set_auth(auth)

        # Mount Point
        mounts = self.server.get_mount_points()

        # Create simple media factory (uses multifilesrc for stable looping)
        factory = SimpleRTSPMediaFactory(self.source_file)

        # Set permissions (only authenticated user can access)
        permissions = GstRtspServer.RTSPPermissions()
        permissions.add_permission_for_role(user, "media.factory.access", True)
        permissions.add_permission_for_role(user, "media.factory.construct", True)
        factory.set_permissions(permissions)

        mounts.add_factory(self.mount_point, factory)

        # Attach to main loop
        self.server.attach(None)

    def run(self):
        loop = GLib.MainLoop()
        url = f"rtsp://{self.user}:{self.password}@localhost:{self.port}{self.mount_point}"
        print(f"Stream ready at: {url}")
        print("Video will loop continuously.")
        try:
            loop.run()
        except KeyboardInterrupt:
            print("\nStopping server...")


def main():
    parser = argparse.ArgumentParser(description="RTSP Streamer CLI")
    parser.add_argument("--source", required=True, help="Path to the video file source")
    parser.add_argument(
        "--port", type=int, default=8777, help="RTSP port (default: 8777)"
    )
    args = parser.parse_args()

    if not os.path.exists(args.source):
        print(f"Error: Source file not found: {args.source}")
        sys.exit(1)

    server = RTSPServer(args.source, port=args.port)
    server.run()


if __name__ == "__main__":
    main()
