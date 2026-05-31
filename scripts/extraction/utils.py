"""
utils.py — Shared utilities for the extraction pipeline.

Functions shared between garmin_pipeline, huawei_pipeline, and fit_extractor
to eliminate duplication and centralise timezone handling.
"""

import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

# Belgian timezone — handles CET (UTC+1) and CEST (UTC+2) automatically
BE = ZoneInfo("Europe/Brussels")


# ── Timezone ────────────────────────────────────────────────────────────────

def local_to_utc(date, time_str: str) -> pd.Timestamp:
    """Convert a local CET/CEST time string to a timezone-naive UTC Timestamp.

    Handles the DST transition (last Sunday of March, 02:00 → 03:00) automatically.
    A session at 14:00 on March 28 (CET, UTC+1) and one at 14:00 on March 30
    (CEST, UTC+2) each produce the correct UTC offset without manual intervention.

    Args:
        date: date object or YYYY-MM-DD string
        time_str: local time string, e.g. "11:09" or "11:09:00"

    Returns:
        Timezone-naive UTC Timestamp
    """
    local_dt = pd.Timestamp(f"{date} {time_str}").tz_localize(BE)
    return local_dt.tz_convert("UTC").tz_localize(None)


def utc_to_local(ts: pd.Timestamp) -> pd.Timestamp:
    """Convert a timezone-naive UTC Timestamp to a timezone-aware Brussels local time."""
    return ts.tz_localize("UTC").tz_convert(BE)


# ── FIT binary helpers ───────────────────────────────────────────────────────

def reconstruct_timestamp_16(base_ts: datetime.datetime, timestamp_16: int) -> datetime.datetime:
    """Reconstruct a full UTC datetime from a Garmin FIT 16-bit relative timestamp.

    Garmin FIT monitoring messages compress timestamps to 16 bits, relative to
    the base timestamp in the preceding monitoring_info message.

    Args:
        base_ts: Full timestamp from the most recent monitoring_info message
        timestamp_16: 16-bit relative timestamp from a monitoring message field

    Returns:
        Timezone-naive UTC datetime
    """
    base_s = int(base_ts.timestamp())
    full = (base_s & ~0xFFFF) | (timestamp_16 & 0xFFFF)
    if full < base_s:
        full += 0x10000
    return datetime.datetime.fromtimestamp(full, tz=datetime.timezone.utc).replace(tzinfo=None)


# ── Check-in helpers ─────────────────────────────────────────────────────────

def get_date_range_from_checkins(
    checkin_path: Path | None, code: str, months: int = 6
) -> tuple[datetime.datetime, datetime.datetime]:
    """Determine processing date range from check-in CSV, falling back to last N months.

    Range: 30 days before first session → 7 days after last session.

    Args:
        checkin_path: Path to check-in CSV, or None
        code: Participant codename
        months: Fallback window in months when no check-in data is found

    Returns:
        (date_start, date_end) as naive datetime objects
    """
    import datetime as _dt
    from checkin_utils import fix_checkin_dates

    date_end = _dt.datetime.now()
    date_start = date_end - _dt.timedelta(days=months * 30)

    if checkin_path and Path(checkin_path).exists():
        try:
            ck = pd.read_csv(checkin_path)
            sess = ck[ck["Deelnemerscode"].str.strip().str.lower() == code.lower()]
            dates = fix_checkin_dates(sess)
            if len(dates):
                date_start = (dates.min() - _dt.timedelta(days=30)).to_pydatetime()
                date_end = (dates.max() + _dt.timedelta(days=7)).to_pydatetime()
        except Exception:
            pass

    return date_start, date_end


# ── Session cross-reference ───────────────────────────────────────────────────

def crossref_sessions(
    checkin_path: Path,
    code: str,
    stress_df: pd.DataFrame,
    hr_df: pd.DataFrame,
    buffer_min: int = 60,
    has_body_battery: bool = True,
) -> tuple[pd.DataFrame, list[pd.DataFrame]]:
    """For each check-in session, extract ±buffer_min biometric windows.

    Uses Europe/Brussels timezone for correct CET/CEST conversion — handles
    both winter (CET, UTC+1) and summer (CEST, UTC+2) sessions automatically.

    Args:
        checkin_path: Path to check-in CSV
        code: Participant codename
        stress_df: Minute-level stress DataFrame indexed by UTC timestamp.
                   For Garmin, also contains a body_battery column.
        hr_df: Minute-level HR DataFrame indexed by UTC timestamp
        buffer_min: Minutes before/after session to include in trace window
        has_body_battery: True for Garmin (body_battery in stress_df), False for Huawei

    Returns:
        (summary_df, traces): one-row-per-session summary + list of minute-level DataFrames
    """
    from checkin_utils import fix_checkin_dates

    checkin = pd.read_csv(checkin_path)
    sessions = checkin[checkin["Deelnemerscode"].str.strip().str.lower() == code.lower()].copy()
    if sessions.empty:
        print(f"  ⚠ No sessions for '{code}'")
        return pd.DataFrame(), []

    # Parse and correct check-in dates, then convert local times → UTC
    sessions["_date"] = fix_checkin_dates(sessions)
    for col, src in [("_start", "Starttijd?"), ("_end", "Eindtijd?")]:
        sessions[col] = sessions.apply(
            lambda r: local_to_utc(r["_date"].date(), r[src]),
            axis=1,
        )

    BUF = pd.Timedelta(minutes=buffer_min)
    summaries, traces = [], []

    for _, row in sessions.iterrows():
        t0, t1 = row["_start"], row["_end"]

        # Build minute-level trace: -buffer_min → +buffer_min
        idx = pd.date_range(t0 - BUF, t1 + BUF, freq="1min")
        trace = pd.DataFrame(index=idx)
        trace.index.name = "timestamp_utc"

        if len(stress_df):
            nearest = stress_df.reindex(idx, method="nearest", tolerance="2min")
            trace["stress"] = nearest["stress"]
            if has_body_battery and "body_battery" in nearest.columns:
                trace["body_battery"] = nearest["body_battery"]
        if len(hr_df):
            trace["heart_rate"] = hr_df.reindex(idx, method="nearest", tolerance="2min")["heart_rate"]

        # Label phases
        trace["phase"] = "pre"
        trace.loc[t0:t1, "phase"] = "during"
        trace.loc[t1 + pd.Timedelta(minutes=1):, "phase"] = "post"
        trace["minutes_relative"] = (trace.index - t0).total_seconds() / 60
        trace["session_date"] = row["_date"].strftime("%Y-%m-%d")
        trace["playlist"] = row["Welke playlist luisterde je?"]
        traces.append(trace)

        # Aggregate per phase
        def phase_stats(col, phase):
            return (
                trace.loc[trace["phase"] == phase, col].dropna()
                if col in trace
                else pd.Series(dtype=float)
            )

        pre_s, dur_s, post_s = [phase_stats("stress", p) for p in ("pre", "during", "post")]
        pre_h, dur_h, post_h = [phase_stats("heart_rate", p) for p in ("pre", "during", "post")]
        pre_bb, dur_bb, post_bb = (
            [phase_stats("body_battery", p) for p in ("pre", "during", "post")]
            if has_body_battery
            else [pd.Series(dtype=float)] * 3
        )

        def safe(s, fn):
            return round(fn(s), 1) if len(s) else None

        def delta(a, b):
            return round(a.mean() - b.mean(), 1) if len(a) and len(b) else None

        # Derive local display times from UTC (correct CET/CEST via zoneinfo)
        local_start = utc_to_local(pd.Timestamp(t0))
        local_end = utc_to_local(pd.Timestamp(t1))

        summaries.append({
            "date":              row["_date"].strftime("%Y-%m-%d"),
            "start_local":       local_start.strftime("%H:%M"),
            "end_local":         local_end.strftime("%H:%M"),
            "duration_min":      int((t1 - t0).total_seconds() / 60),
            "playlist":          row["Welke playlist luisterde je?"],
            "mood_before":       row["Welk gevoel had je?"],
            "mood_before_score": row["Score van de intensiteit van je gevoel"],
            "mood_after":        row["Welk gevoel had je?.1"],
            "mood_after_score":  row["Score van de intensiteit van je gevoel.1"],
            # Pre (buffer_min window)
            "pre_stress_mean":   safe(pre_s, np.mean),
            "pre_hr_mean":       safe(pre_h, np.mean),
            "pre_bb_mean":       safe(pre_bb, np.mean) if has_body_battery else None,
            # During
            "stress_mean":       safe(dur_s, np.mean),
            "stress_min":        safe(dur_s, np.min),
            "stress_max":        safe(dur_s, np.max),
            "hr_mean":           safe(dur_h, np.mean),
            "hr_min":            safe(dur_h, np.min),
            "hr_max":            safe(dur_h, np.max),
            "bb_start":          (int(dur_bb.iloc[0]) if len(dur_bb) else None) if has_body_battery else None,
            "bb_end":            (int(dur_bb.iloc[-1]) if len(dur_bb) else None) if has_body_battery else None,
            "bb_delta":          (int(dur_bb.iloc[-1] - dur_bb.iloc[0]) if len(dur_bb) > 1 else None) if has_body_battery else None,
            # Post (buffer_min window)
            "post_stress_mean":  safe(post_s, np.mean),
            "post_hr_mean":      safe(post_h, np.mean),
            "post_bb_mean":      safe(post_bb, np.mean) if has_body_battery else None,
            # Deltas (post − pre)
            "stress_delta":      delta(post_s, pre_s),
            "hr_delta":          delta(post_h, pre_h),
            "bb_delta_full":     delta(post_bb, pre_bb) if has_body_battery else None,
            # Data quality
            "stress_points":     len(dur_s),
            "hr_points":         len(dur_h),
        })

    return pd.DataFrame(summaries), traces


# ── Session trace output ──────────────────────────────────────────────────────

def write_session_traces(traces: list[pd.DataFrame], out_dir: Path) -> None:
    """Write per-session trace CSVs and a combined session_traces_all.csv.

    Only sessions with at least one valid stress or HR reading are written.
    Silent no-op if traces is empty.
    """
    if not traces:
        return

    tdir = out_dir / "session_traces"
    tdir.mkdir(exist_ok=True)
    all_valid = []

    for t in traces:
        has_data = (
            ("stress" in t.columns and t["stress"].notna().any())
            or ("heart_rate" in t.columns and t["heart_rate"].notna().any())
        )
        if has_data:
            all_valid.append(t)
            fname = f"trace_{t['session_date'].iloc[0]}_{t['playlist'].iloc[0].lower()}.csv"
            t.to_csv(tdir / fname)

    if all_valid:
        pd.concat(all_valid).to_csv(out_dir / "session_traces_all.csv")
        print(f"  → session_traces/ ({len(all_valid)} files)")
