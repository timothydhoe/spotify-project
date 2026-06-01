# Wearable Biometrics Pipeline — Journey & Next Steps

Prepared for R.E.M. study team presentation.

---

## What we built

A pipeline that takes a raw smartwatch data export, cross-references it with the check-in form, and produces minute-level biometric traces around each listening session. One command per participant:

```bash
python3 scripts/wearables/garmin_pipeline.py kokosnoot
python3 scripts/wearables/huawei_pipeline.py limoen
```

Output: per-session stress/HR curves from 60 minutes before to 60 minutes after the playlist, plus daily summaries, PDF reports, and analysis notebooks.

---

## Hurdles & how we solved them

### 1. Garmin data is not what it looks like

**Problem:** The Garmin GDPR export gives you JSON files with daily aggregates — one number per day for stress, HR, steps. That's useless for 30-minute listening sessions. We need minute-level resolution.

**Solution:** The real data is buried in `.fit` binary files inside nested ZIP archives. We used the `fitparse` library to decode Garmin's proprietary binary format and discovered that `stress_level` messages contain per-minute stress readings, and `monitoring` messages contain per-minute HR. We also found that Body Battery is stored in an undocumented field (`unknown_3`) within the stress messages — confirmed by spot-checking against the Garmin Connect app.

### 2. Timestamps are a mess

**Problem:** Garmin FIT files use UTC. The check-in form uses local time (CET, UTC+1). Mixing these up shifts every session window by an hour — enough to miss the playlist entirely.

**Solution:** The pipeline converts all check-in times from local to UTC before windowing. The offset is configurable for participants in different timezones or during daylight saving time.

### 3. The watch fragments data into hundreds of files

**Problem:** The Garmin Vivoactive 5 writes a new FIT file every few hours. Kokosnoot's export had 290 files, bosbes had 28,894 (9 years of Garmin use).

**Solution:** The pipeline reassembles the full timeline by parsing all files, deduplicating by timestamp, and sorting. For large exports, it auto-detects the relevant date range from the check-in CSV and skips files outside that window. This reduced bosbes's processing time from 30+ minutes to ~2 minutes.

### 4. Garmin and Huawei export completely differently

**Problem:** Huawei Health exports are pure JSON (no binary FIT files), with different field names, millisecond epoch timestamps, and a different folder structure. A Garmin pipeline can't read Huawei data.

**Solution:** We built a separate `huawei_pipeline.py` with the same interface and identical output schema (same 29 columns in `session_biometrics.csv`). This means all downstream analysis — notebooks, cross-participant comparisons, ML models — work without changes regardless of which watch the participant wears.

### 5. Huawei GT3 has no stress data in the export

**Problem:** The Huawei GDPR export for the GT3 contains zero stress records (type=11). The watch does measure stress in the app, but Huawei doesn't include continuous stress in the data export — unlike Garmin which exports everything.

**Solution:** We adapted the pipeline to work with HR-only data. The session matching criterion was changed from "has stress data" to "has stress OR HR data." Limoen's analysis uses heart rate as the primary biometric signal instead of stress.

### 6. Limoen's export was created too early

**Problem:** Limoen exported their Huawei data on February 12, but has 6 check-in sessions spanning February 4 through March 23. Only 1 session (Feb 4) falls within the export window.

**Solution:** Identified by comparing the export date range (Jan 5 – Feb 11) against the check-in timestamps. The Feb 4 Energy session does have 31 HR readings and shows a +5 bpm deviation from limoen's circadian baseline at that hour. But 1 session is not enough for meaningful analysis.

### 7. "0 sessions matched" when sessions clearly existed

**Problem:** The cross-participant notebook showed 0 sessions for limoen even after the pipeline ran successfully, because it filtered on `stress_points > 0`. Limoen has zero stress points but does have HR data.

**Solution:** Changed the filter everywhere (pipeline + notebooks) to `stress_points > 0 OR hr_points > 0`.

---

## Current state per participant

| Participant | Watch | Sessions with data | Stress | HR | Body Battery | Status |
|---|---|---|---|---|---|---|
| 🥥 kokosnoot | Garmin Vivoactive 5 | 9 / 14 | ✓ minute-level | ✓ minute-level | ✓ (undocumented field) | Complete — 5 sessions outside export range |
| 🫐 bosbes | Garmin Venu 2S | 5 / 5 | ✓ minute-level | ✓ minute-level | ✓ | Complete |
| 🍋 limoen | Huawei GT3 | 1 / 6 | ✗ not in export | ✓ minute-level | ✗ not available | Needs re-export |

---

## Next steps for limoen

### Immediate (5 minutes)

1. Limoen opens Huawei Health app → Me → Privacy Center → Request Your Data
2. Wait for the export email (usually a few hours)
3. Download and unzip into `data/wearables/limoen/raw/export/`
4. Run: `python3 scripts/wearables/huawei_pipeline.py limoen`

**Expected result:** 5 additional sessions with HR data (Feb 12, Feb 25, Mar 8, Mar 14, Mar 23). This brings limoen from unusable to a 6-session participant with full HR traces.

### What limoen's analysis will look like

Without stress data, limoen's contribution is **HR-only**. This is still meaningful:

- HR responds to emotional arousal during seated listening (not physical activity)
- The Feb 4 session already shows +5 bpm above circadian baseline during Energy playlist
- With 6 sessions, we can compare Energy vs Calm HR response patterns
- The cross-participant notebooks and ML models handle missing stress/BB gracefully (NaN columns)

### What to note in the paper

The Huawei GT3 does measure stress in the app, but the GDPR export does not include continuous stress data. This is a documented limitation of Huawei's data portability — in contrast, Garmin exports all sensor data including undocumented fields. This difference means cross-device comparisons are limited to HR as the common metric.

---

## What we have for analysis

### Data volumes

- **Minute-level readings:** ~72k stress + ~43k HR across kokosnoot and bosbes
- **Daily summaries:** 38 days (kokosnoot) + 70 days (bosbes) + 38 days (limoen)
- **Session traces:** 14 matched sessions with ±60 min biometric windows

### Key findings so far (kokosnoot + bosbes)

- Energy playlists elevate stress ~12 points above time-of-day baseline
- Calm playlists reduce stress ~6 points below baseline
- Stress delta and mood delta are inversely correlated (r = −0.52)
- Calm playlists show larger mood improvements (+1.8) despite smaller physiological shifts
- Baseline state matters: high pre-session stress → larger calming effect regardless of playlist

### Deliverables in the repo

```
scripts/wearables/
├── garmin_pipeline.py          # Garmin (Vivoactive, Venu, etc.)
├── huawei_pipeline.py          # Huawei (GT3, etc.)
└── README.md                   # Setup & usage guide

notebooks/
├── session_traces.ipynb        # Per-participant trace visualisation (14 charts)
├── cross_participant_analysis.ipynb   # Pooled analysis with emoji labels
└── ml_analysis.ipynb           # Playlist classifier, mood predictor, CNN

docs/
└── WEARABLE_DATA.md            # Full data documentation (what/how/why)
```
