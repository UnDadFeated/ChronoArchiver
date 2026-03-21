# WALKTHROUGH.md

# Walkthrough: ChronoArchiver v1.0.16 (Layout Fix & Icon Perfection)
- **GUI Stability**: Resolved a critical startup crash (`_tkinter.TclError`) in the AV1 Encoder tab by correcting an invalid layout parameter.
- **Full-Frame Icon Mastery**: Re-generated the application icon with a zero-padding "Full Frame" motif and intrinsic rounded corners. The icon now occupies 100% of the available taskbar/desktop tile space.
- **Global Release**: Synchronized version `v1.0.16` across GitHub and the official AUR repository.

---

# Walkthrough: ChronoArchiver v1.0.15 (Dependency & Icon Polish)
- **Dependency Resolution**: Corrected `PKGBUILD` to depend on `python-opencv` instead of `opencv`, resolving the `ModuleNotFoundError: No module named 'cv2'`.
- **AUR Metadata Sync**: Forced a `pkgver=1.0.15` update in the AUR repository.
- **Pixel-Perfect Icon Scaling**: Re-processed the premium icon motif to fit exactly 256px height.

---

# Walkthrough: ChronoArchiver v1.0.14 (Architecture & Refined Branding)
- **Architecture Stabilization**: Resolved a critical circular import between `app.py` and `tabs.py` by centralizing UI constants in `theme.py`.
- **Refactored Tabs**: Moved `ui/tabs.py` to `ui/tabs/__init__.py`.
- **Refined Icon**: Initial regeneration with transparency and tight framing.

---

# Walkthrough: ChronoArchiver v1.0.13 (Brand Catchline)
- **Official Catchline**: Integrated "Time to Archive!" into the application title bar and log console header.
- **Unified Branding**: Synchronized the catchline across `README.md`, `PKGBUILD`, and `chronoarchiver.desktop`.
- **Global Release**: Bumped version to `v1.0.13` and synchronized GitHub/AUR.

---

# Walkthrough: ChronoArchiver v1.0.12 (Premium Icon Branding)
- **Integrated High-Fidelity Icon**: Added a modern glassmorphism brand identity.
- **System-Wide Icon Install**: Fixed `PKGBUILD` to install the PNG icon to `/usr/share/pixmaps/`.
- **Sync**: Tagged v1.0.12 and synchronized GitHub and the AUR.
