"""
Bridge panel log lines (via the app logger) to a footer “last error” banner.

Clears when log lines indicate a successful batch completion or the user dismisses.
"""

from __future__ import annotations

import logging
from typing import Callable

# Substrings (matched on uppercased message) that clear the banner (success paths).
_CLEAR_MARKERS = (
    "ENCODING BATCH COMPLETE",
    "BATCH ORGANIZATION COMPLETE",
    "BATCH SCAN COMPLETE",
    "UPSCALE COMPLETE",
    "MODEL SETUP COMPLETE",
    "VIDEO ENCODE JOB COMPLETE",
    "VIDEO ENCODE COMPLETE",
    "EXPORT COMPLETE",
)


def user_error_banner_should_clear(message: str) -> bool:
    """True if a log line indicates success and should dismiss the footer error banner."""
    u = message.upper()
    return any(m in u for m in _CLEAR_MARKERS)


def _should_show_error(message: str, levelno: int) -> bool:
    if levelno >= logging.ERROR:
        return True
    s = message.strip().upper()
    return s.startswith("ERROR") or s.startswith("ERROR:")


class UserErrorBannerHandler(logging.Handler):
    """Forwards user-visible errors to Qt (main thread) via ``on_error`` / ``on_clear`` callbacks."""

    def __init__(
        self,
        on_error: Callable[[str], None],
        on_clear: Callable[[], None],
    ):
        super().__init__(level=logging.INFO)
        self._on_error = on_error
        self._on_clear = on_clear

    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        if user_error_banner_should_clear(msg):
            self._on_clear()
            return
        if _should_show_error(msg, record.levelno):
            self._on_error(msg[:800])


def install_user_error_banner_on_logger(
    lg: logging.Logger,
    on_error: Callable[[str], None],
    on_clear: Callable[[], None],
) -> UserErrorBannerHandler:
    h = UserErrorBannerHandler(on_error, on_clear)
    lg.addHandler(h)
    return h
