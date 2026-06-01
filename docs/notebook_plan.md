# Notebook Plan — Project R.E.M.

## Working conventions

### Tempo & volgorde
- Tackle one notebook at a time, in execution order
- For the visuals rework phase: one notebook at a time, ask questions per visual to decide what to keep/change/add before touching any code

### Vragen stellen
- Ask one clarifying question at a time — never a list
- Wait for the answer before asking the next
- If unsure what the user wants, ask "What would you do?" to get direction before proposing anything

### Wijzigingen
- Always explain what will change and why before making any file changes
- Always ask for permission before executing changes
- Never repeat an idea that was already rejected

### Visuals (rework fase)
- Every visual gets: a clear title, annotation explaining what you're looking at, and a plain-language interpretation — no jargon
- Ask the user which visuals to keep, change, or replace before touching the notebook
- Propose chart type + what it shows before building it

---

## Goal

Replace the four ML scripts in `scripts/analysis/` with proper notebooks. Add pipeline explanation notebooks. Reorganise `notebooks/` into subfolders. Each ML notebook absorbs the relevant existing notebook (viz or analysis) so no separate file is needed.

---

## Target structure

```
notebooks/
├── ml/                                    # ML model notebooks — model logic only
│   ├── bayesian_recommender.ipynb         data loading + model + diagnostics + export artifacts
│   ├── circadian_ml.ipynb                 data loading + Ridge/RF/GBR + diagnostics + export
│   ├── music_class_thresholds.ipynb       data loading + arousal scoring + export
│   └── music_class_unsupervised.ipynb     data loading + GMM/KMeans + export
├── visualisation/                         # All visualisation notebooks — ML insights + pipeline explanation
│   ├── bayesian_recommender_viz.ipynb     loads models/bayesian_recommender/, posteriors + recommendations
│   ├── circadian_ml_viz.ipynb             loads models/circadian_ml/, SHAP + predictions
│   ├── music_class_thresholds_viz.ipynb   loads models/music_classification/, classifications per participant
│   ├── music_class_unsupervised_viz.ipynb loads models/music_unsupervised/, cluster plots
│   ├── recovery_analysis.ipynb            moved from notebooks/ root
│   ├── extraction_pipeline.ipynb          explains extraction output stage by stage
│   ├── baseline_pipeline.ipynb            explains baseline computation + hourly curves
│   └── sessions_pipeline.ipynb            explains session arc + recovery analysis
├── _old/                                  # Legacy notebooks — untouched
├── _tmp/                                  # In-progress drafts
└── who_needs_reminding.ipynb              stays in root (Google Colab tool, separate system)

models/
├── bayesian_recommender/   # .nc, .json artifacts only
├── circadian_ml/           # .pkl artifacts only
├── music_classification/   # .pkl, .json artifacts only
└── music_unsupervised/     # .pkl artifacts only
```

**Rule**: `models/` subfolders contain serialized artifacts only (`.nc`, `.pkl`, `.json`). Results, CSVs, and plots go to `data/analysis/` as always.

---

## Notebooks to delete after replacement

| Existing file | Replaced by |
|---|---|
| `notebooks/bayesian_recommender_viz.ipynb` | absorbed into `ml/bayesian_recommender.ipynb` |
| `notebooks/circadian_ml_analysis.ipynb` | renamed/moved to `ml/circadian_ml.ipynb` |
| `notebooks/ml_music_classification.ipynb` | split into `ml/music_class_thresholds.ipynb` + `ml/music_class_unsupervised.ipynb` |
| `notebooks/recovery_analysis.ipynb` | moved to `visualisation/recovery_analysis.ipynb` |

---

## Scripts to delete after notebook is confirmed working

| Script | Deleted when |
|---|---|
| `scripts/analysis/bayesian_recommender.py` | `ml/bayesian_recommender.ipynb` verified |
| `scripts/analysis/circadian_ml.py` | `ml/circadian_ml.ipynb` verified |
| `scripts/analysis/music_classification.py` | `ml/music_class_thresholds.ipynb` verified |
| `scripts/analysis/music_classifier.py` | `ml/music_class_unsupervised.ipynb` verified |
| `scripts/pipeline/` (stub directory) | already absorbed by `scripts/main.py` — can delete now |

---

## Execution order

```
1. ml/bayesian_recommender.ipynb        (hierarchical Bayesian — most complex)
2. ml/circadian_ml.ipynb                (Ridge/RF/GBR + SHAP — update existing)
3. ml/music_class_thresholds.ipynb      (rule-based arousal scoring)
4. ml/music_class_unsupervised.ipynb    (GMM + KMeans clustering)
5. visualisation/recovery_analysis.ipynb (move only, update sys.path imports)
6. pipeline/extraction_pipeline.ipynb
7. pipeline/baseline_pipeline.ipynb
8. pipeline/sessions_pipeline.ipynb
```

---

## Shared conventions (all notebooks)

### Visual style
Match `notebooks/recovery_analysis.ipynb` exactly:
- Dark background: `'figure.facecolor': '#0f1218'`
- Palette: Okabe-Ito
- Font: monospace
- Language: Dutch (with English code)

### Structure per ML notebook

1. **Setup** — imports, paths, `PARTICIPANT` variable at top (set to a single codename or `"all"`); if `"all"`, loop over all participants
2. **Data loading** — load from `data/analysis/` pipeline outputs; fail with a clear error if inputs are missing (do not silently produce empty output)
3. **Model** — `REUSE_MODEL` flag at top; if `True`, load from `models/`; if `False`, train and save to `models/`
4. **Diagnostics** — minimal checks: train/val scores, not-overfitting check, residual or confusion plot
5. **Results + visualisation** — outputs saved to `data/analysis/`; plots shown inline
6. **Recommendations / conclusions** — interpret what the model says per participant

### Structure per pipeline notebook

1. **Setup** — imports, paths, `PARTICIPANT` variable
2. **Stage-by-stage walkthrough** — one section per pipeline stage; load the intermediate output, show what it contains, visualise key signals
3. **Conclusions** — what does this stage produce and why does it matter

### models/ directory

Contains **serialized model artifacts only**: `.pkl`, `.nc` (NumPyro trace), `.json` (config/thresholds).
Results, CSVs, and plots go to `data/analysis/` as always.
Current contents: `config.json`, `scaler.pkl` (from `music_classification.py`).

---

## Notebook 1a — `ml/bayesian_recommender.ipynb`

**Purpose:** Model only — no participant visualisation.

**Source:** `scripts/analysis/bayesian_recommender.py`

**Key functions to inline:**
- `build_model_data()` — data prep, VALENCE_MAP emotion scoring
- `build_hierarchical_model()` — PyMC model definition
- `fit_model()` — MCMC sampling via NumPyro/JAX
- `check_convergence()` — r-hat, ESS checks
- `export_streamlit_json()` — save recommendations for Streamlit app

**Artifacts saved to `models/bayesian_recommender/`:** `trace.nc`, `summary.json`

**`REUSE_MODEL`:** if `True`, load trace from `models/bayesian_recommender/trace.nc`; skip sampling

**Missing input:** `feature_matrix.csv` missing → soft fallback with warning (no hard fail)

**Missing trace when `REUSE_MODEL=True`:** raise `FileNotFoundError` with clear message

---

## Notebook 1b — `visualisation/bayesian_recommender_viz.ipynb`

**Purpose:** Per-participant insights — loads artifacts from `models/bayesian_recommender/`, no model training.

**Source:** `notebooks/bayesian_recommender_viz.ipynb`

**Content:**
- Mood data overview (valence map, raw mood_delta bar chart)
- Posterior distributions per participant (grid)
- Group-level effects (forest plot)
- Shrinkage plot
- Biometric coefficients
- Recommendation table + horizontal bar chart
- Sensitivity analysis (uses `PARTICIPANT` variable)

**`PARTICIPANT`:** single codename or `"all"` (sensitivity section uses first participant with biometrics when `"all"`)

**Missing trace:** raise `FileNotFoundError` if `models/bayesian_recommender/trace.nc` not found

---

## Notebook 2 — `ml/circadian_ml.ipynb`

**Source:**
- `notebooks/circadian_ml_analysis.ipynb` (update in place, rename, move)
- `scripts/analysis/circadian_ml.py` (verify all logic is covered)

**Known fix needed:** section 8.5 uses `.style.applymap()` which requires jinja2 (not installed). Replace with plain `display()` or remove.

**Models:** Ridge, RF, GBR, DummyMean
**Evaluation:** LOO cross-validation (MAE, RMSE, R²), imputation inside folds
**Explainability:** SHAP + permutation importance (not for inference — clearly documented)

**`REUSE_MODEL`:** if `True`, load fitted models from `models/circadian_ml_models.pkl`

---

## Notebook 3 — `ml/music_class_thresholds.ipynb`

**Sources:**
- `scripts/analysis/music_classification.py` (rule-based arousal scoring, 343 lines)
- `notebooks/ml_music_classification.ipynb` (8 phases — more thorough than the script; reimplemented independently, no imports from script)

**Approach:** MinMaxScaler → weighted arousal score → threshold classification (calm / energy / other)
**Models saved:** `models/scaler.pkl`, `models/config.json` (already there)
**Output:** `data/analysis/{codename}/classified_songs.csv`

**`ml_music_classification.ipynb` is more thorough** — prefer its EDA, threshold tuning, and spot-check sections over the script where they differ.

---

## Notebook 4 — `ml/music_class_unsupervised.ipynb`

**Source:** `scripts/analysis/music_classifier.py` (GMM + BIC, 479 lines)

**Approach:**
- GMM with BIC model selection (k=2–10)
- k=3 forced comparison (matches playlist types)
- PCA scatter, radar chart, cluster report
- KMeans as validation baseline

**`REUSE_MODEL`:** if `True`, load GMM from `models/music_gmm.pkl`

---

## Notebook 5 — `visualisation/recovery_analysis.ipynb`

**Source:** `notebooks/recovery_analysis.ipynb` (move only)

**Changes needed:**
- Update `sys.path` imports: `recovery_analysis.py` moved from `notebooks/` to `scripts/sessions/` — fix any path references
- No logic changes — this is the reference visual style notebook; touch as little as possible

---

## Notebooks 6–8 — `pipeline/extraction_pipeline.ipynb`, `pipeline/baseline_pipeline.ipynb`, `pipeline/sessions_pipeline.ipynb`

**Purpose:** Descriptive — explain each pipeline stage with live data from one participant. Show what goes in, what comes out, and why each step exists.

**Content per notebook:**
- Load pipeline outputs from `data/`
- Visualise key signals per stage (e.g., minute-level stress + activity states for extraction; hourly baseline curves for baseline; recovery advantage distributions for sessions)
- Dutch narrative explaining what each step does and what the results mean
- `PARTICIPANT` variable at top; support `"all"` where useful

**No model training or CSV exports** — purely explanatory + visual.

---

## STATUS

### Bouwen

- [x] `ml/bayesian_recommender.ipynb`
- [x] `visualisation/bayesian_recommender_viz.ipynb`
- [x] `ml/circadian_ml.ipynb`
- [x] `visualisation/circadian_ml_viz.ipynb`
- [x] `ml/music_class_thresholds.ipynb`
- [x] `visualisation/music_class_thresholds_viz.ipynb`
- [x] `ml/music_class_unsupervised.ipynb`
- [x] `visualisation/music_class_unsupervised_viz.ipynb`
- [x] `visualisation/recovery_analysis.ipynb`
- [ ] `visualisation/extraction_pipeline.ipynb`
- [ ] `visualisation/baseline_pipeline.ipynb`
- [ ] `visualisation/sessions_pipeline.ipynb`

### Visuals rework (na bouwen — per notebook, één voor één)

Elk visueel krijgt: heldere titel, annotaties die uitleggen wat je ziet, interpretatie zonder jargon.

- [ ] `visualisation/bayesian_recommender_viz.ipynb`
- [ ] `ml/circadian_ml.ipynb`
- [ ] `visualisation/circadian_ml_viz.ipynb`
- [ ] `ml/music_class_thresholds.ipynb`
- [ ] `visualisation/music_class_thresholds_viz.ipynb`
- [ ] `ml/music_class_unsupervised.ipynb`
- [ ] `visualisation/music_class_unsupervised_viz.ipynb`
- [ ] `visualisation/recovery_analysis.ipynb`
- [ ] `visualisation/extraction_pipeline.ipynb`
- [ ] `visualisation/baseline_pipeline.ipynb`
- [ ] `visualisation/sessions_pipeline.ipynb`

### Opruimen

- [x] Delete replaced scripts from `scripts/analysis/`
- [x] Delete `scripts/pipeline/` stub
