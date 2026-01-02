import json
import pandas as pd
from pathlib import Path
from paths import get_brons_dir

def extract_track_id(uri: str):
    """Haal track_id uit een Spotify URI."""
    if not uri:
        return None
    parts = uri.split(":")
    return parts[-1] if len(parts) >= 3 else None

def load_library():
    """Laad YourLibrary.json en geef een DataFrame terug."""
    library_path = get_brons_dir() / "Spotify_data" / "account_log" / "YourLibrary.json"
    print("Library-bestand:", library_path)

    with open(library_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for item in data.get("tracks", []):
        track_id = extract_track_id(item.get("uri"))
        if track_id:
            rows.append({
                "track_id": track_id,
                "track_name": item.get("track"),
                "artist_name": item.get("artist"),
                "owner": "Astrid"
            })

    df = pd.DataFrame(rows)
    return df
