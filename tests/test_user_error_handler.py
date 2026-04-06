"""User error banner handler routing."""

from __future__ import annotations

import logging

from core.user_error_log_handler import UserErrorBannerHandler, user_error_banner_should_clear


def test_clear_banner_heuristics():
    assert user_error_banner_should_clear("Encoding batch complete.")
    assert user_error_banner_should_clear("Batch organization complete.")
    assert not user_error_banner_should_clear("ERROR: disk full")


def test_handler_emits_error_and_clear():
    errors: list[str] = []
    clears: list[bool] = []

    def on_error(m: str):
        errors.append(m)

    def on_clear():
        clears.append(True)

    h = UserErrorBannerHandler(on_error, on_clear)
    lg = logging.getLogger("test_user_err")
    lg.setLevel(logging.INFO)
    lg.addHandler(h)
    lg.propagate = False

    lg.info("ERROR: something failed")
    lg.info("Encoding batch complete.")
    assert errors == ["ERROR: something failed"]
    assert clears == [True]
    lg.removeHandler(h)
