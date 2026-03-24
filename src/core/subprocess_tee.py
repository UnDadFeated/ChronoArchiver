"""
Hide Windows console flashes for child processes; optional tee of lines to the app UI.
"""

from __future__ import annotations

import platform
import subprocess

_channel: str = "organizer"
_tee = None  # Optional[Callable[[str, str], None]]  (channel, line)


def set_subprocess_channel(ch: str) -> None:
    """'organizer' | 'scanner' — lines go to Media Organizer vs AI Scanner console."""
    global _channel
    _channel = (ch or "organizer").strip() or "organizer"


def set_subprocess_tee_callback(fn) -> None:
    """fn(channel: str, line: str). App should schedule UI updates on the main thread."""
    global _tee
    _tee = fn


def tee_line(line: str) -> None:
    if not line or not _tee:
        return
    s = line.rstrip("\n\r")
    if not s:
        return
    try:
        _tee(_channel, s)
    except Exception:
        pass


def win_hide_kw() -> dict:
    """Merge into subprocess.run / Popen on Windows to avoid console window flash."""
    if platform.system() == "Windows":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}
