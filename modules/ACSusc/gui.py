import re
import tkinter as tk
import pandas as pd

from modules.base_gui import BaseModule, RoundedButton
from .processing import process_dat

SUBPLOT_KW = dict(left=0.10, right=0.97, top=0.91, bottom=0.18, wspace=0.38)

_COLORS = [
    "#c8982a",
    "#6ba3f5",
    "#e87059",
    "#6bcf7f",
    "#c875e8",
    "#e8c175",
    "#75c8e8",
    "#e87575",
]


def _freq_label(f):
    r = round(f)
    return f"{r} Hz" if abs(f - r) < 0.5 else f"{f:.1f} Hz"


def _normalize_col(name):
    return re.sub(r" {2,}", " ", name).strip()


class ACSuscModule(BaseModule):
    def __init__(self, parent, status_cb=None, **kwargs):
        super().__init__(parent, status_cb, **kwargs)
        self._freqs_var         = tk.StringVar(value="")
        self._freqs_placeholder = []
        self._using_placeholder = True
        self._build()

    def _build(self):
        self._build_result_strip()
        self._build_controls()
        self._build_preview()

    def _build_controls(self):
        strip = tk.Frame(self, bg=self.BG)
        strip.pack(pady=(self._s(20), self._s(12)), padx=self._s(40), fill="x")
        strip.columnconfigure(0, weight=1)
        self._build_file_row(strip, grid_row=0)

        tk.Label(strip, text="FREQUENCIES  (Hz, comma-separated  ·  leave blank for auto-detect)",
                 font=self._f("Segoe UI Semibold", 8),
                 bg=self.BG, fg=self.TEXT_DIM).grid(
                 row=2, column=0, sticky="w", pady=(0, self._s(4)))

        action_row = tk.Frame(strip, bg=self.BG)
        action_row.grid(row=3, column=0, sticky="ew")
        action_row.columnconfigure(0, weight=1)

        self._freqs_entry = tk.Entry(action_row, textvariable=self._freqs_var,
                                     font=self._f("Consolas", 10),
                                     bg=self.SURFACE, fg=self.TEXT_DIM,
                                     insertbackground=self.TEXT, relief="flat",
                                     highlightthickness=1,
                                     highlightbackground=self.BORDER,
                                     highlightcolor=self.ACCENT)
        self._freqs_entry.grid(row=0, column=0, sticky="ew",
                               ipady=self._s(8), ipadx=self._s(8))
        self._freqs_entry.bind("<FocusIn>",  self._on_freqs_focus_in)
        self._freqs_entry.bind("<FocusOut>", self._on_freqs_focus_out)

        self._readout_mass = tk.StringVar(value="—")
        card = tk.Frame(action_row, bg=self.SURFACE,
                        highlightthickness=1, highlightbackground=self.BORDER)
        card.grid(row=0, column=1, padx=(self._s(12), 0), sticky="ns")
        p = self._s(10)
        tk.Label(card, text="SAMPLE MASS", font=self._f("Segoe UI Semibold", 7),
                 bg=self.SURFACE, fg=self.TEXT_DIM).pack(
                 anchor="w", padx=p, pady=(self._s(6), self._s(2)))
        tk.Label(card, textvariable=self._readout_mass,
                 font=self._f("Consolas", 11),
                 bg=self.SURFACE, fg=self.TEXT).pack(anchor="w", padx=p)
        tk.Label(card, text="mg", font=self._f("Segoe UI", 7),
                 bg=self.SURFACE, fg=self.TEXT_DIM).pack(
                 anchor="w", padx=p, pady=(self._s(2), self._s(6)))

        self._btn_run = RoundedButton(action_row, text="Convert & Save",
                                     command=self._run,
                                     radius=5,
                                     bg=self.ACCENT, hover_bg=self.ACCENT_DIM,
                                     fg=self.BG,
                                     font=self._f("Segoe UI Semibold", 10),
                                     padx=self._s(20), pady=self._s(8))
        self._btn_run.grid(row=0, column=2, padx=(self._s(10), 0))

    def _build_preview(self):
        fig_frame = tk.Frame(self, bg=self.BG)
        fig_frame.pack(fill="both", expand=True,
                       padx=self._s(40), pady=(self._s(10), 0))
        self._subplot_kw = SUBPLOT_KW
        self._fig, self._canvas = self._make_canvas(fig_frame)
        self._ax_prime  = self._fig.add_subplot(1, 2, 1)
        self._ax_double = self._fig.add_subplot(1, 2, 2)
        self._fig.subplots_adjust(**SUBPLOT_KW)
        self._refresh_ax()
        fig_frame.bind("<Configure>", self._on_resize)
        self._enable_zoom(self._ax_prime, self._ax_double)

    def _refresh_ax(self):
        self._style_ax(self._ax_prime,
                       title="AC χ' vs Temperature",
                       xlabel="Temperature (K)",
                       ylabel="χ' (m³/kg)")
        self._style_ax(self._ax_double,
                       title="AC χ\" vs Temperature",
                       xlabel="Temperature (K)",
                       ylabel="χ\" (m³/kg)")

    def _draw_preview(self, df, freqs):
        self._ax_prime.clear()
        self._ax_double.clear()
        self._refresh_ax()

        for i, f in enumerate(freqs):
            color = _COLORS[i % len(_COLORS)]
            label = _freq_label(f)
            sub = df[df["Frequency (Hz)"] == f].sort_values("Temperature (K)")
            x = sub["Temperature (K)"]
            for ax, col in (
                (self._ax_prime,  "AC X' (m^3/kg)"),
                (self._ax_double, 'AC X" (m^3/kg)'),
            ):
                ax.plot(x, sub[col], color=color, linewidth=1.2, zorder=1)
                ax.scatter(x, sub[col], color=color, s=self._s(18),
                           zorder=2, linewidths=0, label=label)

        legend_kw = dict(fontsize=self._mpl(7.5), facecolor=self.SURFACE,
                         edgecolor=self.BORDER, labelcolor=self.TEXT)
        self._ax_prime.legend(**legend_kw)
        self._ax_double.legend(**legend_kw)
        self._canvas.draw()

    # ── Frequency override entry ───────────────────────────────────────────────

    def _show_placeholder(self):
        if self._freqs_placeholder:
            text = ", ".join(_freq_label(f) for f in self._freqs_placeholder)
        else:
            text = "auto-detect"
        self._freqs_var.set(text)
        self._freqs_entry.config(fg=self.TEXT_DIM)
        self._using_placeholder = True

    def _on_freqs_focus_in(self, _event):
        if self._using_placeholder:
            self._freqs_var.set("")
            self._freqs_entry.config(fg=self.TEXT)
            self._using_placeholder = False

    def _on_freqs_focus_out(self, _event):
        if not self._freqs_var.get().strip():
            self._show_placeholder()

    def _detect_freqs(self, input_path):
        """Read the file, find distinct AC frequencies, update placeholder."""
        try:
            with open(input_path, "r") as fh:
                lines = fh.readlines()
            data_start = next(
                (i for i, l in enumerate(lines) if l.strip() == "[Data]"), None)
            if data_start is None:
                return
            df = pd.read_csv(input_path, skiprows=data_start + 1, sep=",",
                             low_memory=False)
            df.columns = [re.sub(r" {2,}", " ", c).strip() for c in df.columns]
            if "AC Frequency (Hz)" not in df.columns or "Transport Action" not in df.columns:
                return
            df = df[df["Transport Action"] == 1]
            freqs = sorted(df["AC Frequency (Hz)"].dropna().unique())
            if freqs:
                self._freqs_placeholder = freqs
                if self._using_placeholder:
                    self._show_placeholder()
        except Exception:
            pass

    def _parse_freq_override(self):
        """Return list of floats, None (auto), or False (parse error)."""
        if self._using_placeholder:
            return None
        raw = self._freqs_var.get().strip()
        if not raw:
            return None
        # Strip unit suffixes like "Hz" so users can paste labels back in
        cleaned = re.sub(r"[Hh][Zz]", "", raw)
        try:
            values = [float(v.strip()) for v in cleaned.split(",") if v.strip()]
            if not values:
                return None
            if any(v <= 0 for v in values):
                raise ValueError
            return values
        except ValueError:
            self._result_var.set(
                "✗  Frequencies must be comma-separated numbers, e.g. 10, 55, 300")
            self._result_lbl.config(fg=self.ERROR)
            return False

    # ── BaseModule overrides ───────────────────────────────────────────────────

    def _load_input(self, path):
        super()._load_input(path)
        self._detect_freqs(path)

    def _reset(self):
        self._reset_common()
        self._readout_mass.set("—")
        self._ax_prime.clear()
        self._ax_double.clear()
        self._refresh_ax()
        self._canvas.draw()
        self._show_placeholder()

    def _run(self):
        inp = self._input_path.get().strip()
        if not inp:
            self._result_var.set("✗  Please select an input file.")
            self._result_lbl.config(fg=self.ERROR)
            return
        freq_override = self._parse_freq_override()
        if freq_override is False:
            return
        self._start_conversion(inp, freq_override)

    def _process(self, inp, freq_override):
        return process_dat(inp, freq_override)

    def _done(self, rows, mass, csv_path, output_dir, df, freqs):
        self._readout_mass.set(f"{mass:.3f}" if mass else "not found")
        self._draw_preview(df, freqs)
        self._finish(rows, csv_path, output_dir)
