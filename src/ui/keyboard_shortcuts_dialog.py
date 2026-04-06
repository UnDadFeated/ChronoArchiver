"""Keyboard shortcuts reference (non-modal help)."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextEdit, QVBoxLayout

_TEXT = """\
Main window
  Ctrl+Shift+D     Copy debug info (same as footer “COPY DEBUG INFO”)
  Ctrl+/           Open this shortcuts dialog

Dialogs
  Esc              Close dialog (Qt default)

Footer
  COPY CONSOLE, COPY DEBUG INFO, HEALTH, SHORTCUTS, SECURITY, EXPORT DIAGNOSTICS, DEBUG
  — hover each control for details.

Updates
  After upgrading to a new version, a one-time “what’s new” dialog may appear (dismissible;
  optional “do not show” for future upgrades).

Panels
  Tab / Shift+Tab  Move between fields and buttons
  Primary actions  Start, Upscale, Browse — see tooltips when disabled
"""


class KeyboardShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ChronoArchiver — keyboard shortcuts")
        self.setModal(True)
        self.setMinimumSize(440, 320)
        v = QVBoxLayout(self)
        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText(_TEXT.strip())
        te.setStyleSheet(
            "font-family: 'JetBrains Mono', 'DejaVu Sans Mono', monospace; "
            "font-size: 10px; background: #0d0d0d; color: #e5e7eb;"
        )
        v.addWidget(te)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        bb.accepted.connect(self.accept)
        v.addWidget(bb)
        self.setStyleSheet("QDialog { background: #0c0c0c; }")
