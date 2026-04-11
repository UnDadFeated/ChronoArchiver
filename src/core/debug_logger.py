"""
debug_logger.py — Single log file for ChronoArchiver per session.
One file created at startup: chronoarchiver_YYYY-MM-DD_HH-MM-SS.log
Both debug() and standard logging write to this file. Keeps last 5.

Also: uncaught exception hooks (main + threads), optional traceback logging API,
and mirroring of important panel lines into the legacy pipe format.
"""

from __future__ import annotations

import glob
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import threading
import traceback
from datetime import datetime
from typing import Any

try:
    from .app_paths import logs_dir
except ImportError:
    from core.app_paths import logs_dir
LOG_PREFIX = "chronoarchiver"
LOG_SUFFIX = ".log"
MAX_LOG_FILES = 5

_log_dir = None
_log_path = None
_file = None
_jsonl_path = None
_jsonl_file = None

_hooks_installed = False
_prev_sys_excepthook = None
_prev_thread_excepthook = None

_crash_diagnostics_installed = False

# Best-effort UI context for uncaught exceptions (set from the main window).
_activity_context = ""

_uncaught = logging.getLogger("ChronoArchiver.uncaught")

UTILITY_APP = "ChronoArchiver"
UTILITY_MEDIA_ORGANIZER = "Media Organizer"
UTILITY_MASS_AV1_ENCODER = "Mass AV1 Encoder"
UTILITY_AI_MEDIA_SCANNER = "AI Media Scanner"
UTILITY_OPENCV_INSTALL = "OpenCV Install"
UTILITY_MODEL_SETUP = "Model Setup"
# Prerequisite / download popups (FFmpeg, OpenCV, models, PyTorch, updater) — mirror UI lines to master log.
UTILITY_INSTALLER_POPUP = "Installer popup"

# Internal app labels for log_installer_popup (session debug log).
INSTALLER_APP_MAIN = "ChronoArchiver"
INSTALLER_APP_AI_VIDEO_UPSCALER = "AI Video Upscaler"
INSTALLER_APP_AI_IMAGE_UPSCALER = "AI Image Upscaler"
INSTALLER_APP_AI_MEDIA_SCANNER = "AI Media Scanner"
INSTALLER_APP_MASS_AV1_ENCODER = "Mass AV1 Encoder"


def log_installer_popup(app: str, dialog: str, event: str, detail: str = "") -> None:
    """
    Log installer / prerequisite popup activity to the session debug log.

    Use for: show/hide, progress, cancel, completion. ``detail`` is truncated internally if very long.
    """
    try:
        d = (detail or "").strip()
        if len(d) > 2000:
            d = d[:1990] + "… [truncated]"
        msg = f"{app} | {dialog} | {event}"
        if d:
            msg += f" | {d}"
        debug(UTILITY_INSTALLER_POPUP, msg)
    except Exception:
        pass


def _structured_jsonl_enabled() -> bool:
    v = (os.environ.get("CHRONOARCHIVER_JSON_LOG") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _ensure_init():
    global _log_dir, _log_path, _file, _jsonl_path, _jsonl_file
    if _log_path is not None:
        return
    _log_dir = str(logs_dir())
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_path = os.path.join(_log_dir, f"{LOG_PREFIX}_{ts}{LOG_SUFFIX}")
    _file = open(_log_path, "a", encoding="utf-8")
    if _structured_jsonl_enabled():
        _jsonl_path = os.path.join(_log_dir, f"{LOG_PREFIX}_{ts}_structured.jsonl")
        _jsonl_file = open(_jsonl_path, "a", encoding="utf-8")
    _prune_old_logs()


def _prune_old_logs():
    """Keep only the last MAX_LOG_FILES instances (by mtime), including current file."""
    pattern = os.path.join(_log_dir, f"{LOG_PREFIX}_*{LOG_SUFFIX}")
    files = glob.glob(pattern)
    if len(files) <= MAX_LOG_FILES:
        return
    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    for p in files[MAX_LOG_FILES:]:
        try:
            if p != _log_path:
                os.remove(p)
        except OSError:
            pass


def debug(utility: str, message: str):
    """Append a log entry: timestamp | utility | message."""
    try:
        _ensure_init()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        line = f"{ts} | {utility} | {message}\n"
        _file.write(line)
        _file.flush()
        if _jsonl_file is not None:
            rec = {"ts": ts, "utility": utility, "message": message, "kind": "debug"}
            _jsonl_file.write(json.dumps(rec, ensure_ascii=False) + "\n")
            _jsonl_file.flush()
    except Exception:
        pass


def structured_event(event: str, **fields: Any) -> None:
    """
    Append one JSON line to ``*_structured.jsonl`` when ``CHRONOARCHIVER_JSON_LOG`` is enabled.

    Use for major state transitions (encode start/complete, model verify, etc.). Values must be JSON-serializable.
    """
    if not _structured_jsonl_enabled():
        return
    try:
        _ensure_init()
        if _jsonl_file is None:
            return
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        safe: dict[str, Any] = {}
        for k, v in fields.items():
            try:
                json.dumps(v)
                safe[k] = v
            except (TypeError, ValueError):
                safe[k] = repr(v)[:500]
        rec: dict[str, Any] = {"kind": "event", "ts": ts, "event": event, **safe}
        _jsonl_file.write(json.dumps(rec, ensure_ascii=False) + "\n")
        _jsonl_file.flush()
    except Exception:
        pass


def init_log():
    """Ensure log file is created at startup. Call early in app init."""
    _ensure_init()


def get_log_path() -> str:
    """Return the current debug log file path."""
    _ensure_init()
    return _log_path


def set_activity_context(text: str) -> None:
    """Set a short description of current panel/activity for crash logs (main thread)."""
    global _activity_context
    try:
        _activity_context = (text or "").strip()[:500]
    except Exception:
        _activity_context = ""


def get_activity_context() -> str:
    return _activity_context


def append_multiline(utility: str, title: str, body: str, *, max_chars: int = 32000) -> None:
    """Write a multi-line block (e.g. subprocess output) to the session pipe log."""
    try:
        _ensure_init()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        b = (body or "").strip()
        if len(b) > max_chars:
            b = b[: max_chars - 40] + "\n… [truncated] …\n"
        block = f"{ts} | {utility} | {title}\n{b}\n"
        _file.write(block)
        _file.flush()
    except Exception:
        pass


def log_exception(
    exc: BaseException,
    context: str = "",
    *,
    utility: str = UTILITY_APP,
    extra: str | None = None,
) -> None:
    """Log a caught exception with full traceback to pipe file + standard logging."""
    try:
        _ensure_init()
        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        tb_str = "".join(tb)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        head = f"{ts} | {utility} | EXCEPTION"
        if context:
            head += f" [{context}]"
        _file.write(f"{head}\n{tb_str}")
        if extra:
            _file.write(f"Detail: {extra}\n")
        _file.flush()
    except Exception:
        pass
    try:
        _uncaught.error(
            "%s%s",
            f"{context}: " if context else "",
            exc,
            exc_info=(type(exc), exc, exc.__traceback__),
        )
    except Exception:
        pass


def _log_uncaught_tb(exc_type, exc_value, exc_tb, context: str) -> None:
    if exc_type is None or exc_value is None:
        return
    try:
        _ensure_init()
        tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        _file.write(f"{ts} | {UTILITY_APP} | UNCAUGHT [{context}]\n{tb_str}")
        ctx = get_activity_context()
        if ctx:
            _file.write(f"{ts} | {UTILITY_APP} | CRASH CONTEXT | {ctx}\n")
        try:
            from version import __version__

            _file.write(
                f"{ts} | {UTILITY_APP} | CRASH VERSION | ChronoArchiver {__version__} | "
                f"Python {sys.version.splitlines()[0]}\n"
            )
        except Exception:
            pass
        _file.flush()
        _uncaught.error("UNCAUGHT [%s]\n%s", context, tb_str.strip())
    except Exception:
        pass


def _sys_excepthook(exc_type, exc_value, exc_tb):
    try:
        _log_uncaught_tb(exc_type, exc_value, exc_tb, "sys.excepthook")
    except Exception:
        pass
    hook = _prev_sys_excepthook or sys.__excepthook__
    try:
        hook(exc_type, exc_value, exc_tb)
    except Exception:
        pass


def _thread_excepthook(args: threading.ExceptHookArgs) -> None:
    try:
        if args.exc_type is not None:
            _log_uncaught_tb(
                args.exc_type,
                args.exc_value,
                args.exc_traceback,
                f"threading (name={getattr(args.thread, 'name', '?')})",
            )
    except Exception:
        pass
    if _prev_thread_excepthook is not None:
        try:
            _prev_thread_excepthook(args)
        except Exception:
            pass


def install_global_exception_hooks() -> None:
    """Install once: log uncaught exceptions from main thread and worker threads."""
    global _hooks_installed, _prev_sys_excepthook, _prev_thread_excepthook
    if _hooks_installed:
        return
    _ensure_init()
    if sys.excepthook is not _sys_excepthook:
        _prev_sys_excepthook = sys.excepthook
        sys.excepthook = _sys_excepthook
    if hasattr(threading, "excepthook"):
        if threading.excepthook is not _thread_excepthook:
            _prev_thread_excepthook = threading.excepthook
            threading.excepthook = _thread_excepthook
    _hooks_installed = True


def _gdb_backtrace_env_enabled() -> bool:
    v = (os.environ.get("CHRONOARCHIVER_GDB_BACKTRACE") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _try_gdb_live_backtrace_to_log() -> None:
    """Best-effort ``gdb`` attach to this process; requires gdb, Linux-like host, ptrace permission."""
    if not _gdb_backtrace_env_enabled():
        return
    if sys.platform.startswith("win"):
        return
    gdb = shutil.which("gdb")
    if not gdb:
        append_multiline(UTILITY_APP, "gdb backtrace (CHRONOARCHIVER_GDB_BACKTRACE=1)", "(gdb not found in PATH)")
        return
    pid = os.getpid()
    try:
        cp = subprocess.run(
            [
                gdb,
                "-batch",
                "-p",
                str(pid),
                "-ex",
                "set pagination off",
                "-ex",
                "thread apply all bt",
                "-ex",
                "detach",
                "-ex",
                "quit",
            ],
            capture_output=True,
            text=True,
            timeout=45,
        )
        out = ((cp.stdout or "") + (cp.stderr or "")).strip()
        append_multiline(UTILITY_APP, "gdb thread apply all bt (live attach)", out or "(empty gdb output)")
    except Exception as exc:
        append_multiline(UTILITY_APP, "gdb backtrace", f"(failed: {exc})")


def _dump_requested_stacks(reason: str) -> None:
    """Python C-stack + threads via faulthandler; optional gdb (see env). Runs off the signal handler thread."""
    try:
        import faulthandler

        _ensure_init()
        if _file is None:
            return
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        _file.write(f"{ts} | {UTILITY_APP} | STACK DUMP | {reason}\n")
        _file.flush()
        try:
            faulthandler.dump_traceback(file=_file.fileno(), all_threads=True)
        except Exception:
            faulthandler.dump_traceback(file=sys.stderr, all_threads=True)
        _file.flush()
    except Exception:
        pass
    try:
        _try_gdb_live_backtrace_to_log()
    except Exception:
        pass


def _schedule_stack_dump(reason: str) -> None:
    try:
        threading.Thread(target=_dump_requested_stacks, args=(reason,), daemon=True).start()
    except Exception:
        pass


def install_crash_diagnostics() -> None:
    """
    Log fatal signals (when the runtime can still react) into the session file via faulthandler,
    and register SIGUSR2 (Unix) to dump Python stacks + optional gdb backtrace into the same log.
    """
    global _crash_diagnostics_installed
    if _crash_diagnostics_installed:
        return
    _ensure_init()
    _crash_diagnostics_installed = True
    try:
        import faulthandler

        # File descriptor avoids text/binary mode mismatch; interleaves with UTF-8 lines acceptably for a debug log.
        faulthandler.enable(_file.fileno() if _file is not None else sys.stderr.fileno(), all_threads=True)
    except Exception:
        pass
    try:
        pid = os.getpid()
        parts = [
            f"pid={pid}",
            "fatal signals: faulthandler writes Python stacks to this log when possible",
        ]
        if hasattr(signal, "SIGUSR2"):
            parts.append(f"if hung: kill -USR2 {pid} dumps stacks here")
        if _gdb_backtrace_env_enabled():
            parts.append("gdb live attach on SIGUSR2 enabled (CHRONOARCHIVER_GDB_BACKTRACE=1)")
        debug(UTILITY_APP, "CRASH DIAG | " + " | ".join(parts))
        if not sys.platform.startswith("win"):
            debug(
                UTILITY_APP,
                "CRASH DIAG | native: from another terminal (app still running): gdb -p "
                + str(pid)
                + ' -batch -ex "thread apply all bt" -ex "detach" -ex "quit"',
            )
            debug(
                UTILITY_APP,
                "CRASH DIAG | post-mortem: ulimit -c unlimited ; re-run; after SIGSEGV use gdb $(which python3) core*",
            )
    except Exception:
        pass
    if hasattr(signal, "SIGUSR2"):

        def _on_sigusr2(_signum, _frame) -> None:
            _schedule_stack_dump("SIGUSR2")

        try:
            signal.signal(signal.SIGUSR2, _on_sigusr2)
        except Exception:
            pass


def mirror_panel_line(panel: str, msg: str, *, max_len: int = 8000) -> None:
    """Copy important panel console lines into the pipe log (ERROR/WARNING/ffmpeg failures)."""
    s = str(msg).strip()
    if not s or len(s) > max_len:
        s = s[:max_len]
    u = s.upper()
    if not (
        u.startswith("ERROR") or u.startswith("WARNING") or u.startswith("FAILED") or "FFMPEG" in u or "TRACEBACK" in u
    ):
        return
    try:
        debug(UTILITY_APP, f"{panel}: {s}")
    except Exception:
        pass


def install_qt_message_handler() -> None:
    """Route Qt fatal/critical/warning messages to the standard log (call after QApplication + setup_logger)."""
    try:
        from PySide6.QtCore import QtMsgType, qInstallMessageHandler
    except ImportError:
        return

    def _handler(mode, context, message: str) -> None:
        lg = logging.getLogger("ChronoArchiver.Qt")
        try:
            fn = getattr(context, "file", None) or ""
            line = getattr(context, "line", 0)
            loc = f"{fn}:{line} " if fn else ""
        except Exception:
            loc = ""
        text = f"{loc}{message}".strip()
        try:
            if mode == QtMsgType.QtFatalMsg:
                lg.critical(text)
            elif mode == QtMsgType.QtCriticalMsg:
                lg.error(text)
            elif mode == QtMsgType.QtWarningMsg:
                lg.warning(text)
            elif mode == QtMsgType.QtInfoMsg:
                lg.info(text)
            else:
                lg.debug(text)
        except Exception:
            pass

    qInstallMessageHandler(_handler)
