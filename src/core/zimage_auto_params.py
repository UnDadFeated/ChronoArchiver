"""
Automatic Z-Image img2img parameters (scale, max edge, strength, steps, CFG).

Heuristics from source size, portrait/beautify, and freckle hint only (no user prompt field).

**Reference (public guides):** Z-Image Turbo img2img “polish” passes often use **strength ~0.15–0.25**
and **~8 steps**; text-to-image recipes for this family frequently use **very low guidance** (0–2).
Beautify needs **stronger** text steering than plain upscale (magazine / glamour intent) but still
**below** typical SD portrait CFG — use **~3** so negatives and positives both apply without the
muddy reds/greys seen at CFG 6+ on this checkpoint. **Plain upscale** keeps **lower strength** and
**cfg=0** for maximum fidelity.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ZImageAutoParams:
    scale: int
    max_side: int
    strength: float
    steps: int
    cfg: float
    summary: str


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _pick_scale_and_max_side(ow: int, oh: int) -> tuple[int, int]:
    """Smaller sources get higher integer scale; large sources stay conservative for VRAM."""
    m = max(int(ow), int(oh), 1)
    if m <= 480:
        scale, max_side = 4, 2048
    elif m <= 800:
        scale, max_side = 3, 2304
    elif m <= 1400:
        scale, max_side = 2, 2560
    elif m <= 2200:
        scale, max_side = 2, 2048
    else:
        scale, max_side = 2, 1792
    return scale, max_side


def infer_zimage_params(
    *,
    ow: int,
    oh: int,
    portrait_detected: bool = False,
    freckle_heavy: bool = False,
    beautify: bool = False,
) -> ZImageAutoParams:
    """
    :param ow, oh: Source image dimensions (pixels).
    :param portrait_detected: True when a face was found (used only with ``beautify``).
    :param freckle_heavy: Heuristic — slightly lower strength/CFG when Beautify + portrait (dense freckles).
    :param beautify: If True and a face exists, use **magazine-style** img2img (higher strength than plain upscale).
    """
    scale, max_side = _pick_scale_and_max_side(ow, oh)
    if beautify and portrait_detected:
        # Clear separation from plain upscale: “controlled glam” band (~0.27–0.32 in public Z-Image img2img guides).
        strength = 0.29
        steps = 9
        cfg = 3.0
        if freckle_heavy:
            # Dense freckles: less denoise + slightly lower CFG so color stays coherent.
            steps = 9
            cfg = 2.55
            strength = _clamp(strength - 0.06, 0.20, 0.32)
        summary = (
            f"Beautify (magazine / glam){' + freckle hint' if freckle_heavy else ''}: "
            f"{scale}×, max edge {max_side}px, "
            f"strength={strength:.2f}, steps={steps}, cfg={cfg:.2f}"
        )
    else:
        # Plain upscale: weaker img2img than Beautify so the two modes feel clearly different.
        strength = 0.18
        steps = 6
        cfg = 0.0
        summary = (
            f"high-fidelity minimal-change upscale: {scale}×, max edge {max_side}px, "
            f"strength={strength:.2f}, steps={steps}, cfg=0"
        )
    return ZImageAutoParams(
        scale=scale,
        max_side=max_side,
        strength=round(float(strength), 2),
        steps=steps,
        cfg=round(float(cfg), 2),
        summary=summary,
    )
