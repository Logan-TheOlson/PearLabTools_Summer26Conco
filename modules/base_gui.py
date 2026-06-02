"""Base class for all Orange Lab Tools module panels."""
import tkinter as tk
from tkinter import filedialog
import threading

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from modules.drag_file import FileDragWidget


class BaseModule(tk.Frame):
    # Set by main.py before any panels are created (2880x1800 = 1.0)
    SCALE = 1.0
    # On lower-resolution screens, keep fonts the same absolute size as reference.
    # Set by main.py alongside SCALE.
    FONT_SCALE = 1.0

    # ── Palette ───────────────────────────────────────────────────────────────
    BG         = "#13151a"
    SURFACE    = "#1e2028"
    BORDER     = "#383530"
    ACCENT     = "#f5883a"
    ACCENT_DIM = "#6b3c18"
    TEXT       = "#ede0d0"
    TEXT_DIM   = "#8a8478"
    GRID_COLOR = "#272520"
    SUCCESS    = "#5dd6a0"
    ERROR      = "#f07070"

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
        tk.Label(parent, text="INPUT FILE  (.DAT)",
                 font=self._f("Segoe UI Semibold", 8),
                 bg=self.BG, fg=self.TEXT_DIM).grid(
                 row=grid_row, column=0, columnspan=2, sticky="w", pady=(0, self._s(4)))
        file_row = tk.Frame(parent, bg=self.BG)
        file_row.grid(row=grid_row + 1, column=0, columnspan=2,
                      sticky="ew", pady=(0, self._s(12)))
        file_row.columnconfigure(0, weight=1)
        tk.Entry(file_row, textvariable=self._input_path,
                 font=self._f("Consolas", 10),
                 bg=self.SURFACE, fg=self.TEXT, insertbackground=self.TEXT,
                 relief="flat", highlightthickness=1,
                 highlightbackground=self.BORDER,
                 highlightcolor=self.ACCENT).grid(
                 row=0, column=0, sticky="ew",
                 ipady=self._s(8), ipadx=self._s(8))
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

        self._btn_run = tk.Button(parent, text="Convert & Save",
                                  font=self._f("Segoe UI Semibold", 10),
                                  bg=self.ACCENT, fg=self.BG, relief="flat",
                                  activebackground=self.ACCENT_DIM,
                                  activeforeground=self.TEXT,
                                  cursor="hand2", command=self._run,
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
        return tk.Button(parent, text=text, font=self._f("Segoe UI", 10),
                         bg=self.SURFACE, fg=self.TEXT, relief="flat",
                         activebackground=self.BORDER, activeforeground=self.TEXT,
                         highlightthickness=1, highlightbackground=self.BORDER,
                         cursor="hand2", command=cmd,
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

    # ── Shared behaviour ───────────────────────────────────────────────────────

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Select DAT file",
            filetypes=[("DAT files", "*.dat *.DAT"), ("All files", "*.*")])
        if path:
            self._input_path.set(path)
            self._reset()

    def _start_conversion(self, *process_args):
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
