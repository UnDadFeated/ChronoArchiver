#!/usr/bin/env python3
"""
Verify SemVer alignment across canonical files (run from repo root).
Used by .github/workflows/version-consistency.yml. Exit 1 on mismatch.

Also ensures EMBEDDED_RELEASE_NOTES in changelog_notes.py includes the current __version__
(offline what’s-new); run tools/bump_version.py and copy CHANGELOG after bumping.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    v_py = (ROOT / "src" / "version.py").read_text(encoding="utf-8")
    m = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', v_py, re.M)
    if not m:
        print("Could not parse src/version.py", file=sys.stderr)
        return 1
    ver = m.group(1)
    errors: list[str] = []

    pj = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m2 = re.search(r'^version\s*=\s*"([^"]+)"', pj, re.M)
    if not m2 or m2.group(1) != ver:
        errors.append(f'pyproject.toml [project].version must be "{ver}"')

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if f"version-{ver}-blue" not in readme:
        errors.append(f"README.md badge must contain version-{ver}-blue")
    if f"Release **{ver}**" not in readme:
        errors.append(f"README.md must contain Release **{ver}**")

    pkg = (ROOT / "PKGBUILD").read_text(encoding="utf-8")
    m3 = re.search(r"^pkgver=([^\s#]+)", pkg, re.M)
    if not m3 or m3.group(1).strip() != ver:
        errors.append(f"PKGBUILD pkgver must be {ver}")

    sl = (ROOT / "tools" / "setup_launcher.py").read_text(encoding="utf-8")
    if not re.search(
        r'get\(\s*["\']CHRONOARCHIVER_VERSION["\']\s*,\s*["\']' + re.escape(ver) + r'["\']\s*\)',
        sl,
    ):
        errors.append("tools/setup_launcher.py default CHRONOARCHIVER_VERSION mismatch")

    spec = (ROOT / "tools" / "chronoarchiver_setup.spec").read_text(encoding="utf-8")
    if not re.search(
        r'get\(\s*["\']CHRONOARCHIVER_VERSION["\']\s*,\s*["\']' + re.escape(ver) + r'["\']\s*\)',
        spec,
    ):
        errors.append("tools/chronoarchiver_setup.spec default CHRONOARCHIVER_VERSION mismatch")

    cn = (ROOT / "src" / "core" / "changelog_notes.py").read_text(encoding="utf-8")
    if not re.search(rf'["\']{re.escape(ver)}["\']\s*:\s*"""', cn):
        errors.append(
            f'src/core/changelog_notes.py EMBEDDED_RELEASE_NOTES must include a """{ver}""" entry '
            "(copy ## block from CHANGELOG.md after bump)"
        )

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1
    print("OK", ver)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
