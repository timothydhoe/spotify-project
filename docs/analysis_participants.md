# Analysis Participant Contributions

Which participants contribute data to each analysis pipeline.

## Participant Data Availability

| Participant | Wearable | Stress sensor | HR | HRV | Check-ins | Playlists |
|---|---|---|---|---|---|---|
| bosbes | Garmin ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| kokosnoot | Garmin ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| limoen | Huawei ✓ | ✗ | ✓ | ✗ | ✓ | ✓ |
| peer | — | ✗ | ✗ | ✗ | ✓ | ✓ |
| kiwi | — | ✗ | ✗ | ✗ | ✓ (sparse) | ✓ |
| watermeloen | — | ✗ | ✗ | ✗ | ✓ (sparse) | ✓ |

## Session Counts (approximate, 2026-05-24)

| Participant | Sessions | Biometric sessions |
|---|---|---|
| bosbes | 8 | 8 |
| kokosnoot | 16 | 16 |
| limoen | 6 | 6 (HR only, no stress) |
| peer | 10 | 0 |
| kiwi | ~4 | 0 |
| watermeloen | ~4 | 0 |
| **Total** | **~48** | **30** |

## Which Analysis Uses Which Participants

### circadian_baseline.py
- **All 6 participants** contribute to the feature matrix (N≈40 sessions with mood data)
- Participants without stress sensor (limoen): `baseline_deviation_entry` is NaN (~37.5% of rows)
- Participants without HR (peer, kiwi, watermeloen): HR features are NaN (~50% of rows)
- Features with >50% NaN per participant are excluded via `excluded_features.json`

### circadian_ml.py
- **Feature matrix** used: all participants with `mood_delta` present (~40 sessions)
- Imputation inside each LOO fold (median); missing values handled, not excluded
- Hyperparameters selected via inner 5-fold CV on full dataset before LOO evaluation

### circadian_significance.py
- **Per-participant only** — no pooling across participants
- N≥5 guard per test; participants with fewer sessions may have tests skipped
- bosbes and kokosnoot: most tests run; peer: stress/HR tests skipped (no biometrics)

### bayesian_recommender.py
- **All 6 participants** included in the hierarchical model
- `has_biometrics=True`: bosbes, kokosnoot, limoen (HR only)
- `has_biometrics=False`: peer, kiwi, watermeloen (mood check-ins only)
- Check-in-only participants contribute to group-level priors but not biometric coefficients
- Posterior plots generated for all 6; recommendations generated for all 6

### session_arc_analysis.py
- **Biometric participants only**: bosbes, kokosnoot, limoen
- limoen: stress arc unavailable; HR arc available

### music_classification.py / music_classifier.py
- **All 6 participants** — based on Spotify audio features, not biometrics
- Output: per-participant `classified_songs.csv`

## Notes on Pooling

All significance tests are **per-participant** (no pooling). This is statistically appropriate given participant heterogeneity but limits statistical power (N=6–16 per participant for biometric tests).

The Bayesian model uses **partial pooling** (hierarchical model) — participants share a group-level prior. This is the only analysis that formally borrows strength across participants.

For ML models, participants are pooled into a single feature matrix with participant one-hot dummy variables. This treats participant effects as fixed, not random.
