import pandas as pd
import glob

"""
First, create a candidate folder containing all the csv files.

├─ P-5347/
│   ├─ file1.csv
│   ├─ file2.csv
│   ├─ file3.csv   ← just add more files here
│
└─ combined_csvs.py
"""

# get all CSV files in the folder
csv_files = glob.glob("docs/td_playground/testdata/bosbes/Evelien_Viroux.csv") # change 'P-XXX' with candidate folder.

# read and combine
df = pd.concat(
    (pd.read_csv(file) for file in csv_files),
    ignore_index=True
    ).sort_index(axis=1)

# save concatenated csv file
df.to_csv("combined.csv", index=False)

print(f"Combined {len(csv_files)} files into combined.csv")