"""Instantiate main window offscreen (CI skips update polling)."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PySide6")


def test_chronoarchiver_main_window_smoke():
    os.environ["CHRONOARCHIVER_CI"] = "1"
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import sys

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    from ui.app import ChronoArchiverApp

    w = ChronoArchiverApp()
    try:
        w.show()
        app.processEvents()
        for i in range(w.stack.count()):
            w._switch_panel(i)
            app.processEvents()
            assert w.stack.currentIndex() == i
    finally:
        w.close()
        app.processEvents()
