"""Filesystem time preservation (POSIX): mtime set, atime preserved."""

from __future__ import annotations

import os
import tempfile

import pytest

from datetime import datetime, timezone

from core.media_capture_time import (
    _epoch_prefer_mtime_when_metadata_is_midnight_same_day,
    _parse_tag_datetime,
    _unix_epoch_to_win32_filetime_intervals,
    _win32_createfile_failed,
    apply_preserved_filesystem_times,
    epoch_to_ffmpeg_creation_metadata,
    ffmpeg_metadata_creation_args,
)


def test_unix_epoch_to_win32_filetime_unix_zero_anchor():
    """Unix 0 → FILETIME 100-ns count (1601 → 1970 offset)."""
    assert _unix_epoch_to_win32_filetime_intervals(0.0) == 116444736000000000


def test_unix_epoch_to_win32_filetime_pre_1601_returns_none():
    assert _unix_epoch_to_win32_filetime_intervals(-20000000000.0) is None


def test_win32_createfile_failed_sentinels():
    assert _win32_createfile_failed(-1) is True
    assert _win32_createfile_failed(0xFFFFFFFFFFFFFFFF) is True
    assert _win32_createfile_failed(0xFFFFFFFF) is True
    assert _win32_createfile_failed(None) is True
    assert _win32_createfile_failed(42) is False


def test_parse_tag_datetime_z_preserves_utc_instant():
    dt = _parse_tag_datetime("2023-03-15T21:31:09.000000Z")
    assert dt is not None
    assert dt.tzinfo == timezone.utc
    want = datetime(2023, 3, 15, 21, 31, 9, tzinfo=timezone.utc).timestamp()
    assert abs(dt.timestamp() - want) < 0.02


def test_prefer_mtime_when_metadata_midnight_same_day():
    dt_meta = datetime(2023, 3, 15, 0, 0, 0)
    dt_m = datetime(2023, 3, 15, 21, 31, 9)
    ep_m = dt_m.timestamp()
    assert _epoch_prefer_mtime_when_metadata_is_midnight_same_day(dt_meta, ep_m) == ep_m


def test_prefer_metadata_when_it_has_real_time():
    dt_meta = datetime(2023, 3, 15, 14, 30, 0)
    dt_m = datetime(2023, 3, 15, 21, 31, 9)
    ep_meta = dt_meta.timestamp()
    assert _epoch_prefer_mtime_when_metadata_is_midnight_same_day(dt_meta, dt_m.timestamp()) == ep_meta


def test_ffmpeg_metadata_creation_args_sets_format_and_video_stream():
    args = ffmpeg_metadata_creation_args(1_700_000_000.0)
    assert args[0] == "-metadata"
    assert args[2] == "-metadata:s:v:0"
    assert args[1] == args[3]
    assert args[1].startswith("creation_time=")


def test_epoch_to_ffmpeg_creation_metadata_round_trip_parse():
    """Local-offset ISO string must resolve to the same Unix instant as the input epoch."""
    epoch = 1_700_000_000.0
    raw = epoch_to_ffmpeg_creation_metadata(epoch)
    assert raw
    dt = _parse_tag_datetime(raw)
    assert dt is not None
    assert abs(dt.timestamp() - epoch) < 1.0


@pytest.mark.skipif(os.name == "nt", reason="Windows uses SetFileTime path")
def test_apply_preserved_filesystem_times_posix_sets_atime_when_epoch_requested():
    fd, path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    try:
        epoch = 1_700_000_000.0
        os.utime(path, (100.0, 200.0))
        assert apply_preserved_filesystem_times(path, epoch, posix_atime="epoch") is True
        st = os.stat(path)
        assert abs(st.st_mtime - epoch) < 1.0
        assert abs(st.st_atime - epoch) < 1.0
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


@pytest.mark.skipif(os.name == "nt", reason="Windows uses SetFileTime path")
def test_apply_preserved_filesystem_times_sets_mtime_preserves_atime():
    fd, path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    try:
        os.utime(path, (1000.0, 2000.0))
        st0 = os.stat(path)
        epoch = 1_700_000_000.0
        assert apply_preserved_filesystem_times(path, epoch) is True
        st1 = os.stat(path)
        assert abs(st1.st_mtime - epoch) < 1.0
        assert abs(st1.st_atime - st0.st_atime) < 0.001
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
