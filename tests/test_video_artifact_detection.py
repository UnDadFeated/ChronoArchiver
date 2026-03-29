"""Unit and integration tests for ``core.video_artifact_detection``."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from core.video_artifact_detection import (
    ARTIFACT_MASK_MAX_EDGE,
    IMAGE_ARTIFACT_MASK_PERCENTILE_GATE,
    detect_artifact_mask_u8,
    prepare_source_for_realesrgan,
)


def test_detect_empty_bgr_returns_minimal_mask():
    empty = np.zeros((0, 0, 3), dtype=np.uint8)
    m = detect_artifact_mask_u8(empty)
    assert m.shape == (1, 1)
    assert m.dtype == np.uint8
    assert int(m.max()) == 0


def test_prepare_identity_when_no_mask():
    bgr = np.random.randint(0, 255, (24, 32, 3), dtype=np.uint8)
    out = prepare_source_for_realesrgan(bgr, None, lama=None)
    assert out is bgr


def test_prepare_identity_when_mask_empty():
    bgr = np.ones((16, 16, 3), dtype=np.uint8) * 128
    z = np.zeros((8, 8), dtype=np.uint8)
    out = prepare_source_for_realesrgan(bgr, z, lama=None)
    assert np.array_equal(out, bgr)


def test_prepare_skips_inpaint_when_mask_coverage_too_high():
    """Uniform strong mask → coverage check returns original (no Telea/LaMa)."""
    h, w = 80, 80
    bgr = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)
    mask_small = np.full((32, 32), 255, dtype=np.uint8)
    out = prepare_source_for_realesrgan(bgr, mask_small, lama=None)
    assert np.array_equal(out, bgr)


def test_detect_small_synthetic_bgr_produces_uint8_mask():
    """No Test_Files: tiny BGR still runs the full detector."""
    bgr = np.zeros((64, 48, 3), dtype=np.uint8)
    bgr[10:20, 10:20, :] = 200
    m = detect_artifact_mask_u8(bgr)
    assert m.ndim == 2
    assert m.dtype == np.uint8
    assert m.shape[0] <= ARTIFACT_MASK_MAX_EDGE + 2
    assert m.shape[1] <= ARTIFACT_MASK_MAX_EDGE + 2
    assert int(m.max()) <= 255


@pytest.mark.integration
def test_detect_artifact_mask_on_sample_photo(sample_photo_jpg: Path):
    import cv2

    bgr = cv2.imread(str(sample_photo_jpg), cv2.IMREAD_COLOR)
    assert bgr is not None
    m = detect_artifact_mask_u8(bgr)
    assert m.dtype == np.uint8
    assert m.size > 0
    assert int(m.max()) <= 255


@pytest.mark.integration
def test_detect_stricter_image_percentile_gate(sample_photo_jpg: Path):
    """Image path uses higher gate; response should be sparser or equal vs default."""
    import cv2

    bgr = cv2.imread(str(sample_photo_jpg), cv2.IMREAD_COLOR)
    assert bgr is not None
    m_default = detect_artifact_mask_u8(bgr)
    m_image = detect_artifact_mask_u8(bgr, percentile_gate=IMAGE_ARTIFACT_MASK_PERCENTILE_GATE)
    assert int(m_image.sum()) <= int(m_default.sum()) + 1


@pytest.mark.integration
def test_prepare_does_not_crash_on_sample_photo(sample_photo_jpg: Path):
    import cv2

    bgr = cv2.imread(str(sample_photo_jpg), cv2.IMREAD_COLOR)
    assert bgr is not None
    mask = detect_artifact_mask_u8(bgr, percentile_gate=IMAGE_ARTIFACT_MASK_PERCENTILE_GATE)
    out = prepare_source_for_realesrgan(bgr, mask, lama=None)
    assert out.shape == bgr.shape
    assert out.dtype == np.uint8
