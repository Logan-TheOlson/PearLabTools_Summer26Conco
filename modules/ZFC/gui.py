import tkinter as tk

from modules.base_gui import BaseModule
from .processing import process_dat

SUBPLOT_KW = dict(left=0.12, right=0.97, top=0.91, bottom=0.18)
COLOR_ZFC  = "#f5883a"
COLOR_FC   = "#6ba3f5"


class ZFCModule(BaseModule):
    def __init__(self, parent, status_cb=None, **kwargs):
        super().__init__(parent, status_cb, **kwargs)
        self._build()

    def _build(self):
        self._build_result_strip()
        self._build_controls()
        self._build_preview()

    def _build_controls(self):
        strip = tk.Frame(self, bg=self.BG)
        strip.pack(pady=(20, 12), padx=40, fill="x")
        strip.columnconfigure(0, weight=1)
        self._build_file_row(strip, grid_row=0)
        self._build_action_row(strip, grid_row=2)

    def _build_preview(self):
        fig_frame = tk.Frame(self, bg=self.BG)
        fig_frame.pack(fill="both", expand=True, padx=28, pady=(10, 0))
        self._subplot_kw = SUBPLOT_KW
        self._fig, self._canvas = self._make_canvas(fig_frame)
        self._ax = self._fig.add_subplot(1, 1, 1)
        self._fig.subplots_adjust(**SUBPLOT_KW)
        self._refresh_ax()
        fig_frame.bind("<Configure>", self._on_resize)

    def _refresh_ax(self):
        self._style_ax(self._ax, title="ZFC / FC Magnetization vs Temperature",
                       xlabel="Temperature (K)",
                       ylabel="Magnetization (A m²/kg)")

    def _draw_preview(self, df):
        self._ax.clear()
        self._refresh_ax()
        x = df["Temperature (K)"]
        for col, color, label in (
            ("Magnetization ZFC (A m^2/kg)", COLOR_ZFC, "ZFC"),
            ("Magnetization FC (A m^2/kg)",  COLOR_FC,  "FC"),
        ):
            self._ax.plot(x, df[col], color=color, linewidth=1.2, zorder=1)
            self._ax.scatter(x, df[col], color=color, s=18, zorder=2,
                             linewidths=0, label=label)
        self._ax.legend(fontsize=7.5, facecolor=self.SURFACE,
                        edgecolor=self.BORDER, labelcolor=self.TEXT)
        self._canvas.draw()

    def _reset(self):
        self._reset_common()
        self._readout_mass.set("—")
        self._ax.clear()
        self._refresh_ax()
        self._canvas.draw()

    def _run(self):
        inp = self._input_path.get().strip()
        if not inp:
            self._result_var.set("✗  Please select an input file.")
            self._result_lbl.config(fg=self.ERROR)
            return
        self._start_conversion(inp)

    def _process(self, inp):
        return process_dat(inp)

    def _done(self, rows, mass, csv_path, output_dir, df):
        self._readout_mass.set(f"{mass}" if mass else "not found")
        self._draw_preview(df)
        self._finish(rows, csv_path, output_dir)
