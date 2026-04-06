"""First-run / on-demand health summary (environment + disk; no network upload)."""

from __future__ import annotations

import shutil

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

SECURITY_POLICY_URL = "https://github.com/UnDadFeated/ChronoArchiver/blob/main/SECURITY.md"

from core.app_paths import data_dir
from core.debug_info import format_debug_bundle


def _disk_line() -> str:
    try:
        usage = shutil.disk_usage(data_dir())
        free_gb = usage.free / (1024**3)
        total_gb = usage.total / (1024**3)
        return f"Disk (data dir root): {free_gb:.1f} GB free of {total_gb:.1f} GB total\n"
    except OSError as e:
        return f"Disk: could not query ({e})\n"


class HealthSummaryDialog(QDialog):
    def __init__(self, parent=None, *, show_dismiss_checkbox: bool = False):
        super().__init__(parent)
        self.setWindowTitle("ChronoArchiver — health summary")
        self.setModal(True)
        self.setMinimumSize(520, 420)

        v = QVBoxLayout(self)
        intro = QLabel(
            "Environment summary and disk space. Prerequisites also appear in the footer "
            "after startup. Nothing here is sent to the internet automatically."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("font-size: 10px; color: #9ca3af;")
        v.addWidget(intro)

        body = format_debug_bundle().rstrip() + "\n\n" + _disk_line()
        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText(body)
        te.setStyleSheet(
            "font-family: 'JetBrains Mono', 'DejaVu Sans Mono', monospace; "
            "font-size: 9px; background: #0d0d0d; color: #e5e7eb;"
        )
        v.addWidget(te)

        self._chk_dismiss: QCheckBox | None = None
        if show_dismiss_checkbox:
            self._chk_dismiss = QCheckBox("Do not show this summary automatically on startup")
            self._chk_dismiss.setStyleSheet("font-size: 10px; color: #d1d5db;")
            v.addWidget(self._chk_dismiss)

        links = QHBoxLayout()
        sec = QPushButton("Security policy…")
        sec.setStyleSheet("font-size: 9px; color: #93c5fd;")
        sec.setAccessibleDescription("Opens the security and privacy policy in your web browser")
        sec.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(SECURITY_POLICY_URL)))
        links.addWidget(sec)
        links.addStretch()
        v.addLayout(links)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        ok_btn = bb.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setText("OK")
        ok_btn.setDefault(True)
        ok_btn.setAutoDefault(True)
        bb.accepted.connect(self.accept)
        v.addWidget(bb)

        self.setStyleSheet("QDialog { background: #0c0c0c; }")
