""""
Mass AI Encoder tab — layout closely mirrors the original Mass AV1 Encoder v12.
Key constraint: the top strip MUST stay <= 200 px so thread slots and the
progress/button bar are visible inside the ChronoArchiver window.
"""

import customtkinter as ctk
import os
import platform
import threading
import time
import psutil
import subprocess
from tkinter import filedialog, messagebox
import concurrent.futures

from core.av1_engine import AV1EncoderEngine, EncodingProgress
from core.av1_settings import AV1Settings
from ui.theme import (
    BG_PRIMARY, BG_SECONDARY, BG_TERTIARY,
    ACCENT, TEXT_PRIMARY, TEXT_MUTED, SEPARATOR,
    FONT_MAIN, FONT_HEADER,
)

# Shared font shortcuts
_F  = FONT_MAIN[0]   # e.g. "Inter"
_FH = FONT_HEADER[0]
_SML = (_F, 8)        # tiny hint text
_MED = (_F, 10)       # compact label/checkbox text
_HDR = (_F, 9, "bold") # section headers


def _section(parent, text: str):
    ctk.CTkLabel(
        parent, text=text, font=_HDR,
        text_color="#555555", anchor="w",
    ).pack(anchor="w", pady=(0, 2))


def _hint(parent, text: str, padx_left: int = 20):
    ctk.CTkLabel(
        parent, text=text, font=_SML,
        text_color="#444444", anchor="w",
    ).pack(anchor="w", padx=(padx_left, 0), pady=(0, 1))


def _cb(parent, text: str, text_color=None, **kw) -> ctk.CTkCheckBox:
    """Compact checkbox matching Qt density."""
    kwargs = dict(
        text=text, font=_MED,
        checkbox_width=16, checkbox_height=16,
        corner_radius=3, border_width=2,
    )
    if text_color:
        kwargs["text_color"] = text_color
    kwargs.update(kw)
    return ctk.CTkCheckBox(parent, **kwargs)


class ThreadSlot(ctk.CTkFrame):
    """Single encoding-thread monitor row."""

    def __init__(self, master, thread_id: int):
        super().__init__(
            master, fg_color=BG_TERTIARY,
            corner_radius=4, border_width=1, border_color=SEPARATOR,
        )
        self.thread_id = thread_id

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(3, 0))

        self.lbl_title = ctk.CTkLabel(
            top, text=f"Thread {thread_id}", font=(_F, 9, "bold"),
            text_color=TEXT_MUTED, anchor="w",
        )
        self.lbl_title.pack(side="left", fill="x", expand=True)

        self.lbl_speed = ctk.CTkLabel(top, text="-", font=(_F, 9, "bold"), text_color=ACCENT)
        self.lbl_speed.pack(side="right")

        self.progress = ctk.CTkProgressBar(self, height=10, progress_color=ACCENT)
        self.progress.pack(fill="x", padx=8, pady=(2, 1))
        self.progress.set(0)

        bot = ctk.CTkFrame(self, fg_color="transparent")
        bot.pack(fill="x", padx=8, pady=(0, 3))

        self.lbl_vid = ctk.CTkLabel(bot, text="VID: -", font=_SML, text_color=TEXT_MUTED, anchor="w")
        self.lbl_vid.pack(side="left")
        self.lbl_aud = ctk.CTkLabel(bot, text="AUD: -", font=_SML, text_color=TEXT_MUTED, anchor="w")
        self.lbl_aud.pack(side="left", padx=(12, 0))

    def update(self, filename, percent, vid_info, aud_info, speed):
        short = (filename[:28] + "…") if len(filename) > 28 else filename
        self.lbl_title.configure(text=f"T{self.thread_id}: {short}")
        self.progress.set(percent / 100)
        if vid_info:
            self.lbl_vid.configure(text=f"VID: {vid_info}")
        if aud_info:
            self.lbl_aud.configure(text=f"AUD: {aud_info}")
        self.lbl_speed.configure(text=f"{speed:.1f}x")

    def reset(self):
        self.lbl_title.configure(text=f"Thread {self.thread_id}")
        self.progress.set(0)
        self.lbl_vid.configure(text="VID: -")
        self.lbl_aud.configure(text="AUD: -")
        self.lbl_speed.configure(text="-")


class AV1EncoderTab(ctk.CTkFrame):

    def __init__(self, master, log_callback, file_logger,
                 status_callback, background_callback):
        super().__init__(master, fg_color="transparent")

        self.log_callback        = log_callback
        self.file_logger         = file_logger
        self.status_callback     = status_callback
        self.background_callback = background_callback

        self.settings = AV1Settings()
        self.engine   = AV1EncoderEngine()

        self.is_encoding       = False
        self.is_paused         = False
        self.start_time        = 0.0
        self.total_space_saved = 0
        self.active_worker_engines: set = set()
        self.worker_lock       = threading.Lock()

        self.gpu_cache      = "N/A"
        self.last_gpu_check = 0.0
        self.slots: list[ThreadSlot] = []

        # Outer grid: row 0 = top strip (fixed), 1 = slots (expand), 2 = bar (fixed)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        self._build_top_strip()
        self._build_thread_area()
        self._build_bottom_bar()

        threading.Thread(target=self._metrics_loop, daemon=True).start()

    # =========================================================================
    # TOP STRIP
    # =========================================================================

    def _build_top_strip(self):
        top = ctk.CTkFrame(self, fg_color=BG_SECONDARY)
        top.grid(row=0, column=0, padx=10, pady=(8, 4), sticky="ew")

        # Relative widths matching the original: Directories widest, Metrics narrowest
        top.grid_columnconfigure(0, weight=10)
        top.grid_columnconfigure(1, weight=7)
        top.grid_columnconfigure(2, weight=6)
        top.grid_columnconfigure(3, weight=3)

        self._build_directories(top, col=0)
        self._build_configuration(top, col=1)
        self._build_options(top, col=2)
        self._build_metrics(top, col=3)

    def _build_directories(self, parent, col: int):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=0, column=col, padx=8, pady=8, sticky="nsew")
        _section(f, "DIRECTORIES")

        def _path_row(placeholder, hint_text, browse_cmd, saved_key):
            # Use grid so entry expands and Browse stays right-anchored
            row = ctk.CTkFrame(f, fg_color="transparent")
            row.pack(fill="x", pady=(2, 0))
            row.grid_columnconfigure(0, weight=1)

            entry = ctk.CTkEntry(
                row, placeholder_text=placeholder,
                fg_color=BG_TERTIARY, border_width=1,
                font=_MED, height=26,
            )
            entry.grid(row=0, column=0, sticky="ew")
            entry.insert(0, self.settings.get(saved_key))

            ctk.CTkButton(
                row, text="Browse", width=55, height=26,
                font=_MED, fg_color="#333333", hover_color="#444444",
                command=browse_cmd,
            ).grid(row=0, column=1, padx=(4, 0))

            ctk.CTkLabel(
                f, text=hint_text, font=_SML,
                text_color="#444444", anchor="w",
            ).pack(anchor="w", pady=(1, 4))

            return entry

        self.entry_src = _path_row(
            "SOURCE PATH (local or smb://)",
            "Source — local path or network share",
            self.browse_source, "source_folder",
        )
        self.entry_dst = _path_row(
            "TARGET PATH (local or smb://)",
            "Target — AV1 encoded output destination",
            self.browse_target, "target_folder",
        )

    def _build_configuration(self, parent, col: int):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=0, column=col, padx=8, pady=8, sticky="nsew")
        _section(f, "CONFIGURATION")

        lbl_w = 52

        def _lbl(txt):
            return ctk.CTkLabel(f, text=txt, font=_MED,
                                 text_color=TEXT_MUTED, anchor="w", width=lbl_w)

        def _hint_inline(row_frame, txt):
            ctk.CTkLabel(row_frame, text=txt, font=_SML,
                         text_color="#444444").pack(side="left", padx=4)

        # Quality
        r = ctk.CTkFrame(f, fg_color="transparent")
        r.pack(fill="x", pady=1)
        _lbl("Quality").pack(in_=r, side="left")
        self.lbl_quality_val = ctk.CTkLabel(
            r, text=str(self.settings.get("quality")),
            font=(_F, 10, "bold"), text_color=ACCENT, width=22)
        self.lbl_quality_val.pack(side="left")
        self.slider_quality = ctk.CTkSlider(
            r, from_=0, to=63, height=14, command=self.on_quality_change)
        self.slider_quality.set(self.settings.get("quality"))
        self.slider_quality.pack(side="left", fill="x", expand=True, padx=4)
        _hint_inline(r, "CQ level — lower = better quality")

        # Preset
        r = ctk.CTkFrame(f, fg_color="transparent")
        r.pack(fill="x", pady=1)
        _lbl("Preset").pack(in_=r, side="left")
        preset_opts = [
            "P7: Deep Archival", "P6: High Quality", "P5: Balanced",
            "P4: Standard", "P3: Fast", "P2: Draft", "P1: Preview",
        ]
        self.combo_preset = ctk.CTkComboBox(
            r, values=preset_opts, width=155,
            font=_MED, dropdown_font=_MED, command=self.on_preset_change)
        curr = self.settings.get("preset").upper()
        self.combo_preset.set(
            next((x for x in preset_opts if x.startswith(curr)), "P4: Standard"))
        self.combo_preset.pack(side="left", fill="x", expand=True)
        _hint_inline(r, "Encode speed vs. efficiency tradeoff")

        # Threads
        r = ctk.CTkFrame(f, fg_color="transparent")
        r.pack(fill="x", pady=1)
        _lbl("Threads").pack(in_=r, side="left")
        self.combo_jobs = ctk.CTkComboBox(
            r, values=["1", "2", "4"], width=65,
            font=_MED, dropdown_font=_MED, command=self.on_jobs_change)
        self.combo_jobs.set(str(self.settings.get("concurrent_jobs")))
        self.combo_jobs.pack(side="left")
        _hint_inline(r, "Parallel encoding slots (1 / 2 / 4)")

        # Optimize Audio
        r = ctk.CTkFrame(f, fg_color="transparent")
        r.pack(fill="x", pady=(3, 1))
        self.check_audio = _cb(
            r, "Optimize Audio",
            command=lambda: self.settings.set(
                "reencode_audio", bool(self.check_audio.get())))
        if self.settings.get("reencode_audio"):
            self.check_audio.select()
        self.check_audio.pack(side="left")
        _hint_inline(r, "Re-encode PCM/unsupported to Opus")

    def _build_options(self, parent, col: int):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=0, column=col, padx=8, pady=8, sticky="nsew")
        _section(f, "OPTIONS")

        # Keep Subdirs
        self.check_subdirs = _cb(
            f, "Keep Subdirs",
            command=lambda: self.settings.set(
                "maintain_structure", bool(self.check_subdirs.get())))
        if self.settings.get("maintain_structure"):
            self.check_subdirs.select()
        self.check_subdirs.pack(anchor="w", pady=(1, 0))
        _hint(f, "Mirror source folder tree in target")

        # Shutdown When Done
        self.check_shutdown = _cb(
            f, "Shutdown When Done",
            command=lambda: self.settings.set(
                "shutdown_on_finish", bool(self.check_shutdown.get())))
        if self.settings.get("shutdown_on_finish"):
            self.check_shutdown.select()
        self.check_shutdown.pack(anchor="w", pady=(2, 0))
        _hint(f, "Power off system after queue finishes")

        # HW Accelerated Decode
        self.check_hwaccel = _cb(
            f, "HW Accelerated Decode",
            command=lambda: self.settings.set(
                "hw_accel_decode", bool(self.check_hwaccel.get())))
        if self.settings.get("hw_accel_decode"):
            self.check_hwaccel.select()
        self.check_hwaccel.pack(anchor="w", pady=(2, 0))
        _hint(f, "Use GPU for demux / decode stage")

        # Skip Short Clips — checkbox + HH MM SS inline
        skip_row = ctk.CTkFrame(f, fg_color="transparent")
        skip_row.pack(anchor="w", fill="x", pady=(2, 0))
        self.check_skip = _cb(skip_row, "Skip Short Clips",
                               command=self.toggle_skip_fields)
        if self.settings.get("rejects_enabled"):
            self.check_skip.select()
        self.check_skip.pack(side="left")

        def _te(default):
            e = ctk.CTkEntry(skip_row, width=24, height=18, font=(_F, 9))
            e.pack(side="left", padx=(3, 1))
            e.insert(0, str(default))
            return e

        self.entry_skip_h = _te(self.settings.get("rejects_h"))
        self.entry_skip_m = _te(self.settings.get("rejects_m"))
        self.entry_skip_s = _te(self.settings.get("rejects_s"))
        _hint(f, "Skip files shorter than HH:MM:SS threshold")

        # Delete Source on Success
        self.check_del = _cb(
            f, "Delete Source on Success",
            text_color="#ef4444",
            command=self.on_delete_toggle)
        if self.settings.get("delete_on_success"):
            self.check_del.select()
        self.check_del.pack(anchor="w", pady=(2, 0))

        self.check_del_confirm = _cb(
            f, "Confirm Delete Safety",
            command=self.on_delete_toggle)
        if self.settings.get("delete_on_success_confirm"):
            self.check_del_confirm.select()
        self.check_del_confirm.pack(anchor="w", padx=(18, 0))
        _hint(f, "Both boxes must be checked to enable", padx_left=18)

        self.toggle_skip_fields()

    def _build_metrics(self, parent, col: int):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=0, column=col, padx=8, pady=8, sticky="nsew")
        _section(f, "METRICS")

        def _row(label):
            r = ctk.CTkFrame(f, fg_color="transparent")
            r.pack(fill="x", pady=1)
            ctk.CTkLabel(r, text=label, font=_SML,
                         text_color="#555555", width=30, anchor="w").pack(side="left")
            val = ctk.CTkLabel(r, text="–", font=(_F, 9, "bold"),
                               text_color=TEXT_PRIMARY, anchor="w")
            val.pack(side="left")
            return val

        self.lbl_cpu = _row("CPU")
        self.lbl_gpu = _row("GPU")
        self.lbl_ram = _row("RAM")

    # =========================================================================
    # THREAD AREA (middle, expanding)
    # =========================================================================

    def _build_thread_area(self):
        mid = ctk.CTkFrame(self, fg_color="transparent")
        mid.grid(row=1, column=0, padx=10, pady=2, sticky="nsew")
        mid.grid_columnconfigure(0, weight=3)
        mid.grid_columnconfigure(1, weight=1)
        mid.grid_rowconfigure(0, weight=1)

        # Slots panel
        slots_outer = ctk.CTkFrame(mid, fg_color=BG_SECONDARY)
        slots_outer.grid(row=0, column=0, padx=(0, 6), sticky="nsew")

        hdr = ctk.CTkFrame(slots_outer, fg_color="transparent")
        hdr.pack(fill="x", padx=8, pady=(4, 2))
        ctk.CTkLabel(hdr, text="WORK PROGRESS", font=_HDR,
                     text_color="#555555").pack(side="left")
        self.lbl_io = ctk.CTkLabel(hdr, text="I/O: –", font=_SML, text_color=ACCENT)
        self.lbl_io.pack(side="left", padx=12)
        self.lbl_saved = ctk.CTkLabel(hdr, text="Space Saved: 0 MB",
                                      font=(_F, 9, "bold"), text_color="#10b981")
        self.lbl_saved.pack(side="left")
        self.lbl_time = ctk.CTkLabel(hdr, text="Time: --:--:--",
                                     font=(_F, 9, "bold"), text_color=ACCENT)
        self.lbl_time.pack(side="right")

        slots_inner = ctk.CTkFrame(slots_outer, fg_color="transparent")
        slots_inner.pack(fill="both", expand=True, padx=8, pady=(0, 6))

        for i in range(4):
            slot = ThreadSlot(slots_inner, i + 1)
            slot.pack(fill="x", pady=2)
            self.slots.append(slot)
            if i >= self.settings.get("concurrent_jobs"):
                slot.pack_forget()

        # Queue panel
        q_outer = ctk.CTkFrame(mid, fg_color=BG_SECONDARY)
        q_outer.grid(row=0, column=1, sticky="nsew")
        ctk.CTkLabel(q_outer, text="QUEUE", font=_HDR,
                     text_color="#555555").pack(anchor="w", padx=8, pady=(4, 2))
        self.scroll_queue = ctk.CTkScrollableFrame(
            q_outer, fg_color=BG_TERTIARY, corner_radius=0)
        self.scroll_queue.pack(fill="both", expand=True, padx=4, pady=(0, 4))

    # =========================================================================
    # BOTTOM BAR
    # =========================================================================

    def _build_bottom_bar(self):
        bar = ctk.CTkFrame(self, fg_color=BG_SECONDARY)
        bar.grid(row=2, column=0, padx=10, pady=(2, 8), sticky="ew")

        self.master_progress = ctk.CTkProgressBar(
            bar, height=16, progress_color="#059669")
        self.master_progress.pack(fill="x", padx=8, pady=(6, 2))
        self.master_progress.set(0)

        self.lbl_master_stats = ctk.CTkLabel(
            bar, text="0/0 Files Processed (0%)",
            font=_SML, text_color=TEXT_MUTED, anchor="center")
        self.lbl_master_stats.pack()

        btn_row = ctk.CTkFrame(bar, fg_color="transparent")
        btn_row.pack(fill="x", padx=8, pady=(4, 8))

        self.btn_start = ctk.CTkButton(
            btn_row, text="START ENCODING", font=(_FH, 12, "bold"),
            fg_color="#064e3b", hover_color="#065f46", height=38,
            command=self.start_encoding)
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_pause = ctk.CTkButton(
            btn_row, text="PAUSE", font=(_FH, 12, "bold"),
            fg_color=BG_TERTIARY, hover_color="#3a3a3a",
            width=100, height=38, state="disabled",
            command=self.toggle_pause)
        self.btn_pause.pack(side="left", padx=4)

        self.btn_stop = ctk.CTkButton(
            btn_row, text="STOP", font=(_FH, 12, "bold"),
            fg_color="#450a0a", hover_color="#7f1d1d",
            width=100, height=38, state="disabled",
            command=self.stop_encoding)
        self.btn_stop.pack(side="right")

    # =========================================================================
    # CALLBACKS
    # =========================================================================

    def browse_source(self):
        p = filedialog.askdirectory()
        if p:
            self.entry_src.delete(0, "end")
            self.entry_src.insert(0, p)
            self.settings.set("source_folder", p)

    def browse_target(self):
        p = filedialog.askdirectory()
        if p:
            self.entry_dst.delete(0, "end")
            self.entry_dst.insert(0, p)
            self.settings.set("target_folder", p)

    def on_quality_change(self, val):
        v = int(val)
        self.lbl_quality_val.configure(text=str(v))
        self.settings.set("quality", v)

    def on_preset_change(self, val):
        self.settings.set("preset", val.split(":")[0].lower())

    def on_jobs_change(self, val):
        n = int(val)
        self.settings.set("concurrent_jobs", n)
        for i, slot in enumerate(self.slots):
            if i < n:
                slot.pack(fill="x", pady=2)
            else:
                slot.pack_forget()

    def toggle_skip_fields(self):
        enabled = bool(self.check_skip.get())
        self.settings.set("rejects_enabled", enabled)
        state = "normal" if enabled else "disabled"
        for e in (self.entry_skip_h, self.entry_skip_m, self.entry_skip_s):
            e.configure(state=state)

    def on_delete_toggle(self):
        self.settings.set("delete_on_success", bool(self.check_del.get()))
        self.settings.set("delete_on_success_confirm", bool(self.check_del_confirm.get()))

    # =========================================================================
    # BACKGROUND THREADS
    # =========================================================================

    def _metrics_loop(self):
        while True:
            try:
                cpu = psutil.cpu_percent()
                ram = psutil.virtual_memory().percent
                if time.time() - self.last_gpu_check > 5:
                    self.gpu_cache      = self._get_gpu()
                    self.last_gpu_check = time.time()
                gpu = self.gpu_cache
                self.after(0, lambda c=cpu, g=gpu, r=ram: (
                    self.lbl_cpu.configure(text=f"{c:.1f}%"),
                    self.lbl_gpu.configure(text=g),
                    self.lbl_ram.configure(text=f"{r:.1f}%"),
                ))
            except Exception:
                pass
            time.sleep(2)

    def _get_gpu(self) -> str:
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=utilization.gpu",
                 "--format=csv,noheader,nounits"],
                stderr=subprocess.STDOUT, text=True).strip()
            return f"{out}%"
        except Exception:
            return "N/A"

    def _timer_loop(self):
        while self.is_encoding:
            e = int(time.time() - self.start_time)
            h, m, s = e // 3600, (e % 3600) // 60, e % 60
            self.after(0, lambda h=h, m=m, s=s:
                       self.lbl_time.configure(text=f"Time: {h:02}:{m:02}:{s:02}"))
            time.sleep(1)

    # =========================================================================
    # ENCODE LIFECYCLE
    # =========================================================================

    def start_encoding(self):
        src = self.entry_src.get().strip()
        dst = self.entry_dst.get().strip()
        if not src or not dst:
            messagebox.showerror("Error", "Please select source and target directories.")
            return

        self.is_encoding       = True
        self.is_paused         = False
        self.start_time        = time.time()
        self.total_space_saved = 0

        self.btn_start.configure(state="disabled")
        self.btn_pause.configure(state="normal", text="PAUSE", fg_color=BG_TERTIARY)
        self.btn_stop.configure(state="normal")
        self.log_callback("Batch encoding process started.")
        self.status_callback("ENCODING", "#059669")

        threading.Thread(target=self._run_job, args=(src, dst), daemon=True).start()
        threading.Thread(target=self._timer_loop,                  daemon=True).start()

    def stop_encoding(self):
        self.is_encoding = False
        self.is_paused   = False
        with self.worker_lock:
            for eng in self.active_worker_engines:
                eng.cancel()
        self.btn_start.configure(state="normal")
        self.btn_pause.configure(state="disabled", text="PAUSE", fg_color=BG_TERTIARY)
        self.btn_stop.configure(state="disabled")
        for slot in self.slots:
            slot.reset()
        self.status_callback("READY")
        self.background_callback("Idle")

    def toggle_pause(self):
        if not self.is_encoding:
            return
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.btn_pause.configure(text="RESUME", fg_color=ACCENT)
            with self.worker_lock:
                for eng in self.active_worker_engines:
                    eng.pause()
            self.log_callback("Encoding paused.")
        else:
            self.btn_pause.configure(text="PAUSE", fg_color=BG_TERTIARY)
            with self.worker_lock:
                for eng in self.active_worker_engines:
                    eng.resume()
            self.log_callback("Encoding resumed.")

    # =========================================================================
    # JOB RUNNER
    # =========================================================================

    def _run_job(self, src: str, dst: str):
        self.log_callback("Scanning for video files...")
        files = list(self.engine.scan_files(src))
        if not files:
            self.log_callback("No compatible files found.")
            self.after(0, self.stop_encoding)
            return

        self.log_callback(f"Found {len(files)} files to encode.")
        self.after(0, self._populate_queue, [os.path.basename(f[0]) for f in files])

        total = len(files)
        done  = [0]
        lock  = threading.Lock()

        reject_s = 0
        if self.settings.get("rejects_enabled"):
            try:
                reject_s = (
                    int(self.entry_skip_h.get() or 0) * 3600
                    + int(self.entry_skip_m.get() or 0) * 60
                    + int(self.entry_skip_s.get() or 0)
                )
            except ValueError:
                pass

        def worker(file_info, slot_idx):
            if not self.is_encoding:
                return
            path, size = file_info

            if reject_s:
                dur = self.engine._get_video_duration(path)
                if dur < reject_s:
                    self.log_callback(
                        f"Skipping {os.path.basename(path)} ({dur:.0f}s < {reject_s}s)")
                    with lock:
                        done[0] += 1
                        self.after(0, self._update_master, done[0], total)
                    return

            eng = AV1EncoderEngine(job_id=slot_idx)
            eng.on_progress = lambda j, p: self.after(
                0, lambda p=p, si=slot_idx:
                self.slots[si].update(p.file_name, p.percent, None, None, p.speed))
            eng.on_details = lambda j, v, a: self.after(
                0, lambda v=v, a=a, si=slot_idx:
                self.slots[si].update("", 0, v, a, 0))

            with self.worker_lock:
                if not self.is_encoding:
                    return
                self.active_worker_engines.add(eng)
                if self.is_paused:
                    eng.pause()

            fname = os.path.basename(path)
            if self.settings.get("maintain_structure"):
                rel   = os.path.relpath(path, src)
                tpath = os.path.join(dst, os.path.splitext(rel)[0] + "_av1.mkv")
                os.makedirs(os.path.dirname(tpath), exist_ok=True)
            else:
                tpath = os.path.join(dst, os.path.splitext(fname)[0] + "_av1.mkv")

            try:
                ok, _, out_p = eng.encode_file(
                    path, tpath,
                    self.settings.get("quality"),
                    self.settings.get("preset"),
                    self.settings.get("reencode_audio"),
                    hw_accel=self.settings.get("hw_accel_decode"),
                )
                if ok and self.is_encoding:
                    try:
                        saved = size - os.path.getsize(out_p)
                        with lock:
                            self.total_space_saved += max(0, saved)
                            mb = self.total_space_saved // (1024 * 1024)
                            self.after(0, lambda mb=mb:
                                       self.lbl_saved.configure(
                                           text=f"Space Saved: {mb} MB"))
                    except OSError:
                        pass
                    if (self.settings.get("delete_on_success") and
                            self.settings.get("delete_on_success_confirm")):
                        try:
                            os.remove(path)
                            self.log_callback(f"Deleted source: {fname}")
                        except Exception as e:
                            self.log_callback(f"Delete failed ({fname}): {e}")
            finally:
                with self.worker_lock:
                    self.active_worker_engines.discard(eng)
                with lock:
                    done[0] += 1
                    self.after(0, self._update_master, done[0], total)

        jobs = self.settings.get("concurrent_jobs", 1)
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
            for i, fi in enumerate(files):
                ex.submit(worker, fi, i % jobs)

        self.after(0, self.stop_encoding)
        self.log_callback("Batch encoding process complete.")

        if self.settings.get("shutdown_on_finish"):
            self.log_callback("Shutting down system as requested...")
            os.system("shutdown /s /t 60" if platform.system() == "Windows"
                      else "shutdown -h +1")

    # =========================================================================
    # UI HELPERS
    # =========================================================================

    def _populate_queue(self, filenames: list):
        for w in self.scroll_queue.winfo_children():
            w.destroy()
        for name in filenames:
            ctk.CTkLabel(
                self.scroll_queue, text=name,
                font=(_F, 9), text_color=TEXT_MUTED, anchor="w",
            ).pack(fill="x", padx=4)

    def _update_master(self, done: int, total: int):
        prog = done / total if total else 0
        self.master_progress.set(prog)
        self.lbl_master_stats.configure(
            text=f"{done}/{total} Files Processed ({int(prog * 100)}%)")
