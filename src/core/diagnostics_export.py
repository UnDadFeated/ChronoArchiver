"""
Write a local diagnostic archive for issue reports. Nothing is uploaded automatically.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from core.debug_info import format_debug_bundle


def _log_tail_text(max_bytes: int = 120_000) -> str:
    from core.debug_logger import get_log_path

    p = get_log_path()
    try:
        data = Path(p).read_bytes()
    except OSError as e:
        return f"(Could not read log file: {e})\n"
    if len(data) > max_bytes:
        data = data[-max_bytes:]
        return "… [truncated from start] …\n" + data.decode("utf-8", errors="replace")
    return data.decode("utf-8", errors="replace")


_README = """ChronoArchiver diagnostic archive (local only)

This ZIP was created on your machine. ChronoArchiver does not upload it to any server.

You may attach it to a GitHub issue or support email if you choose. It may contain
paths under your user profile (e.g. venv and log locations); review before sending.

Contents:
  environment.txt — version, OS, Python, venv, FFmpeg resolution
  log_tail.txt      — end of the current session debug log

Optional: set CHRONOARCHIVER_JSON_LOG=1 when launching the app to also create
*_structured.jsonl next to the session .log (machine-readable; still local only).
"""


def write_diagnostic_zip(path: Path) -> None:
    """Create a ZIP at ``path`` (``.zip`` suffix recommended)."""
    path = Path(path)
    env_txt = format_debug_bundle()
    tail = _log_tail_text()
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.txt", _README)
        zf.writestr("environment.txt", env_txt)
        zf.writestr("log_tail.txt", tail)
