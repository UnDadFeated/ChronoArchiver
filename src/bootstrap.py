"""
bootstrap.py — First-run venv setup (stdlib + optional tkinter).
Run before main app when venv does not exist.
"""
import os
import sys
from pathlib import Path

# Must run before app imports
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

from core.venv_manager import get_venv_path, get_python_exe, ensure_venv, is_venv_runnable, add_venv_to_path, _is_frozen


def _run_with_ui():
    """Use tkinter for setup window."""
    try:
        import tkinter as tk
        from tkinter import ttk
    except ImportError:
        return _run_headless()

    root = tk.Tk()
    root.title("ChronoArchiver — First-time Setup")
    root.geometry("480x200")
    root.resizable(False, False)
    root.configure(bg="#1a1a1a")

    lbl_title = tk.Label(root, text="Setting up ChronoArchiver...", font=("", 12, "bold"), fg="#e5e7eb", bg="#1a1a1a")
    lbl_title.pack(pady=(20, 8))
    lbl_phase = tk.Label(root, text="Preparing...", font=("", 9), fg="#9ca3af", bg="#1a1a1a")
    lbl_phase.pack(pady=4)
    lbl_detail = tk.Label(root, text="", font=("", 8), fg="#6b7280", bg="#1a1a1a", wraplength=440)
    lbl_detail.pack(pady=4, padx=20)
    prog = ttk.Progressbar(root, mode="indeterminate", length=400)
    prog.pack(pady=16)
    prog.start(10)

    done = [False]
    result = [False]

    def progress(phase, detail):
        lbl_phase.config(text=phase)
        lbl_detail.config(text=detail)
        root.update_idletasks()

    def task():
        result[0] = ensure_venv(progress_callback=progress, skip_opencv=True)  # User installs OpenCV in AI Scanner
        done[0] = True
        root.after(0, root.quit)

    import threading
    t = threading.Thread(target=task, daemon=True)
    t.start()
    root.mainloop()
    prog.stop()
    root.destroy()
    return result[0]


def _run_headless():
    """No UI — print to stdout."""
    def progress(phase, detail):
        print(f"  {phase}  {detail}")

    return ensure_venv(progress_callback=progress, skip_opencv=True)


def _run_frozen_app():
    """Load app.py with importlib; runpy.run_path fails on frozen bundles (no __main__)."""
    import importlib.util

    base = Path(getattr(sys, "_MEIPASS", str(_SCRIPT_DIR)))
    app_py = base / "src" / "ui" / "app.py"
    if not app_py.is_file():
        app_py = base / "ui" / "app.py"
    if not app_py.is_file():
        print(f"ChronoArchiver: missing app (looked under {base})", file=sys.stderr)
        sys.exit(1)
    os.chdir(str(base))
    src_root = str(base / "src")
    if os.path.isdir(src_root) and src_root not in sys.path:
        sys.path.insert(0, src_root)
    add_venv_to_path()
    spec = importlib.util.spec_from_file_location("__main__", app_py)
    if spec is None or spec.loader is None:
        print("ChronoArchiver: cannot load app", file=sys.stderr)
        sys.exit(1)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["__main__"] = mod
    spec.loader.exec_module(mod)


def main():
    get_venv_path()
    # When frozen (PyInstaller), run app directly without venv
    if _is_frozen():
        _run_frozen_app()
        return
    py = get_python_exe()
    app_py = _SCRIPT_DIR / "ui" / "app.py"
    app_root = str(_SCRIPT_DIR)

    if py.exists() and is_venv_runnable():
        add_venv_to_path()  # LD_LIBRARY_PATH for OpenCV CUDA (libcufft, libcudnn) before execv
        os.chdir(app_root)
        try:
            os.execv(str(py), [str(py), str(app_py)] + sys.argv[1:])
        except OSError as e:
            print(f"Failed to launch: {e}")
            sys.exit(1)

    print("ChronoArchiver — First-time setup (creating environment)...")
    ok = _run_with_ui() if os.environ.get("DISPLAY") else _run_headless()
    if not ok:
        print("Setup failed. See messages above.")
        sys.exit(1)
    print("Setup complete. Launching...")
    add_venv_to_path()  # LD_LIBRARY_PATH for OpenCV CUDA (libcufft, libcudnn) before execv
    os.chdir(app_root)
    try:
        os.execv(str(py), [str(py), str(app_py)] + sys.argv[1:])
    except OSError as e:
        print(f"Failed to launch: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
