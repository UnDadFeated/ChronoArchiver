import customtkinter as ctk
import sys
import pathlib
from core.logger import setup_logger
from core.updater import UpdaterEngine
from version import __version__, APP_NAME
import tkinter as tk

from ui.theme import BG_PRIMARY, BG_SECONDARY, BG_TERTIARY, ACCENT, TEXT_PRIMARY, TEXT_MUTED, SEPARATOR, FONT_MAIN, FONT_HEADER

# Ensure src is in path logic if running raw
sys.path.append(str(pathlib.Path(__file__).parent.parent))

# Import tabs after sys.path update
from ui.tabs import OrganizerTab, AIScannerTab, DonateTab
from ui.tabs.av1_tab import AV1EncoderTab

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.configure(fg_color=BG_PRIMARY)
        self.logger = setup_logger()
        self.logger.info("Initializing Main App Window")
        
        self.updater = UpdaterEngine(self, self.log)

        self.title(f"{APP_NAME} - Time to Archive! ({__version__})")
        self.geometry("1100x750") # Slightly larger for the new tab
        self.resizable(False, False)

        # Set Icon
        assets_dir = pathlib.Path(__file__).parent.parent / 'assets'
        if sys.platform == 'win32':
            icon_path = assets_dir / 'icon.ico'
            if icon_path.exists():
                self.iconbitmap(str(icon_path))
        else:
            icon_path = assets_dir / 'icon.png'
            if icon_path.exists():
                img = tk.PhotoImage(file=str(icon_path))
                self.iconphoto(True, img)
        
        # Add 12px padding on outer wrapper
        self.main_wrapper = ctk.CTkFrame(self, fg_color="transparent")
        self.main_wrapper.pack(fill="both", expand=True, padx=12, pady=12)

        # PanedWindow
        self.paned_window = tk.PanedWindow(self.main_wrapper, orient="vertical", sashwidth=6, bg=BG_PRIMARY, borderwidth=0)
        self.paned_window.pack(fill="both", expand=True, padx=0, pady=0)

        # === Top Pane: Tab View ===
        self.top_frame = ctk.CTkFrame(self.paned_window, fg_color="transparent")
        
        self.tab_view = ctk.CTkTabview(self.top_frame, fg_color=BG_SECONDARY, segmented_button_selected_color=ACCENT)
        self.tab_view.pack(fill="both", expand=True, padx=0, pady=0)

        self.tab_org = self.tab_view.add("Media Organizer")
        self.tab_av1 = self.tab_view.add("Mass AI Encoder")
        self.tab_ai = self.tab_view.add("AI Scan")
        self.tab_donate = self.tab_view.add("Donate")

        # Init Tabs
        self.org_frame = OrganizerTab(self.tab_org, self.log, self.logger, self.set_status, self.set_background)
        self.org_frame.pack(fill="both", expand=True)

        self.av1_frame = AV1EncoderTab(self.tab_av1, self.log, self.logger, self.set_status, self.set_background)
        self.av1_frame.pack(fill="both", expand=True)

        self.ai_frame = AIScannerTab(self.tab_ai, self.log, self.logger, self.set_status, self.set_background)
        self.ai_frame.pack(fill="both", expand=True)

        self.donate_frame = DonateTab(self.tab_donate)
        self.donate_frame.pack(fill="both", expand=True)
        
        self.paned_window.add(self.top_frame, minsize=400)
        
        # === Bottom Pane: Log Area ===
        self.bottom_frame = ctk.CTkFrame(self.paned_window, fg_color="transparent")
        
        self.grip_frame = ctk.CTkFrame(self.bottom_frame, fg_color="transparent", height=10)
        self.grip_frame.pack(fill="x", padx=0, pady=0)
        
        self.sep = ctk.CTkFrame(self.grip_frame, height=1, fg_color=SEPARATOR)
        self.sep.pack(fill="x", padx=0, pady=(4, 4))

        self.console_header = ctk.CTkFrame(self.bottom_frame, fg_color="transparent")
        self.console_header.pack(fill="x", padx=0, pady=(0, 2))
        
        ctk.CTkLabel(self.console_header, text="LOG CONSOLE", font=FONT_HEADER, text_color=TEXT_MUTED, anchor="w").pack(side="left")
        
        # Branding Catchline
        ctk.CTkLabel(self.console_header, text="Time to Archive!", 
                     font=(FONT_MAIN[0], FONT_MAIN[1], 'italic'), text_color=ACCENT).pack(side="left", padx=20)
        
        self.btn_update = ctk.CTkButton(self.console_header, text="Check for Updates", width=120, height=24, 
                                        font=FONT_MAIN, corner_radius=6, fg_color=ACCENT, hover_color="#5a8ff0",
                                        command=lambda: self.updater.check_for_updates(manual=True))
        self.btn_update.pack(side="right")
        
        self.log_text = ctk.CTkTextbox(self.bottom_frame, height=150, font=("Consolas", 11), fg_color="#141414", text_color="#a8d8a8", corner_radius=4)
        self.log_text.pack(fill="both", expand=True, padx=0, pady=(0, 0))
        
        self.paned_window.add(self.bottom_frame, minsize=100)
        
        # === Global Footer ===
        self.footer_frame = ctk.CTkFrame(self.main_wrapper, fg_color=BG_SECONDARY, height=28, corner_radius=6)
        self.footer_frame.pack(fill="x", padx=0, pady=(10, 0))
        
        self.lbl_status = ctk.CTkLabel(self.footer_frame, text="READY", font=(FONT_MAIN[0], 10, "bold"), text_color=ACCENT)
        self.lbl_status.pack(side="left", padx=15)
        
        self.lbl_background = ctk.CTkLabel(self.footer_frame, text="Idle", font=(FONT_MAIN[0], 10), text_color=TEXT_MUTED)
        self.lbl_background.pack(side="left", expand=True)
        
        self.btn_footer_donate = ctk.CTkLabel(self.footer_frame, text="SUPPORT PROJECT", font=(FONT_MAIN[0], 9, "bold"), text_color=ACCENT, cursor="hand2")
        self.btn_footer_donate.pack(side="right", padx=15)
        self.btn_footer_donate.bind("<Button-1>", lambda e: self.tab_view.set("Donate"))
        
        self.log(f"Welcome to {APP_NAME} {__version__} (Python Edition)")
        self.log("Ready.")

    def log(self, message):
        def _insert():
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
        self.after(0, _insert)

    def set_status(self, text, color=ACCENT):
        def _update():
            self.lbl_status.configure(text=text.upper(), text_color=color)
        self.after(0, _update)

    def set_background(self, text):
        def _update():
            self.lbl_background.configure(text=text)
        self.after(0, _update)

if __name__ == "__main__":
    app = App()
    app.mainloop()
