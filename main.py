import tkinter as tk
import ctypes
import ctypes.wintypes
import sys
import os

from PIL import Image, ImageTk
from modules.Hysteresis.gui import VSMModule

def resource_path(relative):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative)

if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# ── Palette ───────────────────────────────────────────────────────────────────
BG         = "#13151a"
SURFACE    = "#1e2028"
SIDEBAR    = "#181921"
BORDER     = "#383530"
ACCENT     = "#f5883a"
ACCENT_DIM = "#6b3c18"
TEXT       = "#ede0d0"
TEXT_DIM   = "#8a8478"
ERROR      = "#f07070"
ERROR_DIM  = "#a03030"

# ── Module registry ───────────────────────────────────────────────────────────
# To add a module: import its class above and add an entry here
MODULES = [
    ("Hysteresis", "DAT → CSV", VSMModule),
]

def _apply_rounded_corners(hwnd):
    # Windows 11 DWM rounded corners via DWMAPI
    try:
        DWMWCP_ROUND = ctypes.c_int(2)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            33,  # DWMWA_WINDOW_CORNER_PREFERENCE
            ctypes.byref(DWMWCP_ROUND),
            ctypes.sizeof(DWMWCP_ROUND),
        )
    except Exception:
        pass


def _add_hover(btn, normal_bg, hover_bg, normal_fg=TEXT_DIM, hover_fg=TEXT):
    btn.bind("<Enter>", lambda e: btn.config(bg=hover_bg, fg=hover_fg))
    btn.bind("<Leave>", lambda e: btn.config(bg=normal_bg, fg=normal_fg))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.overrideredirect(True)
        self.configure(bg=BG)

        # Center on screen
        self.update_idletasks()
        w, h = 1300, 860
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(1100, 720)

        # Apply rounded corners (Windows 11 only)
        if sys.platform == "win32":
            try:
                import platform
                if int(platform.version().split('.')[2]) >= 22000:
                    self.update()
                    hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
                    _apply_rounded_corners(hwnd)
            except Exception:
                pass

        # Load icon for titlebar
        self._icon_img = None
        try:
            img = Image.open(resource_path("icon.png"))
            img = img.resize((24, 24), Image.LANCZOS)
            self._icon_img = ImageTk.PhotoImage(img)
        except Exception:
            pass

        self._drag_x        = 0
        self._drag_y        = 0
        self._active_module = None
        self._nav_buttons   = {}
        self._build()
        self._select(MODULES[0][0])

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        # Custom title bar
        titlebar = tk.Frame(self, bg=SURFACE, height=54)
        titlebar.pack(fill="x")
        titlebar.pack_propagate(False)

        # Icon + title
        if self._icon_img:
            tk.Label(titlebar, image=self._icon_img,
                     bg=SURFACE).pack(side="left", padx=(14, 6), pady=15)
        tk.Label(titlebar, text="Orange Lab Tools",
                 font=("Segoe UI Semibold", 11), bg=SURFACE, fg=TEXT).pack(
                 side="left", pady=0)

        # Window controls — right to left
        btn_close = tk.Button(titlebar, text="✕", font=("Segoe UI", 11),
                              bg=SURFACE, fg=TEXT_DIM, relief="flat",
                              cursor="hand2", bd=0, command=self.destroy,
                              padx=14, pady=14)
        btn_close.pack(side="right")
        _add_hover(btn_close, SURFACE, ERROR_DIM, TEXT_DIM, TEXT)

        btn_max = tk.Button(titlebar, text="▢", font=("Segoe UI", 10),
                            bg=SURFACE, fg=TEXT_DIM, relief="flat",
                            cursor="hand2", bd=0, command=self._toggle_maximize,
                            padx=14, pady=14)
        btn_max.pack(side="right")
        _add_hover(btn_max, SURFACE, BORDER)

        btn_min = tk.Button(titlebar, text="─", font=("Segoe UI", 11),
                            bg=SURFACE, fg=TEXT_DIM, relief="flat",
                            cursor="hand2", bd=0, command=self._toggle_minimize,
                            padx=14, pady=14)
        btn_min.pack(side="right")
        _add_hover(btn_min, SURFACE, BORDER)

        # Drag to move
        titlebar.bind("<ButtonPress-1>", self._drag_start)
        titlebar.bind("<B1-Motion>",     self._drag_move)

        # Accent line
        tk.Frame(self, bg=ACCENT, height=2).pack(fill="x")

        # Body: sidebar + content
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)

        self._sidebar = tk.Frame(body, bg=SIDEBAR, width=230)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        tk.Frame(body, bg=BORDER, width=1).pack(side="left", fill="y")

        self._content = tk.Frame(body, bg=BG)
        self._content.pack(side="left", fill="both", expand=True)

        self._build_sidebar()

        # Status bar
        bar = tk.Frame(self, bg=SURFACE)
        bar.pack(fill="x", side="bottom")
        self._status = tk.StringVar(value="Ready.")
        self._status_lbl = tk.Label(bar, textvariable=self._status,
                                    font=("Segoe UI", 9), bg=SURFACE, fg=TEXT_DIM)
        self._status_lbl.pack(side="left", padx=18, pady=7)

    def _build_sidebar(self):
        tk.Label(self._sidebar, text="MODULES",
                 font=("Segoe UI Semibold", 7), bg=SIDEBAR, fg=TEXT_DIM).pack(
                 anchor="w", padx=16, pady=(18, 8))

        for name, subtitle, cls in MODULES:
            row = tk.Frame(self._sidebar, bg=SIDEBAR, cursor="hand2")
            row.pack(fill="x", padx=8, pady=2)

            name_lbl = tk.Label(row, text=name,
                                font=("Segoe UI Semibold", 10),
                                bg=SIDEBAR, fg=TEXT, anchor="w")
            name_lbl.pack(fill="x", padx=8, pady=(6, 0))

            sub_lbl = tk.Label(row, text=subtitle,
                               font=("Segoe UI", 8),
                               bg=SIDEBAR, fg=TEXT_DIM, anchor="w")
            sub_lbl.pack(fill="x", padx=8, pady=(0, 6))

            for widget in (row, name_lbl, sub_lbl):
                widget.bind("<Button-1>", lambda e, n=name: self._select(n))

            self._nav_buttons[name] = (row, name_lbl, sub_lbl)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _toggle_minimize(self):
        self.withdraw()
        self.after(200, lambda: self.iconify())

    def _select(self, name):
        # Update sidebar highlight
        for n, (row, nlbl, slbl) in self._nav_buttons.items():
            active = n == name
            bg = ACCENT_DIM if active else SIDEBAR
            row.config(bg=bg)
            nlbl.config(bg=bg)
            slbl.config(bg=bg)

        # Swap content panel
        for widget in self._content.winfo_children():
            widget.destroy()

        cls = next((c for n, _, c in MODULES if n == name), None)
        panel = cls(self._content, status_cb=self._set_status)
        panel.pack(fill="both", expand=True)
        self._active_module = name

    # ── Window controls ───────────────────────────────────────────────────────

    def _drag_start(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _drag_move(self, event):
        x = self.winfo_x() + event.x - self._drag_x
        y = self.winfo_y() + event.y - self._drag_y
        self.geometry(f"+{x}+{y}")

    def _toggle_maximize(self):
        self.state("zoomed" if self.state() != "zoomed" else "normal")

    def _set_status(self, msg, color=TEXT_DIM):
        self._status.set(msg)
        self._status_lbl.config(fg=color)


if __name__ == "__main__":
    app = App()
    app.mainloop()