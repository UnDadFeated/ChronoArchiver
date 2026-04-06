"""Unit tests for install vs user data path resolution (no GUI)."""

from __future__ import annotations

from pathlib import Path

import pytest

from core import app_paths


@pytest.fixture
def clear_install_root(monkeypatch):
    monkeypatch.delenv(app_paths.ENV_INSTALL_ROOT, raising=False)


def test_install_root_unset(clear_install_root):
    assert app_paths.install_root() is None
    assert app_paths.uses_install_layout() is False


def test_install_root_set(monkeypatch, tmp_path: Path):
    root = tmp_path / "install"
    root.mkdir()
    monkeypatch.setenv(app_paths.ENV_INSTALL_ROOT, str(root))
    assert app_paths.install_root() == root.resolve()
    assert app_paths.uses_install_layout() is True
    assert app_paths.data_dir() == root.resolve()
    assert (app_paths.settings_dir().name) == "Settings"
    assert "Settings" in str(app_paths.settings_dir())


def test_data_dir_user_mode(clear_install_root):
    """Without install root, data_dir resolves to a per-user application path."""
    d = app_paths.data_dir()
    assert app_paths.APP_NAME in str(d)
