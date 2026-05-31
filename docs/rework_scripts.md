# Pipeline Reorganisation Plan — Project R.E.M.

## STATUS TRACKER (update as work progresses)
- [ ] Pipeline 1 — extraction/
- [ ] Pipeline 2 — baseline/
- [ ] Pipeline 3 — sessions/
- [ ] Master pipeline (main.py)
- [ ] Notebooks (ML scripts converted)

**Currently working on:** Not started — awaiting first pipeline kick-off.

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
