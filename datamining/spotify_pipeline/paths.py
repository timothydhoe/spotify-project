from pathlib import Path

def get_data_dir():
    # Vind de Data-map op basis van de locatie van dit bestand
    here = Path(__file__).resolve()
    pipeline_dir = here.parent
    datamining_dir = pipeline_dir.parent
    spotify_project_dir = datamining_dir.parent
    eindwerk_dir = spotify_project_dir.parent
    data_dir = eindwerk_dir / "Data"
    return data_dir

def get_brons_dir():
    return get_data_dir() / "Brons"
