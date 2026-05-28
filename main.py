import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import os
import ctypes
import sys

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from processing import process_dat, DEFAULT_BANDS

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
BG         = "#13151f"
SURFACE    = "#1e2130"
BORDER     = "#353a50"
ACCENT     = "#6ba3f5"
ACCENT_DIM = "#2a4a8a"
TEXT       = "#dde1f0"
TEXT_DIM   = "#8a91a8"
GRID_COLOR = "#272c3f"
SUCCESS    = "#5dd6a0"
ERROR      = "#f07070"
FONT_MONO  = ("Consolas", 10)
FONT_UI    = ("Segoe UI", 10)

# Band color cycle — lighter/more distinct than before
BAND_COLOR_CYCLE = [
    "#6ba3f5", "#5dd6a0", "#f5c842", "#f07070",
    "#b39dff", "#fd9b5a", "#4dd9e8", "#f472d0",
]


def band_color(label, band_labels):
    idx = band_labels.index(label) if label in band_labels else 0
    return BAND_COLOR_CYCLE[idx % len(BAND_COLOR_CYCLE)]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("VSM Converter")
        self.geometry("1100x820")
        self.minsize(900, 700)
        self.configure(bg=BG)
        try:
            self.iconbitmap(resource_path("icon.ico"))
        except Exception:
            pass
        self._input_path  = tk.StringVar()
        self._plot_data   = None
        self._band_labels = []
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        # Header
        header = tk.Frame(self, bg=SURFACE)
        header.pack(fill="x")
        inner = tk.Frame(header, bg=SURFACE)
        inner.pack(side="left", padx=24, pady=14)
        tk.Label(inner, text="VSM  ·  DAT → CSV",
                 font=("Segoe UI Semibold", 16), bg=SURFACE, fg=TEXT).pack(anchor="w")
        tk.Label(inner, text="Quantum Design VSM processor",
                 font=("Segoe UI", 10), bg=SURFACE, fg=TEXT_DIM).pack(anchor="w")
        tk.Frame(self, bg=ACCENT, height=2).pack(fill="x")

        # Scrollable body
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)

        self._build_controls(body)
        self._build_preview(body)

        # Status bar
        bar = tk.Frame(self, bg=SURFACE)
        bar.pack(fill="x", side="bottom")
        self._status = tk.StringVar(value="Ready.")
        self._status_lbl = tk.Label(bar, textvariable=self._status,
                                    font=("Segoe UI", 9), bg=SURFACE, fg=TEXT_DIM)
        self._status_lbl.pack(side="left", padx=18, pady=8)

    def _build_controls(self, parent):
        # Centered control strip
        strip = tk.Frame(parent, bg=BG)
        strip.pack(pady=(20, 12), padx=40, fill="x")

        # Row 1 — file input
        tk.Label(strip, text="INPUT FILE  (.DAT)", font=("Segoe UI Semibold", 8),
                 bg=BG, fg=TEXT_DIM).grid(row=0, column=0, sticky="w", pady=(0, 4))
        file_row = tk.Frame(strip, bg=BG)
        file_row.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        file_row.columnconfigure(0, weight=1)
        tk.Entry(file_row, textvariable=self._input_path, font=FONT_MONO,
                 bg=SURFACE, fg=TEXT, insertbackground=TEXT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).grid(row=0, column=0, sticky="ew", ipady=8, ipadx=8)
        self._pill_btn(file_row, "Browse", self._browse_input).grid(row=0, column=1, padx=(8, 0))

        # Row 2 — band temps + convert side by side
        tk.Label(strip, text="TEMPERATURE BANDS  (K, comma-separated)",
                 font=("Segoe UI Semibold", 8), bg=BG, fg=TEXT_DIM).grid(
                 row=2, column=0, sticky="w", pady=(0, 4))
        action_row = tk.Frame(strip, bg=BG)
        action_row.grid(row=3, column=0, sticky="ew")
        action_row.columnconfigure(0, weight=1)

        self._bands_var = tk.StringVar(value=", ".join(str(t) for t in DEFAULT_BANDS))
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

        strip.columnconfigure(0, weight=1)

    def _build_preview(self, parent):
        # Fixed-size figure centered below controls
        fig_frame = tk.Frame(parent, bg=BG)
        fig_frame.pack(pady=(4, 16))

        self._fig = Figure(figsize=(10, 3.8), dpi=96, facecolor=BG)
        self._ax_raw  = self._fig.add_subplot(1, 2, 1)
        self._ax_corr = self._fig.add_subplot(1, 2, 2)
        self._style_ax(self._ax_raw,  "Original Hysteresis Loops")
        self._style_ax(self._ax_corr, "Paramagnetic Contribution Removed")
        self._fig.tight_layout(pad=2.2)

        self._canvas = FigureCanvasTkAgg(self._fig, master=fig_frame)
        self._canvas.get_tk_widget().pack()

    # ── Plot helpers ──────────────────────────────────────────────────────────

    def _style_ax(self, ax, title=""):
        ax.set_facecolor(SURFACE)
        ax.tick_params(colors=TEXT_DIM, labelsize=7.5)
        ax.xaxis.label.set_color(TEXT_DIM)
        ax.yaxis.label.set_color(TEXT_DIM)
        for spine in ax.spines.values():
            spine.set_edgecolor(BORDER)
        ax.set_xlabel("Field (T)", fontsize=8)
        ax.set_ylabel("Magnetization (A m²/kg)", fontsize=8)
        ax.set_title(title, color=TEXT_DIM, fontsize=8.5, pad=6)
        # Gridlines
        ax.grid(True, color=GRID_COLOR, linewidth=0.6, linestyle='-')
        ax.set_axisbelow(True)
        # Zero lines
        ax.axhline(0, color=BORDER, linewidth=0.8)
        ax.axvline(0, color=BORDER, linewidth=0.8)

    def _draw_preview(self):
        self._ax_raw.clear()
        self._ax_corr.clear()
        self._style_ax(self._ax_raw,  "Original Hysteresis Loops")
        self._style_ax(self._ax_corr, "Paramagnetic Contribution Removed")

        # Collect all y values across both plots to share scale
        all_y_raw  = []
        all_y_corr = []
        for label in self._band_labels:
            data = self._plot_data.get(label)
            if data is None or data['x'] is None:
                continue
            all_y_raw.extend(data['y'])
            if data['corrected'] is not None:
                all_y_corr.extend(data['corrected'])
            else:
                all_y_corr.extend(data['y'])

        # Plot each band
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
                # No correction found — show raw dashed
                self._ax_corr.plot(x, y, color=color, linewidth=1.4,
                                   linestyle='--', alpha=0.5,
                                   label=f"{label} (no correction)")

        # Apply shared y scale with a little padding
        if all_y_raw and all_y_corr:
            y_min = min(min(all_y_raw), min(all_y_corr))
            y_max = max(max(all_y_raw), max(all_y_corr))
            pad   = (y_max - y_min) * 0.06
            for ax in (self._ax_raw, self._ax_corr):
                ax.set_ylim(y_min - pad, y_max + pad)

        for ax in (self._ax_raw, self._ax_corr):
            ax.legend(fontsize=7.5, facecolor=SURFACE, edgecolor=BORDER, labelcolor=TEXT)

        self._fig.tight_layout(pad=2.2)
        self._canvas.draw()

    # ── Widgets ───────────────────────────────────────────────────────────────

    def _pill_btn(self, parent, text, cmd):
        return tk.Button(parent, text=text, font=FONT_UI,
                         bg=SURFACE, fg=TEXT, relief="flat",
                         activebackground=BORDER, activeforeground=TEXT,
                         highlightthickness=1, highlightbackground=BORDER,
                         cursor="hand2", command=cmd, padx=14, pady=7)

    def _browse_input(self):
        path = filedialog.askopenfilename(
            title="Select DAT file",
            filetypes=[("DAT files", "*.dat *.DAT"), ("All files", "*.*")])
        if path:
            self._input_path.set(path)

    def _set_status(self, msg, color=TEXT_DIM):
        self._status.set(msg)
        self._status_lbl.config(fg=color)

    def _parse_band_temps(self):
        # Parse comma-separated integer temperatures from entry
        raw = self._bands_var.get()
        try:
            temps = [int(t.strip()) for t in raw.split(",") if t.strip()]
            if not temps:
                raise ValueError
            return temps
        except ValueError:
            messagebox.showerror("Invalid bands",
                "Temperature bands must be comma-separated integers, e.g.  50, 150, 300")
            return None

    # ── Run ───────────────────────────────────────────────────────────────────

    def _run(self):
        inp = self._input_path.get().strip()
        if not inp:
            messagebox.showwarning("Missing file", "Please select an input file.")
            return
        band_temps = self._parse_band_temps()
        if band_temps is None:
            return

        self._btn_run.config(state="disabled", text="Converting…")
        self._set_status("Processing…", ACCENT)

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
        mass_str = f"{mass} g" if mass else "not found"
        self._set_status(
            f"✓  Done — {rows} rows  ·  Mass: {mass_str}  ·  {output_dir}", SUCCESS)

        self._plot_data   = plot_data
        self._band_labels = [label for label, *_ in band_ranges]
        self._draw_preview()

        messagebox.showinfo("Success",
            f"Converted {rows} rows.\n\nOutput folder:\n{output_dir}\n\n"
f"  • {os.path.basename(csv_path)}  (converted)")

    def _error(self, msg):
        self._btn_run.config(state="normal", text="Convert & Save")
        self._set_status(f"✗  Error: {msg}", ERROR)
        messagebox.showerror("Error", msg)


if __name__ == "__main__":
    app = App()
    app.mainloop()