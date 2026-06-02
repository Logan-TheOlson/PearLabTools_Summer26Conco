import os
import numpy as np
import pandas as pd

from modules.dat_reader import setup_output, read_dat_header, load_dataframe, \
                               to_magnetization


def process_dat(input_path):
    output_dir, dat_name = setup_output(input_path)
    lines, mass, data_start = read_dat_header(input_path)

    df = load_dataframe(input_path, lines, data_start,
                        ["Temperature (K)", "Moment (emu)", "Transport Action"])

    # Keep only actual measurements (Transport Action == 1)
    df = df[df["Transport Action"] == 1].copy()
    df = df.dropna(subset=["Moment (emu)"])
    df = df.loc[df["Moment (emu)"].astype(float) != 0].copy()
    df = to_magnetization(df, mass)
    df = df.drop(columns=["Transport Action"], errors="ignore").reset_index(drop=True)

    # Split at the temperature reset between ZFC and FC runs
    temps = df["Temperature (K)"].values
    split_idx = next(
        (i for i in range(1, len(temps)) if temps[i] < temps[i - 1] - 50), None)
    if split_idx is None:
        raise ValueError("Could not find two runs - no temperature reset detected.")

    zfc = df.iloc[:split_idx].reset_index(drop=True)
    fc  = df.iloc[split_idx:].reset_index(drop=True)

    # Use ZFC temperatures as the shared x-axis; interpolate FC onto them
    x     = zfc["Temperature (K)"].values
    y_zfc = zfc["Magnetization (A m^2/kg)"].values
    y_fc  = np.interp(x, fc["Temperature (K)"].values,
                      fc["Magnetization (A m^2/kg)"].values)

    out = pd.DataFrame({
        "Temperature (K)":              x,
        "Magnetization ZFC (A m^2/kg)": y_zfc,
        "Magnetization FC (A m^2/kg)":  y_fc,
    })

    stem     = os.path.splitext(dat_name)[0]
    csv_path = os.path.join(output_dir, stem + "_converted.csv")
    out.to_csv(csv_path, index=False)

    return len(out), mass, csv_path, output_dir, out
