import os
import re
import numpy as np
import pandas as pd

from modules.dat_reader import setup_output, read_dat_header

_COLS_RAW = [
    "Temperature (K)",
    "AC Frequency (Hz)",
    "AC X'  (emu/Oe)",   # double-space variant as written by ACMS II
    'AC X" (emu/Oe)',
    "Transport Action",
]

# SI conversion: χ [m³/kg] = χ [emu/Oe] × 4π × 10⁻⁶ / (mass_mg × 10⁻⁶ kg)
#                           = χ [emu/Oe] × 4π / mass_mg
_SI_FACTOR = 4 * np.pi

# Frequency matching tolerance for user-provided overrides (20% relative)
_FREQ_TOL = 0.20


def _normalize_cols(df):
    df.columns = [re.sub(r" {2,}", " ", c).strip() for c in df.columns]
    return df


def _match_freqs(detected, targets, tol=_FREQ_TOL):
    """Return subset of detected frequencies closest to each target, within tol."""
    matched = []
    for target in targets:
        diffs = [(abs(f - target) / max(abs(f), 1), f) for f in detected]
        best_diff, best_f = min(diffs)
        if best_diff <= tol and best_f not in matched:
            matched.append(best_f)
    return sorted(matched)


def process_dat(input_path, freq_override=None):
    output_dir, dat_name = setup_output(input_path)
    lines, mass, data_start = read_dat_header(input_path)

    sample_line = lines[data_start + 1]
    delimiter = "\t" if "\t" in sample_line else ","
    df = pd.read_csv(input_path, skiprows=data_start + 1, sep=delimiter, low_memory=False)
    df = _normalize_cols(df)

    needed = [re.sub(r" {2,}", " ", c).strip() for c in _COLS_RAW]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise ValueError(f"Expected columns not found: {', '.join(missing)}")

    df = df[needed].copy()
    df.columns = ["Temperature (K)", "Frequency (Hz)", "AC X' (emu/Oe)", 'AC X" (emu/Oe)', "Transport Action"]

    df = df[df["Transport Action"] == 1].copy()
    df = df.dropna(subset=["AC X' (emu/Oe)", 'AC X" (emu/Oe)']).copy()
    df = df[df["AC X' (emu/Oe)"].astype(float) != 0].copy()

    # Detect distinct frequencies in the file (analogous to temperature-run detection)
    detected = sorted(df["Frequency (Hz)"].dropna().unique())
    if not detected:
        raise ValueError("No valid AC susceptibility measurements found.")

    if freq_override is not None:
        freqs = _match_freqs(detected, freq_override)
        if not freqs:
            avail = ", ".join(f"{f:.4g}" for f in detected)
            raise ValueError(
                f"None of the provided frequencies matched the data. "
                f"Available: {avail} Hz")
        df = df[df["Frequency (Hz)"].isin(freqs)].copy()
    else:
        freqs = detected

    factor = _SI_FACTOR / mass
    df["AC X' (m^3/kg)"]  = df["AC X' (emu/Oe)"].astype(float) * factor
    df['AC X" (m^3/kg)'] = df['AC X" (emu/Oe)'].astype(float) * factor

    out = df[["Temperature (K)", "Frequency (Hz)",
              "AC X' (m^3/kg)", 'AC X" (m^3/kg)']].copy()
    out = out.sort_values(["Frequency (Hz)", "Temperature (K)"]).reset_index(drop=True)

    stem = os.path.splitext(dat_name)[0]
    csv_path = os.path.join(output_dir, stem + "_converted.csv")
    out.to_csv(csv_path, index=False)

    return len(out), mass, csv_path, output_dir, out, freqs
