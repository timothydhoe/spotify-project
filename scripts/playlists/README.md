# Spotify Playlist Generator

Generate personalized **Calm**, **Neutral**, and **Upbeat** playlists from Spotify data.

## Overview

Creates three distinct playlists optimized for different purposes:
- **Calm** (50-110 BPM, low energy) - Stress reduction
- **Neutral** (95-115 BPM, medium energy) - Baseline control
- **Upbeat** (110-130 BPM, high energy) - Energy boost

---

## Quick Start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Setup participant folder
mkdir -p data/playlists/aardbei
mv spotify_csvs/*.csv data/playlists/aardbei/

# 3. Generate playlists
python scripts/playlists/spotify_cli.py all aardbei
```

**Done!** Playlists are in `data/playlists/aardbei/playlists_generated/`

See [QUICKSTART.md](QUICKSTART.md) for more details.

---

## Project Structure

```
data/playlists/[codename]/
├── *.csv                           # Input: Exportify CSVs
└── playlists_generated/            # Output: Generated playlists
    ├── combined.csv
    ├── [codename]_calm_playlist.csv
    ├── [codename]_neutral_playlist.csv
    ├── [codename]_upbeat_playlist.csv
    ├── [codename]_analysis_report.txt
    └── [codename]_*.jpg            # Visualisations

scripts/playlists/
├── spotify_cli.py                  # Main CLI
└── spotify_modules/
    ├── prepare.py                  # CSV processing
    ├── generate.py                 # Playlist generation
    └── analyse.py                  # Analysis & visualisation
```

---

## Commands

### `all` - Complete Workflow

```bash
python scripts/playlists/spotify_cli.py all aardbei
```

Runs: prepare → generate → analyse

**Options:**
- `--no-viz` - Skip visualizations
- `--dry-run` - Preview without making changes
- `--calm-tempo-max 120` - Adjust calm playlist parameters

### `prepare` - Process CSVs

```bash
python scripts/playlists/spotify_cli.py prepare aardbei
```

Combines and cleans Exportify CSV files.

### `generate` - Create Playlists

```bash
python scripts/playlists/spotify_cli.py generate aardbei
```

Generates calm, neutral, and upbeat playlists.

**Advanced tuning:**
```bash
python scripts/playlists/spotify_cli.py generate aardbei \
  --calm-tempo-max 95 \
  --upbeat-energy-min 0.7
```

### `analyse` - Validate & Visualize

```bash
python scripts/playlists/spotify_cli.py analyse aardbei
```

Creates validation report and visualizations.

---

## Parameters

### Default Ranges

| Playlist | Tempo (BPM) | Energy  | Purpose          |
|----------|-------------|---------|------------------|
| Calm     | 50-110      | < 0.8   | Stress reduction |
| Neutral  | 95-115      | 0.5-0.7 | Baseline control |
| Upbeat   | 110-130     | > 0.6   | Energy boost     |

### Changing Defaults

**Method 1:** Edit `spotify_cli.py` (lines 38-54)
```python
DEFAULT_PARAMS = {
    'calm': {
        'min_tempo': 50,
        'max_tempo': 120,  # Changed from 110
        'max_energy': 0.8
    },
    ...
}
```

**Method 2:** Command-line flags
```bash
python scripts/playlists/spotify_cli.py all aardbei --calm-tempo-max 120
```

---

## Validation

Analysis checks 4 criteria:
1. Tempo ranges (calm/neutral/upbeat)
2. Energy separation (calm < 0.8, upbeat > 0.6)
3. Tempo difference (15+ BPM between calm/upbeat)
4. Duration (25+ minutes each)

**Scoring:**
- 3-4 checks passed: Good separation
- 2 checks passed: Acceptable
- 0-1 checks passed: Insufficient separation

---

## Troubleshooting

**"No songs match criteria"**
- Export more playlists from Spotify
- Adjust parameters: `--calm-tempo-max 105`

**"Only X/10 songs"**
- Request more diverse playlists from participant
- Relax filtering criteria

**"Cannot find folder"**
- Verify folder structure: `data/playlists/[codename]/`
- Check you're running from project root

---

## Data Collection Workflow

1. **Participant exports data**
   - Visit https://exportify.net
   - Login with Spotify
   - Export 3+ playlists → Download CSVs

2. **Researcher processes**
   ```bash
   mkdir -p data/playlists/aardbei
   mv csvs/*.csv data/playlists/aardbei/
   python scripts/playlists/spotify_cli.py all aardbei
   ```

3. **Review results**
   - Check `analysis_report.txt` for validation
   - Review visualizations
   - Adjust parameters if needed

---

## Technical Details

### ISO Principle

Playlists use the ISO (Iso Principle) ordering:
- **Calm:** Descending activation (stress → relaxation)
- **Upbeat:** Ascending activation (tired → energized)
- **Neutral:** Consistent activation (stable baseline)

Songs are ordered by "activation score" (weighted combo of tempo + energy).

### Dependencies

- pandas - CSV handling
- numpy - Numerical operations
- matplotlib - Visualization
- seaborn - Statistical plots

### Privacy

- All processing is local
- No external data transmission
- Participant codenames ensure anonymity
- Outputs stay within participant folders

---

## Help

```bash
python scripts/playlists/spotify_cli.py --help          # Basic help
python scripts/playlists/spotify_cli.py --help-full     # All options
python scripts/playlists/spotify_cli.py [command] -h    # Command help
```

---

## Support

For issues:
1. Check troubleshooting section above
2. Review validation criteria
3. Verify CSV format matches Exportify
4. Check folder structure

---

## Playlist generator Documentation

### 18 Jan

**Primary sort: Tempo**
- Calm: Descending tempo (high → low BPM)
- Upbeat: Ascending tempo (low → high BPM)

**Secondary sort: Energy**
- Used as tiebreaker for songs with similar tempo
- Maintains gradient consistency

#### METHODEN - Playlist Generatie

Parameters (aangepast voor haalbaarheid):
```
- Calm: 50-90 BPM, energie <0.6
- Upbeat: 110-180 BPM, energie >0.7
- Neutral: 95-115 BPM, energie 0.5-0.7

**Additionele features: acousticness, valence, loudness**
```

ISO-principe implementatie:
Songs gesorteerd primair op tempo:
```
- Calm: Descending (89.8 → 79.4 BPM, gradient: -0.9 BPM/song)
- Upbeat: Ascending (110.4 → 133.8 BPM, gradient: +2.3 BPM/song)
```

Validatie (bij test op bosbes):
```
- 4/4 criteria behaald
- Duidelijke scheiding: 84/105/123 BPM gemiddeld
- Energie separatie: 0.33/0.61/0.81
```

#### Outlier detectie

file: outlier_detection.py
Only used when in doubt if a playlist seems uneffective. Main use is for Quality Assurance.

**Don't routinely check** every playlist

**DO check** when:
- Validation fails
- Trajectory looks wrong
- Participant gives feedback

**DO** document that you used this for quality assurance


