"""
session_effect.py — Stage 3: Measure music session effect on physiological recovery.

For each music listening session:
1. Classify the pre-session activity state (Stage 1 output)
2. Look up the expected recovery curve for that participant + prior state (Stage 2 output)
3. Fit the actual recovery curve from the session trace
4. Compute recovery advantage = τ_expected - τ_actual (positive = faster recovery with music)
5. Run statistical tests: per-participant t-test + cross-participant mixed-effects model

Inputs:
    - session_traces_all.csv (from existing garmin_pipeline.py output)
    - classified minute DataFrame (from activity_classifier.py)
    - PersonBaseline instance (from baselines.py — load via PersonBaseline.load_from_summary())

Output columns in session_effects.csv:
    date, playlist, pre_state, tau_expected, tau_actual, advantage,
    r2_actual, r2_expected, n_points, mood_delta (if available)
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit, OptimizeWarning

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from baseline.baselines import PersonBaseline, RecoveryCurve, _fit_exp_decay
from sessions.utils import classify_window_state, local_to_utc

# Minutes before session start to use for pre-state classification
_PRE_WINDOW_MIN = 30
# Minimum valid signal points required to attempt curve fitting
_MIN_FIT_POINTS = 8
# Signal to use as primary recovery indicator
_PRIMARY_SIGNAL = "stress"
_SECONDARY_SIGNAL = "heart_rate"


def analyze_sessions(
    session_traces: pd.DataFrame,
    session_biometrics: pd.DataFrame,
    classified_df: pd.DataFrame,
    baseline: PersonBaseline,
    signal: str = _PRIMARY_SIGNAL,
) -> pd.DataFrame:
    """Compute recovery advantage for all sessions of one participant.

    Args:
        session_traces: From session_traces_all.csv — per-minute traces with phase labels.
        session_biometrics: From session_biometrics.csv — one row per session.
        classified_df: Per-minute DataFrame with 'activity_state' column and datetime index.
        baseline: PersonBaseline for this participant (fitted or loaded via load_from_summary()).
        signal: Which physiological signal to analyze (default: 'stress').

    Returns:
        DataFrame with one row per session and recovery statistics.
    """
    results = []

    for _, bio_row in session_biometrics.iterrows():
        session_date = bio_row["date"]
        playlist = bio_row["playlist"]

        # Extract this session's trace
        traces = session_traces[session_traces["session_date"] == session_date].copy()
        if traces.empty:
            continue

        # Classify pre-session state from continuous minute data
        pre_state = _classify_pre_session_state(classified_df, bio_row)

        # Get expected recovery curve
        expected_curve = baseline.get_recovery_curve(pre_state, signal)
        tau_expected = expected_curve.tau if expected_curve else None
        r2_expected = expected_curve.r_squared if expected_curve else None

        # Fit actual recovery from session trace (during + post phases)
        tau_actual, r2_actual, n_points = _fit_session_recovery(traces, signal, expected_curve)

        # Recovery advantage: positive means music helped recover faster
        # Discard if actual curve hit the max bound (500 min) — fit didn't converge
        TAU_MAX = 490.0
        if tau_actual is not None and tau_actual >= TAU_MAX:
            tau_actual = None
            r2_actual = None

        advantage = None
        if tau_expected is not None and tau_actual is not None:
            advantage = round(tau_expected - tau_actual, 2)

        # Mood delta (if available in biometrics)
        mood_before = bio_row.get("mood_before_score")
        mood_after = bio_row.get("mood_after_score")
        mood_delta = None
        if pd.notna(mood_before) and pd.notna(mood_after):
            try:
                mood_delta = float(mood_after) - float(mood_before)
            except (ValueError, TypeError):
                pass

        results.append({
            "date":           session_date,
            "playlist":       playlist,
            "pre_state":      pre_state,
            "pre_stress_mean": bio_row.get("pre_stress_mean"),
            "tau_expected":   round(tau_expected, 2) if tau_expected else None,
            "tau_actual":     round(tau_actual, 2) if tau_actual else None,
            "advantage":      advantage,
            "r2_actual":      round(r2_actual, 3) if r2_actual is not None else None,
            "r2_expected":    round(r2_expected, 3) if r2_expected is not None else None,
            "n_points":       n_points,
            "mood_delta":     mood_delta,
            "mood_before":    mood_before,
            "mood_after":     mood_after,
        })

    return pd.DataFrame(results)


def run_statistics(effects_df: pd.DataFrame) -> dict:
    """Run statistical tests on the session effects DataFrame.

    Args:
        effects_df: Output of analyze_sessions() (or cross-participant concat with 'participant' col).

    Returns:
        Dict with test results: t-test, ANOVA by playlist, mixed-effects model (if statsmodels available).
    """
    from scipy import stats

    results = {}
    valid = effects_df.dropna(subset=["advantage"])

    if len(valid) < 3:
        return {"error": "Insufficient data for statistical testing"}

    # 1. One-sample t-test: is mean advantage significantly different from 0?
    t_stat, p_val = stats.ttest_1samp(valid["advantage"], 0)
    results["ttest"] = {
        "statistic": round(float(t_stat), 3),
        "p_value":   round(float(p_val), 4),
        "n":         int(len(valid)),
        "mean_advantage_min": round(float(valid["advantage"].mean()), 2),
        "std_advantage":  round(float(valid["advantage"].std()), 2),
        "interpretation": "Music sessions show significantly faster recovery" if p_val < 0.05
                          else "No significant recovery difference detected",
    }

    # 2. One-way ANOVA by playlist type
    playlist_groups = [g["advantage"].dropna().values for _, g in valid.groupby("playlist") if len(g) >= 3]
    if len(playlist_groups) >= 2:
        f_stat, p_anova = stats.f_oneway(*playlist_groups)
        results["anova_playlist"] = {
            "f_statistic": round(float(f_stat), 3),
            "p_value":     round(float(p_anova), 4),
            "n_groups":    len(playlist_groups),
        }

        if len(playlist_groups) >= 2:
            try:
                tukey = stats.tukey_hsd(*playlist_groups)
                playlist_names = [name for name, g in valid.groupby("playlist") if len(g) >= 3]
                results["tukey"] = {
                    f"{playlist_names[i]} vs {playlist_names[j]}": {
                        "p_value": round(float(tukey.pvalue[i][j]), 4)
                    }
                    for i in range(len(playlist_names))
                    for j in range(i + 1, len(playlist_names))
                }
            except AttributeError:
                pass

    # 3. Mixed-effects model (requires statsmodels + participant column + ≥2 participants)
    if "participant" in valid.columns and valid["participant"].nunique() >= 2:
        results["mixed_effects"] = _run_mixed_effects(valid)

    return results


def _classify_pre_session_state(classified_df: pd.DataFrame, bio_row: pd.Series) -> str:
    """Majority-vote activity state in the 30 minutes before session start."""
    if classified_df.empty or "activity_state" not in classified_df.columns:
        return "Rest"

    try:
        start_local = pd.Timestamp(f"{bio_row['date']} {bio_row['start_local']}")
        start_utc = local_to_utc(start_local)
        window_start = start_utc - pd.Timedelta(minutes=_PRE_WINDOW_MIN)
        return classify_window_state(classified_df, window_start, start_utc)
    except (KeyError, TypeError, ValueError):
        return "Rest"


def _fit_session_recovery(
    traces: pd.DataFrame,
    signal: str,
    expected_curve: Optional[RecoveryCurve],
) -> tuple[Optional[float], Optional[float], int]:
    """Fit an exponential recovery curve to the during+post session trace.

    Returns (tau, r_squared, n_valid_points).
    """
    if signal not in traces.columns:
        return None, None, 0

    # Use 'during' and 'post' phases as the recovery window
    recovery = traces[traces["phase"].isin(["during", "post"])][signal].dropna()
    n_points = int(len(recovery))

    if n_points < _MIN_FIT_POINTS:
        return None, None, n_points

    # Determine asymptote: use expected curve's asymptote if available, else median of post phase
    if expected_curve is not None:
        asymptote = expected_curve.asymptote
    else:
        post = traces[traces["phase"] == "post"][signal].dropna()
        asymptote = float(post.median()) if len(post) >= 3 else float(recovery.median())

    t = np.arange(len(recovery), dtype=float)
    y = recovery.values.astype(float)

    result = _fit_exp_decay(t, y, asymptote)
    if result is None:
        return None, None, n_points

    tau, r2 = result
    return float(tau), float(r2), n_points


def _run_mixed_effects(df: pd.DataFrame) -> dict:
    """Fit a linear mixed-effects model: advantage ~ playlist + pre_state + (1|participant)."""
    try:
        import statsmodels.formula.api as smf

        data = df[["advantage", "playlist", "pre_state", "participant"]].dropna()
        if len(data) < 10 or data["participant"].nunique() < 2:
            return {"error": "Insufficient data for mixed-effects model"}

        formula = "advantage ~ C(playlist) + C(pre_state)"
        model = smf.mixedlm(formula, data, groups=data["participant"])
        result = model.fit(reml=True, method="lbfgs")

        return {
            "converged":   bool(result.converged),
            "log_lik":     round(float(result.llf), 3),
            "aic":         round(float(result.aic), 3),
            "coefficients": {
                k: {"coef": round(float(v), 3), "p_value": round(float(result.pvalues[k]), 4)}
                for k, v in result.params.items()
            },
        }
    except ImportError:
        return {"error": "statsmodels not installed"}
    except Exception as e:
        return {"error": str(e)}


def load_participant_data(codename: str, data_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load session_traces_all.csv and session_biometrics.csv for a participant."""
    processed = data_root / "wearables" / codename / "processed"
    traces_path = processed / "session_traces_all.csv"
    bio_path = processed / "session_biometrics.csv"

    traces = pd.read_csv(traces_path, index_col="timestamp_utc", parse_dates=True) if traces_path.exists() else pd.DataFrame()
    biometrics = pd.read_csv(bio_path) if bio_path.exists() else pd.DataFrame()

    return traces, biometrics
