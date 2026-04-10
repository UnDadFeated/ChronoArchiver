"""Tests for remote path parsing (no live SSH)."""

from __future__ import annotations

from core.remote_ssh import (
    RemoteTarget,
    is_remote_path,
    parse_remote_destination,
    ssh_command_environment,
    to_sftp_folder_uri,
)


def test_parse_sftp_url_basic():
    r, _ = parse_remote_destination("sftp://htpc@192.168.4.112/mnt/media_hdd/Backup/")
    assert r is not None
    assert r.user == "htpc"
    assert r.host == "192.168.4.112"
    assert r.path == "/mnt/media_hdd/Backup/" or r.path.rstrip("/") == "/mnt/media_hdd/Backup"


def test_parse_user_at_host_colon_path():
    r, _ = parse_remote_destination("user@host.example:/var/tmp")
    assert r is not None
    assert r.user == "user"
    assert r.host == "host.example"
    assert r.path == "/var/tmp"


def test_local_path_not_remote():
    assert parse_remote_destination("/home/me/Videos")[0] is None
    assert is_remote_path("/tmp") is False


def test_is_remote_path():
    assert is_remote_path("sftp://a@b/c") is True
    assert is_remote_path("me@there:/x") is True


def test_to_sftp_folder_uri():
    r = RemoteTarget(host="h", path="/mnt/x", user="u")
    assert to_sftp_folder_uri(r) == "sftp://u@h/mnt/x/"


def test_sshpass_env_strips_askpass(monkeypatch):
    monkeypatch.setenv("SSH_ASKPASS", "/usr/bin/false")
    monkeypatch.setenv("SSH_ASKPASS_REQUIRE", "force")
    monkeypatch.setenv("GIT_ASKPASS", "/usr/bin/false")
    env = ssh_command_environment(None, "secret")
    assert env.get("SSHPASS") == "secret"
    assert "SSH_ASKPASS" not in env
    assert "SSH_ASKPASS_REQUIRE" not in env
    assert "GIT_ASKPASS" not in env
