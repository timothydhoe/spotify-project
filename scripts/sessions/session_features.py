"""
session_features.py — Build the flat ML feature table from pipeline outputs.

Joins session_biometrics.csv + session_effects.csv per participant into one row
per session with all predictors and targets in a single flat table.

Outputs:
    data/analysis/{codename}/session_features.csv   — per-participant
    data/analysis/all_session_features.csv          — pooled cross-participant

Usage:
    python scripts/sessions/session_features.py
    python scripts/sessions/session_features.py --participants kokosnoot bosbes
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

_WEARABLES_DIR = Path(__file__).resolve().parents[2] / "data/wearables"
_ANALYSIS_DIR = Path(__file__).resolve().parents[2] / "data/analysis"

_PARTICIPANTS = [
    "bosbes", "citroen", "kiwi", "kokosnoot",
    "limoen", "peer", "watermeloen", "aardbei",
]


def build_session_features(codename: str) -> pd.DataFrame | None:
    """Build session_features.csv for one participant.

    Reads:
        data/wearables/{codename}/processed/session_biometrics.csv
        data/analysis/{codename}/session_effects.csv

    Returns a DataFrame with one row per session, or None if required files
    are missing.
    """
    bio_path = _WEARABLES_DIR / codename / "processed" / "session_biometrics.csv"
    effects_path = _ANALYSIS_DIR / codename / "session_effects.csv"

    if not bio_path.exists():
        print(f"[{codename}] Missing session_biometrics.csv — skipping")
        return None
    if not effects_path.exists():
        print(f"[{codename}] Missing session_effects.csv — run pipeline.py first")
        return None

    bio = pd.read_csv(bio_path, parse_dates=["date"])
    effects = pd.read_csv(effects_path, parse_dates=["date"])

    # Normalise the date column to date-only (no time component) before joining
    bio["date"] = pd.to_datetime(bio["date"]).dt.normalize()
    effects["date"] = pd.to_datetime(effects["date"]).dt.normalize()

    merged = bio.merge(effects, on="date", how="left", suffixes=("_bio", "_eff"))

    # Resolve columns that exist in both sources (suffixed _bio / _eff after merge).
    # Prefer the _bio version (session_biometrics is the authoritative source for
    # pre-session measurements); fall back to _eff if _bio is absent.
    for col in ("playlist", "pre_stress_mean", "mood_before", "mood_after",
                "mood_before_score", "mood_after_score"):
        bio_col = f"{col}_bio"
        eff_col = f"{col}_eff"
        if bio_col in merged.columns:
            merged[col] = merged[bio_col].combine_first(merged.get(eff_col, pd.Series(dtype=float)))
            merged.drop(columns=[bio_col, eff_col], errors="ignore", inplace=True)
        elif eff_col in merged.columns and col not in merged.columns:
            merged[col] = merged[eff_col]
            merged.drop(columns=[eff_col], errors="ignore", inplace=True)

    # Derive time features from session start
    if "start_local" in merged.columns:
        start = pd.to_datetime(merged["start_local"], errors="coerce")
        merged["hour_of_day"] = start.dt.hour
        merged["day_of_week"] = start.dt.dayofweek  # 0=Monday
    else:
        merged["hour_of_day"] = None
        merged["day_of_week"] = None

    # Standardise mood scale: scores arrive as 4–9 — normalise to 0–10
    for col in ("mood_before_score", "mood_after_score"):
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors="coerce")

    # bb_delta: body_battery start − end (positive = battery recovered during session)
    if "bb_start" in merged.columns and "bb_end" in merged.columns:
        merged["bb_delta"] = merged["bb_end"] - merged["bb_start"]
    elif "bb_delta" not in merged.columns and "bb_drained" in merged.columns:
        merged["bb_delta"] = -merged["bb_drained"]

    # Select and rename columns into the canonical feature schema
    col_map = {
        "date":             "date",
        "playlist":         "playlist",
        "pre_state":           "pre_state",
        "pre_stress_mean":     "pre_stress_mean",
        "pre_hr_mean":         "pre_hr_mean",
        "bb_start":         "bb_start",
        "bb_delta":         "bb_delta",
        "tau_expected":     "tau_expected",
        "tau_actual":       "tau_actual",
        "advantage":        "tau_advantage",
        "r2_actual":        "r2_actual",
        "r2_expected":      "r2_expected",
        "n_points":         "n_points",
        "mood_before_score": "mood_before",
        "mood_after_score":  "mood_after",
        "mood_delta":       "mood_delta",
        "hour_of_day":      "hour_of_day",
        "day_of_week":      "day_of_week",
    }

    present = {src: dst for src, dst in col_map.items() if src in merged.columns}
    features = merged[list(present.keys())].rename(columns=present).copy()
    features.insert(0, "participant", codename)

    return features


def main(participants: list[str]) -> None:
    _ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    all_parts = []

    for codename in participants:
        out_dir = _ANALYSIS_DIR / codename
        out_dir.mkdir(parents=True, exist_ok=True)

        features = build_session_features(codename)
        if features is None or features.empty:
            continue

        out_path = out_dir / "session_features.csv"
        features.to_csv(out_path, index=False)
        print(f"[{codename}] Wrote {len(features)} sessions → {out_path}")
        all_parts.append(features)

    if all_parts:
        combined = pd.concat(all_parts, ignore_index=True)
        combined_path = _ANALYSIS_DIR / "all_session_features.csv"
        combined.to_csv(combined_path, index=False)
        print(f"\nPooled table: {len(combined)} sessions across {len(all_parts)} participants → {combined_path}")
    else:
        print("No data written — run pipeline.py first to generate session_effects.csv files.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build ML feature tables from pipeline outputs")
    parser.add_argument(
        "--participants", nargs="+", default=_PARTICIPANTS,
        help="Participant codenames to process (default: all)"
    )
    args = parser.parse_args()
    main(args.participants)
