# Project R.E.M.

**Regulation of Emotion through Music**  
VDO Data Scientist Eindwerk

---

## Overview

This project generates personalized music playlists to support emotion regulation research. The system creates three playlist types (calm, neutral, upbeat) based on participants' Spotify listening data.

**Key Features:**
- Automated playlist generation from Spotify data
- ISO principle-based song ordering
- Validation and quality analysis
- Privacy-preserving participant management (fruit codenames)

---

## Quick Start

```bash
# Install dependencies
uv sync

# Generate playlists for a participant
python scripts/playlists/spotify_cli.py all aardbei
```

See [QUICKSTART.md](scripts/playlists/QUICKSTART.md) for detailed instructions.

---

## Project Structure

```
spotify-project/
├── data/
│   └── playlists/
│       └── [participant]/           # Participant data (fruit codenames)
│           ├── *.csv                # Input: Exportify CSVs
│           └── playlists_generated/ # Output: Generated playlists
├── docs/
│   ├── info_deelnemers/             # Participant information
│   └── research_muziek/             # Research documentation
├── scripts/
│   └── playlists/
│       ├── spotify_cli.py           # Main CLI
│       ├── spotify_modules/         # Core playlist logic
│       ├── QUICKSTART.md            # Getting started guide
│       └── README.md                # Full documentation
└── tests/                           # Unit tests
```

---

## Participant Codenames

Participants are assigned fruit codenames for privacy:

| Code | Fruit | Status |
|------|-------|--------|
| peer | Pear | - |
| bosbes | Blueberry | - |
| limoen | Lime | - |
| aardbei | Strawberry | - |
| watermeloen | Watermelon | - |

Full list: cherry, grape, peach, orange, lemon, pineapple, banana, apple, kiwi, mango, coconut

---

## Workflow

### Data Collection
1. Participant exports Spotify data via [Exportify.net](https://exportify.net)
2. CSV files placed in `data/playlists/[codename]/`
3. Playlists generated via CLI
4. Outputs delivered to participant

### Development
```bash
# Create feature branch
git checkout -b feature/your-feature

# Make changes, commit, push
git push origin feature/your-feature

# Create Pull Request on GitHub
```

See [contributing.md](contributing.md) for full workflow.

---

## Key Commands

```bash
# Generate playlists (complete workflow)
python scripts/playlists/spotify_cli.py all [codename]

# Step-by-step
python scripts/playlists/spotify_cli.py prepare [codename]
python scripts/playlists/spotify_cli.py generate [codename]
python scripts/playlists/spotify_cli.py analyse [codename]

# Quick analysis
python scripts/playlists/quick_playlist_analysis.py \
  --calm path/to/calm.csv \
  --upbeat path/to/upbeat.csv \
  --id [codename]
```

---

## Documentation

- **QUICKSTART.md** - Quick getting started guide
- **README.md** (in scripts/playlists/) - Full CLI documentation
- **docs/info_deelnemers/** - Participant information materials
- **docs/research_muziek/** - Research methodology

---

## Contributing

### Branch Strategy
- `main` - Stable production code
- `feature/*` - New features
- `fix/*` - Bug fixes
- `docs/*` - Documentation updates

### Workflow
1. Pull latest: `git pull origin main`
2. Create branch: `git checkout -b feature/description`
3. Make changes and commit
4. Push: `git push origin feature/description`
5. Create Pull Request on GitHub
6. After merge: Delete branch and pull main

### Commit Messages
- Use descriptive messages: `Add email validation for participants`
- Not: `fix stuff`, `updates`, `wip`

---

## Contact

**Study Contact:** rem.study@gmail.com

---

## License

Research project - Hogeschool Vives