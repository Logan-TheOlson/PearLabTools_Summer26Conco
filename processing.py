import os
import pandas as pd

def process_dat(input_path):
    output_dir = os.path.join(os.path.dirname(os.path.abspath(input_path)), "output")
    os.makedirs(output_dir, exist_ok=True)

    dat_name = os.path.basename(input_path)

    # Extract mass
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
    df = df.loc[df['Moment (emu)'] != '0']
    df = df.copy()

    df['Field (T)']               = df['Magnetic Field (Oe)'].astype(float) * 1e-4
    df['Moment (A m^2)']          = df['Moment (emu)'].astype(float) * 1e-3
    if mass:
        df['Magnetization (A m^2/kg)'] = df['Moment (A m^2)'] / (mass * 1e-3)

    df = df.drop(columns=['Magnetic Field (Oe)', 'Moment (emu)'])

    # Split by temperature bands
    temp_col = 'Temperature (K)'
    bands = [
        ('50K',  49,  51),
        ('150K', 149, 151),
        ('300K', 299, 301),
    ]

    frames = []
    first_field_added = False
    for label, lo, hi in bands:
        band = df[(df[temp_col] >= lo) & (df[temp_col] <= hi)].copy()
        band.columns = [f"{c} [{label}]" for c in band.columns]
        band = band.reset_index(drop=True)

        band = band.drop(columns=[c for c in band.columns if 'Moment' in c], errors='ignore')

        if first_field_added:
            band = band.drop(columns=[c for c in band.columns if 'Field' in c], errors='ignore')
        else:
            first_field_added = True

        frames.append(band)

    out_df = pd.concat(frames, axis=1)

    csv_name = os.path.splitext(dat_name)[0] + "_converted.csv"
    csv_path = os.path.join(output_dir, csv_name)
    out_df.to_csv(csv_path, index=False)

    return len(out_df), mass, csv_path, output_dir