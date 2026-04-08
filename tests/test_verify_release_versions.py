"""Release metadata verifier (must pass on every commit)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_verify_release_versions_script_exits_zero():
    r = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "verify_release_versions.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr + r.stdout
