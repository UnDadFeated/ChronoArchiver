"""Download / locate LaMa TorchScript weights for neural inpainting (AI Video & Image upscalers)."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.lama_inpaint_runner import invalidate_lama_checkpoint_cache, validate_lama_torchscript_file

# TorchScript export used by simple-lama-inpainting (MIT); compatible with LaMa big-lama.
LAMA_FILENAME = "big-lama.pt"
LAMA_URL = "https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt"
APPROX_LAMA_BYTES = 196 * 1024 * 1024

_MIN_VALID_BYTES = 40 * 1024 * 1024
_DOWNLOAD_TIMEOUT_SEC = 720

_log = logging.getLogger("ChronoArchiver.lama_inpaint")


class LamaInpaintModelManager:
    def __init__(self, models_root: Path) -> None:
        self._root = models_root
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def path(self) -> Path:
        return self._root / LAMA_FILENAME

    def is_ready(self) -> bool:
        p = self.path()
        if not p.is_file():
            return False
        if p.stat().st_size <= _MIN_VALID_BYTES:
            return False
        ok, err, quarantine = validate_lama_torchscript_file(p)
        if ok:
            return True
        if quarantine:
            invalidate_lama_checkpoint_cache(p)
            bad = p.with_name(p.name + ".bad")
            try:
                if bad.is_file():
                    bad.unlink()
                p.rename(bad)
                _log.warning("Moved invalid LaMa checkpoint aside (%s): %s", bad, err)
            except OSError as e:
                _log.warning("Invalid LaMa checkpoint but could not quarantine %s: %s (%s)", p, err, e)
        else:
            _log.warning("LaMa checkpoint check failed (not quarantining): %s: %s", p, err)
        return False

    def download(
        self,
        progress_cb: Callable[[str, int, int], None] | None = None,
        *,
        mirror_cancel: threading.Event | None = None,
    ) -> tuple[bool, str]:
        if mirror_cancel is None:
            self._cancel.clear()
        try:
            self._root.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return False, f"cannot create models folder: {e}"

        dest = self.path()
        temp = dest.with_suffix(".partial")
        try:
            if temp.is_file():
                temp.unlink()
        except OSError:
            pass

        req = Request(LAMA_URL, headers={"User-Agent": "ChronoArchiver/LaMa (weights)"})
        est = APPROX_LAMA_BYTES
        downloaded = 0
        try:
            with urlopen(req, timeout=_DOWNLOAD_TIMEOUT_SEC) as resp:
                code = getattr(resp, "status", None) or getattr(resp, "code", 200)
                if code != 200:
                    return False, f"HTTP {code}"
                cl = resp.headers.get("Content-Length") if resp.headers else None
                try:
                    total = int(cl) if cl is not None and str(cl).strip().isdigit() else est
                except (TypeError, ValueError):
                    total = est
                if total <= 0:
                    total = est

                block = 256 * 1024

                def _abort() -> bool:
                    if self._cancel.is_set():
                        return True
                    return bool(mirror_cancel and mirror_cancel.is_set())

                with open(temp, "wb") as f:
                    while not _abort():
                        chunk = resp.read(block)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb:
                            progress_cb(LAMA_FILENAME, downloaded, total)
        except HTTPError as e:
            try:
                if temp.is_file():
                    temp.unlink()
            except OSError:
                pass
            return False, f"HTTP {e.code}: {e.reason}"
        except URLError as e:
            try:
                if temp.is_file():
                    temp.unlink()
            except OSError:
                pass
            reason = e.reason if getattr(e, "reason", None) else str(e)
            return False, f"network: {reason}"
        except OSError as e:
            try:
                if temp.is_file():
                    temp.unlink()
            except OSError:
                pass
            return False, str(e)

        if self._cancel.is_set() or (mirror_cancel and mirror_cancel.is_set()):
            try:
                temp.unlink()
            except OSError:
                pass
            return False, "cancelled"

        if downloaded < _MIN_VALID_BYTES:
            try:
                if temp.is_file():
                    temp.unlink()
            except OSError:
                pass
            return False, f"download too small ({downloaded} bytes) — check connection or URL"

        try:
            temp.replace(dest)
        except OSError as e:
            try:
                if temp.is_file():
                    temp.unlink()
            except OSError:
                pass
            return False, f"could not save file: {e}"

        if not self.is_ready():
            try:
                if dest.is_file():
                    dest.unlink()
            except OSError:
                pass
            return False, "saved file failed validation (corrupt or wrong content)"

        return True, ""
