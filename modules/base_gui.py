"""Base class for all Pear Tools module panels."""
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog
import threading

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.lines       as mpl_lines
import matplotlib.collections as mpl_coll
import numpy as np

from modules.drag_file import FileDragWidget
from modules import theme
from tkinterdnd2 import DND_FILES


class RoundedButton(tk.Canvas):
    """Flat button with a small rounded-rectangle background drawn on a Canvas.

    Supports .config(state=, text=, bg=) and .cget("state"/"text") so it
    works as a drop-in replacement for tk.Button across the app.
    """

    def __init__(self, parent, text, command,
                 radius=5,
                 bg=theme.SURFACE, hover_bg=theme.BORDER,
                 fg=theme.TEXT,
                 font=("Segoe UI", 10),
                 padx=14, pady=7, **kw):
        self._text_str = text
        self._command  = command
        self._radius   = max(1, radius)
        self._bg       = bg
        self._hover_bg = hover_bg
        self._fg       = fg
        self._padx     = padx
        self._pady     = pady
        self._font     = font
        self._disabled = False

        self._px_w, self._px_h = self._measure(text)

        try:
            pbg = parent.cget("bg")
        except Exception:
            pbg = theme.BG

        kw.setdefault("cursor", "hand2")
        super().__init__(parent, width=self._px_w, height=self._px_h,
                        bg=pbg, highlightthickness=0, bd=0, **kw)

        self._draw(self._bg)
        self.bind("<Enter>",    lambda e: self._on_enter())
        self.bind("<Leave>",    lambda e: self._on_leave())
        self.bind("<Button-1>", lambda e: self._on_click())

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _measure(self, text):
        """Pixel (width, height) for *text* rendered in self._font."""
        fam  = self._font[0] if self._font else "Segoe UI"
        size = abs(self._font[1]) if len(self._font) > 1 else 10
        wt   = (self._font[2]
                if len(self._font) > 2 and self._font[2] in ("bold", "normal")
                else "normal")
        try:
            f  = tkfont.Font(family=fam, size=size, weight=wt)
            tw = f.measure(text)
            th = f.metrics("linespace")
        except Exception:
            tw, th = max(40, len(text) * 7), 14
        return tw + self._padx * 2, th + self._pady * 2

    def _draw(self, bg):
        self.delete("all")
        r = self._radius
        w, h = self._px_w, self._px_h
        x1, y1, x2, y2 = 0, 0, w - 1, h - 1
        # Two overlapping filled rects + four filled corner arcs
        self.create_rectangle(x1+r, y1,   x2-r, y2,   fill=bg, outline=bg)
        self.create_rectangle(x1,   y1+r, x2,   y2-r, fill=bg, outline=bg)
        self.create_arc(x1,     y1,     x1+2*r, y1+2*r, start=90,  extent=90, fill=bg, outline=bg)
        self.create_arc(x2-2*r, y1,     x2,     y1+2*r, start=0,   extent=90, fill=bg, outline=bg)
        self.create_arc(x1,     y2-2*r, x1+2*r, y2,     start=180, extent=90, fill=bg, outline=bg)
        self.create_arc(x2-2*r, y2-2*r, x2,     y2,     start=270, extent=90, fill=bg, outline=bg)
        fg = theme.TEXT_DIM if self._disabled else self._fg
        self.create_text(w // 2, h // 2, text=self._text_str, fill=fg, font=self._font)

    # ── State events ──────────────────────────────────────────────────────────

    def _on_enter(self):
        if not self._disabled:
            self._draw(self._hover_bg)

    def _on_leave(self):
        if not self._disabled:
            self._draw(self._bg)

    def _on_click(self):
        if not self._disabled and self._command:
            self._command()

    # ── Public API (mirrors tk.Button) ────────────────────────────────────────

    def config(self, **kw):
        state = kw.pop("state", None)
        text  = kw.pop("text",  None)
        bg    = kw.pop("bg",    None)
        dirty = False
        if state is not None:
            was = self._disabled
            self._disabled = (state == "disabled")
            dirty = dirty or (was != self._disabled)
        if text is not None and text != self._text_str:
            self._text_str = text
            self._px_w, self._px_h = self._measure(text)
            super().config(width=self._px_w, height=self._px_h)
            dirty = True
        if bg is not None:
            self._bg = bg
            dirty = True
        if kw:
            super().config(**kw)
        if dirty:
            self._draw(self._bg)

    configure = config

    def cget(self, key):
        if key == "text":  return self._text_str
        if key == "state": return "disabled" if self._disabled else "normal"
        if key == "bg":    return self._bg
        return super().cget(key)


class BaseModule(tk.Frame):
    # Set by main.py before any panels are created (2880x1800 = 1.0)
    SCALE = 1.0
    # On lower-resolution screens, keep fonts the same absolute size as reference.
    # Set by main.py alongside SCALE.
    FONT_SCALE = 1.0

    # ── Palette (single source: modules/theme.py) ──────────────────────────────
    BG         = theme.BG
    SURFACE    = theme.SURFACE
    BORDER     = theme.BORDER
    ACCENT     = theme.ACCENT
    ACCENT_DIM = theme.ACCENT_DIM
    TEXT       = theme.TEXT
    TEXT_DIM   = theme.TEXT_DIM
    GRID_COLOR = theme.GRID_COLOR
    SUCCESS    = theme.SUCCESS
    ERROR      = theme.ERROR

    def __init__(self, parent, status_cb=None, **kwargs):
        super().__init__(parent, bg=self.BG, **kwargs)
        self._status_cb  = status_cb or (lambda msg, color=None: None)
        self._input_path = tk.StringVar()
        self._subplot_kw = {}

    # ── Scale helpers ──────────────────────────────────────────────────────────

    def _s(self, n):
        """Scale a pixel / point value."""
        return max(1, round(n * self.SCALE))

    def _f(self, family, size, *extra):
        """Return a scaled tkinter font tuple."""
        return (family, max(6, round(size * self.SCALE * self.FONT_SCALE))) + extra

    def _mpl(self, size):
        """Scale a matplotlib font size (points)."""
        return max(5, round(size * self.SCALE * self.FONT_SCALE))

    # ── Shared widget builders ─────────────────────────────────────────────────

    def _build_result_strip(self):
        tk.Frame(self, bg=self.BORDER, height=1).pack(fill="x", side="bottom")
        bar = tk.Frame(self, bg=self.SURFACE)
        bar.pack(fill="x", side="bottom")
        self._result_var = tk.StringVar(value="No file loaded.")
        self._result_lbl = tk.Label(bar, textvariable=self._result_var,
                                    font=self._f("Segoe UI", 9),
                                    bg=self.SURFACE, fg=self.TEXT_DIM,
                                    anchor="w", justify="left")
        self._result_lbl.pack(side="left", padx=self._s(18), pady=self._s(7))
        self._drag_chip = FileDragWidget(bar, path="")
        self._drag_chip.pack(side="right", padx=self._s(12), pady=self._s(4))
        self._drag_chip.pack_forget()

    def _build_file_row(self, parent, grid_row=0):
        header = tk.Frame(parent, bg=self.BG)
        header.grid(row=grid_row, column=0, columnspan=2, sticky="w",
                    pady=(0, self._s(4)))
        tk.Label(header, text="INPUT FILE  (.DAT)",
                 font=self._f("Segoe UI Semibold", 8),
                 bg=self.BG, fg=self.TEXT_DIM).pack(side="left")
        tk.Label(header, text="·  Browse or Drag 'n Drop File Here",
                 font=self._f("Segoe UI Semibold", 8),
                 bg=self.BG, fg=self.TEXT_DIM).pack(side="left", padx=(self._s(8), 0))
        file_row = tk.Frame(parent, bg=self.BG)
        file_row.grid(row=grid_row + 1, column=0, columnspan=2,
                      sticky="ew", pady=(0, self._s(12)))
        file_row.columnconfigure(0, weight=1)
        self._input_entry = tk.Entry(file_row, textvariable=self._input_path,
                 font=self._f("Consolas", 10),
                 bg=self.SURFACE, fg=self.TEXT, insertbackground=self.TEXT,
                 relief="flat", highlightthickness=1,
                 highlightbackground=self.BORDER,
                 highlightcolor=self.ACCENT)
        self._input_entry.grid(row=0, column=0, sticky="ew",
                               ipady=self._s(8), ipadx=self._s(8))
        self._register_input_dnd(self._input_entry)
        self._pill_btn(file_row, "Browse", self._browse).grid(
                 row=0, column=1, padx=(self._s(8), 0))

    def _build_action_row(self, parent, grid_row=2):
        """SAMPLE MASS card (left) + Convert & Save button (right) on one row."""
        self._readout_mass = tk.StringVar(value="—")
        card = tk.Frame(parent, bg=self.SURFACE,
                        highlightthickness=1, highlightbackground=self.BORDER)
        card.grid(row=grid_row, column=0, sticky="w")
        p = self._s(10)
        tk.Label(card, text="SAMPLE MASS", font=self._f("Segoe UI Semibold", 7),
                 bg=self.SURFACE, fg=self.TEXT_DIM).pack(
                 anchor="w", padx=p, pady=(self._s(8), self._s(4)))
        tk.Label(card, textvariable=self._readout_mass,
                 font=self._f("Consolas", 13),
                 bg=self.SURFACE, fg=self.TEXT).pack(anchor="w", padx=p)
        tk.Label(card, text="mg", font=self._f("Segoe UI", 7),
                 bg=self.SURFACE, fg=self.TEXT_DIM).pack(
                 anchor="w", padx=p, pady=(self._s(2), self._s(8)))

        self._btn_run = RoundedButton(parent, text="Convert & Save",
                                     command=self._run,
                                     radius=5,
                                     bg=self.ACCENT, hover_bg=self.ACCENT_DIM,
                                     fg=self.BG,
                                     font=self._f("Segoe UI Semibold", 10),
                                     padx=self._s(20), pady=self._s(8))
        self._btn_run.grid(row=grid_row, column=0, sticky="e")

    def _make_canvas(self, parent):
        fig = Figure(figsize=(8, 4), dpi=96, facecolor=self.BG, edgecolor=self.BG)
        fig.patch.set_linewidth(0)
        canvas = FigureCanvasTkAgg(fig, master=parent)
        widget = canvas.get_tk_widget()
        widget.config(highlightthickness=0, bd=0, bg=self.BG)
        widget.pack(fill="both", expand=True)
        return fig, canvas

    def _pill_btn(self, parent, text, cmd):
        return RoundedButton(parent, text=text, command=cmd,
                             radius=5,
                             bg=self.SURFACE, hover_bg=self.BORDER,
                             fg=self.TEXT,
                             font=self._f("Segoe UI", 10),
                             padx=self._s(14), pady=self._s(7))

    def _style_ax(self, ax, title="", xlabel="", ylabel=""):
        ax.set_facecolor(self.SURFACE)
        ax.tick_params(colors=self.TEXT_DIM, labelsize=self._mpl(7.5))
        ax.xaxis.label.set_color(self.TEXT_DIM)
        ax.yaxis.label.set_color(self.TEXT_DIM)
        for spine in ax.spines.values():
            spine.set_edgecolor(self.BORDER)
        ax.set_xlabel(xlabel, fontsize=self._mpl(8))
        ax.set_ylabel(ylabel, fontsize=self._mpl(8))
        ax.set_title(title, color=self.TEXT_DIM, fontsize=self._mpl(8.5), pad=self._s(6))
        ax.grid(True, color=self.GRID_COLOR, linewidth=0.6, linestyle="-")
        ax.set_axisbelow(True)

    def _on_resize(self, event):
        w = max(event.width,  200) / 96
        h = max(event.height, 200) / 96
        self._fig.set_size_inches(w, h)
        self._fig.subplots_adjust(**self._subplot_kw)
        self._canvas.draw_idle()

    # ── Box zoom: drag a rectangle to zoom in, double-click to reset ─────────────

    def _enable_zoom(self, *axes):
        """Drag a box on any of ``axes`` to zoom into it; double-click to reset."""
        self._zoom_axes  = list(axes)
        self._zoom_start = None      # (ax, x0, y0, px0, py0) while dragging
        self._zoom_rect  = None      # rubber-band Rectangle
        self._zoom_bg    = None      # cached background for blitting
        self._zoom_on    = False     # True once the user has zoomed in
        self._zoom_home  = {}        # id(ax) -> (xlim, ylim) of the full view
        self._canvas.get_tk_widget().config(cursor="crosshair")
        self._canvas.mpl_connect("draw_event",           self._zoom_cache_home)
        self._canvas.mpl_connect("button_press_event",   self._zoom_press)
        self._canvas.mpl_connect("motion_notify_event",  self._zoom_motion)
        self._canvas.mpl_connect("button_release_event", self._zoom_release)
        # Hover tooltip (shares axes list with zoom)
        self._hover_ann     = None
        self._hover_cache   = []          # rebuilt on every draw_event
        self._hover_last_px = (-999., -999.)   # throttle: last processed pos
        self._canvas.mpl_connect("motion_notify_event", self._hover_motion)
        self._canvas.mpl_connect("axes_leave_event",    self._hover_clear)
        self._canvas.mpl_connect("draw_event",          self._hover_rebuild_cache)

    def _zoom_cache_home(self, _event):
        # Remember the full (un-zoomed) view so double-click can restore it exactly.
        if self._zoom_on or self._zoom_start is not None:
            return
        for ax in self._zoom_axes:
            self._zoom_home[id(ax)] = (ax.get_xlim(), ax.get_ylim())

    def _cancel_zoom(self):
        if self._zoom_rect is not None:
            try:
                self._zoom_rect.remove()
            except Exception:
                pass
        self._zoom_rect = self._zoom_bg = self._zoom_start = None

    def _zoom_clamped_xy(self, ax, event):
        """Event position in data coords, clamped to the axes (works past the edges)."""
        x, y = ax.transData.inverted().transform((event.x, event.y))
        lo_x, hi_x = sorted(ax.get_xlim())
        lo_y, hi_y = sorted(ax.get_ylim())
        return min(max(x, lo_x), hi_x), min(max(y, lo_y), hi_y)

    def _zoom_press(self, event):
        if event.button != 1 or event.inaxes not in self._zoom_axes:
            return
        if event.dblclick:                       # reset to the cached full view
            self._cancel_zoom()
            self._zoom_on = False
            for ax in self._zoom_axes:
                home = self._zoom_home.get(id(ax))
                if home:
                    ax.set_xlim(home[0])
                    ax.set_ylim(home[1])
            self._canvas.draw_idle()
            return
        ax = event.inaxes
        self._hover_clear()
        self._zoom_start = (ax, event.xdata, event.ydata, event.x, event.y)
        self._zoom_rect = Rectangle((event.xdata, event.ydata), 0, 0,
                                    facecolor=self.ACCENT, edgecolor=self.ACCENT,
                                    alpha=0.25, linewidth=1, animated=True, zorder=20)
        ax.add_patch(self._zoom_rect)
        self._canvas.draw()                      # animated rect is skipped -> clean bg
        self._zoom_bg = self._canvas.copy_from_bbox(ax.bbox)

    def _zoom_motion(self, event):
        if self._zoom_start is None or event.x is None or event.y is None:
            return
        ax, x0, y0, _, _ = self._zoom_start
        x1, y1 = self._zoom_clamped_xy(ax, event)
        self._zoom_rect.set_bounds(x0, y0, x1 - x0, y1 - y0)
        self._canvas.restore_region(self._zoom_bg)
        ax.draw_artist(self._zoom_rect)
        self._canvas.blit(ax.bbox)

    def _zoom_release(self, event):
        if self._zoom_start is None:
            return
        ax, x0, y0, px0, py0 = self._zoom_start
        ok = (event.x is not None and event.y is not None
              and abs(event.x - px0) > 6 and abs(event.y - py0) > 6)
        if ok:
            x1, y1 = self._zoom_clamped_xy(ax, event)
        self._cancel_zoom()
        if ok:
            self._zoom_on = True
            ax.set_xlim(min(x0, x1), max(x0, x1))
            ax.set_ylim(min(y0, y1), max(y0, y1))
        self._canvas.draw_idle()

    # ── Hover tooltip ──────────────────────────────────────────────────────────

    def _hover_rebuild_cache(self, _event=None):
        """Pre-compute pixel coords for all data artists after every draw.

        Called on draw_event so the cache stays valid after zoom / resize /
        new data — and _hover_motion never has to touch matplotlib internals.
        """
        cache = []
        for ax in self._zoom_axes:
            for artist in ax.get_children():
                pts_data, lbl = None, ""

                if isinstance(artist, mpl_lines.Line2D):
                    xd = np.asarray(artist.get_xdata(orig=False))
                    yd = np.asarray(artist.get_ydata(orig=False))
                    if xd.size < 2:
                        continue
                    if "Blend" in type(artist.get_transform()).__name__:
                        continue   # axhline / axvline
                    pts_data = np.column_stack([xd, yd])
                    lbl = artist.get_label()

                elif isinstance(artist, mpl_coll.PathCollection):
                    offs = artist.get_offsets()
                    if len(offs) == 0:
                        continue
                    pts_data = np.asarray(offs)
                    lbl = artist.get_label()

                if pts_data is None or len(pts_data) == 0:
                    continue
                try:
                    pts_px = ax.transData.transform(pts_data)
                except Exception:
                    continue

                cache.append((ax, pts_px, pts_data,
                              "" if lbl.startswith("_") else lbl))
        self._hover_cache = cache

    def _hover_motion(self, event):
        """O(N) numpy search on pre-built pixel cache — no matplotlib calls."""
        if self._zoom_start is not None or event.x is None:
            return
        if event.inaxes not in self._zoom_axes:
            self._hover_clear()
            return

        # Throttle: skip if the mouse hasn't moved ≥4 px
        lx, ly = self._hover_last_px
        if abs(event.x - lx) < 4 and abs(event.y - ly) < 4:
            return
        self._hover_last_px = (event.x, event.y)

        ax = event.inaxes
        best_dist, best_xy, best_lbl = float("inf"), None, ""

        for (cart, pts_px, pts_data, lbl) in self._hover_cache:
            if cart is not ax:
                continue
            dists = np.hypot(pts_px[:, 0] - event.x, pts_px[:, 1] - event.y)
            i = int(np.argmin(dists))
            d = float(dists[i])
            if d < best_dist:
                best_dist = d
                best_xy   = (float(pts_data[i, 0]), float(pts_data[i, 1]))
                best_lbl  = lbl

        if best_dist <= 18 and best_xy is not None:
            self._hover_show(ax, best_xy, best_lbl, event)
        else:
            self._hover_clear()

    def _hover_show(self, ax, xy, label, event=None):
        self._hover_clear()
        x, y = xy

        def fmt(v):
            if v == 0:
                return "0"
            if abs(v) >= 1e4 or (abs(v) < 1e-3):
                return f"{v:.3e}"
            return f"{v:.4g}"

        xl = ax.get_xlabel().split("(")[0].strip() or "x"
        yl = ax.get_ylabel().split("(")[0].strip() or "y"
        body = f"{xl}: {fmt(x)}\n{yl}: {fmt(y)}"
        if label:
            body = f"{label}\n{body}"

        # Flip tooltip to the left when near the right edge of the figure
        near_right = (event is not None and
                      event.x > self._fig.get_figwidth() * self._fig.dpi * 0.65)
        xytext = (-10, 10) if near_right else (10, 10)

        self._hover_ann = ax.annotate(
            body, xy=xy, xytext=xytext, textcoords="offset points",
            fontsize=self._mpl(7.5), color=self.TEXT,
            ha="right" if near_right else "left",
            bbox=dict(boxstyle="round,pad=0.35",
                      facecolor=self.SURFACE, edgecolor=self.BORDER,
                      linewidth=0.8, alpha=0.93),
            zorder=30)
        self._canvas.draw_idle()

    def _hover_clear(self, event=None):
        self._hover_last_px = (-999., -999.)   # reset throttle so next entry fires immediately
        if self._hover_ann is not None:
            try:
                self._hover_ann.remove()
            except Exception:
                pass
            self._hover_ann = None
            self._canvas.draw_idle()

    # ── Shared behaviour ───────────────────────────────────────────────────────

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Select DAT file",
            filetypes=[("DAT files", "*.dat *.DAT"), ("All files", "*.*")])
        if path:
            self._load_input(path)

    def _load_input(self, path):
        """Set the input file and reset the preview. Browse and drop both route here."""
        self._zoom_on = False
        self._input_path.set(path)
        self._reset()

    # ── Drag-and-drop input ────────────────────────────────────────────────────
    def _register_input_dnd(self, widget):
        try:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<DropEnter>>", self._on_input_drag_enter)
            widget.dnd_bind("<<DropLeave>>", self._on_input_drag_leave)
            widget.dnd_bind("<<Drop>>",      self._on_input_drop)
        except Exception:
            pass

    def _on_input_drag_enter(self, event):
        self._input_entry.config(highlightbackground=self.ACCENT)
        return event.action

    def _on_input_drag_leave(self, event):
        self._input_entry.config(highlightbackground=self.BORDER)
        return event.action

    def _on_input_drop(self, event):
        self._input_entry.config(highlightbackground=self.BORDER)
        try:
            paths = self.tk.splitlist(event.data)
        except Exception:
            paths = [event.data]
        if paths:
            self._load_input(paths[0])
        return event.action

    def _start_conversion(self, *process_args):
        self._zoom_on = False
        self._btn_run.config(state="disabled", text="Converting…")
        self._status_cb("Processing…", self.ACCENT)

        def worker():
            try:
                result = self._process(*process_args)
                self.after(0, lambda: self._done(*result))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: self._error(err))

        threading.Thread(target=worker, daemon=True).start()

    def _finish(self, rows, csv_path, output_dir):
        self._btn_run.config(state="normal", text="Convert & Save")
        self._status_cb(f"✓  Done  ·  {output_dir}", self.SUCCESS)
        self._drag_chip.set_path(csv_path)
        self._drag_chip.pack(side="right", padx=self._s(12), pady=self._s(4))
        self._result_var.set(f"✓  {rows} rows saved  ·  {csv_path}")
        self._result_lbl.config(fg=self.SUCCESS)

    def _reset_common(self):
        self._drag_chip.pack_forget()
        self._result_var.set("No file loaded.")
        self._result_lbl.config(fg=self.TEXT_DIM)

    def _error(self, msg):
        self._btn_run.config(state="normal", text="Convert & Save")
        self._status_cb(f"✗  Error: {msg}", self.ERROR)
        self._drag_chip.pack_forget()
        self._result_var.set(f"✗  {msg}")
        self._result_lbl.config(fg=self.ERROR)

    # ── Default implementations (override in subclasses as needed) ────────────

    def _build_controls(self):
        strip = tk.Frame(self, bg=self.BG)
        strip.pack(pady=(self._s(20), self._s(12)), padx=self._s(40), fill="x")
        strip.columnconfigure(0, weight=1)
        self._build_file_row(strip, grid_row=0)
        self._build_action_row(strip, grid_row=2)

    def _run(self):
        inp = self._input_path.get().strip()
        if not inp:
            self._result_var.set("✗  Please select an input file.")
            self._result_lbl.config(fg=self.ERROR)
            return
        self._start_conversion(inp)

    def _reset(self):
        self._reset_common()
        self._readout_mass.set("—")
        self._ax.clear()
        self._refresh_ax()
        self._canvas.draw()

    # ── Abstract interface ─────────────────────────────────────────────────────

    def _refresh_ax(self): pass
    def _process(self, *a): raise NotImplementedError
    def _done(self, *a):    raise NotImplementedError
