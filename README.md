# ChronoArchiver

<img src="src/ui/assets/icon.png" width="96" align="right" alt="" />

Desktop app for organizing media by date, batch-encoding video to AV1, and optional local AI tools (scanner, upscalers). Cross-platform (Windows, Linux, macOS). Uses PySide6 and a private app environment—no need to install Python packages system-wide.

[![Version](https://img.shields.io/badge/version-6.8.5-blue.svg)](https://github.com/UnDadFeated/ChronoArchiver/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platforms](https://img.shields.io/badge/platforms-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](https://github.com/UnDadFeated/ChronoArchiver#overview)

## Get started

### Windows

1. Download `ChronoArchiver-Setup-{version}.exe` from [GitHub Releases](https://github.com/UnDadFeated/ChronoArchiver/releases).
2. Run the installer — it downloads the full application on first launch.

### macOS

1. Download `ChronoArchiver-Setup-{version}.app.zip` from [GitHub Releases](https://github.com/UnDadFeated/ChronoArchiver/releases) and unzip it.
2. If Gatekeeper blocks it: right-click → **Open**, or run `xattr -d com.apple.quarantine ChronoArchiver-Setup-{version}.app`.
3. Launch from Finder or Applications.

### Linux

1. Download `ChronoArchiver-Setup-{version}` from [GitHub Releases](https://github.com/UnDadFeated/ChronoArchiver/releases).
2. Make it executable: `chmod +x ChronoArchiver-Setup-{version}`.
3. Run it: `./ChronoArchiver-Setup-{version}`.
   - Required system libraries: `libegl1`, `libgl1`, `libdbus-1-3`, `libxcb-cursor0`.

### Arch Linux

Install from the AUR:

```bash
paru -S chronoarchiver   # or: yay -S chronoarchiver
```

### From source (Python 3.10+)

```bash
git clone https://github.com/UnDadFeated/ChronoArchiver.git
cd ChronoArchiver
python src/bootstrap.py
```

If the bundled environment breaks: `python src/bootstrap.py --reset-venv`.


## Overview

| Area | Role |
|------|------|
| Media Organizer | Sort files into date folders (EXIF, metadata, filename, or modified time). |
| Mass Video Encoder | Batch transcode with H.264, H.265, or AV1; software or hardware encoders when available. |
| AI Media Scanner | Local OpenCV / ONNX classification (no cloud upload for analysis). |
| AI Image / Video Upscaler | Optional AI upscaling workflows. |

GPU support is optional; CPU paths are available. After launch, wait until the footer shows **READY**, then open a panel and set paths or models as prompted.

**If something fails:** wait for **READY**, use each panel’s install/setup actions for engines and models, or open **HEALTH** / the **DEBUG** log path from the footer. Offline-only work continues when the network is unavailable; downloads may show **NO NETWORK**.

For JSON logs: set `CHRONOARCHIVER_JSON_LOG=1` before starting the app.

For **crash diagnostics**, the session debug log records **PID** and hints for **gdb** / **core** analysis. On Linux/macOS, if the app is **hung** (still running), `kill -USR2 <pid>` appends Python stack dumps to the same log; set `CHRONOARCHIVER_GDB_BACKTRACE=1` before that signal to also attempt a live **gdb** `thread apply all bt` (requires **gdb** and ptrace permission). Fatal native crashes may still omit Python stacks; use **core** files + **gdb** as logged.

## Privacy

Scanner and inference run on your machine unless you choose to move data elsewhere. See [SECURITY.md](SECURITY.md) for policy and reporting.

## Repository

| Resource | Link |
|----------|------|
| Changelog | [CHANGELOG.md](CHANGELOG.md) |
| Contributing | [CONTRIBUTING.md](CONTRIBUTING.md) |
| License | [LICENSE](LICENSE) |

Maintainer: [UnDadFeated](https://github.com/UnDadFeated).
