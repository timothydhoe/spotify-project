"""
utils.py — Shared utilities for the baseline pipeline.
"""
from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

# Belgian timezone — handles CET (UTC+1) and CEST (UTC+2) automatically
BE = ZoneInfo("Europe/Brussels")


def local_to_utc(date, time_str: str) -> pd.Timestamp:
    """Convert a local CET/CEST time string to a timezone-naive UTC Timestamp.

    Handles the DST transition automatically — sessions in winter (CET, UTC+1)
    and summer (CEST, UTC+2) each produce the correct UTC offset.

    Args:
        date: date object or YYYY-MM-DD string
        time_str: local time string, e.g. "11:09" or "11:09:00"

    Returns:
        Timezone-naive UTC Timestamp
    """
    local_dt = pd.Timestamp(f"{date} {time_str}").tz_localize(BE)
    return local_dt.tz_convert("UTC").tz_localize(None)


def get_session_dates(proc_dir: Path) -> set:
    """Load session dates from session_biometrics.csv as a set of date objects."""
    path = proc_dir / "session_biometrics.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"session_biometrics.csv not found at {path} — "
            "re-run extraction/pipeline.py with --force to regenerate it"
        )
    sessions_df = pd.read_csv(path)
    return set(pd.to_datetime(sessions_df["date"]).dt.date)


def filter_non_session_days(
    df: pd.DataFrame,
    session_dates: set,
    timestamp_col: str | None = "timestamp",
) -> pd.DataFrame:
    """Return rows from df whose date is not in session_dates.

    Args:
        df: DataFrame to filter.
        session_dates: Set of date objects to exclude.
        timestamp_col: Column name containing timestamps.
                       Pass None to use df.index instead (PersonBaseline usage).
    """
    if not session_dates or df.empty:
        return df
    if timestamp_col is None:
        if not hasattr(df.index, "date"):
            return df
        dates = pd.Series(df.index, index=df.index).apply(lambda ts: ts.date())
        return df[~dates.isin(session_dates)]
    dates = pd.to_datetime(df[timestamp_col]).dt.date
    return df[~dates.isin(session_dates)].copy()
