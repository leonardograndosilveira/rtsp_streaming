"""Detect host network addresses for stream URL advertisement.

Tailscale IP is the primary external address; LAN IP is fallback for local
viewers. Both are exposed via /api/network/info so the UI can display the
correct RTSP URL to copy for remote access.
"""
import subprocess
import socket


def get_tailscale_ip() -> str | None:
    """Return Tailscale IPv4 via `tailscale ip -4`, or None if unavailable."""
    try:
        result = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            ip = result.stdout.strip()
            if ip:
                return ip
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def get_local_ip() -> str:
    """Best-effort LAN IPv4 (not loopback). Falls back to 127.0.0.1."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
