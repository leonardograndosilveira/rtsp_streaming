import subprocess
import os
import signal
import sys

class StreamManager:
    def __init__(self):
        self.process = None
        self.current_source = None
        self.current_type = None

    def start_stream(self, source_type, source_path):
        self.stop_stream()
        
        script_path = os.path.join(os.path.dirname(__file__), "rtsp_server.py")
        cmd = [sys.executable, script_path, "--type", source_type, "--path", source_path]
        
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid 
        )
        
        self.current_source = source_path
        self.current_type = source_type
        return True

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
                "url": "rtsp://localhost:8554/stream"  # Should match rtsp_server.py default
            }
        return {"active": False}
