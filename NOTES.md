# NOTES.md

<HISTORY_RESERVED_DO_NOT_REMOVE>
### v1.0.16 Notes
- Fixed `_tkinter.TclError: bad option "-width"` in `AV1EncoderTab` by removing the invalid `width` parameter from the `.pack()` call.
- Re-generated the application icon with a "Full Frame" motif and intrinsic rounded corners. The motif now occupies 100% of the canvas with zero padding, maximizing taskbar presence.
- Synchronized version 1.0.16 globally across GitHub and AUR.

### v1.0.15 Notes
- Fixed `ModuleNotFoundError: No module named 'cv2'` by correctly identifying `python-opencv` as the required dependency in `PKGBUILD`.
- Corrected AUR metadata by bumping `pkgver=1.0.15` to trigger update notifications for AUR users.
- Refined the premium icon for a pixel-perfect "top-to-bottom" vertical fit. Motif now occupies exactly 256px height with zero padding and absolute alpha transparency.
- Synchronized version 1.0.15 globally across GitHub and AUR.

### v1.0.14 Notes
- Resolved critical `ImportError` by extracting shared UI constants into `src/ui/theme.py`.
- Refactor of `src/ui/tabs.py` into a package `src/ui/tabs/__init__.py` to resolve the directory/file namespace conflict.
- Refined the premium icon: removed initial background artifacts, implemented alpha transparency.

### v1.0.13 Notes
- Integrated the catchline "Time to Archive!" into the UI (`self.title` and a new label in `console_header`).
- Catchline label uses `italic` style and `ACCENT` color for visual distinction.
- Synchronized catchline in `README.md`, `PKGBUILD`, and `chronoarchiver.desktop`.

### v1.0.12 Notes
- Integrated a new high-fidelity application icon ("premium glassmorphism" style).
- Updated `PKGBUILD` and `chronoarchiver.desktop` to properly install and reference the system-wide icon path (`/usr/share/pixmaps/chronoarchiver.png`).
- Performed a global version bump to `1.0.12` and synchronized across GitHub and AUR.
