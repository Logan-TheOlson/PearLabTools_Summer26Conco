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

#Converting to Tesla
df.iloc[:,1]= df.iloc[:, 1].astype(float) * 10**(-4)
#Moment to magnetic moment /mass
df.iloc[:,2]= df.iloc[:, 2].astype(float)/(mass/10**6)

df.rename(columns={'Moment (emu)':'Moment (J/T)'}, inplace=True)
df.rename(columns={'Magnetic Field (Oe)':'Magnetic Field (T)'}, inplace=True)

print(df)
print("The mass of the sample is "+str(mass)+ " mg")
#push