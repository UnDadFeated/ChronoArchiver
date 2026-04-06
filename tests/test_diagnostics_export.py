"""Diagnostic ZIP export (local file only)."""

from __future__ import annotations

import zipfile

from core.diagnostics_export import write_diagnostic_zip


def test_write_diagnostic_zip_contains_files(tmp_path):
    p = tmp_path / "d.zip"
    write_diagnostic_zip(p)
    assert p.is_file()
    with zipfile.ZipFile(p) as zf:
        names = set(zf.namelist())
    assert "README.txt" in names
    assert "environment.txt" in names
    assert "log_tail.txt" in names
