"""Tests for the global filesystem-heavy task lock (no I/O)."""

from __future__ import annotations

import threading

from core.fs_task_lock import fs_heavy_holder_label, release_fs_heavy, try_acquire_fs_heavy


def test_try_acquire_and_release():
    assert try_acquire_fs_heavy() is True
    release_fs_heavy()


def test_holder_label_tracks_named_task():
    assert try_acquire_fs_heavy("Unit Test Task") is True
    assert fs_heavy_holder_label() == "Unit Test Task"
    release_fs_heavy()
    assert fs_heavy_holder_label() is None


def test_second_acquire_fails_while_held():
    assert try_acquire_fs_heavy() is True
    try:
        assert try_acquire_fs_heavy() is False
    finally:
        release_fs_heavy()


def test_release_idempotent():
    assert try_acquire_fs_heavy() is True
    release_fs_heavy()
    release_fs_heavy()
    release_fs_heavy()


def test_concurrent_try_acquire_only_one_wins():
    """Both threads try at once; only one non-blocking acquire succeeds before release."""
    results: list[bool] = []
    start = threading.Barrier(2)
    synced = threading.Barrier(2)

    def worker():
        start.wait()
        ok = try_acquire_fs_heavy()
        results.append(ok)
        synced.wait()
        if ok:
            release_fs_heavy()

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert sorted(results) == [False, True]
