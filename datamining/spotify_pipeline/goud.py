import pandas as pd
from extract_library import load_library
from extract_playlists import load_playlists

def build_goud():
    """Combineer library + playlists tot één Goud-tabel."""

    df_lib = load_library()
    df_pl = load_playlists()

    # Voeg samen
    df = pd.concat([df_lib, df_pl], ignore_index=True)

    # Verwijder dubbele tracks op basis van track_id
    df = df.drop_duplicates(subset=["track_id"])

    # Sorteer voor consistentie
    df = df.sort_values(by="track_name", na_position="last")

    return df
