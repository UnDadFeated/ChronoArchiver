import customtkinter as ctk
import os
import pathlib
import threading
import time
from tkinter import filedialog, messagebox
import concurrent.futures
from core.av1_engine import AV1EncoderEngine, EncodingProgress
from core.av1_settings import AV1Settings
from ui.theme import BG_PRIMARY, BG_SECONDARY, BG_TERTIARY, ACCENT, TEXT_PRIMARY, TEXT_MUTED, SEPARATOR, FONT_MAIN, FONT_HEADER

class ThreadSlot(ctk.CTkFrame):
    """Represents a high-density monitoring slot for a single encoding thread."""
    def __init__(self, master, thread_id):
        super().__init__(master, fg_color=BG_TERTIARY, corner_radius=6, border_width=1, border_color=SEPARATOR)
        self.thread_id = thread_id
        
        self.lbl_title = ctk.CTkLabel(self, text=f"THREAD {thread_id}", font=(FONT_HEADER[0], 9, "bold"), text_color=TEXT_MUTED)
        self.lbl_title.pack(anchor="w", padx=8, pady=(4, 0))
        
        self.progress = ctk.CTkProgressBar(self, height=12, progress_color=ACCENT)
        self.progress.pack(fill="x", padx=8, pady=4)
        self.progress.set(0)
        
        self.info_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.info_frame.pack(fill="x", padx=8, pady=(0, 4))
        
        # Stacked Codecs
        self.codec_frame = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        self.codec_frame.pack(side="left", fill="both", expand=True)
        
        self.lbl_vid = ctk.CTkLabel(self.codec_frame, text="VIDEO: -", font=(FONT_MAIN[0], 8), text_color=TEXT_MUTED, anchor="w", height=10)
        self.lbl_vid.pack(fill="x")
        self.lbl_aud = ctk.CTkLabel(self.codec_frame, text="AUDIO: -", font=(FONT_MAIN[0], 8), text_color=TEXT_MUTED, anchor="w", height=10)
        self.lbl_aud.pack(fill="x")
        
        self.lbl_speed = ctk.CTkLabel(self.info_frame, text="0.0x", font=(FONT_HEADER[0], 11, "bold"), text_color=ACCENT)
        self.lbl_speed.pack(side="right", padx=(5, 0))

    def update(self, filename, percent, vid_info, aud_info, speed):
        self.lbl_title.configure(text=f"T{self.thread_id}: {filename[:20]}..." if len(filename) > 20 else f"T{self.thread_id}: {filename}")
        self.progress.set(percent / 100)
        if vid_info: self.lbl_vid.configure(text=f"VID: {vid_info}")
        if aud_info: self.lbl_aud.configure(text=f"AUD: {aud_info}")
        self.lbl_speed.configure(text=f"{speed:.2f}x")

    def reset(self):
        self.lbl_title.configure(text=f"THREAD {self.thread_id}")
        self.progress.set(0)
        self.lbl_vid.configure(text="VIDEO: -")
        self.lbl_aud.configure(text="AUDIO: -")
        self.lbl_speed.configure(text="0.0x")

class AV1EncoderTab(ctk.CTkFrame):
    def __init__(self, master, log_callback, file_logger, status_callback, background_callback):
        super().__init__(master, fg_color="transparent")
        self.log_callback = log_callback
        self.file_logger = file_logger
        self.status_callback = status_callback
        self.background_callback = background_callback
        self.settings = AV1Settings()
        self.engine = AV1EncoderEngine()
        
        self.is_encoding = False
        self.start_time = 0
        self.total_queue_size = 0
        self.processed_size = 0
        self.active_worker_engines = set()
        self.worker_lock = threading.Lock()
        
        # UI State
        self.slots = []
        self.job_to_slot = {} # job_id -> slot_index

        # Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # === Top: Configuration ===
        self.frame_top = ctk.CTkFrame(self, fg_color=BG_SECONDARY)
        self.frame_top.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        # Paths
        self.path_container = ctk.CTkFrame(self.frame_top, fg_color="transparent")
        self.path_container.pack(fill="x", padx=10, pady=10)
        
        # Source
        ctk.CTkLabel(self.path_container, text="SOURCE:", font=FONT_HEADER, text_color=TEXT_MUTED, width=80, anchor="w").grid(row=0, column=0, padx=(0,10), pady=2)
        self.entry_src = ctk.CTkEntry(self.path_container, placeholder_text="Source directory...", fg_color=BG_TERTIARY, border_color=SEPARATOR, border_width=1)
        self.entry_src.grid(row=0, column=1, sticky="ew", pady=2)
        self.entry_src.insert(0, self.settings.get("source_folder"))
        ctk.CTkButton(self.path_container, text="Browse", width=80, fg_color=ACCENT, command=self.browse_source).grid(row=0, column=2, padx=(10,0), pady=2)
        
        # Target
        ctk.CTkLabel(self.path_container, text="TARGET:", font=FONT_HEADER, text_color=TEXT_MUTED, width=80, anchor="w").grid(row=1, column=0, padx=(0,10), pady=2)
        self.entry_dst = ctk.CTkEntry(self.path_container, placeholder_text="Target directory...", fg_color=BG_TERTIARY, border_color=SEPARATOR, border_width=1)
        self.entry_dst.grid(row=1, column=1, sticky="ew", pady=2)
        self.entry_dst.insert(0, self.settings.get("target_folder"))
        ctk.CTkButton(self.path_container, text="Browse", width=80, fg_color=ACCENT, command=self.browse_target).grid(row=1, column=2, padx=(10,0), pady=2)
        self.path_container.grid_columnconfigure(1, weight=1)

        # Settings
        self.ctrl_container = ctk.CTkFrame(self.frame_top, fg_color="transparent")
        self.ctrl_container.pack(fill="x", padx=10, pady=(0, 10))
        
        ctk.CTkLabel(self.ctrl_container, text="QUALITY:", font=FONT_MAIN, text_color=TEXT_MUTED).pack(side="left", padx=(0,5))
        self.slider_quality = ctk.CTkSlider(self.ctrl_container, from_=0, to=63, width=120, command=self.on_quality_change)
        self.slider_quality.set(self.settings.get("quality"))
        self.slider_quality.pack(side="left", padx=(0, 5))
        self.lbl_quality_val = ctk.CTkLabel(self.ctrl_container, text=str(self.settings.get("quality")), font=FONT_MAIN, text_color=ACCENT, width=30)
        self.lbl_quality_val.pack(side="left", padx=(0, 15))
        
        ctk.CTkLabel(self.ctrl_container, text="PRESET:", font=FONT_MAIN, text_color=TEXT_MUTED).pack(side="left", padx=(0,5))
        self.combo_preset = ctk.CTkComboBox(self.ctrl_container, values=["p1", "p2", "p3", "p4", "p5", "p6", "p7"], width=70, command=self.on_preset_change)
        self.combo_preset.set(self.settings.get("preset"))
        self.combo_preset.pack(side="left", padx=(0, 15))
        
        ctk.CTkLabel(self.ctrl_container, text="THREADS:", font=FONT_MAIN, text_color=TEXT_MUTED).pack(side="left", padx=(0,5))
        self.combo_jobs = ctk.CTkComboBox(self.ctrl_container, values=["1", "2", "4"], width=60, command=self.on_jobs_change)
        self.combo_jobs.set(str(self.settings.get("concurrent_jobs")))
        self.combo_jobs.pack(side="left", padx=(0, 10))

        # === Middle: Dynamic Slots & Queue ===
        self.frame_mid = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_mid.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.frame_mid.grid_columnconfigure(0, weight=3)
        self.frame_mid.grid_columnconfigure(1, weight=1)
        self.frame_mid.grid_rowconfigure(0, weight=1)

        # Thread Slots Area
        self.frame_slots_container = ctk.CTkFrame(self.frame_mid, fg_color=BG_SECONDARY)
        self.frame_slots_container.grid(row=0, column=0, padx=(0, 10), sticky="nsew")
        ctk.CTkLabel(self.frame_slots_container, text="ACTIVE THREADS", font=FONT_HEADER, text_color=TEXT_MUTED).pack(anchor="w", padx=10, pady=5)
        
        self.frame_slots = ctk.CTkFrame(self.frame_slots_container, fg_color="transparent")
        self.frame_slots.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        for i in range(4):
            slot = ThreadSlot(self.frame_slots, i + 1)
            slot.pack(fill="x", pady=2)
            self.slots.append(slot)
            if i >= self.settings.get("concurrent_jobs"):
                slot.pack_forget()

        # Queue List Area
        self.frame_queue = ctk.CTkFrame(self.frame_mid, fg_color=BG_SECONDARY)
        self.frame_queue.grid(row=0, column=1, sticky="nsew")
        ctk.CTkLabel(self.frame_queue, text="QUEUE", font=FONT_HEADER, text_color=TEXT_MUTED).pack(anchor="w", padx=10, pady=5)
        self.scroll_queue = ctk.CTkScrollableFrame(self.frame_queue, fg_color=BG_TERTIARY, corner_radius=0)
        self.scroll_queue.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        # === Bottom: Global Progress & Actions ===
        self.frame_bot = ctk.CTkFrame(self, fg_color=BG_SECONDARY)
        self.frame_bot.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="ew")
        
        # Metrics Strip
        self.metric_strip = ctk.CTkFrame(self.frame_bot, fg_color="transparent", height=20)
        self.metric_strip.pack(fill="x", padx=10, pady=(5, 0))
        
        self.lbl_elapsed = ctk.CTkLabel(self.metric_strip, text="ELAPSED: 00:00:00", font=(FONT_MAIN[0], 10, "bold"), text_color=TEXT_MUTED)
        self.lbl_elapsed.pack(side="left")
        
        self.lbl_eta = ctk.CTkLabel(self.metric_strip, text="ETA: --:--:--", font=(FONT_MAIN[0], 10, "bold"), text_color=ACCENT)
        self.lbl_eta.pack(side="right")
        
        self.master_progress = ctk.CTkProgressBar(self.frame_bot, height=14, progress_color="#059669")
        self.master_progress.pack(fill="x", padx=10, pady=5)
        self.master_progress.set(0)
        
        self.lbl_master_stats = ctk.CTkLabel(self.frame_bot, text="0/0 Files Processed (0%)", font=(FONT_MAIN[0], 10), text_color=TEXT_MUTED)
        self.lbl_master_stats.pack(pady=(0, 5))

        self.btn_panel = ctk.CTkFrame(self.frame_bot, fg_color="transparent")
        self.btn_panel.pack(fill="x", padx=10, pady=(0, 10))
        
        self.btn_start = ctk.CTkButton(self.btn_panel, text="START ENCODING", font=FONT_HEADER, fg_color="#064e3b", hover_color="#065f46", height=40, command=self.start_encoding)
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.btn_stop = ctk.CTkButton(self.btn_panel, text="STOP", font=FONT_HEADER, fg_color="#450a0a", hover_color="#7f1d1d", height=40, state="disabled", command=self.stop_encoding)
        self.btn_stop.pack(side="right")

    def browse_source(self):
        path = filedialog.askdirectory()
        if path:
            self.entry_src.delete(0, "end")
            self.entry_src.insert(0, path)
            self.settings.set("source_folder", path)

    def browse_target(self):
        path = filedialog.askdirectory()
        if path:
            self.entry_dst.delete(0, "end")
            self.entry_dst.insert(0, path)
            self.settings.set("target_folder", path)

    def on_quality_change(self, val):
        self.lbl_quality_val.configure(text=str(int(val)))
        self.settings.set("quality", int(val))

    def on_preset_change(self, val):
        self.settings.set("preset", val)

    def on_jobs_change(self, val):
        num = int(val)
        self.settings.set("concurrent_jobs", num)
        for i, slot in enumerate(self.slots):
            if i < num: slot.pack(fill="x", pady=2)
            else: slot.pack_forget()

    def start_encoding(self):
        src = self.entry_src.get()
        dst = self.entry_dst.get()
        if not src or not dst:
            messagebox.showerror("Error", "Please select directories.")
            return
        
        self.is_encoding = True
        self.start_time = time.time()
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.log_callback("Batch process started.")
        self.status_callback("ENCODING", "#059669")
        
        threading.Thread(target=self._run_job, args=(src, dst), daemon=True).start()
        threading.Thread(target=self._update_timer, daemon=True).start()

    def stop_encoding(self):
        self.is_encoding = False
        with self.worker_lock:
            for eng in self.active_worker_engines: eng.cancel()
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        for slot in self.slots: slot.reset()
        self.status_callback("READY")
        self.background_callback("Idle")

    def _update_timer(self):
        while self.is_encoding:
            elapsed = int(time.time() - self.start_time)
            h, m, s = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
            self.after(0, lambda: self.lbl_elapsed.configure(text=f"ELAPSED: {h:02}:{m:02}:{s:02}"))
            time.sleep(1)

    def _run_job(self, src, dst):
        self.log_callback("Scanning...")
        files = list(self.engine.scan_files(src))
        if not files:
            self.after(0, self.stop_encoding)
            return
        
        self.after(0, self._populate_queue_list, [os.path.basename(f[0]) for f in files])
        
        total_files = len(files)
        self.total_queue_size = sum(f[1] for f in files)
        self.processed_size = 0
        processed_count = 0
        counter_lock = threading.Lock()
        
        def encode_worker(file_info, slot_idx):
            if not self.is_encoding: return
            file_path, size = file_info
            worker_engine = AV1EncoderEngine(job_id=slot_idx)
            
            # Progress Callbacks
            worker_engine.on_progress = lambda j, p: self.after(0, lambda: self.slots[slot_idx].update(p.file_name, p.percent, None, None, p.speed))
            worker_engine.on_details = lambda j, v, a: self.after(0, lambda: self.slots[slot_idx].update("", 0, v, a, 0))
            
            with self.worker_lock:
                if not self.is_encoding: return
                self.active_worker_engines.add(worker_engine)
            
            # Setup output path
            filename = os.path.basename(file_path)
            target_path = os.path.join(dst, os.path.splitext(filename)[0] + "_av1.mkv")
            
            try:
                worker_engine.encode_file(file_path, target_path, self.settings.get("quality"), self.settings.get("preset"), self.settings.get("reencode_audio"))
            finally:
                with self.worker_lock: self.active_worker_engines.discard(worker_engine)
                nonlocal processed_count
                with counter_lock:
                    processed_count += 1
                    self.processed_size += size
                    prog = processed_count / total_files
                    self.after(0, self._update_master_ui, processed_count, total_files, prog)

        concurrent_jobs = self.settings.get("concurrent_jobs", 1)
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_jobs) as executor:
            for i, file_info in enumerate(files):
                executor.submit(encode_worker, file_info, i % concurrent_jobs)
        
        self.after(0, self.stop_encoding)
        self.log_callback("Process complete.")

    def _populate_queue_list(self, filenames):
        for widget in self.scroll_queue.winfo_children(): widget.destroy()
        for f in filenames:
            ctk.CTkLabel(self.scroll_queue, text=f, font=(FONT_MAIN[0], 9), text_color=TEXT_PRIMARY, anchor="w").pack(fill="x", padx=5)

    def _update_master_ui(self, count, total, prog):
        self.master_progress.set(prog)
        self.lbl_master_stats.configure(text=f"{count}/{total} Files Processed ({int(prog*100)}%)")
        # Simple ETA
        if prog > 0:
            elapsed = time.time() - self.start_time
            total_est = elapsed / prog
            remaining = int(total_est - elapsed)
            h, m, s = remaining // 3600, (remaining % 3600) // 60, remaining % 60
            self.lbl_eta.configure(text=f"ETA: {h:02}:{m:02}:{s:02}")

if __name__ == "__main__":
    pass
