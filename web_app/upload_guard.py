"""Upload filename hardening.

A browser-supplied filename is attacker-controlled. Writing it straight into
UPLOAD_DIR lets '../../etc/x' escape the directory (path traversal). We reduce
to a bare basename and reject anything that resolves to nothing useful.
"""
import os


def sanitize_upload_filename(filename):
    """Return a safe basename, or raise ValueError if nothing usable remains."""
    if not filename or not filename.strip():
        raise ValueError(f"invalid upload filename: received {filename!r}, expected a name")
    base = os.path.basename(filename.strip().replace("\\", "/").rstrip("/"))
    if base in ("", ".", ".."):
        raise ValueError(f"invalid upload filename: {filename!r} resolves to no safe name")
    return base
