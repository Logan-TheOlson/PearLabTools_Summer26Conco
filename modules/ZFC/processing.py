import os
import numpy as np
import pandas as pd


def process_dat(input_path):
    output_dir = os.path.join(os.path.dirname(os.path.abspath(input_path)), "output")
    os.makedirs(output_dir, exist_ok=True)
    dat_name = os.path.basename(input_path)

    mass = None
    data_start = None
    with open(input_path, "r") as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        if mass is None and "SAMPLE_MASS" in line:
            parts = line.strip().split(",")
            try:
                mass = float(parts[1])
            except (IndexError, ValueError):
                mass = None
        if line.strip() == "[Data]":
            data_start = i
            break

    df = pd.read_csv(input_path, skiprows=data_start + 1, sep=",")
    df = df[["Temperature (K)", "Moment (emu)", "Transport Action"]]

    # Keep only actual measurements (Transport Action == 1)
    df = df[df["Transport Action"] == 1].copy()
    df = df.dropna(subset=["Moment (emu)"])
    df = df.loc[df["Moment (emu)"].astype(float) != 0].copy()

    df["Moment (A m^2)"] = df["Moment (emu)"].astype(float) * 1e-3
    if mass:
        df["Magnetization (A m^2/kg)"] = df["Moment (A m^2)"] / (mass * 1e-6)

    df = df.drop(columns=["Moment (emu)", "Moment (A m^2)", "Transport Action"])
    df = df.reset_index(drop=True)

    # Split at the temperature reset between ZFC and FC runs
    temps = df["Temperature (K)"].values
    split_idx = next(
        (i for i in range(1, len(temps)) if temps[i] < temps[i - 1] - 50),
        None
    )
    if split_idx is None:
        raise ValueError("Could not find two runs in file — no temperature reset detected.")

    zfc = df.iloc[:split_idx].reset_index(drop=True)
    fc  = df.iloc[split_idx:].reset_index(drop=True)

    # Use ZFC temperatures as the shared x-axis; interpolate FC onto them
    x     = zfc["Temperature (K)"].values
    y_zfc = zfc["Magnetization (A m^2/kg)"].values
    y_fc  = np.interp(x, fc["Temperature (K)"].values, fc["Magnetization (A m^2/kg)"].values)

    out = pd.DataFrame({
        "Temperature (K)":             x,
        "Magnetization ZFC (A m^2/kg)": y_zfc,
        "Magnetization FC (A m^2/kg)":  y_fc,
    })

    stem     = os.path.splitext(dat_name)[0]
    csv_path = os.path.join(output_dir, stem + "_converted.csv")
    out.to_csv(csv_path, index=False)

    return len(out), mass, csv_path, output_dir, out
