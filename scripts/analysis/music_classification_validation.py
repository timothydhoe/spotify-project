"""
music_classification_validation.py — Validate music classification against outcomes.

Two questions:
  1. Does playlist type (Calm/Neutral/Energy) predict mood_delta?
     → One-way Kruskal-Wallis + pairwise Mann-Whitney across playlist types
  2. Does the arousal-score classification correlate with mood_delta?
     → Compute mean arousal score per session from playlist audio features,
       then regress against mood_delta

Outputs: data/analysis/music_classification_validation/
  - classification_vs_outcomes.csv   (per-type mood_delta stats)
  - arousal_mood_regression.csv      (OLS summary)
  - plots/playlist_type_vs_mood.png
  - plots/arousal_score_vs_mood.png

Usage:
    uv run python scripts/analysis/music_classification_validation.py
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.style.use("dark_background")

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.preprocessing import MinMaxScaler

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA = PROJECT_ROOT / "data"
OUT_DIR = DATA / "analysis" / "music_classification_validation"
OUT_DIR.mkdir(parents=True, exist_ok=True)
PLOTS_DIR = OUT_DIR / "plots"
PLOTS_DIR.mkdir(exist_ok=True)

PARTICIPANTS = ["bosbes", "kiwi", "kokosnoot", "limoen", "peer", "watermeloen"]

AROUSAL_WEIGHTS = {
    "energy":        0.35,
    "tempo":         0.30,
    "loudness":      0.20,
    "acousticness": -0.10,
    "danceability":  0.05,
}

PLAYLIST_COLORS = {"Calm": "#4A90D9", "Neutral": "#7B7B7B", "Energy": "#E8913A"}


# ── Data loading ──────────────────────────────────────────────────────────────

def load_feature_matrix() -> pd.DataFrame:
    path = DATA / "analysis" / "circadian_baselines" / "feature_matrix.csv"
    fm = pd.read_csv(path)
    fm = fm.dropna(subset=["mood_delta"])
    fm["playlist"] = fm["playlist"].str.strip()
    return fm


def load_playlist_audio(participant: str, playlist_type: str) -> pd.DataFrame:
    t = playlist_type.lower()
    path = DATA / "playlists" / participant / "playlists_generated" / f"{participant}_{t}_playlist.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def compute_arousal_score(df: pd.DataFrame) -> float | None:
    """Mean arousal score across tracks in a playlist."""
    if df.empty:
        return None
    scaler = MinMaxScaler()
    score = 0.0
    valid_features = []
    for feat, weight in AROUSAL_WEIGHTS.items():
        if feat in df.columns:
            vals = pd.to_numeric(df[feat], errors="coerce").dropna()
            if not vals.empty:
                normalized = (vals - vals.min()) / (vals.max() - vals.min() + 1e-9)
                score += weight * normalized.mean()
                valid_features.append(feat)
    return float(score) if valid_features else None


# ── Analysis 1: Playlist type vs mood_delta ───────────────────────────────────

def playlist_type_analysis(fm: pd.DataFrame) -> pd.DataFrame:
    print("\n=== Analysis 1: Playlist type vs mood_delta ===")

    groups = {}
    rows = []
    for pt in ["Calm", "Neutral", "Energy"]:
        subset = fm[fm["playlist"] == pt]["mood_delta"].dropna()
        groups[pt] = subset.values
        rows.append({
            "playlist_type": pt,
            "N": len(subset),
            "mean_mood_delta": round(subset.mean(), 3) if len(subset) > 0 else None,
            "median_mood_delta": round(subset.median(), 3) if len(subset) > 0 else None,
            "std_mood_delta": round(subset.std(), 3) if len(subset) > 0 else None,
        })
        print(f"  {pt:8s}: N={len(subset):2d}, mean={subset.mean():+.2f}, median={subset.median():+.2f}")

    # Kruskal-Wallis across all 3 groups
    non_empty = [v for v in groups.values() if len(v) >= 3]
    if len(non_empty) >= 2:
        h_stat, p_kruskal = stats.kruskal(*non_empty)
        print(f"\n  Kruskal-Wallis H={h_stat:.3f}, p={p_kruskal:.4f}")
        print(f"  {'Significant (p<0.05)' if p_kruskal < 0.05 else 'Not significant'} — N is small, interpret cautiously")
    else:
        h_stat, p_kruskal = np.nan, np.nan
        print("  Kruskal-Wallis: insufficient data")

    # Pairwise Mann-Whitney
    pairs = [("Calm", "Energy"), ("Calm", "Neutral"), ("Neutral", "Energy")]
    for a, b in pairs:
        ga, gb = groups.get(a, np.array([])), groups.get(b, np.array([]))
        if len(ga) >= 3 and len(gb) >= 3:
            u, p = stats.mannwhitneyu(ga, gb, alternative="two-sided")
            print(f"  {a} vs {b}: U={u:.0f}, p={p:.4f}")
        else:
            print(f"  {a} vs {b}: insufficient data")

    result_df = pd.DataFrame(rows)
    result_df["kruskal_H"] = h_stat
    result_df["kruskal_p"] = p_kruskal
    return result_df


def plot_playlist_type_vs_mood(fm: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    types = ["Calm", "Neutral", "Energy"]
    data = [fm[fm["playlist"] == t]["mood_delta"].dropna().values for t in types]
    colors = [PLAYLIST_COLORS[t] for t in types]

    parts = ax.violinplot(data, positions=range(len(types)), showmedians=True, showextrema=False)
    for i, (pc, col) in enumerate(zip(parts["bodies"], colors)):
        pc.set_facecolor(col)
        pc.set_alpha(0.6)
    parts["cmedians"].set_color("white")

    # Overlay individual points
    for i, (d, col) in enumerate(zip(data, colors)):
        jitter = np.random.default_rng(42).uniform(-0.08, 0.08, len(d))
        ax.scatter(np.full(len(d), i) + jitter, d, color=col, alpha=0.8, s=30, zorder=3)

    ax.axhline(0, color="gray", linewidth=0.8, linestyle="--", alpha=0.5)
    ax.set_xticks(range(len(types)))
    ax.set_xticklabels([f"{t}\n(N={len(d)})" for t, d in zip(types, data)])
    ax.set_ylabel("Mood Delta (na - voor)")
    ax.set_title("Stemmingsverandering per Afspeellijsttype\n(alle deelnemers gepooled, exploratief)")
    ax.set_xlabel("Afspeellijsttype")

    path = PLOTS_DIR / "playlist_type_vs_mood.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"  -> {path}")
    plt.close(fig)


# ── Analysis 2: Arousal score vs mood_delta ───────────────────────────────────

def build_arousal_session_data(fm: pd.DataFrame) -> pd.DataFrame:
    """Attach per-session mean arousal score by loading the participant's playlist audio features."""
    rows = []
    for _, session in fm.iterrows():
        p = session["participant"]
        pt = session.get("playlist", "")
        if not pt or pt not in ("Calm", "Neutral", "Energy"):
            continue
        audio_df = load_playlist_audio(p, pt)
        arousal = compute_arousal_score(audio_df)
        rows.append({
            "participant": p,
            "date": session.get("date"),
            "playlist_type": pt,
            "mood_delta": session["mood_delta"],
            "arousal_score": arousal,
        })
    return pd.DataFrame(rows)


def arousal_regression(session_df: pd.DataFrame) -> pd.DataFrame:
    print("\n=== Analysis 2: Arousal score vs mood_delta (OLS) ===")
    df = session_df.dropna(subset=["arousal_score", "mood_delta"])
    print(f"  Sessions with arousal score + mood_delta: N={len(df)}")

    if len(df) < 5:
        print("  Insufficient data for regression.")
        return pd.DataFrame()

    x = df["arousal_score"].values
    y = df["mood_delta"].values
    slope, intercept, r, p, se = stats.linregress(x, y)
    print(f"  OLS: slope={slope:.3f}, intercept={intercept:.3f}, r={r:.3f}, r²={r**2:.3f}, p={p:.4f}")
    print(f"  {'Significant (p<0.05)' if p < 0.05 else 'Not significant'}")
    print(f"  Interpretation: {'Higher arousal score → higher mood delta' if slope > 0 else 'Higher arousal score → lower mood delta'}")

    # Per playlist type
    for pt in ["Calm", "Neutral", "Energy"]:
        sub = df[df["playlist_type"] == pt]
        if len(sub) >= 4:
            sl, ic, rv, pv, _ = stats.linregress(sub["arousal_score"].values, sub["mood_delta"].values)
            print(f"  {pt:8s}: slope={sl:.3f}, r={rv:.3f}, p={pv:.4f} (N={len(sub)})")

    return pd.DataFrame([{
        "N": len(df),
        "slope": round(slope, 4),
        "intercept": round(intercept, 4),
        "r": round(r, 4),
        "r_squared": round(r**2, 4),
        "p_value": round(p, 4),
        "significant_05": p < 0.05,
    }])


def plot_arousal_vs_mood(session_df: pd.DataFrame) -> None:
    df = session_df.dropna(subset=["arousal_score", "mood_delta"])
    if df.empty:
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    for pt, col in PLAYLIST_COLORS.items():
        sub = df[df["playlist_type"] == pt]
        if not sub.empty:
            ax.scatter(sub["arousal_score"], sub["mood_delta"],
                       color=col, label=f"{pt} (N={len(sub)})", alpha=0.8, s=50)

    # Overall regression line
    x = df["arousal_score"].values
    y = df["mood_delta"].values
    slope, intercept, r, p, _ = stats.linregress(x, y)
    x_line = np.linspace(x.min(), x.max(), 50)
    ax.plot(x_line, slope * x_line + intercept,
            color="white", linewidth=1.5, linestyle="--",
            label=f"OLS (r={r:.2f}, p={p:.3f})")

    ax.axhline(0, color="gray", linewidth=0.8, linestyle=":", alpha=0.5)
    ax.set_xlabel("Gemiddelde Arousal Score (gewogen audio-kenmerken)")
    ax.set_ylabel("Mood Delta (na - voor)")
    ax.set_title("Arousal Score vs Stemmingsverandering\n(exploratief — N=40 sessies, alle deelnemers gepooled)")
    ax.legend(fontsize=9)

    path = PLOTS_DIR / "arousal_score_vs_mood.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    print(f"  -> {path}")
    plt.close(fig)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Music Classification Validation — Project R.E.M.")
    print("=" * 60)

    fm = load_feature_matrix()
    print(f"\n  Feature matrix: N={len(fm)} sessions, "
          f"{fm['participant'].nunique()} participants")
    print(f"  Playlist distribution: {fm['playlist'].value_counts().to_dict()}")

    # Analysis 1: playlist type vs mood outcome
    type_results = playlist_type_analysis(fm)
    type_results.to_csv(OUT_DIR / "classification_vs_outcomes.csv", index=False)
    print(f"  -> classification_vs_outcomes.csv")
    plot_playlist_type_vs_mood(fm)

    # Analysis 2: arousal score vs mood outcome
    print("\n  Computing per-session arousal scores from playlist audio features...")
    session_df = build_arousal_session_data(fm)
    n_with_score = session_df["arousal_score"].notna().sum()
    print(f"  Sessions with arousal score: {n_with_score}/{len(session_df)}")

    reg_results = arousal_regression(session_df)
    if not reg_results.empty:
        reg_results.to_csv(OUT_DIR / "arousal_mood_regression.csv", index=False)
        print(f"  -> arousal_mood_regression.csv")
    plot_arousal_vs_mood(session_df)

    print(f"\n{'=' * 60}")
    print(f"  Done. Outputs in {OUT_DIR}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
