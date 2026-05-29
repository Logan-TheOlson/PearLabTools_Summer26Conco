import os
import numpy as np
import pandas as pd

DEFAULT_BANDS = [50, 150, 300]
BAND_HALF_WIDTH = 1  # +-K around each target temperature


def process_dat(input_path, band_temps=None):
    if band_temps is None:
        band_temps = DEFAULT_BANDS

    output_dir = os.path.join(os.path.dirname(os.path.abspath(input_path)), "output")
    os.makedirs(output_dir, exist_ok=True)
    dat_name = os.path.basename(input_path)

    mass = None
    data_start = None
    with open(input_path, 'r') as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        if mass is None and 'SAMPLE_MASS' in line:
            parts = line.strip().split('\t') if '\t' in line else line.strip().split(',')
            try:
                mass = float(parts[1])
            except (IndexError, ValueError):
                mass = None
        if line.strip() == '[Data]':
            data_start = i
            break

    sample_line = lines[data_start + 1]
    delimiter = '\t' if '\t' in sample_line else ','

    df = pd.read_csv(input_path, skiprows=data_start + 1, sep=delimiter)
    df = df[['Temperature (K)', 'Magnetic Field (Oe)', 'Moment (emu)']]
    df = df.dropna(subset=['Moment (emu)'])
    df = df.loc[df['Moment (emu)'].astype(float) != 0].copy()

    df['Field (T)']      = df['Magnetic Field (Oe)'].astype(float) * 1e-4
    df['Moment (A m^2)'] = df['Moment (emu)'].astype(float) * 1e-3
    if mass:
        df['Magnetization (A m^2/kg)'] = df['Moment (A m^2)'] / (mass * 1e-6)

    df = df.drop(columns=['Magnetic Field (Oe)', 'Moment (emu)'])

    temp_col = 'Temperature (K)'
    band_ranges = [
        (f"{t}K", t - BAND_HALF_WIDTH, t + BAND_HALF_WIDTH)
        for t in band_temps
    ]

    plot_data = {}
    frames = []
    first_field_added = False

    for label, lo, hi in band_ranges:
        band = df[(df[temp_col] >= lo) & (df[temp_col] <= hi)].copy().reset_index(drop=True)
        pdata = compute_band(band)
        plot_data[label] = pdata

        if pdata['corrected'] is not None:
            band['Magnetization Corrected (A m^2/kg)'] = pdata['corrected']

        band = band.drop(columns=[c for c in band.columns if 'Moment' in c], errors='ignore')
        band.columns = [f"{c} [{label}]" for c in band.columns]

        # field column is shared across all bands so only the first band keeps it
        if first_field_added:
            band = band.drop(columns=[c for c in band.columns if 'Field' in c], errors='ignore')
        else:
            first_field_added = True

        frames.append(band)

    stem     = os.path.splitext(dat_name)[0]
    csv_path = os.path.join(output_dir, stem + "_converted.csv")
    pd.concat(frames, axis=1).to_csv(csv_path, index=False)

    return len(frames[0]), mass, csv_path, output_dir, plot_data, band_ranges


def compute_band(band):
    if band.empty:
        return {'x': None, 'y': None, 'corrected': None, 'roots': None,
                'Ms': None, 'Mr': None, 'Hc': None}

    x, y = get_axis(band)
    roots = get_roots(x, y)
    corrected = None
    Ms = Mr = Hc = None

    if roots is not None:
        slope = roots_to_slope(roots, x, y)
        corrected = y - slope * x

        # Ms: mean |magnetization| across both high-field saturation wings
        left_mask  = x < roots[0]
        right_mask = x > roots[-1]
        left_vals  = corrected[left_mask]  if left_mask.sum()  > 0 else np.array([])
        right_vals = corrected[right_mask] if right_mask.sum() > 0 else np.array([])
        wing_means = [np.mean(v) for v in (left_vals, right_vals) if len(v) > 0]
        if wing_means:
            Ms = float(np.mean(np.abs(wing_means)))

        Mr = get_remanent_magnetization(x, corrected)
        Hc = get_coercive_field(x, corrected)

    return {'x': x, 'y': y, 'corrected': corrected, 'roots': roots,
            'Ms': Ms, 'Mr': Mr, 'Hc': Hc}


def get_axis(band):
    return (
        band['Field (T)'].to_numpy(),
        band['Magnetization (A m^2/kg)'].to_numpy(),
    )


def get_roots(x, y):
    # roots of the 3rd derivative mark where the loop enters/exits saturation
    w = np.polynomial.chebyshev.chebfit(x, y, 5)
    d = np.polynomial.chebyshev.chebder(w, 3)
    roots = np.polynomial.chebyshev.chebroots(d)
    real_roots = roots[np.isreal(roots)].real

    if len(real_roots) < 2:
        return None

    real_roots.sort()
    return real_roots


def roots_to_slope(roots, x, y):
    left_mask  = x < roots[0]
    right_mask = x > roots[-1]

    if left_mask.sum() < 2 or right_mask.sum() < 2:
        return np.polyfit(x, y, 1)[0]

    left_slope  = np.polyfit(x[left_mask],  y[left_mask],  1)[0]
    right_slope = np.polyfit(x[right_mask], y[right_mask], 1)[0]

    return (left_slope + right_slope) / 2


def get_remanent_magnetization(x, y):
    # Find the 2 points closest to H=0 and interpolate y at x=0.
    # Uses the corrected (paramagnetic-removed) magnetization.
    closest_indices = np.argpartition(np.abs(x), 2)[:2]
    intercept = np.polyfit(x[closest_indices], y[closest_indices], 1)[1]
    return abs(float(intercept))


def get_coercive_field(x, y):
    # Interpolate |field| at M=0 on each branch and average them.
    # A proper loop crosses zero-magnetization twice (once per sweep direction).
    hc_vals = []
    for i in range(len(y) - 1):
        if y[i] * y[i + 1] <= 0 and y[i] != y[i + 1]:
            t = -y[i] / (y[i + 1] - y[i])
            hc_vals.append(abs(x[i] + t * (x[i + 1] - x[i])))
    return float(np.mean(hc_vals)) if hc_vals else None
