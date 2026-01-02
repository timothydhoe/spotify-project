import json
import pandas as pd
from paths import get_brons_dir
from extract_library import extract_track_id

def load_playlists():
    """Laad Playlist1.json en geef een DataFrame terug."""
    playlist_path = get_brons_dir() / "Spotify_data" / "account_log" / "Playlist1.json"
    print("Playlist-bestand:", playlist_path)

    with open(playlist_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for playlist in data.get("playlists", []):
        for item in playlist.get("items", []):
            track = item.get("track", {})

            # JOUW structuur
            track_uri = track.get("trackUri")
            track_id = extract_track_id(track_uri)

            if track_id:
                rows.append({
                    "track_id": track_id,
                    "track_name": track.get("trackName"),
                    "artist_name": track.get("artistName"),
                    "album_name": track.get("albumName"),
                    "playlist_name": playlist.get("name"),
                    "owner": "Astrid"
                })

    df = pd.DataFrame(rows)
    return df
