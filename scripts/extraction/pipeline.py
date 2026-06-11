#!/usr/bin/env python3
"""
pipeline.py — Extraction pipeline entry point for Project R.E.M.

Runs the full extraction sequence for one or all participants:
  1. Device extraction  — Garmin or Huawei GDPR export → per-minute CSVs
  2. Activity classification — minute-level biometrics → activity state labels

Device type is detected automatically from the raw export folder:
  - Garmin: has *.zip FIT archives
  - Huawei: has "health detail data*.json" files

Skip logic: extraction is skipped per participant if the processed stress CSV
already exists and is newer than any file in the raw export directory.

Usage:
    uv run python scripts/extraction/pipeline.py bosbes
    uv run python scripts/extraction/pipeline.py --all
    uv run python scripts/extraction/pipeline.py bosbes kokosnoot --force
"""

import argparse
import sys
from pathlib import Path

# Allow imports from this package regardless of working directory
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

from activity_classifier import ActivityClassifier
from garmin_pipeline import run as garmin_run
from huawei_pipeline import run as huawei_run

PARTICIPANTS = [
    "bosbes", "citroen", "kiwi", "kokosnoot",
    "limoen", "peer", "watermeloen", "aardbei",
]

# Device-specific stress CSV names (used for skip detection)
_STRESS_CSV = {
    "garmin": "garmin_minute_stress.csv",
    "huawei": "huawei_minute_stress.csv",
}
_HR_CSV = {
    "garmin": "garmin_minute_hr.csv",
    "huawei": "huawei_minute_hr.csv",
}
_ACTIVITY_CSV = {
    "garmin": "garmin_minute_activity.csv",
    "huawei": None,  # Huawei has no FIT activity data
}


def detect_device(export_dir: Path) -> str | None:
    """Detect wearable device from raw export folder contents."""
    if not export_dir.exists():
        return None
    if list(export_dir.rglob("*.zip")):
        return "garmin"
    if list(export_dir.rglob("health detail data*.json")):
        return "huawei"
    return None


def outputs_are_fresh(processed_dir: Path, export_dir: Path, device: str) -> bool:
    """Return True if processed stress CSV exists and is newer than the raw export."""
    stress_csv = processed_dir / _STRESS_CSV[device]
    if not stress_csv.exists():
        return False

    processed_mtime = stress_csv.stat().st_mtime
    raw_files = list(export_dir.rglob("*"))
    if not raw_files:
        return True  # nothing to compare against

    newest_raw = max(f.stat().st_mtime for f in raw_files if f.is_file())
    return processed_mtime >= newest_raw


def classify_activity(code: str, processed_dir: Path, analysis_dir: Path, device: str) -> None:
    """Load minute-level biometrics, run ActivityClassifier, write classified_minutes.csv."""
    stress_csv = processed_dir / _STRESS_CSV[device]
    hr_csv     = processed_dir / _HR_CSV[device]
    act_csv    = (_ACTIVITY_CSV[device] and processed_dir / _ACTIVITY_CSV[device])

    frames = []
    for csv in [stress_csv, hr_csv, act_csv]:
        if csv and csv.exists():
            frames.append(pd.read_csv(csv, index_col=0, parse_dates=True))

    if not frames:
        print(f"  [{code}] No minute-level CSVs found — skipping activity classification")
        return

    minute_df = pd.concat(frames, axis=1)
    minute_df = minute_df[~minute_df.index.duplicated(keep="first")].sort_index()

    classifier = ActivityClassifier()
    states = classifier.predict(minute_df)
    result = minute_df.copy()
    result["activity_state"] = states

    analysis_dir.mkdir(parents=True, exist_ok=True)
    out = analysis_dir / "classified_minutes.csv"
    result.to_csv(out)
    print(f"  [{code}] → classified_minutes.csv ({len(result)} records, "
          f"{states.notna().sum()} classified)")


def run_participant(
    code: str,
    root: Path,
    checkin_path: Path | None,
    months: int,
    force: bool,
) -> None:
    base         = root / "data" / "wearables" / code
    export_dir   = base / "raw" / "export"
    processed_dir = base / "processed"
    analysis_dir  = root / "data" / "analysis" / code

    device = detect_device(export_dir)
    if device is None:
        print(f"[{code}] No raw export found at {export_dir} — skipping")
        return

    print(f"\n{'='*60}")
    print(f"  {code}  ({device})")
    print(f"{'='*60}")

    # Skip extraction if outputs are fresh; also re-run if session_biometrics.csv
    # is missing but a checkin file is available (e.g. path bug was previously active).
    session_bio_missing = (
        checkin_path is not None
        and not (processed_dir / "session_biometrics.csv").exists()
    )
    if not force and outputs_are_fresh(processed_dir, export_dir, device) and not session_bio_missing:
        print(f"  [{code}] Processed files up-to-date — skipping extraction (use --force to re-run)")
    else:
        if device == "garmin":
            garmin_run(export_dir, processed_dir, checkin_path, code, months)
        else:
            huawei_run(export_dir, processed_dir, checkin_path, code, months)

    # Always re-run activity classification so it picks up any new processed files
    print(f"\n  [{code}] Classifying activity states...")
    classify_activity(code, processed_dir, analysis_dir, device)


def main():
    parser = argparse.ArgumentParser(
        description="R.E.M. extraction pipeline — wearable data → per-minute CSVs + activity states",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "participants", nargs="*",
        help="Participant codename(s). Omit to use --all.",
    )
    parser.add_argument(
        "--all", action="store_true",
        help=f"Run for all known participants: {', '.join(PARTICIPANTS)}",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-run extraction even if processed files are up-to-date",
    )
    parser.add_argument(
        "--root", type=Path, default=None,
        help="Project root directory (auto-detected from script location)",
    )
    parser.add_argument(
        "--checkin", type=Path, default=None,
        help="Override path to check-in CSV",
    )
    parser.add_argument(
        "--months", type=int, default=6,
        help="Fallback date window in months if no check-in data found (default: 6)",
    )
    args = parser.parse_args()

    root = args.root or Path(__file__).resolve().parent.parent.parent
    if not (root / "data").exists():
        sys.exit(f"✗ Can't find project root (tried {root}). Use --root.")

    checkin = args.checkin or next((root / "data" / "checkins").glob("[!_]*.csv"), None)

    targets = PARTICIPANTS if args.all else args.participants
    if not targets:
        parser.print_help()
        sys.exit(1)

    for code in targets:
        run_participant(code, root, checkin, args.months, args.force)

    print("\n✓ Extraction pipeline complete.")


if __name__ == "__main__":
    main()
