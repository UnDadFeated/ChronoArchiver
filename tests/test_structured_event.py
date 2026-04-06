"""structured_event is a no-op when CHRONOARCHIVER_JSON_LOG is unset."""

from __future__ import annotations


def test_structured_event_noop_without_env(monkeypatch):
    monkeypatch.delenv("CHRONOARCHIVER_JSON_LOG", raising=False)
    from core.debug_logger import structured_event

    structured_event("test_event", foo=1)
