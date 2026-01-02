import json
from paths import get_brons_dir

path = get_brons_dir() / "Spotify_data" / "account_log" / "Playlist1.json"
print("Bestand:", path)

with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

# Toon de top-level keys
print("Top-level keys:", list(data.keys()))

# Toon een klein stukje van de inhoud
print("Eerste 500 karakters:")
print(json.dumps(data, indent=2)[:500])
