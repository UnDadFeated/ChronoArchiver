"""Organizer EXIF orientation helpers."""

from __future__ import annotations

from core.organizer import _exif_orientation_value, _needs_exif_rotation


def test_exif_orientation_missing_file():
    assert _exif_orientation_value("/nonexistent/path/photo.jpg") is None
    assert _needs_exif_rotation("/nonexistent/path/photo.jpg") is False
