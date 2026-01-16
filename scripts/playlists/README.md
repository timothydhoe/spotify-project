# Spotify Playlist Generator CLI

A command-line tool for generating personalized **Calm**, **Neutral**, and **Upbeat** playlists from Spotify data exported via [Exportify.net](https://exportify.net).

## Overview

This tool processes participant Spotify data to create three distinct playlists optimized for different purposes:
- **Calm Playlist**: Lower tempo (50-110 BPM), lower energy - for stress reduction
- **Neutral Playlist**: Medium tempo (95-115 BPM), medium energy - baseline/control condition
- **Upbeat Playlist**: Higher tempo (110-130 BPM), higher energy - for energy boost

## Project Structure

```
spotify-project/
├── data/
│   └── playlists/
│       └── [participant_codename]/      # e.g., aardbei, bosbes, peer
│           ├── playlist1.csv            # Input: Exportify CSVs
│           ├── playlist2.csv
│           └── playlists_generated/     # Output: Generated files (folder added automatically)
│               ├── combined.csv
│               ├── [codename]_calm_playlist.csv
│               ├── [codename]_neutral_playlist.csv
│               ├── [codename]_upbeat_playlist.csv
│               ├── [codename]_analysis_report.txt
│               └── [codename]_*.jpg
├── scripts/
│   └── playlists/
│       ├── spotify_cli.py               # Main CLI
│       └── spotify_modules/
│           ├── __init__.py
│           ├── prepare.py
│           ├── generate.py
│           └── analyze.py
└── requirements.txt
```

## Installation

```bash
# From project root
pip install -r requirements.txt
```

## Quick Start

### Complete Workflow (Recommended)

Process everything in one command:

```bash
# From project root
python scripts/playlists/spotify_cli.py all bosbes --participant bosbes
```

This will:
1. Find CSVs in `data/playlists/bosbes/`
2. Create `data/playlists/bosbes/playlists_generated/`
3. Combine all CSVs
4. Generate three playlists (12 songs each)
5. Analyze and visualize the results

### Step-by-Step Workflow

Run each step individually for more control:

```bash
# Step 1: Prepare (clean and combine CSVs)
python scripts/playlists/spotify_cli.py prepare bosbes

# Step 2: Generate playlists
python scripts/playlists/spotify_cli.py generate bosbes --participant bosbes

# Step 3: Analyze
python scripts/playlists/spotify_cli.py analyze bosbes --participant bosbes
```

## Commands

### `prepare` - Clean and Combine CSVs

Combines multiple Exportify CSV files into one standardized file.

```bash
python scripts/playlists/spotify_cli.py prepare <codename>
```

**What it does:**
- Finds all CSV files in `data/playlists/<codename>/`
- Creates `playlists_generated/` folder
- Standardizes column names (Track Name → name, etc.)
- Removes duplicate tracks
- Saves `combined.csv` in playlists_generated folder

**Example:**
```bash
python scripts/playlists/spotify_cli.py prepare aardbei
```

### `generate` - Create Playlists

Generates calm, neutral, and upbeat playlists with customizable parameters.

```bash
python scripts/playlists/spotify_cli.py generate <codename> --participant <codename> [options]
```

**Options:**
```
Calm playlist:
  --calm-tempo-min INT      Min BPM (default: 50)
  --calm-tempo-max INT      Max BPM (default: 110)
  --calm-energy-max FLOAT   Max energy (default: 0.8)

Neutral playlist:
  --neutral-tempo-min INT   Min BPM (default: 95)
  --neutral-tempo-max INT   Max BPM (default: 115)
  --neutral-energy-min FLOAT Min energy (default: 0.5)
  --neutral-energy-max FLOAT Max energy (default: 0.7)

Upbeat playlist:
  --upbeat-tempo-min INT    Min BPM (default: 110)
  --upbeat-tempo-max INT    Max BPM (default: 130)
  --upbeat-energy-min FLOAT Min energy (default: 0.6)

Other:
  --preview                 Show detailed song lists
```

**Why these parameters matter:**
- **Tempo (BPM)**: Higher tempo = more energizing, lower = more relaxing
- **Energy**: Spotify's measure of intensity (0-1 scale)
- **Neutral**: Provides control/baseline condition for experimental design
- Thresholds are based on music psychology research on tempo/energy effects

**Examples:**
```bash
# Default parameters
python scripts/playlists/spotify_cli.py generate bosbes --participant bosbes

# Custom parameters (more relaxed calm playlist)
python scripts/playlists/spotify_cli.py generate bosbes --participant bosbes \
  --calm-tempo-max 90 --calm-energy-max 0.5

# With preview
python scripts/playlists/spotify_cli.py generate bosbes --participant bosbes --preview
```

### `analyze` - Analyze Playlists

Performs statistical analysis and generates visualizations.

```bash
python scripts/playlists/spotify_cli.py analyze <codename> --participant <codename> [--no-viz]
```

**Generates:**
- Statistical comparison (tempo, energy, valence, etc.)
- 4 visualization JPGs:
  - Feature comparison boxplots
  - Tempo vs Energy scatter plot
  - Feature distributions
  - Mood quadrant analysis
- Text summary report

**Why analysis matters:**
- Validates that playlists are sufficiently different
- Ensures measurable intervention effects
- Identifies if more songs or different parameters are needed

**Example:**
```bash
# Full analysis with visualizations
python scripts/playlists/spotify_cli.py analyze bosbes --participant bosbes

# Analysis only (no visualizations)
python scripts/playlists/spotify_cli.py analyze bosbes --participant bosbes --no-viz
```

### `all` - Complete Workflow

Runs all steps in sequence.

```bash
python scripts/playlists/spotify_cli.py all <codename> --participant <codename> [options]
```

Accepts all the same options as `generate` command.

## Workflow for Data Collection

1. **Participant exports playlists:**
   - Go to https://exportify.net
   - Log in with Spotify
   - Export 3+ playlists → Download CSV
   - Email CSV files

2. **Researcher prepares data:**
   ```bash
   # Create participant folder (use fruit codenames)
   mkdir -p data/playlists/aardbei
   
   # Copy received CSVs into folder
   mv participant_csvs/*.csv data/playlists/aardbei/
   ```

3. **Generate playlists:**
   ```bash
   python scripts/playlists/spotify_cli.py all aardbei --participant aardbei
   ```

4. **Review results:**
   - Check `[codename]_analysis_report.txt` for validation status
   - Review visualizations for quality assurance
   - Find all outputs in `data/playlists/[codename]/playlists_generated/`
   - If validation fails, adjust parameters or request more songs

## Validation Criteria

The analysis checks 4 criteria:

1. **Tempo ranges**: Calm (50-110 BPM), Neutral (95-115 BPM), Upbeat (110-130 BPM)
2. **Energy separation**: Calm < 0.8, Upbeat > 0.6
3. **Substantial tempo difference**: At least 15 BPM between calm and upbeat
4. **Duration**: All playlists ≥ 25 minutes

**Passing 3+/4 checks** = Good playlist separation  
**Passing 2/4 checks** = Acceptable but review recommended  
**Passing <2/4 checks** = Insufficient separation

## Troubleshooting

### "No songs match criteria"

**Cause:** Participant's library doesn't have enough songs in the BPM/energy ranges.

**Solutions:**
- Ask participant to export more playlists
- Relax parameters: `--calm-tempo-max 120 --upbeat-tempo-min 100`
- Check if CSVs contain audio features (tempo, energy columns)

### "Only X/10 songs"

**Cause:** Too few songs meet the criteria.

**Solutions:**
- Request more playlists from participant
- Adjust parameters to be less restrictive
- Check data quality (missing values)

### Visualizations not generating

**Cause:** Missing matplotlib/seaborn dependencies.

**Solution:**
```bash
pip install matplotlib seaborn
```

## Dependencies

Minimal set of standard data science libraries:

- **pandas**: Essential for CSV handling
- **numpy**: Numerical operations
- **matplotlib**: Visualization
- **seaborn**: Statistical plots

No scipy required - validation uses simplified checks.

## Data Privacy

- All processing happens locally
- No data is sent to external servers
- Participant codenames (aardbei, bosbes, etc.) ensure anonymity
- Keep participant folders secure
- All outputs stay within participant's folder

## Technical Details

### Why this architecture?

- **Modular design**: Each step can run independently for flexibility
- **Organized structure**: Separates data, code, and outputs
- **Configurable parameters**: Adapts to different research needs
- **Validation**: Ensures data quality before use in studies
- **Three playlists**: Calm/neutral/upbeat for rigorous experimental design

### Column standardization

Exportify uses verbose names. We standardize them:
```
Track Name       → name
Artist Name(s)   → artists
Tempo            → tempo
Energy           → energy
Duration (ms)    → duration_ms
... etc
```

This makes downstream processing cleaner and consistent.

### Neutral Playlist Purpose

The neutral playlist serves as a control condition:
- Medium tempo/energy to minimize strong effects
- Allows comparison: calm vs neutral vs upbeat
- Essential for experimental designs requiring baseline

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review validation criteria
3. Verify CSV format matches Exportify output
4. Check folder structure matches expected layout
