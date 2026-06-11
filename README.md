# Project R.E.M.

**Regulation of Emotion through Music**  
VDO Data Scientist Eindwerk

---

## Overview

Project R.E.M. studies whether personalized, ISO-ordered music playlists can measurably
regulate emotional states. The system generates three playlist types — **calm**, **neutral**, and **energy** — from each participant's own Spotify library, then cross-references session outcomes with smartwatch biometrics and self-reported mood check-ins.

**Research questions:**
1. Can ISO-ordered playlists measurably reduce physiological stress?
2. Does reduced stress correlate with improved self-reported mood?
3. Can we classify playlist type from biometric signals alone?
4. Can we predict mood outcome from physiological state + playlist type?

Participants are anonymized with fruit codenames: `bosbes`, `kokosnoot`, `limoen`, `peer`, `kiwi`, `watermeloen`, `aardbei`, `citroen`.

---

## Prerequisites

- **Python 3.12+** and **[uv](https://github.com/astral-sh/uv)** (package manager)
- **Windows:** run shell scripts in [Git Bash](https://git-scm.com/download/win) or WSL

Install uv if you don't have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Windows: dependency groups

Several packages in the `analysis` group (`jax`, `tensorflow`, `pymc`, `torch`) have limited Windows support and may fail to install. If you only need to run the app, skip them:

```bat
uv sync --no-group analysis
```

To install everything (required for the biometric pipeline and ML notebooks), use WSL or a Linux/macOS machine.

---

## Quick Start

```bash
# 1. Clone and set up
git clone <repo-url>
cd spotify-project
./bootstrap.sh

# 2. Place your data files (see Data Setup below)

# 3. Run the biometric pipeline
./scripts/pipeline.sh --all

# 4. Regenerate ML outputs (CSVs, plots, recommendations)
./scripts/notebooks.sh

# 5. Launch the app
./ui/run_app.sh
```

**Windows (app only):**
```bat
uv sync --no-group analysis
uv run shiny run ui/app.py --reload
```
For the full pipeline (biometric processing + ML notebooks), use WSL or Git Bash and run `./bootstrap.sh`.

> **Do I always need to run `notebooks.sh`?**</br>
> Only on a fresh clone (since `data/` is gitignored). The four ML notebooks
> write their outputs — model results, SHAP plots, Bayesian posteriors, music
> classifications — to `data/analysis/`. Once those files exist locally,
> re-running the notebooks is only needed when the underlying wearable data changes.
> Saved models (`models/`) are committed to git, so `notebooks.sh` is fast by default
> (~1–3 min): it loads existing models and re-exports all CSV/JSON/PNG outputs.

---

## Bootstrap Scripts

| Script | What it does |
|--------|-------------|
| `./bootstrap.sh` | First-time setup: checks uv, installs dependencies, creates data directories |
| `./scripts/pipeline.sh` | Biometric pipeline (extraction → baseline → sessions) |
| `./scripts/notebooks.sh` | ML notebooks → app outputs (model results, SHAP, posteriors, music classification) |
| `./scripts/playlists.sh` | Generates playlists for a participant |
| `./ui/run_app.sh` | Launches the Shiny app |

All scripts support `--help`.

---

## Data Setup

Place data files in the right locations before running the pipeline:

```
data/
├── checkins/
│   └── Check-in_formulier_REM.csv        ← Google Forms export
├── playlists/
│   └── <codename>/                        ← Exportify CSVs per participant
└── wearables/
    └── <codename>/
        └── raw/export/                    ← Garmin ZIPs or Huawei JSONs
```

Run `./bootstrap.sh --check` to verify your directory structure at any time.

---

## Running the Pipeline

The pipeline has three stages that run in sequence:

| Stage | Script | What it does |
|-------|--------|-------------|
| 1. Extraction | `scripts/extraction/pipeline.py` | Raw wearable exports → per-minute stress/HR CSVs |
| 2. Baseline | `scripts/baseline/pipeline.py` | Circadian baselines + recovery curves |
| 3. Sessions | `scripts/sessions/pipeline.py` | Session effects, arc analysis, significance tests |

Each stage skips work that's already up to date (freshness checks on output files).

```bash
# Run all participants through all stages
./scripts/pipeline.sh --all

# Run specific participants
./scripts/pipeline.sh bosbes peer

# Force a full re-run, ignoring cached outputs
./scripts/pipeline.sh --all --force

# Skip a stage (e.g. when extraction is already done)
./scripts/pipeline.sh --all --skip-extraction

# Combine options
./scripts/pipeline.sh bosbes --skip-baseline --force
```

---

## Running the Notebooks

The four notebooks in `notebooks/ml/` produce all ML outputs the app reads.
Run them after the biometric pipeline has completed.

```bash
# Fast (default) — load committed models, re-export CSV/JSON/PNG outputs (~1–3 min)
./scripts/notebooks.sh

# Full refit — retrain every model from scratch (~10 min)
./scripts/notebooks.sh --fresh
```

| Notebook | Produces | App page |
|----------|----------|----------|
| `1_circadian_ml.ipynb` | Ridge/RF/GBM results, SHAP plots, Bootstrap CI, RQ3 confusion matrix | Model & Data (RQ3, RQ4) |
| `2_bayesian_recommender.ipynb` | Bayesian posteriors, `recommendations.json`, MCMC diagnostics | Aanbevelingen, Model & Data (RQ4c) |
| `3_music_class_supervised.ipynb` | `classified_songs.csv` per participant (arousal scores) | Jouw Muziek |
| `4_music_class_unsupervised.ipynb` | GMM cluster assignments, PCA scatter | Jouw Muziek (cluster plot) |

The notebooks run in dependency order: notebook 1 must complete before 3 and 4
(they need `feature_matrix.csv` which is built by the biometric pipeline, not by notebook 1 itself).
Notebook 2 is independent.

---

## Generating Playlists

Playlists are generated from a participant's Exportify CSV export using the ISO principle (gradual BPM/energy transitions toward the target state).

```bash
# Full workflow: prepare → generate → analyse
./scripts/playlists.sh bosbes

# Single step
./scripts/playlists.sh bosbes generate

# With parameter overrides
./scripts/playlists.sh bosbes generate --calm-tempo-max 95 --upbeat-energy-min 0.7

# Full CLI help
uv run python scripts/playlists/spotify_cli.py --help
```

Outputs land in `data/playlists/<codename>/playlists_generated/`.

---

## Launching the App

The results are presented in a **Shiny for Python** app styled like Spotify Wrapped.

```bash
# Default (http://127.0.0.1:8000)
./ui/run_app.sh

# Custom port
./ui/run_app.sh --port=8080

# Dev mode with hot-reload
./ui/run_app.sh --reload
```

---

## Project Structure

```
spotify-project/
├── bootstrap.sh               ← First-time setup (Mac/Linux)
├── bootstrap.bat              ← First-time setup (Windows, delegates to .sh)
├── scripts/
│   ├── main.py                ← Master pipeline orchestrator
│   ├── pipeline.sh            ← Shell wrapper for main.py
│   ├── notebooks.sh           ← Runs all 4 ML notebooks → app outputs
│   ├── playlists.sh           ← Shell wrapper for playlist generation
│   ├── extraction/            ← Stage 1: raw wearable data → processed CSVs
│   ├── baseline/              ← Stage 2: circadian baselines + recovery curves
│   ├── sessions/              ← Stage 3: session effects + significance tests
│   ├── playlists/             ← Playlist generation (spotify_cli.py)
│   └── analysis/              ← Standalone analysis scripts (Bayesian, LSTM, etc.)
├── notebooks/
│   ├── ml/                    ← ML model development (Ridge, RF, GBR, Bayesian)
│   └── experimental/          ← Exploratory analysis
├── ui/
│   ├── app.py                 ← Shiny app entry point
│   ├── run_app.sh             ← Shell wrapper to launch the app
│   └── modules/               ← Per-page Shiny modules
└── data/                      ← Gitignored raw data; processed outputs committed
```

---

## Known Data Issues

### Check-in date swapped on mobile (day/month reversed)

When participants fill in the Google Form on a mobile device, the date picker can present fields in MM-DD-YYYY order instead of DD-MM-YYYY. The result is that day and month are swapped — for example, March 10 gets recorded as `3-10-2026`, parsed as October 3.

**Detection:** The `Tijdstempel` column is the server-side submission timestamp and is always reliable. A check-in date that falls after the submission timestamp is a reliable signal that day/month are swapped.

**Fix:** `scripts/wearables/checkin_utils.py` provides `fix_checkin_dates()`, used by all wearables pipeline scripts. It compares each check-in date against the submission timestamp, swaps day/month if suspicious, and emits a `UserWarning` for every corrected row.

---

## Participant Codenames

| Code | Fruit | Biometric data |
|------|-------|----------------|
| bosbes | Blueberry | Full (stress + HR + activity) |
| kokosnoot | Coconut | Full (stress + HR + activity) |
| limoen | Lime | Partial (no stress sensor) |
| peer | Pear | Partial (mood check-ins only) |
| kiwi | Kiwi | Mood check-ins only |
| watermeloen | Watermelon | Mood check-ins only |
| aardbei | Strawberry | - |
| citroen | Lemon | - |

---

## Contributing

### Branch strategy

- `main` — stable code
- `feature/*` — new features
- `fix/*` — bug fixes
- `docs/*` — documentation

### Workflow

```bash
git pull origin main
git checkout -b feature/your-description
# ... make changes ...
git push origin feature/your-description
# Open a Pull Request on GitHub
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for full guidelines.

### Syntax check (no test suite yet)

```bash
uv run python -m py_compile scripts/playlists/spotify_cli.py
```

---

## Contact

**Study:** rem.studie@gmail.com

---

## License

Research project — Hogeschool Vives
