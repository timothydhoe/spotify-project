"""
utils.py — Shared helpers for the sessions pipeline.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo

import pandas as pd

_BRUSSELS = ZoneInfo("Europe/Brussels")


def local_to_utc(dt_local: pd.Timestamp) -> pd.Timestamp:
    """Convert a naive local (Europe/Brussels) timestamp to UTC.

    Handles DST automatically — works correctly for both CET (UTC+1)
    and CEST (UTC+2) periods.
    """
    return dt_local.tz_localize(_BRUSSELS).tz_convert("UTC").tz_localize(None)


def classify_window_state(
    classified_df: pd.DataFrame,
    start_utc: pd.Timestamp,
    end_utc: pd.Timestamp,
) -> str:
    """Majority-vote activity state in the [start_utc, end_utc] window.

    Args:
        classified_df: Per-minute DataFrame with 'activity_state' column
                       and a UTC datetime index.
        start_utc: Window start (UTC, naive).
        end_utc:   Window end (UTC, naive).

    Returns:
        Most common activity state in the window, or 'Rest' if the window
        is empty or the column is missing.
    """
    if classified_df.empty or "activity_state" not in classified_df.columns:
        return "Rest"
    try:
        window = classified_df.loc[start_utc:end_utc, "activity_state"].dropna()
        if window.empty:
            return "Rest"
        return str(window.mode().iloc[0])
    except (KeyError, IndexError):
        return "Rest"
