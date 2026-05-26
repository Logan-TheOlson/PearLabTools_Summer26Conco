import pandas as pd

df = pd.read_table('InputEx.DAT', delimiter=",", skiprows=34)

with open('InputEx.DAT', 'r') as f:
    for line in f:
        if 'SAMPLE_MASS' in line:
            mass = float(line.strip().split(',')[1])
            break

