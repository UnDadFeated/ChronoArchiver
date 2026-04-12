"""
Best-effort original capture / recording time for photos and videos.

Used app-wide to:
- Resolve a single datetime from embedded metadata, then filename/parent heuristics, then filesystem times.
- Apply filesystem times on outputs: **modified** time always; **created** on Windows via
  ``SetFileTime``; on Linux, **birth time** (KDE “Created”) is preserved when updating MP4s by
  overwriting the file in place instead of ``rename``-replacing with a new inode. **atime** is left
  unchanged unless callers choose otherwise.
- Provide FFmpeg ``-metadata creation_time=...`` fragments for re-encoded video.

Priority (images): EXIF DateTimeOriginal / Digitized → ffprobe container tags → filename → parent
folders → mtime → birth time (when available).

Priority (videos): ffprobe format/stream tags (``creation_time``, QuickTime date, etc.) → rare EXIF
→ filename → parent → mtime → birth time.

Other file types: filename → parent → mtime → birth time.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import Callable, Optional

try:
    import piexif
except ImportError:
    piexif = None  # type: ignore[misc, assignment]

MIN_YEAR = 1957

# Fix-media-dates idempotency: treat source-derived epoch vs target as matching within this window (seconds).
DATE_MATCH_TOLERANCE_SEC = 2.0

_PHOTO_EXTS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tiff",
    ".tif",
    ".webp",
    ".heic",
    ".heif",
    ".raw",
    ".dng",
    ".arw",
    ".cr2",
    ".nef",
    ".orf",
    ".rw2",
}
_VIDEO_EXTS = {
    ".mp4",
    ".mov",
    ".avi",
    ".webm",
    ".mkv",
    ".m4v",
    ".wmv",
    ".mpg",
    ".mpeg",
    ".ts",
    ".m2ts",
    ".3gp",
}


def _valid(dt: datetime) -> bool:
    return dt is not None and dt.year >= MIN_YEAR


def _is_local_midnight(dt: datetime) -> bool:
    """True if the clock reads 00:00:00 (date-only / midnight metadata)."""
    return (
        dt.hour == 0
        and dt.minute == 0
        and dt.second == 0
        and getattr(dt, "microsecond", 0) == 0
    )


def _local_wall_naive(dt: datetime) -> datetime:
    """Naive local wall time for calendar / “midnight” checks (aware → system local)."""
    if dt.tzinfo is not None:
        return dt.astimezone().replace(tzinfo=None)
    return dt


def _looks_like_date_only_or_midnight_tag(dt: datetime) -> bool:
    """
    True if metadata looks **date-only** precision: local midnight, or **UTC** 00:00:00 (common
    placeholder in ``creation_time``).
    """
    if _is_local_midnight(_local_wall_naive(dt)):
        return True
    if dt.tzinfo is not None:
        u = dt.astimezone(timezone.utc)
        if u.hour == 0 and u.minute == 0 and u.second == 0 and u.microsecond == 0:
            return True
    return False


def _epoch_prefer_mtime_when_metadata_is_midnight_same_day(
    dt_from_metadata: datetime,
    mtime_epoch: float,
) -> float:
    """
    When tags or path heuristics yield **local midnight** on the same calendar day as the file’s
    ``mtime``, but ``mtime`` carries a real time-of-day, prefer **mtime** (common for
    ``creation_time`` that only stores a date, or ``YYYY-MM-DD`` paths).
    """
    try:
        ep_meta = float(dt_from_metadata.timestamp())
    except (OverflowError, OSError, ValueError):
        return float(mtime_epoch)
    try:
        ep_m = float(mtime_epoch)
    except (TypeError, ValueError, OverflowError):
        return ep_meta
    try:
        dt_m = datetime.fromtimestamp(ep_m)
    except OSError:
        return ep_meta
    lw = _local_wall_naive(dt_from_metadata)
    if not _looks_like_date_only_or_midnight_tag(dt_from_metadata):
        return ep_meta
    if lw.date() != dt_m.date():
        return ep_meta
    if _is_local_midnight(dt_m):
        return ep_meta
    return ep_m


def _parse_tag_datetime(s: str) -> Optional[datetime]:
    s = (s or "").strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        # Keep **timezone-aware** for ISO strings. Stripping to naive and calling ``.timestamp()``
        # makes Python treat the wall clock as **local**, shifting UTC tags by several hours.
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)
            return dt if _valid(dt) else None
        return dt if _valid(dt) else None
    except ValueError:
        pass
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(s[:19] if len(s) >= 19 else s, fmt)
            return dt if _valid(dt) else None
        except ValueError:
            continue
    return None


def _datetime_from_image_exif(file_path: str) -> Optional[datetime]:
    if piexif is None:
        return None
    try:
        exif_dict = piexif.load(file_path)
        exif_section = exif_dict.get("Exif") or {}
        for tag_id in (36867, 36868):  # DateTimeOriginal, DateTimeDigitized
            if tag_id not in exif_section:
                continue
            raw = exif_section[tag_id]
            date_str = raw.decode("utf-8", errors="replace").strip()
            if len(date_str) < 19:
                continue
            date_str = date_str[:19]
            for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    dt = datetime.strptime(date_str, fmt)
                    if _valid(dt):
                        return dt
                except ValueError:
                    continue
    except (OSError, ValueError, TypeError, MemoryError, KeyError):
        pass
    return None


def _datetime_from_ffprobe_dict(data: dict) -> Optional[datetime]:
    """Prefer format tags, then first video stream tags (parsed ffprobe JSON)."""
    tag_keys = (
        "creation_time",
        "com.apple.quicktime.creationdate",
        "com.apple.quicktime.creationDate",
        "date",
        "creation_date",
        "DATE",
    )
    fmt_tags = (data.get("format") or {}).get("tags") or {}
    for k in tag_keys:
        if k in fmt_tags:
            dt = _parse_tag_datetime(str(fmt_tags[k]))
            if dt:
                return dt
    for stream in data.get("streams") or []:
        if (stream.get("codec_type") or "").lower() != "video":
            continue
        st = stream.get("tags") or {}
        for k in tag_keys:
            if k in st:
                dt = _parse_tag_datetime(str(st[k]))
                if dt:
                    return dt
        break
    return None


def _datetime_from_ffprobe_json(file_path: str) -> Optional[datetime]:
    """Prefer format tags, then first video stream tags."""
    try:
        raw = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                file_path,
            ],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=120,
        )
        data = json.loads(raw)
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError, ValueError):
        return None

    return _datetime_from_ffprobe_dict(data)


def _datetime_from_filename(file_path: str) -> Optional[datetime]:
    filename = os.path.basename(file_path)
    # Prefer a leading YYYY-MM-DD_ (or -) prefix from batch renamers / exports before scanning
    # the whole basename (avoids a spurious embedded date winning over an intentional prefix).
    # Require a separator or end after the day so "20240115" or partial tokens do not match.
    lead = re.match(r"^(\d{4})[-_](\d{2})[-_](\d{2})(?=[._\-]|$)", filename)
    if lead:
        y, m, d = lead.groups()
        try:
            dt = datetime.strptime(f"{y}{m}{d}", "%Y%m%d")
            if _valid(dt):
                return dt
        except ValueError:
            pass
    pattern = r"(\d{4})[-_]?(\d{2})[-_]?(\d{2})"
    match = re.search(pattern, filename)
    if match:
        y, m, d = match.groups()
        try:
            dt = datetime.strptime(f"{y}{m}{d}", "%Y%m%d")
            return dt if _valid(dt) else None
        except ValueError:
            pass
    return None


def _datetime_from_parent_dirs(file_path: str) -> Optional[datetime]:
    parent = os.path.dirname(file_path)
    for _ in range(3):
        if not parent or parent == os.path.dirname(parent):
            break
        pname = os.path.basename(parent)
        m = re.search(r"(\d{4})[-_]?(\d{2})[-_]?(\d{2})", pname)
        if m:
            y, mo, d = m.groups()
            try:
                dt = datetime.strptime(f"{y}{mo}{d}", "%Y%m%d")
                return dt if _valid(dt) else None
            except ValueError:
                pass
        parent = os.path.dirname(parent)
    return None


def _datetime_from_stat_mtime(file_path: str) -> Optional[datetime]:
    try:
        ts = pathlib.Path(file_path).stat().st_mtime
        dt = datetime.fromtimestamp(ts)
        return dt if _valid(dt) else None
    except OSError:
        return None


def _datetime_from_stat_birth(file_path: str) -> Optional[datetime]:
    try:
        st = os.stat(file_path)
        if hasattr(st, "st_birthtime"):
            dt = datetime.fromtimestamp(st.st_birthtime)
            return dt if _valid(dt) else None
        if os.name == "nt":
            dt = datetime.fromtimestamp(getattr(st, "st_ctime", st.st_mtime))
            return dt if _valid(dt) else None
    except OSError:
        pass
    return None


def resolve_best_capture_datetime(file_path: str) -> Optional[datetime]:
    """
    Return the best-effort capture / recording time as a naive local datetime.

    Order depends on whether the path looks like a photo or a video (by extension).
    """
    if not file_path or not os.path.isfile(file_path):
        return None
    ext = pathlib.Path(file_path).suffix.lower()
    is_video = ext in _VIDEO_EXTS
    is_photo = ext in _PHOTO_EXTS

    steps: list[Callable[[], Optional[datetime]]] = []

    if is_photo:
        steps.extend(
            [
                lambda: _datetime_from_image_exif(file_path),
                lambda: _datetime_from_ffprobe_json(file_path),
                lambda: _datetime_from_filename(file_path),
                lambda: _datetime_from_parent_dirs(file_path),
                lambda: _datetime_from_stat_mtime(file_path),
                lambda: _datetime_from_stat_birth(file_path),
            ]
        )
    elif is_video:
        steps.extend(
            [
                lambda: _datetime_from_ffprobe_json(file_path),
                lambda: _datetime_from_image_exif(file_path),
                lambda: _datetime_from_filename(file_path),
                lambda: _datetime_from_parent_dirs(file_path),
                lambda: _datetime_from_stat_mtime(file_path),
                lambda: _datetime_from_stat_birth(file_path),
            ]
        )
    else:
        steps.extend(
            [
                lambda: _datetime_from_ffprobe_json(file_path),
                lambda: _datetime_from_image_exif(file_path),
                lambda: _datetime_from_filename(file_path),
                lambda: _datetime_from_parent_dirs(file_path),
                lambda: _datetime_from_stat_mtime(file_path),
                lambda: _datetime_from_stat_birth(file_path),
            ]
        )

    for fn in steps:
        try:
            dt = fn()
            if dt is not None and _valid(dt):
                return dt
        except Exception:
            continue
    return None


def resolve_best_capture_epoch(file_path: str) -> Optional[float]:
    """UTC-ish epoch seconds suitable for ``os.utime`` (naive datetime → local interpretation)."""
    dt = resolve_best_capture_datetime(file_path)
    if dt is None:
        return None
    try:
        m = os.path.getmtime(file_path)
    except OSError:
        try:
            return float(dt.timestamp())
        except (OverflowError, OSError, ValueError):
            return None
    try:
        return float(_epoch_prefer_mtime_when_metadata_is_midnight_same_day(dt, m))
    except (OverflowError, OSError, ValueError):
        return None


def _apply_fs_times_posix(path: str, epoch: float, *, atime_mode: str = "preserve") -> bool:
    """
    Set **mtime** to ``epoch``.

    ``atime_mode`` ``"preserve"`` (default): keep existing **atime**. ``"epoch"``: set **atime** to
    ``epoch`` as well so “Accessed” matches capture when fixing dates (optional callers).
    """
    try:
        if atime_mode == "epoch":
            os.utime(path, (epoch, epoch))
        else:
            st = os.stat(path)
            os.utime(path, (st.st_atime, epoch))
        return True
    except OSError:
        return False


# Windows FILETIME: 100-ns intervals since 1601-01-01 UTC; same offset CPython uses for time.time() ↔ FILETIME.
_WIN32_FILETIME_UNIX_EPOCH_OFFSET_SEC = 11644473600.0


def _unix_epoch_to_win32_filetime_intervals(epoch: float) -> Optional[int]:
    """
    Return unsigned 64-bit count of 100-ns intervals since 1601-01-01, or None if out of range.
    """
    try:
        sec = float(epoch) + _WIN32_FILETIME_UNIX_EPOCH_OFFSET_SEC
        if sec < 0:
            return None
        # Cap avoids overflow in int() for absurd epochs; ~30828 CE upper bound for FILETIME.
        if sec > 1.0e12:
            return None
        return int(sec * 10000000.0)
    except (OverflowError, ValueError, TypeError):
        return None


def _win32_createfile_failed(handle: object) -> bool:
    """True if ``CreateFileW`` returned ``INVALID_HANDLE_VALUE`` (32- or 64-bit)."""
    if handle is None:
        return True
    try:
        v = int(handle)
    except (TypeError, ValueError):
        return True
    # Typical: -1 signed, or all-bits-one as unsigned 32/64-bit.
    if v == -1:
        return True
    if v == 0xFFFFFFFF:
        return True
    if v == 0xFFFFFFFFFFFFFFFF or v == (1 << 64) - 1:
        return True
    return False


def _apply_fs_times_windows(path: str, epoch: float) -> bool:
    """
    Set **creation** and **last modified** (``FILETIME``) to ``epoch``; leave **last access** unchanged.

    Explorer "Date created" and "Date modified" both follow these when the call succeeds.
    """
    import ctypes
    from ctypes import wintypes

    t = _unix_epoch_to_win32_filetime_intervals(epoch)
    if t is None:
        return _apply_fs_times_posix(path, epoch)

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    class FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

    def _intervals_to_filetime(intervals: int) -> FILETIME:
        return FILETIME(intervals & 0xFFFFFFFF, (intervals >> 32) & 0xFFFFFFFF)

    # Two structs: some SetFileTime implementations read parameters in an order where sharing one
    # buffer could theoretically matter; values are identical.
    ft_create = _intervals_to_filetime(t)
    ft_write = FILETIME(ft_create.dwLowDateTime, ft_create.dwHighDateTime)

    GENERIC_WRITE = 0x40000000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    FILE_SHARE_DELETE = 0x00000004
    OPEN_EXISTING = 3
    FILE_ATTRIBUTE_NORMAL = 0x80

    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.SetFileTime.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
    ]
    kernel32.SetFileTime.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    abspath = os.path.abspath(path)
    h = kernel32.CreateFileW(
        abspath,
        GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        None,
    )
    if _win32_createfile_failed(h):
        return _apply_fs_times_posix(path, epoch)
    try:
        # NULL last-access: preserve "Date accessed"; creation + modified = capture time.
        ok = kernel32.SetFileTime(
            h,
            ctypes.byref(ft_create),
            None,
            ctypes.byref(ft_write),
        )
        if not ok:
            return _apply_fs_times_posix(path, epoch)
        return True
    finally:
        kernel32.CloseHandle(h)


def apply_preserved_filesystem_times(
    path: str,
    epoch: Optional[float],
    *,
    posix_atime: str = "preserve",
) -> bool:
    """
    Best-effort: set filesystem **modified** time to the capture ``epoch``. Set **created** time
    to the same on **Windows** (``SetFileTime``).

    On **Linux**, filesystem “Created” (``statx`` birth time) cannot be set with ``utime``; it is
    preserved when MP4 metadata is rewritten by **truncating overwrite** (see
    ``_remux_mp4_inplace_creation_metadata``) instead of ``rename``-replacing the file.

    ``posix_atime``: ``"preserve"`` keeps **atime**; ``"epoch"`` sets **atime** to ``epoch`` as well
    (aligns “Accessed” with capture for **Fix media dates**).

    Returns True if at least the POSIX-style mtime update path succeeded.
    """
    if epoch is None or not path or not os.path.isfile(path):
        return False
    try:
        ep = float(epoch)
    except (TypeError, ValueError, OverflowError):
        return False
    am = posix_atime if posix_atime in ("preserve", "epoch") else "preserve"
    try:
        if os.name == "nt":
            try:
                return _apply_fs_times_windows(path, ep)
            except Exception:
                # ctypes / Windows API failure — still set mtime (and atime unchanged) via utime.
                return _apply_fs_times_posix(path, ep)
        return _apply_fs_times_posix(path, ep, atime_mode="epoch" if am == "epoch" else "preserve")
    except OSError:
        return False


def apply_preserved_times_from_source(source_path: str, output_path: str) -> bool:
    """
    Resolve time from ``source_path`` and apply to ``output_path`` if possible.
    """
    if not output_path or not os.path.isfile(output_path):
        return False
    ep = resolve_best_capture_epoch(source_path)
    return apply_preserved_filesystem_times(output_path, ep)


def epoch_to_ffmpeg_creation_metadata(epoch: float) -> str:
    """
    ISO-8601 string for FFmpeg ``-metadata creation_time=...`` (MP4/MOV).

    Uses the **system local** timezone (``±HH:MM`` offset via ``datetime.isoformat``), not plain
    UTC ``Z``. The Unix instant is unchanged, but some Linux file managers (e.g. KDE Dolphin)
    mis-render ``Z`` tags as a **local** wall clock without shifting the calendar day, so
    ``creation_time`` can appear **after** ``st_mtime`` for the same moment. Local-offset strings
    align typical **Created** (from metadata) with **Modified** (from ``stat``) on the same box.
    """
    try:
        ref = datetime.now().astimezone()
        tzinfo = ref.tzinfo
        if tzinfo is None:
            tzinfo = timezone.utc
        dt = datetime.fromtimestamp(float(epoch), tz=tzinfo)
    except (OverflowError, OSError, ValueError, TypeError):
        return ""
    return dt.isoformat(timespec="microseconds")


def ffmpeg_metadata_creation_args(epoch: Optional[float]) -> list[str]:
    """
    Returns ``[]`` or FFmpeg args for **format** and **first video stream** ``creation_time``.

    MOV/MP4 often store ``creation_time`` on both the **format** and **video stream**; stream tags
    default to **encode time** if not set, so UIs show “today” while the container tag looks fine.
    """
    if epoch is None:
        return []
    s = epoch_to_ffmpeg_creation_metadata(epoch)
    if not s:
        return []
    tag = f"creation_time={s}"
    return ["-metadata", tag, "-metadata:s:v:0", tag]


def _remux_mp4_inplace_creation_metadata(output_path: str, epoch: float) -> bool:
    """
    Stream-copy ``output_path`` to a temp file with ``creation_time`` set, then copy back.

    Uses ``shutil.copyfile(tmp, output)`` instead of ``os.replace(tmp, output)``: on Linux, KDE
    “Created” comes from ``statx`` **birth time**, which is tied to the inode. **Replace** drops
    the old inode (birth time becomes “now”). **Truncating overwrite** keeps the inode so birth time
    stays aligned with the original file when possible.

    Maps first video + optional first audio (same idea as Mass AV1 Encoder).
    """
    meta = ffmpeg_metadata_creation_args(epoch)
    if not meta:
        return True
    out_dir = os.path.dirname(os.path.abspath(output_path)) or "."
    base = os.path.basename(output_path)
    suf = os.path.splitext(base)[1] or ".mp4"
    fd, tmp_path = tempfile.mkstemp(prefix=".ca_datefix_", suffix=suf, dir=out_dir)
    os.close(fd)
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            output_path,
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-c",
            "copy",
            "-map_metadata",
            "0",
        ]
        cmd.extend(meta)
        cmd.append(tmp_path)
        r = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=7200,
        )
        if r.returncode != 0:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            return False
        try:
            shutil.copyfile(tmp_path, output_path)
        except OSError:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            return False
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        return True
    except (OSError, subprocess.SubprocessError, ValueError):
        try:
            if os.path.isfile(tmp_path):
                os.unlink(tmp_path)
        except OSError:
            pass
        return False


def _resolved_epoch_for_sync(source_path: str) -> Optional[float]:
    """Same epoch resolution as ``sync_preserved_media_dates_to_existing_output`` (capture → mtime)."""
    ep = resolve_best_capture_epoch(source_path)
    if ep is None:
        try:
            ep = float(os.path.getmtime(source_path))
        except OSError:
            return None
    return ep


def output_matches_resolved_capture_epoch(
    output_path: str,
    epoch: float,
    *,
    remux_mp4_metadata: bool = True,
    tolerance_sec: float = DATE_MATCH_TOLERANCE_SEC,
) -> bool:
    """
    True if ``output_path`` already has mtime (and MP4 ``creation_time`` when applicable) matching
    ``epoch`` within ``tolerance_sec``.
    """
    if not output_path or not os.path.isfile(output_path):
        return False
    try:
        out_m = float(os.path.getmtime(output_path))
    except OSError:
        return False
    if abs(out_m - epoch) > tolerance_sec:
        return False

    ext = pathlib.Path(output_path).suffix.lower()
    if remux_mp4_metadata and ext in (".mp4", ".m4v", ".mov"):
        expected = epoch_to_ffmpeg_creation_metadata(epoch)
        if not expected:
            return False
        fmt_ct, v_ct = _ffprobe_format_and_video_creation_time_raw(output_path)
        has_fmt = bool(fmt_ct)
        has_v = bool(v_ct)
        if not has_fmt and not has_v:
            return False
        if has_fmt and not _creation_time_strings_match(expected, fmt_ct, tolerance_sec):
            return False
        # Stream-level tag is what many players show; when present it must match (else "today").
        if has_v and not _creation_time_strings_match(expected, v_ct, tolerance_sec):
            return False

    return True


def apply_resolved_epoch_to_existing_output(
    output_path: str,
    epoch: float,
    *,
    remux_mp4_metadata: bool = True,
    force: bool = False,
) -> bool:
    """
    Apply ``epoch`` to ``output_path`` (MP4/MOV/M4V remux + ``os.utime``), skipping work if
    ``output_matches_resolved_capture_epoch`` is already True (unless ``force`` is True).
    """
    if not output_path or not os.path.isfile(output_path):
        return False
    if not force and output_matches_resolved_capture_epoch(
        output_path,
        epoch,
        remux_mp4_metadata=remux_mp4_metadata,
    ):
        return True

    ext = pathlib.Path(output_path).suffix.lower()
    needs_remux = remux_mp4_metadata and ext in (".mp4", ".m4v", ".mov")
    if needs_remux:
        # Do not touch mtime/atime if remux failed — avoids "failed" jobs that still changed FS times
        # while leaving container/stream creation_time stale.
        if not _remux_mp4_inplace_creation_metadata(output_path, epoch):
            return False

    fs_ok = apply_preserved_filesystem_times(output_path, epoch, posix_atime="epoch")
    return fs_ok


def _ffprobe_format_and_video_creation_time_raw(file_path: str) -> tuple[Optional[str], Optional[str]]:
    """
    ``(format_tags.creation_time, first_video_stream.tags.creation_time)`` from one ffprobe JSON pass.
    Either value may be None if missing.
    """
    try:
        raw = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                file_path,
            ],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=120,
        )
        data = json.loads(raw)
    except (subprocess.SubprocessError, OSError, ValueError, json.JSONDecodeError):
        return None, None

    tag_keys = (
        "creation_time",
        "com.apple.quicktime.creationdate",
        "com.apple.quicktime.creationDate",
    )
    fmt_tags = (data.get("format") or {}).get("tags") or {}
    fmt_ct: Optional[str] = None
    for k in tag_keys:
        if k in fmt_tags:
            fmt_ct = str(fmt_tags[k]).strip()
            break

    v_ct: Optional[str] = None
    for stream in data.get("streams") or []:
        if (stream.get("codec_type") or "").lower() != "video":
            continue
        st = stream.get("tags") or {}
        for k in tag_keys:
            if k in st:
                v_ct = str(st[k]).strip()
                break
        break

    return fmt_ct, v_ct


def _creation_time_strings_match(expected: str, actual: Optional[str], tolerance_sec: float) -> bool:
    if not actual:
        return False
    if expected.strip() == actual.strip():
        return True
    dt_exp = _parse_tag_datetime(expected)
    dt_act = _parse_tag_datetime(actual)
    if not dt_exp or not dt_act:
        return False
    return abs((dt_exp - dt_act).total_seconds()) <= tolerance_sec


def preserved_media_dates_already_match(
    source_path: str,
    output_path: str,
    *,
    remux_mp4_metadata: bool = True,
    tolerance_sec: float = DATE_MATCH_TOLERANCE_SEC,
) -> bool:
    """
    True if the target already reflects the desired date from ``source_path`` (filesystem mtime
    and, for MP4/MOV/M4V, ``creation_time`` tag), within ``tolerance_sec``.

    Used to skip redundant remux/``utime`` when re-running **Fix media dates** after an interrupt.
    """
    if not source_path or not output_path:
        return False
    if not os.path.isfile(source_path) or not os.path.isfile(output_path):
        return False
    try:
        if os.path.samefile(source_path, output_path):
            return False
    except OSError:
        return False

    ep = _resolved_epoch_for_sync(source_path)
    if ep is None:
        return False
    return output_matches_resolved_capture_epoch(
        output_path,
        ep,
        remux_mp4_metadata=remux_mp4_metadata,
        tolerance_sec=tolerance_sec,
    )


def sync_preserved_media_dates_to_existing_output(
    source_path: str,
    output_path: str,
    *,
    remux_mp4_metadata: bool = True,
    force: bool = False,
) -> bool:
    """
    Copy best-effort capture/recording time from ``source_path`` onto an existing ``output_path``
    (e.g. ``*_av1.mp4`` next to sources): MP4/MOV/M4V container ``creation_time`` via stream-copy
    remux when ``remux_mp4_metadata`` is True, then set filesystem mtime/atime.

    Does not create ``output_path``; returns False if either path is missing or identical.
    If the target already matches (see ``preserved_media_dates_already_match``), returns True
    without rewriting the file — unless ``force`` is True (Mass AV1 **Fix media dates** always
    passes ``force`` so each job re-applies metadata and filesystem times).
    """
    if not source_path or not output_path:
        return False
    if not os.path.isfile(source_path) or not os.path.isfile(output_path):
        return False
    try:
        if os.path.samefile(source_path, output_path):
            return False
    except OSError:
        return False

    if not force and preserved_media_dates_already_match(
        source_path,
        output_path,
        remux_mp4_metadata=remux_mp4_metadata,
    ):
        return True

    ep = _resolved_epoch_for_sync(source_path)
    if ep is None:
        return False
    return apply_resolved_epoch_to_existing_output(
        output_path,
        ep,
        remux_mp4_metadata=remux_mp4_metadata,
        force=force,
    )
