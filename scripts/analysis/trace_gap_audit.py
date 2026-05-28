"""
trace_gap_audit.py -- Validate per-session biometric data gaps for Project R.E.M.

For each participant × session, reports:
  - Total minutes in trace
  - Stress-filled minutes (non-null)
  - Fill percentage during the "during" phase window
  - Largest contiguous gap (in minutes)
  - Whether the gap falls within the session window (during-phase)

This script is a one-shot diagnostic tool. Run it to confirm that stress data
gaps are genuine wearable limitations (watch removed, charging, swimming)
rather than pipeline processing errors.

Usage:
    uv run python scripts/analysis/trace_gap_audit.py
    uv run python scripts/analysis/trace_gap_audit.py --participant kokosnoot peer
    uv run python scripts/analysis/trace_gap_audit.py --csv  # export to gap_audit.csv
"""
import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent.parent
DATA = ROOT / "data"

PARTICIPANTS = ["bosbes", "kiwi", "kokosnoot", "limoen", "peer", "watermeloen"]


def largest_gap_minutes(series: pd.Series) -> float:
    """Return the length (in rows ≈ minutes) of the longest contiguous null run."""
    if series.notna().all():
        return 0.0
    null_mask  = series.isna()
    max_gap    = 0
    current    = 0
    for v in null_mask:
        if v:
            current += 1
            max_gap = max(max_gap, current)
        else:
            current = 0
    return float(max_gap)


def audit_participant(participant: str) -> list[dict]:
    trace_dir = DATA / "wearables" / participant / "processed" / "session_traces"
    if not trace_dir.exists():
        return []

    records = []
    for f in sorted(trace_dir.glob("trace_*.csv")):
        parts    = f.stem.split("_")
        date_str = parts[1] if len(parts) > 1 else "unknown"
        playlist = parts[2] if len(parts) > 2 else "unknown"

        try:
            df = pd.read_csv(f)
        except Exception as e:
            records.append({
                "participant": participant,
                "date":        date_str,
                "playlist":    playlist,
                "error":       str(e),
            })
            continue

        total_rows   = len(df)
        during       = df[df["phase"] == "during"] if "phase" in df.columns else df
        dur_rows     = len(during)
        dur_filled   = int(during["stress"].notna().sum()) if "stress" in during.columns else 0
        dur_fill_pct = round(dur_filled / dur_rows * 100, 1) if dur_rows > 0 else 0.0
        total_filled = int(df["stress"].notna().sum()) if "stress" in df.columns else 0
        total_fill_pct = round(total_filled / total_rows * 100, 1) if total_rows > 0 else 0.0
        max_gap      = largest_gap_minutes(df["stress"]) if "stress" in df.columns else 0.0
        during_gap   = largest_gap_minutes(during["stress"]) if "stress" in during.columns else 0.0

        records.append({
            "participant":      participant,
            "date":             date_str,
            "playlist":         playlist,
            "total_rows":       total_rows,
            "total_fill_pct":   total_fill_pct,
            "during_rows":      dur_rows,
            "during_fill_pct":  dur_fill_pct,
            "max_gap_total":    max_gap,
            "max_gap_during":   during_gap,
            "status":           "OK" if dur_fill_pct >= 80 else ("PARTIAL" if dur_fill_pct >= 40 else "SPARSE"),
        })
    return records


def main():
    parser = argparse.ArgumentParser(description="Audit per-session stress data gaps.")
    parser.add_argument("--participant", nargs="+", default=None,
                        help="Limit to specific participants (default: all)")
    parser.add_argument("--csv", action="store_true",
                        help="Export results to data/analysis/gap_audit.csv")
    args = parser.parse_args()

    participants = args.participant or PARTICIPANTS
    all_records  = []

    for p in participants:
        records = audit_participant(p)
        if not records:
            print(f"\n[{p}] — geen sessie-traces gevonden (data/wearables/{p}/processed/session_traces/)")
            continue

        print(f"\n{'='*60}")
        print(f"  {p.upper()}  ({len(records)} sessies)")
        print(f"{'='*60}")
        print(f"{'Datum':<12} {'Playlist':<10} {'Totaal%':>8} {'Tijdens%':>9} {'MaxGap(tot)':>12} {'MaxGap(dur)':>12} {'Status':<8}")
        print("-" * 70)
        for r in records:
            if "error" in r:
                print(f"{r['date']:<12} ERROR: {r['error']}")
                continue
            print(
                f"{r['date']:<12} {r['playlist']:<10} "
                f"{r['total_fill_pct']:>7.1f}% "
                f"{r['during_fill_pct']:>8.1f}% "
                f"{r['max_gap_total']:>11.0f}m "
                f"{r['max_gap_during']:>11.0f}m "
                f"{r['status']:<8}"
            )
        all_records.extend(records)

    if all_records:
        sparse = [r for r in all_records if r.get("status") == "SPARSE"]
        partial = [r for r in all_records if r.get("status") == "PARTIAL"]
        ok = [r for r in all_records if r.get("status") == "OK"]
        print(f"\n{'='*60}")
        print(f"  SAMENVATTING")
        print(f"  OK (≥80%): {len(ok)}  |  PARTIAL (40-79%): {len(partial)}  |  SPARSE (<40%): {len(sparse)}")
        print(f"{'='*60}")

        if sparse:
            print("\n  SPARSE sessies (mogelijk horloge afgedaan of opladen):")
            for r in sparse:
                print(f"    {r['participant']:>12} {r['date']}  {r['during_fill_pct']:.1f}% gevuld tijdens sessie")

    if args.csv and all_records:
        out = DATA / "analysis" / "gap_audit.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([r for r in all_records if "error" not in r]).to_csv(out, index=False)
        print(f"\n  Audit opgeslagen: {out}")


if __name__ == "__main__":
    main()
