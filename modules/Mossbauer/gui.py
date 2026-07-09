import os
import tkinter as tk
from tkinter import filedialog

from tkinterdnd2 import DND_FILES
from modules.base_gui import BaseModule, RoundedButton
from .processing import (process, calibrate_alpha_fe, fit_sites,
                         fit_distribution, DEFAULT_VMAX)

# ── Plot layout ───────────────────────────────────────────────────────────────
SPEC_KW = dict(left=0.08, right=0.975, top=0.91, bottom=0.15)

# ── Colour palette ────────────────────────────────────────────────────────────
SPEC_SCATTER = "#c8982a"    # gold  — data points
SPEC_LINE    = "#e8c060"    # light gold — smooth envelope
SPEC_FIT     = "#d65f5f"    # soft red  — Lorentzian fit curve
SPEC_FIT_CMP = "#8a4a44"    # dim red   — individual fit components


class MossbauerModule(BaseModule):
    def __init__(self, parent, status_cb=None, **kwargs):
        super().__init__(parent, status_cb, **kwargs)
        self._vmax_var          = tk.StringVar()
        self._vel_placeholder   = DEFAULT_VMAX
        self._using_placeholder = True
        self._cal_data_loaded   = None
        self._cal_filename_var  = tk.StringVar(value="")
        self._result            = None
        self._fit_result        = None
        # Crystalline-site starting values (ISX,QUX pairs) from L6.JOB.
        self._sites_var         = tk.StringVar(
            value="0.90,2.50; 1.00,1.50; 0.26,0.55; 1.10,2.20")
        self._swid_var          = tk.StringVar(value="0.45")
        self._fit_wid           = False
        self._dist_result       = None
        self._dist_ax           = None
        self._dist_kind         = "qs"
        self._dist_vars = {k: tk.StringVar(value=v) for k, v in (
            ("x0", "0.0"), ("dx", "0.1"), ("nsb", "18"), ("wid", "0.45"),
            ("lam", "0.5"), ("iso", "0.3"), ("qua", "0.0"), ("a23", "2.0"))}
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
        self._cal_indicator_lbl = tk.Label(
            strip, textvariable=self._cal_indicator,
            font=self._f("Segoe UI", 7),
            bg=self.BG, fg=self.ACCENT_DIM)
        self._cal_indicator_lbl.grid(row=2, column=2, sticky="w",
                                     pady=(self._s(3), 0))

        # ── Crystalline-site fit controls (left) + Fold & Save (right) ────
        fit_row = tk.Frame(strip, bg=self.BG)
        fit_row.grid(row=3, column=0, sticky="w", pady=(self._s(10), 0))
        tk.Label(fit_row, text="XTAL SITES  ·  ISX,QUX ; …",
                 font=self._f("Segoe UI Semibold", 8),
                 bg=self.BG, fg=self.TEXT_DIM).pack(side="left",
                                                    padx=(0, self._s(8)))
        self._sites_entry = tk.Entry(
            fit_row, textvariable=self._sites_var, width=34,
            font=self._f("Consolas", 9),
            bg=self.SURFACE, fg=self.TEXT, insertbackground=self.TEXT,
            relief="flat", highlightthickness=1,
            highlightbackground=self.BORDER, highlightcolor=self.ACCENT)
        self._sites_entry.pack(side="left", ipady=self._s(5))
        tk.Label(fit_row, text="WID",
                 font=self._f("Segoe UI Semibold", 8),
                 bg=self.BG, fg=self.TEXT_DIM).pack(side="left",
                                                    padx=(self._s(8), self._s(4)))
        tk.Entry(fit_row, textvariable=self._swid_var, width=6,
                 justify="center", font=self._f("Consolas", 9),
                 bg=self.SURFACE, fg=self.TEXT, insertbackground=self.TEXT,
                 relief="flat", highlightthickness=1,
                 highlightbackground=self.BORDER,
                 highlightcolor=self.ACCENT).pack(side="left", ipady=self._s(5))
        self._btn_wid_mode = self._pill_btn(fit_row, "WID fixed",
                                            self._toggle_wid_mode)
        self._btn_wid_mode.pack(side="left", padx=(self._s(6), 0))
        self._btn_fit = self._pill_btn(fit_row, "Fit Sites", self._fit)
        self._btn_fit.pack(side="left", padx=(self._s(8), 0))

        self._btn_run = RoundedButton(
            strip, text="Fold & Save", command=self._run,
            radius=5,
            bg=self.ACCENT, hover_bg=self.ACCENT_DIM,
            fg=self.BG,
            font=self._f("Segoe UI Semibold", 10),
            padx=self._s(20), pady=self._s(8))
        self._btn_run.grid(row=3, column=1, columnspan=2, sticky="e",
                           pady=(self._s(10), 0))

        # ── Distribution fit controls (NORMOS-DIST style) ─────────────────
        dist_row = tk.Frame(strip, bg=self.BG)
        dist_row.grid(row=4, column=0, columnspan=3, sticky="w",
                      pady=(self._s(10), 0))
        tk.Label(dist_row, text="DISTRIBUTION",
                 font=self._f("Segoe UI Semibold", 8),
                 bg=self.BG, fg=self.TEXT_DIM).pack(
            side="left", padx=(0, self._s(8)), anchor="s", pady=(0, self._s(4)))
        self._btn_dist_kind = self._pill_btn(dist_row, "QS doublets",
                                             self._toggle_dist_kind)
        self._btn_dist_kind.pack(side="left", padx=(0, self._s(10)),
                                 anchor="s")
        for key, label in (("x0", "START"), ("dx", "STEP"), ("nsb", "BINS"),
                           ("wid", "WID"), ("lam", "LAMBDA"), ("iso", "ISO₀"),
                           ("qua", "QUA"), ("a23", "A23")):
            self._mini_entry(dist_row, label, self._dist_vars[key]).pack(
                side="left", padx=(0, self._s(6)))
        self._btn_dist = self._pill_btn(dist_row, "Fit Distribution",
                                        self._fit_dist)
        self._btn_dist.pack(side="left", padx=(self._s(6), 0), anchor="s")

    def _mini_entry(self, parent, label, var, width=6):
        f = tk.Frame(parent, bg=self.BG)
        tk.Label(f, text=label, font=self._f("Segoe UI Semibold", 7),
                 bg=self.BG, fg=self.TEXT_DIM).pack(anchor="w")
        tk.Entry(f, textvariable=var, width=width, justify="center",
                 font=self._f("Consolas", 9),
                 bg=self.SURFACE, fg=self.TEXT, insertbackground=self.TEXT,
                 relief="flat", highlightthickness=1,
                 highlightbackground=self.BORDER,
                 highlightcolor=self.ACCENT).pack(ipady=self._s(4))
        return f

    def _toggle_dist_kind(self):
        self._dist_kind = "bhf" if self._dist_kind == "qs" else "qs"
        self._btn_dist_kind.config(
            text="BHF sextets" if self._dist_kind == "bhf" else "QS doublets")

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
            txt = (f"α-Fe calibrated  ·  DELV {abs(cal['slope']):.4f} mm/s/ch"
                   f"  ·  RMS {cal['rms']:.3f} mm/s"
                   f"  ·  NL {cal['nl_max_dev']:.3f} mm/s")
            if cal.get("nl_warn"):
                txt += "  ⚠ drive nonlinearity"
            self._cal_indicator.set(txt)
            self._cal_indicator_lbl.config(
                fg=self.ERROR if cal.get("nl_warn") else self.ACCENT_DIM)
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
        self._fit_result  = None
        self._dist_result = None
        self._start_conversion(inp, vmax, cal_data)

    def _fail(self, msg):
        self._result_var.set(f"✗  {msg}")
        self._result_lbl.config(fg=self.ERROR)

    # ── Crystalline-site fit (NORMOS xtal doublets) ───────────────────────────

    def _toggle_wid_mode(self):
        self._fit_wid = not self._fit_wid
        self._btn_wid_mode.config(
            text="WID fit" if self._fit_wid else "WID fixed")

    def _parse_sites(self):
        """Parse 'ISX,QUX; ISX,QUX; …' into a list of (isx, qux) pairs."""
        sites = []
        for chunk in self._sites_var.get().split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            parts = chunk.split(",")
            if len(parts) != 2:
                raise ValueError(chunk)
            isx, qux = float(parts[0]), float(parts[1])
            if qux < 0:
                raise ValueError(chunk)
            sites.append((isx, qux))
        if not sites:
            raise ValueError("no sites")
        return sites

    def _fit(self):
        if self._result is None:
            self._fail("Fold a spectrum first.")
            return
        try:
            sites0 = self._parse_sites()
        except ValueError:
            self._fail("Sites must be 'ISX,QUX' pairs separated by ';' "
                       "(e.g. 0.90,2.50; 1.00,1.50).")
            return
        try:
            wid = float(self._swid_var.get())
            if wid <= 0:
                raise ValueError
        except ValueError:
            self._fail("WID must be a positive number (mm/s).")
            return
        try:
            fit = fit_sites(self._result, sites0, wid=wid,
                            fit_wid=self._fit_wid)
        except Exception as exc:
            self._fail(f"Fit failed: {exc}")
            return
        self._fit_result  = fit
        self._dist_result = None
        self._draw(self._result)
        self._drag_chip.set_path(fit["csv_path"])
        n = len(fit["sites"])
        wid_txt = (f"{fit['wid']:.3f}±{fit['wid_err']:.3f}"
                   if fit["fit_wid"] else f"{fit['wid']:.3f} (fixed)")
        self._result_var.set(
            f"✓  Fit {n} site{'s' if n > 1 else ''}"
            f"  ·  WID {wid_txt} mm/s"
            f"  ·  χ²ᵣ {fit['chi2_norm']:.2f}"
            f"  ·  {fit['csv_path']}")
        self._result_lbl.config(fg=self.SUCCESS)
        summary = "   ".join(
            f"S{i + 1}: ISX {s['isx']:+.3f} QUX {s['qux']:.3f} "
            f"A {s['rel_area']:.0f}%"
            for i, s in enumerate(fit["sites"]))
        self._status_cb(f"✓  {summary}", self.SUCCESS)

    # ── Distribution fit (NORMOS-DIST style) ──────────────────────────────────

    def _fit_dist(self):
        if self._result is None:
            self._fail("Fold a spectrum first.")
            return
        try:
            gv = self._dist_vars
            kw = dict(kind=self._dist_kind,
                      x0=float(gv["x0"].get()),  dx=float(gv["dx"].get()),
                      nsb=int(gv["nsb"].get()),  wid=float(gv["wid"].get()),
                      lam=float(gv["lam"].get()), iso0=float(gv["iso"].get()),
                      qua=float(gv["qua"].get()), a23=float(gv["a23"].get()))
            if kw["nsb"] < 3 or kw["dx"] <= 0 or kw["wid"] <= 0 or kw["lam"] < 0:
                raise ValueError
        except ValueError:
            self._fail("Check distribution parameters (BINS ≥ 3, STEP > 0, "
                       "WID > 0, LAMBDA ≥ 0).")
            return
        self._btn_dist.config(state="disabled", text="Fitting…")
        self.update_idletasks()
        try:
            dist = fit_distribution(self._result, **kw)
        except Exception as exc:
            self._fail(f"Distribution fit failed: {exc}")
            return
        finally:
            self._btn_dist.config(state="normal", text="Fit Distribution")
        self._dist_result = dist
        self._fit_result  = None
        self._draw(self._result)
        self._drag_chip.set_path(dist["csv_path"])
        s = dist["stats"]
        self._result_var.set(
            f"✓  Dist fit  ·  ISO {dist['iso']:.4f}±{dist['iso_err']:.4f}"
            f"  ·  ⟨x⟩ {s['mean']:.3f}  σ {s['std']:.3f}"
            f"  ·  χ²ᵣ {dist['chi2_norm']:.2f}  ·  {dist['csv_path']}")
        self._result_lbl.config(fg=self.SUCCESS)
        self._status_cb(
            f"✓  {dist['xname']}: mean {s['mean']:.3f} · median {s['median']:.3f}"
            f" · std {s['std']:.3f} · skew {s['skew']:.2f}"
            f"  ·  report: {dist['report_path']}", self.SUCCESS)

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

    def _remove_dist_inset(self):
        if self._dist_ax is not None:
            try:
                self._dist_ax.remove()
            except Exception:
                pass
            self._dist_ax = None

    def _draw(self, r):
        self._ax.clear()
        self._remove_dist_inset()
        self._style_ax_spec()

        v, t, st = r["velocity"], r["transmission"], r["smooth_transmission"]
        self._ax.scatter(v, t, color=SPEC_SCATTER, s=9, alpha=0.55,
                         linewidths=0, zorder=3, label="Data")
        self._ax.plot(v, st, color=SPEC_LINE, linewidth=1.6, zorder=4,
                      label="Smoothed")
        self._ax.axvline(0, color=self.BORDER, linewidth=0.7, zorder=2)

        if self._fit_result is not None:
            fit = self._fit_result
            b   = fit["baseline"]
            for i, s in enumerate(fit["sites"]):
                self._ax.plot(v, b - s["component"], color=SPEC_FIT_CMP,
                              linewidth=0.9, linestyle="--", alpha=0.6,
                              zorder=4, label=f"Site {i + 1}")
                for pos in (s["isx"] - s["qux"] / 2.0,
                            s["isx"] + s["qux"] / 2.0):
                    self._ax.axvline(pos, color=SPEC_FIT_CMP,
                                     linewidth=0.7, alpha=0.4, zorder=2)
            self._ax.plot(v, fit["curve"], color=SPEC_FIT, linewidth=1.7,
                          zorder=5, label="Fit")

        if self._dist_result is not None:
            dr = self._dist_result
            self._ax.plot(v, dr["curve"], color=SPEC_FIT, linewidth=1.7,
                          zorder=5, label="Dist fit")
            # P(x) inset, upper-left inside the spectrum axes
            self._dist_ax = self._fig.add_axes([0.13, 0.56, 0.24, 0.30])
            da = self._dist_ax
            da.set_facecolor(self.SURFACE)
            da.tick_params(colors=self.TEXT_DIM, labelsize=self._mpl(6))
            for spine in da.spines.values():
                spine.set_edgecolor(self.BORDER)
            da.fill_between(dr["x"], dr["p_density"], step="mid",
                            color=SPEC_FIT, alpha=0.30)
            da.step(dr["x"], dr["p_density"], where="mid",
                    color=SPEC_FIT, linewidth=1.2)
            da.set_xlabel(dr["xname"], fontsize=self._mpl(6.5),
                          color=self.TEXT_DIM)
            da.set_ylabel("P(x)", fontsize=self._mpl(6.5),
                          color=self.TEXT_DIM)
            da.grid(True, color=self.GRID_COLOR, linewidth=0.5)
            da.set_axisbelow(True)

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
        self._remove_dist_inset()
        self._style_ax_spec()
        self._result = None
        self._fit_result = None
        self._dist_result = None
        self._canvas.draw_idle()
