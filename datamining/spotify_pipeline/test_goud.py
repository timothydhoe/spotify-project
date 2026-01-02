from goud import build_goud

df = build_goud()
print(df.head())
print("Aantal unieke tracks in Goud:", len(df))
