"""
venv_manager.py — App-private venv for ChronoArchiver (no sudo).
Ensures all Python deps run from ~/.local/share/ChronoArchiver/venv.
"""

import os
import platform
import subprocess
import sys
from pathlib import Path

try:
    import platformdirs
except ImportError:
    platformdirs = None

APP_NAME = "ChronoArchiver"
APP_AUTHOR = "UnDadFeated"
VENV_PACKAGES = [
    "PySide6", "psutil", "requests", "Pillow", "platformdirs",
    "opencv-python", "piexif",
]


def _data_dir() -> Path:
    if platformdirs:
        return Path(platformdirs.user_data_dir(APP_NAME, APP_AUTHOR))
    return Path.home() / ".local" / "share" / APP_NAME


def get_venv_path() -> Path:
    return _data_dir() / "venv"


def get_python_exe() -> Path:
    venv = get_venv_path()
    if platform.system() == "Windows":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def get_pip_exe() -> Path:
    venv = get_venv_path()
    if platform.system() == "Windows":
        return venv / "Scripts" / "pip.exe"
    return venv / "bin" / "pip"


def is_venv_ready() -> bool:
    """True if venv exists and has the required packages."""
    venv = get_venv_path()
    py = get_python_exe()
    if not py.exists():
        return False
    try:
        r = subprocess.run(
            [str(py), "-c", "import PySide6; import cv2; import PIL; import requests"],
            capture_output=True, timeout=5,
        )
        return r.returncode == 0
    except Exception:
        return False


def ensure_venv(progress_callback=None) -> bool:
    """
    Create venv and install packages. progress_callback(phase: str, detail: str).
    Returns True on success.
    """
    data = _data_dir()
    venv = get_venv_path()
    data.mkdir(parents=True, exist_ok=True)

    def prog(phase, detail=""):
        if progress_callback:
            progress_callback(phase, detail)

    if not (venv / "bin" / "python").exists() and not (venv / "Scripts" / "python.exe").exists():
        prog("Creating virtual environment...", "")
        r = subprocess.run(
            [sys.executable, "-m", "venv", str(venv)],
            capture_output=True, text=True, timeout=60,
        )
        if r.returncode != 0:
            prog("venv creation failed", (r.stderr or r.stdout or "")[:150])
            return False

    pip = get_pip_exe()
    if not pip.exists():
        prog("venv pip not found", "")
        return False

    for pkg in VENV_PACKAGES:
        prog(f"Installing {pkg}...", "")
        proc = subprocess.Popen(
            [str(pip), "install", pkg],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
        )
        for line in iter(proc.stdout.readline, "") if proc.stdout else []:
            line = (line or "").strip()
            if line:
                prog(f"Installing {pkg}...", line[:100])
        proc.wait(timeout=300)
        if proc.returncode != 0:
            prog(f"Failed: {pkg}", "")
            return False

    prog("Setup complete.", "Restart ChronoArchiver.")
    return True


def install_package(pkg: str, progress_callback=None) -> bool:
    """Install a single package into app venv."""
    venv = get_venv_path()
    pip = get_pip_exe()
    if not pip.exists():
        if progress_callback:
            progress_callback("venv not ready", "Run Setup Models first.")
        return False

    def prog(phase, detail=""):
        if progress_callback:
            progress_callback(phase, detail)

    prog(f"Installing {pkg}...", "")
    proc = subprocess.Popen(
        [str(pip), "install", pkg],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )
    for line in iter(proc.stdout.readline, "") if proc.stdout else []:
        line = (line or "").strip()
        if line:
            prog(f"Installing {pkg}...", line[:100])
    proc.wait(timeout=300)
    return proc.returncode == 0


def remove_venv() -> bool:
    """Remove the app venv. Returns True on success."""
    import shutil
    venv = get_venv_path()
    if venv.exists():
        try:
            shutil.rmtree(venv)
            return True
        except OSError:
            pass
    return False


def add_venv_to_path():
    """Add venv site-packages to sys.path (call before importing app deps)."""
    venv = get_venv_path()
    lib = venv / ("Lib" if platform.system() == "Windows" else "lib")
    if not lib.exists():
        return
    for d in lib.iterdir():
        if d.name.startswith("python") and (d / "site-packages").exists():
            sp = str(d / "site-packages")
            if sp not in sys.path:
                sys.path.insert(0, sp)
            break
