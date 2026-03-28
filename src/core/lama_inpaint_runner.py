"""LaMa neural inpainting via TorchScript (big-lama.pt). BGR uint8 in/out."""

from __future__ import annotations

import logging
import warnings
from pathlib import Path

import numpy as np

from core.video_artifact_detection import ARTIFACT_MASK_INPAINT_THRESHOLD_U8

_log = logging.getLogger("ChronoArchiver.lama_inpaint")

# Adapted from simple-lama-inpainting (MIT) / advimman/lama padding helpers.
_lama_checkpoint_cache: dict[str, tuple[float, int, bool, str, bool]] = {}


def _load_lama_jit(path: str | Path, *, map_location):
    """
    Load LaMa TorchScript (big-lama.pt). PyTorch 3.14+ deprecates ``torch.jit.load`` in favor of
    ``torch.export``; we keep JIT until upstream ships a compatible artifact.
    """
    import torch

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return torch.jit.load(str(path), map_location=map_location)


def invalidate_lama_checkpoint_cache(model_path: str | Path) -> None:
    _lama_checkpoint_cache.pop(str(Path(model_path).resolve()), None)


def validate_lama_torchscript_file(model_path: str | Path) -> tuple[bool, str, bool]:
    """Load TorchScript and run a tiny forward. Returns (ok, message, should_quarantine)."""
    p = Path(model_path)
    try:
        st = p.stat()
    except OSError as e:
        return False, str(e), False
    key = str(p.resolve())
    ent = _lama_checkpoint_cache.get(key)
    if ent and ent[0] == st.st_mtime and ent[1] == st.st_size:
        return ent[2], ent[3], ent[4]

    try:
        import torch

        m = _load_lama_jit(p, map_location="cpu")
        m.eval()
        with torch.no_grad():
            ok_fwd = False
            for sz in (64, 96, 128, 192, 256):
                try:
                    x = torch.zeros(1, 3, sz, sz, dtype=torch.float32)
                    mk = torch.zeros(1, 1, sz, sz, dtype=torch.float32)
                    _ = m(x, mk)
                    ok_fwd = True
                    break
                except Exception:
                    continue
            if not ok_fwd:
                raise RuntimeError("LaMa TorchScript forward failed at test sizes")
    except Exception as e:
        err = str(e)
        _lama_checkpoint_cache[key] = (st.st_mtime, st.st_size, False, err, True)
        return False, err, True

    _lama_checkpoint_cache[key] = (st.st_mtime, st.st_size, True, "", False)
    return True, "", False


def _get_image(img: np.ndarray) -> np.ndarray:
    if img.ndim == 3:
        chw = np.transpose(img, (2, 0, 1))
    elif img.ndim == 2:
        chw = img[np.newaxis, ...]
    else:
        raise ValueError("bad image ndim")
    return chw.astype(np.float32) / 255.0


def _ceil_modulo(x: int, mod: int) -> int:
    if x % mod == 0:
        return x
    return (x // mod + 1) * mod


def _pad_img_to_modulo(img: np.ndarray, mod: int) -> tuple[np.ndarray, int, int]:
    _, height, width = img.shape
    out_height = _ceil_modulo(height, mod)
    out_width = _ceil_modulo(width, mod)
    padded = np.pad(
        img,
        ((0, 0), (0, out_height - height), (0, out_width - width)),
        mode="symmetric",
    )
    return padded, height, width


class LamaInpaintRunner:
    def __init__(self, model_path: str | Path, *, device=None) -> None:
        import torch

        self._torch = torch
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = _load_lama_jit(model_path, map_location=self.device)
        self.model.eval()
        self.model.to(self.device)

    def inpaint_bgr(self, bgr: np.ndarray, mask_u8: np.ndarray) -> np.ndarray:
        """``mask_u8`` same size as ``bgr`` or resized; 0 = keep, 255 = strong artifact (soft OK).

        Soft/blurred masks must be thresholded before LaMa: the JIT model binarizes with ``mask > 0``,
        so any positive value becomes a full hole — without a floor, almost the whole frame is
        inpainted (grey mud). We match :data:`ARTIFACT_MASK_INPAINT_THRESHOLD_U8` with Telea, then
        paste LaMa only where the binary mask is set and keep original pixels elsewhere.
        """
        import cv2

        if bgr is None or bgr.size == 0:
            return bgr
        h, w = bgr.shape[:2]
        if mask_u8.shape[0] != h or mask_u8.shape[1] != w:
            mask_u8 = cv2.resize(mask_u8, (w, h), interpolation=cv2.INTER_LINEAR)

        rgb_full = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        m = mask_u8.astype(np.float32) / 255.0
        thr = ARTIFACT_MASK_INPAINT_THRESHOLD_U8 / 255.0
        mask_bin = (m >= thr).astype(np.float32)
        if not np.any(mask_bin > 0.5):
            return bgr

        max_edge = 1024
        nh, nw = h, w
        rgb_s = rgb_full
        mask_s = mask_bin
        if max(h, w) > max_edge:
            scale = max_edge / float(max(h, w))
            nh, nw = max(1, int(h * scale)), max(1, int(w * scale))
            rgb_s = cv2.resize(rgb_full, (nw, nh), cv2.INTER_AREA)
            mask_s = cv2.resize(mask_bin, (nw, nh), interpolation=cv2.INTER_NEAREST)

        mask_gray = (np.clip(mask_s, 0.0, 1.0) * 255.0).astype(np.uint8)

        out_s = self._inpaint_rgb_numpy(rgb_s, mask_gray)
        if nh != h or nw != w:
            out_full = cv2.resize(out_s, (w, h), interpolation=cv2.INTER_LANCZOS4)
        else:
            out_full = out_s

        mb = mask_bin[..., np.newaxis]
        out_rgb = np.clip(
            rgb_full.astype(np.float32) * (1.0 - mb) + out_full.astype(np.float32) * mb,
            0,
            255,
        ).astype(np.uint8)
        return cv2.cvtColor(out_rgb, cv2.COLOR_RGB2BGR)

    def _inpaint_rgb_numpy(self, rgb: np.ndarray, mask_u8: np.ndarray) -> np.ndarray:
        torch = self._torch
        out_image = _get_image(rgb)
        out_mask = _get_image(mask_u8)
        if out_mask.shape[0] == 1:
            pass
        elif out_mask.shape[0] == 3:
            out_mask = out_mask[0:1]
        else:
            out_mask = out_mask[:1]

        orig_h, orig_w = out_image.shape[1], out_image.shape[2]
        out_image, ph, pw = _pad_img_to_modulo(out_image, 8)
        out_mask, _, _ = _pad_img_to_modulo(out_mask, 8)

        ti = torch.from_numpy(out_image).unsqueeze(0).to(self.device)
        tm = torch.from_numpy(out_mask).unsqueeze(0).to(self.device)
        # Binary holes only (runner passes thresholded mask); never treat epsilon-soft as full mask.
        tm = (tm > 0.5).float()

        with torch.inference_mode():
            inpainted = self.model(ti, tm)

        cur = inpainted[0].permute(1, 2, 0).detach().float().cpu().numpy()
        cur = np.nan_to_num(cur, nan=0.0, posinf=1.0, neginf=0.0)
        mx = float(np.nanmax(cur)) if cur.size else 0.0
        if mx <= 1.0 + 1e-3:
            cur = np.clip(cur * 255.0, 0, 255)
        else:
            cur = np.clip(cur, 0, 255)
        cur = cur.astype(np.uint8)
        cur = cur[:orig_h, :orig_w]
        return cur
