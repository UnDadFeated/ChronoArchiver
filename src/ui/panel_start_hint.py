"""Tooltips explaining why the primary action (Start / Upscale) is disabled."""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton


def apply_start_button_hint(
    btn: QPushButton,
    *,
    enabled: bool,
    reasons_when_disabled: list[str],
    enabled_tip: str = "",
) -> None:
    """When ``enabled`` is False, show a short combined reason on hover."""
    if enabled:
        btn.setToolTip(enabled_tip)
        return
    if reasons_when_disabled:
        btn.setToolTip("Cannot start: " + "; ".join(reasons_when_disabled) + ".")
    else:
        btn.setToolTip("Cannot start: fix the items highlighted by the guide.")
