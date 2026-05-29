import os

import numpy as np
import pandas as pd


DEFAULT_BANDS = [50, 150, 300]
BAND_HALF_WIDTH = 1  # ±K around each target temperature


def process_dat(input_path, band_temps=None):
    if band_temps is None:
        band_temps = DEFAULT_BANDS

    output_dir = os.path.join(os.path.dirname(os.path.abspath(input_path)), "output")
    os.makedirs(output_dir, exist_ok=True)
    dat_name = os.path.basename(input_path)

    # Parse for mass
    mass = None
    with open(input_path, 'r') as f:
        for line in f:
            if 'SAMPLE_MASS' in line:
                parts = line.strip().split('\t') if '\t' in line else line.strip().split(',')
                try:
                    mass = float(parts[1])
                except (IndexError, ValueError):
                    mass = None
                break

    # Find [Data] section
    with open(input_path, 'r') as f:
        lines = f.readlines()
    data_start = next(i for i, l in enumerate(lines) if l.strip() == '[Data]')

    # Auto-detect delimiter
    sample_line = lines[data_start + 1]
    delimiter = '\t' if '\t' in sample_line else ','

    df = pd.read_csv(input_path, skiprows=data_start + 1, sep=delimiter)
    df = df[['Temperature (K)', 'Magnetic Field (Oe)', 'Moment (emu)']]
    df = df.dropna(subset=['Moment (emu)'])
    df = df.loc[df['Moment (emu)'] != '0'].copy()

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

    # Slice each band and compute correction
    plot_data = {}
    bands = {}
    for label, lo, hi in band_ranges:
        band = df[(df[temp_col] >= lo) & (df[temp_col] <= hi)].copy().reset_index(drop=True)
        bands[label] = band
        plot_data[label] = compute_band(band)

    # Compile one frame per band with raw + corrected magnetization columns
    frames = []
    first_field_added = False

    for label, lo, hi in band_ranges:
        band  = bands[label].copy()
        pdata = plot_data[label]

        # Add corrected magnetization alongside raw
        if pdata['corrected'] is not None:
            band['Magnetization Corrected (A m^2/kg)'] = pdata['corrected']

        # Drop raw moment column and label remaining columns with band
        band = band.drop(columns=[c for c in band.columns if 'Moment' in c], errors='ignore')
        band.columns = [f"{c} [{label}]" for c in band.columns]

        # Only include field column in the first band
        if first_field_added:
            band = band.drop(columns=[c for c in band.columns if 'Field' in c], errors='ignore')
        else:
            first_field_added = True

        frames.append(band)

    # Save single CSV
    stem     = os.path.splitext(dat_name)[0]
    csv_path = os.path.join(output_dir, stem + "_converted.csv")
    pd.concat(frames, axis=1).to_csv(csv_path, index=False)

    return len(frames[0]), mass, csv_path, output_dir, plot_data, band_ranges


def compute_band(band):
    # Return early if no data for this band
    if band.empty:
        return {'x': None, 'y': None, 'corrected': None, 'roots': None}

    x, y = get_axis(band)
    roots = get_roots(x, y)
    corrected = None

    if roots is not None:
        slope = roots_to_slope(roots, x, y)
        corrected = y - slope * x

    return {'x': x, 'y': y, 'corrected': corrected, 'roots': roots}


def get_axis(band):
    return (
        band['Field (T)'].to_numpy(),
        band['Magnetization (A m^2/kg)'].to_numpy(),
    )


def get_roots(x, y):
    # Fit chebyshev polynomial to 5th degree
    w = np.polynomial.chebyshev.chebfit(x, y, 5)

    # Take third derivative
    d = np.polynomial.chebyshev.chebder(w, 3)

    # Find x values where third derivative = 0 (saturation boundaries)
    roots = np.polynomial.chebyshev.chebroots(d)

    # Exclude complex roots
    real_roots = roots[np.isreal(roots)].real

    if len(real_roots) < 2:
        return None

    real_roots.sort()
    return real_roots


def roots_to_slope(roots, x, y):
    left_mask  = x < roots[0]
    right_mask = x > roots[1]

    if left_mask.sum() < 2 or right_mask.sum() < 2:
        return np.polyfit(x, y, 1)[0]

    left_slope  = np.polyfit(x[left_mask],  y[left_mask],  1)[0]
    right_slope = np.polyfit(x[right_mask], y[right_mask], 1)[0]

    return (left_slope + right_slope) / 2
