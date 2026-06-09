import os
import tkinter as tk
from tkinter import filedialog

from tkinterdnd2 import DND_FILES
from modules.base_gui import BaseModule, RoundedButton
from .processing import process, calibrate_alpha_fe, DEFAULT_VMAX

# ── Plot layout ───────────────────────────────────────────────────────────────
SPEC_KW = dict(left=0.08, right=0.975, top=0.91, bottom=0.15)

# ── Colour palette ────────────────────────────────────────────────────────────
SPEC_SCATTER = "#c8982a"    # gold  — data points
SPEC_LINE    = "#e8c060"    # light gold — smooth envelope


class MossbauerModule(BaseModule):
    def __init__(self, parent, status_cb=None, **kwargs):
        super().__init__(parent, status_cb, **kwargs)
        self._vmax_var          = tk.StringVar()
        self._vel_placeholder   = DEFAULT_VMAX
        self._using_placeholder = True
        self._cal_data_loaded   = None
        self._cal_filename_var  = tk.StringVar(value="")
        self._result            = None
        self._build()

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build(self):
        self._build_result_strip()
        self._build_controls()
        self._build_preview()
        self._show_vel_placeholder()

    def _build_controls(self):
        """Side-by-side: [sample file  |  velocity + cal browse] then [Fold & Save]."""
        strip = tk.Frame(self, bg=self.BG)
        strip.pack(pady=(self._s(20), self._s(10)), padx=self._s(40), fill="x")

        strip.columnconfigure(0, weight=3)
        strip.columnconfigure(1, minsize=self._s(28))
        strip.columnconfigure(2, weight=2)

        # ── Left: sample file input ───────────────────────────────────────
        left_hdr = tk.Frame(strip, bg=self.BG)
        left_hdr.grid(row=0, column=0, sticky="w", pady=(0, self._s(4)))
        tk.Label(left_hdr, text="INPUT FILE  (.DAT)",
                 font=self._f("Segoe UI Semibold", 8),
                 bg=self.BG, fg=self.TEXT_DIM).pack(side="left")
        tk.Label(left_hdr, text="·  Browse or Drag 'n Drop",
                 font=self._f("Segoe UI Semibold", 8),
                 bg=self.BG, fg=self.TEXT_DIM).pack(side="left",
                                                     padx=(self._s(8), 0))

        file_row = tk.Frame(strip, bg=self.BG)
        file_row.grid(row=1, column=0, sticky="ew")
        file_row.columnconfigure(0, weight=1)

        self._input_entry = tk.Entry(
            file_row, textvariable=self._input_path,
            font=self._f("Consolas", 10),
            bg=self.SURFACE, fg=self.TEXT, insertbackground=self.TEXT,
            relief="flat", highlightthickness=1,
            highlightbackground=self.BORDER, highlightcolor=self.ACCENT)
        self._input_entry.grid(row=0, column=0, sticky="ew",
                               ipady=self._s(8), ipadx=self._s(8))
        self._register_input_dnd(self._input_entry)
        self._pill_btn(file_row, "Browse", self._browse).grid(
            row=0, column=1, padx=(self._s(8), 0))

        # ── Right: velocity entry ─────────────────────────────────────────
        right_hdr = tk.Frame(strip, bg=self.BG)
        right_hdr.grid(row=0, column=2, sticky="ew", pady=(0, self._s(4)))
        # Cal filename indicator — packed right first so it anchors to the far right
        tk.Label(right_hdr, textvariable=self._cal_filename_var,
                 font=self._f("Segoe UI Semibold", 8),
                 bg=self.BG, fg=self.ACCENT).pack(side="right")
        tk.Label(right_hdr, text="VELOCITY  (mm/s)",
                 font=self._f("Segoe UI Semibold", 8),
                 bg=self.BG, fg=self.TEXT_DIM).pack(side="left")
        tk.Label(right_hdr, text="·  Drop α-Fe .dat to calibrate",
                 font=self._f("Segoe UI Semibold", 8),
                 bg=self.BG, fg=self.TEXT_DIM).pack(side="left",
                                                     padx=(self._s(8), 0))

        vel_row = tk.Frame(strip, bg=self.BG)
        vel_row.grid(row=1, column=2, sticky="ew")
        vel_row.columnconfigure(0, weight=1)

        self._vmax_entry = tk.Entry(
            vel_row, textvariable=self._vmax_var,
            font=self._f("Consolas", 10),
            bg=self.SURFACE, fg=self.TEXT, insertbackground=self.TEXT,
            relief="flat", highlightthickness=1,
            highlightbackground=self.BORDER, highlightcolor=self.ACCENT)
        self._vmax_entry.grid(row=0, column=0, sticky="ew",
                              ipady=self._s(8), ipadx=self._s(8))
        self._vmax_entry.bind("<FocusIn>",  self._on_vel_focus_in)
        self._vmax_entry.bind("<FocusOut>", self._on_vel_focus_out)
        self._register_cal_dnd(self._vmax_entry)

        self._pill_btn(vel_row, "Browse", self._browse_cal).grid(
            row=0, column=1, padx=(self._s(8), 0))

        # Cal status indicator
        self._cal_indicator = tk.StringVar(value="")
        tk.Label(strip, textvariable=self._cal_indicator,
                 font=self._f("Segoe UI", 7),
                 bg=self.BG, fg=self.ACCENT_DIM).grid(
            row=2, column=2, sticky="w", pady=(self._s(3), 0))

        # ── Fold & Save ───────────────────────────────────────────────────
        self._btn_run = RoundedButton(
            strip, text="Fold & Save", command=self._run,
            radius=5,
            bg=self.ACCENT, hover_bg=self.ACCENT_DIM,
            fg=self.BG,
            font=self._f("Segoe UI Semibold", 10),
            padx=self._s(20), pady=self._s(8))
        self._btn_run.grid(row=3, column=0, columnspan=3, sticky="e",
                           pady=(self._s(10), 0))

    # ── Preview canvas ────────────────────────────────────────────────────────

    def _build_preview(self):
        fig_frame = tk.Frame(self, bg=self.BG)
        fig_frame.pack(fill="both", expand=True,
                       padx=self._s(40), pady=(self._s(4), 0))
        self._subplot_kw = SPEC_KW
        self._fig, self._canvas = self._make_canvas(fig_frame)
        self._ax = self._fig.add_subplot(1, 1, 1)
        self._fig.subplots_adjust(**SPEC_KW)
        self._style_ax_spec()
        fig_frame.bind("<Configure>", self._on_resize)
        self._enable_zoom(self._ax)

    def _style_ax_spec(self):
        self._style_ax(self._ax, title="Folded Spectrum",
                       xlabel="Velocity (mm/s)", ylabel="Relative Transmission")

    def _on_resize(self, event):
        w = max(event.width,  200) / 96
        h = max(event.height, 200) / 96
        self._fig.set_size_inches(w, h)
        self._fig.subplots_adjust(**SPEC_KW)
        self._canvas.draw_idle()

    # ── Velocity placeholder ──────────────────────────────────────────────────

    def _show_vel_placeholder(self):
        self._vmax_var.set(f"{self._vel_placeholder:.3f}")
        self._vmax_entry.config(fg=self.TEXT_DIM)
        self._using_placeholder = True
        self._refresh_cal_indicator()

    def _refresh_cal_indicator(self):
        if self._using_placeholder and self._cal_data_loaded is not None:
            cal = self._cal_data_loaded
            self._cal_indicator.set(
                f"α-Fe calibrated  ·  DELV {abs(cal['slope']):.4f} mm/s/ch"
                f"  ·  RMS {cal['rms']:.3f} mm/s")
        else:
            self._cal_indicator.set("")

    def _on_vel_focus_in(self, event):
        if self._using_placeholder:
            self._vmax_var.set("")
            self._vmax_entry.config(fg=self.TEXT)
            self._using_placeholder = False
            self._cal_indicator.set("")

    def _on_vel_focus_out(self, event):
        if not self._vmax_var.get().strip():
            self._show_vel_placeholder()

    # ── Calibration-file detection ────────────────────────────────────────────

    def _detect_cal(self, path):
        try:
            cal = calibrate_alpha_fe(path)
            self._cal_data_loaded = cal
            self._vel_placeholder = cal["vmax"]
            self._cal_filename_var.set(f"✓  {os.path.basename(path)}")
            self._show_vel_placeholder()
        except Exception as exc:
            self._fail(f"Calibration failed — {os.path.basename(path)}: {exc}")

    def _browse_cal(self):
        path = filedialog.askopenfilename(
            title="Select α-Fe calibration .DAT",
            filetypes=[("DAT files", "*.dat *.DAT"), ("All files", "*.*")])
        if path:
            self._detect_cal(path)

    def _register_cal_dnd(self, widget):
        try:
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind("<<DropEnter>>",
                            lambda e: (widget.config(
                                highlightbackground=self.ACCENT), e.action)[1])
            widget.dnd_bind("<<DropLeave>>",
                            lambda e: (widget.config(
                                highlightbackground=self.BORDER), e.action)[1])
            widget.dnd_bind("<<Drop>>", self._on_cal_drop)
        except Exception:
            pass

    def _on_cal_drop(self, event):
        self._vmax_entry.config(highlightbackground=self.BORDER)
        try:
            paths = self.tk.splitlist(event.data)
        except Exception:
            paths = [event.data]
        if paths:
            self._detect_cal(paths[0])
        return event.action

    # ── Parse velocity params ─────────────────────────────────────────────────

    def _get_vel_params(self):
        if self._using_placeholder:
            return self._vel_placeholder, self._cal_data_loaded
        raw = self._vmax_var.get().strip()
        try:
            vmax = float(raw)
            if vmax <= 0:
                raise ValueError
            return vmax, None
        except ValueError:
            self._fail("Velocity must be a positive number (mm/s).")
            return None, None

    # ── Run / worker / done ───────────────────────────────────────────────────

    def _run(self):
        inp = self._input_path.get().strip()
        if not inp:
            self._fail("Please select an input file.")
            return
        vmax, cal_data = self._get_vel_params()
        if vmax is None:
            return
        self._start_conversion(inp, vmax, cal_data)

    def _fail(self, msg):
        self._result_var.set(f"✗  {msg}")
        self._result_lbl.config(fg=self.ERROR)

    def _process(self, inp, vmax, cal_data):
        return (process(inp, vmax, cal_data=cal_data),)

    def _done(self, result):
        self._result = result
        self._draw(result)
        self._finish(result["rows"], result["csv_path"], result["output_dir"])
        if result["cal"] is not None:
            cal = result["cal"]
            self._status_cb(
                f"✓  Calibrated · DELV {result['delv']:.4f} mm/s/ch · "
                f"RMS {cal['rms']:.3f} mm/s  ·  {result['output_dir']}",
                self.SUCCESS)

    def _finish(self, rows, csv_path, output_dir):
        super()._finish(rows, csv_path, output_dir)
        self._btn_run.config(state="normal", text="Fold & Save")

    def _error(self, msg):
        super()._error(msg)
        self._btn_run.config(text="Fold & Save")

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _draw(self, r):
        self._ax.clear()
        self._style_ax_spec()

        v, t, st = r["velocity"], r["transmission"], r["smooth_transmission"]
        self._ax.scatter(v, t, color=SPEC_SCATTER, s=9, alpha=0.55,
                         linewidths=0, zorder=3, label="Data")
        self._ax.plot(v, st, color=SPEC_LINE, linewidth=1.6, zorder=4,
                      label="Smoothed")
        self._ax.axvline(0, color=self.BORDER, linewidth=0.7, zorder=2)
        self._ax.legend(fontsize=self._mpl(7), facecolor=self.SURFACE,
                        edgecolor=self.BORDER, labelcolor=self.TEXT,
                        loc="upper right")

        lo, hi = float(t.min()), float(t.max())
        pad = max((hi - lo) * 0.10, 0.001)
        self._ax.set_ylim(lo - pad, hi + pad)

        self._fig.subplots_adjust(**SPEC_KW)
        self._canvas.draw_idle()

    # ── Reset ─────────────────────────────────────────────────────────────────

    def _reset(self):
        self._reset_common()
        self._cal_filename_var.set("")
        self._ax.clear()
        self._style_ax_spec()
        self._result = None
        self._canvas.draw_idle()
