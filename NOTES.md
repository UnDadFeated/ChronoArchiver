# NOTES.md

<HISTORY_RESERVED_DO_NOT_REMOVE>
### v1.0.16 Notes
- Fixed `_tkinter.TclError: bad option "-width"` in `AV1EncoderTab` by removing the invalid `width` parameter from the `.pack()` call.
- Re-generated the application icon with a "Full Frame" motif and intrinsic rounded corners. The motif now occupies 100% of the canvas with zero padding, maximizing taskbar presence.
- Synchronized version 1.0.16 globally across GitHub and AUR.

### v1.0.15 Notes
- Fixed `ModuleNotFoundError: No module named 'cv2'` by correctly identifying `python-opencv` as the required dependency in `PKGBUILD`.
- Corrected AUR metadata by bumping `pkgver=1.0.15` to trigger update notifications for AUR users.
- Refined the premium icon for a pixel-perfect "top-to-bottom" vertical fit.

### v1.0.14 Notes
- Resolved critical `ImportError` by extracting shared UI constants into `src/ui/theme.py`.
- Refactor of `src/ui/tabs.py` into a package `src/ui/tabs/__init__.py`.
