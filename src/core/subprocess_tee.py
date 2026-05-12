"""
Hide Windows console flashes for child processes; optional tee of lines to the app UI.
"""

from __future__ import annotations

import platform
import subprocess
import threading
from collections.abc import Callable

_channel: str = "organizer"
_tee: Callable[[str, str], None] | None = None  # (channel, line)
_tee_lock = threading.Lock()


def set_subprocess_channel(ch: str) -> None:
    """'organizer' | 'scanner' — lines go to Media Organizer vs AI Scanner console."""
    global _channel
    with _tee_lock:
        _channel = (ch or "organizer").strip() or "organizer"


def set_subprocess_tee_callback(fn: Callable[[str, str], None] | None) -> None:
    """fn(channel: str, line: str). App should schedule UI updates on the main thread."""
    global _tee
    with _tee_lock:
        _tee = fn


def tee_line(line: str) -> None:
    with _tee_lock:
        fn = _tee
        ch = _channel
    if not line or not fn:
        return
    s = line.rstrip("\n\r")
    if not s:
        return
    try:
        fn(ch, s)
    except Exception:
        pass


def win_hide_kw() -> dict:
    """Merge into subprocess.run / Popen on Windows to avoid console window flash."""
    if platform.system() == "Windows":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}  # type: ignore[attr-defined]
    return {}
