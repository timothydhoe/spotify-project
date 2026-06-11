#!/usr/bin/env python3
"""
pipeline.py — Baseline pipeline entry point for Project R.E.M.

Runs the full baseline sequence for one or all participants:
  1. Circadian baselines — hourly stress/HR means from non-session days
  2. Feature matrix     — per-session ML features with baseline deviations
  3. Recovery curves    — PersonBaseline exponential fits per activity state

Skip logic: all stages are skipped if hourly_baseline.csv exists and is newer
than the participant's minute-level wearable CSVs.

Usage:
    uv run python scripts/baseline/pipeline.py peer
    uv run python scripts/baseline/pipeline.py bosbes kokosnoot
    uv run python scripts/baseline/pipeline.py --all
    uv run python scripts/baseline/pipeline.py peer --force
"""

import argparse
import sys
from pathlib import Path

# Add scripts/ to path so baseline.* and extraction.* imports resolve
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SCRIPTS_DIR))

import pandas as pd

from baseline.baselines import PersonBaseline
from baseline.circadian_baseline import export_baselines

PARTICIPANTS = [
    "bosbes", "citroen", "kiwi", "kokosnoot",
    "limoen", "peer", "watermeloen", "aardbei",
]

_STRESS_CSVS = ("garmin_minute_stress.csv", "huawei_minute_stress.csv")
_HR_CSVS = ("garmin_minute_hr.csv", "huawei_minute_hr.csv")


def _find_minute_csv(proc_dir: Path, candidates: tuple[str, ...]) -> Path | None:
    for name in candidates:
        path = proc_dir / name
        if path.exists():
            return path
    return None


def outputs_are_fresh(processed_dir: Path, output_path: Path) -> bool:
    """Return True if hourly_baseline.csv exists and is newer than wearable minute CSVs."""
    if not output_path.exists():
        return False
    output_mtime = output_path.stat().st_mtime
    for name in _STRESS_CSVS + _HR_CSVS:
        p = processed_dir / name
        if p.exists() and p.stat().st_mtime > output_mtime:
            return False
    return True


def run_participant(code: str, root: Path, force: bool) -> None:
    data_dir     = root / "data" / "wearables"
    analysis_dir = root / "data" / "analysis"
    proc_dir     = data_dir / code / "processed"
    output_path  = analysis_dir / code / "circadian_baselines" / "hourly_baseline.csv"

    if not proc_dir.exists():
        print(f"[{code}] No processed data found at {proc_dir} — skipping")
        return

    has_stress = any((proc_dir / name).exists() for name in _STRESS_CSVS)
    if not has_stress:
        print(f"[{code}] No minute-level stress data in {proc_dir} — skipping (run extraction first)")
        return

    print(f"\n{'='*60}")
    print(f"  {code}")
    print(f"{'='*60}")

    # Skip if outputs are fresh
    if not force and outputs_are_fresh(proc_dir, output_path):
        print(f"  [{code}] Baselines up-to-date — skipping (use --force to re-run)")
        return

    # Stage 1 + 2: circadian baselines + feature matrix
    print(f"  [{code}] Computing circadian baselines and feature matrix...")
    export_baselines([code], data_dir, analysis_dir)

    # Stage 3: PersonBaseline (activity-state baselines + recovery curves)
    print(f"  [{code}] Fitting recovery curves...")
    stress_csv = _find_minute_csv(proc_dir, _STRESS_CSVS)
    hr_csv     = _find_minute_csv(proc_dir, _HR_CSVS)

    # classified_minutes.csv already contains stress + hr + activity_state —
    # use it as the sole source if available to avoid duplicate columns.
    classified_path = analysis_dir / code / "classified_minutes.csv"
    frames = []
    if classified_path.exists():
        frames.append(pd.read_csv(classified_path, index_col=0, parse_dates=True))
    else:
        for csv in [stress_csv, hr_csv]:
            if csv:
                frames.append(pd.read_csv(csv, index_col=0, parse_dates=True))

    if not frames:
        print(f"  [{code}] No minute-level CSVs found — skipping recovery curve fitting")
        return

    minute_df = pd.concat(frames, axis=1)
    minute_df = minute_df[~minute_df.index.duplicated(keep="first")].sort_index()

    session_dates = list(
        pd.read_csv(proc_dir / "session_biometrics.csv")["date"].astype(str)
    )
    bl = PersonBaseline(participant=code)
    bl.fit(minute_df, session_dates)

    summary = bl.summary()
    if summary.empty:
        print(f"  [{code}] No recovery curves fitted (insufficient transition data)")
    else:
        out = analysis_dir / code / "circadian_baselines" / "recovery_curves.csv"
        summary.to_csv(out, index=False)
        print(f"  [{code}] → recovery_curves.csv ({len(summary)} curves)")
        print(summary.to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="R.E.M. baseline pipeline — wearable CSVs → circadian baselines + recovery curves",
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
        help="Re-run even if baseline outputs are up-to-date",
    )
    parser.add_argument(
        "--root", type=Path, default=None,
        help="Project root directory (auto-detected from script location)",
    )
    args = parser.parse_args()

    root = args.root or Path(__file__).resolve().parent.parent.parent
    if not (root / "data").exists():
        sys.exit(f"✗ Can't find project root (tried {root}). Use --root.")

    targets = PARTICIPANTS if args.all else args.participants
    if not targets:
        parser.print_help()
        sys.exit(1)

    for code in targets:
        run_participant(code, root, args.force)

    print("\n✓ Baseline pipeline complete.")


if __name__ == "__main__":
    main()
