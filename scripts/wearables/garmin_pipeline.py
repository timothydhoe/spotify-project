#!/usr/bin/env python3
"""
garmin_pipeline.py — Extract, transform, and analyze Garmin Connect GDPR exports.
Cross-references minute-level biometrics with R.E.M. study check-in sessions.

Usage:
    python garmin_pipeline.py <export_dir> --out <output_dir> --checkin <csv> --code <participant>

Dependencies:
    Required:  pandas, fitparse
    Optional:  matplotlib (for PDF report generation)
"""

import argparse
import json
import sys
import zipfile
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from checkin_utils import fix_checkin_dates


# ── Extract: Daily JSON ─────────────────────────────────────────────────────

def extract_daily(path: Path) -> pd.DataFrame:
    """Parse the UDS (User Daily Summary) aggregator JSON into a flat DataFrame."""
    with open(path) as f:
        raw = json.load(f)

    rows = []
    for r in raw:
        # Find the TOTAL stress aggregator
        stress = {}
        for entry in r.get("allDayStress", {}).get("aggregatorList", []):
            if entry.get("type") == "TOTAL":
                stress = entry
                break

        bb = r.get("bodyBattery", {})
        bb_stats = {s["bodyBatteryStatType"]: s["statsValue"]
                    for s in bb.get("bodyBatteryStatList", [])}
        resp = r.get("respiration", {})

        rows.append({
            "date":            r["calendarDate"],
            "steps":           r.get("totalSteps"),
            "step_goal":       r.get("dailyStepGoal"),
            "distance_m":      r.get("totalDistanceMeters"),
            "total_cal":       r.get("totalKilocalories"),
            "active_cal":      r.get("activeKilocalories"),
            "bmr_cal":         r.get("bmrKilocalories"),
            "resting_hr":      r.get("restingHeartRate"),
            "min_hr":          r.get("minHeartRate"),
            "max_hr":          r.get("maxHeartRate"),
            "highly_active_s": r.get("highlyActiveSeconds"),
            "active_s":        r.get("activeSeconds"),
            "moderate_min":    r.get("moderateIntensityMinutes"),
            "vigorous_min":    r.get("vigorousIntensityMinutes"),
            "avg_stress":      stress.get("averageStressLevel"),
            "max_stress":      stress.get("maxStressLevel"),
            "stress_high_min": round(stress["highDuration"] / 60, 1) if stress.get("highDuration") else None,
            "stress_med_min":  round(stress["mediumDuration"] / 60, 1) if stress.get("mediumDuration") else None,
            "stress_low_min":  round(stress["lowDuration"] / 60, 1) if stress.get("lowDuration") else None,
            "rest_min":        round(stress["restDuration"] / 60, 1) if stress.get("restDuration") else None,
            "bb_charged":      bb.get("chargedValue"),
            "bb_drained":      bb.get("drainedValue"),
            "bb_highest":      bb_stats.get("HIGHEST"),
            "bb_lowest":       bb_stats.get("LOWEST"),
            "avg_resp":        resp.get("avgWakingRespirationValue"),
            "high_resp":       resp.get("highestRespirationValue"),
            "low_resp":        resp.get("lowestRespirationValue"),
        })

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def extract_fitness_age(path: Path) -> pd.DataFrame:
    """Parse fitness age snapshots."""
    with open(path) as f:
        raw = json.load(f)
    rows = [{
        "date":       r.get("asOfDateGmt", "")[:10],
        "chrono_age": r.get("chronologicalAge"),
        "bio_age":    round(r.get("currentBioAge", 0), 2),
        "rhr":        r.get("rhr"),
        "bmi":        round(r.get("bmi", 0), 2),
    } for r in raw]
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


# ── Extract: Minute-level FIT files ─────────────────────────────────────────

def extract_fit_files(fit_zips: list[Path], date_range: tuple = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Extract per-minute stress/BB and HR from FIT binaries inside zips.

    Args:
        date_range: Optional (start, end) datetime tuple. Files outside this range are skipped.

    Returns (stress_df, hr_df), both indexed by UTC timestamp.
    """
    import fitparse
    import datetime

    stress_rows, hr_rows = [], []

    with tempfile.TemporaryDirectory() as tmpdir:
        # Unzip all .fit files
        fit_paths = []
        for zp in fit_zips:
            try:
                with zipfile.ZipFile(zp) as z:
                    for name in z.namelist():
                        if name.endswith(".fit"):
                            z.extract(name, tmpdir)
                            fit_paths.append(Path(tmpdir) / name)
            except Exception:
                pass

        total = len(fit_paths)
        skipped = 0

        for i, fp in enumerate(fit_paths):
            try:
                ff = fitparse.FitFile(str(fp))

                # Quick date check: read first timestamp, skip if outside range
                if date_range:
                    first_ts = None
                    for msg in ff.get_messages("monitoring_info"):
                        first_ts = {f.name: f.value for f in msg.fields}.get("timestamp")
                        break
                    if not first_ts:
                        for msg in fitparse.FitFile(str(fp)).get_messages("stress_level"):
                            first_ts = {f.name: f.value for f in msg.fields}.get("stress_level_time")
                            break
                    if first_ts and (first_ts < date_range[0] or first_ts > date_range[1]):
                        skipped += 1
                        continue

                # Pass 1: stress_level messages (1/min, includes body battery)
                for msg in fitparse.FitFile(str(fp)).get_messages("stress_level"):
                    f = {field.name: field.value for field in msg.fields}
                    if f.get("stress_level_time") and f.get("stress_level_value") is not None:
                        stress_rows.append({
                            "timestamp":    f["stress_level_time"],
                            "stress":       f["stress_level_value"],
                            "body_battery": f.get("unknown_3"),  # undocumented BB field
                        })

                # Pass 2: monitoring messages (HR)
                base_ts = None
                for msg in fitparse.FitFile(str(fp)).get_messages():
                    f = {field.name: field.value for field in msg.fields}
                    if msg.name == "monitoring_info":
                        base_ts = f.get("timestamp")
                    elif msg.name == "monitoring" and f.get("heart_rate", 0) > 0:
                        ts = f.get("timestamp")
                        if not ts and f.get("timestamp_16") and base_ts:
                            # Reconstruct full timestamp from 16-bit relative value
                            base_s = int(base_ts.timestamp())
                            full = (base_s & ~0xFFFF) | (f["timestamp_16"] & 0xFFFF)
                            if full < base_s:
                                full += 0x10000
                            ts = datetime.datetime.fromtimestamp(
                                full, tz=datetime.timezone.utc
                            ).replace(tzinfo=None)
                        if ts:
                            hr_rows.append({"timestamp": ts, "heart_rate": f["heart_rate"]})
            except Exception:
                pass

            # Progress indicator for large exports
            if total > 500 and (i + 1) % 500 == 0:
                print(f"    ... {i + 1}/{total} files processed")

    print(f"  {total} FIT files from {len(fit_zips)} zips" +
          (f" ({skipped} skipped — outside date range)" if skipped else ""))

    # Build, deduplicate, clean
    if not stress_rows:
        return pd.DataFrame(), pd.DataFrame()

    stress_df = (pd.DataFrame(stress_rows)
                 .drop_duplicates("timestamp")
                 .sort_values("timestamp")
                 .set_index("timestamp"))
    stress_df.loc[stress_df["stress"] <= 0, "stress"] = np.nan
    stress_df.loc[~stress_df["body_battery"].between(0, 100), "body_battery"] = np.nan

    hr_df = pd.DataFrame(hr_rows or [], columns=["timestamp", "heart_rate"])
    if not hr_df.empty:
        hr_df = hr_df.drop_duplicates("timestamp").sort_values("timestamp").set_index("timestamp")

    valid = stress_df["stress"].notna().sum()
    print(f"  Stress: {len(stress_df)} records ({valid} valid), HR: {len(hr_df)} records")
    print(f"  Range:  {stress_df.index.min():%Y-%m-%d %H:%M} → {stress_df.index.max():%Y-%m-%d %H:%M} UTC")

    return stress_df, hr_df


# ── Transform ───────────────────────────────────────────────────────────────

def transform(daily: pd.DataFrame) -> pd.DataFrame:
    """Drop no-wear days, add derived columns and 7-day rolling averages."""
    df = daily[daily["steps"].notna() & (daily["steps"] > 0)].copy()

    df["distance_km"]   = (df["distance_m"] / 1000).round(2)
    df["goal_met"]      = df["steps"] >= df["step_goal"]
    df["bb_range"]      = df["bb_highest"] - df["bb_lowest"]
    df["intensity_min"] = df["moderate_min"].fillna(0) + df["vigorous_min"].fillna(0)

    for col in ["steps", "resting_hr", "avg_stress", "bb_highest", "active_cal"]:
        df[f"{col}_7d"] = df[col].rolling(7, min_periods=3).mean().round(1)

    return df


# ── Analyze ─────────────────────────────────────────────────────────────────

def analyze(df: pd.DataFrame) -> dict:
    """Compute summary statistics and generate insights."""
    stress_valid = df[df["avg_stress"] > 0]
    bb_valid = df[df["bb_highest"].notna()]
    corr_data = df[["avg_stress", "bb_highest", "steps"]].dropna()
    corr_data = corr_data[corr_data["avg_stress"] > 0]

    # RHR trend via linear regression
    rhr = df["resting_hr"].dropna()
    rhr_trend = 0.0
    if len(rhr) >= 5:
        rhr_trend = round(np.polyfit(range(len(rhr)), rhr.values, 1)[0] * 7, 2)

    a = {
        "n_days":         len(df),
        "date_range":     f"{df.index.min():%Y-%m-%d} → {df.index.max():%Y-%m-%d}",
        "avg_steps":      int(df["steps"].mean()),
        "median_steps":   int(df["steps"].median()),
        "max_steps":      int(df["steps"].max()),
        "goal_pct":       round(df["goal_met"].mean() * 100, 1),
        "total_km":       round(df["distance_km"].sum(), 1),
        "avg_rhr":        round(df["resting_hr"].mean(), 1),
        "rhr_trend":      rhr_trend,
        "avg_stress":     round(stress_valid["avg_stress"].mean(), 1) if len(stress_valid) else 0,
        "avg_bb_high":    round(bb_valid["bb_highest"].mean(), 1) if len(bb_valid) else 0,
        "avg_bb_low":     round(bb_valid["bb_lowest"].mean(), 1) if len(bb_valid) else 0,
        "depleted_days":  int((bb_valid["bb_lowest"] < 20).sum()) if len(bb_valid) else 0,
        "r_stress_bb":    round(corr_data["avg_stress"].corr(corr_data["bb_highest"]), 3) if len(corr_data) >= 5 else 0,
    }

    # Auto-insights
    a["insights"] = []
    if rhr_trend > 0.5:
        a["insights"].append(f"RHR trending up {rhr_trend:+.1f} bpm/week — watch for fatigue.")
    if a["goal_pct"] < 50:
        a["insights"].append(f"Step goal met only {a['goal_pct']:.0f}% of days.")
    if a["depleted_days"] > a["n_days"] * 0.3:
        a["insights"].append(f"BB below 20 on {a['depleted_days']}/{a['n_days']} days — recovery debt.")

    return a


# ── Cross-reference: check-in sessions × biometrics ────────────────────────

def crossref_sessions(
    checkin_path: Path,
    code: str,
    stress_df: pd.DataFrame,
    hr_df: pd.DataFrame,
    utc_offset: int = 1,
    buffer_min: int = 60,
) -> tuple[pd.DataFrame, list[pd.DataFrame]]:
    """For each check-in session, extract ±60 min biometric windows.

    Returns:
        summary:  one row per session, aggregated pre/during/post stats
        traces:   list of minute-level DataFrames (one per session)
    """
    checkin = pd.read_csv(checkin_path)
    sessions = checkin[checkin["Deelnemerscode"].str.lower() == code.lower()].copy()
    if sessions.empty:
        print(f"  ⚠ No sessions for '{code}'")
        return pd.DataFrame(), []

    # Parse session times → UTC
    sessions["_date"] = fix_checkin_dates(sessions)
    for col, src in [("_start", "Starttijd?"), ("_end", "Eindtijd?")]:
        sessions[col] = sessions.apply(
            lambda r: pd.Timestamp(f"{r['_date'].date()} {r[src]}") - pd.Timedelta(hours=utc_offset),
            axis=1,
        )

    BUF = pd.Timedelta(minutes=buffer_min)
    summaries, traces = [], []

    for _, row in sessions.iterrows():
        t0, t1 = row["_start"], row["_end"]

        # Build minute-level trace: -60 min → +60 min
        idx = pd.date_range(t0 - BUF, t1 + BUF, freq="1min")
        trace = pd.DataFrame(index=idx)
        trace.index.name = "timestamp_utc"

        if len(stress_df):
            nearest = stress_df.reindex(idx, method="nearest", tolerance="1min")
            trace["stress"] = nearest["stress"]
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
            s = trace.loc[trace["phase"] == phase, col].dropna() if col in trace else pd.Series(dtype=float)
            return s

        pre_s,  dur_s,  post_s  = [phase_stats("stress", p) for p in ("pre", "during", "post")]
        pre_h,  dur_h,  post_h  = [phase_stats("heart_rate", p) for p in ("pre", "during", "post")]
        pre_bb, dur_bb, post_bb = [phase_stats("body_battery", p) for p in ("pre", "during", "post")]

        def safe(s, fn):
            return round(fn(s), 1) if len(s) else None

        def delta(post, pre):
            return round(post.mean() - pre.mean(), 1) if len(post) and len(pre) else None

        local_start = t0 + pd.Timedelta(hours=utc_offset)
        local_end   = t1 + pd.Timedelta(hours=utc_offset)

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
            # Pre (60 min)
            "pre_stress_mean":   safe(pre_s, np.mean),
            "pre_hr_mean":       safe(pre_h, np.mean),
            "pre_bb_mean":       safe(pre_bb, np.mean),
            # During
            "stress_mean":       safe(dur_s, np.mean),
            "stress_min":        safe(dur_s, np.min),
            "stress_max":        safe(dur_s, np.max),
            "hr_mean":           safe(dur_h, np.mean),
            "hr_min":            safe(dur_h, np.min),
            "hr_max":            safe(dur_h, np.max),
            "bb_start":          int(dur_bb.iloc[0]) if len(dur_bb) else None,
            "bb_end":            int(dur_bb.iloc[-1]) if len(dur_bb) else None,
            "bb_delta":          int(dur_bb.iloc[-1] - dur_bb.iloc[0]) if len(dur_bb) > 1 else None,
            # Post (60 min)
            "post_stress_mean":  safe(post_s, np.mean),
            "post_hr_mean":      safe(post_h, np.mean),
            "post_bb_mean":      safe(post_bb, np.mean),
            # Deltas (post − pre)
            "stress_delta":      delta(post_s, pre_s),
            "hr_delta":          delta(post_h, pre_h),
            "bb_delta_full":     delta(post_bb, pre_bb),
            # Data quality
            "stress_points":     len(dur_s),
            "hr_points":         len(dur_h),
        })

    return pd.DataFrame(summaries), traces


# ── PDF Report (optional — only if matplotlib is installed) ─────────────────

def render_pdf(daily_df, analysis, fa_df, sessions_df, out_path):
    """Generate a multi-page PDF report. Skipped if matplotlib is unavailable."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib.backends.backend_pdf import PdfPages
        from matplotlib.gridspec import GridSpec
    except ImportError:
        print("  ⚠ matplotlib not installed — skipping PDF report")
        return

    # Theme
    PAL = {
        "bg": "#0f1218", "card": "#181e2a", "grid": "#232b3a",
        "text": "#c9d1d9", "muted": "#586475", "cyan": "#22d3ee",
        "violet": "#a78bfa", "pink": "#f472b6", "green": "#34d399",
        "orange": "#fb923c", "red": "#f87171", "yellow": "#fbbf24",
    }
    plt.rcParams.update({
        "figure.facecolor": PAL["bg"], "axes.facecolor": PAL["card"],
        "axes.edgecolor": PAL["grid"], "axes.labelcolor": PAL["text"],
        "axes.grid": True, "grid.color": PAL["grid"], "grid.linewidth": 0.5,
        "text.color": PAL["text"], "xtick.color": PAL["muted"],
        "ytick.color": PAL["muted"], "xtick.labelsize": 8, "ytick.labelsize": 8,
        "legend.facecolor": PAL["card"], "legend.edgecolor": PAL["grid"],
        "legend.fontsize": 8, "font.family": "monospace", "font.size": 9,
        "figure.dpi": 150,
    })

    def fmt_dates(ax):
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

    df = daily_df
    a = analysis

    with PdfPages(out_path) as pdf:
        # ── Page 1: Daily overview ──
        fig = plt.figure(figsize=(11.7, 16.5))
        fig.suptitle("Garmin Vitals Report", fontsize=16, fontweight="bold",
                     color=PAL["cyan"], y=0.98)
        fig.text(0.5, 0.965, f"{a['date_range']}  ·  {a['n_days']} days",
                 ha="center", fontsize=9, color=PAL["muted"])
        gs = GridSpec(4, 2, figure=fig, hspace=0.38, wspace=0.28,
                      left=0.08, right=0.96, top=0.94, bottom=0.04)

        # Steps
        ax = fig.add_subplot(gs[0, :])
        colors = [PAL["cyan"] if m else PAL["grid"] for m in df["goal_met"]]
        ax.bar(df.index, df["steps"], color=colors, alpha=0.8, width=0.8)
        ax.plot(df.index, df["step_goal"], color=PAL["muted"], ls="--", lw=1, label="Goal")
        ax.plot(df.index, df["steps_7d"], color=PAL["orange"], lw=2, label="7d avg")
        ax.set_title("Daily Steps", fontweight="bold"); ax.legend(loc="upper left"); fmt_dates(ax)

        # Heart Rate
        ax = fig.add_subplot(gs[1, 0])
        ax.fill_between(df.index, df["min_hr"], df["max_hr"], color=PAL["pink"], alpha=0.12)
        ax.plot(df.index, df["resting_hr"], color=PAL["pink"], lw=2, label="Resting HR")
        ax.plot(df.index, df["resting_hr_7d"], color=PAL["violet"], lw=1.5, ls="--", label="7d avg")
        ax.set_title("Heart Rate", fontweight="bold"); ax.set_ylabel("bpm")
        ax.legend(loc="upper left"); fmt_dates(ax)

        # Stress
        ax = fig.add_subplot(gs[1, 1])
        sv = df[df["avg_stress"] > 0]
        ax.bar(sv.index, sv["avg_stress"], color=PAL["orange"], alpha=0.7, width=0.8)
        ax.plot(sv.index, sv["max_stress"], color=PAL["red"], lw=1, marker=".", ms=3, label="Peak")
        ax.axhline(35, color=PAL["yellow"], ls="--", lw=0.8, alpha=0.6)
        ax.set_title("Stress Level", fontweight="bold"); ax.set_ylim(0, 100)
        ax.legend(loc="upper left"); fmt_dates(ax)

        # Body Battery
        ax = fig.add_subplot(gs[2, :])
        bv = df[df["bb_highest"].notna()]
        ax.fill_between(bv.index, bv["bb_lowest"], bv["bb_highest"], color=PAL["green"], alpha=0.25)
        ax.plot(bv.index, bv["bb_highest"], color=PAL["green"], lw=2, label="Peak")
        ax.plot(bv.index, bv["bb_lowest"], color=PAL["red"], lw=1.5, alpha=0.7, label="Trough")
        ax.set_title("Body Battery", fontweight="bold"); ax.set_ylim(0, 100)
        ax.legend(loc="upper left"); fmt_dates(ax)

        # Calories
        ax = fig.add_subplot(gs[3, 0])
        ax.fill_between(df.index, 0, df["bmr_cal"], color=PAL["muted"], alpha=0.3, label="BMR")
        ax.fill_between(df.index, df["bmr_cal"], df["total_cal"], color=PAL["orange"], alpha=0.5, label="Active")
        ax.set_title("Calories", fontweight="bold"); ax.legend(loc="upper left"); fmt_dates(ax)

        # Distance
        ax = fig.add_subplot(gs[3, 1])
        ax.fill_between(df.index, 0, df["distance_km"], color=PAL["cyan"], alpha=0.3)
        ax.plot(df.index, df["distance_km"], color=PAL["cyan"], lw=1.5)
        ax.set_title("Distance (km)", fontweight="bold"); fmt_dates(ax)

        pdf.savefig(fig); plt.close(fig)

        # ── Page 2: Analysis + insights ──
        fig2 = plt.figure(figsize=(11.7, 16.5))
        fig2.suptitle("Deep Dive", fontsize=16, fontweight="bold",
                      color=PAL["cyan"], y=0.98)
        gs2 = GridSpec(4, 2, figure=fig2, hspace=0.38, wspace=0.28,
                       left=0.08, right=0.96, top=0.94, bottom=0.04)

        # Stress vs BB scatter
        ax = fig2.add_subplot(gs2[0, 0])
        sc = df[(df["avg_stress"] > 0) & df["bb_highest"].notna()]
        ax.scatter(sc["avg_stress"], sc["bb_highest"], c=PAL["violet"], alpha=0.7, s=40)
        if len(sc) >= 5:
            z = np.polyfit(sc["avg_stress"], sc["bb_highest"], 1)
            xs = np.linspace(sc["avg_stress"].min(), sc["avg_stress"].max(), 50)
            ax.plot(xs, np.polyval(z, xs), color=PAL["violet"], ls="--", lw=1.2)
        ax.set_title("Stress vs BB Peak", fontweight="bold")
        ax.set_xlabel("Avg Stress"); ax.set_ylabel("BB Peak")

        # Respiration
        ax = fig2.add_subplot(gs2[0, 1])
        rv = df[df["avg_resp"].notna()]
        ax.fill_between(rv.index, rv["low_resp"], rv["high_resp"], color=PAL["violet"], alpha=0.15)
        ax.plot(rv.index, rv["avg_resp"], color=PAL["violet"], lw=2)
        ax.set_title("Respiration", fontweight="bold"); ax.set_ylabel("breaths/min"); fmt_dates(ax)

        # Stress composition
        ax = fig2.add_subplot(gs2[1, :])
        cv = df[df["rest_min"].notna()]
        bottom = np.zeros(len(cv))
        for col, label, clr in [
            ("rest_min", "Rest", PAL["green"]), ("stress_low_min", "Low", PAL["cyan"]),
            ("stress_med_min", "Medium", PAL["orange"]), ("stress_high_min", "High", PAL["red"]),
        ]:
            vals = cv[col].fillna(0).values
            ax.bar(cv.index, vals, bottom=bottom, color=clr, alpha=0.7, label=label, width=0.8)
            bottom += vals
        ax.set_title("Stress Time Composition", fontweight="bold"); ax.set_ylabel("minutes")
        ax.legend(loc="upper left", fontsize=7); fmt_dates(ax)

        # Fitness age
        if fa_df is not None and len(fa_df) > 1:
            ax = fig2.add_subplot(gs2[2, 0])
            ax.plot(fa_df.index, fa_df["chrono_age"], color=PAL["muted"], ls="--", label="Chrono")
            ax.plot(fa_df.index, fa_df["bio_age"], color=PAL["green"], lw=2, label="Bio")
            ax.set_title("Bio vs Chrono Age", fontweight="bold"); ax.legend(); fmt_dates(ax)

        # Summary text
        ax = fig2.add_subplot(gs2[3, :])
        ax.axis("off")
        txt = (
            f"SUMMARY\n{'─'*60}\n"
            f"Steps: avg {a['avg_steps']:,}  median {a['median_steps']:,}  max {a['max_steps']:,}  goal {a['goal_pct']:.0f}%\n"
            f"Distance: {a['total_km']:.1f} km   RHR: {a['avg_rhr']:.0f} bpm (trend {a['rhr_trend']:+.1f}/wk)\n"
            f"Stress: {a['avg_stress']:.0f}/100   BB: peak {a['avg_bb_high']:.0f} trough {a['avg_bb_low']:.0f}\n"
            f"Correlation stress↔BB: r={a['r_stress_bb']:.2f}\n"
        )
        if a["insights"]:
            txt += f"\n{'─'*60}\n" + "\n".join(f"  • {i}" for i in a["insights"])
        ax.text(0.02, 0.95, txt, transform=ax.transAxes, fontsize=9, fontfamily="monospace",
                color=PAL["text"], va="top",
                bbox=dict(boxstyle="round,pad=0.6", fc=PAL["card"], ec=PAL["grid"]))

        pdf.savefig(fig2); plt.close(fig2)

        # ── Page 3: Session cross-reference ──
        if sessions_df is not None and len(sessions_df) and sessions_df["stress_points"].gt(0).any():
            fig3 = plt.figure(figsize=(11.7, 16.5))
            fig3.suptitle("Sessions × Biometrics", fontsize=16, fontweight="bold",
                          color=PAL["cyan"], y=0.98)
            gs3 = GridSpec(3, 2, figure=fig3, hspace=0.40, wspace=0.28,
                           left=0.08, right=0.96, top=0.94, bottom=0.06)

            valid = sessions_df[sessions_df["stress_points"] > 0]
            x = np.arange(len(valid))
            w = 0.25
            labels = [f"{r['date'][5:]}\n{r['playlist']}" for _, r in valid.iterrows()]

            # Stress bars
            ax = fig3.add_subplot(gs3[0, :])
            ax.bar(x - w, valid["pre_stress_mean"].fillna(0), w, color=PAL["muted"], alpha=0.7, label="Pre")
            ax.bar(x, valid["stress_mean"].fillna(0), w, color=PAL["orange"], alpha=0.8, label="During")
            ax.bar(x + w, valid["post_stress_mean"].fillna(0), w, color=PAL["cyan"], alpha=0.7, label="Post")
            ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=7)
            ax.set_title("Session Stress: Pre / During / Post", fontweight="bold")
            ax.legend(loc="upper right", fontsize=7)

            # HR bars
            ax = fig3.add_subplot(gs3[1, :])
            has_hr = valid[valid["hr_points"] > 0]
            if len(has_hr):
                x2 = np.arange(len(has_hr))
                lbls2 = [f"{r['date'][5:]}\n{r['playlist']}" for _, r in has_hr.iterrows()]
                ax.bar(x2 - w, has_hr["pre_hr_mean"].fillna(0), w, color=PAL["muted"], alpha=0.7, label="Pre")
                ax.bar(x2, has_hr["hr_mean"].fillna(0), w, color=PAL["pink"], alpha=0.8, label="During")
                ax.bar(x2 + w, has_hr["post_hr_mean"].fillna(0), w, color=PAL["cyan"], alpha=0.7, label="Post")
                ax.set_xticks(x2); ax.set_xticklabels(lbls2, fontsize=7)
            ax.set_title("Session HR: Pre / During / Post", fontweight="bold")
            ax.legend(loc="upper right", fontsize=7)

            # Mood vs stress scatter
            ax = fig3.add_subplot(gs3[2, 0])
            valid = valid.copy()
            valid["mood_delta"] = valid["mood_after_score"] - valid["mood_before_score"]
            for pl, clr, mk in [("Energy", PAL["orange"], "^"), ("Calm", PAL["cyan"], "o")]:
                sub = valid[valid["playlist"] == pl]
                if len(sub):
                    ax.scatter(sub["stress_delta"].fillna(0), sub["mood_delta"],
                               c=clr, marker=mk, s=80, alpha=0.8, label=pl)
            ax.axhline(0, color=PAL["muted"], ls=":", lw=0.8, alpha=0.5)
            ax.axvline(0, color=PAL["muted"], ls=":", lw=0.8, alpha=0.5)
            ax.set_xlabel("Stress Δ (post−pre)"); ax.set_ylabel("Mood Δ (after−before)")
            ax.set_title("Mood vs Stress Change", fontweight="bold"); ax.legend(fontsize=8)

            pdf.savefig(fig3); plt.close(fig3)

    print(f"  → PDF: {out_path}")


# ── Main ────────────────────────────────────────────────────────────────────

def run(export_dir: Path, out_dir: Path,
        checkin_path: Path | None = None, code: str | None = None,
        months: int = 6):

    print(f"garmin_pipeline — {export_dir}\n")

    # 1. Find files
    jsons = sorted(export_dir.rglob("*.json"))
    zips  = sorted(export_dir.rglob("*.zip"))
    print(f"  Found {len(jsons)} JSON, {len(zips)} ZIP files")

    # Determine date range: from check-in CSV if available, else last N months
    import datetime as _dt
    date_end = _dt.datetime.now()
    date_start = date_end - _dt.timedelta(days=months * 30)

    if checkin_path and code:
        try:
            _ck = pd.read_csv(checkin_path)
            _sess = _ck[_ck["Deelnemerscode"].str.lower() == code.lower()]
            _dates = fix_checkin_dates(_sess)
            if len(_dates):
                date_start = (_dates.min() - _dt.timedelta(days=30)).to_pydatetime()
                date_end   = (_dates.max() + _dt.timedelta(days=7)).to_pydatetime()
        except Exception:
            pass

    print(f"  Date range: {date_start:%Y-%m-%d} → {date_end:%Y-%m-%d}\n")

    # 2. Extract daily JSON (only files overlapping the date range)
    daily_df = fa_df = None
    for p in jsons:
        name = p.name.lower()
        if "udsfile" in name:
            # Try to parse date range from filename: UDSFile_YYYY-MM-DD_YYYY-MM-DD.json
            parts = p.stem.split("_")
            skip = False
            if len(parts) >= 3:
                try:
                    file_end = _dt.datetime.strptime(parts[-1], "%Y-%m-%d")
                    file_start = _dt.datetime.strptime(parts[-2], "%Y-%m-%d")
                    if file_end < date_start or file_start > date_end:
                        skip = True
                except ValueError:
                    pass
            if skip:
                continue
            print(f"  Extracting daily summaries: {p.name}")
            chunk = extract_daily(p)
            daily_df = chunk if daily_df is None else pd.concat([daily_df, chunk])
        elif "fitnessagedata" in name:
            print(f"  Extracting fitness age: {p.name}")
            fa_df = extract_fitness_age(p)

    if daily_df is None or daily_df.empty:
        sys.exit("✗ No UDS data found.")

    # Deduplicate in case UDS files overlap
    daily_df = daily_df[~daily_df.index.duplicated(keep="last")].sort_index()
    print(f"  → {len(daily_df)} daily records")

    # 3. Extract minute-level FIT
    stress_df = hr_df = pd.DataFrame()
    if zips:
        print(f"\n  Parsing FIT files...")
        stress_df, hr_df = extract_fit_files(zips, date_range=(date_start, date_end))

    # 4. Transform
    df = transform(daily_df)
    print(f"\n  {len(df)} valid days after transform")

    # 5. Analyze
    analysis = analyze(df)
    print(f"  Steps: {analysis['avg_steps']:,}  RHR: {analysis['avg_rhr']:.0f}  Stress: {analysis['avg_stress']:.0f}")
    for ins in analysis["insights"]:
        print(f"  💡 {ins}")

    # 6. Cross-reference sessions
    sessions_df = None
    traces = []
    if checkin_path and code:
        print(f"\n  Cross-referencing '{code}' sessions (±60 min)...")
        sessions_df, traces = crossref_sessions(checkin_path, code, stress_df, hr_df)
        n = sessions_df["stress_points"].gt(0).sum() if len(sessions_df) else 0
        print(f"  {n}/{len(sessions_df)} sessions matched")

    # 7. Write outputs
    out_dir.mkdir(parents=True, exist_ok=True)

    df.to_csv(out_dir / "garmin_daily.csv")
    print(f"\n  → garmin_daily.csv")

    if len(stress_df):
        stress_df.to_csv(out_dir / "garmin_minute_stress.csv")
        print(f"  → garmin_minute_stress.csv")
    if len(hr_df):
        hr_df.to_csv(out_dir / "garmin_minute_hr.csv")
        print(f"  → garmin_minute_hr.csv")

    if sessions_df is not None and len(sessions_df):
        sessions_df.to_csv(out_dir / "session_biometrics.csv", index=False)
        print(f"  → session_biometrics.csv")

    if traces:
        tdir = out_dir / "session_traces"
        tdir.mkdir(exist_ok=True)
        all_valid = []
        for t in traces:
            has_data = t.get("stress", pd.Series()).notna().any() or t.get("heart_rate", pd.Series()).notna().any()
            if has_data:
                all_valid.append(t)
                t.to_csv(tdir / f"trace_{t['session_date'].iloc[0]}_{t['playlist'].iloc[0].lower()}.csv")
        if all_valid:
            pd.concat(all_valid).to_csv(out_dir / "session_traces_all.csv")
            print(f"  → session_traces/ ({len(all_valid)} files)")

    render_pdf(df, analysis, fa_df, sessions_df, out_dir / "garmin_vitals_report.pdf")

    print("\n✓ Done.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Garmin pipeline for R.E.M. study",
        usage="%(prog)s <participant_code> [options]",
    )
    p.add_argument("code", type=str, help="Participant codename (e.g. kokosnoot)")
    p.add_argument("--root", type=Path, default=None,
                   help="Project root (auto-detected from script location)")
    p.add_argument("--export", type=Path, default=None,
                   help="Override: path to unzipped Garmin export")
    p.add_argument("--checkin", type=Path, default=None,
                   help="Override: path to check-in CSV")
    p.add_argument("--out", type=Path, default=None,
                   help="Override: output directory")
    p.add_argument("--months", type=int, default=6,
                   help="How many months of data to process (default: 6)")
    args = p.parse_args()

    # Auto-detect project root: script lives in <root>/scripts/wearables/
    root = args.root or Path(__file__).resolve().parent.parent.parent
    if not (root / "data").exists():
        sys.exit(f"✗ Can't find project root (tried {root}). Use --root.")

    code = args.code
    base = root / "data" / "wearables" / code

    export_dir  = args.export  or base / "raw" / "export"
    out_dir     = args.out     or base / "processed"
    checkin     = args.checkin or next(
        (root / "data" / "checkins").glob("*.csv"), None
    )

    if not export_dir.exists():
        sys.exit(f"✗ Export not found: {export_dir}\n"
                 f"  Place the unzipped Garmin export there, or use --export.")

    if checkin and not checkin.exists():
        checkin = None

    run(export_dir, out_dir, checkin, code, args.months)
