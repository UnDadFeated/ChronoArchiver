"""Load CHANGELOG.md and extract the section for a given version (release notes UI)."""

from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Public web fallbacks when no local CHANGELOG is available (e.g. some frozen layouts).
CHANGELOG_BLOB_URL = "https://github.com/UnDadFeated/ChronoArchiver/blob/main/CHANGELOG.md"
CHANGELOG_RAW_URL = "https://raw.githubusercontent.com/UnDadFeated/ChronoArchiver/main/CHANGELOG.md"

# Shipped with the app so “What’s new” always has text when repo CHANGELOG.md is missing or stale.
# On each release bump, copy the ## [X.Y.Z] block from CHANGELOG.md (see tools/bump_version.py reminder).
EMBEDDED_RELEASE_NOTES: dict[str, str] = {
    "6.4.0": """## [6.4.0] - 2026-05-12

### Fixed
- **VAAPI encoding without hardware decode fails**: When `hw_accel_decode` is unchecked, VAAPI branch passed a VAAPI encoder name but no `-vaapi_device` flag, causing FFmpeg to fail with device context errors. Now passes `-vaapi_device /dev/dri/renderD*` when a render node is available even without hardware decode.
- **Scan token not incremented on inline scan-then-start**: When clicking START with an empty queue, `_start_encoding` sets `_scan_in_progress = True` but never increments `_scan_token`. This allows the scan's result to pass the stale-token check if a prior scan used the same token. Now increments `_scan_token` before capturing it in the closure.
- **Remote scan misses 3 video extensions**: Remote scan checked only 8 extensions while local `scan_files()` checks 11. Missing `.m4v`, `.wmv`, `.mpeg` caused inconsistent results between local and remote sources. Added the 3 missing extensions to match `scan_files()`.
- **Lock order comment contradicts actual code**: Comment claimed `_queue_lock` → `_active_lock` ordering but code acquires `_active_lock` → `_queue_lock`. Updated comment to match actual nesting.
""",
    "6.3.0": """## [6.3.0] - 2026-05-12

### Fixed
- **Pipeline prefetch finally block never sends sentinels on normal completion**: The `finally` block gated sentinel-sending on `_pipeline_prefetch_stop.is_set()`, which is only True when STOP is pressed. On normal batch completion, no sentinels were sent and pipeline workers spun forever. Removed the guard so sentinels are always sent (double-sentinel on STOP is harmless — extra None items sit in the discarded queue and are GC'd).
- **`_nvenc_skip_cuda_hwaccel` reset on every engine construction**: The class-level flag was reset to `False` in `__init__`, defeating the purpose of the CUDA-decode retry suppression. The flag is now managed solely by `reset_nvenc_cuda_hwaccel_for_new_batch()` at batch start.
- **`_start_encoding` scan-then-start race**: `_scan_in_progress` was checked but never set to `True`, allowing duplicate scan threads on rapid double-clicks. Added `self._scan_in_progress = True` before thread launch. The scan token was also captured inside the thread body instead of at creation time, allowing stale results to slip through. Now captured in a closure variable at creation time.
""",
    "6.2.0": """## [6.2.0] - 2026-05-12

### Fixed
- **Mass Video Encoder engine pool never populated**: `_engine_pool` was initialized as `[]` in `__init__` and never populated. Replaced the bare `for eng in self._engine_pool:` loop with `self._engine_pool = [VideoEncoderEngine(job_id=i) for i in range(num_workers)]` in `_continue_start_encoding` so workers are actually created and launched.
- **Encoder tautological ternary passes deleted path on failure**: Both `_job_worker` and `_job_worker_pipeline` had `_fin(ok, logical_key, out_p if ok else out_p, meta)` — identical branches passing a deleted temp path on failure. Changed to `_fin(ok, logical_key, out_p if ok else "", meta)`.
- **Duplicated button-reset block in `_stop_encoding`**: The button state was reset twice. Removed the trailing duplicate block.
- **Dead-code guard in `_toggle_pause`**: `if new_state == self._is_paused: return` is always-false (since `new_state = not self._is_paused`). Simplified to direct toggle.
- **Duplicate `output_ext` key in encoder settings defaults**: Removed deprecated duplicate entry.
- **libx265 preset map skipped fastest presets**: P1 mapped to `"fast"` instead of `"ultrafast"`. Now maps full range: `ultrafast → medium` for P1–P7.
- **Remote scan script path contained shell expression**: `$(echo ${TMPDIR:-/tmp})` was single-quoted as a literal path via `sh_single_quote`. Changed to plain `/tmp/chronoarchiver_scan_{token}.py`. The rm_cmd now uses `*_remote_via_posix_sh()` for consistent argument parsing.
""",
    "6.1.0": """## [6.1.0] - 2026-05-12

### Fixed
- **Pipeline prefetch finally block sends sentinels to wrong queue after batch transition**: The `_pipeline_prefetch_loop` finally block unconditionally sent `None` sentinels on exit, which could strand a new batch's workers if the old prefetch thread survived the join timeout. Guarded sentinel-sending with `_pipeline_prefetch_stop.is_set()` check so sentinels are only sent when STOP was explicitly pressed.
- **Space-saved bypass for same-size outputs**: `_apply_encode_finished` skipped zero-savings outputs (`saved_override == 0`) without recalculating from file sizes. Changed condition from `is not None` to `is not None and > 0` so same-size passthrough outputs correctly fall through to file-size recalculation.
- **Concurrent scan-then-start threads from rapid START clicks**: `_start_encoding` with an empty queue launched inline scan-then-start threads without checking `_scan_in_progress`. Added guard to prevent duplicate concurrent scans.

### Added
- **Encoder panel**: Bug fixes 60–71 (pipeline pause, scan token/race, progress slot guard, dead parameter, batch-complete on STOP, space-saved recalc, concurrent scan prevention, and more).
""",
    "6.0.11": """## [6.0.11] - 2026-05-11

### Fixed
- **Mass Video Encoder pause re-inserted item at queue front**: When paused, the item was re-inserted at index 0 via `queue.insert(0, ...)`, causing a tight busy-loop where the same item was popped again immediately. Other queued items were pushed back and blocked from ever being processed. Changed to `queue.append(...)` so the item is placed at the end of the queue, allowing other items to be processed first and preventing the busy-loop.
""",
    "6.0.10": """## [6.0.10] - 2026-05-11

### Fixed
- **Mass Video Encoder pause not respected**: Workers continued pulling items and starting FFmpeg processes while paused. The main loop now checks `self._is_paused` after each queue pop and puts the item back, sleeping 200ms before retrying. The pipeline prefetch loop and pipeline worker also respect pause state.
- **Mass Video Encoder pipeline prefetch never activated**: `_encode_pipeline_q` was declared but never assigned a `queue.Queue`, always remained `None`. Remote pipeline mode is now activated when source is remote and `concurrent_jobs >= 2`. A prefetch thread downloads remote files ahead of encoding to overlap network I/O with NVENC.
- **Mass Video Encoder `_pipeline_prefetch_stop` event never reset**: `threading.Event` was set on stop/complete but never cleared. On a restart after stop, `is_set()` returned `True` causing the prefetch loop to exit immediately. The event is now cleared at the start of each batch.
- **Mass Video Encoder stale `_job_progress` / `_current_files`**: Completed batch state leaked into the next batch. `_job_progress` and `_current_files` are now cleared in `_finalize_batch_complete`. Late-arriving progress signals for finished jobs are discarded by the existing `job_id not in self._current_files` guard.
""",
    "6.0.9": """## [6.0.9] - 2026-05-11

### Fixed
- **Mass Video Encoder not starting**: `self._engine_pool` was an empty list from `__init__` and never populated with `VideoEncoderEngine` instances. The `for eng in self._engine_pool:` loop iterated over zero engines, so no worker threads were spawned. Engines are now created from `concurrent_jobs` setting before the worker loop starts. `_is_encoding = True` moved before thread creation to prevent race condition.
""",
    "6.0.8": """## [6.0.8] - 2026-05-11

### Fixed
- **Mass Video Encoder start button crash**: Fixed `TypeError` when computing `structure_root` — queue items are `(path, size)` tuples but were treated as strings directly. Worker threads now start properly.
- **Mass Video Encoder "Scan suffix" label**: Applied the "Skip Suffix" label rename that was documented in v6.0.6 but never applied to the actual UI code.
""",
    "6.0.7": """## [6.0.7] - 2026-05-11

### Fixed
- **Mass Video Encoder output filename suffix duplication**: Old codec suffixes are now stripped from output filenames (e.g. `movie_h265.mp4` → `movie_h264.mp4` instead of `movie_h265_h264.mp4`).
""",
    "6.0.6": """## [6.0.6] - 2026-05-11

### Changed
- **Mass Video Encoder**: Renamed "Scan suffix" dropdown label to "Skip Suffix" for clarity.
""",
    "6.0.5": """## [6.0.5] - 2026-05-11

### Changed
- **Mass Video Encoder scan suffix**: Added `None` option to the scan suffix dropdown, allowing the scanner to find all files recursively without skipping any codec suffix. Output suffix is now auto-determined from the codec selection.
""",
    "6.0.4": """## [6.0.4] - 2026-05-11

### Fixed
- **Mass Video Encoder scan suffix filter**: Replaced hardcoded `_av1`/`_h264`/`_hevc` filename skip with user-configurable dropdown (`None` / `_h264` / `_h265` / `_av1`). "None" scans all files.
- **Remote scan script**: Now accepts and applies `skip_suffixes` parameter, matching local scan behavior.
""",
    "6.0.3": """## [6.0.3] - 2026-05-11

### Fixed
- **Media Organizer `keep_newer`**: Source newer than target now overwrites instead of renaming to `file_1.jpg`.
- **Mass Video Encoder VAAPI/AMF/QSV**: Hardware encoders no longer silently fall back to software when hardware decode is unchecked.
- **Mass Video Encoder `-fps_mode` passthrough**: Removed duplicate/unconditional placement; now applied only after audio args for MP4/MKV.
- **Mass Video Encoder `passthrough_to_output`**: `-movflags +faststart` applied only for MP4 (not MKV).
- **Mass Video Encoder `scan_files`**: Added `.m4v`, `.wmv`, `.mpeg` extensions.
- **Media Organizer EXIF**: Rotated photos preserve original EXIF bytes; failure cleans up partial files; in-place mode checks writability and disk space.
""",
    "6.0.2": """## [6.0.2] - 2026-05-11

### Fixed
- **Comprehensive bug audit (56 issues)**: Applied fixes across the codebase — double-hashing in model downloads, single-instance lock error distinction, circular imports in AI runner modules, threading protection in subprocess tee, `weights_only=True` on `torch.load`, VideoCapture cancel support, on_progress exception handling, artifact directory creation, LaMa validation reduced to single forward pass, mask squeezing, variable shadowing, settings None guards, import consolidation, blur radius tuning, preset migration assertions, type annotations, broadcast safety, noise score clipping warnings, and more.
- **Model downloads**: Eliminated double-hashing I/O (single-pass missing-model + size computation).
- **Single-instance guard**: Distinguished `Timeout` (another instance) from `OSError` (permissions), added error logging.
""",
    "6.0.1": """## [6.0.1] - 2026-04-19

### Added
- **Flatpak packaging (initial)**: Added `flatpak/io.github.UnDadFeated.ChronoArchiver.yml`, desktop/metainfo files, launcher shim, and `tools/build_flatpak.sh` for local bundle testing on Bazzite/Fedora Atomic.
- **AI Media Scanner**: Added duplicate-detection mode (dhash similarity grouping) with representative swap controls in the scanner panel.

### Changed
- **Flatpak sandbox**: Reduced permissions from full home access to scoped XDG media/document paths and tightened app payload installation to required runtime files.
- **README**: Added Flatpak build/install/run instructions and clarified that Python prerequisites + AI models download in-app after install.

### Fixed
- **RealESRGAN runtime**: Corrected lazy-import refactor fallout in `realesrgan_runner` by removing duplicate NumPy import and keeping annotation-safe module behavior.
""",
    "5.9.0": """## [5.9.0] - 2026-04-11

### Changed
- **Mass Video Encoder**: **If output exists** defaults to **Skip** so re-runs do not overwrite finished outputs by accident.

### Fixed
- **Mass Video Encoder**: **Start** works again after a batch completes (no stuck grey button). **STOP** does not log spurious **FAILED** on **SIGTERM**. **FFmpeg** maps **first video + first audio** only (fixes multi-track / junk-stream mux failures); passthrough remux aligned. **TIP** lines after real failures (**SIGKILL**, **dvd_nav**).
""",
    "5.8.0": """## [5.8.0] - 2026-04-10

### Fixed
- **Mass Video Encoder**: **Worker threads** marshal console lines to the **GUI thread** (no direct **`QPlainTextEdit`** updates); **per-thread progress bars** stay in sync when **finish** handling is deferred vs the next encode on the same engine.

### Added
- **Debug log**: **Crash diagnostics** — **faulthandler** stacks in the session log; **PID** / **gdb** hints at startup; **SIGUSR2** stack dump; optional **`CHRONOARCHIVER_GDB_BACKTRACE`** live **gdb** backtrace (Linux).
""",
    "5.7.11": """## [5.7.11] - 2026-04-12

### Fixed
- **Mass Video Encoder**: **Stale progress** after a file finishes is ignored (**SIGSEGV** mitigation). **Master/ETA/I-O** updates capped at **~10/s**.
""",
    "5.7.10": """## [5.7.10] - 2026-04-12

### Fixed
- **Mass Video Encoder**: **SSH** scan dialog shows **live** progress; **encode finish** UI work is **serialized** for stability.

### Changed
- **Mass Video Encoder**: **FFmpeg** progress posts throttled to **~6.7/s** per worker.
""",
    "5.7.9": """## [5.7.9] - 2026-04-10

### Fixed
- **Mass Video Encoder**: Safer **4-thread** worker exit (**atomic** active-job count); no false **batch complete** on **STOP** in **remote pipeline** mode.

### Changed
- **Mass Video Encoder**: **GC** every **400** files on very long batches.
""",
    "5.7.8": """## [5.7.8] - 2026-04-12

### Fixed
- **NVENC**: Expected **183/218** retry is **INFO**, not **ERROR**. Worker→UI encoder signals are **queued** for thread safety.
""",
    "5.7.7": """## [5.7.7] - 2026-04-12

### Fixed
- **Mass Video Encoder**: Throttled FFmpeg **progress → UI** updates (~8/s per worker) to avoid Qt event-queue overload on long encodes.
""",
    "5.7.6": """## [5.7.6] - 2026-04-12

### Changed
- **Onboarding guide**: Shared primary-button guide styles/helpers in **`panel_widgets`**; Ruff formatting across the tree.

### Fixed
- **AV1 engine** / **remote SSH**: Duplicate import and dead assignment cleanup. **Organizer** / **Encoder** / **Scanner** guide pulse no longer conflicts with disabled or **STOP** button styling.
""",
    "5.7.5": """## [5.7.5] - 2026-04-11

### Changed
- **Mass Video Encoder**: Red **STOP ENCODING** styling (clears guide pulse overrides); **Preset**, **Threads**, and **If output exists** combos size to content.

### Fixed
- **Mass Video Encoder**: **STOP** remains enabled while encoding when the form re-validates.
""",
    "5.7.4": """## [5.7.4] - 2026-04-10

### Fixed
- **Footer GPU %**: Stronger **discrete NVIDIA** selection (``lspci`` domain BDFs + ``nvidia-smi -L``); **encoder** utilization included; optional ``CHRONOARCHIVER_FOOTER_NVIDIA_GPU``.
""",
    "5.7.3": """## [5.7.3] - 2026-04-10

### Fixed
- **Mass Video Encoder**: Console uses **plain text** (`QPlainTextEdit`) instead of rich HTML so long encode batches do not crash Qt during repaint.
""",
    "5.7.2": """## [5.7.2] - 2026-04-10

### Fixed
- **Mass Video Encoder**: Per-job **fps / speed** line parses current FFmpeg progress fields (including ``time=N/A`` warmup and ``KiB``/``Lsize``).
""",
    "5.7.1": """## [5.7.1] - 2026-04-10

### Changed
- **Footer GPU %** (`nvidia-smi`): Uses the same preferred NVIDIA adapter as `detect_gpu()` (discrete before integrated; ``CHRONOARCHIVER_FFMPEG_NVENC_GPU`` override). Linux matches **lspci** to ``pci.bus_id``; Windows multi-GPU falls back to largest **memory.total** when needed.
""",
    "5.7.0": """## [5.7.0] - 2026-04-10

### Added
- **Mass Video Encoder**: Already-**AV1** sources passthrough to `*_av1.mp4` (copy or **ffmpeg -c copy** remux) instead of re-encoding.

### Changed
- Encoder codec UI via **ffprobe** + queued signals; **NVENC** CUDA-decode skip after first **183/218** per batch; browse dialog layout fixes.

### Removed
- Footer **COPY DEBUG INFO**, **SHORTCUTS**, **SECURITY**, **EXPORT DIAGNOSTICS** and related modules.
""",
    "5.6.4": """## [5.6.4] - 2026-04-10

### Added
- **Mass Video Encoder / network batches**: Prefetch pipeline overlaps **scp** downloads with local **FFmpeg** encoding (bounded queue); cleans temps after upload.
""",
    "5.6.3": """## [5.6.3] - 2026-04-10

### Fixed
- **Remote scan / sshpass**: Clears ``SSH_ASKPASS`` / ``GIT_ASKPASS`` when using password mode so captured SSH output is reliable.
- **Encoder**: Remote scan failures log at WARNING; temp encode files use prefix ``chronoarchiver_av1_`` and are cleaned per job and on stop/quit; large scan totals no longer overflow Qt signals; **KeyError** in progress UI fixed (do not replace speed label list with a dict).
""",
    "5.6.2": """## [5.6.2] - 2026-04-10

### Fixed
- **Remote AV1 encoding**: SSH remote steps use ``sh -c`` so **fish** login shells do not break ``python3`` scan/verify.
""",
    "5.6.1": """## [5.6.1] - 2026-04-10

### Fixed
- **AV1 Encoder / Browse**: SSH password from the remote picker is copied to the panel field on OK; remote scan/encode match **Test SSH**. Clearer errors when SSH auth fails (not mislabeled as missing ``python3``).
""",
    "5.6.0": """## [5.6.0] - 2026-04-10

### Added
- **Mass Video Encoder — remote source and/or destination**: **scp** pull, local **FFmpeg**, **scp** push; remote scan via **SSH** + **python3** on the host; optional **sshpass** for password auth.

### Fixed
- **Encoder guide**: Local source + remote destination no longer traps the highlight on **Browse**.
""",
    "5.5.1": """## [5.5.1] - 2026-04-10

### Fixed
- **Guide pulse**: Remote `sftp://` paths no longer leave the highlight stuck on **Browse**; flow continues to **Start** / output where appropriate (encoder skips scan wait for remote URIs).
""",
    "5.5.0": """## [5.5.0] - 2026-04-10

### Added
- **Browse (Organizer, Mass Video Encoder, AI Media Scanner)**: pop-up **Local folder** vs **Remote (SSH / SFTP)** with `sftp://` or `user@host:/path`, optional password (not saved), and **Test SSH**. Remote URIs are stored in the path field; local processing shows a clear error until paths are local or mounted.
""",
    "5.4.4": """## [5.4.4] - 2026-04-09

### Changed
- **README**: Rewritten for first-time users with a simplified onboarding flow while preserving the existing application branding block and documentation links.
""",
    "5.4.3": """## [5.4.3] - 2026-04-08

### Added
- **`tools/verify_release_versions.py`**: CI checks version strings across **pyproject**, **README**, **PKGBUILD**, installer defaults, and **EMBEDDED_RELEASE_NOTES**.

### Fixed
- **CI**: **`libegl1`** and related libs for **PySide6** offscreen; **What’s new** resolves notes from disk, GitHub raw, or bundled text.

### Changed
- **CI**: pinned **Ruff**, Node 24 opt-in for Actions, **`bump_version`** reminder for embedded notes; **Ruff** includes **`tools/`**; **`updater.py`** formatting aligned with **Ruff 0.8.4**.
""",
    "5.4.2": """## [5.4.2] - 2026-04-06

### Added
- **Media Organizer**: **EXIF auto-rotate photos** checkbox in **Execution Mode** — for JPEG/PNG/WebP/TIFF/BMP/GIF with a non-default **Orientation** tag, decode with Pillow, apply **`ImageOps.exif_transpose`**, and save upright (re-encodes). Skipped when **Action** is **Symlink**; unsupported formats fall back to plain move/copy.

### Documentation
- **README**: Media Organizer row mentions optional EXIF auto-rotate.
""",
}


def changelog_file_candidates() -> list[Path]:
    """Paths to try for CHANGELOG.md (git layout, then PyInstaller bundle / install dir)."""
    core = Path(__file__).resolve().parent
    out: list[Path] = []
    # src/core -> parents[1] = repository root
    out.append(core.parents[1] / "CHANGELOG.md")
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            out.append(Path(meipass) / "CHANGELOG.md")
        exe_dir = Path(sys.executable).resolve().parent
        out.append(exe_dir / "CHANGELOG.md")
        out.append(exe_dir.parent / "CHANGELOG.md")
    return out


def read_changelog_markdown() -> tuple[str | None, Path | None]:
    """
    Returns (markdown text, path) if a readable file was found; else (None, None).
    """
    for p in changelog_file_candidates():
        try:
            if p.is_file():
                return p.read_text(encoding="utf-8", errors="replace"), p
        except OSError:
            continue
    return None, None


def changelog_section_for_version(body: str, version: str) -> str | None:
    """Return the full markdown block for ``## [version]`` through the next ``## [`` or EOF."""
    if not body or not version:
        return None
    pat = rf"(?ms)^## \[{re.escape(version.strip())}\].*?(?=^## \[|\Z)"
    m = re.search(pat, body)
    return m.group(0).strip() if m else None


def fetch_changelog_raw_from_github(timeout_s: float = 12.0) -> str | None:
    """Download main-branch CHANGELOG.md from GitHub (for offline installs missing a local file)."""
    try:
        req = urllib.request.Request(
            CHANGELOG_RAW_URL,
            headers={"User-Agent": "ChronoArchiver-WhatsNew"},
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # nosec B310 — fixed GitHub raw URL
            return resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError, ValueError):
        return None


def release_notes_for_version(version: str) -> tuple[str, Path | None, str]:
    """
    Return (markdown body, optional path to local CHANGELOG for “open file”, source tag).

    Resolution order: local CHANGELOG section → GitHub raw (same as repo main) →
    embedded dict shipped with the app → short offline fallback.
    Source is one of: ``local``, ``network``, ``embedded``, ``fallback``.
    """
    v = (version or "").strip()
    body, path = read_changelog_markdown()
    if body:
        section = changelog_section_for_version(body, v)
        if section:
            return section, path, "local"

    remote = fetch_changelog_raw_from_github()
    if remote:
        section = changelog_section_for_version(remote, v)
        if section:
            return section, path, "network"

    if v in EMBEDDED_RELEASE_NOTES:
        return EMBEDDED_RELEASE_NOTES[v].strip(), path, "embedded"

    fb = (
        f"Release notes for **{v}** are not bundled and could not be loaded "
        f"(offline or GitHub unreachable).\n\n"
        f"Use **View changelog** to open the project history in your browser when online."
    )
    return fb, path, "fallback"
