# Quick Start Guide

## Installation

```bash
# From project root
pip install -r requirements.txt
```

## Folder Setup

For each participant:
```bash
# Create participant folder (use fruit codenames)
mkdir -p data/playlists/aardbei

# Add their exported CSV files
mv participant_csvs/*.csv data/playlists/aardbei/
```

## Most Common Usage

### Process participant data (all-in-one)

```bash
# From project root
python scripts/playlists/spotify_cli.py all aardbei --participant aardbei
```

This single command:
1. Finds CSVs in `data/playlists/aardbei/`
2. Creates `data/playlists/aardbei/playlists_generated/`
3. Combines all CSV files
4. Generates three playlists (calm, neutral, upbeat)
5. Creates analysis report and visualizations

### Output files (in playlists_generated folder)

- `aardbei_calm_playlist.csv` - Calm playlist (12 songs)
- `aardbei_neutral_playlist.csv` - Neutral playlist (12 songs) 
- `aardbei_upbeat_playlist.csv` - Upbeat playlist (12 songs)
- `aardbei_analysis_report.txt` - Statistics and validation
- `aardbei_feature_comparison.jpg` - Boxplot comparisons
- `aardbei_tempo_energy.jpg` - Scatter plot
- `aardbei_distributions.jpg` - Feature distributions
- `aardbei_mood_quadrant.jpg` - Mood analysis

## Custom Parameters

If default parameters don't work well:

```bash
# More relaxed calm playlist
python scripts/playlists/spotify_cli.py all aardbei --participant aardbei \
  --calm-tempo-max 95 --calm-energy-max 0.6

# More energetic upbeat playlist
python scripts/playlists/spotify_cli.py all aardbei --participant aardbei \
  --upbeat-tempo-min 115 --upbeat-energy-min 0.7

# Adjust neutral playlist
python scripts/playlists/spotify_cli.py all aardbei --participant aardbei \
  --neutral-tempo-min 100 --neutral-tempo-max 110
```

## Step-by-Step (if needed)

```bash
# 1. Prepare data
python scripts/playlists/spotify_cli.py prepare aardbei

# 2. Generate playlists
python scripts/playlists/spotify_cli.py generate aardbei --participant aardbei

# 3. Analyze results
python scripts/playlists/spotify_cli.py analyze aardbei --participant aardbei
```

## Help

```bash
# See all options
python scripts/playlists/spotify_cli.py --help

# See options for specific command
python scripts/playlists/spotify_cli.py generate --help
```

## Troubleshooting

**"No songs match criteria"**
→ Relax parameters or ask participant for more playlists

**"Only X/10 songs"**
→ Same solution as above

**"FileNotFoundError"**
→ Check you're running from project root and folder structure is correct

**Full documentation: See README.md**
