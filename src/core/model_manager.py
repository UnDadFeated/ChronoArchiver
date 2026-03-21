import os
import requests
import pathlib
import threading
import logging

class ModelManager:
    """Handles checking and downloading AI models for the scanner."""
    
    MODELS = {
        "face_detection": {
            "filename": "face_detection_yunet_2023mar.onnx",
            "url": "https://github.com/opencv/opencv_zoo/raw/master/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
            "sha256": "7b98a0d4c987820173f4e8574d6c442468697690f3174296839611f78e1f57e0" # Example hash
        },
        "animal_detection": {
            "filename": "efficientdet_lite0.tflite",
            "url": "https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/float16/1/efficientdet_lite0.tflite",
            "sha256": "4f36a5a544c8f8b8098c4d2847c23f798e1f5de0e0e0e0e0e0e0e0e0e0e0e0e0" # Example hash
        }
    }
    
    def __init__(self, model_dir: str):
        self.model_dir = pathlib.Path(model_dir)
        self.logger = logging.getLogger("ChronoArchiver") # Updated logger name
        self.stop_event = threading.Event()

    def verify_hash(self, file_path: pathlib.Path, expected_sha: str) -> bool:
        """Verify the SHA-256 hash of a file."""
        import hashlib
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest() == expected_sha
        except Exception:
            return False

    def get_missing_models(self):
        """Returns a list of model keys that are missing or corrupt."""
        missing = []
        for key, info in self.MODELS.items():
            path = self.model_dir / info["filename"]
            if not path.exists() or not self.verify_hash(path, info["sha256"]):
                missing.append(key)
        return missing

    def is_up_to_date(self):
        """Returns True if all models are present and valid."""
        return len(self.get_missing_models()) == 0

    def download_models(self, progress_callback=None):
        """Downloads all missing/corrupt models. progress_callback(current_size, total_size, filename)"""
        missing = self.get_missing_models()
        if not missing:
            return True

        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.stop_event.clear()

        for key in missing:
            if self.stop_event.is_set():
                break
            
            info = self.MODELS[key]
            url = info["url"]
            dest = self.model_dir / info["filename"]
            
            self.logger.info(f"Downloading model: {info['filename']}")
            
            try:
                # Remove if exists (might be corrupt)
                if dest.exists(): dest.unlink()

                response = requests.get(url, stream=True, timeout=30)
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                
                with open(dest, 'wb') as f:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if self.stop_event.is_set():
                            break
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback:
                                progress_callback(downloaded, total_size, info["filename"])
                
                if self.stop_event.is_set():
                    if dest.exists(): dest.unlink()
                    self.logger.info(f"Download cancelled for {info['filename']}")
                    return False

                # Verify after download
                if not self.verify_hash(dest, info["sha256"]):
                    self.logger.error(f"Integrity check failed for {info['filename']}")
                    if dest.exists(): dest.unlink()
                    return False

            except Exception as e:
                self.logger.error(f"Failed to download {info['filename']}: {e}")
                if dest.exists(): dest.unlink()
                return False

        return self.is_up_to_date()

        return self.is_up_to_date()

    def cancel(self):
        self.stop_event.set()
