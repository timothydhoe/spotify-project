from pathlib import Path

here = Path(__file__).resolve()
print("Dit script staat in:", here)

# spotify_pipeline/
pipeline_dir = here.parent
print("Pipeline-map:", pipeline_dir)

# datamining/
datamining_dir = pipeline_dir.parent
print("Datamining-map:", datamining_dir)

# spotify-project/
spotify_project_dir = datamining_dir.parent
print("Spotify-project-map:", spotify_project_dir)

# Eindwerk/
eindwerk_dir = spotify_project_dir.parent
print("Eindwerk-map:", eindwerk_dir)

# Data/
data_dir = eindwerk_dir / "Data"
print("Data-map:", data_dir)
