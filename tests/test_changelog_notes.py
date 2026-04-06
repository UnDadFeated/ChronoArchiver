"""Tests for CHANGELOG section extraction."""

from __future__ import annotations

from pathlib import Path

from core.changelog_notes import changelog_section_for_version, read_changelog_markdown


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
