"""
pipeline.py — Entry point for Pipeline 3: session effects.

Depends on outputs from:
    Pipeline 1 (extraction): classified_minutes.csv per participant
    Pipeline 2 (baseline):   recovery_baselines.csv per participant

Stages:
    1. session_effect.py     — per-session recovery advantage vs baseline curve
    2. session_features.py   — flat ML feature table per session
    3. session_arc_analysis.py — arc deviations, window comparisons, long-term trends
    4. circadian_significance.py — Wilcoxon + OLS significance tests
    5. recovery_analysis.py  — quality filtering, recovery_features.csv, plots

Usage:
    uv run python scripts/sessions/pipeline.py peer
    uv run python scripts/sessions/pipeline.py --all
    uv run python scripts/sessions/pipeline.py --participants bosbes kokosnoot
    uv run python scripts/sessions/pipeline.py --help

Skip condition:
    If data/analysis/session_arc/significance_results.csv exists and is newer
    than data/analysis/{codename}/recovery_baselines.csv for all participants,
    the pipeline is skipped unless --force is passed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

# Add scripts/ to path so cross-package imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from baseline.baselines import PersonBaseline
from sessions.session_effect import analyze_sessions, run_statistics, load_participant_data
from sessions.session_features import build_session_features
from sessions.session_arc_analysis import build_arc_deviations, run_significance_tests, compute_long_term_trends
from sessions.session_arc_analysis import plot_arc_per_participant, plot_deviation_heatmap, plot_long_term_trends, plot_rolling_baseline, plot_significance_summary
from sessions.circadian_significance import load_participant_data as load_feature_matrix, main as run_circadian_significance
from sessions.recovery_analysis import main as run_recovery_analysis, DEFAULT_R2_THRESHOLD

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
ANALYSIS_ROOT = DATA_ROOT / "analysis"
WEARABLES_DIR = DATA_ROOT / "wearables"

PARTICIPANTS = [
    "bosbes", "citroen", "kiwi", "kokosnoot",
    "limoen", "peer", "watermeloen", "aardbei",
]


# ── Skip logic ───────────────────────────────────────────────────────────────

def _is_fresh(codename: str) -> bool:
    """Return True if session arc significance results are newer than baseline outputs."""
    sig_path = ANALYSIS_ROOT / "session_arc" / "significance_results.csv"
    baseline_path = ANALYSIS_ROOT / codename / "recovery_baselines.csv"

    if not sig_path.exists():
        return False
    if not baseline_path.exists():
        return True  # no baseline to compare against — nothing to do

    return sig_path.stat().st_mtime > baseline_path.stat().st_mtime


# ── Per-participant stage 1–2 ────────────────────────────────────────────────

def _load_minute_data(codename: str) -> pd.DataFrame:
    """Merge per-minute stress, HR, body_battery, and classified activity state."""
    processed = WEARABLES_DIR / codename / "processed"
    classified_path = ANALYSIS_ROOT / codename / "classified_minutes.csv"
    frames = []

    stress_path = processed / "garmin_minute_stress.csv"
    if stress_path.exists():
        df = pd.read_csv(stress_path, index_col="timestamp", parse_dates=True)
        cols = [c for c in ("stress", "body_battery") if c in df.columns]
        if cols:
            frames.append(df[cols])

    for hr_name in ("garmin_minute_hr.csv", "huawei_minute_hr.csv"):
        hr_path = processed / hr_name
        if hr_path.exists():
            df = pd.read_csv(hr_path, index_col="timestamp", parse_dates=True)
            if "heart_rate" in df.columns:
                frames.append(df[["heart_rate"]])
            break

    if classified_path.exists():
        df = pd.read_csv(classified_path, index_col="timestamp", parse_dates=True)
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    merged = frames[0]
    for df in frames[1:]:
        merged = merged.join(df, how="outer")
    merged = merged.sort_index()
    merged.index.name = "timestamp"
    return merged


def run_participant(codename: str) -> dict:
    """Run stages 1–2 (session_effect + session_features) for one participant."""
    print(f"\n{'='*60}")
    print(f"  Participant: {codename}")
    print(f"{'='*60}")

    out_dir = ANALYSIS_ROOT / codename
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load baseline from Pipeline 2 output
    baseline_path = out_dir / "recovery_baselines.csv"
    if not baseline_path.exists():
        print(f"  [!] recovery_baselines.csv not found — run baseline/pipeline.py first")
        return {"participant": codename, "status": "no_baseline"}

    baseline_df = pd.read_csv(baseline_path)
    baseline = PersonBaseline.load_from_summary(baseline_df, participant=codename)
    n_curves = len(baseline_df)
    print(f"  Loaded {n_curves} recovery curves from recovery_baselines.csv")

    # Load session traces and biometrics
    traces, biometrics = load_participant_data(codename, DATA_ROOT)
    if traces.empty or biometrics.empty:
        print(f"  [!] No session data — skipping")
        return {"participant": codename, "status": "no_sessions"}

    # Load classified minutes (Pipeline 1 output)
    classified_path = out_dir / "classified_minutes.csv"
    if classified_path.exists():
        minute_df = pd.read_csv(classified_path, index_col="timestamp", parse_dates=True)
    else:
        print(f"  [!] classified_minutes.csv not found — run extraction/pipeline.py first")
        minute_df = pd.DataFrame()

    # Stage 1 — session effect analysis
    print("  Stage 1: Analysing session effects...")
    effects_df = analyze_sessions(traces, biometrics, minute_df, baseline)

    if effects_df.empty:
        print(f"  [!] No effects computed")
        return {"participant": codename, "status": "no_effects"}

    effects_df["participant"] = codename
    effects_path = out_dir / "session_effects.csv"
    effects_df.to_csv(effects_path, index=False)

    n_valid = effects_df["advantage"].notna().sum()
    mean_adv = effects_df["advantage"].mean() if n_valid > 0 else None
    print(f"  → {len(effects_df)} sessions, {n_valid} with valid advantage scores")
    if mean_adv is not None:
        print(f"  → Mean recovery advantage: {mean_adv:+.1f} min")

    # Stage 2 — ML feature table
    print("  Stage 2: Building ML feature table...")
    features = build_session_features(codename)
    if features is not None and not features.empty:
        feat_path = out_dir / "session_features.csv"
        features.to_csv(feat_path, index=False)
        print(f"  → {len(features)} rows → session_features.csv")

    return {
        "participant": codename,
        "status": "ok",
        "n_sessions": len(effects_df),
        "n_valid_advantages": int(n_valid),
        "mean_advantage_min": round(float(mean_adv), 2) if mean_adv is not None else None,
    }


# ── Cross-participant stages ──────────────────────────────────────────────────

def run_cross_participant(all_effects: list[pd.DataFrame]) -> None:
    """Pool all participants and write cross-participant stats."""
    print(f"\n{'='*60}")
    print("  Cross-participant statistics")
    print(f"{'='*60}")

    combined = pd.concat(all_effects, ignore_index=True)
    combined_path = ANALYSIS_ROOT / "cross_participant_effects.csv"
    combined.to_csv(combined_path, index=False)
    print(f"  Pooled {len(combined)} sessions from {combined['participant'].nunique()} participants")

    stats = run_statistics(combined)

    if "ttest" in stats:
        t = stats["ttest"]
        print(f"\n  One-sample t-test (advantage ≠ 0):")
        print(f"    n={t['n']}, mean={t['mean_advantage_min']:+.2f} min, "
              f"t={t['statistic']:.3f}, p={t['p_value']:.4f}")
        print(f"    → {t['interpretation']}")

    if "anova_playlist" in stats:
        a = stats["anova_playlist"]
        print(f"\n  ANOVA by playlist: F={a['f_statistic']:.3f}, p={a['p_value']:.4f}")

    stats_path = ANALYSIS_ROOT / "cross_participant_stats.json"
    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)
    print(f"\n  → cross_participant_effects.csv and cross_participant_stats.json")


def run_arc_analysis(participants: list[str]) -> None:
    """Stage 3 — arc deviations, significance tests, long-term trends, plots."""
    print(f"\n{'='*60}")
    print("  Stage 3: Session arc analysis")
    print(f"{'='*60}")

    arc_output = ANALYSIS_ROOT / "session_arc"
    plot_dir = arc_output / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    arc_df = build_arc_deviations(participants)
    if arc_df.empty:
        print("  No arc data produced.")
        return

    arc_df.to_csv(arc_output / "arc_deviations.csv", index=False)
    print(f"  {len(arc_df)} sessions × {len(arc_df.columns)} columns → arc_deviations.csv")

    sig_df = run_significance_tests(arc_df)
    sig_df.to_csv(arc_output / "significance_results.csv", index=False)
    n_sig = int((sig_df["q_value"] < 0.05).sum()) if not sig_df.empty else 0
    print(f"  {len(sig_df)} tests, {n_sig} significant at FDR q < 0.05 → significance_results.csv")

    trends_df = compute_long_term_trends(arc_df)
    trends_df.to_csv(arc_output / "long_term_trends.csv", index=False)
    print(f"  {len(trends_df)} trend analyses → long_term_trends.csv")

    plot_arc_per_participant(arc_df, plot_dir)
    plot_deviation_heatmap(arc_df, plot_dir)
    plot_long_term_trends(arc_df, plot_dir)
    plot_rolling_baseline(arc_df, plot_dir)
    plot_significance_summary(sig_df, plot_dir)
    print(f"  Plots → {plot_dir}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pipeline 3 — session effects for Project R.E.M."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("codename", nargs="?", help="Single participant codename")
    group.add_argument("--all", action="store_true", help="Run all known participants")
    group.add_argument("--participants", nargs="+", metavar="CODENAME",
                       help="One or more participant codenames")
    parser.add_argument("--force", action="store_true",
                        help="Re-run even if outputs are already fresh")
    parser.add_argument("--r2-threshold", type=float, default=DEFAULT_R2_THRESHOLD,
                        help=f"r2_actual threshold for reliable flag (default: {DEFAULT_R2_THRESHOLD})")
    args = parser.parse_args()

    if args.codename:
        participants = [args.codename]
    elif args.all:
        participants = PARTICIPANTS
    elif args.participants:
        participants = args.participants
    else:
        parser.print_help()
        sys.exit(0)

    ANALYSIS_ROOT.mkdir(parents=True, exist_ok=True)

    # Skip check
    if not args.force:
        fresh = [p for p in participants if _is_fresh(p)]
        if fresh:
            print(f"  Outputs already fresh for: {', '.join(fresh)}")
            print("  Pass --force to re-run.")
            participants = [p for p in participants if p not in fresh]
        if not participants:
            print("  Nothing to do.")
            return

    # Stages 1–2 per participant
    summaries = []
    all_effects = []

    for codename in participants:
        try:
            summary = run_participant(codename)
            summaries.append(summary)

            effects_path = ANALYSIS_ROOT / codename / "session_effects.csv"
            if effects_path.exists():
                df = pd.read_csv(effects_path)
                if not df.empty:
                    if "participant" not in df.columns:
                        df["participant"] = codename
                    all_effects.append(df)
        except Exception as e:
            print(f"\n  [!] {codename}: {e}")
            summaries.append({"participant": codename, "status": "error", "error": str(e)})

    # Cross-participant stats
    if len(all_effects) >= 2:
        run_cross_participant(all_effects)
    elif len(all_effects) == 1:
        print("\n  Only 1 participant with data — skipping cross-participant stats")

    # ML feature table (all participants)
    print(f"\n{'='*60}")
    print("  Pooled ML feature table")
    print(f"{'='*60}")
    all_features = []
    for codename in participants:
        feat_path = ANALYSIS_ROOT / codename / "session_features.csv"
        if feat_path.exists():
            df = pd.read_csv(feat_path)
            if not df.empty:
                all_features.append(df)
    if all_features:
        combined = pd.concat(all_features, ignore_index=True)
        combined_path = ANALYSIS_ROOT / "all_session_features.csv"
        combined.to_csv(combined_path, index=False)
        print(f"  {len(combined)} sessions → all_session_features.csv")

    # Stage 3 — arc analysis
    run_arc_analysis(participants)

    # Stage 4 — circadian significance (reads feature_matrix.csv from Pipeline 2)
    print(f"\n{'='*60}")
    print("  Stage 4: Circadian significance tests")
    print(f"{'='*60}")
    try:
        run_circadian_significance()
    except FileNotFoundError as e:
        print(f"  [!] {e}")

    # Stage 5 — recovery analysis
    print(f"\n{'='*60}")
    print("  Stage 5: Recovery analysis")
    print(f"{'='*60}")
    run_recovery_analysis(participants, args.r2_threshold)

    # Summary
    print(f"\n{'='*60}")
    print("  Summary")
    print(f"{'='*60}")
    for s in summaries:
        p = s["participant"]
        status = s["status"]
        if status == "ok":
            mean_adv = s.get('mean_advantage_min') or 0
            print(f"  {p:<15} OK  {s['n_sessions']} sessions, "
                  f"mean advantage {mean_adv:+.1f} min")
        else:
            print(f"  {p:<15} --  {status}")


if __name__ == "__main__":
    main()
