"""Activity context for crash logs."""

from __future__ import annotations

from core.debug_logger import get_activity_context, set_activity_context


def test_set_activity_context_roundtrip():
    set_activity_context("panel=Test activity=idle")
    assert "Test" in get_activity_context()
    assert "idle" in get_activity_context()
