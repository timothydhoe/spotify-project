# Wearable Biometrics — Data Pipeline Documentation

## Context

This document describes how physiological data from participants' smartwatches is extracted, processed, and integrated into the R.E.M. study (Regulation of Emotion through Music). The goal is to cross-reference objective biometric signals (heart rate, stress, Body Battery) with the self-reported mood check-ins captured during playlist listening sessions.

Currently supported: **Garmin Vivoactive 5**. The architecture accommodates additional devices.

---

## Project Integration

### Where things live

```
spotify-project/
├── data/
│   ├── playlists/
│   │   └── [participant]/            # existing — Exportify CSVs + generated playlists
│   ├── checkins/                     # NEW — Google Forms check-in exports
│   │   └── checkin_formulier_rem.csv
│   └── wearables/                    # NEW — smartwatch data
│       └── [participant]/
│           ├── raw/                  # untouched GDPR export (gitignored)
│           │   └── garmin_export.zip
│           └── processed/            # pipeline outputs (committed)
│               ├── garmin_daily.csv
│               ├── garmin_minute_stress.csv
│               ├── garmin_minute_hr.csv
│               ├── session_biometrics.csv
│               ├── session_traces_all.csv
│               └── session_traces/
│                   └── trace_YYYY-MM-DD_playlist.csv
├── scripts/
│   ├── playlists/                    # existing — playlist generation
│   └── wearables/                    # NEW — biometric pipelines
│       └── garmin_pipeline.py
├── docs/
│   ├── info_deelnemers/              # existing
│   ├── research_muziek/              # existing
│   └── WEARABLE_DATA.md             # NEW — this document
├── reports/                          # NEW — generated PDF reports
│   └── [participant]/
│       └── garmin_vitals_report.pdf
└── ...
```

The pattern mirrors `data/playlists/[participant]/`: each participant gets a folder under `data/wearables/[participant]/` with `raw/` (gitignored) and `processed/` (committed) subdirectories.

### .gitignore additions

```gitignore
# Wearable raw exports — contain PII (email, profile, location)
data/wearables/*/raw/
```

The processed CSVs are safe to commit since the pipeline strips identifiers.

### pyproject.toml additions

```toml
[project.optional-dependencies]
wearables = ["fitparse", "matplotlib", "pandas", "numpy"]
```

Or with uv: `uv add fitparse matplotlib` (pandas/numpy are likely already present).

### Running the pipeline

```bash
# 1. Participant exports data from Garmin Connect and places the zip:
#    data/wearables/kokosnoot/raw/garmin_export.zip

# 2. Unzip into the raw folder
unzip data/wearables/kokosnoot/raw/garmin_export.zip \
      -d data/wearables/kokosnoot/raw/export

# 3. Run the pipeline
python scripts/wearables/garmin_pipeline.py \
    data/wearables/kokosnoot/raw/export \
    --out data/wearables/kokosnoot/processed \
    --checkin data/checkins/checkin_formulier_rem.csv \
    --code kokosnoot

# 4. PDF report lands in reports/
cp data/wearables/kokosnoot/processed/garmin_vitals_report.pdf \
   reports/kokosnoot/
```

---

## What We Export

Participants request a GDPR data export from Garmin Connect (Account → Data Management → Export Your Data). This produces a ZIP containing:

### Daily Aggregates (JSON)

Source: `DI_CONNECT/DI-Connect-Aggregator/UDSFile_*.json`

Each record = one calendar day. Key fields:

| Field | Type | Description |
|-------|------|-------------|
| `calendarDate` | date | The day |
| `totalSteps` / `dailyStepGoal` | int | Step count and adaptive goal |
| `totalDistanceMeters` | int | Total distance walked/run |
| `totalKilocalories` / `activeKilocalories` / `bmrKilocalories` | float | Energy expenditure breakdown |
| `restingHeartRate` / `minHeartRate` / `maxHeartRate` | int | Daily HR summary (bpm) |
| `moderateIntensityMinutes` / `vigorousIntensityMinutes` | int | WHO-style intensity tracking |
| `allDayStress.aggregatorList[type=TOTAL]` | nested | Avg/max stress, duration per tier (rest, low, medium, high) in seconds |
| `bodyBattery` | nested | Charged/drained values, highest/lowest with timestamps |
| `respiration` | nested | Avg/highest/lowest waking respiration rate (breaths/min) |

Resolution: **1 record per day**. Useful for trends and day-level context.

### Minute-Level Biometrics (FIT binary)

Source: `DI_CONNECT/DI-Connect-Uploaded-Files/UploadedFiles_*_Part*.zip`

Contains `.fit` files (Garmin's binary protocol). The watch fragments recording into multiple files per day — a typical export yields hundreds of files. We extract two message types:

**`stress_level`** — 1 reading per minute when worn:

| Field | Type | Description |
|-------|------|-------------|
| `stress_level_time` | datetime (UTC) | Minute timestamp |
| `stress_level_value` | int | Stress score 0–100. Values ≤ 0 = off-wrist or too active to measure |
| `unknown_3` | int | Body Battery level (0–100), reverse-engineered from undocumented schema |

**`monitoring`** — HR sampled roughly every 60s:

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | datetime (UTC) | Measurement time |
| `heart_rate` | int | Instantaneous HR (bpm). 0 = off-wrist |

Resolution: **~1 per minute**. This is the critical layer for aligning with listening sessions.

### Fitness Age (JSON)

Source: `DI_CONNECT/DI-Connect-Wellness/*_fitnessAgeData.json`

Periodic snapshots of Garmin's composite fitness age metric.

| Field | Type | Description |
|-------|------|-------------|
| `chronologicalAge` | int | Actual age |
| `currentBioAge` | float | Estimated biological age |
| `rhr` / `bmi` | int / float | Inputs to the calculation |

Resolution: ~1 per day, only on recalculation days.

### Other Files (low signal for R.E.M.)

| Source | Content | Why we skip it |
|--------|---------|---------------|
| `DI-Connect-Fitness/*_summarizedActivities.json` | Logged activities | Participants aren't logging activities during listening |
| `DI-Connect-Wellness/*_sleepData.json` | Sleep stages | Empty stubs in exports seen so far |
| `DI-Connect-User/` | Profile, settings, goals | Context only — contains PII |
| `DI-GOLF/`, `DI_BASEBALL_IMPACT/`, etc. | Sport modules | Not relevant |

---

## How We Extract

### Pipeline Stages

1. **Discover** — walks the export tree, catalogs all JSON and ZIP files
2. **Extract (JSON)** — parses daily UDS, fitness age, activities, hydration into DataFrames
3. **Extract (FIT)** — unzips `.fit` archives, parses `stress_level` and `monitoring` messages via `fitparse`, deduplicates across fragmented files
4. **Transform** — drops no-wear days, derives columns (distance km, goal met, 7-day rolling averages, intensity minutes)
5. **Cross-reference** — aligns check-in sessions with minute-level biometric windows. For each session: **60 min pre**, during, **60 min post** for stress, HR, Body Battery. Computes per-phase aggregates and deltas. Also exports full minute-by-minute traces per session
6. **Render** — multi-page PDF report + CSV exports

### Timezone Handling

FIT timestamps are **UTC**. Check-in times are **local (CET, UTC+1)**. The pipeline converts local → UTC before windowing. Configurable via `utc_offset_hours` (default: 1). Adjust for CEST (UTC+2) if sessions span a DST change.

### Output Files

| File | Description |
|------|-------------|
| `garmin_daily.csv` | One row per day — all daily metrics + derived columns |
| `garmin_minute_stress.csv` | Minute-level stress + Body Battery (UTC timestamps) |
| `garmin_minute_hr.csv` | Minute-level heart rate (UTC timestamps) |
| `session_biometrics.csv` | **The key join table.** One row per listening session with pre/during/post biometrics + mood scores |
| `session_traces/trace_YYYY-MM-DD_playlist.csv` | **Per-session minute-level traces.** Each row = 1 minute, columns: stress, HR, Body Battery, phase (pre/during/post), minutes_relative (-60 to +60). One file per session |
| `session_traces_all.csv` | All session traces concatenated into a single file for bulk analysis |
| `garmin_vitals_report.pdf` | Visual report: daily trends, deep dive, session cross-reference |

---

## Why These Metrics

| Metric | Relevance to R.E.M. |
|--------|---------------------|
| **Stress (minute)** | Derived from HRV — highest-resolution proxy for autonomic nervous system state. Directly measures physiological response to music. Calm playlists should shift stress down; Energy playlists may shift it up. |
| **Heart rate** | Complements stress. During seated listening, HR changes are primarily affective (not physical). |
| **Body Battery** | Composite of HRV, stress, activity, sleep. Session context: a participant at BB=30 responds differently than at BB=90. |
| **Daily aggregates** | Confound control. Did the participant walk 25k steps? Was overall stress elevated before the session? |
| **Pre/during/post** | 60-min buffer captures the full baseline before music starts and the persistence (or decay) of effect after it ends. The delta (post − pre) is the primary measure of physiological impact. The per-session traces enable visualizing the exact minute where biometrics shift. |

---

## Known Limitations

- **Sleep data** is empty in exports received so far. May require longer export windows.
- **Body Battery in FIT** lives in undocumented field `unknown_3`. Matches Garmin Connect app values on spot-check, but is reverse-engineered.
- **Export date coverage** — Garmin export may not cover all check-in sessions. Participants should export *after* their last session.
- **Off-wrist gaps** produce null readings. Pipeline handles gracefully, but sessions during gaps yield no data.
- **FIT fragmentation** — the watch writes new files every few hours. Pipeline reassembles by deduplicating across all files.
- **DST** — hardcoded UTC offset must be adjusted manually for DST transitions.
- **Device-specific** — this pipeline is Garmin Vivoactive 5. Other devices (Apple Watch, Fitbit) will need separate parsers under `scripts/wearables/`.
