"""
Per-frame luma / chroma noise scores for AI Video Upscaler (OpenCV stats, no extra NN).

Scores are in [0, 1]. A temporal pass smooths each track so NR strength does not flicker frame
to frame; symmetric smoothing needs a full pre-scan of the source video.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

# Align with video_upscaler_panel heuristics (same analysis sizes / Gauss params).
LUMA_ANALYSIS_MAX_EDGE = 640
LUMA_GAUSS_KSIZE = 7
LUMA_GAUSS_SIGMA = 1.5
# Map HF stats to 0..1 (above old boolean thresholds → mid–high scores).
LUMA_SCORE_MED_SCALE = 10.0  # median HF residual: ~4 threshold → partial score
LUMA_SCORE_MEAN_SCALE = 22.0  # mean HF residual: ~7 threshold

CHROMA_MEAN_Y_LOW = 98.0
CHROMA_MEAN_Y_MID = 132.0
CHROMA_SPREAD_MIN = 22.0
CHROMA_SPREAD_SCALE = 45.0  # std(U)+std(V) extra above baseline → score


def _resize_bgr_for_analysis(bgr, max_edge: int):
    import cv2

    if bgr is None or bgr.size == 0:
        return bgr
    h, w = bgr.shape[:2]
    m = max(h, w)
    if m <= max_edge or m <= 0:
        return bgr
    s = float(max_edge) / float(m)
    nh, nw = max(1, int(h * s)), max(1, int(w * s))
    return cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_AREA)


def luma_noise_score_from_source(bgr) -> float:
    """
    Continuous luma noise score [0, 1] from source BGR (high-frequency residual on Y).
    """
    import cv2

    if bgr is None or bgr.size == 0:
        return 0.0
    bgr = _resize_bgr_for_analysis(bgr, LUMA_ANALYSIS_MAX_EDGE)
    yuv = cv2.cvtColor(bgr, cv2.COLOR_BGR2YUV)
    y = yuv[:, :, 0]
    k = LUMA_GAUSS_KSIZE | 1
    if k < 3:
        k = 3
    blur = cv2.GaussianBlur(y, (k, k), LUMA_GAUSS_SIGMA)
    diff = np.abs(y.astype(np.float32) - blur.astype(np.float32))
    med = float(np.median(diff))
    mean_hf = float(np.mean(diff))
    s_med = float(np.clip((med - 2.0) / LUMA_SCORE_MED_SCALE, 0.0, 1.0))
    s_mean = float(np.clip((mean_hf - 3.0) / LUMA_SCORE_MEAN_SCALE, 0.0, 1.0))
    return float(np.clip(0.45 * s_med + 0.55 * s_mean, 0.0, 1.0))


def chroma_noise_score_from_source(bgr) -> float:
    """
    Continuous chroma noise score [0, 1] from YUV spread + luma (low light / tape speckle).
    """
    import cv2

    if bgr is None or bgr.size == 0:
        return 0.0
    yuv = cv2.cvtColor(bgr, cv2.COLOR_BGR2YUV)
    y, u, v = cv2.split(yuv)
    mean_y = float(np.mean(y.astype(np.float32)))
    chroma_spread = float(np.std(u.astype(np.float32))) + float(np.std(v.astype(np.float32)))
    s_spread = float(np.clip((chroma_spread - 12.0) / CHROMA_SPREAD_SCALE, 0.0, 1.0))
    if mean_y < CHROMA_MEAN_Y_LOW:
        s_dark = 0.55 + 0.45 * min(1.0, (CHROMA_MEAN_Y_LOW - mean_y) / CHROMA_MEAN_Y_LOW)
        return float(np.clip(max(s_dark, s_spread), 0.0, 1.0))
    if mean_y < CHROMA_MEAN_Y_MID and chroma_spread >= CHROMA_SPREAD_MIN:
        s_mid = 0.35 + 0.65 * float(np.clip((chroma_spread - CHROMA_SPREAD_MIN) / 35.0, 0.0, 1.0))
        return float(np.clip(max(s_mid, s_spread * 0.85), 0.0, 1.0))
    return float(np.clip(s_spread * 0.5, 0.0, 1.0))


def temporal_smooth_1d(values: np.ndarray, *, radius: int = 2) -> np.ndarray:
    """
    Symmetric weighted moving average (triangular kernel) for arbitrary scalars — no clipping.
    Use for grade parameters (brightness, contrast, …) that are not in [0, 1].
    """
    x = np.asarray(values, dtype=np.float64).ravel()
    n = x.size
    if n <= 1:
        return x.astype(np.float64)
    r = max(0, int(radius))
    k = 2 * r + 1
    t = np.arange(k, dtype=np.float64) - r
    kernel = (r + 1 - np.abs(t)).clip(min=0.0)
    if kernel.sum() <= 0:
        kernel = np.ones(k, dtype=np.float64)
    kernel /= kernel.sum()
    pad = np.pad(x, (r, r), mode="edge")
    out = np.convolve(pad, kernel, mode="valid")
    assert out.shape[0] == n
    return out


def temporal_smooth_scores_1d(scores: np.ndarray, *, radius: int = 2) -> np.ndarray:
    """
    Same as :func:`temporal_smooth_1d` but clips to ``[0, 1]`` (luma/chroma noise strengths).
    """
    return np.clip(temporal_smooth_1d(scores, radius=radius), 0.0, 1.0)


def pre_scan_noise_scores(
    path: str,
    *,
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[np.ndarray, np.ndarray] | None:
    """
    Back-compat: same full pre-scan as :func:`core.video_frame_preanalysis.pre_scan_video_upscale`,
    but returns only temporally smoothed luma/chroma NR strengths.
    """
    from core.video_frame_preanalysis import pre_scan_video_upscale

    r = pre_scan_video_upscale(path, on_progress=on_progress)
    if r is None:
        return None
    return r["luma_nr"], r["chroma_nr"]
