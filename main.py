import pandas as pd

#To input a new DAT file for processing drag the file from
#file manager to the left column in the same subfolder as the main.py program
#To then run the program, update the fileName variable with the
# name of the new file and run

fileName="InputEx.DAT"

df = pd.read_table(fileName, delimiter=",", skiprows=34)

with open(fileName, 'r') as f:
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