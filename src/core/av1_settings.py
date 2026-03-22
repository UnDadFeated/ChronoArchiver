import json
import os
import platformdirs

class AV1Settings:
    """Handles persistent settings for ChronoArchiver AV1 Encoder."""
    
    def __init__(self):
        self.config_dir = platformdirs.user_config_dir("ChronoArchiver")
        self.config_path = os.path.join(self.config_dir, "av1_config.json")
        self.defaults = {
            "quality": 30,
            "preset": "p4",
            "output_ext": ".mkv",
            "reencode_audio": True,
            "concurrent_jobs": 2,
            "source_folder": "",
            "target_folder": "",
            "maintain_structure": True,
            "debug_mode": False,
            "rejects_enabled": False,
            "rejects_h": 0,
            "rejects_m": 0,
            "rejects_s": 10,
            "delete_on_success": False,
            "delete_on_success_confirm": False,
            "hw_accel_decode": False,
            "shutdown_on_finish": False,
            "existing_output": "overwrite"  # overwrite | skip | rename
        }
        self.data = self.load()

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    return {**self.defaults, **json.load(f)}
            except (json.JSONDecodeError, OSError) as e:
                print(f"Error loading config: {e}")
                return self.defaults.copy()
        return self.defaults.copy()

    def save(self):
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self.data, f, indent=4)
        except OSError as e:
            print(f"Error saving config: {e}")

    def get(self, key):
        return self.data.get(key, self.defaults.get(key))

    def set(self, key, value):
        self.data[key] = value
        self.save()
