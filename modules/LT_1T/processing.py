import os
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
    df = df[["Temperature (K)", "Moment (emu)"]]
    df = df.dropna(subset=["Moment (emu)"])
    df = df.loc[df["Moment (emu)"].astype(float) != 0].copy()

    df["Moment (A m^2)"] = df["Moment (emu)"].astype(float) * 1e-3
    if mass:
        df["Magnetization (A m^2/kg)"] = df["Moment (A m^2)"] / (mass * 1e-6)

    df = df.drop(columns=["Moment (emu)", "Moment (A m^2)"])

    stem     = os.path.splitext(dat_name)[0]
    csv_path = os.path.join(output_dir, stem + "_converted.csv")
    df.to_csv(csv_path, index=False)

    return len(df), mass, csv_path, output_dir, df
