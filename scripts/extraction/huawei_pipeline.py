#!/usr/bin/env python3
"""
huawei_pipeline.py — Extract, transform, and analyze Huawei Health GDPR exports.
Cross-references minute-level biometrics with R.E.M. study check-in sessions.

Tested with: Huawei GT3 (Watch GT 3). Should work with any Huawei Health export.

Usage:
    python huawei_pipeline.py <participant_code> [options]

Dependencies:
    Required:  pandas, numpy
    Optional:  matplotlib (for PDF report)
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Allow direct execution from any working directory
sys.path.insert(0, str(Path(__file__).parent))

from utils import (
    get_date_range_from_checkins,
    crossref_sessions,
    write_session_traces,
)


# ── Extract: Health detail data (HR, Stress, SpO2) ─────────────────────────

HEALTH_TYPES = {
    3: "sleep", 7: "heart_rate", 9: "sleep_analyzed",
    11: "stress", 12: "exercise_intensity", 16: "spo2",
}

HR_KEYS = {"DATA_POINT_DYNAMIC_HEARTRATE", "HEARTRATE_RATE"}
RESTING_HR_KEYS = {"DATA_POINT_REST_HEARTRATE", "DATA_POINT_NEW_REST_HEARTRATE"}


def _ms_to_datetime(ms):
    """Convert millisecond epoch (UTC) to timezone-naive datetime."""
    return pd.Timestamp(ms, unit="ms", tz="UTC").tz_localize(None)


def extract_health_detail(json_files: list[Path], date_range=None):
    """Parse all health detail JSONs into HR and stress DataFrames.

    Huawei stores millisecond timestamps in UTC.

    Returns (hr_df, stress_df, rhr_df), all indexed by UTC timestamp.
    """
    hr_rows = []
    resting_hr_rows = []
    stress_rows = []

    for fp in json_files:
        try:
            with open(fp) as f:
                records = json.load(f)
        except Exception:
            continue

        if not isinstance(records, list):
            continue

        for rec in records:
            rec_type = rec.get("type")
            start_ms = rec.get("startTime", 0)

            if date_range and start_ms:
                ts = pd.Timestamp(start_ms, unit="ms")
                if ts < date_range[0] or ts > date_range[1]:
                    continue

            for sp in rec.get("samplePoints", []):
                key = sp.get("key", "")
                val_str = sp.get("value", "")
                sp_start = sp.get("startTime", start_ms)

                try:
                    ts = _ms_to_datetime(sp_start)
                except Exception:
                    continue

                if key in HR_KEYS:
                    try:
                        hr = float(val_str)
                        if 30 < hr < 220:
                            hr_rows.append({"timestamp": ts, "heart_rate": int(hr)})
                    except (ValueError, TypeError):
                        pass

                elif key in RESTING_HR_KEYS:
                    try:
                        rhr = float(val_str)
                        if 30 < rhr < 150:
                            resting_hr_rows.append({"timestamp": ts, "resting_hr": int(rhr)})
                    except (ValueError, TypeError):
                        pass

                elif rec_type == 11 and key == "STRESS_DATA":
                    try:
                        payload = json.loads(val_str)
                        score = int(payload["score"])
                        if 1 <= score <= 99:
                            stress_rows.append({"timestamp": ts, "stress": score})
                    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
                        pass

    hr_df = pd.DataFrame(hr_rows or [], columns=["timestamp", "heart_rate"])
    if not hr_df.empty:
        hr_df = hr_df.drop_duplicates("timestamp").sort_values("timestamp").set_index("timestamp")

    stress_df = pd.DataFrame(stress_rows or [], columns=["timestamp", "stress"])
    if not stress_df.empty:
        stress_df = stress_df.drop_duplicates("timestamp").sort_values("timestamp").set_index("timestamp")

    rhr_df = pd.DataFrame(resting_hr_rows or [], columns=["timestamp", "resting_hr"])
    if not rhr_df.empty:
        rhr_df = rhr_df.drop_duplicates("timestamp").sort_values("timestamp").set_index("timestamp")

    return hr_df, stress_df, rhr_df


# ── Extract: Sport per minute merged data ───────────────────────────────────

def extract_sport_per_minute(json_files: list[Path], date_range=None):
    """Parse sport per minute JSONs into a daily summary DataFrame."""
    rows = []

    for fp in json_files:
        try:
            with open(fp) as f:
                days = json.load(f)
        except Exception:
            continue

        if not isinstance(days, list):
            continue

        for day_rec in days:
            record_day = day_rec.get("recordDay")
            if not record_day:
                continue

            date_str = str(record_day)
            date = pd.Timestamp(f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}")

            if date_range and (date < date_range[0] or date > date_range[1]):
                continue

            day_steps = day_distance = day_calories = 0
            for entry in day_rec.get("sportDataUserData", []):
                for info in entry.get("sportBasicInfos", []):
                    day_steps    += info.get("steps", 0)
                    day_distance += info.get("distance", 0)
                    day_calories += info.get("calorie", 0)

            rows.append({
                "date":       date,
                "steps":      day_steps,
                "distance_m": day_distance,
                "calories":   round(day_calories / 1000, 1) if day_calories else 0,
            })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.groupby("date").sum().sort_index()
    return df


# ── Transform ───────────────────────────────────────────────────────────────

def build_daily(hr_df, stress_df, rhr_df, sport_df):
    """Combine all data sources into a daily summary."""
    all_dates = set()
    for df in [hr_df, stress_df, rhr_df]:
        if not df.empty:
            all_dates.update(df.index.date)
    if sport_df is not None and not sport_df.empty:
        all_dates.update(sport_df.index.date if hasattr(sport_df.index, "date") else [])

    if not all_dates:
        return pd.DataFrame()

    rows = []
    for date in sorted(all_dates):
        date_str = str(date)
        day_start = pd.Timestamp(date_str)
        day_end = day_start + pd.Timedelta(days=1)

        day_hr     = hr_df.loc[day_start:day_end]["heart_rate"] if not hr_df.empty else pd.Series(dtype=float)
        day_stress = stress_df.loc[day_start:day_end]["stress"] if not stress_df.empty else pd.Series(dtype=float)
        day_rhr    = rhr_df.loc[day_start:day_end]["resting_hr"] if not rhr_df.empty else pd.Series(dtype=float)

        steps = distance = calories = None
        if sport_df is not None and not sport_df.empty:
            try:
                sport_row = sport_df.loc[day_start]
                steps    = sport_row.get("steps", 0)
                distance = sport_row.get("distance_m", 0)
                calories = sport_row.get("calories", 0)
            except KeyError:
                pass

        rows.append({
            "date":            pd.Timestamp(date),
            "steps":           steps if steps and steps > 0 else None,
            "distance_m":      distance,
            "total_cal":       calories,
            "resting_hr":      int(day_rhr.median()) if len(day_rhr) else None,
            "min_hr":          int(day_hr.min()) if len(day_hr) else None,
            "max_hr":          int(day_hr.max()) if len(day_hr) else None,
            "avg_hr":          round(day_hr.mean(), 1) if len(day_hr) else None,
            "hr_readings":     len(day_hr),
            "avg_stress":      round(day_stress.mean(), 1) if len(day_stress) else None,
            "max_stress":      int(day_stress.max()) if len(day_stress) else None,
            "min_stress":      int(day_stress.min()) if len(day_stress) else None,
            "stress_readings": len(day_stress),
        })

    df = pd.DataFrame(rows).set_index("date").sort_index()
    df["distance_km"] = (df["distance_m"] / 1000).round(2) if "distance_m" in df else None

    for col in ["avg_stress", "resting_hr", "steps"]:
        if col in df.columns:
            df[f"{col}_7d"] = df[col].rolling(7, min_periods=3).mean().round(1)

    return df


# ── Analyze ─────────────────────────────────────────────────────────────────

def analyze(df):
    """Compute summary statistics."""
    valid = df.dropna(subset=["steps"])
    stress_valid = df[df["avg_stress"].notna() & (df["avg_stress"] > 0)]

    rhr = df["resting_hr"].dropna()
    rhr_trend = 0.0
    if len(rhr) >= 5:
        rhr_trend = round(np.polyfit(range(len(rhr)), rhr.values, 1)[0] * 7, 2)

    a = {
        "n_days":     len(valid),
        "date_range": f"{df.index.min():%Y-%m-%d} → {df.index.max():%Y-%m-%d}" if len(df) else "n/a",
        "avg_steps":  int(valid["steps"].mean()) if len(valid) else 0,
        "max_steps":  int(valid["steps"].max()) if len(valid) else 0,
        "total_km":   round(valid["distance_km"].sum(), 1) if "distance_km" in valid else 0,
        "avg_rhr":    round(rhr.mean(), 1) if len(rhr) else 0,
        "rhr_trend":  rhr_trend,
        "avg_stress": round(stress_valid["avg_stress"].mean(), 1) if len(stress_valid) else 0,
        "insights":   [],
    }

    if rhr_trend > 0.5:
        a["insights"].append(f"RHR trending up {rhr_trend:+.1f} bpm/week.")
    if a["avg_stress"] > 40:
        a["insights"].append(f"Average stress ({a['avg_stress']:.0f}) is elevated.")

    return a


# ── PDF Report ───────────────────────────────────────────────────────────────

def render_pdf(daily_df, analysis, sessions_df, out_path):
    """Generate PDF report. Skipped if matplotlib unavailable."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib.backends.backend_pdf import PdfPages
        from matplotlib.gridspec import GridSpec
    except ImportError:
        print("  ⚠ matplotlib not installed — skipping PDF")
        return

    PAL = {
        "bg": "#0f1218", "card": "#181e2a", "grid": "#232b3a",
        "text": "#c9d1d9", "muted": "#586475", "cyan": "#22d3ee",
        "violet": "#a78bfa", "pink": "#f472b6", "green": "#34d399",
        "orange": "#fb923c", "red": "#f87171",
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

    def fmt(ax):
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

    df = daily_df
    a = analysis

    with PdfPages(out_path) as pdf:
        fig = plt.figure(figsize=(11.7, 16.5))
        fig.suptitle("Huawei Health Report", fontsize=16, fontweight="bold",
                     color=PAL["cyan"], y=0.98)
        fig.text(0.5, 0.965, f"{a['date_range']}  ·  {a['n_days']} days",
                 ha="center", fontsize=9, color=PAL["muted"])
        gs = GridSpec(3, 2, figure=fig, hspace=0.38, wspace=0.28,
                      left=0.08, right=0.96, top=0.94, bottom=0.06)

        ax = fig.add_subplot(gs[0, :])
        valid = df[df["steps"].notna()]
        ax.bar(valid.index, valid["steps"], color=PAL["cyan"], alpha=0.8, width=0.8)
        if "steps_7d" in valid:
            ax.plot(valid.index, valid["steps_7d"], color=PAL["orange"], lw=2, label="7d avg")
        ax.set_title("Daily Steps", fontweight="bold"); ax.legend(loc="upper left"); fmt(ax)

        ax = fig.add_subplot(gs[1, 0])
        hr_valid = df[df["min_hr"].notna()]
        if len(hr_valid):
            ax.fill_between(hr_valid.index, hr_valid["min_hr"], hr_valid["max_hr"],
                            color=PAL["pink"], alpha=0.12)
            if hr_valid["resting_hr"].notna().any():
                ax.plot(hr_valid.index, hr_valid["resting_hr"], color=PAL["pink"], lw=2, label="Resting")
            ax.set_title("Heart Rate", fontweight="bold"); ax.set_ylabel("bpm")
            ax.legend(loc="upper left"); fmt(ax)

        ax = fig.add_subplot(gs[1, 1])
        sv = df[df["avg_stress"].notna() & (df["avg_stress"] > 0)]
        if len(sv):
            ax.bar(sv.index, sv["avg_stress"], color=PAL["orange"], alpha=0.7, width=0.8)
            ax.plot(sv.index, sv["max_stress"], color=PAL["red"], lw=1, marker=".", ms=3, label="Peak")
            ax.axhline(35, color=PAL["muted"], ls="--", lw=0.8, alpha=0.6)
            ax.set_title("Stress", fontweight="bold"); ax.set_ylim(0, 100)
            ax.legend(loc="upper left"); fmt(ax)

        ax = fig.add_subplot(gs[2, :])
        ax.axis("off")
        txt = (
            f"SUMMARY\n{'─'*50}\n"
            f"Steps: avg {a['avg_steps']:,}  max {a['max_steps']:,}\n"
            f"Distance: {a['total_km']:.1f} km\n"
            f"RHR: {a['avg_rhr']:.0f} bpm (trend {a['rhr_trend']:+.1f}/wk)\n"
            f"Stress: {a['avg_stress']:.0f}/100\n"
        )
        if a["insights"]:
            txt += f"\n{'─'*50}\n" + "\n".join(f"  • {i}" for i in a["insights"])
        ax.text(0.02, 0.95, txt, transform=ax.transAxes, fontsize=9, fontfamily="monospace",
                color=PAL["text"], va="top",
                bbox=dict(boxstyle="round,pad=0.6", fc=PAL["card"], ec=PAL["grid"]))

        pdf.savefig(fig); plt.close(fig)

        if sessions_df is not None and len(sessions_df) and (
            sessions_df["stress_points"].gt(0) | sessions_df["hr_points"].gt(0)
        ).any():
            fig2 = plt.figure(figsize=(11.7, 16.5))
            fig2.suptitle("Sessions × Biometrics", fontsize=16, fontweight="bold",
                          color=PAL["cyan"], y=0.98)
            gs2 = GridSpec(2, 1, figure=fig2, hspace=0.35,
                           left=0.08, right=0.96, top=0.94, bottom=0.06)

            valid = sessions_df[(sessions_df["stress_points"] > 0) | (sessions_df["hr_points"] > 0)]
            x = np.arange(len(valid))
            w = 0.25
            labels = [f"{r['date'][5:]}\n{r['playlist']}" for _, r in valid.iterrows()]

            ax = fig2.add_subplot(gs2[0])
            ax.bar(x - w, valid["pre_stress_mean"].fillna(0), w, color=PAL["muted"], alpha=0.7, label="Pre")
            ax.bar(x, valid["stress_mean"].fillna(0), w, color=PAL["orange"], alpha=0.8, label="During")
            ax.bar(x + w, valid["post_stress_mean"].fillna(0), w, color=PAL["cyan"], alpha=0.7, label="Post")
            ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=7)
            ax.set_title("Session Stress", fontweight="bold"); ax.legend(fontsize=7)

            ax = fig2.add_subplot(gs2[1])
            has_hr = valid[valid["hr_points"] > 0]
            if len(has_hr):
                x2 = np.arange(len(has_hr))
                lbls2 = [f"{r['date'][5:]}\n{r['playlist']}" for _, r in has_hr.iterrows()]
                ax.bar(x2 - w, has_hr["pre_hr_mean"].fillna(0), w, color=PAL["muted"], alpha=0.7, label="Pre")
                ax.bar(x2, has_hr["hr_mean"].fillna(0), w, color=PAL["pink"], alpha=0.8, label="During")
                ax.bar(x2 + w, has_hr["post_hr_mean"].fillna(0), w, color=PAL["cyan"], alpha=0.7, label="Post")
                ax.set_xticks(x2); ax.set_xticklabels(lbls2, fontsize=7)
            ax.set_title("Session HR", fontweight="bold"); ax.legend(fontsize=7)

            pdf.savefig(fig2); plt.close(fig2)

    print(f"  → PDF: {out_path}")


# ── Main ────────────────────────────────────────────────────────────────────

def run(export_dir, out_dir, checkin_path=None, code=None, months=6):
    print(f"huawei_pipeline — {export_dir}\n")

    # 1. Find files
    health_jsons = sorted(export_dir.rglob("health detail data*.json"))
    sport_jsons  = sorted(export_dir.rglob("sport per minute merged data*.json"))
    print(f"  Found {len(health_jsons)} health detail JSONs, {len(sport_jsons)} sport JSONs")

    # 2. Determine date range
    date_start, date_end = get_date_range_from_checkins(checkin_path, code or "", months)
    dr = (pd.Timestamp(date_start), pd.Timestamp(date_end))
    print(f"  Date range: {dr[0]:%Y-%m-%d} → {dr[1]:%Y-%m-%d}\n")

    # 3. Extract
    print("  Extracting health detail data...")
    hr_df, stress_df, rhr_df = extract_health_detail(health_jsons, date_range=dr)
    print(f"  HR: {len(hr_df)} readings, Stress: {len(stress_df)} readings, RHR: {len(rhr_df)} readings")
    if len(hr_df):
        print(f"  Range: {hr_df.index.min():%Y-%m-%d %H:%M} → {hr_df.index.max():%Y-%m-%d %H:%M} UTC")

    print("\n  Extracting sport per minute data...")
    sport_df = extract_sport_per_minute(sport_jsons, date_range=dr)
    print(f"  Sport: {len(sport_df)} days")

    # 4. Build daily summary
    daily_df = build_daily(hr_df, stress_df, rhr_df, sport_df)
    print(f"\n  {len(daily_df)} daily records")

    if daily_df.empty:
        sys.exit("✗ No data found in date range.")

    # 5. Analyze
    analysis = analyze(daily_df)
    print(f"  Steps: {analysis['avg_steps']:,}  RHR: {analysis['avg_rhr']:.0f}  Stress: {analysis['avg_stress']:.0f}")
    for ins in analysis["insights"]:
        print(f"  💡 {ins}")

    # 6. Cross-reference sessions (Huawei has no body battery)
    sessions_df = None
    traces = []
    if checkin_path and code:
        print(f"\n  Cross-referencing '{code}' sessions (±60 min)...")
        sessions_df, traces = crossref_sessions(
            checkin_path, code, stress_df, hr_df, has_body_battery=False
        )
        has_data = (sessions_df["stress_points"].gt(0) | sessions_df["hr_points"].gt(0))
        n = has_data.sum() if len(sessions_df) else 0
        print(f"  {n}/{len(sessions_df)} sessions matched")

    # 7. Write outputs
    out_dir.mkdir(parents=True, exist_ok=True)

    daily_df.to_csv(out_dir / "huawei_daily.csv")
    print(f"\n  → huawei_daily.csv")

    if len(stress_df):
        stress_df.to_csv(out_dir / "huawei_minute_stress.csv")
        print(f"  → huawei_minute_stress.csv")
    if len(hr_df):
        hr_df.to_csv(out_dir / "huawei_minute_hr.csv")
        print(f"  → huawei_minute_hr.csv")

    if sessions_df is not None and len(sessions_df):
        sessions_df.to_csv(out_dir / "session_biometrics.csv", index=False)
        print(f"  → session_biometrics.csv")

    write_session_traces(traces, out_dir)

    render_pdf(daily_df, analysis, sessions_df, out_dir / "huawei_vitals_report.pdf")

    print("\n✓ Done.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Huawei Health pipeline for R.E.M. study",
        usage="%(prog)s <participant_code> [options]",
    )
    p.add_argument("code", type=str, help="Participant codename (e.g. limoen)")
    p.add_argument("--root", type=Path, default=None)
    p.add_argument("--export", type=Path, default=None)
    p.add_argument("--checkin", type=Path, default=None)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--months", type=int, default=6)
    args = p.parse_args()

    root = args.root or Path(__file__).resolve().parent.parent.parent
    if not (root / "data").exists():
        sys.exit(f"✗ Can't find project root (tried {root}). Use --root.")

    code = args.code
    base = root / "data" / "wearables" / code

    export_dir = args.export or base / "raw" / "export"
    out_dir    = args.out    or base / "processed"
    checkin    = args.checkin or next(
        (f for f in (root / "data" / "checkins").glob("*.csv")
         if not f.name.startswith("_")), None
    )

    if not export_dir.exists():
        sys.exit(f"✗ Export not found: {export_dir}\n"
                 f"  Place the unzipped Huawei export there, or use --export.")

    if checkin and not checkin.exists():
        checkin = None

    run(export_dir, out_dir, checkin, code, args.months)
