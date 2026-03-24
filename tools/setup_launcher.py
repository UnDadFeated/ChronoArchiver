"""
ChronoArchiver Setup Launcher — Minimal bootstrap (~6MB) that downloads the full app on first run.
Uses only stdlib: tkinter, urllib, zipfile. No external dependencies.
"""
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.error
import zipfile
from pathlib import Path

# Version embedded at build time via version.txt in bundle
def _read_version() -> str:
    try:
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        for name in ("_setup_version.txt", "version.txt"):
            vpath = os.path.join(base, name)
            if os.path.isfile(vpath):
                return open(vpath, "r", encoding="utf-8").read().strip()
    except Exception:
        pass
    return os.environ.get("CHRONOARCHIVER_VERSION", "3.6.0")


VERSION = _read_version()
GITHUB_RELEASES = "https://api.github.com/repos/UnDadFeated/ChronoArchiver/releases/tags/v{version}"


def _app_dir() -> Path:
    """App installation directory (AppData on Windows, ~/Library on macOS)."""
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        return Path(base) / "ChronoArchiver" / "app"
    return Path.home() / "Library" / "Application Support" / "ChronoArchiver" / "app"


def _version_file() -> Path:
    return _app_dir().parent / "version.txt"


def _is_installed() -> bool:
    """True if app is already installed and matches our version."""
    vf = _version_file()
    if not vf.exists():
        return False
    try:
        return vf.read_text().strip() == VERSION
    except Exception:
        return False


def _exe_path() -> Path:
    """Path to the main app executable."""
    app_dir = _app_dir()
    if platform.system() == "Windows":
        # Zip contains ChronoArchiver/ folder with ChronoArchiver.exe
        return app_dir / "ChronoArchiver" / "ChronoArchiver.exe"
    return app_dir / "ChronoArchiver.app" / "Contents" / "MacOS" / "ChronoArchiver"


def _download_url(platform_key: str) -> str:
    """Get download URL for the app zip from GitHub releases."""
    url = GITHUB_RELEASES.format(version=VERSION)
    suffix = "win64.zip" if platform_key == "win" else "mac64.zip"
    expected_name = f"ChronoArchiver-{VERSION}-{suffix}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ChronoArchiver-Setup", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        for a in data.get("assets", []):
            if a.get("name") == expected_name:
                return a.get("browser_download_url", "")
    except Exception:
        pass
    return ""


def _download_with_progress(url: str, dest_path: str, progress_cb) -> bool:
    """Stream download with progress. progress_cb(component, pct, speed_mbps, size_mb)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ChronoArchiver-Setup"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0) or 0)
            downloaded = 0
            start = time.time()
            chunk_size = 256 * 1024
            with open(dest_path, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    elapsed = time.time() - start
                    speed = (downloaded / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                    pct = (100.0 * downloaded / total) if total > 0 else 0
                    size_mb = downloaded / (1024 * 1024)
                    progress_cb("ChronoArchiver", min(100.0, pct), speed, size_mb)
        return True
    except Exception:
        return False


def _run_app():
    """Launch the installed app."""
    exe = _exe_path()
    if not exe.exists():
        return False
    app_dir = exe.parent
    if platform.system() == "Windows":
        flags = getattr(subprocess, "CREATE_NEW_PROCESS", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
        subprocess.Popen([str(exe)] + sys.argv[1:], cwd=str(app_dir), creationflags=flags, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        # macOS: run the .app bundle
        app_bundle = exe.parent.parent.parent  # ChronoArchiver.app
        subprocess.Popen(["open", "-a", str(app_bundle)] + sys.argv[1:])
    return True


def _do_setup_gui():
    """Show progress window, download, extract, launch."""
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        print("ChronoArchiver: tkinter required for setup UI.")
        return False

    platform_key = "win" if platform.system() == "Windows" else "mac"
    url = _download_url(platform_key)
    if not url:
        root = tk.Tk()
        root.withdraw()
        tk.messagebox.showerror("ChronoArchiver", f"Could not find download for v{VERSION}. Check your connection.")
        root.destroy()
        return False

    root = tk.Tk()
    root.title("ChronoArchiver — Setup")
    root.geometry("480x200")
    root.resizable(False, False)
    root.configure(bg="#0d0d0d")
    root.option_add("*Font", "TkDefaultFont 9")

    lbl_title = tk.Label(root, text="Downloading ChronoArchiver…", fg="#e5e7eb", bg="#0d0d0d", font=("", 11, "bold"))
    lbl_title.pack(pady=(20, 8))
    lbl_component = tk.Label(root, text="ChronoArchiver", fg="#9ca3af", bg="#0d0d0d")
    lbl_component.pack(pady=2)
    lbl_speed = tk.Label(root, text="", fg="#10b981", bg="#0d0d0d")
    lbl_speed.pack(pady=2)
    prog = ttk.Progressbar(root, length=420, mode="determinate")
    prog.pack(pady=12)
    lbl_pct = tk.Label(root, text="0%", fg="#6b7280", bg="#0d0d0d")
    lbl_pct.pack(pady=2)

    result = [False]
    done = [False]

    def progress_cb(component, pct, speed_mbps, size_mb):
        def update():
            lbl_component.config(text=component)
            prog["value"] = min(100, pct)
            lbl_pct.config(text=f"{pct:.1f}%")
            if speed_mbps >= 0.01:
                lbl_speed.config(text=f"{speed_mbps:.2f} MB/s  ·  {size_mb:.1f} MB")
            root.update_idletasks()
        root.after(0, update)

    def task():
        try:
            app_dir = _app_dir()
            app_dir.mkdir(parents=True, exist_ok=True)
            # Download to temp
            fd, zip_path = tempfile.mkstemp(suffix=".zip")
            os.close(fd)
            if not _download_with_progress(url, zip_path, progress_cb):
                result[0] = False
                done[0] = True
                return
            # Extract
            progress_cb("Extracting…", 95, 0, 0)
            if app_dir.exists():
                shutil.rmtree(app_dir)
            app_dir.mkdir(parents=True)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(app_dir)
            try:
                os.remove(zip_path)
            except OSError:
                pass
            # Write version
            _version_file().parent.mkdir(parents=True, exist_ok=True)
            _version_file().write_text(VERSION)
            result[0] = True
        except Exception:
            result[0] = False
        done[0] = True

    def poll():
        if done[0]:
            root.quit()
            return
        root.after(100, poll)

    threading.Thread(target=task, daemon=True).start()
    root.after(100, poll)
    root.mainloop()
    root.destroy()

    if not result[0]:
        root2 = tk.Tk()
        root2.withdraw()
        tk.messagebox.showerror("ChronoArchiver", "Download or extraction failed. Check your connection.")
        root2.destroy()
        return False
    return True


def main():
    if _is_installed() and _exe_path().exists():
        _run_app()
        return
    if _do_setup_gui():
        _run_app()


if __name__ == "__main__":
    main()
