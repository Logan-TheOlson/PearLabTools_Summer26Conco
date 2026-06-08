import tkinter as tk
import ctypes
import ctypes.wintypes
import sys
import os
import platform

from PIL import Image, ImageTk
from tkinterdnd2 import TkinterDnD
from modules.base_gui import BaseModule
from modules.Hysteresis.gui import VSMModule
from modules.LT_1T.gui import LT1TModule
from modules.ZFC.gui import ZFCModule
from modules.RTSIRM.gui import RTSIRMModule

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
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "ConcoPhys.PearLabTools.1")
    except Exception:
        pass

# ── Palette (single source: modules/theme.py) ──────────────────────────────────
from modules.theme import (
    BG, SURFACE, SIDEBAR, BORDER, ACCENT, ACCENT_DIM,
    TEXT, TEXT_DIM, ERROR, ERROR_DIM,
)

MODULES = [
    ("Hysteresis", "DAT → CSV", VSMModule),
    ("Low Temp. 1 Tesla", "DAT → CSV", LT1TModule),
    ("Zero Field Cooling",   "DAT → CSV", ZFCModule),
    ("Room Temp. SIRM",     "DAT → CSV", RTSIRMModule),
]

def _hwnd(widget):
    wid  = widget.winfo_id()
    hwnd = ctypes.windll.user32.GetAncestor(wid, 2)  # GA_ROOT
    return hwnd or ctypes.windll.user32.GetParent(wid)

def _is_win11():
    try:
        return int(platform.version().split(".")[2]) >= 22000
    except Exception:
        return False

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


class App(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.overrideredirect(True)
        self.configure(bg=BG)

        # Scale window to the same proportion of screen real-estate as designed on
        # the reference display (1500x1000 on 2880x1800).
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        scale = sw / 2880
        BaseModule.SCALE = scale
        self._s = lambda n: max(1, round(n * scale))
        # Keep absolute font size constant across resolutions;
        # only boost on screens smaller than the reference 2880x1800.
        font_scale = max(1.0, 1.0 / scale)
        BaseModule.FONT_SCALE = font_scale
        self._f = lambda fam, sz, *ex: (fam, max(6, round(sz * scale * font_scale))) + ex
        w = int(sw * 1500 / 2880)
        h = int(sh * 1000 / 1800)
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self._min_w = int(sw * 1100 / 2880)
        self._min_h = int(sh * 720 / 1800)
        self.minsize(self._min_w, self._min_h)

        # Apply rounded corners (Windows 11 only)
        if sys.platform == "win32" and _is_win11():
            try:
                self.update()
                _apply_rounded_corners(_hwnd(self))
            except Exception:
                pass

        # Load icon — use .ico (png was removed)
        self._icon_img    = None
        self._taskbar_img = None
        try:
            raw = Image.open(resource_path("icon.ico"))
            self._icon_img    = ImageTk.PhotoImage(raw.resize((self._s(24), self._s(24)), Image.LANCZOS))
            self._taskbar_img = ImageTk.PhotoImage(raw.resize((32, 32), Image.LANCZOS))
            self.iconphoto(True, self._taskbar_img)
        except Exception:
            pass
        try:
            self.iconbitmap(resource_path("icon.ico"))
        except Exception:
            pass

        self._drag_x          = 0
        self._drag_y          = 0
        self._restoring       = False
        self._maximized       = False
        self._normal_geometry = None
        self._active_module   = None
        self._nav_buttons   = {}
        self._panels        = {}
        self._build()
        self._select(MODULES[0][0])
        self._register_taskbar()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        # Custom title bar
        titlebar = tk.Frame(self, bg=SURFACE, height=self._s(54))
        titlebar.pack(fill="x")
        titlebar.pack_propagate(False)

        # Icon + title
        if self._icon_img:
            tk.Label(titlebar, image=self._icon_img,
                     bg=SURFACE).pack(side="left", padx=(self._s(14), self._s(6)), pady=self._s(15))
        tk.Label(titlebar, text="Pear Tools",
                 font=self._f("Segoe UI Semibold", 11), bg=SURFACE, fg=TEXT).pack(
                 side="left", pady=0)

        # Window controls — right to left
        btn_close = tk.Button(titlebar, text="✕", font=self._f("Segoe UI", 11),
                              bg=SURFACE, fg=TEXT_DIM, relief="flat",
                              cursor="hand2", bd=0, command=self.destroy,
                              padx=self._s(14), pady=self._s(14))
        btn_close.pack(side="right")
        _add_hover(btn_close, SURFACE, ERROR_DIM, TEXT_DIM, TEXT)

        self._btn_max = tk.Button(titlebar, text="▢", font=self._f("Segoe UI", 10),
                            bg=SURFACE, fg=TEXT_DIM, relief="flat",
                            cursor="hand2", bd=0, command=self._toggle_maximize,
                            padx=self._s(14), pady=self._s(14))
        self._btn_max.pack(side="right")
        _add_hover(self._btn_max, SURFACE, BORDER)

        btn_min = tk.Button(titlebar, text="─", font=self._f("Segoe UI", 11),
                            bg=SURFACE, fg=TEXT_DIM, relief="flat",
                            cursor="hand2", bd=0, command=self._toggle_minimize,
                            padx=self._s(14), pady=self._s(14))
        btn_min.pack(side="right")
        _add_hover(btn_min, SURFACE, BORDER)

        # Drag to move; double-click to maximize / restore
        titlebar.bind("<ButtonPress-1>",   self._drag_start)
        titlebar.bind("<B1-Motion>",       self._drag_move)
        titlebar.bind("<Double-Button-1>", lambda e: self._toggle_maximize())

        # Accent line
        tk.Frame(self, bg=ACCENT, height=max(1, self._s(2))).pack(fill="x")

        # Body: sidebar + content
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)

        self._sidebar = tk.Frame(body, bg=SIDEBAR, width=self._s(230))
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
                                    font=self._f("Segoe UI", 9), bg=SURFACE, fg=TEXT_DIM)
        self._status_lbl.pack(side="left", padx=self._s(18), pady=self._s(7))

        # Resize grip (bottom-right corner)
        self._build_grip()

    def _build_grip(self):
        g  = self._s(26)
        lw = self._s(3)
        self._grip = tk.Canvas(self, width=g, height=g, bg=SURFACE,
                               highlightthickness=0, bd=0, cursor="size_nw_se")
        # Three diagonal lines filling the corner triangle (shortest at the corner)
        for d in (self._s(7), self._s(14), self._s(21)):
            self._grip.create_line(g - d, g, g, g - d, fill=ACCENT, width=lw)
        self._grip.place(relx=1.0, rely=1.0, anchor="se")
        self._grip.bind("<ButtonPress-1>", self._resize_start)
        self._grip.bind("<B1-Motion>",     self._resize_move)

    def _build_sidebar(self):
        tk.Label(self._sidebar, text="MODULES",
                 font=self._f("Segoe UI Semibold", 7), bg=SIDEBAR, fg=TEXT_DIM).pack(
                 anchor="w", padx=self._s(16), pady=(self._s(18), self._s(8)))

        for name, subtitle, cls in MODULES:
            wrapper = tk.Frame(self._sidebar, bg=SIDEBAR)
            wrapper.pack(fill="x", pady=self._s(2))
            wrapper.columnconfigure(1, weight=1)
            wrapper.rowconfigure(0, weight=1)

            # Canvas never collapses — reliable 3px bar, stretches to row height
            line = tk.Canvas(wrapper, width=3, height=1,
                             bg=SIDEBAR, highlightthickness=0)
            line.grid(row=0, column=0, sticky="ns")

            row = tk.Frame(wrapper, bg=SIDEBAR, cursor="hand2")
            row.grid(row=0, column=1, sticky="ew")

            name_lbl = tk.Label(row, text=name,
                                font=self._f("Segoe UI Semibold", 10),
                                bg=SIDEBAR, fg=TEXT, anchor="w")
            name_lbl.pack(fill="x", padx=self._s(8), pady=(self._s(6), 0))

            sub_lbl = tk.Label(row, text=subtitle,
                               font=self._f("Segoe UI", 8),
                               bg=SIDEBAR, fg=TEXT_DIM, anchor="w")
            sub_lbl.pack(fill="x", padx=self._s(8), pady=(0, self._s(6)))

            for widget in (wrapper, row, name_lbl, sub_lbl):
                widget.bind("<Button-1>", lambda e, n=name: self._select(n))
                widget.bind("<Enter>",    lambda e, n=name: self._nav_enter(n))
                widget.bind("<Leave>",    lambda e, n=name: self._nav_leave(n))

            self._nav_buttons[name] = (line, row, name_lbl, sub_lbl)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _set_window_icon(self):
        if sys.platform != "win32":
            return
        try:
            ico = resource_path("icon.ico")
            if not os.path.exists(ico):
                return
            LR_LOADFROMFILE = 0x0010
            IMAGE_ICON      = 1
            WM_SETICON      = 0x0080
            ICON_SMALL, ICON_BIG = 0, 1
            GCLP_HICON, GCLP_HICONSM = -14, -34
            load   = ctypes.windll.user32.LoadImageW
            send   = ctypes.windll.user32.SendMessageW
            setcls = ctypes.windll.user32.SetClassLongPtrW
            hsmall = load(None, ico, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
            hbig   = load(None, ico, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
            if not hsmall or not hbig:
                return
            wid  = self.winfo_id()
            root = _hwnd(self)
            for hwnd in {wid, root}:
                if hwnd:
                    send(hwnd, WM_SETICON, ICON_SMALL, hsmall)
                    send(hwnd, WM_SETICON, ICON_BIG,   hbig)
            if root:
                setcls(root, GCLP_HICONSM, hsmall)
                setcls(root, GCLP_HICON,   hbig)
        except Exception:
            pass

    def _register_taskbar(self):
        if sys.platform != "win32":
            return
        try:
            GWL_EXSTYLE      = -20
            WS_EX_APPWINDOW  = 0x00040000
            WS_EX_TOOLWINDOW = 0x00000080
            hwnd  = _hwnd(self)
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            self.withdraw()
            self.after(10, self._taskbar_show)
        except Exception:
            pass

    def _taskbar_show(self):
        self.deiconify()
        self.after(100, self._set_window_icon)

    def _toggle_minimize(self):
        self._restoring = False
        self.withdraw()                          # hide first to avoid white flash
        self.overrideredirect(False)             # required for iconify to work
        self.after(50, self._do_iconify)

    def _do_iconify(self):
        try:
            self.iconbitmap(resource_path("icon.ico"))
        except Exception:
            pass
        self.iconify()
        self._restoring = True                   # only accept <Map> after this point
        self.bind("<Map>", self._on_restore)

    def _on_restore(self, event):
        if not self._restoring:
            return
        self.unbind("<Map>")
        self._restoring = False
        self.overrideredirect(True)
        self.deiconify()
        if sys.platform == "win32":
            self.after(50, self._set_window_icon)
            if _is_win11():
                try:
                    self.update()
                    _apply_rounded_corners(_hwnd(self))
                except Exception:
                    pass

    def _nav_enter(self, name):
        if name == self._active_module:
            return
        line, row, nlbl, slbl = self._nav_buttons[name]
        for w in (row, nlbl, slbl):
            w.config(bg="#222220")

    def _nav_leave(self, name):
        if name == self._active_module:
            return
        line, row, nlbl, slbl = self._nav_buttons[name]
        for w in (row, nlbl, slbl):
            w.config(bg=SIDEBAR)

    def _select(self, name):
        for n, (line, row, nlbl, slbl) in self._nav_buttons.items():
            active = n == name
            line.config(bg=ACCENT if active else SIDEBAR)
            for w in (row, nlbl, slbl):
                w.config(bg=SIDEBAR)

        # Create the panel the first time it's selected, then just show/hide
        if name not in self._panels:
            cls = next((c for n, _, c in MODULES if n == name), None)
            self._panels[name] = cls(self._content, status_cb=self._set_status)

        for n, panel in self._panels.items():
            if n == name:
                panel.pack(fill="both", expand=True)
            else:
                panel.pack_forget()

        self._active_module = name

    # ── Window controls ───────────────────────────────────────────────────────

    def _drag_start(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _drag_move(self, event):
        x = self.winfo_x() + event.x - self._drag_x
        y = self.winfo_y() + event.y - self._drag_y
        self.geometry(f"+{x}+{y}")

    def _resize_start(self, event):
        if self._maximized or self.state() == "zoomed":
            if self.state() == "zoomed":
                self.state("normal")
            self._maximized = False
            self._btn_max.config(text="▢")
            self.update_idletasks()
        self._resize_x = event.x_root
        self._resize_y = event.y_root
        self._resize_w = self.winfo_width()
        self._resize_h = self.winfo_height()

    def _resize_move(self, event):
        new_w = max(self._min_w, self._resize_w + event.x_root - self._resize_x)
        new_h = max(self._min_h, self._resize_h + event.y_root - self._resize_y)
        self.geometry(f"{new_w}x{new_h}")

    def _work_area(self):
        """Work area (screen minus taskbar) of the monitor the window is on."""
        if sys.platform != "win32":
            return None
        try:
            user32 = ctypes.windll.user32
            MONITOR_DEFAULTTONEAREST = 2
            monitor = user32.MonitorFromWindow(_hwnd(self), MONITOR_DEFAULTTONEAREST)

            class MONITORINFO(ctypes.Structure):
                _fields_ = [("cbSize",    ctypes.wintypes.DWORD),
                            ("rcMonitor", ctypes.wintypes.RECT),
                            ("rcWork",    ctypes.wintypes.RECT),
                            ("dwFlags",   ctypes.wintypes.DWORD)]

            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if user32.GetMonitorInfoW(monitor, ctypes.byref(mi)):
                r = mi.rcWork
                return (r.left, r.top, r.right - r.left, r.bottom - r.top)
        except Exception:
            pass
        return None

    def _toggle_maximize(self):
        # Restore
        if self._maximized:
            if self._normal_geometry:
                self.geometry(self._normal_geometry)
            self._maximized = False
            self._btn_max.config(text="▢")
            return
        # Maximize to the work area so the taskbar stays visible
        area = self._work_area()
        if area:
            self._normal_geometry = self.geometry()
            x, y, w, h = area
            self.geometry(f"{w}x{h}+{x}+{y}")
            self._maximized = True
            self._btn_max.config(text="❐")
        else:
            self.state("zoomed" if self.state() != "zoomed" else "normal")
            self._btn_max.config(text="❐" if self.state() == "zoomed" else "▢")

    def _set_status(self, msg, color=TEXT_DIM):
        self._status.set(msg)
        self._status_lbl.config(fg=color)


if __name__ == "__main__":
    app = App()
    app.mainloop()