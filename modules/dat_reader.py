# Shared helpers for reading VersaLab .DAT files.
import os
import pandas as pd


def setup_output(input_path):
    output_dir = os.path.join(os.path.dirname(os.path.abspath(input_path)), "output")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir, os.path.basename(input_path)


def read_dat_header(input_path):
    # Return (lines, mass_mg, data_start_index).  Raises ValueError on bad files
    with open(input_path, "r") as f:
        lines = f.readlines()

    mass = None
    data_start = None
    for i, line in enumerate(lines):
        if mass is None and "SAMPLE_MASS" in line:
            parts = line.strip().split("\t") if "\t" in line else line.strip().split(",")
            try:
                mass = float(parts[1])
            except (IndexError, ValueError):
                pass
        if line.strip() == "[Data]":
            data_start = i
            break

    if data_start is None:
        raise ValueError("No [Data] section found - is this a VersaLab .DAT file?")
    if mass is None:
        raise ValueError("SAMPLE_MASS not found in file header.")

    return lines, mass, data_start


def load_dataframe(input_path, lines, data_start, columns):
    # Read the [Data] section into a DataFrame, keeping only the requested columns
    sample_line = lines[data_start + 1]
    delimiter = "\t" if "\t" in sample_line else ","
    df = pd.read_csv(input_path, skiprows=data_start + 1, sep=delimiter)
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"Expected columns not found in file: {', '.join(missing)}")
    return df[columns]


def filter_measurements(df):
    # Drop rows with null or zero Moment
    df = df.dropna(subset=["Moment (emu)"])
    return df.loc[df["Moment (emu)"].astype(float) != 0].copy()


def to_magnetization(df, mass_mg):
    # Convert Moment (emu) -> Magnetization (A m^2/kg), drop intermediate columns
    df = df.copy()
    df["Moment (A m^2)"] = df["Moment (emu)"].astype(float) * 1e-3
    df["Magnetization (A m^2/kg)"] = df["Moment (A m^2)"] / (mass_mg * 1e-6)
    return df.drop(columns=["Moment (emu)", "Moment (A m^2)"])
