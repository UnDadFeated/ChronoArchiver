"""Debug bundle formatting (imports core + version)."""

from __future__ import annotations

from version import __version__

from core.debug_info import format_debug_bundle


def test_format_debug_bundle_contains_version_and_paths():
    text = format_debug_bundle()
    assert __version__ in text
    assert "ChronoArchiver" in text
    assert "sys.executable:" in text
    assert "App venv root:" in text
    assert "ffmpeg" in text.lower()
