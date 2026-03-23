"""
converter_engine.py — Media conversion engine for ChronoArchiver.
Uses FFmpeg for video, PIL for images. Supports crop, scale, rotate, transparency.
"""

import os
import subprocess
import pathlib
import threading
from typing import List, Callable, Optional, Generator
from dataclasses import dataclass

try:
    from PIL import Image, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from .debug_logger import debug, UTILITY_MEDIA_CONVERTER
except ImportError:
    UTILITY_MEDIA_CONVERTER = "Media Converter"
    def debug(*a): pass

VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.webm', '.mkv', '.m4v', '.wmv', '.mpg', '.mpeg', '.ts'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.tif', '.gif'}


@dataclass
class ConvertOptions:
    out_format: str  # mp4, webp, jpg, etc.
    crop_x: int = 0
    crop_y: int = 0
    crop_w: int = 0
    crop_h: int = 0
    scale_w: int = 0
    scale_h: int = 0
    scale_pct: int = 0  # 0 = use w/h, else percentage
    rotate: int = 0  # 0, 90, 180, 270
    transparency: bool = False  # for PNG/WebP
    quality: int = 95  # for lossy formats


class ConverterEngine:
    """Engine for batch media conversion (video via FFmpeg, images via PIL)."""

    def __init__(self, logger_callback: Optional[Callable[[str], None]] = None):
        self.logger = logger_callback or (lambda x: debug(UTILITY_MEDIA_CONVERTER, x))
        self.cancel_flag = False

    def cancel(self):
        self.cancel_flag = True

    def scan_files(
        self,
        directory: str,
        include_photos: bool = True,
        include_videos: bool = True,
        recursive: bool = True,
        stop_event: Optional[threading.Event] = None,
    ) -> Generator[tuple, None, None]:
        """Yield (full_path, size, 'video'|'image') for each media file."""
        exts = set()
        if include_photos:
            exts.update(IMAGE_EXTS)
        if include_videos:
            exts.update(VIDEO_EXTS)
        if not exts:
            return
        try:
            for root, dirs, files in os.walk(directory):
                if stop_event and stop_event.is_set():
                    break
                if not recursive:
                    dirs.clear()
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                for f in files:
                    ext = pathlib.Path(f).suffix.lower()
                    if ext not in exts:
                        continue
                    full = os.path.join(root, f)
                    try:
                        size = os.path.getsize(full)
                    except OSError:
                        size = 0
                    kind = "video" if ext in VIDEO_EXTS else "image"
                    yield (full, size, kind)
        except Exception as e:
            self.logger(f"Scan error: {e}")

    def convert_file(
        self,
        src: str,
        dst: str,
        opts: ConvertOptions,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> bool:
        """Convert one file. Returns True on success."""
        ext = pathlib.Path(src).suffix.lower()
        is_video = ext in VIDEO_EXTS
        if is_video:
            return self._convert_video(src, dst, opts, progress_callback)
        return self._convert_image(src, dst, opts, progress_callback)

    def _convert_video(
        self,
        src: str,
        dst: str,
        opts: ConvertOptions,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> bool:
        """Convert video via FFmpeg."""
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        vf_parts = []
        if opts.crop_w > 0 and opts.crop_h > 0:
            vf_parts.append(f"crop={opts.crop_w}:{opts.crop_h}:{opts.crop_x}:{opts.crop_y}")
        if opts.scale_w > 0 or opts.scale_h > 0:
            if opts.scale_w > 0 and opts.scale_h > 0:
                vf_parts.append(f"scale={opts.scale_w}:{opts.scale_h}")
            elif opts.scale_w > 0:
                vf_parts.append(f"scale={opts.scale_w}:-2")
            else:
                vf_parts.append(f"scale=-2:{opts.scale_h}")
        elif opts.scale_pct > 0:
            vf_parts.append(f"scale=iw*{opts.scale_pct}/100:ih*{opts.scale_pct}/100")
        if opts.rotate == 90:
            vf_parts.append("transpose=1")
        elif opts.rotate == 180:
            vf_parts.append("hflip,vflip")
        elif opts.rotate == 270:
            vf_parts.append("transpose=2")
        vf = ",".join(vf_parts) if vf_parts else None
        fmt = opts.out_format.lower().lstrip(".")
        codec = "libx264" if fmt in ("mp4", "mkv", "avi", "mov") else "libvpx-vp9" if fmt == "webm" else "libx264"
        cmd = ["ffmpeg", "-y", "-i", src]
        if vf:
            cmd.extend(["-vf", vf])
        cmd.extend(["-c:v", codec, "-c:a", "copy", dst])
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if r.returncode != 0:
                self.logger(f"FFmpeg error: {r.stderr[:200] if r.stderr else 'unknown'}")
                return False
            return True
        except subprocess.TimeoutExpired:
            self.logger("FFmpeg timeout")
            return False
        except Exception as e:
            self.logger(f"Convert error: {e}")
            return False

    def _convert_image(
        self,
        src: str,
        dst: str,
        opts: ConvertOptions,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> bool:
        """Convert image via PIL."""
        if not PIL_AVAILABLE:
            self.logger("PIL not available")
            return False
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        try:
            with Image.open(src) as img:
                img = ImageOps.exif_transpose(img)
                fmt = opts.out_format.lower().lstrip(".")
                if img.mode in ("RGBA", "LA") and fmt in ("jpg", "jpeg") and not opts.transparency:
                    img = img.convert("RGB")
                if opts.crop_w > 0 and opts.crop_h > 0:
                    img = img.crop((opts.crop_x, opts.crop_y, opts.crop_x + opts.crop_w, opts.crop_y + opts.crop_h))
                if opts.rotate == 90:
                    img = img.rotate(-90, expand=True)
                elif opts.rotate == 180:
                    img = img.rotate(180, expand=True)
                elif opts.rotate == 270:
                    img = img.rotate(90, expand=True)
                w, h = img.size
                if opts.scale_w > 0 or opts.scale_h > 0:
                    if opts.scale_w > 0 and opts.scale_h > 0:
                        nw, nh = opts.scale_w, opts.scale_h
                    elif opts.scale_w > 0:
                        nw, nh = opts.scale_w, int(h * opts.scale_w / w)
                    else:
                        nw, nh = int(w * opts.scale_h / h), opts.scale_h
                    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
                elif opts.scale_pct > 0:
                    nw = max(1, w * opts.scale_pct // 100)
                    nh = max(1, h * opts.scale_pct // 100)
                    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
                if fmt in ("png", "webp") and opts.transparency and img.mode != "RGBA":
                    img = img.convert("RGBA")
                save_kw = {}
                if fmt in ("jpg", "jpeg", "webp"):
                    save_kw["quality"] = opts.quality
                if fmt == "webp" and opts.transparency:
                    save_kw["lossless"] = False
                img.save(dst, **save_kw)
            return True
        except Exception as e:
            self.logger(f"Image convert error: {e}")
            return False
