# WALKTHROUGH.md

# Walkthrough: ChronoArchiver v1.0.16 (Layout Fix & Icon Perfection)
- **GUI Stability**: Resolved a critical startup crash (`_tkinter.TclError`) in the AV1 Encoder tab by correcting an invalid layout parameter.
- **Full-Frame Icon Mastery**: Re-generated the application icon with a zero-padding "Full Frame" motif and intrinsic rounded corners. The icon now occupies 100% of the available taskbar/desktop tile space.
- **Global Release**: Synchronized version `v1.0.16` across GitHub and the official AUR repository.

---

# Walkthrough: ChronoArchiver v1.0.15 (Dependency & Icon Polish)
- **Dependency Resolution**: Corrected `PKGBUILD` to depend on `python-opencv` instead of `opencv`.
- **AUR Metadata Sync**: Forced a `pkgver=1.0.15` update.

---

# Walkthrough: ChronoArchiver v1.0.14 (Architecture & Refined Branding)
- **Architecture Stabilization**: Resolved a critical circular import between `app.py` and `tabs.py`.
