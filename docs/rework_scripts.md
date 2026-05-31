# Pipeline Reorganisation Plan — Project R.E.M.

## STATUS TRACKER (update as work progresses)
- [x] Pipeline 1 — extraction/
- [x] Pipeline 2 — baseline/
- [x] Pipeline 3 — sessions/
- [x] Master pipeline (main.py)
- [ ] Notebooks (ML scripts converted) — plan in docs/notebook_plan.md

**Currently working on:** Notebooks (ML scripts converted)

---

## Context

`scripts/analysis/` and `scripts/wearables/` have grown into overlapping, flat collections. The goal is to consolidate everything into **three focused sub-pipelines** living directly under `scripts/`, each with a single entry point, wired together by a master orchestrator (`scripts/main.py`). ML/exploratory scripts become notebooks. **Duplicate code and functions must be merged, not copied, during each migration.**

---

## Target Architecture

```
scripts/
├── main.py              ← master orchestrator (adapted from scripts/pipeline/main.py stub)
├── pipeline_config.py   ← adapted from scripts/pipeline/pipeline_config.py; real paths
├── extraction/          ← Pipeline 1: raw wearable data → per-minute CSVs
│   ├── pipeline.py      ← entry point
│   ├── garmin_pipeline.py   (moved from scripts/wearables/)
│   ├── huawei_pipeline.py   (moved from scripts/wearables/)
│   ├── fit_extractor.py     (moved from scripts/analysis/)
│   └── activity_classifier.py (moved from scripts/analysis/)
├── baseline/            ← Pipeline 2: per-participant baselines
│   ├── pipeline.py      ← entry point
│   ├── baselines.py         (moved from scripts/analysis/)
│   └── circadian_baseline.py (moved from scripts/analysis/)
└── sessions/            ← Pipeline 3: session effects (short + long term)
    ├── pipeline.py      ← entry point (absorbs scripts/analysis/pipeline.py)
    ├── session_effect.py    (moved from scripts/analysis/)
    ├── session_features.py  (moved from scripts/analysis/)
    ├── session_arc_analysis.py (moved from scripts/analysis/)
    ├── circadian_significance.py (moved from scripts/analysis/)
    └── recovery_analysis.py (converted from notebooks/recovery_analysis.ipynb)

notebooks/
    ├── bayesian_recommender.ipynb   (converted from scripts/analysis/)
    ├── circadian_ml.ipynb           (converted from scripts/analysis/)
    ├── music_classification.ipynb   (converted from scripts/analysis/)
    └── music_classifier.ipynb       (converted from scripts/analysis/)
```

**Retired after reorganisation:** `scripts/analysis/` (emptied), `scripts/wearables/` (emptied), `scripts/pipeline/` (absorbed), `scripts/analysis/pipeline.py` (logic absorbed into sessions/pipeline.py).

**Note:** `scripts/playlists/` stays untouched — it's a separate, complete subsystem.

---

## Pipeline Descriptions

### Pipeline 1 — extraction/
**Purpose:** Pulls raw smartwatch data (Garmin or Huawei GDPR export) and check-ins, produces cleaned per-minute CSVs and session traces.

**Entry point CLI:** `uv run python scripts/extraction/pipeline.py [codename|--all]`

**Stages:**
1. `garmin_pipeline.py run()` or `huawei_pipeline.py run()` (device detected from available raw data)
2. `fit_extractor.run()` — extracts intensity/steps from FIT binaries
3. `activity_classifier.ActivityClassifier().predict()` — adds per-minute activity state

**Skip condition:** If `data/wearables/{codename}/processed/garmin_minute_stress.csv` (or huawei equivalent) exists and is newer than raw export, skip extraction.

**Output:** `data/wearables/{codename}/processed/` (unchanged locations)

---

### Pipeline 2 — baseline/
**Purpose:** Computes per-participant circadian (hourly) stress/HR baselines and recovery curves from non-session days.

**Entry point CLI:** `uv run python scripts/baseline/pipeline.py [codename|--all]`

**Stages:**
1. `circadian_baseline.py` — hourly baseline + feature matrix
2. `baselines.py` — recovery curves (exponential fit) + PersonBaseline objects

**Skip condition:** If `data/analysis/{codename}/circadian_baselines/hourly_baseline.csv` exists and is newer than minute-level wearable CSVs.

**Output:** `data/analysis/{codename}/circadian_baselines/`, `data/analysis/circadian_baselines/feature_matrix.csv`

---

### Pipeline 3 — sessions/
**Purpose:** Measures short-term session effects (pre/during/post biometrics, recovery advantage) and long-term trends; runs significance tests.

**Entry point CLI:** `uv run python scripts/sessions/pipeline.py [codename|--all]`

**Stages:**
1. `session_effect.py` — per-session recovery advantage vs baseline curve
2. `session_features.py` — flat ML feature table per session
3. `session_arc_analysis.py` — arc deviations, window comparisons, long-term trends
4. `circadian_significance.py` — Wilcoxon + OLS significance tests
5. `recovery_analysis.py` — recovery curves (converted from notebooks/recovery_analysis.ipynb)

**Skip condition:** If `data/analysis/session_arc/significance_results.csv` exists and is newer than baseline outputs.

**Output:** `data/analysis/session_arc/`, `data/analysis/circadian_baselines/significance_tests.csv`

**Known issue — resolved during migration (2026-05-31):**
`PersonBaseline.get_recovery_curve()` — most fitted curves have R²≈0 (noisy segments,
wrong y0 anchor, majority of transitions not true recovery events). Decision: no hard
upstream filter. Instead, add `r2_expected` column to session_effect.py output so
analysts can apply any threshold at analysis time. `recovery_analysis.py` defines the
`reliable` flag (r2_actual > threshold AND pre_stress ≥ asymptote) for primary conclusions.

---

### Pipeline 3 — Detailed Migration Plan (finalised 2026-05-31)

**Decisions made before migration:**

| # | Question | Decision |
|---|----------|----------|
| 1 | R² guard | No hard filter upstream. Add `r2_expected` to session_effect.py output. Apply threshold at analysis time in recovery_analysis.py via `reliable` flag. |
| 2 | PersonBaseline deserialization | Add `PersonBaseline.load_from_summary(df)` class method to `scripts/baseline/baselines.py`. Reconstructs `RecoveryCurve` objects from recovery_baselines.csv columns. Pipeline 3 never re-fits — loads from Pipeline 2 output. |
| 3 | Activity state classification | Merge into `sessions/utils.py` as `classify_window_state(classified_df, start_utc, end_utc)`. Pre-session window stays 30 min. `session_effect.py` keeps its own date parsing, calls the shared function at the end. |
| 4 | `compute_signal_baseline()` | Keep inline in session_arc_analysis.py. Add TODO comment pointing to parallel logic in `baseline/circadian_baseline.py` for future consolidation. |
| 5 | Timezone fix | Fix during migration using `zoneinfo.ZoneInfo("Europe/Brussels")` in both session_effect.py and session_arc_analysis.py. Add `local_to_utc(dt_local)` helper to `sessions/utils.py`. |

**Migration order (one step at a time, verify before next):**

1. **`scripts/sessions/__init__.py`** — create empty, marks package
2. **`scripts/sessions/utils.py`** — create new; contains `classify_window_state()` (moved from session_arc_analysis.py) + `local_to_utc(dt_local)` timezone helper using `ZoneInfo("Europe/Brussels")`
3. **`scripts/baseline/baselines.py`** — add `PersonBaseline.load_from_summary(df)` class method only; no other changes to Pipeline 2 files
4. **`scripts/sessions/session_effect.py`** — move from scripts/analysis/; update import to `from baseline.baselines import ...`; replace hardcoded `-1h` offset with `local_to_utc()` from utils; add `r2_expected` to output rows; replace `_classify_pre_session_state()` with call to `classify_window_state()` from utils
5. **`scripts/sessions/session_features.py`** — move from scripts/analysis/; update path constants only (no code imports from other pipelines)
6. **`scripts/sessions/session_arc_analysis.py`** — move from scripts/analysis/; update imports to `from baseline.circadian_baseline import ...` and `from sessions.utils import classify_window_state`; replace hardcoded `-1h` offsets with `local_to_utc()` from utils; remove local `classify_window_state()` (now in utils); add TODO comment on `compute_signal_baseline()`
7. **`scripts/sessions/circadian_significance.py`** — move from scripts/analysis/; update path constants only (no cross-pipeline imports)
8. **`scripts/sessions/recovery_analysis.py`** — convert from notebooks/recovery_analysis.ipynb; extract quality filter logic, recovery_features.csv export, per-participant recovery window plots, summary stats; drop notebook-only cells
9. **`scripts/sessions/pipeline.py`** — create new entry point; loads classified_minutes.csv (Pipeline 1 output) + recovery_baselines.csv (Pipeline 2 output) via `PersonBaseline.load_from_summary()`; runs all five stages in order
10. **Delete** `scripts/analysis/session_effect.py`, `session_features.py`, `session_arc_analysis.py`, `circadian_significance.py`, `pipeline.py` after verification passes

**Verification (completed 2026-05-31 on peer):**
```bash
uv run python -m py_compile scripts/sessions/pipeline.py
uv run python scripts/sessions/pipeline.py --help
uv run python scripts/sessions/pipeline.py peer --force
```

**DST validation result:** Compared `pre_state` classification using old hardcoded `-1h` offset
vs new `ZoneInfo("Europe/Brussels")` on peer's 18 post-DST sessions (≥ 2026-03-29).
**5 of 18 sessions received a different pre_state** — the old pipeline was looking at the
wrong 30-minute window for all CEST sessions, causing the wrong baseline recovery curve
to be selected. The fix is validated and materially affects results.

---

### Master Pipeline — scripts/main.py
**Purpose:** Runs all three sub-pipelines in order for all participants, with per-stage skip logic.

**CLI:** `uv run python scripts/main.py [--all | --participants p1 p2] [--skip-extraction] [--skip-baseline] [--skip-sessions] [--force]`

**Flow:**
```
for each participant:
  1. extraction/pipeline.py  (skip if outputs fresh)
  2. baseline/pipeline.py    (skip if outputs fresh)
  3. sessions/pipeline.py    (skip if outputs fresh)
```

**Adapts from existing:** `scripts/pipeline/main.py` (current stub) — rewrite to match real data paths; retire `pipeline_config.py` bronze/silver/gold paths in favour of actual paths from garmin/huawei pipelines.

---

## Import Chain (critical — must update after moves)

`scripts/analysis/pipeline.py` currently imports:
```python
from fit_extractor import ...
from activity_classifier import ActivityClassifier
from baselines import PersonBaseline
from session_effect import ...
from session_features import ...
```
After moves these become cross-package imports, e.g.:
```python
from extraction.activity_classifier import ActivityClassifier
from baseline.baselines import PersonBaseline
```
Each sub-folder needs `__init__.py`. The entry-point scripts will add their parent folder to `sys.path` so imports resolve cleanly.

`session_arc_analysis.py` reads data files only (no cross-script code imports).
`bayesian_recommender.py` reads `feature_matrix.csv` from disk — file path only, no code imports.

---

## Deduplication Focus (per pipeline, before finalising)

- **garmin_pipeline.py vs huawei_pipeline.py**: `crossref_sessions()` is nearly identical — candidate for a shared `crossref_sessions(minute_df, checkins_df, window_min)` helper in `extraction/utils.py`
- **baselines.py vs circadian_baseline.py**: both compute non-session-day exclusion logic — merge into one shared filter
- **session_arc_analysis.py vs session_effect.py**: both read session traces and classify windows — check for overlapping logic before migrating
- **recovery_analysis.ipynb vs session_effect.py/baselines.py**: the notebook does recovery analysis — audit overlap with existing scripts before converting to `recovery_analysis.py`

---

## Notebooks to Create

| Script | Target notebook | Existing notebook to extend? |
|--------|----------------|------------------------------|
| `bayesian_recommender.py` | `notebooks/bayesian_recommender.ipynb` | Extend `bayesian_recommender_viz.ipynb` or new |
| `circadian_ml.py` | `notebooks/circadian_ml_analysis.ipynb` | Extend existing `circadian_ml_analysis.ipynb` |
| `music_classification.py` | `notebooks/music_classification.ipynb` | Extend `ml_music_classification.ipynb` |
| `music_classifier.py` | `notebooks/music_classifier.ipynb` | New |

Scripts are removed from `scripts/analysis/` once notebook equivalents are confirmed working.

---

## Execution Order (one pipeline at a time)

1. **Pipeline 1 — extraction/** (first — all downstream pipelines depend on its outputs)
2. **Pipeline 2 — baseline/** (depends on extraction outputs)
3. **Pipeline 3 — sessions/** (depends on baseline outputs)
4. **Master pipeline** — wire all three + skip logic
5. **Notebooks** — one per script, after pipelines are stable

Each step: ask clarifying questions → propose specific file changes → get permission → execute.

---

## Verification (after each pipeline)

```bash
# Syntax check
uv run python -m py_compile scripts/extraction/pipeline.py

# Dry run (imports + --help)
uv run python scripts/extraction/pipeline.py --help

# Full run on one participant
uv run python scripts/extraction/pipeline.py bosbes
```

---

## How to Resume (after context clear)

1. Read this file — the STATUS TRACKER at the top shows exactly where we left off.
2. Read only the files relevant to the current pipeline (listed per pipeline above).
3. The Deduplication Focus section lists known candidates to investigate before each migration.
4. Each pipeline is self-contained — no need to re-read earlier pipelines to work on the next one.
