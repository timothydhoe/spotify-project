from extract_playlists import load_playlists

df = load_playlists()
print(df.head())
print("Aantal tracks in playlists:", len(df))
