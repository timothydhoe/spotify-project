from pathlib import Path
from paths import get_data_dir

def write_zilver(df, filename):
    """Schrijf een DataFrame weg naar Zilver/spotify_data."""
    data_dir = get_data_dir()
    zilver_dir = data_dir / "Zilver" / "spotify_data"
    zilver_dir.mkdir(parents=True, exist_ok=True)

    output_path = zilver_dir / filename
    df.to_excel(output_path, index=False)

    print("Zilver-bestand geschreven naar:", output_path)
