#!/usr/bin/env bash
# run_pipeline.sh — Full analysis pipeline for Project R.E.M.
#
# Prerequisites:
#   1. Garmin GDPR exports unzipped to data/wearables/{p}/raw/export/
#   2. Exportify CSVs placed in data/playlists/{p}/
#   3. Check-in Google Form export at data/checkins/Check-in_formulier_REM.csv
#
# Run from project root:  bash run_pipeline.sh [participant]
# Omit participant to run all.

set -e

PARTICIPANTS="${1:-bosbes kokosnoot limoen peer}"

echo "=== Step 1: Wearables pipeline ==="
for p in $PARTICIPANTS; do
    echo "  Processing $p..."
    uv run python scripts/wearables/garmin_pipeline.py "$p" || \
    uv run python scripts/wearables/huawei_pipeline.py "$p" || \
    echo "  WARNING: No wearables pipeline succeeded for $p"
done

echo "=== Step 2: Playlist generation ==="
for p in $PARTICIPANTS; do
    echo "  Generating playlists for $p..."
    uv run python scripts/playlists/spotify_cli.py all "$p" || \
    echo "  WARNING: Playlist generation failed for $p"
done

echo "=== Step 3: Session features ==="
uv run python scripts/analysis/session_features.py

echo "=== Step 4: Circadian baselines + feature matrix ==="
uv run python scripts/analysis/circadian_baseline.py

echo "=== Step 5: Circadian ML models ==="
uv run python scripts/analysis/circadian_ml.py

echo "=== Step 6: Bayesian recommender ==="
uv run python scripts/analysis/bayesian_recommender.py

echo "=== Step 7: Significance tests ==="
uv run python scripts/analysis/circadian_significance.py

echo "=== Done. Start app with: uv run shiny run app.py ==="
