# Workflow Suggestions for Project R.E.M.

Suggestions for Claude skills, subagents, hooks, and automations that fit the project's current shape and deadlines.

---

## 1. Hooks

### 1a. Auto-syntax-check after Python edits
**Type:** `PostToolUse` on `Edit` / `Write` for `*.py` files
**What it does:** Immediately runs `python -m py_compile` on any Python file Claude modifies.
**Why useful:** CLAUDE.md explicitly names `py_compile` as the only testing mechanism. Right now this is a manual step that's easy to forget. Catching a syntax error the moment the file is saved costs nothing; catching it after a pipeline run on a participant wastes time.

### 1b. PII path guard
**Type:** `PreToolUse` on `Write` / `Edit` / `Bash`
**What it does:** Checks if the target path contains `data/wearables/*/raw/` and blocks the tool call with a warning if so.
**Why useful:** Raw wearable data contains participant PII. CLAUDE.md already flags this as critical. A hook makes the guard automatic rather than relying on memory.

### 1c. Clear notebook outputs before commit
**Type:** `PreToolUse` on `Bash` when the command contains `git commit`
**What it does:** Runs `jupyter nbconvert --clear-output --inplace notebooks/*.ipynb` before any commit.
**Why useful:** Notebook output cells can contain participant-identifiable traces (plots, printed DataFrames). Clearing outputs before committing is standard practice in research repos but is currently not enforced.

---

## 2. Skills (slash commands)

### 2a. `/participant-status`
**What it does:** Scans `data/playlists/` and `data/wearables/*/processed/` for all known codenames and prints a per-participant table: playlists generated (yes/no), wearable data processed (yes/no), most recent check-in date (from `data/checkins/`), and session count.
**Why useful:** With ~8 participants across two device types, it's easy to lose track of who has complete data. A one-command status view replaces manually checking each folder.

### 2b. `/run-participant [codename]`
**What it does:** Runs the full playlist pipeline (`prepare → generate → analyse`) for a given codename, surfaces any validation failures, and prints the playlist stats summary.
**Why useful:** The three-step pipeline is already well-defined in `spotify_cli.py`; this skill wraps it with output formatting and error surfacing so you don't have to remember the exact command syntax.

### 2c. `/new-participant [codename] [device: garmin|huawei]`
**What it does:** Creates the expected directory structure (`data/playlists/[codename]/`, `data/wearables/[codename]/raw/`, `data/wearables/[codename]/processed/`), then prints the onboarding checklist: Exportify export instructions, correct GDPR export path, pipeline command to run after export arrives.
**Why useful:** Adding a new participant currently requires knowing the exact folder conventions and pipeline commands. A skill makes onboarding repeatable and less error-prone.

### 2d. `/notebook-summary [notebook_name]`
**What it does:** Executes a named notebook with `nbconvert --execute` and returns a natural-language summary of key outputs (printed stats, plot descriptions, validation results).
**Why useful:** The ML and cross-participant notebooks are long-running and output-heavy. A summary agent saves time when you just want to know "did anything change in the aggregate analysis after adding a new participant?"

---

## 3. Scheduled / Remote Agents

### 3a. Daily check-in reminder check
**Type:** Scheduled remote agent (cron)
**Schedule:** Daily (e.g., 09:00)
**What it does:** Reads `data/checkins/Check-in_formulier_REM.csv`, identifies participants who haven't checked in for 3+ days, and outputs a summary. This is the automated equivalent of `who_needs_reminding.ipynb`, which is currently a manual Google Colab tool.
**Why useful:** The notebook requires manual execution in Colab. A scheduled local agent runs automatically and could log results or send a summary via any notification channel you configure.

### 3b. Weekly data-completeness report
**Type:** Scheduled remote agent
**Schedule:** Weekly (e.g., Monday 08:00)
**What it does:** Runs the same logic as `/participant-status` but formats it as a Markdown report saved to `reports/weekly_status_[date].md`, covering playlist generation status, wearable data freshness, session counts, and any participants with missing data.
**Why useful:** Keeps a running paper trail of the study's data collection progress — useful for supervisor check-ins and the final writeup.

---

## 4. Subagent Workflows

### 4a. Wearable data intake workflow
**Trigger:** When new raw wearable data arrives for a participant
**Steps:**
1. Detect device type from export folder structure (Garmin vs Huawei)
2. Run the correct pipeline (`garmin_pipeline.py` or `huawei_pipeline.py`)
3. Validate that all 6 expected output CSVs exist in `processed/`
4. Run the cross-participant analysis notebook to update aggregate stats
5. Output a brief summary of session count and stress/HR data range

**Why useful:** Right now each step requires knowing the correct script and flags. A workflow agent makes the intake path deterministic and catches missing outputs early.

### 4b. ML notebook → production script exporter
**Trigger:** Manual, when a model in a notebook has stabilized
**Steps:**
1. Read the target notebook and identify the trained model, feature columns, and evaluation metrics
2. Extract the training + inference code into a standalone `scripts/ml/[model_name].py`
3. Save the feature list and evaluation summary to `models/[model_name]_config.json`
4. Run `py_compile` on the generated script

**Why useful:** The ML work is currently notebook-only. With the June 20 deadline approaching, moving proven models out of notebooks and into scripts will be necessary for the Streamlit app. This workflow makes that extraction systematic rather than ad-hoc.

### 4c. Streamlit app scaffolding agent
**Trigger:** Manual, when ready to start the app
**Steps:**
1. Read all `playlists_generated/` directories to understand available data shape
2. Read `session_biometrics.csv` files to understand biometric output schema
3. Scaffold a `streamlit_app/` directory with: a main page, per-participant summary page, and a data-loading module that wraps the existing processed CSVs
4. Wire in the "Spotify Wrapped" visual concept from `docs/`

**Why useful:** The Streamlit app is the final deliverable (June 20, 2026) and hasn't started. A scaffolding agent that reads the actual data schemas will produce something immediately runnable rather than a generic template.

---

## 5. Priority Order

Given the June 20 deadline (~12 weeks away), here's a suggested priority:

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| High | Hook 1a (auto py_compile) | Low | Prevents silent regressions |
| High | Hook 1b (PII guard) | Low | Prevents irreversible mistake |
| High | Skill: `/participant-status` | Low | Daily utility |
| Medium | Scheduled: daily check-in check | Medium | Replaces manual Colab notebook |
| Medium | Workflow: wearable intake | Medium | Reduces per-participant friction |
| Medium | ML → script exporter | Medium | Critical path to Streamlit app |
| Medium | Hook 1c (clear notebook outputs) | Low | Research hygiene |
| Lower | Skill: `/notebook-summary` | High | Nice-to-have |
| Lower | Streamlit scaffolding agent | High | Start when ML models stabilize |
