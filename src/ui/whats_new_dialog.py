"""Dismissible reminder after upgrading to a new app version."""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from core.changelog_notes import CHANGELOG_BLOB_URL, release_notes_for_version


class WhatsNewDialog(QDialog):
    def __init__(self, parent=None, *, version: str):
        super().__init__(parent)
        self.setWindowTitle(f"ChronoArchiver — what's new in {version}")
        self.setModal(True)
        self.setMinimumSize(520, 380)

        v = QVBoxLayout(self)
        section, path, source = release_notes_for_version(version)
        source_hint = {
            "local": "",
            "embedded": " (bundled highlights)",
            "network": " (loaded from GitHub)",
            "fallback": "",
        }.get(source, "")
        intro = QLabel(
            f"You are now running ChronoArchiver {version}. "
            f"Highlights for this version are below{source_hint}. "
            "The full history is in CHANGELOG.md or on GitHub."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("font-size: 11px; color: #e5e7eb;")
        v.addWidget(intro)

        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText(section[:14_000] + ("…" if len(section) > 14_000 else ""))
        te.setStyleSheet(
            "font-family: 'JetBrains Mono', 'DejaVu Sans Mono', monospace; "
            "font-size: 9px; background: #0d0d0d; color: #e5e7eb;"
        )
        v.addWidget(te)

        self._chk_suppress = QCheckBox("Do not show release notes after future updates")
        self._chk_suppress.setStyleSheet("font-size: 10px; color: #d1d5db;")
        v.addWidget(self._chk_suppress)

        row = QHBoxLayout()
        view = QPushButton("View changelog…")
        view.setStyleSheet("font-size: 9px; color: #93c5fd;")
        view.setAccessibleDescription("Opens the full changelog in the browser or local viewer")
        view.clicked.connect(self._open_changelog)
        row.addWidget(view)
        row.addStretch()
        v.addLayout(row)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        ok_btn = bb.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setText("OK")
        ok_btn.setDefault(True)
        bb.accepted.connect(self.accept)
        v.addWidget(bb)

        self._changelog_path = path  # may be None; View changelog uses browser fallback
        self.setStyleSheet("QDialog { background: #0c0c0c; }")

    def suppress_future(self) -> bool:
        return self._chk_suppress.isChecked()

    def _open_changelog(self) -> None:
        if self._changelog_path is not None and self._changelog_path.is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._changelog_path.resolve())))
        else:
            QDesktopServices.openUrl(QUrl(CHANGELOG_BLOB_URL))
