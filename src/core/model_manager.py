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
            "url": "https://github.com/opencv/opencv_zoo/raw/master/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
        },
        "animal_detection": {
            "filename": "efficientdet_lite0.tflite",
            "url": "https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/float16/1/efficientdet_lite0.tflite"
        }
    }
    
    def __init__(self, model_dir: str):
        self.model_dir = pathlib.Path(model_dir)
        self.logger = logging.getLogger("MediaOrganizer")
        self.stop_event = threading.Event()

    def get_missing_models(self):
        """Returns a list of model keys that are missing from disk."""
        missing = []
        for key, info in self.MODELS.items():
            if not (self.model_dir / info["filename"]).exists():
                missing.append(key)
        return missing

    def is_up_to_date(self):
        """Returns True if all models are present."""
        return len(self.get_missing_models()) == 0

    def download_models(self, progress_callback=None):
        """Downloads all missing models. progress_callback(current_size, total_size, filename)"""
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
                response = requests.get(url, stream=True)
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
                    if dest.exists():
                        dest.unlink()
                    self.logger.info(f"Download cancelled for {info['filename']}")
                    return False

            except Exception as e:
                self.logger.error(f"Failed to download {info['filename']}: {e}")
                return False

        return self.is_up_to_date()

    def cancel(self):
        self.stop_event.set()
