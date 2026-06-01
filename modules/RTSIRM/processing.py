import os

from modules.dat_reader import setup_output, read_dat_header, load_dataframe, \
                               filter_measurements, to_magnetization


def process_dat(input_path):
    output_dir, dat_name = setup_output(input_path)
    lines, mass, data_start = read_dat_header(input_path)

    df = load_dataframe(input_path, lines, data_start,
                        ["Temperature (K)", "Moment (emu)"])
    df = filter_measurements(df)
    df = to_magnetization(df, mass)

    stem     = os.path.splitext(dat_name)[0]
    csv_path = os.path.join(output_dir, stem + "_converted.csv")
    df.to_csv(csv_path, index=False)

    return len(df), mass, csv_path, output_dir, df
