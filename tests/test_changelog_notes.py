"""Tests for CHANGELOG section extraction."""

from __future__ import annotations

from pathlib import Path

from version import __version__

from core.changelog_notes import (
    changelog_section_for_version,
    read_changelog_markdown,
    release_notes_for_version,
)


def test_changelog_section_for_version_extracts_block():
    md = """## [Unreleased]

## [5.4.0] - 2026-04-03

### Added
- Alpha feature

## [5.3.0] - 2026-04-03

### Added
- Older
"""
    s = changelog_section_for_version(md, "5.4.0")
    assert s is not None
    assert "5.4.0" in s
    assert "Alpha feature" in s
    assert "Older" not in s


def test_read_changelog_matches_repo_file():
    text, path = read_changelog_markdown()
    assert text is not None and path is not None
    assert path.name == "CHANGELOG.md"
    assert "## [" in text
    root = Path(__file__).resolve().parents[1]
    assert path.resolve() == (root / "CHANGELOG.md").resolve()


def test_release_notes_prefers_local_changelog():
    text, path, src = release_notes_for_version(__version__)
    assert src == "local"
    assert len(text) > 20


def test_release_notes_embedded_when_offline(monkeypatch):
    monkeypatch.setattr("core.changelog_notes.read_changelog_markdown", lambda: (None, None))
    monkeypatch.setattr("core.changelog_notes.fetch_changelog_raw_from_github", lambda timeout_s=12.0: None)
    text, path, src = release_notes_for_version("5.4.2")
    assert src == "embedded"
    assert path is None
    assert "EXIF" in text
