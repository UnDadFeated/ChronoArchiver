"""Load CHANGELOG.md and extract the section for a given version (release notes UI)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Public web fallbacks when no local CHANGELOG is available (e.g. some frozen layouts).
CHANGELOG_BLOB_URL = "https://github.com/UnDadFeated/ChronoArchiver/blob/main/CHANGELOG.md"
CHANGELOG_RAW_URL = "https://raw.githubusercontent.com/UnDadFeated/ChronoArchiver/main/CHANGELOG.md"


def changelog_file_candidates() -> list[Path]:
    """Paths to try for CHANGELOG.md (git layout, then PyInstaller bundle)."""
    core = Path(__file__).resolve().parent
    out: list[Path] = []
    # src/core directory -> parents[1] = repository root (parents[0] is src/)
    out.append(core.parents[1] / "CHANGELOG.md")
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            out.append(Path(meipass) / "CHANGELOG.md")
    return out


def read_changelog_markdown() -> tuple[str | None, Path | None]:
    """
    Returns (markdown text, path) if a readable file was found; else (None, None).
    """
    for p in changelog_file_candidates():
        try:
            if p.is_file():
                return p.read_text(encoding="utf-8", errors="replace"), p
        except OSError:
            continue
    return None, None


def changelog_section_for_version(body: str, version: str) -> str | None:
    """Return the full markdown block for ``## [version]`` through the next ``## [`` or EOF."""
    if not body or not version:
        return None
    pat = rf"(?ms)^## \[{re.escape(version.strip())}\].*?(?=^## \[|\Z)"
    m = re.search(pat, body)
    return m.group(0).strip() if m else None
