# Spotify TUI - Interactive Interface

A terminal user interface (TUI) for the Spotify Playlist Manager which lets the user navigate with arrow keys instead of typing commands!

## Installation

```bash
# Install the additional dependency
uv add questionary rich
```

## Usage

```bash
# Run the interactive interface
python spotify_tui.py
```

## Features

### Generate Playlists
- Select participant from list
- Choose playlist type (all/calm/neutral/upbeat)
- Automatically runs generation

### Outlier Detection
- Select participant and playlist type
- Shows outliers in generated playlists
- Validates data quality

### Validate Playlist
- Check if playlist meets criteria
- Shows ISO trajectories
- Validates parameters

### View Statistics
- See participant playlist stats
- Track generation progress

## Navigation

- **↑↓ Arrow keys**: Navigate options
- **Enter**: Select option
- **Ctrl+C**: Exit anytime

## Comparison: CLI vs TUI

### Old way (CLI):
```bash
python scripts/playlists/spotify_cli.py all bosbes
python scripts/playlists/outlier_detection.py --playlist data/playlists/bosbes/playlists_generated/bosbes_calm_playlist.csv --type calm
```

### New way (TUI):
```bash
python spotify_tui.py
# Then just navigate with arrows and press Enter!
```

## CLI Still Available

The original CLI commands still work! Use TUI for interactive work, CLI for scripting/automation.
