"""
converter_panel.py — Media Converter panel for ChronoArchiver.
Convert video/photo with crop, scale, rotate, transparency. FFmpeg + PIL.
"""

import os
import threading
import pathlib

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QCheckBox,
    QProgressBar, QFileDialog, QListWidget, QSizePolicy,
    QComboBox, QSpinBox, QGridLayout, QFrame,
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer
from PySide6.QtGui import QShowEvent

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from core.converter_engine import ConverterEngine, ConvertOptions
from core.debug_logger import debug, UTILITY_MEDIA_CONVERTER


class _Signals(QObject):
    log_msg = Signal(str)
    progress = Signal(float)
    status = Signal(str)
    finished = Signal()
    scan_done = Signal(list, str)  # items (path, size, kind), src_dir


class MediaConverterPanel(QWidget):
    def __init__(self, log_callback=None, status_callback=None, parent=None):
        super().__init__(parent)
        self._log_cb = log_callback
        self._status_cb = status_callback
        self._sig = _Signals()
        self._sig.log_msg.connect(self._add_log)
        self._sig.progress.connect(self._on_progress)
        self._sig.status.connect(self._on_status)
        self._sig.finished.connect(self._on_finished)
        self._sig.scan_done.connect(self._on_scan_done)

        self._engine = ConverterEngine(logger_callback=self._add_log)
        self._is_running = False
        self._is_scanning = False
        self._queue = []
        self._scan_stop = threading.Event()
        self._stop_event = threading.Event()

        _shint = "font-size: 7px; color: #444; margin-top: -1px;"
        _strip_h = 100

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 2, 6, 2)
        root.setSpacing(2)

        # ── COMMAND STRIP ─────────────────────────────────────────────────────
        h_strip = QHBoxLayout()
        h_strip.setSpacing(6)

        # 1. Directories
        grp_dir = QGroupBox("Directories")
        grp_dir.setFixedHeight(_strip_h)
        v_dir = QVBoxLayout(grp_dir)
        v_dir.setContentsMargins(6, 2, 6, 2)
        v_dir.setSpacing(0)
        h_src = QHBoxLayout()
        h_src.setSpacing(4)
        self._edit_src = QLineEdit()
        self._edit_src.setPlaceholderText("SOURCE — folder with media...")
        self._edit_src.setStyleSheet(
            "color:#fff; font-size:11px; font-weight:500; min-height:22px; "
            "background:#121212; border:1px solid #1a1a1a;")
        self._edit_src.textChanged.connect(self._update_start_enabled)
        h_src.addWidget(self._edit_src, 1)
        self._btn_browse_src = QPushButton("Browse")
        self._btn_browse_src.setFixedWidth(48)
        self._btn_browse_src.setStyleSheet("font-size:8px; font-weight:700; color:#aaa; border:2px solid transparent;")
        self._btn_browse_src.clicked.connect(self._browse_src)
        h_src.addWidget(self._btn_browse_src)
        v_dir.addLayout(h_src)
        v_dir.addWidget(QLabel("Photos and/or videos to convert", styleSheet=_shint))
        h_tgt = QHBoxLayout()
        h_tgt.setSpacing(4)
        self._edit_tgt = QLineEdit()
        self._edit_tgt.setPlaceholderText("TARGET — output folder...")
        self._edit_tgt.setStyleSheet(
            "color:#fff; font-size:11px; font-weight:500; min-height:22px; "
            "background:#121212; border:1px solid #1a1a1a;")
        self._edit_tgt.textChanged.connect(self._update_start_enabled)
        h_tgt.addWidget(self._edit_tgt, 1)
        self._btn_browse_tgt = QPushButton("Browse")
        self._btn_browse_tgt.setFixedWidth(48)
        self._btn_browse_tgt.setStyleSheet("font-size:8px; font-weight:700; color:#aaa; border:2px solid transparent;")
        self._btn_browse_tgt.clicked.connect(self._browse_tgt)
        h_tgt.addWidget(self._btn_browse_tgt)
        v_dir.addLayout(h_tgt)
        v_dir.addWidget(QLabel("Output destination (mirrors subdirs)", styleSheet=_shint))
        h_strip.addWidget(grp_dir, 6)

        # 2. Format & Options
        grp_fmt = QGroupBox("Format & Options")
        grp_fmt.setFixedHeight(_strip_h)
        v_fmt = QVBoxLayout(grp_fmt)
        v_fmt.setContentsMargins(6, 2, 6, 2)
        v_fmt.setSpacing(2)
        h_fmt = QHBoxLayout()
        h_fmt.addWidget(QLabel("Output:", styleSheet="font-size:7px; color:#888;"))
        self._combo_format = QComboBox()
        self._combo_format.setStyleSheet("font-size:8px; min-height:18px;")
        self._combo_format.addItems(["jpg", "png", "webp", "bmp", "tiff", "mp4", "webm", "mkv", "avi"])
        h_fmt.addWidget(self._combo_format, 1)
        v_fmt.addLayout(h_fmt)
        self._chk_photos = QCheckBox("Photos")
        self._chk_photos.setChecked(True)
        self._chk_photos.setStyleSheet("font-size:8px; font-weight:700; color:#aaa;")
        self._chk_videos = QCheckBox("Videos")
        self._chk_videos.setChecked(True)
        self._chk_videos.setStyleSheet("font-size:8px; font-weight:700; color:#aaa;")
        self._chk_recursive = QCheckBox("Recursive")
        self._chk_recursive.setChecked(True)
        self._chk_recursive.setStyleSheet("font-size:8px; font-weight:700; color:#aaa;")
        self._chk_transparency = QCheckBox("Transparency (PNG/WebP)")
        self._chk_transparency.setStyleSheet("font-size:8px; font-weight:700; color:#aaa;")
        self._chk_transparency.setToolTip("Preserve/add alpha channel for images")
        for w in [self._chk_photos, self._chk_videos, self._chk_recursive, self._chk_transparency]:
            v_fmt.addWidget(w)
        h_strip.addWidget(grp_fmt, 3)

        # 3. Transform
        grp_tr = QGroupBox("Transform")
        grp_tr.setFixedHeight(_strip_h)
        v_tr = QVBoxLayout(grp_tr)
        v_tr.setContentsMargins(6, 2, 6, 2)
        v_tr.setSpacing(2)
        g_crop = QGridLayout()
        g_crop.addWidget(QLabel("Crop:", styleSheet="font-size:7px; color:#888;"), 0, 0)
        self._spin_cx = QSpinBox(); self._spin_cx.setRange(0, 99999); self._spin_cx.setPrefix("x:")
        self._spin_cy = QSpinBox(); self._spin_cy.setRange(0, 99999); self._spin_cy.setPrefix("y:")
        self._spin_cw = QSpinBox(); self._spin_cw.setRange(0, 99999); self._spin_cw.setPrefix("w:")
        self._spin_ch = QSpinBox(); self._spin_ch.setRange(0, 99999); self._spin_ch.setPrefix("h:")
        for s in [self._spin_cx, self._spin_cy, self._spin_cw, self._spin_ch]:
            s.setStyleSheet("font-size:8px;"); s.setFixedWidth(58)
        g_crop.addWidget(self._spin_cx, 0, 1); g_crop.addWidget(self._spin_cy, 0, 2)
        g_crop.addWidget(self._spin_cw, 0, 3); g_crop.addWidget(self._spin_ch, 0, 4)
        v_tr.addLayout(g_crop)
        h_scale = QHBoxLayout()
        h_scale.addWidget(QLabel("Scale:", styleSheet="font-size:7px; color:#888;"))
        self._spin_sw = QSpinBox(); self._spin_sw.setRange(0, 99999); self._spin_sw.setSpecialValueText("—")
        self._spin_sh = QSpinBox(); self._spin_sh.setRange(0, 99999); self._spin_sh.setSpecialValueText("—")
        self._spin_pct = QSpinBox(); self._spin_pct.setRange(0, 400); self._spin_pct.setSuffix("%")
        self._spin_pct.setSpecialValueText("—")
        for s in [self._spin_sw, self._spin_sh, self._spin_pct]:
            s.setStyleSheet("font-size:8px;"); s.setFixedWidth(55)
        h_scale.addWidget(self._spin_sw); h_scale.addWidget(QLabel("×")); h_scale.addWidget(self._spin_sh)
        h_scale.addWidget(QLabel(" or ")); h_scale.addWidget(self._spin_pct)
        v_tr.addLayout(h_scale)
        h_rot = QHBoxLayout()
        h_rot.addWidget(QLabel("Rotate:", styleSheet="font-size:7px; color:#888;"))
        self._combo_rotate = QComboBox()
        self._combo_rotate.setStyleSheet("font-size:8px; min-height:18px;")
        self._combo_rotate.addItems(["0°", "90° CW", "180°", "270° CW"])
        h_rot.addWidget(self._combo_rotate)
        h_rot.addWidget(QLabel("Quality:", styleSheet="font-size:7px; color:#888;"))
        self._spin_quality = QSpinBox(); self._spin_quality.setRange(1, 100); self._spin_quality.setValue(95)
        self._spin_quality.setStyleSheet("font-size:8px;"); self._spin_quality.setFixedWidth(45)
        h_rot.addWidget(self._spin_quality)
        v_tr.addLayout(h_rot)
        h_strip.addWidget(grp_tr, 4)

        root.addLayout(h_strip)

        # ── PROGRESS & CONTROL ─────────────────────────────────────────────────
        grp_exec = QGroupBox("Conversion Progress")
        h_exec = QHBoxLayout(grp_exec)
        h_exec.setContentsMargins(6, 2, 6, 2)
        h_exec.setSpacing(8)
        self._bar = QProgressBar()
        self._bar.setObjectName("masterBar")
        self._bar.setFixedHeight(18)
        self._bar.setFormat("Ready")
        h_exec.addWidget(self._bar, 1)
        self._lbl_status = QLabel("Ready")
        self._lbl_status.setStyleSheet("color:#10b981; font-size:8px; font-weight:700; min-width:90px;")
        h_exec.addWidget(self._lbl_status)
        self._btn_scan = QPushButton("SCAN")
        self._btn_scan.setStyleSheet("font-size:8px; font-weight:700; min-height:20px;")
        self._btn_scan.clicked.connect(self._scan)
        h_exec.addWidget(self._btn_scan)
        self._btn_start = QPushButton("START CONVERSION")
        self._btn_start.setObjectName("btnStart")
        self._btn_start.setFixedHeight(28)
        self._btn_start.setEnabled(False)
        self._btn_start.clicked.connect(self._run_job)
        h_exec.addWidget(self._btn_start)
        self._btn_stop = QPushButton("STOP")
        self._btn_stop.setObjectName("btnStop")
        self._btn_stop.setFixedHeight(28)
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._stop_job)
        h_exec.addWidget(self._btn_stop)
        root.addWidget(grp_exec)

        # ── CONSOLE ───────────────────────────────────────────────────────────
        grp_log = QGroupBox("Console")
        v_log = QVBoxLayout(grp_log)
        v_log.setContentsMargins(6, 4, 6, 4)
        v_log.setSpacing(0)
        self._log_list = QListWidget()
        v_log.addWidget(self._log_list)
        root.addWidget(grp_log, 1)

        # Guide
        self._guide_pulse_timer = QTimer(self)
        self._guide_pulse_timer.setInterval(550)
        self._guide_pulse_timer.timeout.connect(self._pulse_guide)
        self._guide_glow_phase = 0
        self._guide_target = None
        self._update_start_enabled()

    def get_activity(self) -> str:
        return "converting" if self._is_running else "idle"

    def _add_log(self, msg: str):
        self._log_list.addItem(msg)
        self._log_list.scrollToBottom()
        if self._log_cb:
            self._log_cb(msg)

    def _browse_src(self):
        f = QFileDialog.getExistingDirectory(self, "Select Source Folder")
        if f:
            self._edit_src.setText(f)

    def _browse_tgt(self):
        f = QFileDialog.getExistingDirectory(self, "Select Target Folder")
        if f:
            self._edit_tgt.setText(f)

    def _can_start(self) -> bool:
        src = self._edit_src.text().strip()
        tgt = self._edit_tgt.text().strip()
        if not src or not os.path.isdir(src):
            return False
        if not tgt or not os.path.isdir(tgt):
            return False
        if not self._chk_photos.isChecked() and not self._chk_videos.isChecked():
            return False
        return len(self._queue) > 0

    def _update_start_enabled(self):
        can = not self._is_running and self._can_start()
        self._btn_start.setEnabled(can)
        self._guide_pulse_timer.start()

    def _get_guide_target(self):
        if self._is_running or self._is_scanning:
            return None
        src = self._edit_src.text().strip()
        if not src or not os.path.isdir(src):
            return self._btn_browse_src
        tgt = self._edit_tgt.text().strip()
        if not tgt or not os.path.isdir(tgt):
            return self._btn_browse_tgt
        if not self._chk_photos.isChecked() and not self._chk_videos.isChecked():
            return self._chk_photos
        if len(self._queue) == 0:
            return self._btn_scan
        return self._btn_start

    def _pulse_guide(self):
        target = self._get_guide_target()
        if target != self._guide_target:
            self._clear_guide_glow(self._guide_target)
            self._guide_target = target
        if not target:
            self._guide_pulse_timer.stop()
            self._clear_guide_glow(self._guide_target)
            self._guide_target = None
            return
        self._guide_glow_phase = 1 - self._guide_glow_phase
        if self._guide_glow_phase:
            if target == self._btn_start:
                target.setStyleSheet("background-color:#10b981; color:#064e3b; border:2px solid #ef4444; font-size:10px; font-weight:900;")
            else:
                target.setStyleSheet("font-size:8px; font-weight:700; color:#ef4444; border:2px solid #ef4444;")
        else:
            self._clear_guide_glow(target)

    def _clear_guide_glow(self, w):
        if not w:
            return
        if w == self._btn_start:
            w.setStyleSheet("background-color:#10b981; color:#064e3b; border:2px solid transparent; font-size:10px; font-weight:900;")
        elif w in (self._btn_browse_src, self._btn_browse_tgt, self._btn_scan):
            w.setStyleSheet("font-size:8px; font-weight:700; color:#aaa; border:2px solid transparent;")

    def _scan(self):
        src = self._edit_src.text().strip()
        if not src or not os.path.isdir(src):
            self._add_log("Select a valid source folder.")
            return
        self._is_scanning = True
        self._scan_stop.clear()
        self._btn_scan.setEnabled(False)
        self._add_log("Scanning...")

        def task():
            items = []
            try:
                for path, size, kind in self._engine.scan_files(
                    src,
                    include_photos=self._chk_photos.isChecked(),
                    include_videos=self._chk_videos.isChecked(),
                    recursive=self._chk_recursive.isChecked(),
                    stop_event=self._scan_stop,
                ):
                    items.append((path, size, kind))
            except Exception as e:
                self._add_log(f"Scan error: {e}")
            self._sig.scan_done.emit(items, src)

        threading.Thread(target=task, daemon=True).start()

    def _on_scan_done(self, items: list, src: str):
        self._is_scanning = False
        self._btn_scan.setEnabled(True)
        self._queue = items
        total = sum(s for _, s, _ in items)
        self._add_log(f"Found {len(items)} files ({total / (1024*1024):.1f} MB).")
        self._update_start_enabled()

    def _build_opts(self) -> ConvertOptions:
        fmt = self._combo_format.currentText().strip().lower()
        return ConvertOptions(
            out_format=fmt,
            crop_x=self._spin_cx.value(),
            crop_y=self._spin_cy.value(),
            crop_w=self._spin_cw.value(),
            crop_h=self._spin_ch.value(),
            scale_w=self._spin_sw.value() or 0,
            scale_h=self._spin_sh.value() or 0,
            scale_pct=self._spin_pct.value() or 0,
            rotate=[0, 90, 180, 270][self._combo_rotate.currentIndex()],
            transparency=self._chk_transparency.isChecked(),
            quality=self._spin_quality.value(),
        )

    def _run_job(self):
        src_dir = self._edit_src.text().strip()
        tgt_dir = self._edit_tgt.text().strip()
        if not src_dir or not os.path.isdir(src_dir) or not tgt_dir or not os.path.isdir(tgt_dir):
            return
        if not self._queue:
            self._add_log("Scan first to build queue.")
            return
        self._is_running = True
        self._stop_event.clear()
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)
        if self._status_cb:
            self._status_cb("converting")

        def task():
            opts = self._build_opts()
            total = len(self._queue)
            done = 0
            ok_count = 0
            for path, size, kind in self._queue:
                if self._stop_event.is_set():
                    break
                rel = os.path.relpath(path, src_dir)
                stem = pathlib.Path(path).stem
                ext = f".{opts.out_format.lstrip('.')}"
                dst = os.path.join(tgt_dir, pathlib.Path(rel).parent, stem + ext)
                try:
                    success = self._engine.convert_file(path, dst, opts)
                    if success:
                        ok_count += 1
                        self._add_log(f"[OK] {os.path.basename(path)} → {stem}{ext}")
                    else:
                        self._add_log(f"[FAIL] {os.path.basename(path)}")
                except Exception as e:
                    self._add_log(f"[FAIL] {os.path.basename(path)}: {e}")
                done += 1
                self._sig.progress.emit(100.0 * done / total if total else 0)
                self._sig.status.emit(f"{done}/{total}")
            self._sig.finished.emit()

        threading.Thread(target=task, daemon=True).start()

    def _stop_job(self):
        self._stop_event.set()
        self._engine.cancel()

    def _on_progress(self, pct: float):
        self._bar.setValue(int(pct))
        self._bar.setFormat("%p%")

    def _on_status(self, s: str):
        self._lbl_status.setText(s)

    def _on_finished(self):
        self._is_running = False
        self._btn_start.setEnabled(self._can_start())
        self._btn_stop.setEnabled(False)
        self._bar.setValue(100)
        self._bar.setFormat("Done")
        self._lbl_status.setText("Complete")
        if self._status_cb:
            self._status_cb("idle")
