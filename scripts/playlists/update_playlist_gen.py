"""
update_playlist_gen.py

Generates three playlists (calm, energy, neutral) from ML-classified song data
for hardcoded participants: kokosnoot and peer.

Input:  data/playlists/[participant]/playlist_ml/classified_songs.csv
Output: data/playlists/[participant]/playlist_0204/{calm,energy,neutral}_playlist.csv
"""

import pandas as pd
from pathlib import Path

PARTICIPANTS = ["kokosnoot", "peer"]
PLAYLIST_SIZE = 10
BASE_DIR = Path(__file__).resolve().parents[2] / "data" / "playlists"

CLASS_MAP = {
    "calm": "calm",
    "energy": "energy",
    "neutral": "other",  # 'other' in the class column maps to neutral playlist
}


def generate_playlists(participant: str) -> None:
    input_path = BASE_DIR / participant / "playlist_ml" / "classified_songs.csv"
    output_dir = BASE_DIR / participant / "playlist_0204"

    if not input_path.exists():
        print(f"[{participant}] Input file not found: {input_path}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path)

    for playlist_name, class_label in CLASS_MAP.items():
        pool = df[df["class"] == class_label]

        if len(pool) < PLAYLIST_SIZE:
            print(
                f"[{participant}] Warning: only {len(pool)} '{class_label}' songs "
                f"available (wanted {PLAYLIST_SIZE}). Using all of them."
            )
            sample = pool
        else:
            sample = pool.sample(n=PLAYLIST_SIZE, random_state=None)

        out_path = output_dir / f"{playlist_name}_playlist.csv"
        sample.to_csv(out_path, index=False)
        print(f"[{participant}] {playlist_name}: {len(sample)} songs → {out_path}")


if __name__ == "__main__":
    for participant in PARTICIPANTS:
        generate_playlists(participant)
