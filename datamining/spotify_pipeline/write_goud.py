from pathlib import Path
from paths import get_data_dir

def write_goud(df, filename="goud_master.xlsx"):
    """Schrijf de Goud-laag weg naar Data/Goud/spotify_data."""
    data_dir = get_data_dir()
    goud_dir = data_dir / "Goud" / "spotify_data"
    goud_dir.mkdir(parents=True, exist_ok=True)

    output_path = goud_dir / filename
    df.to_excel(output_path, index=False)

    print("Goud-bestand geschreven naar:", output_path)
