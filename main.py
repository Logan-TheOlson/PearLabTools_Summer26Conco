import pandas as pd

df = pd.read_table('InputEx.DAT', delimiter=",", skiprows=34)

with open('InputEx.DAT', 'r') as f:
    for line in f:
        if 'SAMPLE_MASS' in line:
            mass = float(line.strip().split(',')[1])
            break

df = df.iloc[:,[2,3,4]]
df = df.dropna(subset=['Moment (emu)'])
df = df.loc[df['Moment (emu)'] != '0']

print(df)
print(mass)
