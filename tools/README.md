# Build Tools for ChronoArchiver

## Installers (Windows x64 / macOS)

Installers are built automatically by GitHub Actions when you push a version tag (e.g. `v3.5.0`). The workflow produces:

- **Windows**: `ChronoArchiver-3.5.0-win64.exe` (Inno Setup)
- **macOS**: `ChronoArchiver-3.5.0-mac64.dmg`

These appear on the [Releases](https://github.com/UnDadFeated/ChronoArchiver/releases) page.

## Building locally

**Requirements:** Python 3.10+, PyInstaller, all app dependencies. Build on the target OS (Windows for .exe, macOS for .dmg).

### Windows

```powershell
pip install -r requirements.txt pyinstaller static-ffmpeg opencv-python GitPython
pyinstaller tools/chronoarchiver.spec
# Install Inno Setup, then:
iscc tools/ChronoArchiver.iss
# Output: dist/ChronoArchiver-3.5.0-win64.exe
```

### macOS

```bash
pip install -r requirements.txt pyinstaller static-ffmpeg opencv-python GitPython
pyinstaller tools/chronoarchiver.spec
# Create DMG manually or use create-dmg
```

## Files

- `chronoarchiver.spec` — PyInstaller spec (entry: `src/bootstrap.py`)
- `ChronoArchiver.iss` — Inno Setup script for Windows installer
- `../.github/workflows/release-installers.yml` — CI build workflow
