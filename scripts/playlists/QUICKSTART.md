# Quick Start Guide

## Installation

```bash
pip install -r requirements.txt
```

## Setup

```bash
# Create participant folder
mkdir -p data/playlists/aardbei

# Add Spotify CSV files (from Exportify.net)
mv your_csvs/*.csv data/playlists/aardbei/
```

## Run

```bash
# Generate everything (one command)
python scripts/playlists/spotify_cli.py all aardbei
```

That's it! Your playlists are in `data/playlists/aardbei/playlists_generated/`

---

## Output Files

- `aardbei_calm_playlist.csv` - 12 calm songs
- `aardbei_neutral_playlist.csv` - 12 neutral songs
- `aardbei_upbeat_playlist.csv` - 12 upbeat songs
- `aardbei_analysis_report.txt` - Validation report
- `aardbei_*.jpg` - Visualizations (4 plots)

---

## Custom Parameters

Adjust thresholds if needed:

```bash
# More relaxed calm playlist
python scripts/playlists/spotify_cli.py all aardbei --calm-tempo-max 120

# More energetic upbeat playlist
python scripts/playlists/spotify_cli.py all aardbei --upbeat-tempo-min 120

# Skip visualizations (faster)
python scripts/playlists/spotify_cli.py all aardbei --no-viz
```

---

## Help

```bash
python scripts/playlists/spotify_cli.py --help
python scripts/playlists/spotify_cli.py --help-full  # Advanced options
```

---

## Troubleshooting

**"No songs match criteria"**  
→ Participant needs to export more playlists, or adjust parameters

**"Cannot find folder"**  
→ Check folder structure: `data/playlists/[codename]/`

**Full documentation:** See [README.md](README.md)