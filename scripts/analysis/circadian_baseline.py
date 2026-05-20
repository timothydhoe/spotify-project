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


MIN_OBS_PER_HOUR = 5  # Below this threshold, hourly baseline is set to NaN


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
        Columns: hour (0–23), mean_stress, std_stress, n_observations.
        Hours with fewer than MIN_OBS_PER_HOUR readings get NaN values.
    """
    proc_dir = data_dir / participant / "processed"

    # Load minute-level stress (auto-detects Garmin or Huawei)
    stress_df = _load_minute_stress(proc_dir)

    # Load session dates to exclude
    sessions_df = pd.read_csv(proc_dir / "session_biometrics.csv")
    session_dates = set(pd.to_datetime(sessions_df["date"]).dt.date)

    # Filter to non-session days
    stress_df["date"] = stress_df["timestamp"].dt.date
    non_session = stress_df[~stress_df["date"].isin(session_dates)].copy()

    # Group by hour of day
    non_session["hour"] = non_session["timestamp"].dt.hour
    baseline = (
        non_session.groupby("hour")["stress"]
        .agg(mean_stress="mean", std_stress="std", n_observations="count")
        .reset_index()
    )

    # Set unreliable hours to NaN (too few observations for a stable estimate)
    sparse = baseline["n_observations"] < MIN_OBS_PER_HOUR
    baseline.loc[sparse, ["mean_stress", "std_stress"]] = np.nan

    return baseline


def build_feature_matrix(
    participants: list[str],
    data_dir: Path,
) -> pd.DataFrame:
    """Build a feature matrix with one row per session, pooled across participants.

    Parameters
    ----------
    participants : list[str]
        List of participant codenames.
    data_dir : Path
        Root data directory (e.g., Path('data/wearables')).

    Returns
    -------
    pd.DataFrame
        Feature matrix with targets (mood_delta, stress_delta).
    """
    rows = []

    for participant in participants:
        baseline = compute_circadian_baseline(participant, data_dir)
        baseline_lookup = baseline.set_index("hour")["mean_stress"]

        proc_dir = data_dir / participant / "processed"
        sessions = pd.read_csv(proc_dir / "session_biometrics.csv")

        # Load daily HRV if available (from raw healthStatusData.json)
        hrv_lookup = _load_daily_hrv(data_dir / participant / "raw")

        # Parse dates and times
        sessions["date"] = pd.to_datetime(sessions["date"])
        sessions["hour_of_day"] = sessions["start_local"].str.split(":").str[0].astype(int)
        sessions["day_of_week"] = sessions["date"].dt.dayofweek

        # Sort by date for days_since_last_session
        sessions = sessions.sort_values("date").reset_index(drop=True)

        for i, row in sessions.iterrows():
            hour = row["hour_of_day"]
            expected_stress = baseline_lookup.get(hour, np.nan)

            # Baseline deviation: actual pre_stress minus expected at that hour
            pre_stress = row["pre_stress_mean"]
            baseline_deviation = pre_stress - expected_stress if pd.notna(pre_stress) else np.nan

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

            features = {
                "participant": participant,
                "date": row["date"],
                "playlist": row["playlist"],
                "baseline_deviation_entry": baseline_deviation,
                "hour_of_day": hour,
                "day_of_week": row["day_of_week"],
                "playlist_calm": 1 if row["playlist"] == "Calm" else 0,
                "playlist_energy": 1 if row["playlist"] == "Energy" else 0,
                "mood_before_score": mood_before,
                "bb_start": row["bb_start"],
                "days_since_last_session": days_since_last,
                "hrv_rmssd": hrv_rmssd,
                # Targets
                "mood_delta": mood_delta,
                "stress_delta": stress_delta,
                # Context (not features, but useful for inspection)
                "pre_stress_mean": pre_stress,
                "expected_stress_at_hour": expected_stress,
            }
            rows.append(features)

    return pd.DataFrame(rows)


def export_baselines(
    participants: list[str],
    data_dir: Path,
    analysis_dir: Path,
) -> pd.DataFrame:
    """Compute and export circadian baselines and feature matrix to CSV.

    Per-participant baselines go to:
        {analysis_dir}/{participant}/circadian_baselines/hourly_baseline.csv
    Combined feature matrix goes to:
        {analysis_dir}/circadian_baselines/feature_matrix.csv
    """
    combined_dir = analysis_dir / "circadian_baselines"
    combined_dir.mkdir(parents=True, exist_ok=True)

    for participant in participants:
        participant_dir = analysis_dir / participant / "circadian_baselines"
        participant_dir.mkdir(parents=True, exist_ok=True)

        baseline = compute_circadian_baseline(participant, data_dir)
        baseline.to_csv(participant_dir / "hourly_baseline.csv", index=False)

    feature_matrix = build_feature_matrix(participants, data_dir)
    feature_matrix.to_csv(combined_dir / "feature_matrix.csv", index=False)

    return feature_matrix


if __name__ == "__main__":
    from pathlib import Path

    DATA_DIR = Path(__file__).resolve().parents[2] / "data/wearables"
    ANALYSIS_DIR = Path(__file__).resolve().parents[2] / "data/analysis"
    PARTICIPANTS = ["bosbes", "kokosnoot", "limoen", "peer"]

    fm = export_baselines(PARTICIPANTS, DATA_DIR, ANALYSIS_DIR)
    print(f"Feature matrix: {len(fm)} sessions, {fm.columns.tolist()}")
    print(f"\nMood delta stats:\n{fm['mood_delta'].describe()}")
    print(f"\nBaseline deviation stats:\n{fm['baseline_deviation_entry'].describe()}")
