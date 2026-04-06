"""
Serialize heavy filesystem work across panels (Media Organizer, Mass AV1 encode,
AI Media Scanner batch scan, AI Image / Video upscaler jobs) so concurrent operations
do not contend on the same volumes.
"""

from __future__ import annotations

import threading
from typing import Optional

_lock = threading.Lock()
_holder: Optional[str] = None


def try_acquire_fs_heavy(name: str = "") -> bool:
    """Non-blocking acquire. ``name`` identifies the task for status display (e.g. panel title)."""
    ok = _lock.acquire(blocking=False)
    if ok:
        global _holder
        _holder = (name or "Heavy task").strip() or "Heavy task"
    return ok


def acquire_fs_heavy_blocking(name: str = "") -> None:
    """Blocking acquire (reserved for callers that must wait)."""
    global _holder
    _lock.acquire()
    _holder = (name or "Heavy task").strip() or "Heavy task"


def release_fs_heavy() -> None:
    global _holder
    _holder = None
    try:
        _lock.release()
    except RuntimeError:
        pass


def fs_heavy_holder_label() -> Optional[str]:
    """Human-readable name of the task holding the lock, or ``None`` if idle."""
    return _holder
