# Base class for all Orange Lab Tools module panels
import tkinter as tk
from tkinter import filedialog
import threading

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from modules.drag_file import FileDragWidget


class BaseModule(tk.Frame):
    # ── Shared palette ────────────────────────────────────────────────────────
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
    FONT_MONO  = ("Consolas", 10)
    FONT_UI    = ("Segoe UI", 10)

    def __init__(self, parent, status_cb=None, **kwargs):
        super().__init__(parent, bg=self.BG, **kwargs)
        self._status_cb  = status_cb or (lambda msg, color=None: None)
        self._input_path = tk.StringVar()
        self._subplot_kw = {}

    # ── Shared widget builders ─────────────────────────────────────────────────

    def _build_result_strip(self):
        # Status bar pinned to bottom with drag-to-export chip on the right
        tk.Frame(self, bg=self.BORDER, height=1).pack(fill="x", side="bottom")
        bar = tk.Frame(self, bg=self.SURFACE)
        bar.pack(fill="x", side="bottom")
        self._result_var = tk.StringVar(value="No file loaded.")
        self._result_lbl = tk.Label(bar, textvariable=self._result_var,
                                    font=("Segoe UI", 9), bg=self.SURFACE, fg=self.TEXT_DIM,
                                    anchor="w", justify="left")
        self._result_lbl.pack(side="left", padx=18, pady=7)
        self._drag_chip = FileDragWidget(bar, path="")
        self._drag_chip.pack(side="right", padx=12, pady=4)
        self._drag_chip.pack_forget()

    def _build_file_row(self, parent, grid_row=0):
        # INPUT FILE label + path entry + Browse button, placed into a grid parent
        tk.Label(parent, text="INPUT FILE  (.DAT)", font=("Segoe UI Semibold", 8),
                 bg=self.BG, fg=self.TEXT_DIM).grid(
                 row=grid_row, column=0, columnspan=2, sticky="w", pady=(0, 4))
        file_row = tk.Frame(parent, bg=self.BG)
        file_row.grid(row=grid_row + 1, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        file_row.columnconfigure(0, weight=1)
        tk.Entry(file_row, textvariable=self._input_path, font=self.FONT_MONO,
                 bg=self.SURFACE, fg=self.TEXT, insertbackground=self.TEXT, relief="flat",
                 highlightthickness=1, highlightbackground=self.BORDER,
                 highlightcolor=self.ACCENT).grid(row=0, column=0, sticky="ew", ipady=8, ipadx=8)
        self._pill_btn(file_row, "Browse", self._browse).grid(row=0, column=1, padx=(8, 0))

    def _build_action_row(self, parent, grid_row=2):
        """SAMPLE MASS card on left + Convert & Save button on right, same grid row."""
        self._readout_mass = tk.StringVar(value="\u2014")
        card = tk.Frame(parent, bg=self.SURFACE,
                        highlightthickness=1, highlightbackground=self.BORDER)
        card.grid(row=grid_row, column=0, sticky="w")
        tk.Label(card, text="SAMPLE MASS", font=("Segoe UI Semibold", 7),
                 bg=self.SURFACE, fg=self.TEXT_DIM).pack(anchor="w", padx=10, pady=(8, 4))
        tk.Label(card, textvariable=self._readout_mass, font=("Consolas", 13),
                 bg=self.SURFACE, fg=self.TEXT).pack(anchor="w", padx=10)
        tk.Label(card, text="mg", font=("Segoe UI", 7),
                 bg=self.SURFACE, fg=self.TEXT_DIM).pack(anchor="w", padx=10, pady=(2, 8))

        self._btn_run = tk.Button(parent, text="Convert & Save",
                                  font=("Segoe UI Semibold", 10),
                                  bg=self.ACCENT, fg=self.BG, relief="flat",
                                  activebackground=self.ACCENT_DIM, activeforeground=self.TEXT,
                                  cursor="hand2", command=self._run, padx=20, pady=8)
        self._btn_run.grid(row=grid_row, column=0, sticky="e")

    def _make_canvas(self, parent):
        # Create a Figure and embed a TkAgg canvas in parent. Returns (fig, canvas)
        fig = Figure(figsize=(8, 4), dpi=96, facecolor=self.BG, edgecolor=self.BG)
        fig.patch.set_linewidth(0)
        canvas = FigureCanvasTkAgg(fig, master=parent)
        widget = canvas.get_tk_widget()
        widget.config(highlightthickness=0, bd=0, bg=self.BG)
        widget.pack(fill="both", expand=True)
        return fig, canvas

    def _pill_btn(self, parent, text, cmd):
        return tk.Button(parent, text=text, font=self.FONT_UI,
                         bg=self.SURFACE, fg=self.TEXT, relief="flat",
                         activebackground=self.BORDER, activeforeground=self.TEXT,
                         highlightthickness=1, highlightbackground=self.BORDER,
                         cursor="hand2", command=cmd, padx=14, pady=7)

    def _style_ax(self, ax, title="", xlabel="", ylabel=""):
        ax.set_facecolor(self.SURFACE)
        ax.tick_params(colors=self.TEXT_DIM, labelsize=7.5)
        ax.xaxis.label.set_color(self.TEXT_DIM)
        ax.yaxis.label.set_color(self.TEXT_DIM)
        for spine in ax.spines.values():
            spine.set_edgecolor(self.BORDER)
        ax.set_xlabel(xlabel, fontsize=8)
        ax.set_ylabel(ylabel, fontsize=8)
        ax.set_title(title, color=self.TEXT_DIM, fontsize=8.5, pad=6)
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
        # Disable the run button, spin up the worker thread, re-enable on finish
        self._btn_run.config(state="disabled", text="Converting\u2026")
        self._status_cb("Processing\u2026", self.ACCENT)

        def worker():
            try:
                result = self._process(*process_args)
                self.after(0, lambda: self._done(*result))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: self._error(err))

        threading.Thread(target=worker, daemon=True).start()

    def _finish(self, rows, csv_path, output_dir):
        # Common UI update after a successful conversion. Call from subclass _done()
        self._btn_run.config(state="normal", text="Convert & Save")
        self._status_cb(f"\u2713  Done  \u00b7  {output_dir}", self.SUCCESS)
        self._drag_chip.set_path(csv_path)
        self._drag_chip.pack(side="right", padx=12, pady=4)
        self._result_var.set(f"\u2713  {rows} rows saved  \u00b7  {csv_path}")
        self._result_lbl.config(fg=self.SUCCESS)

    def _reset_common(self):
        # Reset the status strip. Call at the top of each subclass _reset()
        self._drag_chip.pack_forget()
        self._result_var.set("No file loaded.")
        self._result_lbl.config(fg=self.TEXT_DIM)

    def _error(self, msg):
        self._btn_run.config(state="normal", text="Convert & Save")
        self._status_cb(f"\u2717  Error: {msg}", self.ERROR)
        self._drag_chip.pack_forget()
        self._result_var.set(f"\u2717  {msg}")
        self._result_lbl.config(fg=self.ERROR)
