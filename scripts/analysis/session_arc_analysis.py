"""
session_arc_analysis.py — Full session arc significance analysis with long-term effects.

For each session, compares physiological metrics (stress, HR, body battery)
across three windows (pre/during/post) against each participant's personal
circadian baseline. Classifies activity state per window and runs thesis-grade
significance tests with long-term trend analysis.

Prerequisites:
    - Run pipeline.py first to generate classified_minutes.csv per participant
    - Wearable data must be processed (garmin_pipeline.py / huawei_pipeline.py)

Outputs:
    data/analysis/session_arc/arc_deviations.csv
    data/analysis/session_arc/significance_results.csv
    data/analysis/session_arc/long_term_trends.csv
    data/analysis/session_arc/plots/*.png

Usage:
    python scripts/analysis/session_arc_analysis.py
    python scripts/analysis/session_arc_analysis.py --participants bosbes peer
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

sys.path.insert(0, str(Path(__file__).parent))

from circadian_baseline import MIN_OBS_PER_HOUR, _load_daily_hrv

# ── Configuration ───────────────────────────────────────────────────────────

PARTICIPANTS = ["bosbes", "kokosnoot", "limoen", "peer"]

DATA_ROOT = Path(__file__).resolve().parent.parent.parent / "data"
WEARABLES_DIR = DATA_ROOT / "wearables"
ANALYSIS_DIR = DATA_ROOT / "analysis"
OUTPUT_DIR = ANALYSIS_DIR / "session_arc"

# Signals in priority order — stress is mandatory, rest are optional
SIGNALS = ["stress", "heart_rate", "body_battery"]

# Rolling baseline window (non-session days before each session)
ROLLING_DAYS = 14


# ═══════════════════════════════════════════════════════════════════════════
#  1. DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════

def _load_minute_signal(proc_dir: Path, signal: str) -> pd.DataFrame | None:
    """Load minute-level data for a given signal.

    Returns DataFrame indexed by timestamp with one signal column, or None.
    """
    if signal == "stress":
        candidates = ["garmin_minute_stress.csv", "huawei_minute_stress.csv"]
    elif signal == "heart_rate":
        candidates = ["garmin_minute_hr.csv", "huawei_minute_hr.csv"]
    elif signal == "body_battery":
        # BB lives inside the Garmin stress file; Huawei doesn't have it
        candidates = ["garmin_minute_stress.csv"]
    else:
        return None

    for fname in candidates:
        path = proc_dir / fname
        if not path.exists():
            continue
        df = pd.read_csv(path, parse_dates=["timestamp"], index_col="timestamp")
        if signal in df.columns:
            return df[[signal]].dropna(subset=[signal])
    return None


def _load_classified_minutes(participant: str) -> pd.DataFrame:
    """Load classified_minutes.csv produced by pipeline.py."""
    path = ANALYSIS_DIR / participant / "classified_minutes.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"classified_minutes.csv not found for {participant}. "
            "Run: python scripts/analysis/pipeline.py --participants " + participant
        )
    return pd.read_csv(path, index_col="timestamp", parse_dates=True)


# ═══════════════════════════════════════════════════════════════════════════
#  2. CIRCADIAN BASELINES (generalised to any signal)
# ═══════════════════════════════════════════════════════════════════════════

def compute_signal_baseline(
    participant: str, signal: str,
) -> pd.DataFrame | None:
    """Compute hourly circadian baseline for *signal* from non-session days.

    Returns DataFrame with columns: hour, mean_{signal}, std_{signal}, n_observations.
    Returns None if the signal data is not available for this participant.
    """
    proc_dir = WEARABLES_DIR / participant / "processed"

    signal_df = _load_minute_signal(proc_dir, signal)
    if signal_df is None or signal_df.empty:
        return None

    bio_path = proc_dir / "session_biometrics.csv"
    if not bio_path.exists():
        return None
    sessions = pd.read_csv(bio_path)
    session_dates = set(pd.to_datetime(sessions["date"]).dt.date)

    signal_df = signal_df.copy()
    signal_df["_date"] = signal_df.index.date
    non_session = signal_df[~signal_df["_date"].isin(session_dates)]

    if non_session.empty:
        return None

    non_session = non_session.copy()
    non_session["hour"] = non_session.index.hour
    baseline = (
        non_session.groupby("hour")[signal]
        .agg(**{
            f"mean_{signal}": "mean",
            f"std_{signal}": "std",
            "n_observations": "count",
        })
        .reset_index()
    )

    sparse = baseline["n_observations"] < MIN_OBS_PER_HOUR
    baseline.loc[sparse, [f"mean_{signal}", f"std_{signal}"]] = np.nan
    return baseline


def compute_rolling_baseline(
    participant: str,
    signal: str,
    session_date: pd.Timestamp,
    n_days: int = ROLLING_DAYS,
) -> pd.DataFrame | None:
    """Compute a rolling circadian baseline using the last *n_days* non-session
    days before *session_date*.

    Falls back to the global baseline when fewer than *n_days* are available.
    """
    proc_dir = WEARABLES_DIR / participant / "processed"
    signal_df = _load_minute_signal(proc_dir, signal)
    if signal_df is None or signal_df.empty:
        return None

    bio_path = proc_dir / "session_biometrics.csv"
    if not bio_path.exists():
        return None
    sessions = pd.read_csv(bio_path)
    session_dates = set(pd.to_datetime(sessions["date"]).dt.date)

    target = session_date.date() if hasattr(session_date, "date") else session_date

    signal_df = signal_df.copy()
    signal_df["_date"] = signal_df.index.date
    non_session_before = signal_df[
        (~signal_df["_date"].isin(session_dates)) & (signal_df["_date"] < target)
    ]

    available_days = sorted(non_session_before["_date"].unique())
    if len(available_days) < n_days:
        # Fall back to global baseline
        return compute_signal_baseline(participant, signal)

    rolling_days = set(available_days[-n_days:])
    rolling_data = non_session_before[non_session_before["_date"].isin(rolling_days)].copy()
    rolling_data["hour"] = rolling_data.index.hour

    baseline = (
        rolling_data.groupby("hour")[signal]
        .agg(**{
            f"mean_{signal}": "mean",
            f"std_{signal}": "std",
            "n_observations": "count",
        })
        .reset_index()
    )
    sparse = baseline["n_observations"] < MIN_OBS_PER_HOUR
    baseline.loc[sparse, [f"mean_{signal}", f"std_{signal}"]] = np.nan
    return baseline


# ═══════════════════════════════════════════════════════════════════════════
#  3. ACTIVITY STATE CLASSIFICATION PER WINDOW
# ═══════════════════════════════════════════════════════════════════════════

def classify_window_state(
    classified_df: pd.DataFrame,
    start_utc: pd.Timestamp,
    end_utc: pd.Timestamp,
) -> str:
    """Majority-vote activity state in the [start_utc, end_utc] window."""
    if classified_df.empty or "activity_state" not in classified_df.columns:
        return "Rest"
    try:
        window = classified_df.loc[start_utc:end_utc, "activity_state"].dropna()
        if window.empty:
            return "Rest"
        return str(window.mode().iloc[0])
    except (KeyError, IndexError):
        return "Rest"


# ═══════════════════════════════════════════════════════════════════════════
#  4. BUILD ARC DEVIATIONS TABLE
# ═══════════════════════════════════════════════════════════════════════════

def build_arc_deviations(participants: list[str] | None = None) -> pd.DataFrame:
    """Build one-row-per-session table with deviations for all windows and signals.

    For stress and heart_rate: deviation = window_mean - expected_at_hour.
    For body_battery: absolute bb_delta (post - pre); no hourly deviation.
    """
    participants = participants or PARTICIPANTS
    rows: list[dict] = []

    for participant in participants:
        proc_dir = WEARABLES_DIR / participant / "processed"
        traces_path = proc_dir / "session_traces_all.csv"
        bio_path = proc_dir / "session_biometrics.csv"

        if not traces_path.exists() or not bio_path.exists():
            print(f"  [{participant}] Missing traces or biometrics — skipping")
            continue

        traces = pd.read_csv(traces_path, parse_dates=["timestamp_utc"])
        biometrics = pd.read_csv(bio_path)

        # classified_minutes.csv from pipeline.py
        try:
            classified_df = _load_classified_minutes(participant)
        except FileNotFoundError as exc:
            print(f"  [{participant}] {exc}")
            continue

        # Global baselines per available signal
        baselines: dict[str, pd.DataFrame] = {}
        for signal in SIGNALS:
            bl = compute_signal_baseline(participant, signal)
            if bl is not None:
                baselines[signal] = bl.set_index("hour")

        if "stress" not in baselines:
            print(f"  [{participant}] No stress baseline available — skipping")
            continue

        # Daily HRV lookup (optional — only some Garmin participants)
        hrv_lookup = _load_daily_hrv(WEARABLES_DIR / participant / "raw")

        # Sort sessions chronologically for session numbering
        biometrics["date"] = pd.to_datetime(biometrics["date"])
        biometrics = biometrics.sort_values("date").reset_index(drop=True)

        for session_num, (_, bio_row) in enumerate(biometrics.iterrows(), 1):
            session_date_str = str(bio_row["date"].date())
            session_traces = traces[traces["session_date"] == session_date_str]
            if session_traces.empty:
                continue

            # Parse session timing (biometrics stores CET; traces are UTC)
            start_local = pd.Timestamp(f"{bio_row['date'].date()} {bio_row['start_local']}")
            end_local = pd.Timestamp(f"{bio_row['date'].date()} {bio_row['end_local']}")
            start_utc = start_local - pd.Timedelta(hours=1)
            end_utc = end_local - pd.Timedelta(hours=1)

            # Slice phases from traces (already labelled)
            pre_traces = session_traces[session_traces["phase"] == "pre"]
            during_traces = session_traces[session_traces["phase"] == "during"]
            post_traces = session_traces[session_traces["phase"] == "post"]

            # Classify activity state per window (using full continuous classified_df)
            pre_state = classify_window_state(
                classified_df,
                start_utc - pd.Timedelta(minutes=30),
                start_utc,
            )
            during_state = classify_window_state(classified_df, start_utc, end_utc)
            post_state = classify_window_state(
                classified_df,
                end_utc,
                end_utc + pd.Timedelta(minutes=30),
            )

            # Hours for baseline lookup (UTC)
            pre_hour = start_utc.hour
            if not during_traces.empty:
                during_ts = pd.to_datetime(during_traces["timestamp_utc"])
                during_hour = int(during_ts.dt.hour.median())
            else:
                during_hour = start_utc.hour
            post_hour = end_utc.hour

            row: dict = {
                "participant": participant,
                "date": bio_row["date"].date(),
                "session_number": session_num,
                "playlist": bio_row["playlist"],
                "pre_state": pre_state,
                "during_state": during_state,
                "post_state": post_state,
                "hour_pre": pre_hour,
                "hour_during": during_hour,
                "hour_post": post_hour,
            }

            # ── Deviations per signal ───────────────────────────────────────
            for signal in SIGNALS:
                if signal == "body_battery":
                    # BB: absolute delta only (no circadian deviation)
                    bb_col = "body_battery"
                    bb_pre = (
                        float(pre_traces[bb_col].mean())
                        if bb_col in pre_traces.columns and not pre_traces[bb_col].dropna().empty
                        else np.nan
                    )
                    bb_post = (
                        float(post_traces[bb_col].mean())
                        if bb_col in post_traces.columns and not post_traces[bb_col].dropna().empty
                        else np.nan
                    )
                    row["bb_mean_pre"] = bb_pre
                    row["bb_mean_post"] = bb_post
                    row["bb_delta"] = (
                        bb_post - bb_pre
                        if pd.notna(bb_pre) and pd.notna(bb_post)
                        else np.nan
                    )
                    continue

                if signal not in baselines:
                    for w in ("pre", "during", "post"):
                        row[f"{signal}_dev_{w}"] = np.nan
                        row[f"{signal}_mean_{w}"] = np.nan
                        row[f"{signal}_expected_{w}"] = np.nan
                    continue

                bl = baselines[signal]
                mean_col = f"mean_{signal}"

                for w_name, w_traces, w_hour in [
                    ("pre", pre_traces, pre_hour),
                    ("during", during_traces, during_hour),
                    ("post", post_traces, post_hour),
                ]:
                    actual = (
                        float(w_traces[signal].dropna().mean())
                        if signal in w_traces.columns and not w_traces[signal].dropna().empty
                        else np.nan
                    )
                    expected = (
                        float(bl.at[w_hour, mean_col])
                        if w_hour in bl.index and pd.notna(bl.at[w_hour, mean_col])
                        else np.nan
                    )
                    deviation = (
                        actual - expected
                        if pd.notna(actual) and pd.notna(expected)
                        else np.nan
                    )

                    row[f"{signal}_dev_{w_name}"] = deviation
                    row[f"{signal}_mean_{w_name}"] = actual
                    row[f"{signal}_expected_{w_name}"] = expected

            # ── Mood ────────────────────────────────────────────────────────
            mood_before = bio_row.get("mood_before_score")
            mood_after = bio_row.get("mood_after_score")
            row["mood_before"] = mood_before
            row["mood_after"] = mood_after
            if pd.notna(mood_before) and pd.notna(mood_after):
                row["mood_delta"] = float(mood_after) - float(mood_before)
            else:
                row["mood_delta"] = np.nan

            # ── HRV daily covariate (optional) ─────────────────────────────
            row["hrv_rmssd"] = hrv_lookup.get(session_date_str, np.nan)

            # ── Rolling baseline stress deviation (for long-term tracking) ─
            rolling_bl = compute_rolling_baseline(
                participant, "stress", bio_row["date"]
            )
            if rolling_bl is not None:
                rl = rolling_bl.set_index("hour")
                rolling_exp = (
                    float(rl.at[pre_hour, "mean_stress"])
                    if pre_hour in rl.index and pd.notna(rl.at[pre_hour, "mean_stress"])
                    else np.nan
                )
                pre_actual = row.get("stress_mean_pre", np.nan)
                row["rolling_baseline_stress_pre"] = rolling_exp
                row["rolling_stress_dev_pre"] = (
                    pre_actual - rolling_exp
                    if pd.notna(pre_actual) and pd.notna(rolling_exp)
                    else np.nan
                )
            else:
                row["rolling_baseline_stress_pre"] = np.nan
                row["rolling_stress_dev_pre"] = np.nan

            # ── N days available for rolling baseline ───────────────────────
            row["rolling_n_days"] = _count_rolling_days(participant, bio_row["date"])

            rows.append(row)

    return pd.DataFrame(rows)


def _count_rolling_days(participant: str, session_date: pd.Timestamp) -> int:
    """Count how many non-session days are available before this session."""
    proc_dir = WEARABLES_DIR / participant / "processed"
    signal_df = _load_minute_signal(proc_dir, "stress")
    if signal_df is None:
        return 0

    bio_path = proc_dir / "session_biometrics.csv"
    if not bio_path.exists():
        return 0
    sessions = pd.read_csv(bio_path)
    session_dates = set(pd.to_datetime(sessions["date"]).dt.date)
    target = session_date.date() if hasattr(session_date, "date") else session_date

    signal_df = signal_df.copy()
    signal_df["_date"] = signal_df.index.date
    non_session_before = signal_df[
        (~signal_df["_date"].isin(session_dates)) & (signal_df["_date"] < target)
    ]
    return len(non_session_before["_date"].unique())


# ═══════════════════════════════════════════════════════════════════════════
#  5. SIGNIFICANCE TESTS (thesis-grade)
# ═══════════════════════════════════════════════════════════════════════════

def _bootstrap_ci(values: np.ndarray, n_boot: int = 1000, alpha: float = 0.05):
    """Bootstrap 95 % confidence interval (BCa when scipy supports it)."""
    if len(values) < 3:
        return np.nan, np.nan
    try:
        res = sp_stats.bootstrap(
            (values,), np.mean, n_resamples=n_boot,
            confidence_level=1 - alpha, method="BCa",
        )
        return float(res.confidence_interval.low), float(res.confidence_interval.high)
    except Exception:
        rng = np.random.default_rng(42)
        means = [
            np.mean(rng.choice(values, len(values), replace=True))
            for _ in range(n_boot)
        ]
        lo = float(np.percentile(means, 100 * alpha / 2))
        hi = float(np.percentile(means, 100 * (1 - alpha / 2)))
        return lo, hi


def _cohens_d(values: np.ndarray) -> float:
    return float(values.mean() / values.std()) if values.std() > 0 else 0.0


def _one_sample_row(values: pd.Series, metric: str, window: str, group: str) -> dict:
    """One-sample t-test vs 0 with all thesis-grade metrics."""
    v = values.dropna().values
    if len(v) < 3:
        return {}

    t, p = sp_stats.ttest_1samp(v, 0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        sw_stat, sw_p = sp_stats.shapiro(v)
    ci_lo, ci_hi = _bootstrap_ci(v)

    return {
        "test_name": "one_sample_ttest",
        "metric": metric,
        "window": window,
        "group": group,
        "n": len(v),
        "mean": float(v.mean()),
        "std": float(v.std()),
        "ci_low": ci_lo,
        "ci_high": ci_hi,
        "statistic": float(t),
        "p_value": float(p),
        "effect_size": abs(_cohens_d(v)),
        "effect_size_type": "cohens_d",
        "normality_ok": bool(sw_p >= 0.05),
        "equal_variance_ok": None,
    }


def _paired_row(pre: pd.Series, post: pd.Series, metric: str) -> dict:
    """Paired t-test (pre vs post) with effect size."""
    paired = pd.DataFrame({"pre": pre, "post": post}).dropna()
    if len(paired) < 3:
        return {}

    diff = paired["post"] - paired["pre"]
    t, p = sp_stats.ttest_rel(paired["pre"], paired["post"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        sw_stat, sw_p = sp_stats.shapiro(diff.values)
    ci_lo, ci_hi = _bootstrap_ci(diff.values)

    return {
        "test_name": "paired_ttest_pre_vs_post",
        "metric": metric,
        "window": "pre_vs_post",
        "group": "all",
        "n": len(paired),
        "mean": float(diff.mean()),
        "std": float(diff.std()),
        "ci_low": ci_lo,
        "ci_high": ci_hi,
        "statistic": float(t),
        "p_value": float(p),
        "effect_size": abs(_cohens_d(diff.values)),
        "effect_size_type": "cohens_d",
        "normality_ok": bool(sw_p >= 0.05),
        "equal_variance_ok": None,
    }


def _anova_rows(
    df: pd.DataFrame, value_col: str, group_col: str, metric: str, window: str,
) -> list[dict]:
    """One-way ANOVA + Tukey HSD + Levene's test."""
    subset = df[[value_col, group_col]].dropna()

    groups: dict[str, pd.Series] = {}
    for name, grp in subset.groupby(group_col):
        vals = grp[value_col].dropna()
        if len(vals) >= 2:
            groups[name] = vals

    if len(groups) < 2:
        return []

    gv = list(groups.values())
    gn = list(groups.keys())
    results: list[dict] = []

    f_stat, p_val = sp_stats.f_oneway(*gv)
    lev_stat, lev_p = sp_stats.levene(*gv)

    # η² = SS_between / SS_total
    all_vals = pd.concat(gv)
    grand_mean = all_vals.mean()
    ss_between = sum(len(g) * (g.mean() - grand_mean) ** 2 for g in gv)
    ss_total = float(((all_vals - grand_mean) ** 2).sum())
    eta_sq = ss_between / ss_total if ss_total > 0 else 0.0

    results.append({
        "test_name": f"anova_by_{group_col}",
        "metric": metric,
        "window": window,
        "group": f"{group_col}: {', '.join(str(g) for g in gn)}",
        "n": len(all_vals),
        "mean": float(all_vals.mean()),
        "std": float(all_vals.std()),
        "ci_low": None,
        "ci_high": None,
        "statistic": float(f_stat),
        "p_value": float(p_val),
        "effect_size": float(eta_sq),
        "effect_size_type": "eta_squared",
        "normality_ok": None,
        "equal_variance_ok": bool(lev_p >= 0.05),
    })

    # Tukey HSD pairwise
    try:
        from statsmodels.stats.multicomp import pairwise_tukeyhsd

        combined = pd.DataFrame({
            "value": pd.concat(gv).values,
            "group": sum([[n] * len(v) for n, v in groups.items()], []),
        })
        tukey = pairwise_tukeyhsd(combined["value"], combined["group"])
        for row in tukey.summary().data[1:]:
            results.append({
                "test_name": f"tukey_{group_col}",
                "metric": metric,
                "window": window,
                "group": f"{row[0]} vs {row[1]}",
                "n": len(all_vals),
                "mean": float(row[2]),
                "std": None,
                "ci_low": float(row[4]),
                "ci_high": float(row[5]),
                "statistic": None,
                "p_value": float(row[3]),
                "effect_size": None,
                "effect_size_type": None,
                "normality_ok": None,
                "equal_variance_ok": None,
            })
    except Exception:
        pass

    return results


def run_significance_tests(arc_df: pd.DataFrame) -> pd.DataFrame:
    """Run all thesis-grade significance tests on the arc deviations table.

    Tests:
        A. One-sample t-test per metric per window (deviation ≠ 0)
        B. Paired t-test (pre vs post) per metric
        C. One-way ANOVA by playlist type
        D. One-way ANOVA by pre_state
        + FDR correction (Benjamini–Hochberg) across all raw p-values
    """
    from statsmodels.stats.multitest import multipletests

    results: list[dict] = []

    # Deviation columns for stress and heart_rate
    dev_cols = {
        "stress": ["stress_dev_pre", "stress_dev_during", "stress_dev_post"],
        "heart_rate": ["heart_rate_dev_pre", "heart_rate_dev_during", "heart_rate_dev_post"],
    }

    # A — one-sample t-tests (deviation ≠ 0)
    for metric, cols in dev_cols.items():
        for col in cols:
            window = col.rsplit("_", 1)[-1]  # pre / during / post
            if col not in arc_df.columns:
                continue
            row = _one_sample_row(arc_df[col], metric, window, "all")
            if row:
                results.append(row)

    # mood_delta one-sample
    if "mood_delta" in arc_df.columns:
        row = _one_sample_row(arc_df["mood_delta"], "mood_delta", "overall", "all")
        if row:
            results.append(row)

    # bb_delta one-sample
    if "bb_delta" in arc_df.columns:
        row = _one_sample_row(arc_df["bb_delta"], "body_battery", "delta", "all")
        if row:
            results.append(row)

    # B — paired t-tests (pre vs post)
    for metric in ("stress", "heart_rate"):
        pre_col = f"{metric}_dev_pre"
        post_col = f"{metric}_dev_post"
        if pre_col in arc_df.columns and post_col in arc_df.columns:
            row = _paired_row(arc_df[pre_col], arc_df[post_col], metric)
            if row:
                results.append(row)

    # C — ANOVA by playlist
    for metric in ("stress", "heart_rate"):
        for window in ("pre", "during", "post"):
            col = f"{metric}_dev_{window}"
            if col in arc_df.columns:
                results.extend(_anova_rows(arc_df, col, "playlist", metric, window))

    if "mood_delta" in arc_df.columns:
        results.extend(_anova_rows(arc_df, "mood_delta", "playlist", "mood_delta", "overall"))
    if "bb_delta" in arc_df.columns:
        results.extend(_anova_rows(arc_df, "bb_delta", "playlist", "body_battery", "delta"))

    # D — ANOVA by pre_state
    for metric in ("stress", "heart_rate"):
        for window in ("pre", "during", "post"):
            col = f"{metric}_dev_{window}"
            if col in arc_df.columns:
                results.extend(_anova_rows(arc_df, col, "pre_state", metric, window))

    if "mood_delta" in arc_df.columns:
        results.extend(_anova_rows(arc_df, "mood_delta", "pre_state", "mood_delta", "overall"))

    if not results:
        return pd.DataFrame()

    results_df = pd.DataFrame(results)

    # FDR correction (Benjamini–Hochberg)
    p_vals = results_df["p_value"].values
    if len(p_vals) > 1:
        _, q_vals, _, _ = multipletests(p_vals, method="fdr_bh")
        results_df["q_value"] = q_vals
    else:
        results_df["q_value"] = results_df["p_value"]

    return results_df


# ═══════════════════════════════════════════════════════════════════════════
#  6. LONG-TERM EFFECTS
# ═══════════════════════════════════════════════════════════════════════════

def compute_long_term_trends(arc_df: pd.DataFrame) -> pd.DataFrame:
    """Compute session-order trends, rolling-baseline drift, and cumulative exposure."""
    results: list[dict] = []

    outcome_cols = [
        ("stress_dev_post", "stress_dev_post"),
        ("mood_delta", "mood_delta"),
    ]

    # A — session-order linear trend per participant
    for participant in arc_df["participant"].unique():
        pdata = arc_df[arc_df["participant"] == participant].sort_values("session_number")

        for col, name in outcome_cols:
            if col not in pdata.columns:
                continue
            valid = pdata[["session_number", col]].dropna()
            if len(valid) < 3:
                continue

            slope, intercept, r, p, _ = sp_stats.linregress(
                valid["session_number"], valid[col],
            )
            results.append({
                "participant": participant,
                "analysis": "session_order_trend",
                "metric": name,
                "slope": float(slope),
                "intercept": float(intercept),
                "r_squared": float(r ** 2),
                "p_value": float(p),
                "n": len(valid),
            })

    # Pooled session-order trend
    for col, name in outcome_cols:
        if col not in arc_df.columns:
            continue
        valid = arc_df[["session_number", col]].dropna()
        if len(valid) < 3:
            continue
        slope, intercept, r, p, _ = sp_stats.linregress(
            valid["session_number"], valid[col],
        )
        results.append({
            "participant": "pooled",
            "analysis": "session_order_trend",
            "metric": name,
            "slope": float(slope),
            "intercept": float(intercept),
            "r_squared": float(r ** 2),
            "p_value": float(p),
            "n": len(valid),
        })

    # B — rolling-baseline drift per participant
    for participant in arc_df["participant"].unique():
        pdata = arc_df[arc_df["participant"] == participant].sort_values("date")
        if "rolling_baseline_stress_pre" not in pdata.columns:
            continue
        valid = pdata[["session_number", "rolling_baseline_stress_pre"]].dropna()
        if len(valid) < 3:
            continue
        slope, intercept, r, p, _ = sp_stats.linregress(
            valid["session_number"], valid["rolling_baseline_stress_pre"],
        )
        results.append({
            "participant": participant,
            "analysis": "rolling_baseline_drift",
            "metric": "stress_baseline",
            "slope": float(slope),
            "intercept": float(intercept),
            "r_squared": float(r ** 2),
            "p_value": float(p),
            "n": len(valid),
        })

    # C — cumulative exposure (Spearman rank correlation)
    arc_sorted = arc_df.sort_values(["participant", "date"]).copy()
    arc_sorted["cumulative_sessions"] = arc_sorted.groupby("participant").cumcount() + 1

    for col, name in outcome_cols:
        if col not in arc_sorted.columns:
            continue
        valid = arc_sorted[["cumulative_sessions", col]].dropna()
        if len(valid) < 3:
            continue
        rho, p = sp_stats.spearmanr(valid["cumulative_sessions"], valid[col])
        results.append({
            "participant": "pooled",
            "analysis": "cumulative_exposure",
            "metric": name,
            "slope": float(rho),       # Spearman ρ stored in slope column
            "intercept": None,
            "r_squared": float(rho ** 2),
            "p_value": float(p),
            "n": len(valid),
        })

    # D — HRV daily trend (optional, per participant)
    hrv_data = arc_df[["session_number", "hrv_rmssd", "participant"]].dropna()
    for participant in hrv_data["participant"].unique():
        pdata = hrv_data[hrv_data["participant"] == participant].sort_values("session_number")
        if len(pdata) < 3:
            continue
        slope, intercept, r, p, _ = sp_stats.linregress(
            pdata["session_number"], pdata["hrv_rmssd"],
        )
        results.append({
            "participant": participant,
            "analysis": "hrv_daily_trend",
            "metric": "hrv_rmssd",
            "slope": float(slope),
            "intercept": float(intercept),
            "r_squared": float(r ** 2),
            "p_value": float(p),
            "n": len(pdata),
        })

    return pd.DataFrame(results)


# ═══════════════════════════════════════════════════════════════════════════
#  7. PLOTTING
# ═══════════════════════════════════════════════════════════════════════════

def _ensure_agg_backend():
    import matplotlib
    matplotlib.use("Agg")


def plot_arc_per_participant(arc_df: pd.DataFrame, output_dir: Path) -> None:
    """Grouped bar chart of arc deviations per participant per signal."""
    _ensure_agg_backend()
    import matplotlib.pyplot as plt

    participants = arc_df["participant"].unique()
    signals = ["stress", "heart_rate"]
    windows = ["pre", "during", "post"]

    fig, axes = plt.subplots(
        len(participants), len(signals),
        figsize=(12, 4 * len(participants)),
        squeeze=False,
    )

    for i, participant in enumerate(participants):
        pdata = arc_df[arc_df["participant"] == participant]
        for j, signal in enumerate(signals):
            ax = axes[i, j]
            means, errs = [], []
            for w in windows:
                col = f"{signal}_dev_{w}"
                if col not in pdata.columns:
                    means.append(0)
                    errs.append((0, 0))
                    continue
                vals = pdata[col].dropna()
                m = float(vals.mean()) if len(vals) > 0 else 0.0
                means.append(m)
                if len(vals) >= 3:
                    lo, hi = _bootstrap_ci(vals.values)
                    errs.append((m - lo, hi - m))
                else:
                    errs.append((0, 0))

            colors = ["#d32f2f" if m > 0 else "#1976d2" for m in means]
            yerr = np.array(errs).T
            ax.bar(windows, means, color=colors, yerr=yerr, capsize=5, alpha=0.8)
            ax.axhline(0, color="black", linewidth=0.5, linestyle="--")
            ax.set_title(f"{participant} — {signal}")
            ax.set_ylabel("Deviation from baseline")

    plt.tight_layout()
    fig.savefig(output_dir / "arc_per_participant.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_deviation_heatmap(arc_df: pd.DataFrame, output_dir: Path) -> None:
    """Session × window deviation heatmap (diverging red–blue)."""
    _ensure_agg_backend()
    import matplotlib.pyplot as plt

    cols = [
        c for c in [
            "stress_dev_pre", "stress_dev_during", "stress_dev_post",
            "heart_rate_dev_pre", "heart_rate_dev_during", "heart_rate_dev_post",
        ]
        if c in arc_df.columns
    ]
    if not cols:
        return

    plot_df = arc_df.sort_values(["participant", "date"]).reset_index(drop=True)
    labels = plot_df.apply(lambda r: f"{r['participant'][:4]} {r['date']}", axis=1)

    data = plot_df[cols].values.astype(float)
    vmax = max(abs(np.nanmin(data)), abs(np.nanmax(data)), 1)

    fig, ax = plt.subplots(figsize=(10, max(6, len(plot_df) * 0.4)))
    im = ax.imshow(data, aspect="auto", cmap="RdBu_r", vmin=-vmax, vmax=vmax)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels([c.replace("_dev_", "\n") for c in cols], fontsize=9)
    plt.colorbar(im, label="Deviation from baseline")
    ax.set_title("Session × Window Deviation Heatmap")

    plt.tight_layout()
    fig.savefig(output_dir / "deviation_heatmap.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_long_term_trends(arc_df: pd.DataFrame, output_dir: Path) -> None:
    """Session-order scatter with per-participant + pooled regression lines."""
    _ensure_agg_backend()
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    for ax, (col, label) in zip(axes, [
        ("stress_dev_post", "Post-session Stress Deviation"),
        ("mood_delta", "Mood Delta"),
    ]):
        if col not in arc_df.columns:
            continue

        for participant in arc_df["participant"].unique():
            pdata = arc_df[arc_df["participant"] == participant].sort_values("session_number")
            valid = pdata[["session_number", col]].dropna()
            if valid.empty:
                continue
            ax.scatter(valid["session_number"], valid[col], label=participant, alpha=0.7, s=40)
            if len(valid) >= 3:
                slope, intercept, *_ = sp_stats.linregress(
                    valid["session_number"], valid[col],
                )
                x_line = np.array([valid["session_number"].min(), valid["session_number"].max()])
                ax.plot(x_line, slope * x_line + intercept, "--", alpha=0.5)

        # Pooled trend
        valid_all = arc_df[["session_number", col]].dropna()
        if len(valid_all) >= 3:
            slope, intercept, _, p, _ = sp_stats.linregress(
                valid_all["session_number"], valid_all[col],
            )
            x_line = np.array([valid_all["session_number"].min(), valid_all["session_number"].max()])
            ax.plot(
                x_line, slope * x_line + intercept, "k-",
                linewidth=2, label=f"pooled (p={p:.3f})",
            )

        ax.axhline(0, color="gray", linewidth=0.5, linestyle="--")
        ax.set_xlabel("Session Number")
        ax.set_ylabel(label)
        ax.set_title(label)
        ax.legend(fontsize=8)

    plt.tight_layout()
    fig.savefig(output_dir / "long_term_trends.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_rolling_baseline(arc_df: pd.DataFrame, output_dir: Path) -> None:
    """Rolling 14-day baseline stress over time per participant."""
    _ensure_agg_backend()
    import matplotlib.pyplot as plt

    if "rolling_baseline_stress_pre" not in arc_df.columns:
        return

    fig, ax = plt.subplots(figsize=(10, 5))
    for participant in arc_df["participant"].unique():
        pdata = arc_df[arc_df["participant"] == participant].sort_values("date")
        valid = pdata[["date", "rolling_baseline_stress_pre"]].dropna()
        if valid.empty:
            continue
        ax.plot(
            pd.to_datetime(valid["date"]),
            valid["rolling_baseline_stress_pre"],
            "o-", label=participant, alpha=0.7,
        )

    ax.set_xlabel("Date")
    ax.set_ylabel("Rolling 14-day Baseline Stress")
    ax.set_title("Rolling Baseline Drift Over Study Period")
    ax.legend()
    fig.autofmt_xdate()

    plt.tight_layout()
    fig.savefig(output_dir / "rolling_baseline.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_significance_summary(sig_df: pd.DataFrame, output_dir: Path) -> None:
    """Horizontal bar chart of -log10(q) per test, color-coded by significance."""
    _ensure_agg_backend()
    import matplotlib.pyplot as plt

    if sig_df.empty:
        return

    main = sig_df[~sig_df["test_name"].str.contains("tukey")].copy()
    if main.empty:
        return

    colors = []
    for q in main["q_value"]:
        if q < 0.05:
            colors.append("#4caf50")
        elif q < 0.1:
            colors.append("#ff9800")
        else:
            colors.append("#f44336")

    labels = main.apply(
        lambda r: f"{r['test_name']}: {r['metric']} ({r['window']})", axis=1,
    )

    fig, ax = plt.subplots(figsize=(12, max(4, len(main) * 0.5)))
    y_pos = range(len(main))
    ax.barh(y_pos, -np.log10(main["q_value"].clip(1e-10)), color=colors, alpha=0.8)
    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(labels, fontsize=8)
    ax.axvline(-np.log10(0.05), color="red", linestyle="--", label="q = 0.05")
    ax.axvline(-np.log10(0.1), color="orange", linestyle="--", label="q = 0.10")
    ax.set_xlabel("-log10(q-value)")
    ax.set_title("Significance Summary (FDR-corrected)")
    ax.legend()

    plt.tight_layout()
    fig.savefig(output_dir / "significance_summary.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════════════════
#  8. MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Session arc significance analysis for Project R.E.M."
    )
    parser.add_argument(
        "--participants", nargs="+", default=PARTICIPANTS,
        help="Participant codenames (default: %(default)s)",
    )
    args = parser.parse_args()

    plot_dir = OUTPUT_DIR / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    # Step 1 — build arc deviations
    print("Building arc deviations...")
    arc_df = build_arc_deviations(args.participants)
    if arc_df.empty:
        print("  No data produced — check that pipeline.py has been run.")
        return
    arc_df.to_csv(OUTPUT_DIR / "arc_deviations.csv", index=False)
    print(f"  {len(arc_df)} sessions x {len(arc_df.columns)} columns")

    # Step 2 — significance tests
    print("\nRunning significance tests...")
    sig_df = run_significance_tests(arc_df)
    sig_df.to_csv(OUTPUT_DIR / "significance_results.csv", index=False)
    n_sig = int((sig_df["q_value"] < 0.05).sum()) if not sig_df.empty else 0
    print(f"  {len(sig_df)} tests, {n_sig} significant at FDR q < 0.05")

    # Step 3 — long-term trends
    print("\nComputing long-term trends...")
    trends_df = compute_long_term_trends(arc_df)
    trends_df.to_csv(OUTPUT_DIR / "long_term_trends.csv", index=False)
    print(f"  {len(trends_df)} trend analyses")

    # Step 4 — plots
    print("\nGenerating plots...")
    plot_arc_per_participant(arc_df, plot_dir)
    plot_deviation_heatmap(arc_df, plot_dir)
    plot_long_term_trends(arc_df, plot_dir)
    plot_rolling_baseline(arc_df, plot_dir)
    plot_significance_summary(sig_df, plot_dir)
    print(f"  Plots saved to {plot_dir}")

    # Summary
    print(f"\n{'=' * 60}")
    print("  Arc Analysis Summary")
    print(f"{'=' * 60}")
    for participant in arc_df["participant"].unique():
        pdata = arc_df[arc_df["participant"] == participant]
        stress_dev = pdata["stress_dev_post"].dropna() if "stress_dev_post" in pdata.columns else pd.Series(dtype=float)
        mood = pdata["mood_delta"].dropna() if "mood_delta" in pdata.columns else pd.Series(dtype=float)
        print(f"  {participant:<15} {len(pdata)} sessions")
        if not stress_dev.empty:
            print(f"    Post stress dev: {stress_dev.mean():+.1f} +/- {stress_dev.std():.1f}")
        if not mood.empty:
            print(f"    Mood delta:      {mood.mean():+.1f} +/- {mood.std():.1f}")

    # Flag underpowered tests
    if not sig_df.empty:
        underpowered = sig_df[sig_df["n"] < 10]
        if not underpowered.empty:
            print(f"\n  WARNING: {len(underpowered)} tests have N < 10 — interpret with caution")


if __name__ == "__main__":
    main()
