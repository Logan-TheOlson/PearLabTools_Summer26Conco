import tkinter as tk
from modules.base_gui import BaseModule
from .processing import process_dat

SUBPLOT_KW  = dict(left=0.12, right=0.97, top=0.91, bottom=0.18)
ACCENT_LINE = "#a07820"


class LT1TModule(BaseModule):
    def __init__(self, parent, status_cb=None, **kwargs):
        super().__init__(parent, status_cb, **kwargs)
        self._build()

    def _build(self):
        self._build_result_strip()
        self._build_controls()
        self._build_preview()

    def _build_preview(self):
        fig_frame = tk.Frame(self, bg=self.BG)
        fig_frame.pack(fill="both", expand=True,
                       padx=self._s(40), pady=(self._s(10), 0))
        self._subplot_kw = SUBPLOT_KW
        self._fig, self._canvas = self._make_canvas(fig_frame)
        self._ax = self._fig.add_subplot(1, 1, 1)
        self._fig.subplots_adjust(**SUBPLOT_KW)
        self._refresh_ax()
        fig_frame.bind("<Configure>", self._on_resize)
        self._enable_zoom(self._ax)

    def _refresh_ax(self):
        self._style_ax(self._ax,
                       title="Magnetization vs Temperature",
                       xlabel="Temperature (K)",
                       ylabel="Magnetization (A m²/kg)")

    def _draw_preview(self, df):
        self._ax.clear()
        self._refresh_ax()
        x, y = df["Temperature (K)"], df["Magnetization (A m^2/kg)"]
        self._ax.plot(x, y, color=ACCENT_LINE, linewidth=1.2, zorder=1)
        self._ax.scatter(x, y, color=self.ACCENT,
                         s=self._s(18), zorder=2, linewidths=0)
        self._canvas.draw()

    def _process(self, inp):   return process_dat(inp)
    def _done(self, rows, mass, csv_path, output_dir, df):
        self._readout_mass.set(f"{mass:.3f}" if mass else "not found")
        self._draw_preview(df)
        self._finish(rows, csv_path, output_dir)
