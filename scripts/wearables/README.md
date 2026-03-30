# Wearables Pipeline

Extracts biometric data from Garmin smartwatch exports and cross-references it with R.E.M. study listening sessions.

## Setup

```bash
uv add fitparse matplotlib
```

## Usage

```bash
python3 scripts/wearables/garmin_pipeline.py kokosnoot
```

That's it. The script finds all paths automatically from the project structure.

## Step by step

### 1. Participant exports their data

Go to [Garmin Connect](https://connect.garmin.com) → Account → Data Management → Export Your Data. This takes a few hours. Garmin emails a download link when ready.

### 2. Place the export

```bash
mkdir -p data/wearables/kokosnoot/raw
unzip ~/Downloads/garmin_export.zip -d data/wearables/kokosnoot/raw/export
```

Verify the structure looks like this:

```
data/wearables/kokosnoot/raw/export/
├── DI_CONNECT/
│   ├── DI-Connect-Aggregator/
│   ├── DI-Connect-Uploaded-Files/
│   └── ...
└── ...
```

If the unzip created an extra wrapper folder, pass it directly:

```bash
python3 scripts/wearables/garmin_pipeline.py kokosnoot \
    --export data/wearables/kokosnoot/raw/export/ExtraFolder
```

### 3. Make sure the check-in CSV is in place

```
data/checkins/checkin_formulier_rem.csv
```

The pipeline auto-finds the first `.csv` in that folder.

### 4. Run

```bash
python3 scripts/wearables/garmin_pipeline.py kokosnoot
```

### 5. Check outputs

Everything lands in `data/wearables/kokosnoot/processed/`:

| File | What it is |
|------|------------|
| `garmin_daily.csv` | One row per day: *steps, HR, stress, Body Battery, calories* |
| `garmin_minute_stress.csv` | Per-minute stress + Body Battery |
| `garmin_minute_hr.csv` | Per-minute heart rate |
| `session_biometrics.csv` | One row per listening session: *pre/during/post biometrics + mood* |
| `session_traces/` | Per-session minute-level curves (60 min before → 60 min after) |
| `session_traces_all.csv` | All traces in one file |
| `garmin_vitals_report.pdf` | Visual report (3 pages) |

## Running for a different participant

Same steps, different name:

```bash
mkdir -p data/wearables/kiwi/raw
unzip kiwi_garmin.zip -d data/wearables/kiwi/raw/export
python3 scripts/wearables/garmin_pipeline.py kiwi
```

## Options

```
python3 scripts/wearables/garmin_pipeline.py <codename> [options]

  --export PATH    Override Garmin export location
  --checkin PATH   Override check-in CSV location
  --out PATH       Override output directory
  --root PATH      Override project root (auto-detected)
```

## Important notes

- **Timing:** participants should export *after* their last listening session, otherwise the final sessions won't have matching data.
- **Timezone:** FIT files use UTC. Check-in times are assumed CET (UTC+1). If a participant is in a different timezone, the offset needs adjusting in the code.
- **Privacy:** the `raw/` folder contains PII (email, profile). It's gitignored. Only `processed/` gets committed.
- **matplotlib is optional.** If not installed, everything runs fine. You just don't get the PDF report.

## Known data issues

### Check-in date swapped on mobile (day/month reversed)

**Issue:** When participants fill in the Google Form on a mobile device, the date picker can present fields in MM-DD-YYYY order instead of DD-MM-YYYY. The result is a date where day and month are swapped — for example, March 10 gets entered as `3-10-2026`, which pandas (with `dayfirst=True`) interprets as October 3, 2026.

**Detection:** The `Tijdstempel` column is the server-side form submission timestamp and is always correct. A check-in date that falls *after* the submission timestamp is physically impossible, so it reliably flags a swapped date.

**Fix:** `checkin_utils.py` (in this folder) provides a `fix_checkin_dates()` function used by all three pipeline scripts in place of a bare `pd.to_datetime()` call. When a suspicious date is detected, it swaps day and month in the raw string and re-parses. If the result is on or before the submission timestamp (plus one day of tolerance for midnight edge cases), the correction is accepted. A `UserWarning` is always emitted when a correction is applied, so it appears in pipeline output:

```
UserWarning: [check-in date] Submitted 2026-03-10: '3-10-2026' looks day/month-swapped (mobile bug) — auto-corrected to 2026-03-10
```

If the swap still does not yield a plausible date, the original value is kept and a warning is emitted asking for manual inspection.

---

## Troubleshooting

**"Export not found"** → the unzipped Garmin data isn't at `data/wearables/<name>/raw/export/`. Check the path.

**"No UDS data found"** → the export doesn't contain daily summary JSONs. Make sure `DI_CONNECT/DI-Connect-Aggregator/UDSFile_*.json` exists inside the export folder.

**Sessions show 0 stress/HR points** → those sessions fall outside the Garmin export date range. Re-export from Garmin.

**"fitparse not installed"** → run `uv add fitparse` or `pip install fitparse`. Without it, minute-level data can't be extracted.
