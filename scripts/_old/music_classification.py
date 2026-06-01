"""
music_classification.py — Arousal-score based music classification pipeline.

Classifies songs in a participant's Spotify library into CALM, ENERGY, or OTHER
based on weighted audio features. Uses rule-based thresholds (not ML model).

Outputs:
    data/playlists/{codename}/playlist_ml/classified_songs.csv
    data/playlists/{codename}/playlist_ml/{codename}_classification_report.txt
    models/scaler.pkl (MinMaxScaler fitted on this data)
    models/config.json (pipeline config + class distribution)

Usage:
    python scripts/analysis/music_classification.py peer
    python scripts/analysis/music_classification.py --all
    python scripts/analysis/music_classification.py peer --calm-threshold 0.45 --energy-threshold 0.55

See notebooks/ml_music_classification.ipynb for exploratory analysis & validation.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

# ══════════════════════════════════════════════════════════════════════════════
#  PROJECT PATHS
# ══════════════════════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLAYLISTS_DIR = PROJECT_ROOT / "data" / "playlists"
MODELS_DIR = PROJECT_ROOT / "models"

# ══════════════════════════════════════════════════════════════════════════════
#  DEFAULTS
# ══════════════════════════════════════════════════════════════════════════════

SCORING_FEATURES = [
    "tempo", "energy", "loudness", "valence", "danceability",
    "acousticness", "instrumentalness", "speechiness",
]

AROUSAL_WEIGHTS = {
    "energy": 0.35,
    "tempo": 0.30,
    "loudness": 0.20,
    "acousticness": -0.10,
    "danceability": 0.05,
}

DEFAULT_CALM_THRESHOLD = 0.35
DEFAULT_ENERGY_THRESHOLD = 0.65
DEFAULT_VALENCE_FLOOR = 0.25
DEFAULT_SPEECHINESS_MAX = 0.66
DEFAULT_LIVENESS_MAX = 0.80


def load_and_validate(codename: str) -> pd.DataFrame:
    """Load combined.csv for a participant and validate data quality."""
    csv_path = PLAYLISTS_DIR / codename / "playlists_generated" / "combined.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"File not found: {csv_path}")

    df = pd.read_csv(csv_path)
    df["participant"] = codename

    # Check required features
    missing = [f for f in SCORING_FEATURES if f not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Remove duplicates by uri if available, else by name+artists
    if "uri" in df.columns:
        n_dupes = df.duplicated(subset=["uri"], keep="first").sum()
        df = df.drop_duplicates(subset=["uri"], keep="first").copy()
    else:
        n_dupes = df.duplicated(subset=["name", "artists"], keep="first").sum()
        df = df.drop_duplicates(subset=["name", "artists"], keep="first").copy()

    # Handle missing values
    n_before = len(df)
    df = df.dropna(subset=SCORING_FEATURES + ["liveness"])
    n_dropped = n_before - len(df)

    print(f"Loaded {csv_path.name}: {len(df)} songs (removed {n_dupes} dupes, {n_dropped} NaN rows)")
    return df


def prefilter(df: pd.DataFrame, speechiness_max: float, liveness_max: float) -> pd.DataFrame:
    """Remove live recordings and speech-only tracks."""
    n_before = len(df)

    # Remove speech-only tracks
    speech_mask = df["speechiness"] > speechiness_max
    n_speech = speech_mask.sum()

    # Remove live recordings
    live_mask = df["liveness"] > liveness_max
    n_live = live_mask.sum()

    # Apply both
    df = df[~speech_mask & ~live_mask].copy()
    n_removed = n_before - len(df)

    if n_removed > 0:
        print(f"  Pre-filtered: removed {n_removed} tracks ({n_speech} speech, {n_live} live)")

    return df


def classify_pipeline(
    df: pd.DataFrame,
    calm_threshold: float = DEFAULT_CALM_THRESHOLD,
    energy_threshold: float = DEFAULT_ENERGY_THRESHOLD,
    valence_floor: float = DEFAULT_VALENCE_FLOOR,
) -> tuple[pd.DataFrame, MinMaxScaler]:
    """
    Run the classification pipeline: normalize → arousal score → classify.

    Returns: (df_with_classifications, fitted_scaler)
    """
    # Normalize features to [0, 1]
    scaler = MinMaxScaler()
    X_scaled = scaler.fit_transform(df[SCORING_FEATURES])
    df_scaled = pd.DataFrame(X_scaled, columns=SCORING_FEATURES, index=df.index)

    # Compute arousal score
    df["arousal_score"] = sum(
        weight * df_scaled[feature]
        for feature, weight in AROUSAL_WEIGHTS.items()
    )

    # Classify
    def classify_track(arousal: float, valence_norm: float) -> str:
        if arousal < calm_threshold and valence_norm >= valence_floor:
            return "calm"
        elif arousal > energy_threshold:
            return "energy"
        else:
            return "other"

    df["class"] = [
        classify_track(arousal, valence)
        for arousal, valence in zip(df["arousal_score"], df_scaled["valence"])
    ]

    return df, scaler


def save_outputs(
    df: pd.DataFrame,
    codename: str,
    scaler: MinMaxScaler,
    calm_threshold: float,
    energy_threshold: float,
    valence_floor: float,
    df_raw: pd.DataFrame,
) -> None:
    """Save CSV output, report, scaler, and config."""
    output_dir = PLAYLISTS_DIR / codename / "playlist_ml"
    output_dir.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. CSV with classifications
    csv_path = output_dir / "classified_songs.csv"
    df.to_csv(csv_path, index=False)
    print(f"✓ Saved {csv_path.name}")

    # 2. Text report
    class_counts = df["class"].value_counts()
    report_lines = [
        f"Music Classification Report — {codename}",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"{'='*60}",
        f"",
        f"SUMMARY",
        f"  Songs loaded:      {len(df_raw)}",
        f"  Songs classified:  {len(df)}",
        f"",
        f"CLASS DISTRIBUTION",
    ]

    for cls in ["calm", "energy", "other"]:
        n = class_counts.get(cls, 0)
        pct = n / len(df) * 100
        report_lines.append(f"  {cls.upper():>6}: {n:>5} songs ({pct:.1f}%)")

    # Mean features per class
    report_lines += [
        f"",
        f"MEAN FEATURES PER CLASS",
        f"",
    ]
    class_means = df.groupby("class")[SCORING_FEATURES + ["arousal_score"]].mean().round(3)
    for line in class_means.to_string().split("\n"):
        report_lines.append(f"  {line}")

    report_lines += [
        f"",
        f"THRESHOLDS",
        f"  CALM:   arousal < {calm_threshold} AND valence >= {valence_floor}",
        f"  ENERGY: arousal > {energy_threshold}",
        f"  OTHER:  everything else",
    ]

    report_path = output_dir / f"{codename}_classification_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print(f"✓ Saved {report_path.name}")

    # 3. Scaler
    scaler_path = MODELS_DIR / "scaler.pkl"
    joblib.dump(scaler, scaler_path)
    print(f"✓ Saved scaler.pkl")

    # 4. Config
    config = {
        "created": datetime.now().isoformat(),
        "participant": codename,
        "n_songs_total": len(df_raw),
        "n_songs_classified": len(df),
        "scoring_features": SCORING_FEATURES,
        "arousal_weights": AROUSAL_WEIGHTS,
        "thresholds": {
            "calm": calm_threshold,
            "energy": energy_threshold,
            "valence_floor": valence_floor,
        },
        "class_distribution": {
            cls: int(class_counts.get(cls, 0)) for cls in ["calm", "energy", "other"]
        },
    }
    config_path = MODELS_DIR / "config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"✓ Saved config.json")


def main():
    parser = argparse.ArgumentParser(
        description="Arousal-score music classification pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/analysis/music_classification.py peer
  python scripts/analysis/music_classification.py --all
  python scripts/analysis/music_classification.py peer --calm-threshold 0.45 --energy-threshold 0.55
        """,
    )

    parser.add_argument(
        "participant",
        nargs="?",
        default=None,
        help="Participant codename, or omit to use --all",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all participants in data/playlists/",
    )
    parser.add_argument(
        "--calm-threshold",
        type=float,
        default=DEFAULT_CALM_THRESHOLD,
        help=f"Arousal score threshold for CALM class (default: {DEFAULT_CALM_THRESHOLD})",
    )
    parser.add_argument(
        "--energy-threshold",
        type=float,
        default=DEFAULT_ENERGY_THRESHOLD,
        help=f"Arousal score threshold for ENERGY class (default: {DEFAULT_ENERGY_THRESHOLD})",
    )
    parser.add_argument(
        "--valence-floor",
        type=float,
        default=DEFAULT_VALENCE_FLOOR,
        help=f"Minimum valence for CALM tracks (default: {DEFAULT_VALENCE_FLOOR})",
    )

    args = parser.parse_args()

    # Determine participants to process
    if args.all:
        participants = sorted([d.name for d in PLAYLISTS_DIR.glob("*/") if d.is_dir()])
    elif args.participant:
        participants = [args.participant]
    else:
        parser.print_help()
        return

    print(f"Processing {len(participants)} participant(s)\n")

    for codename in participants:
        try:
            print(f"{'─'*60}")
            print(f"  {codename}")
            print(f"{'─'*60}")

            # Load and preprocess
            df_raw = load_and_validate(codename)
            df = prefilter(
                df_raw,
                speechiness_max=DEFAULT_SPEECHINESS_MAX,
                liveness_max=DEFAULT_LIVENESS_MAX,
            )

            # Classify
            df, scaler = classify_pipeline(
                df,
                calm_threshold=args.calm_threshold,
                energy_threshold=args.energy_threshold,
                valence_floor=args.valence_floor,
            )

            # Save
            save_outputs(
                df,
                codename,
                scaler,
                args.calm_threshold,
                args.energy_threshold,
                args.valence_floor,
                df_raw,
            )

            print()

        except Exception as e:
            print(f"  ERROR: {e}")
            print()


if __name__ == "__main__":
    main()
