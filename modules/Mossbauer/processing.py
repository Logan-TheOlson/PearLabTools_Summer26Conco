"""Mössbauer spectrum reduction.

Folds a raw triangular-sweep MCA spectrum and assigns a velocity (mm/s) axis,
either from a settable maximum velocity or by calibrating against an alpha-Fe
reference spectrum.  No fitting of the *sample* is performed — this is a data
reducer in the same spirit as the other Pear Tools modules (raw .DAT -> tidy
.CSV + preview).

Kept deliberately dependency-light (numpy + pandas only, no scipy) so it does
not bloat the PyInstaller one-file build.
"""
import os
import numpy as np
import pandas as pd

from modules.dat_reader import setup_output

# Room-temperature alpha-Fe line positions (mm/s) relative to centroid.
# Inner -> outer pairs: ±0.840, ±3.076, ±5.312; outer splitting 10.624 mm/s.
ALPHA_FE_VELOCITIES = np.array([-5.312, -3.076, -0.840, 0.840, 3.076, 5.312])

# Off-resonance level estimated from this percentile of folded counts.
_BASELINE_PCTL = 92.0

# Gaussian-smooth sigma in channels for the preview "smooth" curve.
# sigma=2.0 ch ≈ 0.18 mm/s, much narrower than the thinnest physical line
# (~0.45 mm/s FWHM ≈ 5 ch) so the smooth tracks line shapes without smearing.
_SMOOTH_SIGMA = 2.0

# Default maximum velocity shown in the entry before any cal file is loaded.
# Matches VMAX in the reference NORMOS job (L6.JOB).
DEFAULT_VMAX = 11.5


# ── I/O ──────────────────────────────────────────────────────────────────────

def load_raw(path):
    """Read a raw MCA spectrum: one integer count per line (whitespace split)."""
    with open(path, "r") as f:
        tokens = f.read().split()
    if not tokens:
        raise ValueError("File is empty.")
    try:
        counts = np.array([float(t) for t in tokens])
    except ValueError:
        raise ValueError("Expected a plain list of counts (one integer per line).")
    if counts.size < 16:
        raise ValueError(f"Only {counts.size} channels found — not a spectrum.")
    return counts


# ── Folding ───────────────────────────────────────────────────────────────────

def find_fold_point(counts):
    """Locate the folding point of a triangular-sweep spectrum.

    Returns the *pairing sum* s = 2 × fold-point channel for which the up-
    and down-sweep halves best overlap, refined to sub-channel precision.
    Channel i pairs with channel s - i.
    """
    n = counts.size
    idx = np.arange(n)
    sums = np.arange(int(n * 0.6), int(n * 1.4) + 1)

    def mismatch(s):
        j = s - idx
        m = (j >= 0) & (j < n) & (idx < j)
        if m.sum() < n // 4:
            return np.inf
        a, b = counts[idx[m]], counts[j[m]]
        return np.mean((a - b) ** 2) / (a.mean() * b.mean())

    costs = np.array([mismatch(s) for s in sums])
    k = int(np.argmin(costs))
    s0 = float(sums[k])
    if 0 < k < len(sums) - 1:                        # parabolic sub-channel refine
        c0, c1, c2 = costs[k - 1], costs[k], costs[k + 1]
        denom = c0 - 2 * c1 + c2
        if denom > 0:
            s0 += 0.5 * (c0 - c2) / denom
    return s0


def fold(counts, s):
    """Fold counts about pairing sum s; return the summed half-spectrum.

    NORMOS convention: the pairing sum is rounded to the nearest integer and
    channel i is added directly to channel s - i, with no fractional
    interpolation.  (NORMOS prints a parabolically refined fold point but
    folds on its discrete scan grid — verified against L6.PLT, which our
    integer fold reproduces to print precision.)
    """
    n = counts.size
    s = float(round(s))
    m = int(s // 2) + 1
    i = np.arange(m)
    partner = np.interp(s - i, np.arange(n), counts)   # exact at integers
    return counts[i] + partner


# ── Smooth preview curve ──────────────────────────────────────────────────────

def smooth(y, sigma_ch=_SMOOTH_SIGMA):
    """Gaussian-kernel moving average (numpy-only; no scipy required).

    Edge-pads with the boundary value to avoid roll-off artefacts.
    """
    hw = int(np.ceil(4.0 * sigma_ch))
    x  = np.arange(-hw, hw + 1)
    k  = np.exp(-0.5 * (x / sigma_ch) ** 2)
    k /= k.sum()
    padded = np.pad(y, hw, mode="edge")
    return np.convolve(padded, k, mode="valid")


# ── Baseline ──────────────────────────────────────────────────────────────────

def _baseline(folded):
    """Robust off-resonance level used to normalise to relative transmission."""
    return float(np.percentile(folded, _BASELINE_PCTL))


# ── Alpha-Fe calibration ──────────────────────────────────────────────────────

def _find_dips(absorption, n_lines):
    """Sub-channel positions of up to n_lines deepest peaks in an absorption
    array (baseline - signal, clipped at 0), sorted ascending by channel."""
    smoothed = np.convolve(absorption, [0.25, 0.5, 0.25], mode="same")

    n       = absorption.size
    min_sep = max(3, n // 40)
    work    = smoothed.copy()
    peaks   = []
    for _ in range(n_lines):
        p = int(np.argmax(work))
        if work[p] <= 0:
            break
        peaks.append(p)
        work[max(0, p - min_sep):p + min_sep + 1] = 0.0

    refined = []
    for p in peaks:                                   # parabolic peak refine
        if 0 < p < n - 1:
            y0, y1, y2 = absorption[p - 1], absorption[p], absorption[p + 1]
            denom = y0 - 2 * y1 + y2
            d = 0.5 * (y0 - y2) / denom if denom != 0 else 0.0
            refined.append(p + float(np.clip(d, -1.0, 1.0)))
        else:
            refined.append(float(p))
    return np.array(sorted(refined))


def detect_alpha_fe_lines(folded, n_lines=6):
    """Sub-channel positions of the n_lines deepest absorption dips,
    sorted ascending by channel number."""
    absorption = np.clip(_baseline(folded) - folded, 0.0, None)
    lines = _find_dips(absorption, n_lines)
    if lines.size < n_lines:
        raise ValueError(
            f"Found only {lines.size} absorption lines in the calibration "
            f"spectrum; expected {n_lines} (alpha-Fe). Is this an alpha-Fe foil?")
    return lines


def calibrate_alpha_fe(cal_path):
    """Fold an alpha-Fe calibration file and fit channel -> velocity (mm/s).

    Returns a dict that can be passed directly to process() as cal_data.
    """
    counts = load_raw(cal_path)
    s      = find_fold_point(counts)
    folded = fold(counts, s)
    lines  = detect_alpha_fe_lines(folded, n_lines=ALPHA_FE_VELOCITIES.size)

    slope, intercept = np.polyfit(lines, ALPHA_FE_VELOCITIES, 1)
    residuals = (slope * lines + intercept) - ALPHA_FE_VELOCITIES
    rms = float(np.sqrt(np.mean(residuals ** 2)))

    # Nonlinearity diagnostic: a quadratic fit through the same six lines.
    # Drive transducers with sinusoidal error show a systematic (not random)
    # residual pattern; the max |quadratic - linear| deviation across the
    # channel range where lines actually sit quantifies it in mm/s.
    quad_coeffs   = np.polyfit(lines, ALPHA_FE_VELOCITIES, 2)
    quad_res      = np.polyval(quad_coeffs, lines) - ALPHA_FE_VELOCITIES
    rms_quad      = float(np.sqrt(np.mean(quad_res ** 2)))
    span          = np.linspace(lines.min(), lines.max(), 256)
    nl_dev        = np.polyval(quad_coeffs, span) - (slope * span + intercept)
    nl_max_dev    = float(np.abs(nl_dev).max())
    # Warn when curvature is both physically meaningful (> 0.02 mm/s) and
    # clearly systematic (quadratic soaks up most of the linear residual).
    nl_warn       = nl_max_dev > 0.02 and rms_quad < 0.5 * rms

    base         = _baseline(folded)
    transmission = folded / base
    velocity     = slope * np.arange(folded.size) + intercept

    return {
        "slope":               float(slope),
        "intercept":           float(intercept),
        "zero_channel":        float(-intercept / slope),
        "lines":               lines,
        "line_velocities":     slope * lines + intercept,
        "rms":                 rms,
        "residuals":           residuals,        # per-line, mm/s (linear fit)
        "rms_quad":            rms_quad,
        "nl_max_dev":          nl_max_dev,
        "nl_warn":             nl_warn,
        "fold_point":          s / 2.0,
        "velocity":            velocity,
        "transmission":        transmission,
        "smooth_transmission": smooth(transmission),
        # Convenience: the effective VMAX implied by this calibration
        "vmax":                float(np.abs(velocity).max()),
    }


# ── Lorentzian fitting ────────────────────────────────────────────────────────
#
# Model: T(v) = b − Σ_i d_i · (Γ_i/2)² / ((v − p_i)² + (Γ_i/2)²)
# Parameter vector θ = [b, p₁, Γ₁, d₁, p₂, Γ₂, d₂, ...].
# Fitted with Levenberg-Marquardt on an analytic Jacobian (numpy-only).

def _lorentz_unit(v, pos, fwhm):
    """Unit-height Lorentzian."""
    hw = fwhm / 2.0
    return hw * hw / ((v - pos) ** 2 + hw * hw)


def _fit_model(theta, v, n_lines):
    y = np.full_like(v, theta[0])
    for i in range(n_lines):
        pos, fwhm, depth = theta[1 + 3 * i: 4 + 3 * i]
        y -= depth * _lorentz_unit(v, pos, fwhm)
    return y


def _fit_jacobian(theta, v, n_lines):
    J = np.empty((v.size, theta.size))
    J[:, 0] = 1.0
    for i in range(n_lines):
        pos, fwhm, depth = theta[1 + 3 * i: 4 + 3 * i]
        hw    = fwhm / 2.0
        dv    = v - pos
        denom = dv * dv + hw * hw
        J[:, 1 + 3 * i] = -depth * 2.0 * hw * hw * dv / denom ** 2   # ∂/∂pos
        J[:, 2 + 3 * i] = -depth * hw * dv * dv / denom ** 2         # ∂/∂fwhm
        J[:, 3 + 3 * i] = -(hw * hw / denom)                         # ∂/∂depth
    return J


def _est_fwhm_channels(absorption, p):
    """Rough FWHM in channels: walk out from dip p to the half-depth crossings."""
    half = absorption[p] / 2.0
    lo = p
    while lo > 0 and absorption[lo] > half:
        lo -= 1
    hi = p
    while hi < absorption.size - 1 and absorption[hi] > half:
        hi += 1
    return max(hi - lo, 2)


def _initial_theta(v, t, n_lines):
    base       = float(np.percentile(t, _BASELINE_PCTL))
    absorption = np.clip(base - t, 0.0, None)
    dips       = _find_dips(absorption, n_lines)
    if dips.size < n_lines:
        raise ValueError(
            f"Only {dips.size} candidate absorption lines found — "
            f"try fitting fewer than {n_lines}.")
    dv    = float(np.abs(np.median(np.diff(v))))
    theta = [base]
    for p in dips:
        pi = int(round(p))
        theta += [float(np.interp(p, np.arange(v.size), v)),
                  _est_fwhm_channels(absorption, pi) * dv,
                  max(float(absorption[pi]), 1e-4)]
    return np.array(theta)


def _clamp_theta(theta, n_lines, v_lo, v_hi, min_fwhm, max_fwhm):
    theta = theta.copy()
    theta[0] = np.clip(theta[0], 0.5, 2.0)
    for i in range(n_lines):
        theta[1 + 3 * i] = np.clip(theta[1 + 3 * i], v_lo, v_hi)
        theta[2 + 3 * i] = np.clip(theta[2 + 3 * i], min_fwhm, max_fwhm)
        theta[3 + 3 * i] = np.clip(theta[3 + 3 * i], 0.0, 1.0)
    return theta


def fit_lorentzians(velocity, transmission, n_lines, sigma=None, max_iter=200):
    """Fit n_lines Lorentzian absorption lines plus a flat baseline.

    sigma, if given, is the per-channel 1σ uncertainty of transmission
    (Poisson: sqrt(folded)/baseline_counts) and is used as fit weights.

    Returns a dict with per-line parameters (sorted by position), 1σ errors
    from the scaled covariance matrix, the fitted curve, and fit metrics.
    """
    v = np.asarray(velocity, float)
    t = np.asarray(transmission, float)
    theta = _initial_theta(v, t, n_lines)
    w = np.ones_like(t) if sigma is None else 1.0 / np.clip(sigma, 1e-12, None)

    dv       = float(np.abs(np.median(np.diff(v))))
    min_fwhm = max(0.02, 2.0 * dv)
    max_fwhm = float(v.max() - v.min())

    def clamp(th):
        return _clamp_theta(th, n_lines, v.min(), v.max(), min_fwhm, max_fwhm)

    theta, cost, errs = _levmar(
        theta,
        lambda th: _fit_model(th, v, n_lines),
        lambda th: _fit_jacobian(th, v, n_lines),
        t, w, clamp, max_iter=max_iter)
    dof = max(v.size - theta.size, 1)

    lines = []
    for i in range(n_lines):
        pos, fwhm, depth = theta[1 + 3 * i: 4 + 3 * i]
        pe, fe, de = errs[1 + 3 * i: 4 + 3 * i]
        lines.append({
            "position":  float(pos),  "position_err": float(pe),
            "fwhm":      float(fwhm), "fwhm_err":     float(fe),
            "depth":     float(depth), "depth_err":   float(de),
            # Integrated absorption area = depth · π · Γ/2  (transmission·mm/s)
            "area":      float(depth * np.pi * fwhm / 2.0),
        })
    lines.sort(key=lambda ln: ln["position"])

    curve = _fit_model(theta, v, n_lines)
    return {
        "baseline":     float(theta[0]),
        "baseline_err": float(errs[0]),
        "lines":        lines,
        "curve":        curve,
        "n_lines":      n_lines,
        "rms_resid":    float(np.sqrt(np.mean((curve - t) ** 2))),
        "redchi":       float(cost / dof),
    }


def fit_folded(result, n_lines):
    """Fit Lorentzians to a process() result; save params to <stem>_fit.csv
    and rewrite the folded CSV with a Fitted Transmission column."""
    v, t = result["velocity"], result["transmission"]
    sigma = np.sqrt(np.clip(result["folded"], 1.0, None)) / result["baseline_counts"]
    fit = fit_lorentzians(v, t, n_lines, sigma=sigma)

    stem = os.path.basename(result["csv_path"])
    stem = os.path.splitext(stem)[0]
    if stem.endswith("_folded"):
        stem = stem[:-len("_folded")]

    fit_csv = os.path.join(result["output_dir"], stem + "_fit.csv")
    pd.DataFrame([{
        "Line":                i + 1,
        "Position (mm/s)":     ln["position"],
        "Position Err":        ln["position_err"],
        "FWHM (mm/s)":         ln["fwhm"],
        "FWHM Err":            ln["fwhm_err"],
        "Depth (%)":           ln["depth"] * 100.0,
        "Depth Err (%)":       ln["depth_err"] * 100.0,
        "Area (%*mm/s)":       ln["area"] * 100.0,
    } for i, ln in enumerate(fit["lines"])]).to_csv(fit_csv, index=False)

    pd.DataFrame({
        "Channel":               result["channels"],
        "Velocity (mm/s)":       v,
        "Relative Transmission": t,
        "Fitted Transmission":   fit["curve"],
        "Absorption (%)":        result["absorption_pct"],
        "Folded Counts":         result["folded"],
    }).to_csv(result["csv_path"], index=False)

    fit["csv_path"] = fit_csv
    return fit


# ── Crystalline doublet sites (NORMOS xtal-site style) ───────────────────────
#
# Each site is a symmetric quadrupole doublet, as in NORMOS: two Lorentzian
# lines of equal area at ISX ± QUX/2, common width WID (FWHM).  Fitted
# parameters per site are ISX, QUX and the site area (NORMOS ISXFIT/QUXFIT/
# ARXFIT); the width is shared by all sites and fixed by default (WIXFIT=F).

def _levmar(theta, model_fn, jac_fn, t, w, clamp_fn, max_iter=200):
    """Generic weighted Levenberg-Marquardt.  Returns (theta, cost, errs)."""
    def resid(th):
        return (model_fn(th) - t) * w

    r    = resid(theta)
    cost = float(r @ r)
    lam  = 1e-3
    J    = jac_fn(theta) * w[:, None]
    for _ in range(max_iter):
        g   = J.T @ r
        JTJ = J.T @ J
        d   = np.clip(np.diag(JTJ), 1e-12, None)
        improved = False
        for _try in range(10):
            try:
                delta = np.linalg.solve(JTJ + lam * np.diag(d), -g)
            except np.linalg.LinAlgError:
                lam *= 10.0
                continue
            th_new = clamp_fn(theta + delta)
            r_new  = resid(th_new)
            c_new  = float(r_new @ r_new)
            if c_new < cost:
                small = cost - c_new < 1e-10 * max(cost, 1e-30)
                theta, r, cost = th_new, r_new, c_new
                J = jac_fn(theta) * w[:, None]
                lam = max(lam / 3.0, 1e-12)
                improved = not small
                break
            lam *= 5.0
        if not improved:
            break

    dof = max(t.size - theta.size, 1)
    try:
        cov  = np.linalg.pinv(J.T @ J) * (cost / dof)
        errs = np.sqrt(np.clip(np.diag(cov), 0.0, None))
    except np.linalg.LinAlgError:
        errs = np.full_like(theta, np.nan)
    return theta, cost, errs


def _sites_unpack(theta, n_sites, fit_wid, wid_fixed):
    """theta -> (baseline, wid, list of (isx, qux, area))."""
    b   = theta[0]
    wid = theta[1] if fit_wid else wid_fixed
    off = 2 if fit_wid else 1
    sites = [tuple(theta[off + 3 * i: off + 3 * i + 3]) for i in range(n_sites)]
    return b, wid, sites


def _site_profile(v, isx, qux, area, wid):
    """Absorption profile of one doublet site (area in transmission·mm/s)."""
    h = area / (np.pi * wid)                   # per-line peak depth
    return h * (_lorentz_unit(v, isx - qux / 2.0, wid)
                + _lorentz_unit(v, isx + qux / 2.0, wid))


def fit_sites(result, sites0, wid=0.45, fit_wid=False):
    """Fit NORMOS-style crystalline doublet sites to a process() result.

    sites0 : list of (ISX, QUX) starting values, one pair per site.
    wid    : common linewidth (FWHM, mm/s); starting value if fit_wid.

    Writes <stem>_sites.csv and rewrites the folded CSV with the theory
    curve.  Returns a dict with per-site parameters, errors and the curve.
    """
    v = result["velocity"]
    t = result["transmission"]
    w = result["baseline_counts"] / np.sqrt(np.clip(result["folded"], 1.0, None))
    n_sites = len(sites0)

    base       = float(np.percentile(t, _BASELINE_PCTL))
    absorption = np.clip(base - t, 0.0, None)
    dv         = float(np.abs(np.median(np.diff(v))))
    min_wid    = max(0.02, 2.0 * dv)
    max_wid    = float(v.max() - v.min())

    theta = [base] + ([wid] if fit_wid else [])
    for isx, qux in sites0:
        # Initial area from the observed depth at the two line positions.
        d1 = float(np.interp(isx - qux / 2.0, v, absorption))
        d2 = float(np.interp(isx + qux / 2.0, v, absorption))
        theta += [isx, qux, max((d1 + d2) / 2.0 * np.pi * wid, 1e-5)]
    theta = np.array(theta)

    off = 2 if fit_wid else 1

    def model(th):
        b, wd, ss = _sites_unpack(th, n_sites, fit_wid, wid)
        y = np.full_like(v, b)
        for isx, qux, area in ss:
            y -= _site_profile(v, isx, qux, area, wd)
        return y

    def jac(th):
        b, wd, ss = _sites_unpack(th, n_sites, fit_wid, wid)
        J = np.zeros((v.size, th.size))
        J[:, 0] = 1.0
        for i, (isx, qux, area) in enumerate(ss):
            h = area / (np.pi * wd)
            hw = wd / 2.0
            cols = []
            for sign in (-1.0, +1.0):
                p     = isx + sign * qux / 2.0
                dvv   = v - p
                denom = dvv * dvv + hw * hw
                U     = hw * hw / denom
                dU_dp = 2.0 * hw * hw * dvv / denom ** 2
                dU_dw = hw * dvv * dvv / denom ** 2
                cols.append((U, dU_dp, dU_dw, sign))
            k = off + 3 * i
            J[:, k]     = -h * sum(c[1] for c in cols)                 # ∂/∂ISX
            J[:, k + 1] = -h * sum(0.5 * c[3] * c[1] for c in cols)    # ∂/∂QUX
            J[:, k + 2] = -sum(c[0] for c in cols) / (np.pi * wd)      # ∂/∂area
            if fit_wid:
                J[:, 1] += (-h * sum(c[2] for c in cols)
                            + area / (np.pi * wd * wd) * sum(c[0] for c in cols))
        return J

    def clamp(th):
        th = th.copy()
        th[0] = np.clip(th[0], 0.5, 2.0)
        if fit_wid:
            th[1] = np.clip(th[1], min_wid, max_wid)
        for i in range(n_sites):
            k = off + 3 * i
            th[k]     = np.clip(th[k],     v.min(), v.max())
            th[k + 1] = np.clip(th[k + 1], 0.0, 2.0 * v.max())
            th[k + 2] = np.clip(th[k + 2], 0.0, None)
        return th

    theta, cost, errs = _levmar(theta, model, jac, t, w, clamp)
    b, wd, ss = _sites_unpack(theta, n_sites, fit_wid, wid)

    total_area = sum(area for _, _, area in ss)
    out_sites = []
    for i, (isx, qux, area) in enumerate(ss):
        k = off + 3 * i
        out_sites.append({
            "isx":       float(isx),  "isx_err":  float(errs[k]),
            "qux":       float(qux),  "qux_err":  float(errs[k + 1]),
            "area":      float(area), "area_err": float(errs[k + 2]),
            "rel_area":  float(100.0 * area / total_area) if total_area > 0 else 0.0,
            "component": _site_profile(v, isx, qux, area, wd),
        })

    curve = model(theta)
    dof   = max(v.size - theta.size, 1)

    stem = os.path.basename(result["csv_path"])
    stem = os.path.splitext(stem)[0]
    if stem.endswith("_folded"):
        stem = stem[:-len("_folded")]
    sites_csv = os.path.join(result["output_dir"], stem + "_sites.csv")
    pd.DataFrame([{
        "Site":            i + 1,
        "ISX (mm/s)":      s["isx"],
        "ISX Err":         s["isx_err"],
        "QUX (mm/s)":      s["qux"],
        "QUX Err":         s["qux_err"],
        "WID (mm/s)":      wd,
        "Area (mm/s)":     s["area"],
        "Area Err":        s["area_err"],
        "Rel. Area (%)":   s["rel_area"],
    } for i, s in enumerate(out_sites)]).to_csv(sites_csv, index=False)

    pd.DataFrame({
        "Channel":               result["channels"],
        "Velocity (mm/s)":       v,
        "Relative Transmission": t,
        "Fitted Transmission":   curve,
        "Absorption (%)":        result["absorption_pct"],
        "Folded Counts":         result["folded"],
    }).to_csv(result["csv_path"], index=False)

    return {
        "sites":      out_sites,
        "baseline":   float(b),
        "wid":        float(wd),
        "wid_err":    float(errs[1]) if fit_wid else 0.0,
        "fit_wid":    fit_wid,
        "curve":      curve,
        "chi2_norm":  float(cost / dof),
        "total_area": float(total_area),
        "csv_path":   sites_csv,
    }


# ── Hyperfine distribution fitting (NORMOS-DIST style) ───────────────────────
#
# Fits a histogram distribution of hyperfine parameters, after R.A. Brand's
# NORMOS-DIST (1990): NSB subspectra on a fixed grid x_j = x0 + j·dx, each a
# fixed-shape Lorentzian multiplet of linewidth WID, with non-negative
# amplitudes h_j found by NNLS under Hesse-Rübartsch second-difference
# smoothing (weight LAMDA).  The global isomer shift ISO and the baseline are
# the only nonlinear/free parameters (same two fit variables NORMOS uses).
#
# kind="qs":  symmetric quadrupole doublets, lines at ISO ± x/2   (METHOD=6)
# kind="bhf": magnetic sextets, x = hyperfine field in Tesla      (METHOD=1)

# 57Fe sextet line positions in mm/s per Tesla (alpha-Fe: 33.0 T at RT).
SEXTET_POS_COEF = ALPHA_FE_VELOCITIES / 33.0
# First-order quadrupole line-shift pattern for a sextet.
SEXTET_QSHIFT   = np.array([1.0, -1.0, -1.0, -1.0, -1.0, 1.0])


def _nnls(A, b, max_iter=None):
    """Lawson-Hanson non-negative least squares:  min ||Ax - b||,  x >= 0."""
    m, n = A.shape
    x    = np.zeros(n)
    P    = np.zeros(n, bool)
    w    = A.T @ (b - A @ x)
    tol  = 1e-10 * max(np.abs(w).max(), 1.0)
    max_iter = max_iter or 3 * n
    for _ in range(max_iter):
        if P.all() or np.all(w[~P] <= tol):
            break
        j = int(np.argmax(np.where(~P, w, -np.inf)))
        P[j] = True
        while True:
            s = np.zeros(n)
            s[P] = np.linalg.lstsq(A[:, P], b, rcond=None)[0]
            if np.all(s[P] > 0):
                break
            neg   = P & (s <= 0)
            alpha = np.min(x[neg] / (x[neg] - s[neg]))
            x     = x + alpha * (s - x)
            P    &= x > 1e-14
        x = s
        w = A.T @ (b - A @ x)
    return x


def _dist_basis(v, kind, x, iso, wid, qua=0.0, a23=2.0):
    """Basis matrix (len(v) x len(x)); column j is the unit-depth absorption
    profile of the subspectrum at grid value x_j."""
    A = np.empty((v.size, x.size))
    if kind == "qs":
        for j, xj in enumerate(x):
            A[:, j] = 0.5 * (_lorentz_unit(v, iso - xj / 2.0, wid)
                             + _lorentz_unit(v, iso + xj / 2.0, wid))
    elif kind == "bhf":
        wts = np.array([3.0, a23, 1.0, 1.0, a23, 3.0])
        wts /= wts.sum()
        for j, xj in enumerate(x):
            pos = iso + SEXTET_POS_COEF * xj + SEXTET_QSHIFT * (qua / 2.0)
            A[:, j] = sum(wts[i] * _lorentz_unit(v, pos[i], wid)
                          for i in range(6))
    else:
        raise ValueError(f"Unknown distribution kind: {kind!r}")
    return A


def _dist_solve(v, t, w, kind, x, iso, wid, lam, qua, a23):
    """Solve amplitudes + baseline at fixed ISO.

    Returns (h, baseline, chi2, penalty): chi2 is the plain weighted sum of
    squared residuals, penalty the Hesse-Rübartsch smoothing term."""
    A = _dist_basis(v, kind, x, iso, wid, qua, a23)
    n = x.size

    # Hesse-Rübartsch smoothing rows: sqrt(mu) * second difference of h.
    # The 0.5 factor calibrates LAMDA against NORMOS-DIST: with it, the L6
    # reference job (LAMDA=0.5) reproduces the .RES distribution shape.
    mu = 0.5 * lam * float(np.mean(w ** 2))
    D  = np.zeros((n - 2, n))
    for i in range(n - 2):
        D[i, i:i + 3] = (1.0, -2.0, 1.0)
    S = np.sqrt(mu) * D

    baseline = float(np.percentile(t, _BASELINE_PCTL))
    h    = np.zeros(n)
    Aw   = np.vstack([A * w[:, None], S])
    tail = np.zeros(n - 2)
    for _ in range(4):                       # alternate h (NNLS) and baseline
        bw  = np.concatenate([(baseline - t) * w, tail])
        h   = _nnls(Aw, bw)
        fit_abs  = A @ h
        baseline = float(np.sum(w ** 2 * (t + fit_abs)) / np.sum(w ** 2))
    resid = (baseline - fit_abs - t) * w
    return h, baseline, float(resid @ resid), float(np.sum((S @ h) ** 2))


def fit_distribution(result, kind="qs", x0=0.0, dx=0.1, nsb=18,
                     wid=0.45, lam=0.5, iso0=0.3, qua=0.0, a23=2.0):
    """NORMOS-DIST style distribution fit on a process() result.

    ISO is optimised by golden-section search (variable projection: the
    amplitudes are re-solved by NNLS at every trial ISO).  Writes
    <stem>_dist.csv, a RES-style <stem>_dist_report.txt, and rewrites the
    folded CSV with the theory curve.
    """
    v = result["velocity"]
    t = result["transmission"]
    w = result["baseline_counts"] / np.sqrt(np.clip(result["folded"], 1.0, None))
    x = x0 + dx * np.arange(nsb)

    def objective(iso):
        # NORMOS minimises the total functional: chi2 + smoothing penalty.
        _, _, chi2, pen = _dist_solve(v, t, w, kind, x, iso, wid, lam, qua, a23)
        return chi2 + pen

    # Golden-section search for ISO over iso0 ± 1 mm/s.
    gr   = (np.sqrt(5.0) - 1.0) / 2.0
    a, b = iso0 - 1.0, iso0 + 1.0
    c, d = b - gr * (b - a), a + gr * (b - a)
    fc, fd = objective(c), objective(d)
    while b - a > 1e-4:
        if fc < fd:
            b, d, fd = d, c, fc
            c  = b - gr * (b - a)
            fc = objective(c)
        else:
            a, c, fc = c, d, fd
            d  = a + gr * (b - a)
            fd = objective(d)
    iso = (a + b) / 2.0

    h, baseline, chi2, pen = _dist_solve(v, t, w, kind, x, iso, wid, lam, qua, a23)
    curve = baseline - _dist_basis(v, kind, x, iso, wid, qua, a23) @ h

    # 1-sigma ISO error from the chi2 curvature (delta chi2 = 1).
    eps  = 5e-3
    total = chi2 + pen
    d2   = (objective(iso + eps) - 2.0 * total + objective(iso - eps)) / eps ** 2
    iso_err = float(np.sqrt(2.0 / d2)) if d2 > 0 else float("nan")

    # NORMOS conventions: "Chi-square (normalized)" is the *total* functional
    # over N-2 (only BKG and ISO count as fit variables); the Hesse-Rübartsch
    # parameter is the pure chi2 over N - active bins - 2.
    n_act     = int(np.sum(h > 0))
    chi2_norm = total / max(v.size - 2, 1)
    hr_param  = chi2 / max(v.size - n_act - 2, 1)

    # Distribution statistics (probability p_j from amplitudes).
    area_j     = h * np.pi * wid / 2.0          # resonant area per bin (mm/s)
    total_area = float(area_j.sum())
    if total_area <= 0:
        raise ValueError("Distribution fit collapsed to zero area — "
                         "check the grid range and start values.")
    p     = area_j / total_area
    # Midpoint cumulative (D at bin j includes half of bin j) — the NORMOS
    # convention, and what its median is interpolated on.
    cum   = np.cumsum(p) - p / 2.0
    mean  = float(np.sum(p * x))
    var   = float(np.sum(p * (x - mean) ** 2))
    std   = float(np.sqrt(var))
    stats = {
        "mean":     mean,
        "median":   float(np.interp(0.5, cum, x)),
        "rms":      float(np.sqrt(np.sum(p * x ** 2))),
        "std":      std,
        "skew":     float(np.sum(p * (x - mean) ** 3) / std ** 3) if std > 0 else 0.0,
        "kurtosis": float(np.sum(p * (x - mean) ** 4) / std ** 4 - 3.0) if std > 0 else 0.0,
    }

    stem = os.path.basename(result["csv_path"])
    stem = os.path.splitext(stem)[0]
    if stem.endswith("_folded"):
        stem = stem[:-len("_folded")]
    xname = "QUA (mm/s)" if kind == "qs" else "BHF (T)"

    dist_csv = os.path.join(result["output_dir"], stem + "_dist.csv")
    pd.DataFrame({
        xname:            x,
        "Area (mm/s)":    area_j,
        "P(x) (%/unit)":  100.0 * p / dx,
        "D(x) (%)":       100.0 * cum,
    }).to_csv(dist_csv, index=False)

    report = os.path.join(result["output_dir"], stem + "_dist_report.txt")
    _write_dist_report(report, result, kind, x, xname, p, cum, dx,
                       iso, iso_err, baseline, chi2_norm, hr_param,
                       total_area, stats, wid, lam, qua, a23)

    pd.DataFrame({
        "Channel":               result["channels"],
        "Velocity (mm/s)":       v,
        "Relative Transmission": t,
        "Fitted Transmission":   curve,
        "Absorption (%)":        result["absorption_pct"],
        "Folded Counts":         result["folded"],
    }).to_csv(result["csv_path"], index=False)

    return {
        "kind":        kind,
        "x":           x,
        "xname":       xname,
        "h":           h,
        "p":           p,
        "p_density":   100.0 * p / dx,
        "cum_pct":     100.0 * cum,
        "iso":         float(iso),
        "iso_err":     iso_err,
        "baseline":    baseline,
        "curve":       curve,
        "chi2_norm":   float(chi2_norm),
        "hr_param":    float(hr_param),
        "total_area":  total_area,
        "stats":       stats,
        "csv_path":    dist_csv,
        "report_path": report,
    }


def _write_dist_report(path, result, kind, x, xname, p, cum, dx,
                       iso, iso_err, baseline, chi2_norm, hr_param,
                       total_area, stats, wid, lam, qua, a23):
    """RES-style plain-text summary (after the NORMOS .RES layout)."""
    bar = "-" * 79
    L = [bar,
         "            Mossbauer distribution fit (NORMOS-DIST style)",
         bar,
         f" Distribution kind                     = "
         f"{'quadrupole doublets (METHOD 6)' if kind == 'qs' else 'magnetic sextets (METHOD 1)'}",
         f" Number of subspectra             NSB  = {x.size:5d}",
         f" Grid start / step                     = {x[0]:9.4f} / {dx:.4f}",
         f" Linewidth (FWHM)                 WID  = {wid:9.4f} mm/s",
         f" Smoothing                       LAMDA = {lam:9.4f}"]
    if kind == "bhf":
        L += [f" Quadrupole line shift            QUA  = {qua:9.4f} mm/s",
              f" Area ratio 2,5 / 3,4             A23  = {a23:9.4f}"]
    L += [bar,
          f" Fold point (channel)                  = {result['fold_point']:.4f}",
          f" Channels after folding                = {result['n']}",
          f" Calibration constant            DELV  = {result['delv']:9.4f} mm/s/ch",
          bar,
          f" Isomer shift                     ISO  = {iso:9.4f} +- {iso_err:.4f} mm/s",
          f" Baseline (rel. transmission)          = {baseline:9.6f}",
          f" Hesse-Ruebartsch parameter            = {hr_param:9.4f}",
          f" Chi-square (normalized)               = {chi2_norm:9.4f}",
          f" Total distribution area               = {total_area:.4E} mm/s",
          bar,
          f" Average value                         = {stats['mean']:9.4f} +- (see std)",
          f" Median value                          = {stats['median']:9.4f}",
          f" RMS average value                     = {stats['rms']:9.4f}",
          f" Standard deviation                    = {stats['std']:9.4f}",
          f" Skew of distribution                  = {stats['skew']:9.4f}",
          f" Kurtosis of distribution              = {stats['kurtosis']:9.4f}",
          bar,
          f" #  x={xname:<12s} P(x)     D(x)(%)   Distribution plot",
          ]
    pmax = max(p.max(), 1e-30)
    for j in range(x.size):
        stars = int(round(32.0 * p[j] / pmax))
        L.append(f"{j + 1:3d} {x[j]:9.3f} {100.0 * p[j] / dx:9.3f} "
                 f"{cum[j] * 100.0:8.3f}   I{'*' * stars}")
    L += [bar, ""]
    with open(path, "w") as f:
        f.write("\n".join(L))


# ── Main reduction ────────────────────────────────────────────────────────────

def process(input_path, vmax, cal_data=None):
    """Fold input_path and assign a velocity axis.

    Parameters
    ----------
    input_path : str
        Raw MCA spectrum (.dat, one integer count per line).
    vmax : float
        Maximum velocity (mm/s).  Used for a symmetric linear axis when
        cal_data is None, and for display/CSV metadata when cal_data is set.
    cal_data : dict or None
        Result of calibrate_alpha_fe().  When provided the accurate
        slope+intercept calibration is used instead of a simple linspace.

    Returns a dict of arrays and scalar metrics for the GUI.
    """
    output_dir, dat_name = setup_output(input_path)
    counts   = load_raw(input_path)
    s        = find_fold_point(counts)
    folded   = fold(counts, s)
    n        = folded.size
    channels = np.arange(n)

    if cal_data is not None:
        velocity     = cal_data["slope"] * channels + cal_data["intercept"]
        delv         = abs(cal_data["slope"])
        zero_channel = cal_data["zero_channel"]
    else:
        if vmax <= 0:
            raise ValueError("Velocity must be a positive number (mm/s).")
        velocity     = np.linspace(-vmax, vmax, n)
        delv         = (2.0 * vmax) / (n - 1)
        zero_channel = (n - 1) / 2.0

    baseline_counts = _baseline(folded)
    transmission    = folded / baseline_counts
    absorption_pct  = (1.0 - transmission) * 100.0

    stem     = os.path.splitext(dat_name)[0]
    csv_path = os.path.join(output_dir, stem + "_folded.csv")
    pd.DataFrame({
        "Channel":               channels,
        "Velocity (mm/s)":       velocity,
        "Relative Transmission": transmission,
        "Absorption (%)":        absorption_pct,
        "Folded Counts":         folded,
    }).to_csv(csv_path, index=False)

    return {
        "channels":             channels,
        "velocity":             velocity,
        "folded":               folded,
        "baseline_counts":      baseline_counts,
        "transmission":         transmission,
        "smooth_transmission":  smooth(transmission),
        "absorption_pct":       absorption_pct,
        "fold_point":           s / 2.0,
        "delv":                 delv,
        "zero_channel":         zero_channel,
        "vmax":                 float(np.abs(velocity).max()),
        "max_abs":              float(absorption_pct.max()),
        "n":                    n,
        "cal":                  cal_data,       # passed through for the GUI
        "rows":                 n,
        "csv_path":             csv_path,
        "output_dir":           output_dir,
    }
