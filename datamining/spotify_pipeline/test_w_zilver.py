from extract_library import load_library
from extract_playlists import load_playlists
from write_zilver import write_zilver

# Test library
df_lib = load_library()
write_zilver(df_lib, "library_astrid.xlsx")

# Test playlists
df_pl = load_playlists()
write_zilver(df_pl, "playlist_astrid.xlsx")
