import os
import pandas as pd

# Method Declaration
def process_dat(input_path):
    # Set base directory to assist in output path definition
    output_dir = os.path.join(os.path.dirname(os.path.abspath(input_path)), "output")
    os.makedirs(output_dir, exist_ok=True)
    dat_name = os.path.basename(input_path)

    # Parse for mass
    mass = None
    with open(input_path, 'r') as f:
        for line in f:
            # Find line with SAMPLE_MASS in it and extract the float
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

    # Read the data from 3 important columns using detected start and delimiter
    df = pd.read_csv(input_path, skiprows=data_start + 1, sep=delimiter)
    df = df[['Temperature (K)', 'Magnetic Field (Oe)', 'Moment (emu)']]
    # Drop empty and control values
    df = df.dropna(subset=['Moment (emu)'])
    df = df.loc[df['Moment (emu)'] != '0']
    df = df.copy()

    # Cast, clean, and convert data
    df['Field (T)']               = df['Magnetic Field (Oe)'].astype(float) * 1e-4
    df['Moment (A m^2)']          = df['Moment (emu)'].astype(float) * 1e-3
    if mass:
        df['Magnetization (A m^2/kg)'] = df['Moment (A m^2)'] / (mass * 1e-3)

    df = df.drop(columns=['Magnetic Field (Oe)', 'Moment (emu)'])

    # Split by temperature bands
    temp_col = 'Temperature (K)'
    band_ranges = [
        ('50K',  49,  51),
        ('150K', 149, 151),
        ('300K', 299, 301),
    ]

    # Separate bands into individual dataframes for arithmetic
    bands = {}
    for label, lo, hi in band_ranges:
        band = df[(df[temp_col] >= lo) & (df[temp_col] <= hi)].copy()
        band = band.reset_index(drop=True)
        bands[label] = band

    # Separate the bands and operate on them
    bands = compute_band_50K(bands)
    bands = compute_band_150K(bands)
    bands = compute_band_300K(bands)

    # Selectively compile columns into new table
    frames = []
    first_field_added = False
    for label, lo, hi in band_ranges:
        band = bands[label].copy()
        band.columns = [f"{c} [{label}]" for c in band.columns]

        band = band.drop(columns=[c for c in band.columns if 'Moment' in c], errors='ignore')

        if first_field_added:
            band = band.drop(columns=[c for c in band.columns if 'Field' in c], errors='ignore')
        else:
            first_field_added = True

        frames.append(band)

    # Prepare and output converted CSV file
    out_df = pd.concat(frames, axis=1)

    csv_name = os.path.splitext(dat_name)[0] + "_converted.csv"
    csv_path = os.path.join(output_dir, csv_name)
    out_df.to_csv(csv_path, index=False)

    return len(out_df), mass, csv_path, output_dir

def compute_band_50K(bands):
    b = bands['50K']
    c = b['Magnetization (A m^2/kg)'].to_numpy()
    print(type(c))
    print(c)
    return bands


def compute_band_150K(bands):
    b = bands['150K']
    return bands


def compute_band_300K(bands):
    b = bands['300K']
    return bands