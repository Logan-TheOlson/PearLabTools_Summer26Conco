import tkinter as tk
from tkinter import filedialog
import threading

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from .processing import process_dat, DEFAULT_BANDS

# ── Palette ───────────────────────────────────────────────────────────────────
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

BAND_COLOR_CYCLE = [
    "#6ba3f5", "#5dd6a0", "#f5c842", "#f07070",
    "#b39dff", "#fd9b5a", "#4dd9e8", "#f472d0",
]


def band_color(label, band_labels):
    idx = band_labels.index(label) if label in band_labels else 0
    return BAND_COLOR_CYCLE[idx % len(BAND_COLOR_CYCLE)]


class VSMModule(tk.Frame):
    def __init__(self, parent, status_cb=None, **kwargs):
        super().__init__(parent, bg=BG, **kwargs)
        self._status_cb   = status_cb or (lambda msg, color=None: None)
        self._input_path  = tk.StringVar()
        self._bands_var   = tk.StringVar(value=", ".join(str(t) for t in DEFAULT_BANDS))
        self._plot_data   = None
        self._band_labels = []
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        self._build_controls()
        self._build_preview()

    def _build_controls(self):
        strip = tk.Frame(self, bg=BG)
        strip.pack(pady=(20, 12), padx=40, fill="x")
        strip.columnconfigure(0, weight=1)

        tk.Label(strip, text="INPUT FILE  (.DAT)", font=("Segoe UI Semibold", 8),
                 bg=BG, fg=TEXT_DIM).grid(row=0, column=0, sticky="w", pady=(0, 4))
        file_row = tk.Frame(strip, bg=BG)
        file_row.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        file_row.columnconfigure(0, weight=1)
        tk.Entry(file_row, textvariable=self._input_path, font=FONT_MONO,
                 bg=SURFACE, fg=TEXT, insertbackground=TEXT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).grid(row=0, column=0, sticky="ew", ipady=8, ipadx=8)
        self._pill_btn(file_row, "Browse", self._browse).grid(row=0, column=1, padx=(8, 0))

        tk.Label(strip, text="TEMPERATURE BANDS  (K, comma-separated)",
                 font=("Segoe UI Semibold", 8), bg=BG, fg=TEXT_DIM).grid(
                 row=2, column=0, sticky="w", pady=(0, 4))
        action_row = tk.Frame(strip, bg=BG)
        action_row.grid(row=3, column=0, sticky="ew")
        action_row.columnconfigure(0, weight=1)
        tk.Entry(action_row, textvariable=self._bands_var, font=FONT_MONO,
                 bg=SURFACE, fg=TEXT, insertbackground=TEXT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).grid(row=0, column=0, sticky="ew", ipady=8, ipadx=8)
        self._btn_run = tk.Button(action_row, text="Convert & Save",
                                  font=("Segoe UI Semibold", 10),
                                  bg=ACCENT, fg=BG, relief="flat",
                                  activebackground=ACCENT_DIM, activeforeground=TEXT,
                                  cursor="hand2", command=self._run,
                                  padx=20, pady=8)
        self._btn_run.grid(row=0, column=1, padx=(10, 0))

        self._result_var = tk.StringVar()
        self._result_lbl = tk.Label(strip, textvariable=self._result_var,
                                    font=("Segoe UI", 9), bg=BG, fg=TEXT_DIM,
                                    anchor="w", justify="left")
        self._result_lbl.grid(row=4, column=0, sticky="w", pady=(8, 0))

    def _build_preview(self):
        fig_frame = tk.Frame(self, bg=BG)
        fig_frame.pack(fill="both", expand=True, padx=16, pady=(4, 16))

        self._fig     = Figure(figsize=(10, 3.6), dpi=96, facecolor=BG, edgecolor=BG)
        self._ax_raw  = self._fig.add_subplot(1, 2, 1)
        self._ax_corr = self._fig.add_subplot(1, 2, 2)
        self._style_ax(self._ax_raw,  "Original Hysteresis Loops",  show_ylabel=True)
        self._style_ax(self._ax_corr, "Paramagnetic Contribution Removed", show_ylabel=False)
        self._fig.text(0.02, 0.5, "Magnetization (A m²/kg)", va='center', ha='left',
                       rotation='vertical', fontsize=8, color=TEXT_DIM)
        self._fig.subplots_adjust(left=0.13, right=0.97, top=0.91, bottom=0.18, wspace=0.35)
        self._fig.patch.set_linewidth(0)

        self._canvas = FigureCanvasTkAgg(self._fig, master=fig_frame)
        widget = self._canvas.get_tk_widget()
        widget.config(highlightthickness=0, bd=0, bg=BG)
        widget.pack(fill="both", expand=True)

        fig_frame.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        w = max(event.width,  200) / 96
        h = max(event.height, 200) / 96
        self._fig.set_size_inches(w, h)
        self._fig.subplots_adjust(left=0.13, right=0.97, top=0.91, bottom=0.18, wspace=0.35)
        self._canvas.draw_idle()

    # ── Plot helpers ──────────────────────────────────────────────────────────

    def _style_ax(self, ax, title="", show_ylabel=False):
        ax.set_facecolor(SURFACE)
        ax.tick_params(colors=TEXT_DIM, labelsize=7.5)
        ax.xaxis.label.set_color(TEXT_DIM)
        ax.yaxis.label.set_color(TEXT_DIM)
        for spine in ax.spines.values():
            spine.set_edgecolor(BORDER)
        ax.set_xlabel("Field (T)", fontsize=8)
        ax.set_ylabel("")  # handled by shared figure text
        ax.set_title(title, color=TEXT_DIM, fontsize=8.5, pad=6)
        ax.grid(True, color=GRID_COLOR, linewidth=0.6, linestyle='-')
        ax.set_axisbelow(True)
        ax.axhline(0, color=BORDER, linewidth=0.8)
        ax.axvline(0, color=BORDER, linewidth=0.8)

    def _draw_preview(self):
        self._ax_raw.clear()
        self._ax_corr.clear()
        self._style_ax(self._ax_raw,  "Original Hysteresis Loops",  show_ylabel=True)
        self._style_ax(self._ax_corr, "Paramagnetic Contribution Removed", show_ylabel=False)

        all_y_raw  = []
        all_y_corr = []
        for label in self._band_labels:
            data = self._plot_data.get(label)
            if data is None or data['x'] is None:
                continue
            all_y_raw.extend(data['y'])
            all_y_corr.extend(data['corrected'] if data['corrected'] is not None else data['y'])

        for label in self._band_labels:
            data = self._plot_data.get(label)
            if data is None or data['x'] is None:
                continue

            color = band_color(label, self._band_labels)
            x, y  = data['x'], data['y']

            self._ax_raw.plot(x, y, color=color, linewidth=1.4, label=label)

            if data['corrected'] is not None:
                self._ax_corr.plot(x, data['corrected'], color=color,
                                   linewidth=1.4, label=label)
            else:
                self._ax_corr.plot(x, y, color=color, linewidth=1.4,
                                   linestyle='--', alpha=0.5,
                                   label=f"{label} (no correction)")

        # lock both plots to the same y range so they're visually comparable
        if all_y_raw and all_y_corr:
            y_min = min(min(all_y_raw), min(all_y_corr))
            y_max = max(max(all_y_raw), max(all_y_corr))
            pad   = (y_max - y_min) * 0.06
            for ax in (self._ax_raw, self._ax_corr):
                ax.set_ylim(y_min - pad, y_max + pad)

        for ax in (self._ax_raw, self._ax_corr):
            ax.legend(fontsize=7.5, facecolor=SURFACE, edgecolor=BORDER, labelcolor=TEXT)

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

    def _parse_band_temps(self):
        raw = self._bands_var.get()
        try:
            temps = [int(t.strip()) for t in raw.split(",") if t.strip()]
            if not temps:
                raise ValueError
            return temps
        except ValueError:
            self._result_var.set("✗  Bands must be comma-separated integers, e.g. 50, 150, 300")
            self._result_lbl.config(fg=ERROR)
            return None

    # ── Run ───────────────────────────────────────────────────────────────────

    def _run(self):
        inp = self._input_path.get().strip()
        if not inp:
            self._result_var.set("✗  Please select an input file.")
            self._result_lbl.config(fg=ERROR)
            return
        band_temps = self._parse_band_temps()
        if band_temps is None:
            return

        self._btn_run.config(state="disabled", text="Converting…")
        self._status_cb("Processing…", ACCENT)

        def worker():
            try:
                rows, mass, csv_path, output_dir, plot_data, band_ranges = \
                    process_dat(inp, band_temps)
                self.after(0, lambda: self._done(
                    rows, mass, csv_path, output_dir, plot_data, band_ranges))
            except Exception as e:
                self.after(0, lambda: self._error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _done(self, rows, mass, csv_path, output_dir, plot_data, band_ranges):
        self._btn_run.config(state="normal", text="Convert & Save")
        self._status_cb(f"✓  Done  ·  {output_dir}", SUCCESS)

        self._plot_data   = plot_data
        self._band_labels = [label for label, *_ in band_ranges]
        self._draw_preview()

        mass_str_full = f"{mass} mg" if mass else "not found"
        self._result_var.set(
            f"✓  {rows} rows saved  ·  Mass: {mass_str_full}\n{csv_path}")
        self._result_lbl.config(fg=SUCCESS)

    def _error(self, msg):
        self._btn_run.config(state="normal", text="Convert & Save")
        self._status_cb(f"✗  Error: {msg}", ERROR)
        self._result_var.set(f"✗  {msg}")
        self._result_lbl.config(fg=ERROR)
