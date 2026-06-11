"""
circadian_baseline.py — Computes per-participant circadian stress baselines
and builds feature matrices for mood/stress prediction.

The circadian baseline is the mean stress at each hour of day (0–23),
computed exclusively from non-session days. This allows quantifying how
"above/below normal" a participant's pre-session stress is, controlling
for time-of-day effects.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .utils import filter_non_session_days, get_session_dates, local_to_utc


MIN_OBS_PER_HOUR = 5  # Below this threshold, hourly baseline is set to NaN

# Ordinal encoding for pre-session activity state (higher = more active)
PRE_STATE_ENCODING = {"Sleep": 0, "Rest": 1, "Light": 2, "Medium": 3, "Heavy": 4}


def _load_minute_stress(proc_dir: Path) -> pd.DataFrame:
    """Load minute-level stress from Garmin or Huawei processed file.

    Returns DataFrame with columns: timestamp, stress.
    """
    for fname in ("garmin_minute_stress.csv", "huawei_minute_stress.csv"):
        path = proc_dir / fname
        if path.exists():
            df = pd.read_csv(path, parse_dates=["timestamp"])
            df = df.dropna(subset=["stress"])
            return df[["timestamp", "stress"]]
    raise FileNotFoundError(f"No minute-level stress file found in {proc_dir}")


def _load_minute_hr(proc_dir: Path) -> pd.DataFrame:
    """Load minute-level heart rate from Garmin or Huawei processed file.

    Returns DataFrame with columns: timestamp, heart_rate.
    """
    for fname in ("garmin_minute_hr.csv", "huawei_minute_hr.csv"):
        path = proc_dir / fname
        if path.exists():
            df = pd.read_csv(path, parse_dates=["timestamp"])
            df = df.dropna(subset=["heart_rate"])
            return df[["timestamp", "heart_rate"]]
    raise FileNotFoundError(f"No minute-level HR file found in {proc_dir}")


def _load_daily_hrv(raw_dir: Path) -> dict[str, float]:
    """Load daily HRV (RMSSD) from Garmin healthStatusData.json if available.

    Returns dict mapping date string ('YYYY-MM-DD') to HRV RMSSD value.
    Returns empty dict if no HRV data found.
    """
    import json

    hrv = {}
    # Garmin GDPR export stores health status in DI_CONNECT/DI-Connect-Wellness/
    wellness_dir = raw_dir / "export" / "DI_CONNECT" / "DI-Connect-Wellness"
    if not wellness_dir.exists():
        return hrv

    for path in wellness_dir.glob("*healthStatusData*.json"):
        with open(path) as f:
            data = json.load(f)
        for rec in data:
            date = rec.get("calendarDate")
            for m in rec.get("metrics", []):
                if m.get("type") == "HRV" and m.get("value") is not None:
                    hrv[date] = m["value"]
    return hrv


def _load_daily_resp(proc_dir: Path) -> dict[str, float]:
    """Load daily average respiration from garmin_daily.csv if available.

    Returns dict mapping date string ('YYYY-MM-DD') to avg_resp value.
    Returns empty dict if no daily file found or column missing.
    """
    path = proc_dir / "garmin_daily.csv"
    if not path.exists():
        return {}
    df = pd.read_csv(path)
    if "avg_resp" not in df.columns or "date" not in df.columns:
        return {}
    df = df.dropna(subset=["avg_resp"])
    return dict(zip(df["date"].astype(str), df["avg_resp"]))


def compute_circadian_baseline(
    participant: str,
    data_dir: Path,
) -> pd.DataFrame:
    """Compute hourly stress baseline from non-session days.

    Parameters
    ----------
    participant : str
        Participant codename (e.g., 'bosbes').
    data_dir : Path
        Root data directory (e.g., Path('data/wearables')).

    Returns
    -------
    pd.DataFrame
        Columns: hour (0–23), mean_stress, std_stress, n_obs_stress.
        Hours with fewer than MIN_OBS_PER_HOUR readings get NaN values.
    """
    proc_dir = data_dir / participant / "processed"

    stress_df = _load_minute_stress(proc_dir)
    session_dates = get_session_dates(proc_dir)
    non_session = filter_non_session_days(stress_df, session_dates)

    non_session["hour"] = non_session["timestamp"].dt.hour
    baseline = (
        non_session.groupby("hour")["stress"]
        .agg(mean_stress="mean", std_stress="std", n_obs_stress="count")
        .reset_index()
    )

    # Set unreliable hours to NaN (too few observations for a stable estimate)
    sparse = baseline["n_obs_stress"] < MIN_OBS_PER_HOUR
    baseline.loc[sparse, ["mean_stress", "std_stress"]] = np.nan

    return baseline


def compute_circadian_hr_baseline(
    participant: str,
    data_dir: Path,
) -> pd.DataFrame:
    """Compute hourly heart rate baseline from non-session days.

    Parameters
    ----------
    participant : str
        Participant codename (e.g., 'bosbes').
    data_dir : Path
        Root data directory (e.g., Path('data/wearables')).

    Returns
    -------
    pd.DataFrame
        Columns: hour (0–23), mean_hr, std_hr, n_obs_hr.
        Hours with fewer than MIN_OBS_PER_HOUR readings get NaN values.
    """
    proc_dir = data_dir / participant / "processed"

    hr_df = _load_minute_hr(proc_dir)
    session_dates = get_session_dates(proc_dir)
    non_session = filter_non_session_days(hr_df, session_dates)

    non_session["hour"] = non_session["timestamp"].dt.hour
    baseline = (
        non_session.groupby("hour")["heart_rate"]
        .agg(mean_hr="mean", std_hr="std", n_obs_hr="count")
        .reset_index()
    )

    # Set unreliable hours to NaN (too few observations for a stable estimate)
    sparse = baseline["n_obs_hr"] < MIN_OBS_PER_HOUR
    baseline.loc[sparse, ["mean_hr", "std_hr"]] = np.nan

    return baseline


def compute_pre_study_baseline(
    participant: str,
    data_dir: Path,
) -> pd.DataFrame:
    """Compute hourly stress baseline from days before the first session only.

    Used as a fixed reference for long-term trend analysis.
    Returns DataFrame: hour, mean_stress_pre, std_stress_pre, n_obs_stress_pre.
    """
    proc_dir = data_dir / participant / "processed"
    stress_df = _load_minute_stress(proc_dir)

    # Find first session date
    sessions_df = pd.read_csv(proc_dir / "session_biometrics.csv")
    first_session = pd.to_datetime(sessions_df["date"]).min().date()

    # Filter to days strictly before first session
    stress_df["date"] = stress_df["timestamp"].dt.date
    pre_study = stress_df[stress_df["date"] < first_session].copy()

    if len(pre_study) == 0:
        print(f"  WARNING: {participant} has no stress data before first session")
        return pd.DataFrame(columns=["hour", "mean_stress_pre", "std_stress_pre", "n_obs_stress_pre"])

    pre_study["hour"] = pre_study["timestamp"].dt.hour
    baseline = (
        pre_study.groupby("hour")["stress"]
        .agg(mean_stress_pre="mean", std_stress_pre="std", n_obs_stress_pre="count")
        .reset_index()
    )

    sparse = baseline["n_obs_stress_pre"] < MIN_OBS_PER_HOUR
    baseline.loc[sparse, ["mean_stress_pre", "std_stress_pre"]] = np.nan

    return baseline


def compute_pre_study_hr_baseline(
    participant: str,
    data_dir: Path,
) -> pd.DataFrame:
    """Compute hourly HR baseline from days before the first session only.

    Used as a fixed reference for long-term trend analysis.
    Returns DataFrame: hour, mean_hr_pre, std_hr_pre, n_obs_hr_pre.
    """
    proc_dir = data_dir / participant / "processed"
    hr_df = _load_minute_hr(proc_dir)

    # Find first session date
    sessions_df = pd.read_csv(proc_dir / "session_biometrics.csv")
    first_session = pd.to_datetime(sessions_df["date"]).min().date()

    # Filter to days strictly before first session
    hr_df["date"] = hr_df["timestamp"].dt.date
    pre_study = hr_df[hr_df["date"] < first_session].copy()

    if len(pre_study) == 0:
        print(f"  WARNING: {participant} has no HR data before first session")
        return pd.DataFrame(columns=["hour", "mean_hr_pre", "std_hr_pre", "n_obs_hr_pre"])

    pre_study["hour"] = pre_study["timestamp"].dt.hour
    baseline = (
        pre_study.groupby("hour")["heart_rate"]
        .agg(mean_hr_pre="mean", std_hr_pre="std", n_obs_hr_pre="count")
        .reset_index()
    )

    sparse = baseline["n_obs_hr_pre"] < MIN_OBS_PER_HOUR
    baseline.loc[sparse, ["mean_hr_pre", "std_hr_pre"]] = np.nan

    return baseline


# ══════════════════════════════════════════════════════════════════════════════
#  ACTIVITY STATE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _load_classified_minutes(participant: str, analysis_dir: Path) -> pd.DataFrame | None:
    """Load classified_minutes.csv produced by the extraction pipeline.

    Returns None (with warning) if the file doesn't exist yet.
    """
    path = analysis_dir / participant / "classified_minutes.csv"
    if not path.exists():
        print(
            f"  WARNING: [{participant}] classified_minutes.csv not found — "
            f"pre_state will be NaN. Run: uv run python scripts/extraction/pipeline.py {participant}"
        )
        return None
    return pd.read_csv(path, index_col="timestamp", parse_dates=True)


def _classify_window_state(
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


def build_feature_matrix(
    participants: list[str],
    data_dir: Path,
    analysis_dir: Path,
) -> pd.DataFrame:
    """Build a feature matrix with one row per session, pooled across participants.

    Parameters
    ----------
    participants : list[str]
        List of participant codenames.
    data_dir : Path
        Root wearables directory (e.g., Path('data/wearables')).
    analysis_dir : Path
        Root analysis directory (e.g., Path('data/analysis')).

    Returns
    -------
    tuple[pd.DataFrame, dict[str, list[str]]]
        Feature matrix with targets (mood_delta, stress_delta), and a dict
        of excluded optional features per participant (>50% NaN threshold).
    """
    OPTIONAL_FEATURES = ["hrv_rmssd", "avg_resp_daily"]
    EXCLUSION_THRESHOLD = 0.50  # exclude if more than 50% NaN

    rows = []

    for participant in participants:
        baseline = compute_circadian_baseline(participant, data_dir)
        baseline_lookup = baseline.set_index("hour")["mean_stress"]

        hr_baseline = compute_circadian_hr_baseline(participant, data_dir)
        hr_baseline_lookup = hr_baseline.set_index("hour")["mean_hr"]

        pre_study_bl = compute_pre_study_baseline(participant, data_dir)
        pre_study_stress_lookup = pre_study_bl.set_index("hour")["mean_stress_pre"] if len(pre_study_bl) > 0 else pd.Series(dtype=float)

        pre_study_hr_bl = compute_pre_study_hr_baseline(participant, data_dir)
        pre_study_hr_lookup = pre_study_hr_bl.set_index("hour")["mean_hr_pre"] if len(pre_study_hr_bl) > 0 else pd.Series(dtype=float)

        proc_dir = data_dir / participant / "processed"
        sessions = pd.read_csv(proc_dir / "session_biometrics.csv")

        # Load daily HRV if available (from raw healthStatusData.json)
        hrv_lookup = _load_daily_hrv(data_dir / participant / "raw")

        # Load daily respiration if available (from garmin_daily.csv)
        resp_lookup = _load_daily_resp(proc_dir)

        # Load classified minutes for pre_state computation
        classified_df = _load_classified_minutes(participant, analysis_dir)

        # Parse dates and times
        sessions["date"] = pd.to_datetime(sessions["date"])
        sessions["hour_of_day"] = sessions["start_local"].str.split(":").str[0].astype(int)
        sessions["day_of_week"] = sessions["date"].dt.dayofweek

        # Sort by date for days_since_last_session and session_number
        sessions = sessions.sort_values("date").reset_index(drop=True)

        for i, row in sessions.iterrows():
            hour = row["hour_of_day"]
            expected_stress = baseline_lookup.get(hour, np.nan)

            # Baseline deviation: actual pre_stress minus expected at that hour
            pre_stress = row["pre_stress_mean"]
            baseline_deviation = pre_stress - expected_stress if pd.notna(pre_stress) else np.nan

            # HR baseline deviation: actual pre_hr minus expected at that hour
            expected_hr = hr_baseline_lookup.get(hour, np.nan)
            pre_hr = row["pre_hr_mean"]
            hr_baseline_deviation = pre_hr - expected_hr if pd.notna(pre_hr) else np.nan

            # Pre-study deviations (fixed reference for long-term trend analysis)
            pre_study_expected_stress = pre_study_stress_lookup.get(hour, np.nan)
            pre_study_stress_deviation = pre_stress - pre_study_expected_stress if pd.notna(pre_stress) else np.nan

            pre_study_expected_hr = pre_study_hr_lookup.get(hour, np.nan)
            pre_study_hr_deviation = pre_hr - pre_study_expected_hr if pd.notna(pre_hr) else np.nan

            # Days since last session
            if i == 0:
                days_since_last = np.nan
            else:
                prev_date = sessions.loc[i - 1, "date"]
                days_since_last = (row["date"] - prev_date).days

            # Targets
            mood_before = row["mood_before_score"]
            mood_after = row["mood_after_score"]
            mood_delta = mood_after - mood_before if pd.notna(mood_before) and pd.notna(mood_after) else np.nan

            stress_delta = row.get("stress_delta", np.nan)

            # HRV for session date (optional — only peer has this currently)
            session_date_str = row["date"].strftime("%Y-%m-%d")
            hrv_rmssd = hrv_lookup.get(session_date_str, np.nan)

            # Daily respiration for session date (optional)
            avg_resp_daily = resp_lookup.get(session_date_str, np.nan)

            # Pre-session activity state from classified minutes
            if classified_df is not None:
                start_utc = local_to_utc(row["date"].date(), row["start_local"])
                pre_state = _classify_window_state(
                    classified_df,
                    start_utc - pd.Timedelta(minutes=30),
                    start_utc,
                )
                pre_state_encoded = PRE_STATE_ENCODING.get(pre_state, np.nan)
            else:
                pre_state = np.nan
                pre_state_encoded = np.nan

            features = {
                "participant": participant,
                "date": row["date"],
                "playlist": row["playlist"],
                "session_number": i + 1,  # 1-indexed, per participant
                "baseline_deviation_entry": baseline_deviation,
                "hr_baseline_deviation": hr_baseline_deviation,
                "hour_of_day": hour,
                "day_of_week": row["day_of_week"],
                "playlist_calm": 1 if row["playlist"] == "Calm" else 0,
                "playlist_energy": 1 if row["playlist"] == "Energy" else 0,
                "mood_before_score": mood_before,
                "bb_start": row["bb_start"],
                "days_since_last_session": days_since_last,
                "hrv_rmssd": hrv_rmssd,
                "avg_resp_daily": avg_resp_daily,
                "pre_state": pre_state,
                "pre_state_encoded": pre_state_encoded,
                # Targets
                "mood_delta": mood_delta,
                "stress_delta": stress_delta,
                # Session window means (pre already used above; during/post from biometrics)
                "pre_stress_mean": pre_stress,
                "during_stress_mean": row.get("stress_mean", np.nan),
                "post_stress_mean": row.get("post_stress_mean", np.nan),
                "pre_hr_mean": pre_hr,
                "during_hr_mean": row.get("hr_mean", np.nan),
                "post_hr_mean": row.get("post_hr_mean", np.nan),
                # Context (not features, but useful for inspection)
                "expected_stress_at_hour": expected_stress,
                "expected_hr_at_hour": expected_hr,
                # Pre-study deviations (fixed reference for long-term trend)
                "pre_study_stress_deviation": pre_study_stress_deviation,
                "pre_study_hr_deviation": pre_study_hr_deviation,
            }
            rows.append(features)

    fm = pd.DataFrame(rows)

    # Compute per-participant exclusion guard for optional features
    excluded_features: dict[str, list[str]] = {}
    for participant in fm["participant"].unique():
        mask = fm["participant"] == participant
        n_sessions = mask.sum()
        excluded = []
        for feat in OPTIONAL_FEATURES:
            n_missing = fm.loc[mask, feat].isna().sum()
            if n_missing / n_sessions > EXCLUSION_THRESHOLD:
                excluded.append(feat)
        excluded_features[participant] = excluded
        if excluded:
            print(f"  {participant}: excluding {excluded} from ML/significance (>{EXCLUSION_THRESHOLD*100:.0f}% NaN)")

    return fm, excluded_features


def export_baselines(
    participants: list[str],
    data_dir: Path,
    analysis_dir: Path,
) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    """Compute and export circadian baselines and feature matrix to CSV.

    Per-participant baselines go to:
        {analysis_dir}/{participant}/circadian_baselines/hourly_baseline.csv
    Combined feature matrix goes to:
        {analysis_dir}/circadian_baselines/feature_matrix.csv
    Exclusion metadata goes to:
        {analysis_dir}/circadian_baselines/excluded_features.json
    """
    import json

    combined_dir = analysis_dir / "circadian_baselines"
    combined_dir.mkdir(parents=True, exist_ok=True)

    for participant in participants:
        participant_dir = analysis_dir / participant / "circadian_baselines"
        participant_dir.mkdir(parents=True, exist_ok=True)

        stress_baseline = compute_circadian_baseline(participant, data_dir)
        hr_baseline = compute_circadian_hr_baseline(participant, data_dir)
        pre_stress_baseline = compute_pre_study_baseline(participant, data_dir)
        pre_hr_baseline = compute_pre_study_hr_baseline(participant, data_dir)

        # Merge all baselines into one CSV for easy visualization
        baseline = stress_baseline.merge(hr_baseline, on="hour", how="outer")
        baseline = baseline.merge(pre_stress_baseline, on="hour", how="outer")
        baseline = baseline.merge(pre_hr_baseline, on="hour", how="outer")
        baseline.to_csv(participant_dir / "hourly_baseline.csv", index=False)

    feature_matrix, excluded_features = build_feature_matrix(participants, data_dir, analysis_dir)

    # Upsert: merge with the existing combined file so re-running for one
    # participant does not erase the others' rows.
    combined_path = combined_dir / "feature_matrix.csv"
    if combined_path.exists():
        existing = pd.read_csv(combined_path)
        if "participant" in existing.columns:
            existing = existing[~existing["participant"].isin(participants)]
            feature_matrix = pd.concat([existing, feature_matrix], ignore_index=True)

    feature_matrix.to_csv(combined_path, index=False)

    # Save exclusion metadata for downstream code (ML, significance tests)
    with open(combined_dir / "excluded_features.json", "w") as f:
        json.dump(excluded_features, f, indent=2)

    return feature_matrix, excluded_features
