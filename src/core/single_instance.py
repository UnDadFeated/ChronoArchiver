"""
single_instance.py — Ensure only one ChronoArchiver instance runs.
Uses filelock; second launch exits with message.
"""

import logging

from pathlib import Path

try:
    from .app_paths import runtime_dir
except ImportError:
    from core.app_paths import runtime_dir

_log = logging.getLogger("ChronoArchiver.single_instance")

_lock = None


def _lock_file_path() -> Path:
    return runtime_dir() / "chronoarchiver.lock"


def ensure_single_instance() -> bool:
    """
    Call at app startup. Returns True if this is the only instance.
    Returns False if another instance is running; caller should exit.
    """
    global _lock
    try:
        from filelock import FileLock, Timeout

        lock_path = _lock_file_path()
        _lock = FileLock(str(lock_path))
        try:
            _lock.acquire(timeout=0)
            return True
        except Timeout:
            return False
    except OSError as e:
        _log.error("Cannot create single-instance lock file at %s: %s — check directory permissions", lock_path, e)
        return False
    except Exception as e:
        _log.error("Unexpected error initializing single-instance lock: %s", e)
        return False


def release_single_instance():
    """Call on app exit to release the lock."""
    global _lock
    if _lock:
        try:
            _lock.release()
        except Exception:
            pass
        _lock = None
