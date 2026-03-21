"""
debug_logger.py — Centralized DEBUG logging for ChronoArchiver.
Single file, timestamps, utility name, rotation (keep last 3 files).
"""

import os
import platformdirs
from datetime import datetime

APP_NAME = "ChronoArchiver"
DEBUG_BASENAME = "chronoarchiver_debug.log"
MAX_DEBUG_FILES = 3

_log_dir = None
_log_path = None
_file = None

UTILITY_MEDIA_ORGANIZER = "Media Organizer"
UTILITY_MASS_AV1_ENCODER = "Mass AV1 Encoder"
UTILITY_AI_MEDIA_SCANNER = "AI Media Scanner"


def _ensure_init():
    global _log_dir, _log_path, _file
    if _log_path is not None:
        return
    _log_dir = platformdirs.user_log_dir(APP_NAME, "UnDadFeated")
    os.makedirs(_log_dir, exist_ok=True)
    _log_path = os.path.join(_log_dir, DEBUG_BASENAME)
    _rotate()
    _file = open(_log_path, "a", encoding="utf-8")


def _rotate():
    """Rotate debug logs: keep current + 2 older = 3 files total."""
    base = os.path.join(_log_dir, DEBUG_BASENAME)
    # Delete oldest (.2); shift .1 -> .2, current -> .1; then open fresh current
    if os.path.exists(f"{base}.{MAX_DEBUG_FILES - 1}"):
        try:
            os.remove(f"{base}.{MAX_DEBUG_FILES - 1}")
        except OSError:
            pass
    if os.path.exists(f"{base}.1"):
        try:
            os.rename(f"{base}.1", f"{base}.2")
        except OSError:
            pass
    if os.path.exists(base):
        try:
            os.rename(base, f"{base}.1")
        except OSError:
            pass


def debug(utility: str, message: str):
    """Append a DEBUG entry: timestamp | utility | message."""
    try:
        _ensure_init()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        line = f"{ts} | {utility} | {message}\n"
        _file.write(line)
        _file.flush()
    except Exception:
        pass


def get_log_path() -> str:
    """Return the current debug log file path."""
    _ensure_init()
    return _log_path


def get_log_content() -> str:
    """Return the full content of the current debug log."""
    try:
        path = get_log_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()
    except Exception:
        pass
    return ""
