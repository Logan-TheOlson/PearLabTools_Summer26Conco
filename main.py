import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import os
import shutil
import ctypes
import sys
import pandas as pd

def resource_path(relative):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative)

# ── DPI awareness (Windows) ───────────────────────────────────────────────────
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# ── Palette ───────────────────────────────────────────────────────────────────
BG         = "#0f1117"
SURFACE    = "#1a1d27"
BORDER     = "#2a2d3a"
ACCENT     = "#4f8ef7"
ACCENT_DIM = "#1e3a6e"
TEXT       = "#e8eaf0"
TEXT_DIM   = "#6b7080"
SUCCESS    = "#3ecf8e"
ERROR      = "#f76f6f"
FONT_MONO  = ("Consolas", 10)
FONT_UI    = ("Segoe UI", 10)

# ── Processing logic ──────────────────────────────────────────────────────────
def process_dat(input_path):
    output_dir = os.path.join(os.path.dirname(os.path.abspath(input_path)), "output")
    os.makedirs(output_dir, exist_ok=True)

    dat_name = os.path.basename(input_path)

    mass = None
    with open(input_path, 'r') as f:
        for line in f:
            if 'SAMPLE_MASS' in line:
                parts = line.strip().split('\t') if '\t' in line else line.strip().split(',')
                try:
                    mass = float(parts[1])
                except (IndexError, ValueError):
                    mass = None
                break

    with open(input_path, 'r') as f:
        lines = f.readlines()
    data_start = next(i for i, l in enumerate(lines) if l.strip() == '[Data]')

    # Auto-detect delimiter from the first data line
    sample_line = lines[data_start + 1]
    delimiter = '\t' if '\t' in sample_line else ','

    df = pd.read_csv(input_path, skiprows=data_start + 1, sep=delimiter)
    df = df[['Temperature (K)', 'Magnetic Field (Oe)', 'Moment (emu)']]
    df = df.dropna(subset=['Moment (emu)'])
    df = df.loc[df['Moment (emu)'] != '0']
    df = df.copy()

    df['Field (T)'] = df['Magnetic Field (Oe)'].astype(float) * 1e-4
    df['Moment (A m^2)'] = df['Moment (emu)'].astype(float) * 1e-3
    if mass:
        df['Magnetization (A m^2/kg)'] = df['Moment (A m^2)'] / (mass * 1e-3)

    df = df.drop(columns=['Magnetic Field (Oe)', 'Moment (emu)'])

    temp_col = 'Temperature (K)'
    bands = [
        ('50K',  49,  51),
        ('150K', 149, 151),
        ('300K', 299, 301),
    ]

    frames = []
    for label, lo, hi in bands:
        band = df[(df[temp_col] >= lo) & (df[temp_col] <= hi)].copy()
        band.columns = [f"{c} [{label}]" for c in band.columns]
        band = band.reset_index(drop=True)
        frames.append(band)

    out_df = pd.concat(frames, axis=1)

    csv_name = os.path.splitext(dat_name)[0] + "_converted.csv"
    csv_path = os.path.join(output_dir, csv_name)
    out_df.to_csv(csv_path, index=False)

    return len(out_df), mass, csv_path, output_dir

# ── GUI ───────────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("VSM Converter")
        self.geometry("1000x800")
        self.minsize(1000, 800)
        self.configure(bg=BG)
        self.iconbitmap(resource_path("icon.ico"))
        self._input_path = tk.StringVar()
        self._build()

    def _build(self):
        # ── Header ────────────────────────────────────────────────────────────
        header = tk.Frame(self, bg=SURFACE)
        header.pack(fill="x")
        inner = tk.Frame(header, bg=SURFACE)
        inner.pack(side="left", padx=24, pady=14)
        tk.Label(inner, text="VSM  ·  DAT → CSV",
                 font=("Segoe UI Semibold", 16), bg=SURFACE, fg=TEXT).pack(anchor="w")
        tk.Label(inner, text="Quantum Design VSM processor",
                 font=("Segoe UI", 10), bg=SURFACE, fg=TEXT_DIM).pack(anchor="w")
        tk.Frame(self, bg=ACCENT, height=2).pack(fill="x")

        # ── Body ──────────────────────────────────────────────────────────────
        body = tk.Frame(self, bg=BG, padx=32, pady=24)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)

        # Input file
        tk.Label(body, text="INPUT FILE  (.DAT)", font=("Segoe UI Semibold", 8),
                 bg=BG, fg=TEXT_DIM).grid(row=0, column=0, sticky="w", pady=(0, 5))
        row_in = tk.Frame(body, bg=BG)
        row_in.grid(row=1, column=0, sticky="ew", pady=(0, 20))
        row_in.columnconfigure(0, weight=1)
        tk.Entry(row_in, textvariable=self._input_path, font=FONT_MONO,
                 bg=SURFACE, fg=TEXT, insertbackground=TEXT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).grid(row=0, column=0, sticky="ew", ipady=9, ipadx=10)
        self._pill_btn(row_in, "Browse", self._browse_input).grid(row=0, column=1, padx=(10, 0))

        # Output note
        tk.Label(body, text="Output saves to an 'output' folder next to the input file.",
                 font=("Segoe UI", 9), bg=BG, fg=TEXT_DIM).grid(row=2, column=0, sticky="w", pady=(0, 20))

        # Conversions info box
        info = tk.Frame(body, bg=SURFACE, pady=12, padx=16)
        info.grid(row=3, column=0, sticky="ew", pady=(0, 22))
        tk.Label(info, text="CONVERSIONS APPLIED", font=("Segoe UI Semibold", 8),
                 bg=SURFACE, fg=TEXT_DIM).pack(anchor="w", pady=(0, 6))
        convs = [
            ("Magnetic Field",  "Oe  →  T",        "× 1 × 10⁻⁴"),
            ("Moment",          "emu →  A·m²",      "× 1 × 10⁻³"),
            ("Magnetization",   "emu →  A·m²/kg",   "÷ sample mass"),
        ]
        for label, conv, factor in convs:
            r = tk.Frame(info, bg=SURFACE)
            r.pack(fill="x", pady=2)
            tk.Label(r, text=label, font=FONT_MONO, bg=SURFACE, fg=TEXT,
                     width=16, anchor="w").pack(side="left")
            tk.Label(r, text=conv, font=FONT_MONO, bg=SURFACE, fg=TEXT_DIM,
                     width=16, anchor="w").pack(side="left")
            tk.Label(r, text=f"({factor})", font=FONT_MONO, bg=SURFACE,
                     fg=TEXT_DIM).pack(side="left")

        # Temperature bands info
        bands_frame = tk.Frame(body, bg=SURFACE, pady=12, padx=16)
        bands_frame.grid(row=4, column=0, sticky="ew", pady=(0, 22))
        tk.Label(bands_frame, text="TEMPERATURE BANDS", font=("Segoe UI Semibold", 8),
                 bg=SURFACE, fg=TEXT_DIM).pack(anchor="w", pady=(0, 6))
        bands = [
            ("50K",  "49 – 51 K"),
            ("150K", "149 – 151 K"),
            ("300K", "299 – 301 K"),
        ]
        for label, rng in bands:
            r = tk.Frame(bands_frame, bg=SURFACE)
            r.pack(fill="x", pady=2)
            tk.Label(r, text=label, font=FONT_MONO, bg=SURFACE, fg=TEXT,
                     width=8, anchor="w").pack(side="left")
            tk.Label(r, text=rng, font=FONT_MONO, bg=SURFACE, fg=TEXT_DIM).pack(side="left")

        # Convert button
        self._btn_run = tk.Button(body, text="Convert & Save",
                                  font=("Segoe UI Semibold", 12),
                                  bg=ACCENT, fg="white", relief="flat",
                                  activebackground=ACCENT_DIM, activeforeground="white",
                                  cursor="hand2", command=self._run,
                                  padx=32, pady=12)
        self._btn_run.grid(row=5, column=0, sticky="ew")

        # ── Status bar ────────────────────────────────────────────────────────
        self._status = tk.StringVar(value="Ready.")
        bar = tk.Frame(self, bg=SURFACE)
        bar.pack(fill="x", side="bottom")
        self._status_lbl = tk.Label(bar, textvariable=self._status,
                                    font=("Segoe UI", 9), bg=SURFACE, fg=TEXT_DIM)
        self._status_lbl.pack(side="left", padx=18, pady=8)

    def _pill_btn(self, parent, text, cmd):
        return tk.Button(parent, text=text, font=FONT_UI,
                         bg=SURFACE, fg=TEXT, relief="flat",
                         activebackground=BORDER, activeforeground=TEXT,
                         highlightthickness=1, highlightbackground=BORDER,
                         cursor="hand2", command=cmd, padx=16, pady=8)

    # ── Actions ───────────────────────────────────────────────────────────────
    def _browse_input(self):
        path = filedialog.askopenfilename(
            title="Select DAT file",
            filetypes=[("DAT files", "*.dat *.DAT"), ("All files", "*.*")])
        if path:
            self._input_path.set(path)

    def _set_status(self, msg, color=TEXT_DIM):
        self._status.set(msg)
        self._status_lbl.config(fg=color)

    def _run(self):
        inp = self._input_path.get().strip()
        if not inp:
            messagebox.showwarning("Missing file", "Please select an input file.")
            return
        self._btn_run.config(state="disabled", text="Converting…")
        self._set_status("Processing…", ACCENT)

        def worker():
            try:
                rows, mass, csv_path, output_dir = process_dat(inp)
                self.after(0, lambda: self._done(rows, mass, csv_path, output_dir))
            except Exception as e:
                import traceback
                traceback.print_exc()
                err = str(e)
                self.after(0, lambda: self._error(err))
        threading.Thread(target=worker, daemon=True).start()

    def _done(self, rows, mass, csv_path, output_dir):
        self._btn_run.config(state="normal", text="Convert & Save")
        mass_str = f"{mass} g" if mass else "not found"
        self._set_status(f"✓  Done — {rows} rows  ·  Mass: {mass_str}  ·  {output_dir}", SUCCESS)
        messagebox.showinfo("Success",
            f"Converted {rows} rows.\n\nOutput folder:\n{output_dir}\n\n"
            f"  • {os.path.basename(self._input_path.get())}  (original)\n"
            f"  • {os.path.basename(csv_path)}  (converted)")

    def _error(self, msg):
        self._btn_run.config(state="normal", text="Convert & Save")
        self._set_status(f"✗  Error: {msg}", ERROR)
        messagebox.showerror("Error", msg)

if __name__ == "__main__":
    app = App()
    app.mainloop()