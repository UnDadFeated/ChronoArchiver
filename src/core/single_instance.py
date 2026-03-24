"""
single_instance.py — Ensure only one ChronoArchiver instance runs.
Uses filelock; second launch exits with message.
"""
from pathlib import Path

try:
    import platformdirs
    _lock_dir = Path(platformdirs.user_runtime_dir("ChronoArchiver", "UnDadFeated"))
except Exception:
    _lock_dir = Path.home() / ".local" / "state" / "ChronoArchiver"

_LOCK_FILE = _lock_dir / "chronoarchiver.lock"
_lock = None


def ensure_single_instance() -> bool:
    """
    Call at app startup. Returns True if this is the only instance.
    Returns False if another instance is running; caller should exit.
    """
    global _lock
    _lock_dir.mkdir(parents=True, exist_ok=True)
    try:
        from filelock import FileLock, Timeout
        _lock = FileLock(str(_LOCK_FILE))
        _lock.acquire(timeout=0)
        return True
    except Exception:
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
