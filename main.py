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
def process_dat(input_path, output_dir):
    """
    Creates output_dir, copies the original .DAT into it, and writes
    a converted .CSV alongside it. Returns (row_count, mass, csv_path).
    """
    os.makedirs(output_dir, exist_ok=True)

    # Copy original DAT
    dat_name = os.path.basename(input_path)
    shutil.copy2(input_path, os.path.join(output_dir, dat_name))

    # Extract mass
    mass = None
    with open(input_path, 'r') as f:
        for line in f:
            if 'SAMPLE_MASS' in line:
                mass = float(line.strip().split(',')[1])
                break

    with open(input_path, 'r') as f:
        lines = f.readlines()
    data_start = next(i for i, l in enumerate(lines) if l.strip() == '[Data]')

    df = pd.read_csv(input_path, skiprows=data_start + 1)
    df = df.iloc[:, [2, 3, 4]]
    df = df.dropna(subset=['Moment (emu)'])
    df = df.loc[df['Moment (emu)'] != '0']
    df = df.copy()

    df['Field (T)']               = df['Magnetic Field (Oe)'].astype(float) * 1e-4
    df['Moment (A·m²)']           = df['Moment (emu)'].astype(float) * 1e-3
    if mass:
        df['Magnetization (A·m²/kg)'] = df['Moment (A·m²)'] / (mass * 1e-3)

    # Drop raw columns
    df = df.drop(columns=['Magnetic Field (Oe)', 'Moment (emu)'])

    csv_name = os.path.splitext(dat_name)[0] + "_converted.csv"
    csv_path = os.path.join(output_dir, csv_name)
    df.to_csv(csv_path, index=False)

    return len(df), mass, csv_path

# ── GUI ───────────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("VSM Converter")
        self.geometry("1000x800")
        self.minsize(1000, 800)
        self.configure(bg=BG)
        self.iconbitmap(resource_path("icon.ico"))
        self._input_path  = tk.StringVar()
        self._output_dir  = tk.StringVar()
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

        # Output folder
        tk.Label(body, text="OUTPUT FOLDER", font=("Segoe UI Semibold", 8),
                 bg=BG, fg=TEXT_DIM).grid(row=2, column=0, sticky="w", pady=(0, 5))
        tk.Label(body, text="A new folder will be created containing the original .DAT and the converted .CSV",
                 font=("Segoe UI", 8), bg=BG, fg=TEXT_DIM).grid(row=3, column=0, sticky="w", pady=(0, 5))
        row_out = tk.Frame(body, bg=BG)
        row_out.grid(row=4, column=0, sticky="ew", pady=(0, 24))
        row_out.columnconfigure(0, weight=1)
        tk.Entry(row_out, textvariable=self._output_dir, font=FONT_MONO,
                 bg=SURFACE, fg=TEXT, insertbackground=TEXT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).grid(row=0, column=0, sticky="ew", ipady=9, ipadx=10)
        self._pill_btn(row_out, "Browse", self._browse_output).grid(row=0, column=1, padx=(10, 0))

        # Conversions info box
        info = tk.Frame(body, bg=SURFACE, pady=12, padx=16)
        info.grid(row=5, column=0, sticky="ew", pady=(0, 22))
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
            tk.Label(r, text=conv,  font=FONT_MONO, bg=SURFACE, fg=TEXT_DIM,
                     width=16, anchor="w").pack(side="left")
            tk.Label(r, text=f"({factor})", font=FONT_MONO, bg=SURFACE,
                     fg=TEXT_DIM).pack(side="left")

        # Convert button
        self._btn_run = tk.Button(body, text="Convert & Save",
                                  font=("Segoe UI Semibold", 12),
                                  bg=ACCENT, fg="white", relief="flat",
                                  activebackground=ACCENT_DIM, activeforeground="white",
                                  cursor="hand2", command=self._run,
                                  padx=32, pady=12)
        self._btn_run.grid(row=6, column=0, sticky="ew")

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
            if not self._output_dir.get():
                stem = os.path.splitext(path)[0]
                self._output_dir.set(stem + "_output")

    def _browse_output(self):
        path = filedialog.askdirectory(title="Select output folder (will be created if needed)")
        if path:
            self._output_dir.set(path)

    def _set_status(self, msg, color=TEXT_DIM):
        self._status.set(msg)
        self._status_lbl.config(fg=color)

    def _run(self):
        inp = self._input_path.get().strip()
        out = self._output_dir.get().strip()
        if not inp or not out:
            messagebox.showwarning("Missing paths", "Please select an input file and output folder.")
            return

        self._btn_run.config(state="disabled", text="Converting…")
        self._set_status("Processing…", ACCENT)

        def worker():
            try:
                rows, mass, csv_path = process_dat(inp, out)
                self.after(0, lambda: self._done(rows, mass, csv_path))
            except Exception as e:
                self.after(0, lambda: self._error(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _done(self, rows, mass, csv_path):
        self._btn_run.config(state="normal", text="Convert & Save")
        mass_str = f"{mass} g" if mass else "not found"
        self._set_status(f"✓  Done — {rows} rows  ·  Mass: {mass_str}  ·  {self._output_dir.get()}", SUCCESS)
        messagebox.showinfo("Success",
            f"Converted {rows} rows.\n\nOutput folder:\n{self._output_dir.get()}\n\n"
            f"  • {os.path.basename(self._input_path.get())}  (original)\n"
            f"  • {os.path.basename(csv_path)}  (converted)")

    def _error(self, msg):
        self._btn_run.config(state="normal", text="Convert & Save")
        self._set_status(f"✗  Error: {msg}", ERROR)
        messagebox.showerror("Error", msg)


if __name__ == "__main__":
    app = App()
    app.mainloop()