import time
import requests
import pathlib
import threading
import logging
import hashlib
import tarfile

try:
    from .debug_logger import debug, UTILITY_MODEL_SETUP
except ImportError:
    from core.debug_logger import debug, UTILITY_MODEL_SETUP

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
                self.logger.warning(f"Hash mismatch for {file_path.name}! Expected: {expected_sha}, Actual: {actual_sha}")
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

                with requests.get(url, stream=True, timeout=(10, 60)) as response:
                    response.raise_for_status()
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
                                    status = "Extracting... please wait..." if (is_tar and overall >= 0.99) else dl_dest.name
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
                        progress_callback(total_size, total_size, "Installing models... please wait...", overall, label, url)
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
                    self.logger.error(f"Integrity check failed for {info['filename']}")
                    debug(UTILITY_MODEL_SETUP, f"Model hash mismatch: {info['filename']}")
                    if dest.exists():
                        dest.unlink()
                    return False

                done_bytes += total_size if total_size > 0 else model_size

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
