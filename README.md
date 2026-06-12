# Project R.E.M.

**Regulation of Emotion through Music** — VDO Data Scientist Eindwerk, Hogeschool Vives

Studies whether personalized ISO-ordered playlists (calm / neutral / energy) can measurably regulate emotional states, cross-referenced with smartwatch biometrics and self-reported mood check-ins.

---

## Prerequisites

- **Python 3.12+** and **[uv](https://github.com/astral-sh/uv)**
- **Windows:** use Git Bash or WSL; run `uv sync --no-group analysis` to skip heavy ML deps (jax, pymc, torch) if you only need the app

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Quick Start

```bash
# 1. First-time setup
./bootstrap.sh

# 2. Place data files (see Data Layout below), then run the biometric pipeline
./scripts/pipeline.sh --all

# 3. Generate ML outputs — fast by default (~1–3 min), models/ is committed
./scripts/notebooks.sh

# 4. Launch the app
./ui/run_app.sh          # → http://127.0.0.1:8000
```

> All scripts accept `--help`. Run `./bootstrap.sh --check` to verify your data directories.

---

## Project Structure

```
spotify-project/
├── scripts/
│   ├── pipeline.sh          ← runs extraction → baseline → sessions
│   ├── notebooks.sh         ← runs all 4 ML notebooks → app outputs
│   ├── playlists.sh         ← playlist generation for a participant
│   ├── extraction/          ← Stage 1: raw wearable exports → per-minute CSVs
│   ├── baseline/            ← Stage 2: circadian baselines + recovery curves
│   ├── sessions/            ← Stage 3: session effects + significance tests
│   ├── playlists/           ← ISO playlist generator (spotify_cli.py)
│   └── analysis/            ← Standalone scripts: Bayesian, LSTM, ML classifiers
├── notebooks/ml/            ← Four ML notebooks (see below)
├── ui/
│   ├── app.py               ← Shiny app entry point
│   └── modules/             ← Per-page Shiny modules
└── data/                    ← Gitignored raw data; processed outputs committed
```

---

## Key Commands

| Task | Command |
|------|---------|
| Full pipeline (all participants) | `./scripts/pipeline.sh --all` |
| Specific participants | `./scripts/pipeline.sh bosbes peer` |
| Force re-run | `./scripts/pipeline.sh --all --force` |
| Skip a stage | `./scripts/pipeline.sh --all --skip-extraction` |
| ML notebooks (fast, default) | `./scripts/notebooks.sh` |
| ML notebooks (full retrain) | `./scripts/notebooks.sh --fresh` |
| Generate playlists | `./scripts/playlists.sh <codename>` |
| App with hot-reload | `./ui/run_app.sh --reload` |

---

## Notebooks → App Outputs

The four notebooks in `notebooks/ml/` run after the biometric pipeline and write everything the app reads. Saved models are committed, so the default run re-exports CSVs/plots without retraining.

| Notebook | Produces |
|----------|---------|
| `1_circadian_ml.ipynb` | Ridge/RF/GBM results, SHAP plots, RQ3 confusion matrix |
| `2_bayesian_recommender.ipynb` | Bayesian posteriors, `recommendations.json` |
| `3_music_class_supervised.ipynb` | `classified_songs.csv` per participant |
| `4_music_class_unsupervised.ipynb` | GMM cluster assignments, PCA scatter |

Notebooks 3 and 4 need `feature_matrix.csv` (built by the biometric pipeline). Notebook 2 is independent.

---

## Data Layout

Place input files here before running the pipeline:

```
data/
├── checkins/
│   └── Check-in_formulier_REM.csv    ← Google Forms export
├── playlists/
│   └── <codename>/                   ← Exportify CSVs per participant
└── wearables/
    └── <codename>/
        └── raw/export/               ← Garmin ZIPs or Huawei JSONs
```

Participants use fruit codenames: `bosbes`, `kokosnoot`, `limoen`, `peer`, `kiwi`, `watermeloen`, `aardbei`, `citroen`.

> `data/wearables/*/raw/` is gitignored — never commit raw exports (they contain participant PII).

---

## Notes

- **SSL on conda:** if `uv sync` fails with `UnknownIssuer`, run `SSL_CERT_DIR="" SSL_CERT_FILE="" uv sync`
- **Check-in date bug:** mobile Google Forms can swap day/month; `scripts/wearables/checkin_utils.py::fix_checkin_dates()` corrects this automatically with a warning
- **No test suite yet:** run `uv run python -m py_compile <file>` for a syntax check before committing

---

**Contact:** rem.studie@gmail.com
