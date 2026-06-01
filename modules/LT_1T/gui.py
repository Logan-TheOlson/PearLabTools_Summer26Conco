import tkinter as tk
from tkinter import filedialog
import threading

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from .processing import process_dat

# ── Palette ───────────────────────────────────────────────────────────────────
BG         = "#13151a"
SURFACE    = "#1e2028"
BORDER     = "#383530"
ACCENT     = "#f5883a"
ACCENT_DIM = "#6b3c18"
ACCENT_LINE = "#c46828"
TEXT       = "#ede0d0"
TEXT_DIM   = "#8a8478"
GRID_COLOR = "#272520"
SUCCESS    = "#5dd6a0"
ERROR      = "#f07070"
FONT_MONO  = ("Consolas", 10)
FONT_UI    = ("Segoe UI", 10)


class LT1TModule(tk.Frame):
    def __init__(self, parent, status_cb=None, **kwargs):
        super().__init__(parent, bg=BG, **kwargs)
        self._status_cb  = status_cb or (lambda msg, color=None: None)
        self._input_path = tk.StringVar()
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        self._build_result_strip()
        self._build_controls()
        self._build_preview()

    def _build_controls(self):
        strip = tk.Frame(self, bg=BG)
        strip.pack(pady=(20, 12), padx=40, fill="x")
        strip.columnconfigure(0, weight=1)

        tk.Label(strip, text="INPUT FILE  (.DAT)", font=("Segoe UI Semibold", 8),
                 bg=BG, fg=TEXT_DIM).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        file_row = tk.Frame(strip, bg=BG)
        file_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        file_row.columnconfigure(0, weight=1)
        tk.Entry(file_row, textvariable=self._input_path, font=FONT_MONO,
                 bg=SURFACE, fg=TEXT, insertbackground=TEXT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).grid(row=0, column=0, sticky="ew", ipady=8, ipadx=8)
        self._pill_btn(file_row, "Browse", self._browse).grid(row=0, column=1, padx=(8, 0))

        # Mass card (left) and Convert button (right) on the same row
        self._readout_mass = tk.StringVar(value="—")
        card = tk.Frame(strip, bg=SURFACE,
                        highlightthickness=1, highlightbackground=BORDER)
        card.grid(row=2, column=0, sticky="w")
        tk.Label(card, text="SAMPLE MASS", font=("Segoe UI Semibold", 7),
                 bg=SURFACE, fg=TEXT_DIM).pack(anchor="w", padx=10, pady=(8, 4))
        tk.Label(card, textvariable=self._readout_mass, font=("Consolas", 13),
                 bg=SURFACE, fg=TEXT).pack(anchor="w", padx=10)
        tk.Label(card, text="mg", font=("Segoe UI", 7),
                 bg=SURFACE, fg=TEXT_DIM).pack(anchor="w", padx=10, pady=(2, 8))

        self._btn_run = tk.Button(strip, text="Convert & Save",
                                  font=("Segoe UI Semibold", 10),
                                  bg=ACCENT, fg=BG, relief="flat",
                                  activebackground=ACCENT_DIM, activeforeground=TEXT,
                                  cursor="hand2", command=self._run,
                                  padx=20, pady=8)
        self._btn_run.grid(row=2, column=0, sticky="e")

    def _build_preview(self):
        fig_frame = tk.Frame(self, bg=BG)
        fig_frame.pack(fill="both", expand=True, padx=28, pady=(10, 0))

        self._fig = Figure(figsize=(8, 4), dpi=96, facecolor=BG, edgecolor=BG)
        self._ax  = self._fig.add_subplot(1, 1, 1)
        self._style_ax(self._ax)
        self._fig.subplots_adjust(left=0.12, right=0.97, top=0.91, bottom=0.18)
        self._fig.patch.set_linewidth(0)

        self._canvas = FigureCanvasTkAgg(self._fig, master=fig_frame)
        widget = self._canvas.get_tk_widget()
        widget.config(highlightthickness=0, bd=0, bg=BG)
        widget.pack(fill="both", expand=True)

        fig_frame.bind("<Configure>", self._on_resize)

    def _build_result_strip(self):
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", side="bottom")
        bar = tk.Frame(self, bg=SURFACE)
        bar.pack(fill="x", side="bottom")
        self._result_var = tk.StringVar(value="No file loaded.")
        self._result_lbl = tk.Label(bar, textvariable=self._result_var,
                                    font=("Segoe UI", 9), bg=SURFACE, fg=TEXT_DIM,
                                    anchor="w", justify="left")
        self._result_lbl.pack(side="left", padx=18, pady=7)

    def _on_resize(self, event):
        w = max(event.width,  200) / 96
        h = max(event.height, 200) / 96
        self._fig.set_size_inches(w, h)
        self._fig.subplots_adjust(left=0.12, right=0.97, top=0.91, bottom=0.18)
        self._canvas.draw_idle()

    # ── Plot helpers ──────────────────────────────────────────────────────────

    def _style_ax(self, ax):
        ax.set_facecolor(SURFACE)
        ax.tick_params(colors=TEXT_DIM, labelsize=7.5)
        ax.xaxis.label.set_color(TEXT_DIM)
        ax.yaxis.label.set_color(TEXT_DIM)
        for spine in ax.spines.values():
            spine.set_edgecolor(BORDER)
        ax.set_xlabel("Temperature (K)", fontsize=8)
        ax.set_ylabel("Magnetization (A m²/kg)", fontsize=8)
        ax.set_title("Magnetization vs Temperature", color=TEXT_DIM, fontsize=8.5, pad=6)
        ax.grid(True, color=GRID_COLOR, linewidth=0.6, linestyle="-")
        ax.set_axisbelow(True)

    def _draw_preview(self, df):
        self._ax.clear()
        self._style_ax(self._ax)
        x = df["Temperature (K)"]
        y = df["Magnetization (A m^2/kg)"]
        # lighter connecting line first, then orange scatter dots on top
        self._ax.plot(x, y, color=ACCENT_LINE, linewidth=1.2, zorder=1)
        self._ax.scatter(x, y, color=ACCENT, s=18, zorder=2, linewidths=0)
        self._canvas.draw()

    # ── Widgets ───────────────────────────────────────────────────────────────

    def _pill_btn(self, parent, text, cmd):
        return tk.Button(parent, text=text, font=FONT_UI,
                         bg=SURFACE, fg=TEXT, relief="flat",
                         activebackground=BORDER, activeforeground=TEXT,
                         highlightthickness=1, highlightbackground=BORDER,
                         cursor="hand2", command=cmd, padx=14, pady=7)

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Select DAT file",
            filetypes=[("DAT files", "*.dat *.DAT"), ("All files", "*.*")])
        if path:
            self._input_path.set(path)

    # ── Run ───────────────────────────────────────────────────────────────────

    def _run(self):
        inp = self._input_path.get().strip()
        if not inp:
            self._result_var.set("✗  Please select an input file.")
            self._result_lbl.config(fg=ERROR)
            return

        self._btn_run.config(state="disabled", text="Converting…")
        self._status_cb("Processing…", ACCENT)

        def worker():
            try:
                rows, mass, csv_path, output_dir, df = process_dat(inp)
                self.after(0, lambda: self._done(rows, mass, csv_path, output_dir, df))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: self._error(err))

        threading.Thread(target=worker, daemon=True).start()

    def _done(self, rows, mass, csv_path, output_dir, df):
        self._btn_run.config(state="normal", text="Convert & Save")
        self._status_cb(f"✓  Done  ·  {output_dir}", SUCCESS)

        self._readout_mass.set(f"{mass}" if mass else "not found")
        self._draw_preview(df)

        self._result_var.set(f"✓  {rows} rows saved  ·  {csv_path}")
        self._result_lbl.config(fg=SUCCESS)

    def _error(self, msg):
        self._btn_run.config(state="normal", text="Convert & Save")
        self._status_cb(f"✗  Error: {msg}", ERROR)
        self._result_var.set(f"✗  {msg}")
        self._result_lbl.config(fg=ERROR)
