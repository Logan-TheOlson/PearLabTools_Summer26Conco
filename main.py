
import pandas as pd

df = pd.read_csv('InputEx.DAT', delimiter=",", skiprows=34)

print(df.head())