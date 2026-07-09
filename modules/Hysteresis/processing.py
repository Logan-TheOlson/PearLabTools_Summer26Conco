import os
import numpy as np
import pandas as pd

from modules.dat_reader import setup_output, read_dat_header, load_dataframe, \
                               filter_measurements, to_magnetization

DEFAULT_BANDS   = [50, 150, 300]
BAND_HALF_WIDTH = 1  # +-K around each target temperature


def process_dat(input_path, band_temps=None, remove_paramagnetic=True):
    if band_temps is None:
        band_temps = DEFAULT_BANDS

    output_dir, dat_name = setup_output(input_path)
    lines, mass, data_start = read_dat_header(input_path)

    df = load_dataframe(input_path, lines, data_start,
                        ["Temperature (K)", "Magnetic Field (Oe)", "Moment (emu)"])
    df = filter_measurements(df)
    df["Field (T)"] = df["Magnetic Field (Oe)"].astype(float) * 1e-4
    df = df.drop(columns=["Magnetic Field (Oe)"])
    df = to_magnetization(df, mass)

    temp_col    = "Temperature (K)"
    band_ranges = [(f"{t}K", t - BAND_HALF_WIDTH, t + BAND_HALF_WIDTH) for t in band_temps]

    plot_data = {}
    frames    = []
    first_field_added = False

    for label, lo, hi in band_ranges:
        band  = df[(df[temp_col] >= lo) & (df[temp_col] <= hi)].copy().reset_index(drop=True)
        pdata = compute_band(band, remove_paramagnetic=remove_paramagnetic)
        plot_data[label] = pdata

        if pdata["corrected"] is not None:
            band["Magnetization Corrected (A m^2/kg)"] = pdata["corrected"]

        band = band.drop(columns=[c for c in band.columns if "Moment" in c], errors="ignore")
        band.columns = [f"{c} [{label}]" for c in band.columns]

        # field column is shared across bands so only the first band keeps it
        if first_field_added:
            band = band.drop(columns=[c for c in band.columns if "Field" in c], errors="ignore")
        else:
            first_field_added = True

        frames.append(band)

    stem     = os.path.splitext(dat_name)[0]
    csv_path = os.path.join(output_dir, stem + "_converted.csv")
    pd.concat(frames, axis=1).to_csv(csv_path, index=False)

    return len(frames[0]), mass, csv_path, output_dir, plot_data, band_ranges


def compute_band(band, remove_paramagnetic=True):
    if band.empty:
        return {"x": None, "y": None, "corrected": None, "roots": None,
                "Ms": None, "Mr": None, "Hc": None}

    x, y  = band["Field (T)"].to_numpy(), band["Magnetization (A m^2/kg)"].to_numpy()
    corrected = Ms = Mr = Hc = None

    if remove_paramagnetic:
        slope, left_mask, right_mask = _high_field_slope(x, y)
        corrected = y - slope * x

        # Ms: mean |magnetization| across the same high-field wings used for slope
        left_vals  = corrected[left_mask]
        right_vals = corrected[right_mask]
        wing_means = [np.mean(v) for v in (left_vals, right_vals) if len(v) > 0]
        if wing_means:
            Ms = float(np.mean(np.abs(wing_means)))

        Mr = _interpolate_at_zero(x, corrected)
        Hc = _interpolate_at_zero(corrected, x)

    return {"x": x, "y": y, "corrected": corrected, "roots": None,
            "Ms": Ms, "Mr": Mr, "Hc": Hc}


def _branch_split(x):
    """Index where the field sweep reverses direction (the turnaround point)."""
    n = len(x)
    min_i, max_i = int(np.argmin(x)), int(np.argmax(x))
    if 0 < min_i < n - 1:
        return min_i
    if 0 < max_i < n - 1:
        return max_i
    return n // 2


def _first_crossing(independent, dependent):
    """
    Walk along the branch and return |dependent| at the FIRST zero-crossing of
    independent.  Taking only the first crossing per branch prevents spurious
    extra crossings (noise, field dithering) from polluting the result.
    """
    for i in range(len(independent) - 1):
        a, b = independent[i], independent[i + 1]
        if a * b <= 0 and a != b:
            t = -a / (b - a)
            return abs(dependent[i] + t * (dependent[i + 1] - dependent[i]))
    return None


def _interpolate_at_zero(independent, dependent):
    """
    Average |dependent| at the first zero-crossing of independent on each of
    the two sweep branches.  Splitting by branch means noise or dithering near
    zero can only produce one crossing per branch instead of many.
    """
    mid  = _branch_split(independent)
    vals = []
    for sl in (slice(0, mid + 1), slice(mid, None)):
        v = _first_crossing(independent[sl], dependent[sl])
        if v is not None:
            vals.append(v)
    return float(np.mean(vals)) if vals else None


def _high_field_slope(x, y, fraction=0.20):
    """Return (slope, left_mask, right_mask) using the outer `fraction` of each field extreme.

    Thresholds are computed independently per side so asymmetric sweeps work correctly.
    """
    x_min, x_max = float(np.min(x)), float(np.max(x))
    left_mask  = x < x_min * (1.0 - fraction)
    right_mask = x > x_max * (1.0 - fraction)
    if left_mask.sum() < 2 or right_mask.sum() < 2:
        slope = np.polyfit(x, y, 1)[0]
    else:
        left_slope  = np.polyfit(x[left_mask],  y[left_mask],  1)[0]
        right_slope = np.polyfit(x[right_mask], y[right_mask], 1)[0]
        slope = (left_slope + right_slope) / 2
    return slope, left_mask, right_mask


def get_roots(x, y):
    # roots of the 3rd derivative of a Chebyshev fit mark the saturation boundaries
    w = np.polynomial.chebyshev.chebfit(x, y, 5)
    d = np.polynomial.chebyshev.chebder(w, 3)
    roots = np.polynomial.chebyshev.chebroots(d)
    real_roots = roots[np.isreal(roots)].real
    if len(real_roots) < 2:
        return None
    real_roots.sort()
    return real_roots


