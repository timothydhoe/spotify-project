# Handoff Prompt — Project R.E.M. Notebooks

## What this project is

**Project R.E.M.** (Regulation of Emotion through Music) is a data science thesis project.
The system generates personalised music playlists (calm / neutral / energy) from participants'
Spotify libraries, cross-referenced with smartwatch biometrics and self-reported mood check-ins.
The goal is to study whether ISO-ordered personalised playlists can measurably regulate emotional state.

Participants are anonymised with fruit codenames: **bosbes, kokosnoot, limoen, peer**.
The project lives at: `C:\Users\astri\Desktop\Data_Scientist\Eindwerk\spotify-project`

---

## What we are doing right now

We are replacing all analysis scripts in `scripts/analysis/` with proper Jupyter notebooks,
and adding pipeline explanation notebooks. The full plan is in `docs/notebook_plan.md`.

The work is split into three phases:

1. **Bouwen** — build all ML notebooks + paired visualisation notebooks + pipeline notebooks
2. **Visuals rework** — after all notebooks are built, go back and improve every visual
3. **Opruimen** — delete replaced scripts and stub directories

**Current status (Bouwen phase):**
- [x] `notebooks/ml/bayesian_recommender.ipynb` — built, runs clean
- [x] `notebooks/visualisation/bayesian_recommender_viz.ipynb` — built, runs clean
- [x] `notebooks/ml/circadian_ml.ipynb` — built, runs clean
- [x] `notebooks/visualisation/circadian_ml_viz.ipynb` — built, runs clean
- [x] `notebooks/ml/music_class_thresholds.ipynb`
- [x] `notebooks/visualisation/music_class_thresholds_viz.ipynb`
- [x] `notebooks/ml/music_class_unsupervised.ipynb`
- [x] `notebooks/visualisation/music_class_unsupervised_viz.ipynb`
- [x] `notebooks/visualisation/recovery_analysis.ipynb`
- [ ] `notebooks/visualisation/extraction_pipeline.ipynb`
- [ ] `notebooks/visualisation/baseline_pipeline.ipynb`
- [ ] `notebooks/visualisation/sessions_pipeline.ipynb`

---

## Next step

**Build `notebooks/visualisation/extraction_pipeline.ipynb` directly in Jupyter.**

Do NOT use a generation script. Write the notebook cells by hand using NotebookEdit/Write.

Agreed structure (approved by user):
1. Markdown: title + pipeline overview (input → output diagram)
2. Code: imports + constants (PROJECT_ROOT, OI palette, dark theme, PARTICIPANTS, DEVICE map)
3. Code: data loading (stress, HR, session_biometrics, session_traces_all, classified_minutes per participant) — load `session_biometrics.csv` WITHOUT `index_col=0` so `date` stays a column
4. Markdown: Sectie 1 — Datadekking uitleg
5. Code: lollipop (continuous segments per participant) + wearing strip (pcolormesh, `shading='nearest'`, Y = `np.arange(n) + 0.5`, X = date_range)
6. Markdown: Sectie 2 — Minuut-voor-minuut signalen
7. Code: time series (stress + HR, 5-min downsample, session marker lines)
8. Markdown: Sectie 3 — Check-in koppeling
9. Code: check-in matching table (total / matched / unmatched per participant)
10. Markdown: Sectie 4 — Sessietrace
11. Code: session trace viz (pre / during / post phases, one participant example)
12. Markdown: Sectie 5 — Activiteitsclassificatie
13. Code: activity classification stacked bar chart

Before writing any code, follow the Q&A convention: ask ONE clarifying question at a time.

---

## Architecture rules (non-negotiable)

- `notebooks/ml/` = model logic only (data loading, train/load, diagnostics, export)
- `notebooks/visualisation/` = all visualisation (ML insights + pipeline explanations)
- `models/{model_name}/` = serialised artifacts only (.pkl, .nc, .json) — one subfolder per model
- Pipeline explanation notebooks belong in `visualisation/`, NOT in a separate `pipeline/` folder
- No imports from `scripts/` — all functions must be inlined
- `REUSE_MODEL` flag at top of every ML notebook
- `PARTICIPANT = "all"` at top, auto-detect from data — no hardcoded participant lists
- `PROJECT_ROOT = Path().resolve().parent.parent` (notebooks live two levels deep)
- Dark theme: `figure.facecolor: #0f1218`, `axes.facecolor: #181e2a`, Okabe-Ito palette, monospace font
- Dutch markdown, English code
- `FileNotFoundError` with clear Dutch message if required inputs are missing
- For the circadian ML notebook specifically: `models/circadian_ml/models.pkl` stores
  comparisons, results, fitted pipelines, X_data, y_data, groups, feature_names so the
  viz notebook can load everything without re-fitting

---

## Conversational rules (follow these strictly)

### Questions
- Ask ONE clarifying question at a time — never a list
- Wait for the answer before asking the next
- If unsure what the user wants, ask "What would you do?" before proposing anything

### Changes
- Always explain what will change and why before touching any file
- Always ask permission before executing changes
- Never repeat an idea that was already rejected

### Visuals (rework phase — not yet started)
- Every visual gets: clear title, annotation explaining what you're looking at,
  plain-language interpretation — no jargon
- Ask which visuals to keep/change/replace before touching the notebook
- Propose chart type + what it shows before building it

---

## Notebook 3 — `ml/music_class_thresholds.ipynb` (NEXT)

**Sources:**
- `scripts/analysis/music_classification.py` — rule-based arousal scoring, 343 lines
- `notebooks/ml_music_classification.ipynb` — 8 phases; prefer this for EDA, threshold tuning, spot-checks

**Approach:** MinMaxScaler → weighted arousal score → threshold classification (calm / energy / other)

**Artifacts to save:** `models/music_classification/scaler.pkl`, `models/music_classification/config.json`

**Output:** `data/analysis/{codename}/classified_songs.csv`

**`REUSE_MODEL`:** True → load scaler + config from `models/music_classification/`; False → fit and save

**Key note:** `ml_music_classification.ipynb` is more thorough than the script — prefer its EDA,
threshold tuning, and spot-check sections where they differ. No imports from the script.

---

## Notebook 3 paired viz — `visualisation/music_class_thresholds_viz.ipynb`

**Purpose:** Per-participant classification insights — loads from `models/music_classification/`,
shows classified song distributions, threshold effectiveness, spot-checks.
No model training.

---

## Notebook 4 — `ml/music_class_unsupervised.ipynb`

**Source:** `scripts/analysis/music_classifier.py` (GMM + BIC, 479 lines)

**Approach:**
- GMM with BIC model selection (k=2–10)
- k=3 forced comparison (matches playlist types)
- PCA scatter, radar chart, cluster report
- KMeans as validation baseline

**`REUSE_MODEL`:** True → load GMM from `models/music_unsupervised/gmm.pkl`

---

## Data context

Feature matrix rebuilt and available: `data/analysis/circadian_baselines/feature_matrix.csv`
- 82 sessions: kokosnoot 40, peer 30, limoen 8, bosbes 4
- Circadian ML models trained and saved to `models/circadian_ml/models.pkl`
- Bayesian trace at `models/bayesian_recommender/trace.nc`

All four participants have processed wearable data under `data/wearables/{codename}/processed/`.
Pipeline has been run on all four: extraction → baseline → sessions all up-to-date.

---

## Environment

- Python 3.12, managed by `uv` — always use `uv run python`, never bare `python`
- Venv at `.venv/`, kernel registered as `spotify-project`
- Run from project root
- `PYTHONUTF8=1` set in `~/.bashrc`
- No automated test suite — use `uv run python -m py_compile <script>` to syntax-check
