"""
Single-pass video pre-analysis for AI Video Upscaler: noise, grade (per-frame), WB cast, skin warmth,
optional per-frame artifact masks on disk.

All scalar tracks are temporally smoothed (±2 frames) after the full decode pass so grades stay stable
in time. Constants mirror ``video_upscaler_panel`` (keep in sync when tuning).

When ``artifact_dir`` is set, each frame writes ``NNNNNN.npz`` with a compressed ``mask`` (uint8) for
the second pass; callers must delete that directory after encode.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict

import numpy as np

from core.video_artifact_detection import detect_artifact_mask_u8
from core.video_frame_noise import (
    chroma_noise_score_from_source,
    luma_noise_score_from_source,
    temporal_smooth_1d,
    temporal_smooth_scores_1d,
)

# --- Defaults & auto aesthetic (match video_upscaler_panel) ---
VUP_POST_BRIGHTNESS = 0.0
VUP_POST_CONTRAST = 1.03
VUP_POST_SATURATION = 1.0
VUP_UNSHARP_STRENGTH = 0.46

VUP_AESTHETIC_ANALYSIS_MAX_EDGE = 640
VUP_AUTO_AESTH_MEAN_Y_DARK = 52.0
VUP_AUTO_AESTH_MEAN_Y_BRIGHT = 210.0
VUP_AUTO_AESTH_BRIGHTNESS_MAX_DELTA = 10.0
VUP_AUTO_AESTH_STD_Y_FLAT = 34.0
VUP_AUTO_AESTH_STD_Y_PUNCHY = 68.0
VUP_AUTO_AESTH_SAT_DULL = 78.0
VUP_AUTO_AESTH_SAT_HOT = 232.0
VUP_AUTO_AESTH_LAP_SOFT = 140.0
VUP_AUTO_AESTH_LAP_CRISP = 2800.0

VUP_AUTO_CAST_UV_SUM_MIN = 20.0
VUP_AUTO_CAST_STRENGTH_MAX = 0.12

# Skin: HSV mask + dull-skin boost (no ML). Strength is 0–1 before temporal smooth.
_SKIN_ANALYSIS_MAX_EDGE = 560
_SKIN_RATIO_MIN = 0.012


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


def aesthetic_tuple_from_source(bgr) -> tuple[float, float, float, float]:
    """
    Brightness / contrast / saturation / unsharp from one BGR frame.

    Unsharp strength is the sharpness vs softness dial (lower = softer, higher = crisper), derived from
    Laplacian variance on luma — same rules as the former first-frame-only pass.
    """
    import cv2

    if bgr is None or bgr.size == 0:
        return (
            float(VUP_POST_BRIGHTNESS),
            float(VUP_POST_CONTRAST),
            float(VUP_POST_SATURATION),
            float(VUP_UNSHARP_STRENGTH),
        )
    sm = _resize_bgr_for_analysis(bgr, VUP_AESTHETIC_ANALYSIS_MAX_EDGE)
    yuv = cv2.cvtColor(sm, cv2.COLOR_BGR2YUV)
    y_u8 = yuv[:, :, 0]
    y_f = y_u8.astype(np.float32)
    mean_y = float(np.mean(y_f))
    std_y = float(np.std(y_f))

    hsv = cv2.cvtColor(sm, cv2.COLOR_BGR2HSV)
    mean_s = float(np.mean(hsv[:, :, 1].astype(np.float32)))

    lap = cv2.Laplacian(y_u8, cv2.CV_64F)
    lap_var = float(lap.var())

    b = float(VUP_POST_BRIGHTNESS)
    c = float(VUP_POST_CONTRAST)
    s = float(VUP_POST_SATURATION)
    sh = float(VUP_UNSHARP_STRENGTH)

    if mean_y < VUP_AUTO_AESTH_MEAN_Y_DARK:
        b += min(
            VUP_AUTO_AESTH_BRIGHTNESS_MAX_DELTA,
            (VUP_AUTO_AESTH_MEAN_Y_DARK - mean_y) * 0.22,
        )
    elif mean_y > VUP_AUTO_AESTH_MEAN_Y_BRIGHT:
        b -= min(
            VUP_AUTO_AESTH_BRIGHTNESS_MAX_DELTA * 0.6,
            (mean_y - VUP_AUTO_AESTH_MEAN_Y_BRIGHT) * 0.15,
        )

    if std_y < VUP_AUTO_AESTH_STD_Y_FLAT:
        c += min(0.1, (VUP_AUTO_AESTH_STD_Y_FLAT - std_y) / 220.0)
    elif std_y > VUP_AUTO_AESTH_STD_Y_PUNCHY:
        c -= min(0.06, (std_y - VUP_AUTO_AESTH_STD_Y_PUNCHY) / 450.0)

    c = float(np.clip(c, 1.0, 1.16))

    if mean_s < VUP_AUTO_AESTH_SAT_DULL:
        s += min(0.12, (VUP_AUTO_AESTH_SAT_DULL - mean_s) / 380.0)
    elif mean_s > VUP_AUTO_AESTH_SAT_HOT:
        s -= min(0.08, (mean_s - VUP_AUTO_AESTH_SAT_HOT) / 180.0)

    s = float(np.clip(s, 0.9, 1.15))

    if lap_var < VUP_AUTO_AESTH_LAP_SOFT:
        sh *= 1.1
    elif lap_var > VUP_AUTO_AESTH_LAP_CRISP:
        sh *= 0.9

    sh = float(np.clip(sh, 0.32, 0.54))

    b = float(np.clip(b, -VUP_AUTO_AESTH_BRIGHTNESS_MAX_DELTA, VUP_AUTO_AESTH_BRIGHTNESS_MAX_DELTA))

    return (b, c, s, sh)


def cast_strength_from_source(bgr) -> float:
    """Mild YUV chroma centering for global WB drift; 0 = none."""
    import cv2
    import numpy as np

    if bgr is None or bgr.size == 0:
        return 0.0
    sm = _resize_bgr_for_analysis(bgr, VUP_AESTHETIC_ANALYSIS_MAX_EDGE)
    yuv = cv2.cvtColor(sm, cv2.COLOR_BGR2YUV)
    _, u, v = cv2.split(yuv)
    du = float(np.mean(u.astype(np.float32)) - 128.0)
    dv = float(np.mean(v.astype(np.float32)) - 128.0)
    spread = abs(du) + abs(dv)
    if spread < VUP_AUTO_CAST_UV_SUM_MIN:
        return 0.0
    return float(min(VUP_AUTO_CAST_STRENGTH_MAX, (spread - VUP_AUTO_CAST_UV_SUM_MIN) / 320.0))


def skin_tone_strength_from_source(bgr) -> float:
    """
    Heuristic 0–1: how much skin-specific warmth (U/V nudge under HSV skin mask) may help.

    Uses classic HSV skin ranges on a downscaled frame; stronger when more skin coverage and
    duller skin saturation (typical under heavy WB or flat lighting).
    """
    import cv2

    if bgr is None or bgr.size == 0:
        return 0.0
    sm = _resize_bgr_for_analysis(bgr, _SKIN_ANALYSIS_MAX_EDGE)
    hsv = cv2.cvtColor(sm, cv2.COLOR_BGR2HSV)
    m1 = cv2.inRange(hsv, np.array([0, 35, 48], np.uint8), np.array([26, 255, 255], np.uint8))
    m2 = cv2.inRange(hsv, np.array([168, 35, 48], np.uint8), np.array([179, 255, 255], np.uint8))
    mask = cv2.bitwise_or(m1, m2)
    skin_ratio = float(np.count_nonzero(mask)) / float(mask.size)
    if skin_ratio < _SKIN_RATIO_MIN:
        return 0.0
    px = hsv[mask > 0]
    if px.size < 48:
        return 0.0
    mean_s = float(np.mean(px[:, 1].astype(np.float32)))
    # Duller skin (lower S) → allow a bit more corrective warmth
    dull = float(np.clip(1.15 - mean_s / 160.0, 0.25, 1.0))
    return float(np.clip(skin_ratio * 2.8 * dull, 0.0, 1.0))


def apply_skin_tone_warmth_bgr(bgr, strength: float):
    """
    Local YUV nudge toward natural warmth on HSV skin-colored pixels; ``strength`` in [0, 1].
    Applied after global grade and WB cast so it only refines skin regions.
    """
    import cv2

    if bgr is None or bgr.size == 0 or strength <= 1e-6:
        return bgr
    h, w = bgr.shape[:2]
    sm = _resize_bgr_for_analysis(bgr, _SKIN_ANALYSIS_MAX_EDGE)
    hsv = cv2.cvtColor(sm, cv2.COLOR_BGR2HSV)
    m1 = cv2.inRange(hsv, np.array([0, 35, 48], np.uint8), np.array([26, 255, 255], np.uint8))
    m2 = cv2.inRange(hsv, np.array([168, 35, 48], np.uint8), np.array([179, 255, 255], np.uint8))
    mask = cv2.bitwise_or(m1, m2)
    mask = cv2.GaussianBlur(mask, (5, 5), 0)
    if mask.shape[1] != w or mask.shape[0] != h:
        mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_LINEAR)
    m = mask.astype(np.float32) * (1.0 / 255.0)
    yuv = cv2.cvtColor(bgr, cv2.COLOR_BGR2YUV)
    y, u, v = cv2.split(yuv)
    u_f = u.astype(np.float32)
    v_f = v.astype(np.float32)
    du = strength * 0.28 * m * (125.5 - u_f)
    dv = strength * 0.22 * m * (131.0 - v_f)
    u_f = np.clip(u_f + du, 0, 255)
    v_f = np.clip(v_f + dv, 0, 255)
    return cv2.cvtColor(
        cv2.merge([y, u_f.astype(np.uint8), v_f.astype(np.uint8)]),
        cv2.COLOR_YUV2BGR,
    )


def _clip_grade_arrays(
    b: np.ndarray,
    c: np.ndarray,
    s: np.ndarray,
    sh: np.ndarray,
    cast: np.ndarray,
    skin: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    b = np.clip(b, -VUP_AUTO_AESTH_BRIGHTNESS_MAX_DELTA, VUP_AUTO_AESTH_BRIGHTNESS_MAX_DELTA)
    c = np.clip(c, 1.0, 1.16)
    s = np.clip(s, 0.9, 1.15)
    sh = np.clip(sh, 0.32, 0.54)
    cast = np.clip(cast, 0.0, VUP_AUTO_CAST_STRENGTH_MAX)
    skin = np.clip(skin, 0.0, 1.0)
    return b, c, s, sh, cast, skin


class VideoPreanalysis(TypedDict):
    luma_nr: np.ndarray
    chroma_nr: np.ndarray
    brightness: np.ndarray
    contrast: np.ndarray
    saturation: np.ndarray
    sharpness: np.ndarray
    cast: np.ndarray
    skin_tone: np.ndarray


def pre_scan_video_upscale(
    path: str,
    *,
    on_progress: Callable[[int, int], None] | None = None,
    smooth_radius: int = 2,
    artifact_dir: str | None = None,
) -> VideoPreanalysis | None:
    """
    One full decode: per-frame noise, grade (b/c/s/sharpness), cast, skin tone; then temporal smooth.

    If ``artifact_dir`` is set, writes ``{artifact_dir}/{i:06d}.npz`` per frame with key ``mask``
    (uint8 artifact map for :func:`core.video_artifact_detection.prepare_source_for_realesrgan`).

    Sharpness here is unsharp amount (same as softness↔sharpness dial: lower = softer image).
    """
    import os

    import cv2

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None
    nf = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    ls: list[float] = []
    cs: list[float] = []
    bb: list[float] = []
    cc: list[float] = []
    ss: list[float] = []
    shh: list[float] = []
    cst: list[float] = []
    sk: list[float] = []

    fi = 0
    try:
        while True:
            ok, fr = cap.read()
            if not ok or fr is None:
                break
            ls.append(luma_noise_score_from_source(fr))
            cs.append(chroma_noise_score_from_source(fr))
            b, c, s, sh = aesthetic_tuple_from_source(fr)
            bb.append(b)
            cc.append(c)
            ss.append(s)
            shh.append(sh)
            cst.append(cast_strength_from_source(fr))
            sk.append(skin_tone_strength_from_source(fr))
            if artifact_dir is not None:
                am = detect_artifact_mask_u8(fr)
                np.savez_compressed(
                    os.path.join(artifact_dir, f"{fi:06d}.npz"),
                    mask=am,
                )
            fi += 1
            if on_progress is not None:
                n_done = len(ls)
                tot = nf if nf > 0 else 0
                on_progress(n_done, tot)
    finally:
        cap.release()

    if not ls:
        return None
    if on_progress is not None and nf <= 0:
        n = len(ls)
        on_progress(n, n)

    r = max(0, int(smooth_radius))
    luma = temporal_smooth_scores_1d(np.array(ls, dtype=np.float64), radius=r)
    chroma = temporal_smooth_scores_1d(np.array(cs, dtype=np.float64), radius=r)
    b_ar = temporal_smooth_1d(np.array(bb, dtype=np.float64), radius=r)
    c_ar = temporal_smooth_1d(np.array(cc, dtype=np.float64), radius=r)
    s_ar = temporal_smooth_1d(np.array(ss, dtype=np.float64), radius=r)
    sh_ar = temporal_smooth_1d(np.array(shh, dtype=np.float64), radius=r)
    cast_ar = temporal_smooth_1d(np.array(cst, dtype=np.float64), radius=r)
    skin_ar = temporal_smooth_1d(np.array(sk, dtype=np.float64), radius=r)

    b_ar, c_ar, s_ar, sh_ar, cast_ar, skin_ar = _clip_grade_arrays(
        b_ar, c_ar, s_ar, sh_ar, cast_ar, skin_ar
    )
    luma = np.clip(luma, 0.0, 1.0)
    chroma = np.clip(chroma, 0.0, 1.0)

    out: VideoPreanalysis = {
        "luma_nr": luma,
        "chroma_nr": chroma,
        "brightness": b_ar,
        "contrast": c_ar,
        "saturation": s_ar,
        "sharpness": sh_ar,
        "cast": cast_ar,
        "skin_tone": skin_ar,
    }
    return out
