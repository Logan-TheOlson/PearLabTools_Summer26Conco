import tkinter as tk
import pandas as pd

from modules.base_gui import BaseModule
from .processing import process_dat, DEFAULT_BANDS

BAND_COLOR_CYCLE = [
    "#6ba3f5", "#5dd6a0", "#f5c842", "#f07070",
    "#b39dff", "#fd9b5a", "#4dd9e8", "#f472d0",
]

SUBPLOT_KW = dict(left=0.13, right=0.97, top=0.91, bottom=0.18, wspace=0.35)


def band_color(label, band_labels):
    idx = band_labels.index(label) if label in band_labels else 0
    return BAND_COLOR_CYCLE[idx % len(BAND_COLOR_CYCLE)]


class VSMModule(BaseModule):
    def __init__(self, parent, status_cb=None, **kwargs):
        super().__init__(parent, status_cb, **kwargs)
        self._bands_var         = tk.StringVar(value="")
        self._bands_placeholder = list(DEFAULT_BANDS)
        self._using_placeholder = True
        self._plot_data         = None
        self._band_labels       = []
        self._remove_para_var   = tk.BooleanVar(value=True)
        self._build()
        self._show_placeholder()

    def _build(self):
        self._build_result_strip()
        self._build_controls()
        self._build_readouts()
        self._build_preview()

    def _build_controls(self):
        strip = tk.Frame(self, bg=self.BG)
        strip.pack(pady=(self._s(20), self._s(12)), padx=self._s(40), fill="x")
        strip.columnconfigure(0, weight=1)
        self._build_file_row(strip, grid_row=0)

        tk.Label(strip, text="TEMPERATURE BANDS  (K, comma-separated)",
                 font=self._f("Segoe UI Semibold", 8),
                 bg=self.BG, fg=self.TEXT_DIM).grid(
                 row=2, column=0, sticky="w", pady=(0, self._s(4)))
        action_row = tk.Frame(strip, bg=self.BG)
        action_row.grid(row=3, column=0, sticky="ew")
        action_row.columnconfigure(0, weight=1)

        self._bands_entry = tk.Entry(action_row, textvariable=self._bands_var,
                                     font=self._f("Consolas", 10),
                                     bg=self.SURFACE, fg=self.TEXT,
                                     insertbackground=self.TEXT, relief="flat",
                                     highlightthickness=1,
                                     highlightbackground=self.BORDER,
                                     highlightcolor=self.ACCENT)
        self._bands_entry.grid(row=0, column=0, sticky="ew",
                               ipady=self._s(8), ipadx=self._s(8))
        self._bands_entry.bind("<FocusIn>",  self._on_bands_focus_in)
        self._bands_entry.bind("<FocusOut>", self._on_bands_focus_out)

        chk_wrap = tk.Frame(action_row, bg=self.BG, cursor="hand2")
        chk_wrap.grid(row=0, column=1, padx=(self._s(14), 0))
        self._chk_canvas = self._make_checkbox_canvas(chk_wrap, self._remove_para_var)
        self._chk_canvas.pack(side="left", padx=(0, self._s(6)))
        chk_lbl = tk.Label(chk_wrap, text="REMOVE PARAMAGNETIC\nCONTRIBUTION",
                           font=self._f("Segoe UI Semibold", 8),
                           bg=self.BG, fg=self.TEXT_DIM, justify="left",
                           cursor="hand2")
        chk_lbl.pack(side="left")
        chk_lbl.bind("<Button-1>", lambda e: self._toggle_para())

        self._btn_run = tk.Button(action_row, text="Convert & Save",
                                  font=self._f("Segoe UI Semibold", 10),
                                  bg=self.ACCENT, fg=self.BG, relief="flat",
                                  activebackground=self.ACCENT_DIM,
                                  activeforeground=self.TEXT,
                                  cursor="hand2", command=self._run,
                                  padx=self._s(20), pady=self._s(8))
        self._btn_run.grid(row=0, column=2, padx=(self._s(10), 0))

    def _build_readouts(self):
        readout_row = tk.Frame(self, bg=self.BG)
        readout_row.pack(padx=self._s(40), pady=(0, self._s(8)), fill="x")
        self._readout_mass = tk.StringVar(value="—")
        self._metric_cards = [
            ("SAMPLE MASS",              "mg",           None,  1),
            ("SATURATION MAGNETIZATION", "A m²/kg", "Ms",  1),
            ("REMANENT MAGNETIZATION",   "A m²/kg", "Mr",  1),
            ("COERCIVE FIELD",           "mT",           "Hc",  1000),
        ]
        self._param_frames = {}
        p = self._s(10)
        for i, (title, unit, key, _) in enumerate(self._metric_cards):
            last = i == len(self._metric_cards) - 1
            card = tk.Frame(readout_row, bg=self.SURFACE,
                            highlightthickness=1, highlightbackground=self.BORDER)
            card.grid(row=0, column=i, sticky="nsew",
                      padx=(0, 0 if last else self._s(8)))
            readout_row.columnconfigure(i, weight=1)
            tk.Label(card, text=title, font=self._f("Segoe UI Semibold", 7),
                     bg=self.SURFACE, fg=self.TEXT_DIM).pack(
                     anchor="w", padx=p, pady=(self._s(8), self._s(4)))
            if key is None:
                tk.Label(card, textvariable=self._readout_mass,
                         font=self._f("Consolas", 13),
                         bg=self.SURFACE, fg=self.TEXT).pack(anchor="w", padx=p)
            else:
                content = tk.Frame(card, bg=self.SURFACE)
                content.pack(fill="x", padx=p)
                self._param_frames[key] = content
                tk.Label(content, text="—", font=self._f("Consolas", 11),
                         bg=self.SURFACE, fg=self.TEXT_DIM).pack(anchor="w")
            tk.Label(card, text=unit, font=self._f("Segoe UI", 7),
                     bg=self.SURFACE, fg=self.TEXT_DIM).pack(
                     anchor="w", padx=p, pady=(self._s(2), self._s(8)))

    def _build_preview(self):
        fig_frame = tk.Frame(self, bg=self.BG)
        fig_frame.pack(fill="both", expand=True,
                       padx=self._s(28), pady=(self._s(10), 0))
        self._subplot_kw = SUBPLOT_KW
        self._fig, self._canvas = self._make_canvas(fig_frame)
        self._ax_raw  = self._fig.add_subplot(1, 2, 1)
        self._ax_corr = self._fig.add_subplot(1, 2, 2)
        self._fig.text(0.02, 0.5, "Magnetization (A m²/kg)",
                       va="center", ha="left", rotation="vertical",
                       fontsize=self._mpl(8), color=self.TEXT_DIM)
        self._fig.subplots_adjust(**SUBPLOT_KW)
        self._style_axes()
        self._on_para_toggle()
        fig_frame.bind("<Configure>", self._on_resize)

    def _make_checkbox_canvas(self, parent, var):
        size = self._s(20)
        c = tk.Canvas(parent, width=size, height=size,
                      bg=self.BG, highlightthickness=0, cursor="hand2")
        c._var  = var
        c._size = size
        var.trace_add("write", lambda *_: self._redraw_checkbox(c))
        c.bind("<Button-1>", lambda e: self._toggle_para())
        self._redraw_checkbox(c)
        return c

    def _redraw_checkbox(self, c):
        c.delete("all")
        s = c._size
        pad = max(1, self._s(2))
        c.create_rectangle(pad, pad, s - pad, s - pad,
                           outline=self.BORDER, fill=self.SURFACE, width=self._s(1))
        if c._var.get():
            m = s * 0.18
            c.create_line(m, s * 0.5, s * 0.4, s - m, s - m, m,
                          fill=self.ACCENT, width=self._s(2),
                          capstyle="round", joinstyle="round")

    def _toggle_para(self):
        self._remove_para_var.set(not self._remove_para_var.get())
        self._on_para_toggle()

    def _on_para_toggle(self):
        show = self._remove_para_var.get()
        self._ax_corr.set_visible(show)
        kw = SUBPLOT_KW
        if show:
            self._fig.subplots_adjust(**kw)
        else:
            self._ax_raw.set_position([kw["left"], kw["bottom"],
                                       kw["right"] - kw["left"],
                                       kw["top"] - kw["bottom"]])
        self._canvas.draw_idle()

    def _style_axes(self):
        corr_title = ("Paramagnetic Contribution Removed"
                      if self._remove_para_var.get()
                      else "Hysteresis Loops (No Correction)")
        for ax, title in ((self._ax_raw,  "Original Hysteresis Loops"),
                          (self._ax_corr, corr_title)):
            self._style_ax(ax, title=title, xlabel="Field (T)")
            ax.axhline(0, color=self.BORDER, linewidth=0.8)
            ax.axvline(0, color=self.BORDER, linewidth=0.8)

    def _draw_preview(self):
        self._ax_raw.clear()
        self._ax_corr.clear()
        self._style_axes()
        all_y_raw, all_y_corr = [], []
        for label in self._band_labels:
            data = self._plot_data.get(label)
            if data is None or data["x"] is None:
                continue
            all_y_raw.extend(data["y"])
            all_y_corr.extend(data["corrected"] if data["corrected"] is not None else data["y"])
        for label in self._band_labels:
            data = self._plot_data.get(label)
            if data is None or data["x"] is None:
                continue
            color = band_color(label, self._band_labels)
            self._ax_raw.plot(data["x"], data["y"], color=color,
                              linewidth=1.4, label=label)
            if data["corrected"] is not None:
                self._ax_corr.plot(data["x"], data["corrected"],
                                   color=color, linewidth=1.4, label=label)
            else:
                self._ax_corr.plot(data["x"], data["y"], color=color,
                                   linewidth=1.4, linestyle="--", alpha=0.5,
                                   label=f"{label} (no correction)")
        if all_y_raw and all_y_corr:
            y_min = min(min(all_y_raw), min(all_y_corr))
            y_max = max(max(all_y_raw), max(all_y_corr))
            pad   = (y_max - y_min) * 0.06
            for ax in (self._ax_raw, self._ax_corr):
                ax.set_ylim(y_min - pad, y_max + pad)
        for ax in (self._ax_raw, self._ax_corr):
            ax.legend(fontsize=self._mpl(7.5), facecolor=self.SURFACE,
                      edgecolor=self.BORDER, labelcolor=self.TEXT)
        self._on_para_toggle()

    def _update_readouts(self, band_labels, plot_data, mass):
        self._readout_mass.set(f"{mass:.3f}" if mass else "not found")
        for _, _, key, scale in self._metric_cards:
            if key is None:
                continue
            frame = self._param_frames[key]
            for w in frame.winfo_children():
                w.destroy()
            for label in band_labels:
                val = (plot_data.get(label) or {}).get(key)
                row = tk.Frame(frame, bg=self.SURFACE)
                row.pack(fill="x", pady=1)
                tk.Label(row, text=label, font=self._f("Segoe UI", 8),
                         bg=self.SURFACE, fg=self.TEXT_DIM,
                         width=6, anchor="w").pack(side="left")
                tk.Label(row,
                         text=f"{val * scale:.3f}" if val is not None else "—",
                         font=self._f("Consolas", 11),
                         bg=self.SURFACE,
                         fg=self.TEXT if val is not None else self.TEXT_DIM,
                         anchor="e").pack(side="right")

    def _show_placeholder(self):
        self._bands_var.set(", ".join(str(t) for t in self._bands_placeholder))
        self._bands_entry.config(fg=self.TEXT_DIM)
        self._using_placeholder = True

    def _on_bands_focus_in(self, event):
        if self._using_placeholder:
            self._bands_var.set("")
            self._bands_entry.config(fg=self.TEXT)
            self._using_placeholder = False

    def _on_bands_focus_out(self, event):
        if not self._bands_var.get().strip():
            self._show_placeholder()

    def _detect_bands(self, input_path):
        try:
            import pandas as pd
            with open(input_path, "r") as f:
                lines = f.readlines()
            data_start = next(
                (i for i, l in enumerate(lines) if l.strip() == "[Data]"), None)
            if data_start is None:
                return
            df = pd.read_csv(input_path, skiprows=data_start + 1, sep=",",
                             usecols=["Temperature (K)", "Moment (emu)"])
            df = df.dropna(subset=["Moment (emu)"])
            df = df.loc[df["Moment (emu)"].astype(float) != 0]
            bands = sorted(set(round(t / 10) * 10
                               for t in df["Temperature (K)"].astype(float)))
            if bands:
                self._bands_placeholder = bands
                if self._using_placeholder:
                    self._show_placeholder()
        except Exception:
            pass

    def _parse_band_temps(self):
        if self._using_placeholder:
            return list(self._bands_placeholder)
        raw = self._bands_var.get()
        try:
            temps = [int(t.strip()) for t in raw.split(",") if t.strip()]
            if not temps:
                raise ValueError
            return temps
        except ValueError:
            self._result_var.set("✗  Bands must be comma-separated integers, e.g. 50, 150, 300")
            self._result_lbl.config(fg=self.ERROR)
            return None

    def _browse(self):
        super()._browse()
        if self._input_path.get():
            self._detect_bands(self._input_path.get())

    def _reset(self):
        self._reset_common()
        self._readout_mass.set("—")
        for key, frame in self._param_frames.items():
            for w in frame.winfo_children():
                w.destroy()
            tk.Label(frame, text="—", font=self._f("Consolas", 11),
                     bg=self.SURFACE, fg=self.TEXT_DIM).pack(anchor="w")
        self._ax_raw.clear()
        self._ax_corr.clear()
        self._style_axes()
        self._on_para_toggle()
        self._plot_data   = None
        self._band_labels = []
        self._show_placeholder()

    def _run(self):
        inp = self._input_path.get().strip()
        if not inp:
            self._result_var.set("✗  Please select an input file.")
            self._result_lbl.config(fg=self.ERROR)
            return
        band_temps = self._parse_band_temps()
        if band_temps is None:
            return
        remove_para = self._remove_para_var.get()
        self._start_conversion(inp, band_temps, remove_para)

    def _process(self, inp, band_temps, remove_para):
        return process_dat(inp, band_temps, remove_paramagnetic=remove_para)

    def _done(self, rows, mass, csv_path, output_dir, plot_data, band_ranges):
        self._plot_data   = plot_data
        self._band_labels = [label for label, *_ in band_ranges]
        self._draw_preview()
        self._update_readouts(self._band_labels, plot_data, mass)
        self._finish(rows, csv_path, output_dir)
