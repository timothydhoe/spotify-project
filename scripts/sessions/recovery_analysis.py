"""
recovery_analysis.py — Recovery curve quality filtering, export, and visualisation.

Converted from notebooks/recovery_analysis.ipynb.

Reads session_effects.csv and recovery_baselines.csv per participant, applies
quality filters, exports recovery_features.csv with a 'reliable' flag, and
generates per-participant recovery window plots.

Quality filters:
    1. r2_actual > R2_THRESHOLD  — the session curve fit is good enough to trust tau_actual
    2. pre_stress_mean >= asymptote — stress was elevated before the session; otherwise
       the exponential model has nowhere to go and produces an artefact

Outputs:
    data/analysis/recovery_features.csv          — all sessions with reliable flag
    data/analysis/recovery_features_summary.csv  — per-participant mean advantage
    data/analysis/recovery_windows_{codename}.png — per-participant baseline plot

Usage:
    python scripts/sessions/recovery_analysis.py
    python scripts/sessions/recovery_analysis.py --participants bosbes peer
    python scripts/sessions/recovery_analysis.py --r2-threshold 0.1
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import curve_fit, OptimizeWarning

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from baseline.baselines import _fit_exp_decay

# ── Paths ────────────────────────────────────────────────────────────────────

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
ANALYSIS_ROOT = DATA_ROOT / "analysis"
WEARABLES_DIR = DATA_ROOT / "wearables"

PARTICIPANTS = [
    "bosbes", "citroen", "kiwi", "kokosnoot",
    "limoen", "peer", "watermeloen", "aardbei",
]

# Default quality threshold — see notebook discussion for scientific justification.
# Sessions with r2_actual below this are flagged unreliable but kept in the output.
DEFAULT_R2_THRESHOLD = 0.05

# Maximum recovery windows to plot per participant (keeps plots readable)
_MAX_WINDOWS = 8
_RECOVERY_WINDOW_MIN = 90
_MIN_RECOVERY_POINTS = 10

STATE_ORDER = {"Sleep": 0, "Rest": 1, "Light": 2, "Medium": 3, "Heavy": 4}


# ── Data loading ─────────────────────────────────────────────────────────────

def _load_participant(codename: str) -> dict:
    """Load session_effects.csv, recovery_baselines.csv, and classified_minutes.csv."""
    analysis_dir = ANALYSIS_ROOT / codename
    proc_dir = WEARABLES_DIR / codename / "processed"

    effects_path = analysis_dir / "session_effects.csv"
    baselines_path = analysis_dir / "recovery_baselines.csv"
    classified_path = analysis_dir / "classified_minutes.csv"

    data = {}

    if effects_path.exists():
        data["effects"] = pd.read_csv(effects_path, parse_dates=["date"])
        data["effects"]["participant"] = codename
    if baselines_path.exists():
        data["baselines"] = pd.read_csv(baselines_path)
    if classified_path.exists():
        data["classified"] = pd.read_csv(classified_path, index_col="timestamp", parse_dates=True)

    return data


# ── Quality filtering ─────────────────────────────────────────────────────────

def apply_quality_filter(
    effects: pd.DataFrame,
    baselines: pd.DataFrame | None,
    r2_threshold: float,
) -> pd.DataFrame:
    """Add a 'reliable' boolean column to effects based on two quality criteria.

    Criteria:
        1. r2_actual > r2_threshold  (session curve fit is trustworthy)
        2. pre_stress_mean >= asymptote  (stress was elevated; model has room to decay)

    Both criteria must pass for reliable=True. Sessions failing either are kept
    in the output with reliable=False — they are never silently dropped.
    """
    effects = effects.copy()

    # Build asymptote lookup per pre_state from baselines
    asym_map: dict[str, float] = {}
    if baselines is not None:
        stress_bl = baselines[baselines["signal"] == "stress"]
        for _, row in stress_bl.iterrows():
            asym_map[str(row["from_state"])] = float(row["asymptote"])

    if "asymptote" not in effects.columns:
        effects["asymptote"] = effects["pre_state"].map(asym_map)

    r2_ok = (
        effects["r2_actual"].isna() | (effects["r2_actual"] > r2_threshold)
    )
    pre_stress_ok = (
        effects["pre_stress_mean"].isna() |
        effects["asymptote"].isna() |
        (effects["pre_stress_mean"] >= effects["asymptote"])
    )

    effects["reliable"] = r2_ok & pre_stress_ok & effects["advantage"].notna()
    return effects


# ── Export ────────────────────────────────────────────────────────────────────

def build_recovery_features(
    all_data: dict[str, dict],
    r2_threshold: float,
) -> pd.DataFrame:
    """Pool all participants into recovery_features.csv with the reliable flag."""
    parts = []

    for codename, data in all_data.items():
        effects = data.get("effects")
        baselines = data.get("baselines")
        if effects is None or effects.empty:
            continue

        effects = apply_quality_filter(effects, baselines, r2_threshold)

        # Add t_90_min if not present
        if "t_90_min" not in effects.columns and "tau_actual" in effects.columns:
            effects["t_90_min"] = effects["tau_actual"] * 2.3

        # Normalise date column name
        if "session_date" not in effects.columns:
            if "date" in effects.columns:
                effects = effects.rename(columns={"date": "session_date"})

        preferred_cols = [
            "participant", "session_date", "playlist", "pre_state",
            "tau_actual", "tau_expected", "asymptote", "advantage",
            "r2_actual", "r2_expected", "t_90_min",
            "pre_stress_mean", "mood_delta", "reliable",
        ]
        present = [c for c in preferred_cols if c in effects.columns]
        parts.append(effects[present])

    if not parts:
        return pd.DataFrame()

    return pd.concat(parts, ignore_index=True)


# ── Plotting ──────────────────────────────────────────────────────────────────

def _ensure_agg_backend() -> None:
    import matplotlib
    matplotlib.use("Agg")


def plot_recovery_windows(
    codename: str,
    classified: pd.DataFrame,
    baselines: pd.DataFrame,
    effects: pd.DataFrame,
    output_dir: Path,
) -> None:
    """Per-participant: raw recovery windows on non-session days + fitted baseline curve."""
    _ensure_agg_backend()
    import matplotlib.pyplot as plt

    if "activity_state" not in classified.columns or "stress" not in classified.columns:
        return

    # Exclude session days
    session_dates: set = set()
    if "session_date" in effects.columns:
        session_dates = {pd.Timestamp(d).date() for d in effects["session_date"].dropna()}
    elif "date" in effects.columns:
        session_dates = {pd.Timestamp(d).date() for d in effects["date"].dropna()}

    non_session = classified[
        ~classified.index.to_series().apply(lambda ts: ts.date() in session_dates)
    ]

    # Find downward activity transitions on non-session days
    effort = non_session["activity_state"].map(STATE_ORDER).fillna(1)
    prev_effort = effort.shift(1)
    trans_times = non_session.index[effort < prev_effort]

    windows_by_state: dict[str, list] = {}
    for ts in trans_times:
        prev_ts = ts - pd.Timedelta(minutes=1)
        if prev_ts not in non_session.index:
            continue
        from_state = non_session.at[prev_ts, "activity_state"]
        stay_start = ts - pd.Timedelta(minutes=3)
        prior = non_session.loc[stay_start:prev_ts, "activity_state"]
        if len(prior) < 3 or not (prior == from_state).all():
            continue
        window_end = ts + pd.Timedelta(minutes=_RECOVERY_WINDOW_MIN)
        window = non_session.loc[ts:window_end, "stress"].dropna()
        if len(window) < _MIN_RECOVERY_POINTS:
            continue
        windows_by_state.setdefault(from_state, []).append(window)

    # Only plot states with a valid (non-saturated) baseline
    stress_bl = baselines[baselines["signal"] == "stress"]
    valid_bl = stress_bl[stress_bl["tau_min"] < 490]
    states_to_plot = [s for s in valid_bl["from_state"].values if s in windows_by_state]

    if not states_to_plot:
        return

    n_cols = len(states_to_plot)
    fig, axes = plt.subplots(1, n_cols, figsize=(5 * n_cols, 4), squeeze=False)
    fig.suptitle(
        f"{codename} — recovery windows on non-session days (grey) + fitted curve (white)",
        fontsize=11,
    )

    for j, state in enumerate(states_to_plot):
        ax = axes[0][j]
        bl_row = valid_bl[valid_bl["from_state"] == state].iloc[0]
        asymptote = float(bl_row["asymptote"])
        tau_bl = float(bl_row["tau_min"])
        n_obs = int(bl_row["n_obs"])
        r2_bl = float(bl_row["r_squared"])

        windows = windows_by_state[state][:_MAX_WINDOWS]
        for win in windows:
            t_win = np.arange(len(win), dtype=float)
            ax.plot(t_win, win.values, color="#586475", linewidth=0.8, alpha=0.35)

        t_full = np.arange(0, _RECOVERY_WINDOW_MIN + 1, 1.0)
        start_mean = float(np.mean([w.iloc[0] for w in windows])) if windows else asymptote + 20
        y_bl = asymptote + (start_mean - asymptote) * np.exp(-t_full / tau_bl)
        ax.plot(
            t_full, y_bl, color="white", linewidth=2.0, linestyle="--", alpha=0.9,
            label=f"τ={tau_bl:.0f} min (n={n_obs}, r²={r2_bl:.2f})",
        )
        ax.axhline(
            asymptote, color="#56B4E9", linewidth=1.0, linestyle=":", alpha=0.7,
            label=f"asymptote = {asymptote:.0f}",
        )
        ax.set_xlabel("Minutes after transition")
        ax.set_ylabel("Stress")
        ax.set_title(f"Pre-state: {state}  ({len(windows)} windows)", fontsize=10)
        ax.legend(fontsize=7, loc="upper right")

    plt.tight_layout()
    out_path = output_dir / f"recovery_windows_{codename}.png"
    plt.savefig(out_path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    print(f"  [{codename}] Recovery window plot → {out_path.name}")


# ── Summary stats ─────────────────────────────────────────────────────────────

def print_summary(df: pd.DataFrame, r2_threshold: float) -> None:
    """Print a scoreboard: all sessions vs reliable sessions."""
    from scipy import stats

    reliable = df[df["reliable"] == True]  # noqa: E712

    n_total = len(df)
    n_r2_dropped = int((df["r2_actual"].notna() & (df["r2_actual"] <= r2_threshold)).sum())
    n_pre_dropped = int(
        (df["pre_stress_mean"].notna() & df["asymptote"].notna() &
         (df["pre_stress_mean"] < df["asymptote"])).sum()
    )

    print(f"\nAll sessions loaded:              {n_total}")
    print(f"  – r2_actual <= {r2_threshold}:            {n_r2_dropped} flagged unreliable")
    print(f"  – pre_stress < asymptote:         {n_pre_dropped} flagged unreliable")
    print(f"Reliable sessions:                {len(reliable)}")

    if len(reliable) > 1 and "advantage" in reliable.columns:
        t_stat, p_val = stats.ttest_1samp(reliable["advantage"].dropna(), 0)
        sig = "significant" if p_val < 0.05 else "not significant"
        print()
        print("━━ CORE RESULT (reliable sessions only) ━━━━━━━━━━━━━━━━━━")
        print(f"  Mean advantage : {reliable['advantage'].mean():+.1f} min")
        print(f"  Std deviation  : {reliable['advantage'].std():.1f} min")
        print(f"  t-test (n={len(reliable):<2})  : t={t_stat:.3f},  p={p_val:.4f}  ({sig})")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        if "playlist" in reliable.columns:
            print("\nBy playlist (reliable sessions):")
            print(
                reliable.groupby("playlist")["advantage"]
                .agg(mean="mean", std="std", n="count")
                .round(2)
                .to_string()
            )


# ── Main ──────────────────────────────────────────────────────────────────────

def main(participants: list[str], r2_threshold: float) -> None:
    ANALYSIS_ROOT.mkdir(parents=True, exist_ok=True)

    all_data: dict[str, dict] = {}
    for codename in participants:
        data = _load_participant(codename)
        if not data:
            continue
        if "effects" not in data:
            print(f"[{codename}] No session_effects.csv — run sessions/pipeline.py first")
            continue
        all_data[codename] = data
        print(f"[{codename}] Loaded {len(data['effects'])} sessions")

    if not all_data:
        print("No data loaded.")
        return

    # Build combined recovery features table
    features_df = build_recovery_features(all_data, r2_threshold)

    if features_df.empty:
        print("No recovery features produced.")
        return

    out_path = ANALYSIS_ROOT / "recovery_features.csv"
    features_df.to_csv(out_path, index=False)
    print(f"\nRecovery features → {out_path}  ({len(features_df)} rows)")

    # Per-participant summary
    if "participant" in features_df.columns and "advantage" in features_df.columns:
        summary = (
            features_df.groupby("participant")["advantage"]
            .agg(mean_advantage="mean", std_advantage="std", n_sessions="count")
            .round(2)
            .reset_index()
        )
        summary_path = ANALYSIS_ROOT / "recovery_features_summary.csv"
        summary.to_csv(summary_path, index=False)
        print(f"Per-participant summary → {summary_path}")

    # Score board
    print_summary(features_df, r2_threshold)

    # Recovery window plots
    print("\nGenerating recovery window plots...")
    for codename, data in all_data.items():
        classified = data.get("classified")
        baselines = data.get("baselines")
        effects = data.get("effects")
        if classified is None or baselines is None or effects is None:
            continue
        plot_recovery_windows(codename, classified, baselines, effects, ANALYSIS_ROOT)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Recovery analysis — quality filter, export, and plots"
    )
    parser.add_argument(
        "--participants", nargs="+", default=PARTICIPANTS,
        help="Participant codenames (default: all)",
    )
    parser.add_argument(
        "--r2-threshold", type=float, default=DEFAULT_R2_THRESHOLD,
        help=f"Minimum r2_actual for a session to be marked reliable (default: {DEFAULT_R2_THRESHOLD})",
    )
    args = parser.parse_args()
    main(args.participants, args.r2_threshold)
