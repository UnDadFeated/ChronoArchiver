"""
venv_manager.py — App-private venv for ChronoArchiver (no sudo).
Ensures all Python deps run from ~/.local/share/ChronoArchiver/venv.
"""

import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import platformdirs
except ImportError:
    platformdirs = None

try:
    import requests
except ImportError:
    requests = None

APP_NAME = "ChronoArchiver"
APP_AUTHOR = "UnDadFeated"
OPENCV_CUDA_API = "https://api.github.com/repos/cudawarped/opencv-python-cuda-wheels/releases/latest"
OPENCV_STANDARD_APPROX_BYTES = 90 * 1024 * 1024  # ~90 MB
# Fallback when API unavailable: system opencv-cuda (pacman) ~7498 MiB installed
# (cuda+cuDNN+vtk+openmpi+opencv-cuda+python-opencv-cuda). Our pip wheel is smaller.
OPENCV_CUDA_FALLBACK_BYTES = 7498 * 1024 * 1024

# Base packages (opencv chosen by get_opencv_package())
VENV_PACKAGES_BASE = [
    "PySide6", "psutil", "requests", "Pillow", "platformdirs",
    "piexif",
]


def detect_gpu() -> str:
    """Return 'nvidia', 'amd', 'intel', or ''."""
    try:
        r = subprocess.run(
            ["nvidia-smi"], capture_output=True, timeout=3,
        )
        if r.returncode == 0:
            return "nvidia"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    try:
        with open("/sys/class/drm/card0/device/vendor", "r") as f:
            vendor = f.read().strip()
        if "0x1002" in vendor or "amd" in vendor.lower():
            return "amd"
        if "0x8086" in vendor:
            return "intel"
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["lspci"], capture_output=True, text=True, timeout=2,
        )
        if r.returncode == 0:
            out = (r.stdout or "").lower()
            if "amd" in out and ("radeon" in out or "graphics" in out):
                return "amd"
            if "intel" in out and ("xe" in out or "arc" in out or "uhd" in out or "iris" in out or "graphics" in out):
                return "intel"
            if "amd" in out:
                return "amd"
            if "intel" in out:
                return "intel"
    except Exception:
        pass
    return ""


def get_opencv_variant() -> str:
    """
    Return OpenCV install variant based on GPU:
    - 'cuda': NVIDIA → cudawarped wheel
    - 'opencl_amd': AMD Radeon → opencv-python (OpenCL / ROCm path, cv2.UMat)
    - 'opencl_intel': Intel Xe/Arc/integrated → opencv-python (OpenCL)
    - 'opencl': No discrete GPU → opencv-python (OpenCL, universal)
    """
    gpu = detect_gpu()
    if gpu == "nvidia":
        return "cuda"
    if gpu == "amd":
        return "opencl_amd"
    if gpu == "intel":
        return "opencl_intel"
    return "opencl"


def get_opencv_variant_label() -> str:
    """Human-readable label for the selected OpenCV variant."""
    v = get_opencv_variant()
    return {
        "cuda": "OpenCV (CUDA)",
        "opencl_amd": "OpenCV (OpenCL — AMD Radeon)",
        "opencl_intel": "OpenCV (OpenCL — Intel)",
        "opencl": "OpenCV (OpenCL)",
    }.get(v, "OpenCV (OpenCL)")


def get_opencv_package() -> str:
    """Return opencv package for pip (bootstrap/ensure_venv). CUDA uses wheel install separately."""
    if get_opencv_variant() == "cuda":
        return "opencv-python"  # Bootstrap uses standard; user installs CUDA via Install button
    return "opencv-python"


def get_venv_packages() -> list:
    return VENV_PACKAGES_BASE + [get_opencv_package()]


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


def check_opencv_in_venv() -> bool:
    """True if venv exists and can import cv2 (runtime check, not import-time cache)."""
    py = get_python_exe()
    if not py.exists():
        return False
    try:
        r = subprocess.run([str(py), "-c", "import cv2"], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:
        return False


def is_venv_runnable() -> bool:
    """True if venv exists and can run the app (PySide6, PIL, requests). Does NOT require OpenCV."""
    py = get_python_exe()
    if not py.exists():
        return False
    try:
        r = subprocess.run(
            [str(py), "-c", "import PySide6; import PIL; import requests"],
            capture_output=True, timeout=5,
        )
        return r.returncode == 0
    except Exception:
        return False


def is_venv_ready() -> bool:
    """True if venv exists and has all required packages including OpenCV."""
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


def ensure_venv(progress_callback=None, skip_opencv: bool = False) -> bool:
    """
    Create venv and install packages. progress_callback(phase: str, detail: str).
    skip_opencv: if True, do not install opencv (caller will install separately).
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

    packages = VENV_PACKAGES_BASE + ([] if skip_opencv else [get_opencv_package()])
    for pkg in packages:
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


def get_opencv_install_size(variant: str | None = None) -> tuple:
    """Return (size_bytes, human_str) for OpenCV install."""
    components = get_opencv_install_components(variant)
    total = sum(s for _, s in components)
    if total <= 0:
        total = OPENCV_CUDA_FALLBACK_BYTES if (variant or get_opencv_variant()) == "cuda" else OPENCV_STANDARD_APPROX_BYTES
    gb, mb = total / (1024**3), total / (1024**2)
    return total, f"~{gb:.2f} GB" if gb >= 0.1 else f"~{mb:.1f} MB"


def get_opencv_install_components(variant: str | None = None) -> list[tuple[str, int]]:
    """Return [(component_name, size_bytes), ...] for the install confirmation dialog.
    variant: 'cuda'|'opencl_amd'|'opencl_intel'|'opencl' (default: from get_opencv_variant)."""
    v = variant or get_opencv_variant()
    if v == "cuda":
        if not requests:
            return [("opencv-contrib-python (CUDA)", OPENCV_CUDA_FALLBACK_BYTES)]
        try:
            r = requests.get(OPENCV_CUDA_API, timeout=10)
            if r.status_code != 200:
                return [("opencv-contrib-python (CUDA)", OPENCV_CUDA_FALLBACK_BYTES)]
            data = r.json()
            is_win = platform.system() == "Windows"
            for a in data.get("assets", []):
                name = a.get("name", "")
                if not name.endswith(".whl"):
                    continue
                size = int(a.get("size", 0) or 0)
                if size <= 0:
                    continue
                if is_win and "win_amd64" in name:
                    return [("opencv-contrib-python (CUDA, Windows)", size)]
                if not is_win and "linux" in name.lower() and "x86_64" in name:
                    return [("opencv-contrib-python (CUDA, Linux)", size)]
        except Exception:
            pass
        return [("opencv-contrib-python (CUDA)", OPENCV_CUDA_FALLBACK_BYTES)]
    # opencl_amd, opencl_intel, opencl: all use opencv-python
    url, size = _get_opencv_standard_wheel_url()
    labels = {
        "opencl_amd": "opencv-python (OpenCL — AMD Radeon)",
        "opencl_intel": "opencv-python (OpenCL — Intel)",
        "opencl": "opencv-python (OpenCL)",
    }
    label = labels.get(v, "opencv-python (OpenCL)")
    if url and size > 0:
        return [(label, size)]
    return [(label, OPENCV_STANDARD_APPROX_BYTES)]


def _get_opencv_standard_wheel_url() -> tuple:
    """Return (url, size_bytes) for opencv-python wheel from PyPI. Returns (None, 0) on failure."""
    if not requests:
        return None, 0
    try:
        r = requests.get("https://pypi.org/pypi/opencv-python/json", timeout=15)
        if r.status_code != 200:
            return None, 0
        data = r.json()
        is_win = platform.system() == "Windows"
        for info in data.get("urls", []):
            if info.get("packagetype") != "bdist_wheel":
                continue
            fn = info.get("filename", "").lower()
            if is_win and "win_amd64" in fn:
                return info.get("url"), int(info.get("size", 0) or 0)
            if not is_win and "manylinux" in fn and "x86_64" in fn:
                return info.get("url"), int(info.get("size", 0) or 0)
            if platform.system() == "Darwin" and "macosx" in fn:
                return info.get("url"), int(info.get("size", 0) or 0)
        return None, 0
    except Exception:
        return None, 0


def _download_wheel_with_progress(url: str, progress_callback, total_hint: int = 0) -> Path | None:
    """Download wheel to temp file, report progress. Returns path or None on failure."""
    if not requests:
        return None
    try:
        r = requests.get(url, stream=True, timeout=(10, 120))
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0) or 0) or total_hint
        progress_callback("Downloading...", "", 0, total)
        fd, path = tempfile.mkstemp(suffix=".whl")
        try:
            with os.fdopen(fd, "wb") as f:
                downloaded = 0
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        progress_callback("Downloading...", "", downloaded, total)
            return Path(path)
        except Exception:
            try:
                os.unlink(path)
            except OSError:
                pass
            return None
    except Exception:
        return None


def install_opencv(progress_callback=None, variant: str | None = None) -> bool:
    """Install OpenCV into venv.
    variant: 'cuda'|'opencl_amd'|'opencl_intel'|'opencl' (default: from get_opencv_variant).
    progress_callback(phase, detail, downloaded=0, total=0) — total>0 enables size-based bar."""
    pip = get_pip_exe()
    if not pip.exists():
        if progress_callback:
            progress_callback("venv not ready", "Run first-time setup first.", 0, 0)
        return False

    def prog(phase, detail="", downloaded=0, total=0):
        if progress_callback:
            progress_callback(phase, detail[:100] if detail else "", downloaded, total)

    # Uninstall existing opencv (all variants)
    prog("Removing existing OpenCV...", "")
    subprocess.run(
        [str(pip), "uninstall", "-y",
         "opencv-python", "opencv-python-headless",
         "opencv-contrib-python", "opencv-contrib-python-headless",
         "opencv-openvino-contrib-python"],
        capture_output=True, timeout=60,
    )

    v = variant or get_opencv_variant()
    wheel_path: Path | None = None
    try:
        if v == "cuda" and detect_gpu() == "nvidia" and requests:
            prog("Fetching OpenCV CUDA wheel URL...", "")
            try:
                r = requests.get(OPENCV_CUDA_API, timeout=10)
                if r.status_code != 200:
                    prog("Failed", "Could not fetch release info", 0, 0)
                    return False
                data = r.json()
                wheel_url = None
                wheel_size = 0
                is_win = platform.system() == "Windows"
                for a in data.get("assets", []):
                    name = a.get("name", "")
                    if name.endswith(".whl"):
                        if is_win and "win_amd64" in name:
                            wheel_url = a.get("browser_download_url")
                            wheel_size = int(a.get("size", 0) or 0)
                            break
                        if not is_win and "linux" in name.lower() and "x86_64" in name:
                            wheel_url = a.get("browser_download_url")
                            wheel_size = int(a.get("size", 0) or 0)
                            break
                if not wheel_url:
                    prog("Failed", "No matching CUDA wheel for this platform", 0, 0)
                    return False
                wheel_path = _download_wheel_with_progress(
                    wheel_url,
                    lambda p, d, down, tot: prog(p, d, down, tot),
                    total_hint=wheel_size,
                )
            except Exception as e:
                prog("Failed", str(e)[:80], 0, 0)
                return False
        else:
            wheel_url, wheel_size = _get_opencv_standard_wheel_url()
            if wheel_url:
                wheel_path = _download_wheel_with_progress(
                    wheel_url,
                    lambda p, d, down, tot: prog(p, d, down, tot),
                    total_hint=wheel_size or OPENCV_STANDARD_APPROX_BYTES,
                )
            if not wheel_path:
                prog("Installing OpenCV...", "Downloading via pip...", 0, 0)
                return install_package("opencv-python", lambda p, d: progress_callback(p, d, 0, 0))

        if not wheel_path or not wheel_path.exists():
            prog("Failed", "Download failed", 0, 0)
            return False

        prog("Installing OpenCV...", "Installing wheel...", 0, 0)
        result = subprocess.run(
            [str(pip), "install", str(wheel_path)],
            capture_output=True, text=True, timeout=300,
        )
        try:
            wheel_path.unlink()
        except OSError:
            pass
        if result.returncode != 0:
            prog("Failed", (result.stderr or result.stdout or "")[:80], 0, 0)
            return False
        prog("Complete.", "", 1, 1)
        return True
    finally:
        if wheel_path and wheel_path.exists():
            try:
                wheel_path.unlink()
            except OSError:
                pass


def uninstall_opencv(progress_callback=None) -> bool:
    """Remove OpenCV from venv (all variants)."""
    pip = get_pip_exe()
    if not pip.exists():
        return False
    r = subprocess.run(
        [str(pip), "uninstall", "-y",
         "opencv-python", "opencv-python-headless",
         "opencv-contrib-python", "opencv-contrib-python-headless",
         "opencv-openvino-contrib-python"],
        capture_output=True, text=True, timeout=60,
    )
    return r.returncode == 0


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
