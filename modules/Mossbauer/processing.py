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
DEFAULT_VMAX = 11.56


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

    The partner channel s - i is fractional in general, so it is sampled by
    linear interpolation (same convention NORMOS uses).
    """
    n = counts.size
    m = int(np.floor(s / 2.0)) + 1
    i = np.arange(m)
    partner = np.interp(s - i, np.arange(n), counts)
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

def detect_alpha_fe_lines(folded, n_lines=6):
    """Sub-channel positions of the n_lines deepest absorption dips,
    sorted ascending by channel number."""
    absorption = np.clip(_baseline(folded) - folded, 0.0, None)
    smoothed   = np.convolve(absorption, [0.25, 0.5, 0.25], mode="same")

    n       = folded.size
    min_sep = max(3, n // 40)
    work    = smoothed.copy()
    peaks   = []
    for _ in range(n_lines):
        p = int(np.argmax(work))
        if work[p] <= 0:
            break
        peaks.append(p)
        work[max(0, p - min_sep):p + min_sep + 1] = 0.0

    if len(peaks) < n_lines:
        raise ValueError(
            f"Found only {len(peaks)} absorption lines in the calibration "
            f"spectrum; expected {n_lines} (alpha-Fe). Is this an alpha-Fe foil?")

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
        "fold_point":          s / 2.0,
        "velocity":            velocity,
        "transmission":        transmission,
        "smooth_transmission": smooth(transmission),
        # Convenience: the effective VMAX implied by this calibration
        "vmax":                float(np.abs(velocity).max()),
    }


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

    transmission   = folded / _baseline(folded)
    absorption_pct = (1.0 - transmission) * 100.0

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
