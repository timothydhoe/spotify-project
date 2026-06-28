#!/usr/bin/env python3
"""Generate presentation visuals for RQ1-RQ5.

Output: docs/presentation_visuals/rq{1-5}_*.png
"""

import json
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import matplotlib.image as mpimg
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "analysis"
OUT = ROOT / "docs" / "presentation_visuals"
OUT.mkdir(parents=True, exist_ok=True)

# ── Shared style ───────────────────────────────────────────────────────────────
PLAYLIST_COLORS = {"Calm": "#4A90D9", "Neutral": "#8C8C8C", "Energy": "#E8742A"}
PARTICIPANT_COLORS = {
    "bosbes":      "#E8742A",
    "kokosnoot":   "#4A90D9",
    "peer":        "#50B86C",
    "watermeloen": "#9B59B6",
}
PLAYLIST_ORDER = ["Calm", "Neutral", "Energy"]

plt.rcParams.update({
    "font.family":         "DejaVu Sans",
    "font.size":           11,
    "axes.titlesize":      12,
    "axes.titleweight":    "bold",
    "axes.labelsize":      10,
    "figure.facecolor":    "white",
    "axes.facecolor":      "#F5F5F5",
    "axes.spines.top":     False,
    "axes.spines.right":   False,
    "axes.grid":           True,
    "grid.alpha":          0.4,
    "grid.color":          "#CCCCCC",
    "legend.framealpha":   0.9,
})

# ── Load data ──────────────────────────────────────────────────────────────────
df_rec = pd.read_csv(DATA / "recovery_features.csv")
df_rel = df_rec[df_rec["reliable"]].copy()

df_sig = pd.read_csv(DATA / "circadian_baselines" / "significance_tests.csv")

with open(DATA / "bayesian_recommender" / "recommendations.json") as f:
    recs = json.load(f)


# ═══════════════════════════════════════════════════════════════════════════════
# RQ1 — Herstelvoordeel: 3-panel
# ═══════════════════════════════════════════════════════════════════════════════
def plot_rq1():
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.5))
    fig.suptitle(
        "RQ1 — Herstelvoordeel (τ-verschil in minuten, n=17 betrouwbare sessies)",
        fontsize=13, fontweight="bold", y=1.01,
    )

    # ── Panel 1: per deelnemer ─────────────────────────────────────────────
    ax = axes[0]
    participants = ["bosbes", "kokosnoot", "peer", "watermeloen"]
    for i, p in enumerate(participants):
        sub = df_rel[df_rel["participant"] == p]["advantage"]
        color = PARTICIPANT_COLORS[p]
        ax.scatter(
            [i] * len(sub), sub,
            color=color, s=80, zorder=3, alpha=0.85,
        )
        ax.hlines(sub.mean(), i - 0.3, i + 0.3, colors=color, linewidths=2.5, zorder=4)

    ax.axhline(0, color="#999", lw=1.2, ls="--", zorder=2)
    ax.set_xticks(range(len(participants)))
    ax.set_xticklabels(participants, rotation=15, ha="right")
    ax.set_ylabel("Herstelvoordeel (min)")
    ax.set_title("Per deelnemer")
    ax.set_xlabel("")

    labels = [
        mpatches.Patch(color=PARTICIPANT_COLORS[p], label=f"{p} (n={len(df_rel[df_rel['participant']==p])})")
        for p in participants
    ]
    ax.legend(handles=labels, fontsize=9, loc="upper left")

    # ── Panel 2: per playlisttype ──────────────────────────────────────────
    ax = axes[1]
    playlists_present = [p for p in PLAYLIST_ORDER if p in df_rel["playlist"].unique()]
    for i, pl in enumerate(playlists_present):
        sub = df_rel[df_rel["playlist"] == pl]["advantage"]
        color = PLAYLIST_COLORS[pl]
        # box
        bp = ax.boxplot(
            sub, positions=[i], widths=0.45,
            patch_artist=True,
            boxprops=dict(facecolor=color, alpha=0.4),
            medianprops=dict(color=color, linewidth=2),
            whiskerprops=dict(color=color),
            capprops=dict(color=color),
            flierprops=dict(markerfacecolor=color, markersize=5),
        )
        # individual points
        ax.scatter(
            [i] * len(sub), sub,
            color=color, s=60, zorder=3, alpha=0.8,
        )

    ax.axhline(0, color="#999", lw=1.2, ls="--", zorder=2)
    ax.set_xticks(range(len(playlists_present)))
    ax.set_xticklabels(playlists_present)
    ax.set_title("Per playlisttype")
    ax.set_ylabel("Herstelvoordeel (min)")

    n_labels = [mpatches.Patch(color=PLAYLIST_COLORS[p], label=f"{p} (n={len(df_rel[df_rel['playlist']==p])})")
                for p in playlists_present]
    ax.legend(handles=n_labels, fontsize=9)

    # ── Panel 3: per activiteitstoestand ──────────────────────────────────
    ax = axes[2]
    # keep states with ≥ 2 sessions
    state_counts = df_rel["pre_state"].value_counts()
    states = state_counts[state_counts >= 2].index.tolist()
    states_sorted = sorted(states)

    for i, st in enumerate(states_sorted):
        sub = df_rel[df_rel["pre_state"] == st]["advantage"]
        ax.scatter(
            [i] * len(sub), sub,
            s=70, zorder=3, alpha=0.85,
            color=[PARTICIPANT_COLORS.get(p, "#888")
                   for p in df_rel[df_rel["pre_state"] == st]["participant"]],
        )
        ax.hlines(sub.mean(), i - 0.3, i + 0.3, colors="#555", linewidths=2, zorder=4)

    ax.axhline(0, color="#999", lw=1.2, ls="--", zorder=2)
    ax.set_xticks(range(len(states_sorted)))
    ax.set_xticklabels(states_sorted, rotation=15, ha="right")
    ax.set_title("Per activiteitstoestand (pre-sessie, n≥2)")
    ax.set_ylabel("Herstelvoordeel (min)")

    part_handles = [mpatches.Patch(color=c, label=p) for p, c in PARTICIPANT_COLORS.items()
                    if p in df_rel["participant"].unique()]
    ax.legend(handles=part_handles, fontsize=9, loc="upper left")

    fig.tight_layout()
    path = OUT / "rq1_herstelvoordeel.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ {path.name}")


# ═══════════════════════════════════════════════════════════════════════════════
# RQ2 — Scatter: herstelvoordeel vs stemming
# ═══════════════════════════════════════════════════════════════════════════════
def plot_rq2():
    fig, ax = plt.subplots(figsize=(7.5, 6))

    x = df_rel["advantage"].values
    y = df_rel["mood_delta"].values

    # trend line
    mask = ~(np.isnan(x) | np.isnan(y))
    r, p = stats.pearsonr(x[mask], y[mask])
    m, b = np.polyfit(x[mask], y[mask], 1)
    xline = np.linspace(x[mask].min(), x[mask].max(), 200)
    ax.plot(xline, m * xline + b, color="#999", lw=1.5, ls="--", zorder=2,
            label=f"Trendlijn (r={r:.2f}, p={p:.2f}, n={mask.sum()})")

    # points per participant
    for p_name, color in PARTICIPANT_COLORS.items():
        sub = df_rel[df_rel["participant"] == p_name]
        if sub.empty:
            continue
        ax.scatter(
            sub["advantage"], sub["mood_delta"],
            color=color, s=90, zorder=3, alpha=0.85,
            label=p_name,
        )

    ax.axhline(0, color="#bbb", lw=1, ls=":")
    ax.axvline(0, color="#bbb", lw=1, ls=":")

    ax.set_xlabel("Herstelvoordeel τ (min)\n[positief = sneller herstel dan baseline]")
    ax.set_ylabel("Mood delta (na − voor sessie)")
    ax.set_title(
        "RQ2 — Fysiologisch herstel vs. stemmingsverandering\n"
        "(alleen betrouwbare sessies, r²>0.05 kwaliteitsfilter)"
    )
    ax.legend(fontsize=9, loc="upper right")

    fig.tight_layout()
    path = OUT / "rq2_herstel_vs_stemming.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ {path.name}")


# ═══════════════════════════════════════════════════════════════════════════════
# RQ3 — Heatmap effect sizes per deelnemer × playlist
# ═══════════════════════════════════════════════════════════════════════════════
def plot_rq3():
    # Extract per-playlist during-session stress effect sizes
    rq3 = df_sig[
        (df_sig["test_category"] == "immediate_by_playlist") &
        (df_sig["metric"] == "stress") &
        (df_sig["test_name"].str.contains("during"))
    ].copy()
    rq3["playlist"] = rq3["test_name"].str.extract(r"pre_vs_during_(\w+)")

    # Build pivot: rows=participant, cols=playlist
    pivot = rq3.pivot(index="participant", columns="playlist", values="effect_size")
    pivot_p = rq3.pivot(index="participant", columns="playlist", values="p_value")
    pivot_n = rq3.pivot(index="participant", columns="playlist", values="n")

    # Add watermeloen row (no per-playlist data → NaN)
    for p in ["bosbes", "kokosnoot", "peer", "watermeloen"]:
        if p not in pivot.index:
            pivot.loc[p] = np.nan
            pivot_p.loc[p] = np.nan
            pivot_n.loc[p] = np.nan

    # Reorder
    row_order = ["peer", "kokosnoot", "bosbes", "watermeloen"]
    col_order = [c for c in PLAYLIST_ORDER if c in pivot.columns]
    pivot = pivot.reindex(index=row_order, columns=col_order)
    pivot_p = pivot_p.reindex(index=row_order, columns=col_order)
    pivot_n = pivot_n.reindex(index=row_order, columns=col_order)

    fig, ax = plt.subplots(figsize=(7, 5))

    # Diverging colormap: negative (blue) = stress decrease = goed
    # Positive (red) = stress increase = ongunstig
    sns.heatmap(
        pivot,
        ax=ax,
        cmap="RdBu_r",        # blauw = stress daalt (goed), rood = stress stijgt (ongunstig)
        center=0,
        vmin=-1, vmax=1,
        annot=False,
        linewidths=0.8,
        linecolor="#ddd",
        cbar_kws={"label": "Effect size (rank-biserial r)"},
    )

    # Custom cell annotations: effect size + sig marker + n
    for i, row in enumerate(pivot.index):
        for j, col in enumerate(pivot.columns):
            val = pivot.loc[row, col]
            pval = pivot_p.loc[row, col]
            n_val = pivot_n.loc[row, col]
            if pd.isna(val):
                ax.text(j + 0.5, i + 0.5, "—", ha="center", va="center",
                        fontsize=13, color="#999")
            else:
                sig = "*" if (not pd.isna(pval) and pval < 0.05) else ""
                n_str = f"n={int(n_val)}" if not pd.isna(n_val) else ""
                ax.text(j + 0.5, i + 0.35, f"{val:.2f}{sig}",
                        ha="center", va="center", fontsize=12,
                        fontweight="bold" if sig else "normal",
                        color="white" if abs(val) > 0.6 else "#333")
                ax.text(j + 0.5, i + 0.68, n_str,
                        ha="center", va="center", fontsize=8.5, color="#555")

    ax.set_xlabel("Playlisttype", fontsize=11)
    ax.set_ylabel("Deelnemer", fontsize=11)
    ax.set_title(
        "RQ3 — Biometrische stressrespons per deelnemer × playlist\n"
        "Effect size (stress tijdens vs. voor sessie)   * p<0.05",
        fontsize=12, fontweight="bold",
    )
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=0)

    # Watermeloen note
    fig.text(
        0.5, -0.04,
        "watermeloen: te weinig sessies per playlisttype voor gestratificeerde analyse  |  "
        "Blauw = stress daalt  ·  Rood = stress stijgt",
        ha="center", fontsize=8.5, color="#666", style="italic",
    )

    fig.tight_layout()
    path = OUT / "rq3_effect_heatmap.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ {path.name}")


# ═══════════════════════════════════════════════════════════════════════════════
# RQ4 — Forest plot aanbevelingen (reuse existing, regenerate for consistent style)
# ═══════════════════════════════════════════════════════════════════════════════
def plot_rq4():
    participants = ["bosbes", "kiwi", "kokosnoot", "limoen", "peer", "watermeloen"]
    playlists = PLAYLIST_ORDER

    fig, ax = plt.subplots(figsize=(9, 6.5))

    bar_height = 0.22
    offsets = {"Calm": -bar_height, "Neutral": 0, "Energy": bar_height}
    y_positions = {p: i for i, p in enumerate(reversed(participants))}

    for pl in playlists:
        color = PLAYLIST_COLORS[pl]
        for part in participants:
            data = recs.get(part, {}).get(pl)
            if not data:
                continue
            y = y_positions[part] + offsets[pl]
            mean = data["mean_delta"]
            ci_low = data["ci_low"]
            ci_high = data["ci_high"]

            ax.barh(y, mean, height=bar_height * 0.85,
                    color=color, alpha=0.75, zorder=3)
            ax.errorbar(
                mean, y,
                xerr=[[mean - ci_low], [ci_high - mean]],
                fmt="none", color=color, capsize=4, linewidth=1.5, zorder=4,
            )

    ax.axvline(0, color="#888", lw=1.2, ls="--", zorder=2)
    ax.set_yticks(list(y_positions.values()))
    ax.set_yticklabels(list(reversed(participants)), fontsize=11)
    ax.set_xlabel("Voorspelde mood delta (89% CI)", fontsize=11)
    ax.set_title(
        "RQ4 — Bayesiaanse aanbeveling per deelnemer\n"
        "Hiërarchisch model: partial pooling, 4 × 1000 MCMC-steekproeven, R-hat < 1.01",
        fontsize=12, fontweight="bold",
    )

    legend_patches = [mpatches.Patch(color=PLAYLIST_COLORS[pl], label=pl) for pl in playlists]
    ax.legend(handles=legend_patches, fontsize=10, loc="lower right")

    fig.tight_layout()
    path = OUT / "rq4_aanbevelingen.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ {path.name}")


# ═══════════════════════════════════════════════════════════════════════════════
# RQ5 — 3-panel composite: BIC/AIC + silhouette + PCA k=3
# ═══════════════════════════════════════════════════════════════════════════════
def plot_rq5():
    src_bic = DATA / "music_classification" / "bic_aic_comparison.png"
    src_pca = DATA / "music_classification" / "pca_scatter_k3.png"

    img_bic = mpimg.imread(str(src_bic))   # already a 2-panel (BIC left, silhouette right)
    img_pca = mpimg.imread(str(src_pca))

    # Split bic image in half horizontally
    w = img_bic.shape[1]
    img_bic_left  = img_bic[:, : w // 2, :]   # BIC/AIC panel
    img_bic_right = img_bic[:, w // 2 :, :]   # Silhouette panel

    fig = plt.figure(figsize=(17, 5.5))
    fig.suptitle(
        "RQ5 — Automatische muziekclassificatie via GMM-clustering op audiofeatures\n"
        "BIC/AIC prefereert k=8; geforceerd k=3 (ISO-principe) toont sterke overlap",
        fontsize=12, fontweight="bold", y=1.02,
    )

    gs = gridspec.GridSpec(1, 3, figure=fig, wspace=0.04)

    for idx, (img, title) in enumerate([
        (img_bic_left,  "Modelkeuze: BIC & AIC"),
        (img_bic_right, "Clusterqualiteit: silhouette score"),
        (img_pca,       "PCA — k=3 (geforceerd)"),
    ]):
        ax = fig.add_subplot(gs[idx])
        ax.imshow(img)
        ax.set_title(title, fontsize=11, fontweight="bold", pad=6)
        ax.axis("off")

    fig.tight_layout()
    path = OUT / "rq5_muziekclassificatie.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ {path.name}")


# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"Writing to: {OUT}\n")
    plot_rq1()
    plot_rq2()
    plot_rq3()
    plot_rq4()
    plot_rq5()
    print("\nKlaar — alle 5 visuals gegenereerd.")
