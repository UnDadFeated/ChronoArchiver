"""Unit tests for centralized error codes database."""

from __future__ import annotations

from core.errors import AppErrorCode, format_error_msg


def test_error_detail_attributes():
    code = AppErrorCode.VENV_INTERPRETER_NOT_FOUND
    assert code.value.code == "E101"
    assert code.value.area == "Venv / Setup"
    assert "interpreter" in code.value.description.lower()
    assert "PATH" in code.value.possible_fixes


def test_format_error_msg():
    code = AppErrorCode.ORGANIZER_SRC_NOT_FOUND
    msg = format_error_msg(code)
    assert "[E201]" in msg
    assert "Media Organizer" in msg
    assert "Possible Fix" in msg


def test_format_error_msg_with_context():
    code = AppErrorCode.ENCODER_FFMPEG_MISSING
    msg = format_error_msg(code, "my_custom_context")
    assert "[E301]" in msg
    assert "my_custom_context" in msg
