"""
scanner_panel.py — AI Media Scanner panel for ChronoArchiver.
Visual style exactly matches Mass AV1 Encoder v12.
"""

import csv
import os
import shutil
import threading

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QLineEdit, QCheckBox, QListWidget, QListWidgetItem,
    QProgressBar, QFileDialog, QSpinBox,
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from core.scanner import ScannerEngine
from core.model_manager import ModelManager


class _Signals(QObject):
    log_msg  = Signal(str)
    progress = Signal(float)
    finished = Signal()


class AIScannerPanel(QWidget):

    def __init__(self, log_callback=None, parent=None):
        super().__init__(parent)
        self._log_cb = log_callback
        self._sig    = _Signals()
        self._sig.log_msg.connect(self._add_log)
        self._sig.progress.connect(self._on_progress)
        self._sig.finished.connect(self._on_finished)

        _base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        _model_dir = os.path.join(_base, 'core', 'models')
        self._model_mgr = ModelManager(_model_dir)

        self._engine = None  # Initialized in _run_job
        self._is_running = False

        _shint = "font-size: 7px; color: #444; margin-top: -1px;"

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 2, 6, 2)
        root.setSpacing(2)

        # ── COMMAND STRIP ─────────────────────────────────────────────────────
        h_strip = QHBoxLayout()
        h_strip.setSpacing(6)

        # 1. Directories
        grp_dir = QGroupBox("Directories")
        v_dir = QVBoxLayout(grp_dir)
        v_dir.setContentsMargins(8, 2, 8, 2); v_dir.setSpacing(1)

        self._edit_path = QLineEdit()
        self._edit_path.setPlaceholderText("SELECT PHOTO LIBRARY TO SCAN...")
        self._edit_path.setStyleSheet(
            "color:#fff; font-size:12px; font-weight:500; "
            "background:#121212; border:1px solid #1a1a1a;")

        h_src = QHBoxLayout(); h_src.setSpacing(4)
        h_src.addWidget(self._edit_path, 1)
        btn_br = QPushButton("Browse"); btn_br.setFixedWidth(52)
        btn_br.setStyleSheet("font-size:8px; font-weight:700; color:#aaa;")
        btn_br.clicked.connect(self._browse)
        h_src.addWidget(btn_br)

        v_dir.addLayout(h_src)
        v_dir.addWidget(QLabel("Folder containing photos for AI object detection (YuNet/SSD)",
                               styleSheet=_shint))
        h_strip.addWidget(grp_dir, 11)

        # 2. Options
        grp_opts = QGroupBox("Options")
        v_opts = QVBoxLayout(grp_opts)
        v_opts.setContentsMargins(8, 4, 8, 4); v_opts.setSpacing(4)

        self._chk_recursive = QCheckBox("Recursive"); self._chk_recursive.setChecked(True)
        self._chk_recursive.setStyleSheet("font-size:8px; font-weight:700; color:#aaa; spacing:4px;")
        v_opts.addWidget(self._chk_recursive)

        self._chk_animals = QCheckBox("Keep Animals")
        self._chk_animals.setStyleSheet("font-size:8px; font-weight:700; color:#aaa; spacing:4px;")
        self._chk_animals.setToolTip("Also keep photos with detected animals (cats, dogs, etc.)")
        v_opts.addWidget(self._chk_animals)

        h_thr = QHBoxLayout(); h_thr.setSpacing(4)
        lbl_thr = QLabel("Animal conf:"); lbl_thr.setStyleSheet("font-size:8px; color:#888;")
        self._spin_thresh = QSpinBox(); self._spin_thresh.setRange(10, 90); self._spin_thresh.setValue(40)
        self._spin_thresh.setSuffix("%"); self._spin_thresh.setStyleSheet("font-size:8px;")
        self._spin_thresh.setToolTip("Detection confidence threshold (higher = stricter)")
        h_thr.addWidget(lbl_thr); h_thr.addWidget(self._spin_thresh, 1)
        v_opts.addLayout(h_thr)

        v_opts.addStretch(1)
        h_strip.addWidget(grp_opts, 3)

        # 3. Model
        grp_mod = QGroupBox("Engine Status")
        v_mod = QVBoxLayout(grp_mod)
        v_mod.setContentsMargins(8, 4, 8, 4); v_mod.setSpacing(4)

        self._lbl_model = QLabel("Checking models...")
        self._lbl_model.setStyleSheet("font-size:8px; font-weight:700; color:#10b981;")
        v_mod.addWidget(self._lbl_model)
        
        self._btn_setup = QPushButton("Setup Models")
        self._btn_setup.setStyleSheet("font-size:8px; font-weight:700; color:#aaa;")
        self._btn_setup.clicked.connect(self._setup_models)
        v_mod.addWidget(self._btn_setup)

        v_mod.addStretch(1)
        h_strip.addWidget(grp_mod, 4)

        root.addLayout(h_strip)

        # ── EXECUTION ─────────────────────────────────────────────────────────
        grp_exec = QGroupBox("Scanning Progress")
        v_exec   = QVBoxLayout(grp_exec)
        v_exec.setContentsMargins(8, 4, 8, 8); v_exec.setSpacing(1)

        self._bar = QProgressBar()
        self._bar.setObjectName("masterBar")
        self._bar.setFixedHeight(18)
        self._bar.setTextVisible(True)
        self._bar.setFormat("Ready")
        v_exec.addWidget(self._bar)

        self._lbl_status = QLabel("Ready to start scan")
        self._lbl_status.setAlignment(Qt.AlignCenter)
        self._lbl_status.setStyleSheet("color:#10b981; font-size:10px; font-weight:800; margin-top:2px;")
        v_exec.addWidget(self._lbl_status)

        h_ctrl = QHBoxLayout(); h_ctrl.setSpacing(8)
        self._btn_start = QPushButton("START AI SCAN")
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
        root.addWidget(grp_exec)

        # ── RESULTS (Keep | Move) ───────────────────────────────────────────
        grp_res = QGroupBox("Results")
        v_res = QVBoxLayout(grp_res)
        v_res.setContentsMargins(8, 2, 8, 2)
        h_lists = QHBoxLayout(); h_lists.setSpacing(8)
        v_k = QVBoxLayout(); v_k.addWidget(QLabel("Keep (subjects)")); self._list_keep = QListWidget(); self._list_keep.setMinimumWidth(180); v_k.addWidget(self._list_keep)
        v_m = QVBoxLayout(); v_m.addWidget(QLabel("Move (others)")); self._list_move = QListWidget(); self._list_move.setMinimumWidth(180); v_m.addWidget(self._list_move)
        w_k = QWidget(); w_k.setLayout(v_k); h_lists.addWidget(w_k, 1)
        w_m = QWidget(); w_m.setLayout(v_m); h_lists.addWidget(w_m, 1)
        v_res.addLayout(h_lists)
        h_res_btns = QHBoxLayout(); h_res_btns.setSpacing(8)
        self._btn_move_files = QPushButton("Move Files")
        self._btn_move_files.setStyleSheet("font-size:8px; font-weight:700;")
        self._btn_move_files.clicked.connect(self._move_others)
        self._btn_export = QPushButton("Export CSV")
        self._btn_export.setStyleSheet("font-size:8px; font-weight:700;")
        self._btn_export.clicked.connect(self._export_csv)
        h_res_btns.addWidget(self._btn_move_files); h_res_btns.addWidget(self._btn_export)
        h_res_btns.addStretch()
        v_res.addLayout(h_res_btns)
        grp_res.setMaximumHeight(200)
        root.addWidget(grp_res)

        # ── CONSOLE ───────────────────────────────────────────────────────────
        grp_log = QGroupBox("Console")
        grp_log.setFixedHeight(180)
        v_log = QVBoxLayout(grp_log)
        v_log.setContentsMargins(6, 4, 6, 4); v_log.setSpacing(0)
        self._log_list = QListWidget()
        v_log.addWidget(self._log_list)
        root.addWidget(grp_log)

        # Check models on init
        QTimer.singleShot(500, self._check_models)

    def _check_models(self):
        if self._model_mgr.is_up_to_date():
            self._lbl_model.setText("Models Ready")
            self._lbl_model.setStyleSheet("font-size:8px; font-weight:700; color:#10b981;")
            self._btn_setup.hide()
        else:
            self._lbl_model.setText("ResNet Needs Setup")
            self._lbl_model.setStyleSheet("font-size:8px; font-weight:700; color:#ef4444;")
            self._btn_setup.show()

    def _setup_models(self):
        self._add_log("Starting model setup...")
        def _progress(downloaded, total_size, filename):
            if total_size > 0:
                pct = int(downloaded / total_size * 100)
                self._sig.log_msg.emit(f"Downloading: {filename} ({pct}%)")
            else:
                self._sig.log_msg.emit(f"Downloading: {filename}...")
        def _task():
            self._model_mgr.download_models(_progress)
            QTimer.singleShot(0, self._check_models)
        threading.Thread(target=_task, daemon=True).start()

    def _browse(self):
        f = QFileDialog.getExistingDirectory(self, "Select Library to Scan")
        if f:
            self._edit_path.setText(f)

    def _run_job(self):
        path = self._edit_path.text().strip()
        if not path or not os.path.isdir(path):
            self._add_log("ERROR: Invalid directory."); return

        self._btn_start.setEnabled(False)
        self._btn_stop.setEnabled(True)

        def _log(msg): self._sig.log_msg.emit(msg)
        self._engine = ScannerEngine(logger_callback=_log)
        # progress_callback is an attribute, not a constructor arg
        self._engine.progress_callback = lambda c, t, eta, f: self._sig.progress.emit(c / max(t,1))

        def _run():
            self._engine.run_scan(path,
                include_subfolders=self._chk_recursive.isChecked(),
                keep_animals=self._chk_animals.isChecked(),
                animal_threshold=self._spin_thresh.value() / 100.0)
            self._sig.finished.emit()

        threading.Thread(target=_run, daemon=True).start()

    def _stop_job(self):
        if self._engine: self._engine.cancel() 
        self._is_running = False
        self._btn_stop.setEnabled(False)

    def _on_progress(self, val):
        self._bar.setValue(int(val * 100))

    def _on_finished(self):
        self._is_running = False
        self._btn_start.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._bar.setFormat("Complete")
        self._lbl_status.setText("Scan Complete")
        self._add_log("Batch scan complete.")
        self._populate_results()

    def _populate_results(self):
        self._list_keep.clear()
        self._list_move.clear()
        if not self._engine:
            return
        for p in self._engine.keep_list:
            self._list_keep.addItem(os.path.basename(p))
        for p in self._engine.others_list:
            it = QListWidgetItem(os.path.basename(p))
            it.setData(Qt.UserRole, p)
            self._list_move.addItem(it)

    def _move_others(self):
        if not self._engine or not self._engine.others_list:
            self._add_log("No files to move. Run a scan first.")
            return
        base = self._edit_path.text().strip()
        if not base or not os.path.isdir(base):
            self._add_log("ERROR: Invalid source path.")
            return
        dest_dir = os.path.join(base, "Archived_Others")
        os.makedirs(dest_dir, exist_ok=True)
        moved = 0
        for p in self._engine.others_list:
            if os.path.isfile(p):
                try:
                    shutil.move(p, os.path.join(dest_dir, os.path.basename(p)))
                    moved += 1
                except Exception as e:
                    self._add_log(f"Move failed: {p} — {e}")
        self._add_log(f"Moved {moved} files to {dest_dir}.")
        self._list_move.clear()
        self._engine.others_list.clear()

    def _export_csv(self):
        if not self._engine:
            self._add_log("Run a scan first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "", "CSV (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Category", "Path"])
                for p in self._engine.keep_list:
                    w.writerow(["Keep", p])
                for p in self._engine.others_list:
                    w.writerow(["Move", p])
            self._add_log(f"Exported to {path}.")
        except Exception as e:
            self._add_log(f"Export failed: {e}")

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
