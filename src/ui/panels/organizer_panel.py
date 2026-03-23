"""
organizer_panel.py — Media Organizer panel for ChronoArchiver.
Visual style matches Mass AV1 Encoder v12.
Uses src/core/organizer.py unchanged.
"""

import os
import threading

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QCheckBox, QComboBox,
    QProgressBar, QFileDialog, QListWidget, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from core.organizer import OrganizerEngine
from core.debug_logger import debug, UTILITY_MEDIA_ORGANIZER


class _Signals(QObject):
    log_msg  = Signal(str)
    progress = Signal(float)
    status   = Signal(str)
    finished = Signal()
    stats    = Signal(int, int, int)  # moved, skipped, duplicates


class MediaOrganizerPanel(QWidget):

    def __init__(self, log_callback=None, status_callback=None, parent=None):
        super().__init__(parent)
        self._log_cb = log_callback
        self._status_cb = status_callback
        self._sig    = _Signals()
        self._sig.log_msg.connect(self._add_log)
        self._sig.progress.connect(self._on_progress)
        self._sig.status.connect(self._on_status)
        self._sig.finished.connect(self._on_finished)
        self._sig.stats.connect(self._on_stats)

        self._engine = None  # Initialized in _run_job
        self._is_running = False
        self._last_stats = (0, 0, 0)

        _shint = "font-size: 7px; color: #444; margin-top: -1px;"

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 2, 6, 2)
        root.setSpacing(2)

        # ── COMMAND STRIP ─────────────────────────────────────────────────────
        h_strip = QHBoxLayout()
        h_strip.setSpacing(6)
        _box_height = 118  # Equal height for all three boxes

        # 1. Directories
        grp_dir = QGroupBox("Directories")
        grp_dir.setFixedHeight(_box_height)
        v_dir = QVBoxLayout(grp_dir)
        v_dir.setContentsMargins(6, 2, 6, 2)
        v_dir.setSpacing(1)
        self._edit_path = QLineEdit()
        self._edit_path.setPlaceholderText("SOURCE — folder containing media...")
        self._edit_path.setStyleSheet(
            "color:#fff; font-size:11px; font-weight:500; min-height:22px; "
            "background:#121212; border:1px solid #1a1a1a;")
        h_src = QHBoxLayout()
        h_src.setSpacing(4)
        h_src.addWidget(self._edit_path, 1)
        self._btn_browse_src = QPushButton("Browse")
        self._btn_browse_src.setFixedSize(48, 22)
        self._btn_browse_src.setStyleSheet("font-size:8px; font-weight:700; color:#aaa; border:2px solid transparent;")
        self._btn_browse_src.clicked.connect(self._browse)
        h_src.addWidget(self._btn_browse_src)
        v_dir.addLayout(h_src)
        v_dir.addWidget(QLabel("Source (EXIF/metadata/ffprobe)", styleSheet=_shint))
        self._edit_target = QLineEdit()
        self._edit_target.setPlaceholderText("TARGET (optional)")
        self._edit_target.setStyleSheet(
            "color:#fff; font-size:11px; font-weight:500; min-height:22px; "
            "background:#121212; border:1px solid #1a1a1a;")
        h_tgt = QHBoxLayout()
        h_tgt.setSpacing(4)
        h_tgt.addWidget(self._edit_target, 1)
        self._btn_browse_target = QPushButton("Browse")
        self._btn_browse_target.setFixedSize(48, 22)
        self._btn_browse_target.setStyleSheet("font-size:8px; font-weight:700; color:#aaa; border:2px solid transparent;")
        self._btn_browse_target.clicked.connect(self._browse_target)
        h_tgt.addWidget(self._btn_browse_target)
        v_dir.addLayout(h_tgt)
        v_dir.addWidget(QLabel("Blank = in-place", styleSheet=_shint))
        h_strip.addWidget(grp_dir, 11)

        # 2. Options
        grp_opts = QGroupBox("Options")
        grp_opts.setFixedHeight(_box_height)
        v_opts = QVBoxLayout(grp_opts)
        v_opts.setContentsMargins(6, 2, 6, 2)
        v_opts.setSpacing(1)
        h_row = QHBoxLayout()
        self._chk_photos = QCheckBox("Photos")
        self._chk_photos.setChecked(True)
        self._chk_videos = QCheckBox("Videos")
        self._chk_videos.setChecked(True)
        self._chk_sidecars = QCheckBox("Sidecars")
        self._chk_sidecars.setToolTip("Move .xmp, .aae, .xml, .json with main files")
        for cb in [self._chk_photos, self._chk_videos, self._chk_sidecars]:
            cb.setStyleSheet("font-size:8px; font-weight:700; color:#aaa; border:2px solid transparent;")
            h_row.addWidget(cb)
        v_opts.addLayout(h_row)
        self._edit_exts = QLineEdit()
        self._edit_exts.setPlaceholderText("Extensions (.jpg,.mp4)")
        self._edit_exts.setStyleSheet("font-size:8px; color:#888; background:#121212; border:1px solid #1a1a1a; padding:2px; min-height:20px;")
        v_opts.addWidget(self._edit_exts)
        self._edit_exclude = QLineEdit()
        self._edit_exclude.setPlaceholderText("Exclude dirs: .trash, @Recently Deleted")
        self._edit_exclude.setToolTip("Comma-separated folder names to skip (always skips .trash, @Recently Deleted)")
        self._edit_exclude.setStyleSheet("font-size:7px; color:#666; background:#121212; border:1px solid #1a1a1a; padding:2px; min-height:18px;")
        v_opts.addWidget(self._edit_exclude)
        v_opts.addStretch()
        h_strip.addWidget(grp_opts, 3)

        # 3. Execution Mode
        grp_mode = QGroupBox("Execution Mode")
        grp_mode.setFixedHeight(_box_height)
        v_mode = QVBoxLayout(grp_mode)
        v_mode.setContentsMargins(6, 2, 6, 2)
        v_mode.setSpacing(2)
        self._chk_dry = QCheckBox("Dry Run (Simulation)")
        self._chk_dry.setChecked(True)
        self._chk_dry.setStyleSheet("font-size:8px; font-weight:700; color:#aaa;")
        v_mode.addWidget(self._chk_dry)
        lbl_struct = QLabel("Folder structure:")
        lbl_struct.setStyleSheet("font-size:7px; color:#888; margin-top:4px;")
        v_mode.addWidget(lbl_struct)
        self._combo_structure = QComboBox()
        self._combo_structure.addItems([
            "YYYY/YYYY-MM (nested)",
            "YYYY-MM (flat month)",
            "YYYY-MM-DD (flat day)",
            "YYYY/YYYY-MM/YYYY-MM-DD (nested day)",
        ])
        self._combo_structure.setStyleSheet("font-size:8px; min-height:20px;")
        v_mode.addWidget(self._combo_structure)
        h_mode = QHBoxLayout()
        self._combo_action = QComboBox()
        self._combo_action.addItems(["Move", "Copy", "Symlink"])
        self._combo_action.setToolTip("Move=relocate; Copy=duplicate; Symlink=create links")
        self._combo_action.setStyleSheet("font-size:7px; min-height:18px;")
        self._combo_dup = QComboBox()
        self._combo_dup.addItems(["Rename", "Skip", "Keep newer", "Overwrite if same"])
        self._combo_dup.setToolTip("Rename=add timestamp; Skip=skip if exists; Keep newer=skip if target newer; Overwrite=skip if identical")
        self._combo_dup.setStyleSheet("font-size:7px; min-height:18px;")
        h_mode.addWidget(QLabel("Action:", styleSheet="font-size:7px; color:#888;"))
        h_mode.addWidget(self._combo_action, 1)
        h_mode.addWidget(QLabel("Dup:", styleSheet="font-size:7px; color:#888;"))
        h_mode.addWidget(self._combo_dup, 1)
        v_mode.addLayout(h_mode)
        v_mode.addStretch()
        h_strip.addWidget(grp_mode, 4)

        root.addLayout(h_strip)

        # ── EXECUTION ─────────────────────────────────────────────────────────
        grp_exec = QGroupBox("Organization Progress")
        v_exec   = QVBoxLayout(grp_exec)
        v_exec.setContentsMargins(8, 4, 8, 8); v_exec.setSpacing(1)

        self._bar = QProgressBar()
        self._bar.setObjectName("masterBar")
        self._bar.setFixedHeight(18)
        self._bar.setTextVisible(True)
        self._bar.setFormat("Ready")
        v_exec.addWidget(self._bar)

        self._lbl_status = QLabel("Ready to organize")
        self._lbl_status.setAlignment(Qt.AlignCenter)
        self._lbl_status.setStyleSheet("color:#10b981; font-size:10px; font-weight:800; margin-top:2px;")
        v_exec.addWidget(self._lbl_status)

        h_ctrl = QHBoxLayout(); h_ctrl.setSpacing(8)
        self._btn_start = QPushButton("START ORGANIZATION")
        self._btn_start.setObjectName("btnStart")
        self._btn_start.setMinimumHeight(40)
        self._btn_start.clicked.connect(self._run_job)
        h_ctrl.addWidget(self._btn_start, 2)

        self._btn_stop = QPushButton("STOP")
        self._btn_stop.setObjectName("btnStop")
        self._btn_stop.setMinimumHeight(40)
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._stop_job)
        h_ctrl.addWidget(self._btn_stop, 1)

        v_exec.addLayout(h_ctrl)

        self._edit_path.textChanged.connect(self._update_start_enabled)
        self._edit_target.textChanged.connect(self._update_start_enabled)
        self._chk_photos.stateChanged.connect(self._update_start_enabled)
        self._chk_videos.stateChanged.connect(self._update_start_enabled)
        self._edit_exts.textChanged.connect(self._update_start_enabled)
        self._guide_pulse_timer = QTimer(self)
        self._guide_pulse_timer.setInterval(550)
        self._guide_pulse_timer.timeout.connect(self._pulse_guide)
        self._guide_glow_phase = 0
        self._guide_target = None
        self._update_start_enabled()
        grp_exec.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        root.addWidget(grp_exec)

        # ── CONSOLE ───────────────────────────────────────────────────────────
        grp_log = QGroupBox("Console")
        v_log = QVBoxLayout(grp_log)
        v_log.setContentsMargins(6, 4, 6, 4); v_log.setSpacing(0)
        h_log = QHBoxLayout()
        h_log.addStretch()
        self._btn_export = QPushButton("Export Log")
        self._btn_export.setToolTip("Save console log to file")
        self._btn_export.setStyleSheet("font-size:7px; min-height:18px;")
        self._btn_export.clicked.connect(self._export_log)
        h_log.addWidget(self._btn_export)
        v_log.addLayout(h_log)
        self._log_list = QListWidget()
        v_log.addWidget(self._log_list)
        root.addWidget(grp_log, 1)  # Stretch: console takes all remaining vertical space

    def _can_start(self):
        path = self._edit_path.text().strip()
        if not path or not os.path.isdir(path):
            return False
        exts_override = self._edit_exts.text().strip()
        if exts_override:
            exts = set()
            for p in exts_override.replace(" ", "").split(","):
                ext = p.strip().lower()
                if ext and not ext.startswith("."):
                    ext = "." + ext
                if ext:
                    exts.add(ext)
        else:
            exts = set()
            if self._chk_photos.isChecked():
                exts.update({'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'})
            if self._chk_videos.isChecked():
                exts.update({'.mp4', '.mov', '.avi', '.webm', '.mkv', '.m4v', '.wmv'})
        if not exts:
            return False
        target = self._edit_target.text().strip()
        if target and not os.path.isdir(target):
            return False
        return True

    def _get_guide_target(self):
        """Returns the button/widget that needs user attention next (step by step)."""
        if self._is_running:
            return None
        path = self._edit_path.text().strip()
        if not path or not os.path.isdir(path):
            return self._btn_browse_src
        exts_override = self._edit_exts.text().strip()
        if exts_override:
            exts = set()
            for p in exts_override.replace(" ", "").split(","):
                ext = p.strip().lower()
                if ext and not ext.startswith("."):
                    ext = "." + ext
                if ext:
                    exts.add(ext)
        else:
            exts = set()
            if self._chk_photos.isChecked():
                exts.update({'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'})
            if self._chk_videos.isChecked():
                exts.update({'.mp4', '.mov', '.avi', '.webm', '.mkv', '.m4v', '.wmv'})
        if not exts:
            return self._chk_photos
        target = self._edit_target.text().strip()
        if target and not os.path.isdir(target):
            return self._btn_browse_target
        return self._btn_start

    def _update_start_enabled(self):
        can = not self._is_running and self._can_start()
        self._btn_start.setEnabled(can)
        self._guide_glow_phase = 0
        self._guide_pulse_timer.start()

    def _clear_guide_glow(self, w):
        if not w:
            return
        if w == self._btn_start:
            w.setStyleSheet("background-color:#10b981; color:#064e3b; border:2px solid transparent; font-size:10px; font-weight:900;")
        elif w == self._btn_browse_src or w == self._btn_browse_target:
            w.setStyleSheet("font-size:8px; font-weight:700; color:#aaa; border:2px solid transparent; min-height:22px;")
        elif w == self._chk_photos:
            w.setStyleSheet("font-size:8px; font-weight:700; color:#aaa; border:2px solid transparent;")

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
            elif target == self._btn_browse_src or target == self._btn_browse_target:
                target.setStyleSheet("font-size:8px; font-weight:700; color:#ef4444; border:2px solid #ef4444; min-height:22px;")
            else:
                target.setStyleSheet("font-size:8px; font-weight:700; color:#ef4444; border:2px solid #ef4444;")
        else:
            self._clear_guide_glow(target)

    def _browse(self):
        f = QFileDialog.getExistingDirectory(self, "Select Source Folder")
        if f:
            self._edit_path.setText(f)

    def _browse_target(self):
        f = QFileDialog.getExistingDirectory(self, "Select Target Folder (optional)")
        if f:
            self._edit_target.setText(f)

    def _export_log(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Log", "", "Text (*.txt);;All (*)")
        if path:
            try:
                lines = [self._log_list.item(i).text() for i in range(self._log_list.count())]
                with open(path, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
                self._add_log(f"Log exported to {path}")
            except OSError as e:
                self._add_log(f"Export failed: {e}")

    def _run_job(self):
        path = self._edit_path.text().strip()
        if not path or not os.path.isdir(path):
            self._add_log("ERROR: Invalid source directory.")
            debug(UTILITY_MEDIA_ORGANIZER, f"ERROR: Invalid source directory: {path or '(empty)'}")
            return

        exts_override = self._edit_exts.text().strip()
        if exts_override:
            exts = set()
            for p in exts_override.replace(" ", "").split(","):
                ext = p.strip().lower()
                if ext and not ext.startswith("."):
                    ext = "." + ext
                if ext:
                    exts.add(ext)
        else:
            exts = set()
            if self._chk_photos.isChecked():
                exts.update({'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'})
            if self._chk_videos.isChecked():
                exts.update({'.mp4', '.mov', '.avi', '.webm', '.mkv', '.m4v', '.wmv'})
        if not exts:
            self._add_log("ERROR: Select at least one media type or specify extensions.")
            debug(UTILITY_MEDIA_ORGANIZER, "ERROR: No media types selected")
            return

        target = self._edit_target.text().strip() or None
        if target and not os.path.isdir(target):
            self._add_log("ERROR: Target directory does not exist.")
            debug(UTILITY_MEDIA_ORGANIZER, f"ERROR: Target directory does not exist: {target}")
            return

        structure_keys = ("nested", "flat_month", "flat_day", "nested_day")
        folder_structure = structure_keys[self._combo_structure.currentIndex()]
        action_keys = ("move", "copy", "symlink")
        action = action_keys[self._combo_action.currentIndex()]
        dup_keys = ("rename", "skip", "keep_newer", "overwrite")
        duplicate_policy = dup_keys[self._combo_dup.currentIndex()]
        exclude_text = self._edit_exclude.text().strip()
        exclude_dirs = {p.strip() for p in exclude_text.split(",") if p.strip()} if exclude_text else None
        debug(UTILITY_MEDIA_ORGANIZER, f"Organization start: path={path}, action={action}, structure={folder_structure}, target={target or 'in-place'}")
        self._is_running = True
        if self._status_cb:
            self._status_cb("organizing")
        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)

        def _log(msg):
            self._sig.log_msg.emit(msg)

        self._engine = OrganizerEngine(logger_callback=_log)

        def _prog(bytes_done, total_bytes, files_done, total_files, filename):
            pct = (bytes_done / total_bytes) if total_bytes > 0 else 0.0
            self._sig.progress.emit(pct)
            self._sig.status.emit(f"{files_done}/{total_files}  {filename}")

        def _stats(moved, skipped, duplicates):
            self._sig.stats.emit(moved, skipped, duplicates)

        def _run():
            try:
                self._engine.organize(path,
                    dry_run=self._chk_dry.isChecked(),
                    folder_structure=folder_structure,
                    valid_exts=exts,
                    target_dir=target,
                    action=action,
                    move_sidecars=self._chk_sidecars.isChecked(),
                    exclude_dirs=exclude_dirs,
                    duplicate_policy=duplicate_policy,
                    progress_callback=_prog,
                    stats_callback=_stats)
            except Exception as e:
                self._sig.log_msg.emit(f"ERROR: {e}")
                debug(UTILITY_MEDIA_ORGANIZER, f"Organizer thread exception: {e}")
            finally:
                self._sig.finished.emit()

        threading.Thread(target=_run, daemon=True).start()

    def _stop_job(self):
        if self._engine:
            self._engine.cancel()
            debug(UTILITY_MEDIA_ORGANIZER, "Organization stopped by user")
        self._update_start_enabled()
        self._btn_stop.setEnabled(False)

    def _on_progress(self, val):
        self._bar.setValue(int(val * 100))

    def _on_status(self, msg):
        self._lbl_status.setText(msg)

    def _on_stats(self, moved, skipped, duplicates):
        self._last_stats = (moved, skipped, duplicates)

    def get_activity(self):
        return "organizing" if self._is_running else "idle"

    def _on_finished(self):
        self._is_running = False
        if self._status_cb:
            self._status_cb("idle")
        self._update_start_enabled()
        self._btn_stop.setEnabled(False)
        self._bar.setFormat("Complete")
        stats = getattr(self, "_last_stats", (0, 0, 0))
        moved, skipped, duplicates = stats
        self._lbl_status.setText(f"Moved: {moved} | Skipped: {skipped} | Duplicates: {duplicates}")
        self._add_log("Batch organization complete.")
        debug(UTILITY_MEDIA_ORGANIZER, f"Organization complete: moved={moved}, skipped={skipped}, duplicates={duplicates}")

    def _add_log(self, msg):
        sb = self._log_list.verticalScrollBar()
        at_bot = sb.value() >= sb.maximum() - 4
        self._log_list.addItem(msg)
        if at_bot:
            self._log_list.scrollToBottom()
        if self._log_list.count() > 1000:
            self._log_list.takeItem(0)
        if self._log_cb:
            self._log_cb(msg)
