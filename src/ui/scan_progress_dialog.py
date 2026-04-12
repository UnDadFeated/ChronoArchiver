"""
Modal-less scan progress dialog — shared by Mass AV1 Encoder, Media Organizer, etc.
"""

from __future__ import annotations

import time

from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar
from PySide6.QtGui import QCloseEvent, QShowEvent

from core.debug_logger import log_installer_popup, INSTALLER_APP_MASS_AV1_ENCODER


class ScanProgressDialog(QDialog):
    """Separate window showing file count and total size during a directory scan."""

    def __init__(
        self,
        parent=None,
        *,
        title: str = "Scanning Source",
        log_app: str = INSTALLER_APP_MASS_AV1_ENCODER,
    ):
        super().__init__(parent)
        self._log_app = log_app
        self.setWindowTitle(title)
        self.setModal(False)
        self.setFixedSize(320, 120)
        v = QVBoxLayout(self)
        v.setSpacing(8)
        v.setContentsMargins(12, 12, 12, 12)
        self._lbl_files = QLabel("Files: 0")
        self._lbl_files.setStyleSheet("font-size:12px; font-weight:600; color:#10b981;")
        v.addWidget(self._lbl_files)
        self._lbl_size = QLabel("Total size: 0 B")
        self._lbl_size.setStyleSheet("font-size:11px; color:#aaa;")
        v.addWidget(self._lbl_size)
        self._bar = QProgressBar()
        self._bar.setRange(0, 0)
        self._bar.setFixedHeight(12)
        v.addWidget(self._bar)
        self.setStyleSheet("QDialog { background: #0d0d0d; }")
        self._last_scan_log_ts = 0.0
        self._last_scan_count = 0

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        log_installer_popup(self._log_app, "ScanProgressDialog", "opened")

    def closeEvent(self, event: QCloseEvent) -> None:
        log_installer_popup(self._log_app, "ScanProgressDialog", "closed")
        super().closeEvent(event)

    def update_progress(self, count: int, total_bytes: object):
        self._lbl_files.setText(f"Files: {count}")
        try:
            tb = int(total_bytes)
        except (TypeError, ValueError):
            tb = 0
        total_bytes = max(0, tb)
        if total_bytes >= 1024**3:
            sz = f"{total_bytes / (1024**3):.2f} GB"
        elif total_bytes >= 1024**2:
            sz = f"{total_bytes / (1024**2):.1f} MB"
        elif total_bytes >= 1024:
            sz = f"{total_bytes / 1024:.1f} KB"
        else:
            sz = f"{total_bytes} B"
        self._lbl_size.setText(f"Total size: {sz}")
        now = time.monotonic()
        if count >= self._last_scan_count + 500 or (now - self._last_scan_log_ts) >= 5.0:
            self._last_scan_log_ts = now
            self._last_scan_count = count
            log_installer_popup(
                self._log_app,
                "ScanProgressDialog",
                "progress",
                f"files={count} total_bytes={total_bytes}",
            )
