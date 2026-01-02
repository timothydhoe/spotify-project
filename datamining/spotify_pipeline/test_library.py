from extract_library import load_library

df = load_library()
print(df.head())
print("Aantal tracks in library:", len(df))
