"""
Heuristic detection of common digital video defects (macroblocking, combing, banding, chroma stress,
dropout). Produces a downscaled uint8 mask per frame for the second pass.

The encode pass blends inpainted pixels with the source where the mask is high (LaMa neural
inpainting when weights are installed, else OpenCV Telea), then Real-ESRGAN runs on the blended image.
"""

from __future__ import annotations

import numpy as np

# Downscaled mask size cap (storage + speed); resized to full frame for repair.
ARTIFACT_MASK_MAX_EDGE = 256

# Soft artifact masks are blurred; LaMa/Telea must use a threshold so faint pixels are not
# treated as full holes (TorchScript uses mask>0 → entire frame becomes “inpaint” → grey mud).
# Stricter than early Telea-only tuning: we only want confident digital-defect pixels.
ARTIFACT_MASK_INPAINT_THRESHOLD_U8 = 42

# After combining layers, drop the bottom of the response (texture/edges often sit in the bulk).
# Keeps only the strongest ~percentile tail as “defect” signal (per frame, on downscaled map).
ARTIFACT_MASK_PERCENTILE_GATE = 91.0

# Blend toward inpainted pixels (Telea/LaMa); keep most of the original so SR refines real detail.
ARTIFACT_INPAINT_BLEND = 0.48

# If this fraction of pixels would be treated as defective, skip inpaint entirely (SR only).
ARTIFACT_MASK_MAX_COVERAGE_FRAC = 0.045

# LaMa is for localized holes; above this mask density use classical Telea only (or skip above max).
ARTIFACT_LAMA_MAX_COVERAGE_FRAC = 0.018

# AI Image Upscaler (Z-Image): stills have more fine detail misclassified as “defects” — stricter gate
# and smaller blend/coverage so we only touch minor compression/blockiness, not the whole photo.
IMAGE_ARTIFACT_MASK_PERCENTILE_GATE = 92.5
IMAGE_UPSCALER_INPAINT_BLEND = 0.36
IMAGE_UPSCALER_MAX_COVERAGE_FRAC = 0.032
IMAGE_UPSCALER_LAMA_MAX_COVERAGE_FRAC = 0.011


def detect_artifact_mask_u8(
    bgr,
    *,
    max_edge: int = ARTIFACT_MASK_MAX_EDGE,
    percentile_gate: float | None = None,
) -> np.ndarray:
    """
    Return a single-channel uint8 mask (H×W at downscaled size): 0 = clean, 255 = strong artifact.

    Combines: macroblock/pixelation, horizontal combing/interlace stress, banding, chroma bleeding
    (high chroma Laplacian), dropout/clipped flat regions.
    """
    import cv2

    if bgr is None or bgr.size == 0:
        return np.zeros((1, 1), dtype=np.uint8)
    h0, w0 = bgr.shape[:2]
    sm = bgr
    m = max(h0, w0)
    if m > max_edge:
        s = max_edge / float(m)
        sm = cv2.resize(bgr, (max(1, int(w0 * s)), max(1, int(h0 * s))), cv2.INTER_AREA)
    h, w = sm.shape[:2]
    y = cv2.cvtColor(sm, cv2.COLOR_BGR2GRAY)
    yf = y.astype(np.float32)
    layers: list[np.ndarray] = []

    # 1) Macroblocking / heavy pixelation: NN upscale of coarse grid vs original
    tw = max(8, w // 8)
    th = max(8, h // 8)
    tiny = cv2.resize(sm, (tw, th), cv2.INTER_AREA)
    nn = cv2.resize(tiny, (w, h), cv2.INTER_NEAREST)
    d = cv2.cvtColor(cv2.absdiff(sm, nn), cv2.COLOR_BGR2GRAY).astype(np.float32)
    # Do not NORM_MINMAX (that labels arbitrary texture as full-strength defect every frame).
    p99d = float(np.percentile(d, 99.0)) + 1e-6
    layers.append(np.clip(d / p99d * 255.0, 0, 255).astype(np.uint8))

    # 2) Interlace / combing — also fires on horizontal edges in progressive video; downweight.
    sy = cv2.Sobel(y, cv2.CV_32F, 0, 1, ksize=3)
    comb = np.abs(sy)
    p99 = float(np.percentile(comb, 99.0)) + 1e-6
    comb_u8 = np.clip(comb / p99 * 255.0, 0, 255).astype(np.uint8)
    layers.append((comb_u8.astype(np.float32) * 0.5).clip(0, 255).astype(np.uint8))

    # 3) Banding: second vertical derivative (step edges in gradients)
    gy = cv2.Sobel(yf, cv2.CV_32F, 0, 1, ksize=5)
    dgy = cv2.Sobel(gy, cv2.CV_32F, 0, 1, ksize=3)
    ab = np.abs(dgy)
    p99b = float(np.percentile(ab, 99.0)) + 1e-6
    layers.append(np.clip(ab / p99b * 255.0, 0, 255).astype(np.uint8))

    # 4) Chroma bleeding / chroma errors: high Laplacian energy in U/V
    yuv = cv2.cvtColor(sm, cv2.COLOR_BGR2YUV)
    u = yuv[:, :, 1].astype(np.float32)
    v = yuv[:, :, 2].astype(np.float32)
    lu = cv2.Laplacian(u, cv2.CV_32F)
    lv = cv2.Laplacian(v, cv2.CV_32F)
    chrom = np.sqrt(lu * lu + lv * lv)
    p99c = float(np.percentile(chrom, 99.0)) + 1e-6
    layers.append(np.clip(chrom / p99c * 255.0, 0, 255).astype(np.uint8))

    # 5) Dropout / clipped flat patches (dead sensor blocks, macro corruption)
    local = cv2.medianBlur(y, 5)
    flat = cv2.absdiff(y, local)
    _, flatm = cv2.threshold(flat, 3, 255, cv2.THRESH_BINARY_INV)
    _, dark = cv2.threshold(y, 10, 255, cv2.THRESH_BINARY_INV)
    _, bright = cv2.threshold(y, 245, 255, cv2.THRESH_BINARY)
    dropout = cv2.bitwise_and(cv2.bitwise_or(dark, bright), flatm)
    layers.append(dropout)

    out = np.maximum.reduce(layers)
    out = cv2.GaussianBlur(out, (3, 3), 0)
    # Per-frame gate: keep only the upper tail (true blockiness tends to spike above texture floor).
    gate = float(percentile_gate if percentile_gate is not None else ARTIFACT_MASK_PERCENTILE_GATE)
    flat = out.astype(np.float32).ravel()
    pg = float(np.percentile(flat, gate))
    out = np.maximum(flat - pg, 0.0).reshape(out.shape)
    mx = float(out.max())
    if mx > 1e-6:
        out = (out * (255.0 / mx)).clip(0, 255).astype(np.uint8)
    else:
        out = np.zeros_like(layers[0], dtype=np.uint8)
    return out


def prepare_source_for_realesrgan(
    bgr,
    mask_small: np.ndarray | None,
    *,
    lama: object | None = None,
    inpaint_blend: float = ARTIFACT_INPAINT_BLEND,
    max_coverage_frac: float = ARTIFACT_MASK_MAX_COVERAGE_FRAC,
    lama_max_coverage_frac: float = ARTIFACT_LAMA_MAX_COVERAGE_FRAC,
) -> np.ndarray:
    """
    Light touch-up of **digital defects** only, then Real-ESRGAN upscales.

    Order is already: optional classical/neural inpaint blend → SR. We do **not** repaint the scene;
    if the heuristic map covers too much of the frame, inpaint is skipped and only SR runs.

    ``mask_small`` is the downscaled mask from :func:`detect_artifact_mask_u8` (same ``max_edge``).
    """
    import cv2

    if bgr is None or bgr.size == 0:
        return bgr
    if mask_small is None or mask_small.size == 0 or not np.any(mask_small):
        return bgr
    h, w = bgr.shape[:2]
    m = cv2.resize(mask_small, (w, h), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
    thr = ARTIFACT_MASK_INPAINT_THRESHOLD_U8 / 255.0
    coverage = float(np.mean(m >= thr))
    if coverage > max_coverage_frac:
        return bgr

    if lama is not None and coverage > lama_max_coverage_frac:
        lama = None

    _, mh = cv2.threshold(
        (m * 255.0).astype(np.uint8),
        ARTIFACT_MASK_INPAINT_THRESHOLD_U8,
        255,
        cv2.THRESH_BINARY,
    )
    if not np.any(mh):
        return bgr
    # Shrink repair regions slightly so edges of real detail stay untouched.
    mh = cv2.erode(mh, np.ones((3, 3), dtype=np.uint8), iterations=1)
    if not np.any(mh):
        return bgr

    mask_full_u8 = (np.clip(m, 0.0, 1.0) * 255.0).astype(np.uint8)
    blend = float(np.clip(inpaint_blend, 0.0, 1.0))
    inp = None
    if lama is not None:
        try:
            inp = lama.inpaint_bgr(bgr, mask_full_u8)
        except Exception:
            inp = None
        if inp is not None and inp.shape == bgr.shape:
            mb = np.clip(m[..., np.newaxis] * blend, 0.0, 1.0)
            return np.clip(
                bgr.astype(np.float32) * (1.0 - mb) + inp.astype(np.float32) * mb,
                0,
                255,
            ).astype(np.uint8)
    inp = cv2.inpaint(bgr, mh, 5, cv2.INPAINT_TELEA)
    mb = np.clip(m[..., np.newaxis] * blend, 0.0, 1.0)
    return np.clip(
        bgr.astype(np.float32) * (1.0 - mb) + inp.astype(np.float32) * mb,
        0,
        255,
    ).astype(np.uint8)
