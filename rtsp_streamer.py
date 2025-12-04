#!/usr/bin/env python3
import sys
import argparse
import os
import gi

# Required for GStreamer
try:
    gi.require_version('Gst', '1.0')
    gi.require_version('GstRtspServer', '1.0')
except ValueError as e:
    print(f"Error: Missing GStreamer dependencies. {e}")
    print("Please install: gir1.2-gst-rtsp-server-1.0")
    sys.exit(1)
from gi.repository import Gst, GstRtspServer, GLib


class LoopingRTSPMediaFactory(GstRtspServer.RTSPMediaFactory):
    """Custom media factory that creates looping media."""
    
    def __init__(self, source_file):
        super().__init__()
        self.source_file = source_file
        # Pipeline: Read file -> Parse H.264 -> RTP Payload (passthrough, no re-encoding)
        pipeline_str = (
            f'( filesrc location="{self.source_file}" ! '
            'qtdemux name=demux demux.video_0 ! queue ! h264parse ! '
            'rtph264pay name=pay0 pt=96 )'
        )
        print(f"Pipeline: {pipeline_str}")
        self.set_launch(pipeline_str)
        self.set_shared(True)
    
    def do_media_configure(self, media):
        """Called when media is configured. Add EOS handler for looping."""
        pipeline = media.get_element()
        
        # Find the pay0 element and add a pad probe to intercept EOS
        pay0 = pipeline.get_by_name('pay0')
        if pay0:
            srcpad = pay0.get_static_pad('src')
            if srcpad:
                srcpad.add_probe(
                    Gst.PadProbeType.EVENT_DOWNSTREAM,
                    self._pad_probe_callback,
                    pipeline
                )
    
    def _pad_probe_callback(self, pad, info, pipeline):
        """Pad probe callback to intercept EOS and seek back to start."""
        event = info.get_event()
        if event.type == Gst.EventType.EOS:
            print("End of stream detected, looping...")
            # Schedule seek in main context to avoid deadlock
            GLib.idle_add(self._do_seek, pipeline)
            # Drop the EOS event so it doesn't reach the client
            return Gst.PadProbeReturn.DROP
        return Gst.PadProbeReturn.OK
    
    def _do_seek(self, pipeline):
        """Perform seek back to the beginning."""
        pipeline.seek_simple(
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
            0
        )
        return False  # Don't repeat


class RTSPServer:
    def __init__(self, source_file, port=8777, mount_point="/stream", user="admin", password="admin"):
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
        token.set_string('media.factory.role', user)
        basic = GstRtspServer.RTSPAuth.make_basic(user, password)
        auth.add_basic(basic, token)
        self.server.set_auth(auth)

        # Mount Point
        mounts = self.server.get_mount_points()
        
        # Create looping media factory
        factory = LoopingRTSPMediaFactory(self.source_file)
        
        # Set permissions (only authenticated user can access)
        permissions = GstRtspServer.RTSPPermissions()
        permissions.add_permission_for_role(user, 'media.factory.access', True)
        permissions.add_permission_for_role(user, 'media.factory.construct', True)
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
    args = parser.parse_args()

    if not os.path.exists(args.source):
        print(f"Error: Source file not found: {args.source}")
        sys.exit(1)

    server = RTSPServer(args.source)
    server.run()


if __name__ == "__main__":
    main()
