"""Pure helpers for building a custom RTSP endpoint (port + mount path).

Kept separate from StreamManager so the URL/port/cmd logic is testable in
isolation without spawning GStreamer. The 'custom URL and port' product
requirement lives here.
"""

DEFAULT_PORT = 8554
DEFAULT_MOUNT = "/stream"
DEFAULT_HOST = "localhost"


def normalize_mount_path(mount):
    """Coerce a user-supplied mount into a clean '/path' form.

    Empty/whitespace -> DEFAULT_MOUNT. Collapses leading slashes and drops a
    trailing slash so 'cam1', '/cam1', '//cam1/' all map to '/cam1'.
    """
    if mount is None:
        return DEFAULT_MOUNT
    cleaned = mount.strip()
    if not cleaned:
        return DEFAULT_MOUNT
    cleaned = "/" + cleaned.lstrip("/")
    cleaned = cleaned.rstrip("/")
    return cleaned or DEFAULT_MOUNT


def validate_port(port):
    """Return port as int in 1..65535, else raise ValueError with context."""
    try:
        value = int(port)
    except (TypeError, ValueError):
        raise ValueError(f"invalid port: received {port!r}, expected int 1-65535")
    if not (1 <= value <= 65535):
        raise ValueError(f"invalid port: received {value}, expected 1-65535")
    return value


def build_rtsp_url(port, mount, host=DEFAULT_HOST):
    """Compose the published RTSP URL, validating port and mount."""
    valid_port = validate_port(port)
    clean_mount = normalize_mount_path(mount)
    return f"rtsp://{host}:{valid_port}{clean_mount}"


def build_rtsp_server_cmd(executable, script, source_type, source_path, port, mount):
    """Build the argv for the rtsp_server.py child, including --port/--mount."""
    valid_port = validate_port(port)
    clean_mount = normalize_mount_path(mount)
    return [
        executable, script,
        "--type", source_type,
        "--path", source_path,
        "--port", str(valid_port),
        "--mount", clean_mount,
    ]
