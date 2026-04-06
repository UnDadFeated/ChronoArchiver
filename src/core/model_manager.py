import time
import requests
import pathlib
import threading
import logging
import hashlib
import tarfile
import shutil
from pathlib import Path
from typing import Callable, Optional

try:
    from .debug_logger import debug, structured_event, UTILITY_MODEL_SETUP
    from .http_utils import requests_get_stream_with_retries
except ImportError:
    from core.debug_logger import debug, structured_event, UTILITY_MODEL_SETUP
    from core.http_utils import requests_get_stream_with_retries


class ModelManager:
    """Handles checking and downloading AI models for the scanner."""

    MODEL_VERSION = "2025-01"  # YOLOv8 replaces SSD
    VERSION_URL = "https://raw.githubusercontent.com/UnDadFeated/ChronoArchiver/main/docs/models_version.txt"

    MODELS = {
        "face_detection": {
            "filename": "face_detection_yunet_2023mar.onnx",
            "label": "Face (YuNet)",
            "url": "https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx",
            "sha256": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
            "approx_size": 233_000,
        },
        "object_detection_yolov8": {
            "filename": "yolov8n.onnx",
            "label": "Persons & Animals (YOLOv8)",
            "url": "https://huggingface.co/Kalray/yolov8/resolve/main/yolov8n.onnx",
            "sha256": "65158dad735be799c2466fa15e260c09558080bd530b42a8d0c3d1b419afd8b5",
            "approx_size": 12_800_000,  # ~12.2 MB
        },
    }

    def __init__(self, model_dir: str):
        self.model_dir = pathlib.Path(model_dir)
        self.logger = logging.getLogger("ChronoArchiver.Scanner")
        self.stop_event = threading.Event()

    def verify_hash(self, file_path: pathlib.Path, expected_sha: str) -> bool:
        """Verify the SHA-256 hash of a file."""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            actual_sha = sha256_hash.hexdigest()
            if actual_sha != expected_sha:
                self.logger.warning(
                    f"Hash mismatch for {file_path.name}! Expected: {expected_sha}, Actual: {actual_sha}"
                )
                return False
            return True
        except Exception as e:
            self.logger.error(f"Error during hash verification: {e}")
            return False

    def get_missing_models(self):
        """Returns a list of model keys that are missing or corrupt."""
        missing = []
        for key, info in self.MODELS.items():
            path = self.model_dir / info["filename"]
            if not path.exists() or not self.verify_hash(path, info["sha256"]):
                missing.append(key)
        return missing

    def get_total_download_size(self):
        """Returns approximate total bytes to download for all missing models."""
        missing = self.get_missing_models()
        total = 0
        for key in missing:
            info = self.MODELS[key]
            total += info.get("approx_size", 0)
        return total

    def is_up_to_date(self):
        """Returns True if all models are present and valid."""
        return len(self.get_missing_models()) == 0

    def check_model_update_available(self):
        """Returns True if a newer model version is available (optional check)."""
        try:
            r = requests.get(self.VERSION_URL, timeout=5)
            if r.status_code != 200:
                return False
            remote = r.text.strip()
            return bool(remote and remote != self.MODEL_VERSION)
        except Exception:
            return False

    def download_models(self, progress_callback=None):
        """Downloads all missing/corrupt models. progress_callback(downloaded, total, filename, overall_0_to_1, label, url)"""
        missing = self.get_missing_models()
        if not missing:
            debug(UTILITY_MODEL_SETUP, "Model download: all models present")
            return True

        total_bytes = self.get_total_download_size()
        debug(UTILITY_MODEL_SETUP, f"Model download start: missing={missing}, total~{total_bytes} bytes")
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.stop_event.clear()

        done_bytes = 0

        for key in missing:
            if self.stop_event.is_set():
                break

            info = self.MODELS[key]
            url = info["url"]
            dest = self.model_dir / info["filename"]
            label = info.get("label", info["filename"])
            model_size = info.get("approx_size", 0)

            self.logger.info(f"Downloading model: {info['filename']} from {url}")

            dl_dest = None
            try:
                if dest.exists():
                    dest.unlink()

                with requests_get_stream_with_retries(url, timeout=(10, 120), attempts=3) as response:
                    try:
                        total_size = int(response.headers.get("content-length", 0) or 0)
                    except (TypeError, ValueError):
                        total_size = 0
                    if total_size <= 0:
                        total_size = model_size

                    is_tar = "tar_extract" in info
                    dl_dest = dest if not is_tar else dest.with_suffix(".tar.gz")

                    with open(dl_dest, "wb") as f:
                        downloaded = 0
                        for chunk in response.iter_content(chunk_size=8192):
                            if self.stop_event.is_set():
                                break
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                overall = (done_bytes + downloaded) / max(total_bytes, 1) if total_bytes else 0
                                overall = min(1.0, overall)
                                if progress_callback:
                                    status = (
                                        "Extracting... please wait..." if (is_tar and overall >= 0.99) else dl_dest.name
                                    )
                                    progress_callback(downloaded, total_size, status, overall, label, url)

                if self.stop_event.is_set():
                    if dl_dest.exists():
                        dl_dest.unlink()
                    self.logger.info(f"Download cancelled for {info['filename']}")
                    debug(UTILITY_MODEL_SETUP, f"Model download cancelled: {info['filename']}")
                    return False

                if "tar_extract" in info:
                    if progress_callback:
                        overall = (done_bytes + total_size) / max(total_bytes, 1)
                        overall = min(1.0, overall)
                        progress_callback(
                            total_size, total_size, "Installing models... please wait...", overall, label, url
                        )
                        time.sleep(0.25)
                    with tarfile.open(dl_dest, "r:gz") as tar:
                        try:
                            member = tar.getmember(info["tar_extract"])
                        except KeyError:
                            raise ValueError(f"Archive missing expected member: {info['tar_extract']}")
                        member.name = dest.name
                        if hasattr(tarfile, "data_filter"):
                            tar.extract(member, path=dest.parent, filter="data")
                        else:
                            tar.extract(member, path=dest.parent)
                    dl_dest.unlink()

                if progress_callback:
                    progress_callback(0, 0, "Installing models... please wait...", 1.0, "Verifying", url)
                    time.sleep(0.25)
                hash_ok = self.verify_hash(dest, info["sha256"])
                if not hash_ok:
                    self.logger.warning(f"Integrity check failed for {info['filename']}, retrying download once")
                    debug(UTILITY_MODEL_SETUP, f"Model hash mismatch, retry: {info['filename']}")
                    try:
                        if dest.exists():
                            dest.unlink()
                    except OSError:
                        pass
                    if dl_dest is not None and dl_dest.exists():
                        try:
                            dl_dest.unlink()
                        except OSError:
                            pass
                    with requests_get_stream_with_retries(url, timeout=(10, 120), attempts=3) as response:
                        try:
                            total_size = int(response.headers.get("content-length", 0) or 0)
                        except (TypeError, ValueError):
                            total_size = 0
                        if total_size <= 0:
                            total_size = model_size
                        is_tar = "tar_extract" in info
                        dl_dest = dest if not is_tar else dest.with_suffix(".tar.gz")
                        with open(dl_dest, "wb") as f:
                            downloaded = 0
                            for chunk in response.iter_content(chunk_size=8192):
                                if self.stop_event.is_set():
                                    break
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    overall = (done_bytes + downloaded) / max(total_bytes, 1) if total_bytes else 0
                                    overall = min(1.0, overall)
                                    if progress_callback:
                                        st = (
                                            "Extracting... please wait..."
                                            if (is_tar and overall >= 0.99)
                                            else dl_dest.name
                                        )
                                        progress_callback(downloaded, total_size, st, overall, label, url)
                    if self.stop_event.is_set():
                        if dl_dest.exists():
                            dl_dest.unlink()
                        return False
                    if "tar_extract" in info:
                        if progress_callback:
                            overall = (done_bytes + total_size) / max(total_bytes, 1)
                            overall = min(1.0, overall)
                            progress_callback(
                                total_size, total_size, "Installing models... please wait...", overall, label, url
                            )
                            time.sleep(0.25)
                        with tarfile.open(dl_dest, "r:gz") as tar:
                            try:
                                member = tar.getmember(info["tar_extract"])
                            except KeyError:
                                raise ValueError(f"Archive missing expected member: {info['tar_extract']}")
                            member.name = dest.name
                            if hasattr(tarfile, "data_filter"):
                                tar.extract(member, path=dest.parent, filter="data")
                            else:
                                tar.extract(member, path=dest.parent)
                        dl_dest.unlink()
                    if progress_callback:
                        progress_callback(0, 0, "Installing models... please wait...", 1.0, "Verifying", url)
                        time.sleep(0.25)
                    if not self.verify_hash(dest, info["sha256"]):
                        self.logger.error(f"Integrity check failed for {info['filename']} after retry")
                        debug(UTILITY_MODEL_SETUP, f"Model hash mismatch after retry: {info['filename']}")
                        if dest.exists():
                            dest.unlink()
                        return False

                done_bytes += total_size if total_size > 0 else model_size
                structured_event(
                    "scanner_model_ready",
                    model_key=key,
                    filename=info["filename"],
                )

            except Exception as e:
                self.logger.error(f"Failed to download {info['filename']}: {e}")
                debug(UTILITY_MODEL_SETUP, f"Model download failed: {info['filename']} — {e}")
                if dest.exists():
                    dest.unlink()
                if dl_dest is not None and dl_dest.exists():
                    dl_dest.unlink()
                return False

        ok = self.is_up_to_date()
        debug(UTILITY_MODEL_SETUP, f"Model download complete: ok={ok}")
        return ok

    def cancel(self):
        self.stop_event.set()


# ---------------------------------------------------------------------------
# Z-Image Pro Upscaler models (Hugging Face Z-Image-Turbo snapshot)
# ---------------------------------------------------------------------------

try:
    # Optional: only needed when using the upscaler UI.
    from huggingface_hub import HfApi, hf_hub_download, list_repo_files
except ImportError:  # pragma: no cover
    HfApi = None  # type: ignore[misc, assignment]
    hf_hub_download = None  # type: ignore[misc, assignment]
    list_repo_files = None  # type: ignore[misc, assignment]

REPO_ID = "Tongyi-MAI/Z-Image-Turbo"
HF_MODEL_URL = f"https://huggingface.co/{REPO_ID}"


def snapshot_path(models_root: Path) -> Path:
    return Path(models_root) / "Tongyi-MAI_Z-Image-Turbo"


class ZImageModelManager:
    """Cancellable file-by-file HF download for Z-Image-Turbo (diffusers)."""

    def __init__(self, models_root: Path):
        self.models_root = Path(models_root)
        self.snapshot_dir = snapshot_path(self.models_root)
        self.stop_event = threading.Event()

    def cancel(self) -> None:
        self.stop_event.set()

    def is_up_to_date(self) -> bool:
        if not self.snapshot_dir.is_dir():
            return False
        transformer_cfg = self.snapshot_dir / "transformer" / "config.json"
        if not transformer_cfg.is_file():
            return False
        try:
            if not any(self.snapshot_dir.glob("transformer/*.safetensors")):
                return False
        except OSError:
            return False
        return True

    def estimate_total_bytes(self) -> int:
        if HfApi is None:
            return 12 * 1024 * 1024 * 1024
        try:
            api = HfApi()
            info = api.model_info(REPO_ID, files_metadata=True)
            total = 0
            for s in info.siblings or []:
                if getattr(s, "size", None):
                    total += int(s.size)
            return max(total, 1024)
        except Exception:
            return 12 * 1024 * 1024 * 1024

    def _file_size_map(self) -> dict[str, int]:
        out: dict[str, int] = {}
        if HfApi is None:
            return out
        try:
            api = HfApi()
            info = api.model_info(REPO_ID, files_metadata=True)
            for s in info.siblings or []:
                key = getattr(s, "path", None) or getattr(s, "rfilename", None)
                if key and getattr(s, "size", None):
                    out[str(key)] = int(s.size)
        except Exception:
            pass
        return out

    def download_models(self, progress_callback: Optional[Callable[..., None]] = None) -> bool:
        """
        Download repo files one-by-one (enables cancel between files).
        progress_callback(downloaded, total_size, filename, overall_0_to_1, label, url)
        """
        if hf_hub_download is None or list_repo_files is None or HfApi is None:
            return False
        self.stop_event.clear()
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

        try:
            files = list(list_repo_files(repo_id=REPO_ID, repo_type="model"))
        except Exception:
            return False

        sizes = self._file_size_map()
        total_est = max(self.estimate_total_bytes(), 1)
        done_cum = 0
        label = "Z-Image-Turbo"

        for rel in files:
            if self.stop_event.is_set():
                return False
            sz = int(sizes.get(rel, 0) or 0)
            url = f"{HF_MODEL_URL}/resolve/main/{rel}"
            if progress_callback:
                overall = done_cum / total_est
                progress_callback(0, sz or 1, rel, min(1.0, overall), label, url)
            try:
                hf_hub_download(
                    repo_id=REPO_ID,
                    filename=rel,
                    local_dir=str(self.snapshot_dir),
                    local_dir_use_symlinks=False,
                    resume_download=True,
                )
            except Exception:
                return False
            done_cum += sz if sz > 0 else 0
            if progress_callback:
                overall = done_cum / total_est
                progress_callback(sz or 1, sz or 1, rel, min(1.0, overall), label, url)

        if progress_callback:
            progress_callback(0, 0, "Verifying", 1.0, label, HF_MODEL_URL)

        # Optional LaMa (shared with AI Video Upscaler): neural inpaint before Z-Image refinement.
        try:
            from core.app_paths import settings_dir
            from core.lama_inpaint_models import LAMA_URL, LamaInpaintModelManager

            lama_root = settings_dir() / "ai_video_upscaler" / "models"
            lama_mgr = LamaInpaintModelManager(lama_root)
            if not lama_mgr.is_ready():

                def _lama_prog(fn: str, downloaded: int, total: int) -> None:
                    if progress_callback:
                        tot = max(int(total), 1)
                        frac = min(1.0, downloaded / tot)
                        overall = min(1.0, 0.92 + 0.08 * frac)
                        progress_callback(
                            downloaded,
                            tot,
                            fn,
                            overall,
                            "LaMa inpainting (cleanup)",
                            LAMA_URL,
                        )

                ok_lama, _err = lama_mgr.download(_lama_prog, mirror_cancel=self.stop_event)
                if not ok_lama:
                    debug(
                        UTILITY_MODEL_SETUP,
                        "LaMa download skipped or failed (Telea fallback still available for cleanup).",
                    )
        except Exception as e:
            debug(UTILITY_MODEL_SETUP, f"LaMa optional download hook: {e}")

        return self.is_up_to_date()

    def remove_snapshot(self) -> None:
        if self.snapshot_dir.is_dir():
            try:
                shutil.rmtree(self.snapshot_dir, ignore_errors=False)
            except OSError:
                pass
