"""
Structured environment summary for issue reports (clipboard / support).
"""

from __future__ import annotations

import platform
import shutil
import sys

from version import __version__

from core.app_paths import ENV_INSTALL_ROOT, data_dir, install_root, logs_dir, settings_dir
from core.venv_manager import check_ffmpeg_in_venv, get_python_exe, get_venv_path


def format_debug_bundle() -> str:
    """Plain-text block: version, OS, Python, paths, FFmpeg resolution."""
    lines: list[str] = []
    lines.append(f"ChronoArchiver {__version__}")
    lines.append(f"OS: {platform.system()} {platform.release()} ({platform.machine()})")
    lines.append(f"Python: {sys.version.splitlines()[0]}")
    lines.append(f"sys.executable: {sys.executable}")
    vroot = get_venv_path()
    py_exe = get_python_exe()
    lines.append(f"App venv root: {vroot}")
    lines.append(f"App venv Python: {py_exe} (exists={py_exe.is_file()})")
    lines.append(f"Data dir: {data_dir()}")
    lines.append(f"Settings dir: {settings_dir()}")
    lines.append(f"Logs dir: {logs_dir()}")
    ir = install_root()
    lines.append(f"{ENV_INSTALL_ROOT}: {ir if ir is not None else '(unset)'}")
    ff_sys = shutil.which("ffmpeg")
    lines.append(f"ffmpeg (PATH): {ff_sys or '(none)'}")
    lines.append(f"ffmpeg bundled in venv (static-ffmpeg crumb): {check_ffmpeg_in_venv()}")
    return "\n".join(lines) + "\n"
