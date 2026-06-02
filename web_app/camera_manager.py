import glob
import os

class CameraManager:
    @staticmethod
    def get_available_cameras():
        """
        Detects available video devices (webcams) on Linux.
        Returns a list of dictionaries with 'id' and 'name'.
        """
        devices = glob.glob('/dev/video*')
        cameras = []
        
        for device in sorted(devices):
            if os.access(device, os.R_OK):
                cameras.append({
                    "id": device,
                    "name": f"Camera ({device})"
                })
        
        return cameras
