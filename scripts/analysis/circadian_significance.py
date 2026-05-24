"""
circadian_significance.py — Significance testing for session effects.

Per-participant inference tests on the feature matrix built by circadian_baseline.py.
Separate from circadian_ml.py (prediction) — this script answers "is there an effect?"

Tests:
    1. Immediate session effects (Wilcoxon signed-rank, two-tailed):
       - Pre vs during/post stress & HR — unstratified
       - Same, stratified by playlist type
       - Same, stratified by playlist × pre_state
    2. Mood effect (one-sample Wilcoxon):
       - mood_delta ≠ 0 per playlist type
    3. Long-term trend (OLS regression):
       - pre_study_stress/hr_deviation over session sequence

Output:
    data/analysis/circadian_baselines/significance_tests.csv
    One row per test per participant. Columns:
    participant, test_category, test_name, metric, statistic, p_value,
    effect_size, direction, n, significant_05

Usage:
    python scripts/analysis/circadian_significance.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm, wilcoxon
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests

# ── Paths ───────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = PROJECT_ROOT / "data" / "analysis"
COMBINED_DIR = ANALYSIS_DIR / "circadian_baselines"
FEATURE_MATRIX_PATH = COMBINED_DIR / "feature_matrix.csv"
OUTPUT_PATH = COMBINED_DIR / "significance_tests.csv"

MIN_OBS = 5  # minimum observations to run a test


# ── Data loading ────────────────────────────────────────────────────────────


def load_participant_data() -> dict[str, pd.DataFrame]:
    """Load feature matrix and split by participant.

    Returns dict of {participant_codename: DataFrame}.
    """
    if not FEATURE_MATRIX_PATH.exists():
        raise FileNotFoundError(
            f"Feature matrix not found: {FEATURE_MATRIX_PATH}\n"
            f"Run: python scripts/analysis/circadian_baseline.py"
        )

    fm = pd.read_csv(FEATURE_MATRIX_PATH)
    return {name: group.reset_index(drop=True) for name, group in fm.groupby("participant")}


# ── Test functions (stubs) ──────────────────────────────────────────────────


def _run_wilcoxon(
    pre: pd.Series,
    post: pd.Series,
    participant: str,
    test_category: str,
    test_name: str,
    metric: str,
) -> dict | None:
    """Run a single Wilcoxon signed-rank test on paired pre/post values.

    Returns a result dict, or None if fewer than MIN_OBS valid pairs.
    """
    # Drop pairs where either value is NaN
    mask = pre.notna() & post.notna()
    pre_clean = pre[mask].values
    post_clean = post[mask].values
    n = len(pre_clean)

    if n < MIN_OBS:
        return None

    diff = post_clean - pre_clean

    # All-zero differences → no test possible
    if np.all(diff == 0):
        return None

    stat, p_value = wilcoxon(diff, alternative="two-sided")

    # Effect size r = Z / sqrt(N) with correct sign from observed direction.
    # norm.ppf(1 - p/2) gives |Z| from the two-tailed p; multiply by the sign
    # of the mean difference so r reflects the direction of the effect.
    mean_diff = np.mean(diff)
    z_abs = norm.ppf(1 - p_value / 2) if p_value < 1.0 else 0.0
    z = z_abs * np.sign(mean_diff) if mean_diff != 0 else 0.0
    effect_size = z / np.sqrt(n)

    direction = "increase" if mean_diff > 0 else "decrease" if mean_diff < 0 else "none"

    return {
        "participant": participant,
        "test_category": test_category,
        "test_name": test_name,
        "metric": metric,
        "statistic": round(stat, 4),
        "p_value": round(p_value, 6),
        "effect_size": round(effect_size, 4),
        "direction": direction,
        "n": n,
        "significant_05": p_value < 0.05,
    }


def test_immediate(df: pd.DataFrame, participant: str) -> list[dict]:
    """Wilcoxon signed-rank: pre vs during/post stress & HR, all sessions."""
    results = []

    pairs = [
        ("pre_stress_mean", "during_stress_mean", "pre_vs_during", "stress"),
        ("pre_stress_mean", "post_stress_mean", "pre_vs_post", "stress"),
        ("pre_hr_mean", "during_hr_mean", "pre_vs_during", "hr"),
        ("pre_hr_mean", "post_hr_mean", "pre_vs_post", "hr"),
    ]

    for pre_col, post_col, test_name, metric in pairs:
        if pre_col not in df.columns or post_col not in df.columns:
            continue
        result = _run_wilcoxon(
            df[pre_col], df[post_col],
            participant, "immediate_all", test_name, metric,
        )
        if result is not None:
            results.append(result)

    return results


def test_by_playlist(df: pd.DataFrame, participant: str) -> list[dict]:
    """Wilcoxon signed-rank: pre vs during/post, stratified by playlist type."""
    results = []

    if "playlist" not in df.columns:
        return results

    pairs = [
        ("pre_stress_mean", "during_stress_mean", "pre_vs_during", "stress"),
        ("pre_stress_mean", "post_stress_mean", "pre_vs_post", "stress"),
        ("pre_hr_mean", "during_hr_mean", "pre_vs_during", "hr"),
        ("pre_hr_mean", "post_hr_mean", "pre_vs_post", "hr"),
    ]

    for playlist_type, group in df.groupby("playlist"):
        for pre_col, post_col, test_name, metric in pairs:
            if pre_col not in group.columns or post_col not in group.columns:
                continue
            result = _run_wilcoxon(
                group[pre_col], group[post_col],
                participant,
                "immediate_by_playlist",
                f"{test_name}_{playlist_type}",
                metric,
            )
            if result is not None:
                results.append(result)

    return results


def test_by_playlist_activity(df: pd.DataFrame, participant: str) -> list[dict]:
    """Wilcoxon signed-rank: pre vs during/post, stratified by playlist × pre_state."""
    results = []

    if "playlist" not in df.columns or "pre_state" not in df.columns:
        return results

    pairs = [
        ("pre_stress_mean", "during_stress_mean", "pre_vs_during", "stress"),
        ("pre_stress_mean", "post_stress_mean", "pre_vs_post", "stress"),
        ("pre_hr_mean", "during_hr_mean", "pre_vs_during", "hr"),
        ("pre_hr_mean", "post_hr_mean", "pre_vs_post", "hr"),
    ]

    for (playlist_type, pre_state), group in df.groupby(["playlist", "pre_state"]):
        for pre_col, post_col, test_name, metric in pairs:
            if pre_col not in group.columns or post_col not in group.columns:
                continue
            result = _run_wilcoxon(
                group[pre_col], group[post_col],
                participant,
                "immediate_by_playlist_activity",
                f"{test_name}_{playlist_type}_{pre_state}",
                metric,
            )
            if result is not None:
                results.append(result)

    return results


def test_mood(df: pd.DataFrame, participant: str) -> list[dict]:
    """One-sample Wilcoxon: mood_delta ≠ 0, per playlist type."""
    results = []

    if "mood_delta" not in df.columns or "playlist" not in df.columns:
        return results

    for playlist_type, group in df.groupby("playlist"):
        values = group["mood_delta"].dropna().values
        n = len(values)

        if n < MIN_OBS:
            continue

        # All zeros → no test possible
        if np.all(values == 0):
            continue

        stat, p_value = wilcoxon(values, alternative="two-sided")

        mean_val = np.mean(values)
        z_abs = norm.ppf(1 - p_value / 2) if p_value < 1.0 else 0.0
        z = z_abs * np.sign(mean_val) if mean_val != 0 else 0.0
        effect_size = z / np.sqrt(n)

        direction = "improvement" if mean_val > 0 else "worsening" if mean_val < 0 else "none"

        results.append({
            "participant": participant,
            "test_category": "mood_by_playlist",
            "test_name": f"mood_delta_{playlist_type}",
            "metric": "mood",
            "statistic": round(stat, 4),
            "p_value": round(p_value, 6),
            "effect_size": round(effect_size, 4),
            "direction": direction,
            "n": n,
            "significant_05": p_value < 0.05,
        })

    return results


def test_long_term_trend(df: pd.DataFrame, participant: str) -> list[dict]:
    """OLS regression: pre_study deviation over session sequence number."""
    results = []

    # Sort by date to get correct session sequence
    df_sorted = df.sort_values("date").reset_index(drop=True)
    df_sorted["session_seq"] = range(1, len(df_sorted) + 1)

    trend_cols = [
        ("pre_study_stress_deviation", "stress_deviation"),
        ("pre_study_hr_deviation", "hr_deviation"),
        ("hrv_rmssd", "hrv"),
        ("avg_resp_daily", "respiration"),
    ]

    for col, metric in trend_cols:
        if col not in df_sorted.columns:
            continue

        valid = df_sorted[[col, "session_seq"]].dropna()
        n = len(valid)

        # For optional features (HRV, respiration), require >50% non-NaN
        if col in ("hrv_rmssd", "avg_resp_daily"):
            if n < len(df_sorted) * 0.5:
                continue

        if n < MIN_OBS:
            continue

        # OLS: col ~ session_seq + intercept
        X = sm.add_constant(valid["session_seq"])
        model = sm.OLS(valid[col], X).fit()

        slope = model.params["session_seq"]
        p_value = model.pvalues["session_seq"]
        direction = "increasing" if slope > 0 else "decreasing" if slope < 0 else "flat"

        results.append({
            "participant": participant,
            "test_category": "long_term_trend",
            "test_name": f"trend_over_sessions",
            "metric": metric,
            "statistic": round(slope, 6),
            "p_value": round(p_value, 6),
            "effect_size": round(slope, 6),
            "direction": direction,
            "n": n,
            "significant_05": p_value < 0.05,
        })

    return results


# ── Main ────────────────────────────────────────────────────────────────────


def main() -> None:
    participant_data = load_participant_data()
    all_results: list[dict] = []

    for participant, df in sorted(participant_data.items()):
        print(f"  {participant}: {len(df)} sessions")

        all_results.extend(test_immediate(df, participant))
        all_results.extend(test_by_playlist(df, participant))
        all_results.extend(test_by_playlist_activity(df, participant))
        all_results.extend(test_mood(df, participant))
        all_results.extend(test_long_term_trend(df, participant))

    # Save results
    if all_results:
        results_df = pd.DataFrame(all_results)

        # Benjamini-Hochberg FDR correction across all tests
        p_vals = results_df["p_value"].values
        _, q_vals, _, _ = multipletests(p_vals, method="fdr_bh")
        results_df["q_value"] = np.round(q_vals, 6)
        results_df["significant_fdr"] = q_vals < 0.05

        COMBINED_DIR.mkdir(parents=True, exist_ok=True)
        results_df.to_csv(OUTPUT_PATH, index=False)
        sig_05  = results_df["significant_05"].sum()
        sig_fdr = results_df["significant_fdr"].sum()
        print(f"\n  Saved {len(results_df)} test results → {OUTPUT_PATH.name}")
        print(f"  Significant at p<0.05: {sig_05} | Significant after FDR (q<0.05): {sig_fdr}")
    else:
        print("\n  No tests produced results.")


if __name__ == "__main__":
    main()
