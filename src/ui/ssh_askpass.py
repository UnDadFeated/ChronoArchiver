#!/usr/bin/env python3
"""SSH_ASKPASS helper: OpenSSH invokes this when no TTY is available."""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication, QInputDialog, QLineEdit
    except ImportError:
        return 1

    app = QApplication(["chronoarchiver-ssh-askpass"])
    try:
        prompt = sys.argv[1] if len(sys.argv) > 1 else "Password:"
        text, ok = QInputDialog.getText(
            None,
            "SSH authentication",
            prompt,
            QLineEdit.EchoMode.Password,
        )
        if ok and text is not None:
            sys.stdout.write(text)
            sys.stdout.flush()
        return 0 if ok else 1
    finally:
        app.quit()
        app.deleteLater()
        app.processEvents()


if __name__ == "__main__":
    raise SystemExit(main())
