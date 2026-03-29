# ChronoArchiver test inventory

## Layout

| File | Role |
|------|------|
| `conftest.py` | `sys.path` → `src/`, fixtures: `repo_root`, `test_files_dir`, `sample_photo_jpg`, `sample_video_path` |
| `test_smoke_imports.py` | Core modules import without side effects |
| `test_app_paths.py` | `app_paths` helpers |
| `test_realesrgan_helpers.py` | Video upscaler math / caps (no weights) |
| `test_video_target_presets.py` | Preset keys and scale mapping |
| `test_video_artifact_detection.py` | Artifact mask + `prepare_source_for_realesrgan` (unit + `Test_Files`) |
| `test_test_files_workspace.py` | `Test_Files/` tree readable (skipped if folder missing) |
| `test_integration_*.py` | FFmpeg, OpenCV, ML runtime, AV1, organizer, scanner, RRDBNet — `@pytest.mark.integration` |
| `test_qt_offscreen.py` | Minimal Qt (`@pytest.mark.qt`) |

## Markers

- **`integration`**: FFmpeg/OpenCV/torch/media; uses **`Test_Files/`** when present.
- **`qt`**: PySide6 offscreen.

## Running (automation)

From repo root, with dev deps and `src` on path (pytest does this via `pyproject.toml`):

```bash
python -m pip install -r requirements.txt pytest
# optional: same venv as the app (PyTorch, PySide6, etc.)
python -m pytest tests/ -v --tb=short
```

**With optional media** (local only; not in CI):

- Clone or keep **`Test_Files/Test_Photos`** and **`Test_Files/Test_Videos`** under the repo root.
- Integration tests that need them will run; otherwise they **skip** with a clear message.

**Subsets:**

```bash
python -m pytest tests/ -m integration -v
python -m pytest tests/ -m qt -v
python -m pytest tests/ -m "not qt" -v
```

**CI (`.github/workflows/ci.yml`)**: Ubuntu, Python 3.12, FFmpeg, `requirements.txt` + CPU torch, **no** `Test_Files` — integration tests skip media-dependent cases; smoke + unit paths still run.
