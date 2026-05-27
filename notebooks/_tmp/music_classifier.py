"""
music_classifier.py
-------------------
Assumption-free music classification using Gaussian Mixture Models.

Instead of hardcoded BPM/energy thresholds, this script lets the data
define natural song groupings from Spotify audio features.

Compares:
  - k=3 (forced, for direct comparison with calm/neutral/energy)
  - k=optimal (BIC-selected, letting the data decide)

Usage:
    python scripts/analysis/music_classifier.py
"""

import json
import warnings
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=FutureWarning)

# ============================================================
# CONFIG
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLAYLISTS_DIR = PROJECT_ROOT / "data" / "playlists"
OUTPUT_DIR = PROJECT_ROOT / "data" / "analysis" / "music_classification"
MODELS_DIR = PROJECT_ROOT / "models"

FEATURES = ["tempo", "energy", "valence", "danceability", "acousticness", "loudness"]

# Pre-filters (remove non-music content, not genre assumptions)
SPEECHINESS_MAX = 0.66
LIVENESS_MAX = 0.80

# GMM search range
K_MIN, K_MAX = 2, 10

# Exportify column mapping (verbose → lowercase)
COLUMN_MAPPING = {
    "Track Name": "name",
    "Artist Name(s)": "artists",
    "Album Name": "album",
    "Duration (ms)": "duration_ms",
    "Tempo": "tempo",
    "Energy": "energy",
    "Valence": "valence",
    "Acousticness": "acousticness",
    "Danceability": "danceability",
    "Loudness": "loudness",
    "Speechiness": "speechiness",
    "Instrumentalness": "instrumentalness",
    "Liveness": "liveness",
    "Key": "key",
    "Mode": "mode",
    "Time Signature": "time_signature",
    "Track URI": "uri",
}


# ============================================================
# DATA LOADING
# ============================================================

def load_all_songs() -> pd.DataFrame:
    """Load and combine songs from all participants."""
    frames = []

    for participant_dir in sorted(PLAYLISTS_DIR.iterdir()):
        if not participant_dir.is_dir():
            continue

        codename = participant_dir.name

        # Prefer combined.csv (already cleaned by prepare.py)
        combined = participant_dir / "combined.csv"
        if combined.exists():
            df = pd.read_csv(combined)
            df.rename(columns=COLUMN_MAPPING, inplace=True)
            df.columns = df.columns.str.lower()
            df["participant"] = codename
            frames.append(df)
            continue

        # Fall back to raw Exportify CSVs
        csv_files = list(participant_dir.glob("*.csv"))
        # Skip generated playlists
        csv_files = [f for f in csv_files if "playlist" not in f.stem.lower()]
        for csv_file in csv_files:
            df = pd.read_csv(csv_file)
            df.rename(columns=COLUMN_MAPPING, inplace=True)
            df.columns = df.columns.str.lower()
            df["participant"] = codename
            frames.append(df)

    if not frames:
        raise FileNotFoundError(f"No song data found in {PLAYLISTS_DIR}")

    combined = pd.concat(frames, ignore_index=True)

    # Deduplicate by URI
    if "uri" in combined.columns:
        combined.drop_duplicates(subset="uri", inplace=True)

    return combined


def prefilter(df: pd.DataFrame) -> pd.DataFrame:
    """Remove spoken word and live recordings (content filters, not genre)."""
    n_before = len(df)
    mask = pd.Series(True, index=df.index)

    if "speechiness" in df.columns:
        mask &= df["speechiness"] <= SPEECHINESS_MAX
    if "liveness" in df.columns:
        mask &= df["liveness"] <= LIVENESS_MAX

    df_filtered = df[mask].copy()
    n_removed = n_before - len(df_filtered)
    if n_removed > 0:
        print(f"  Pre-filter removed {n_removed} songs (speech/live)")

    return df_filtered


# ============================================================
# GMM FITTING
# ============================================================

def fit_gmm_range(X: np.ndarray, k_min: int, k_max: int) -> dict:
    """Fit GMMs for k_min..k_max, return BIC/AIC/silhouette per k."""
    results = {}
    for k in range(k_min, k_max + 1):
        gmm = GaussianMixture(
            n_components=k,
            covariance_type="full",
            n_init=5,
            random_state=42,
        )
        gmm.fit(X)
        labels = gmm.predict(X)
        sil = silhouette_score(X, labels) if k > 1 else 0.0
        results[k] = {
            "bic": gmm.bic(X),
            "aic": gmm.aic(X),
            "silhouette": sil,
            "model": gmm,
        }
        print(f"  k={k}: BIC={gmm.bic(X):.0f}, AIC={gmm.aic(X):.0f}, silhouette={sil:.3f}")

    return results


def classify_songs(
    df: pd.DataFrame, X: np.ndarray, gmm: GaussianMixture, k: int, label_prefix: str
) -> pd.DataFrame:
    """Add cluster labels and probabilities to dataframe."""
    probas = gmm.predict_proba(X)
    labels = gmm.predict(X)

    df_out = df.copy()
    df_out[f"cluster_{label_prefix}"] = labels
    for i in range(k):
        df_out[f"prob_c{i}_{label_prefix}"] = probas[:, i]
    df_out[f"confidence_{label_prefix}"] = probas.max(axis=1)

    return df_out


def cluster_profiles(
    df: pd.DataFrame, features: list, cluster_col: str
) -> pd.DataFrame:
    """Compute mean feature values per cluster."""
    profiles = df.groupby(cluster_col)[features].agg(["mean", "std", "count"])
    # Flatten multi-level columns
    profiles.columns = [f"{feat}_{stat}" for feat, stat in profiles.columns]
    # Add count (same for all features, take first)
    count_cols = [c for c in profiles.columns if c.endswith("_count")]
    if count_cols:
        profiles["n_songs"] = profiles[count_cols[0]]
        profiles.drop(columns=count_cols, inplace=True)
    return profiles


# ============================================================
# VISUALIZATION
# ============================================================

def plot_bic_aic(results: dict, optimal_k: int, output_path: Path):
    """Plot BIC and AIC curves with optimal k marked."""
    ks = sorted(results.keys())
    bics = [results[k]["bic"] for k in ks]
    aics = [results[k]["aic"] for k in ks]
    sils = [results[k]["silhouette"] for k in ks]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    ax1.plot(ks, bics, "o-", label="BIC", color="#9673a6")
    ax1.plot(ks, aics, "s--", label="AIC", color="#6c8ebf")
    ax1.axvline(optimal_k, color="#b85450", linestyle=":", label=f"Optimal k={optimal_k}")
    ax1.axvline(3, color="#82b366", linestyle=":", alpha=0.6, label="k=3 (forced)")
    ax1.set_xlabel("Number of clusters (k)")
    ax1.set_ylabel("Information criterion")
    ax1.set_title("Model Selection: BIC & AIC")
    ax1.legend()
    ax1.grid(alpha=0.3)

    ax2.plot(ks, sils, "o-", color="#d79b00")
    ax2.axvline(optimal_k, color="#b85450", linestyle=":", label=f"Optimal k={optimal_k}")
    ax2.axvline(3, color="#82b366", linestyle=":", alpha=0.6, label="k=3 (forced)")
    ax2.set_xlabel("Number of clusters (k)")
    ax2.set_ylabel("Silhouette score")
    ax2.set_title("Cluster Quality: Silhouette Score")
    ax2.legend()
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved {output_path.name}")


def plot_pca_scatter(X: np.ndarray, labels: np.ndarray, k: int, title: str, output_path: Path):
    """2D PCA scatter plot colored by cluster."""
    pca = PCA(n_components=2)
    X_2d = pca.fit_transform(X)

    fig, ax = plt.subplots(figsize=(10, 7))
    palette = sns.color_palette("husl", k)

    for i in range(k):
        mask = labels == i
        ax.scatter(
            X_2d[mask, 0], X_2d[mask, 1],
            c=[palette[i]], label=f"Cluster {i}", alpha=0.5, s=15,
        )

    ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0]:.1%} variance)")
    ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1]:.1%} variance)")
    ax.set_title(title)
    ax.legend()
    ax.grid(alpha=0.2)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved {output_path.name}")


def plot_feature_boxplots(df: pd.DataFrame, features: list, cluster_col: str, title: str, output_path: Path):
    """Per-feature boxplots by cluster."""
    n_features = len(features)
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    axes = axes.flatten()

    for i, feat in enumerate(features):
        sns.boxplot(data=df, x=cluster_col, y=feat, ax=axes[i], palette="husl")
        axes[i].set_title(feat)
        axes[i].grid(alpha=0.2)

    for j in range(i + 1, len(axes)):
        axes[j].set_visible(False)

    fig.suptitle(title, fontsize=14)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved {output_path.name}")


def plot_cluster_radar(profiles: pd.DataFrame, features: list, title: str, output_path: Path):
    """Radar chart showing cluster mean profiles (normalized 0-1)."""
    mean_cols = [f"{f}_mean" for f in features]
    data = profiles[mean_cols].copy()
    data.columns = features

    # Normalize to 0-1 for radar comparability
    for col in data.columns:
        col_min, col_max = data[col].min(), data[col].max()
        if col_max > col_min:
            data[col] = (data[col] - col_min) / (col_max - col_min)

    angles = np.linspace(0, 2 * np.pi, len(features), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    palette = sns.color_palette("husl", len(data))

    for idx, (cluster_id, row) in enumerate(data.iterrows()):
        values = row.tolist() + [row.iloc[0]]
        ax.plot(angles, values, "o-", label=f"Cluster {cluster_id}", color=palette[idx], linewidth=2)
        ax.fill(angles, values, alpha=0.1, color=palette[idx])

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(features, fontsize=11)
    ax.set_title(title, fontsize=14, pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.0))

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved {output_path.name}")


# ============================================================
# REPORT
# ============================================================

def write_report(
    n_songs: int,
    n_participants: int,
    results: dict,
    optimal_k: int,
    profiles_k3: pd.DataFrame,
    profiles_opt: pd.DataFrame,
    sil_k3: float,
    sil_opt: float,
    output_path: Path,
):
    """Write comparison report."""
    lines = [
        "=" * 60,
        "MUSIC CLASSIFICATION REPORT — Gaussian Mixture Models",
        "=" * 60,
        "",
        f"Songs analysed:  {n_songs}",
        f"Participants:    {n_participants}",
        f"Features:        {', '.join(FEATURES)}",
        f"Pre-filters:     speechiness <= {SPEECHINESS_MAX}, liveness <= {LIVENESS_MAX}",
        "",
        "-" * 60,
        "MODEL SELECTION (BIC)",
        "-" * 60,
    ]
    for k in sorted(results.keys()):
        r = results[k]
        marker = " ← optimal" if k == optimal_k else ""
        marker += " ← forced" if k == 3 else ""
        lines.append(f"  k={k:2d}  BIC={r['bic']:>10.0f}  AIC={r['aic']:>10.0f}  silhouette={r['silhouette']:.3f}{marker}")

    lines += [
        "",
        f"Optimal k (lowest BIC): {optimal_k}",
        f"Silhouette (k=3):       {sil_k3:.3f}",
        f"Silhouette (k=optimal): {sil_opt:.3f}",
        "",
        "-" * 60,
        "CLUSTER PROFILES — k=3 (forced)",
        "-" * 60,
        profiles_k3.to_string(),
        "",
        "-" * 60,
        f"CLUSTER PROFILES — k={optimal_k} (optimal)",
        "-" * 60,
        profiles_opt.to_string(),
        "",
        "=" * 60,
    ]

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Saved {output_path.name}")


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 50)
    print("Music Classifier — Gaussian Mixture Models")
    print("=" * 50)

    # Load data
    print("\n[1/6] Loading songs...")
    df = load_all_songs()
    print(f"  Loaded {len(df)} songs from {df['participant'].nunique()} participants")

    # Pre-filter
    print("\n[2/6] Pre-filtering...")
    df = prefilter(df)

    # Check features exist
    missing = [f for f in FEATURES if f not in df.columns]
    if missing:
        raise ValueError(f"Missing features in data: {missing}")

    # Drop rows with NaN features
    df = df.dropna(subset=FEATURES)
    print(f"  {len(df)} songs with complete features")

    # Scale
    print("\n[3/6] Scaling features...")
    scaler = StandardScaler()
    X = scaler.fit_transform(df[FEATURES].values)

    # Fit GMMs
    print("\n[4/6] Fitting GMMs (k=2..10)...")
    results = fit_gmm_range(X, K_MIN, K_MAX)

    optimal_k = min(results, key=lambda k: results[k]["bic"])
    print(f"\n  → Optimal k = {optimal_k} (lowest BIC)")

    gmm_k3 = results[3]["model"]
    gmm_opt = results[optimal_k]["model"]

    # Classify
    print("\n[5/6] Classifying songs...")
    df = classify_songs(df, X, gmm_k3, 3, "k3")
    df = classify_songs(df, X, gmm_opt, optimal_k, "opt")

    profiles_k3 = cluster_profiles(df, FEATURES, "cluster_k3")
    profiles_opt = cluster_profiles(df, FEATURES, "cluster_opt")

    # Output
    print("\n[6/6] Saving outputs...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # CSVs
    df.to_csv(OUTPUT_DIR / "classified_songs_k3.csv", index=False)
    df.to_csv(OUTPUT_DIR / "classified_songs_optimal.csv", index=False)
    profiles_k3.to_csv(OUTPUT_DIR / "cluster_means_k3.csv")
    profiles_opt.to_csv(OUTPUT_DIR / "cluster_means_optimal.csv")

    # Scaler & config
    joblib.dump(scaler, OUTPUT_DIR / "scaler.pkl")
    config = {
        "features": FEATURES,
        "optimal_k": optimal_k,
        "k3_silhouette": results[3]["silhouette"],
        "opt_silhouette": results[optimal_k]["silhouette"],
        "k3_bic": results[3]["bic"],
        "opt_bic": results[optimal_k]["bic"],
        "n_songs": len(df),
        "n_participants": df["participant"].nunique(),
    }
    (OUTPUT_DIR / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    # Plots
    plot_bic_aic(results, optimal_k, OUTPUT_DIR / "bic_aic_comparison.png")
    plot_pca_scatter(X, gmm_k3.predict(X), 3, "PCA — k=3 (forced)", OUTPUT_DIR / "pca_scatter_k3.png")
    plot_pca_scatter(X, gmm_opt.predict(X), optimal_k, f"PCA — k={optimal_k} (optimal)", OUTPUT_DIR / "pca_scatter_optimal.png")
    plot_feature_boxplots(df, FEATURES, "cluster_k3", "Feature Distributions — k=3", OUTPUT_DIR / "feature_boxplots_k3.png")
    plot_feature_boxplots(df, FEATURES, "cluster_opt", f"Feature Distributions — k={optimal_k}", OUTPUT_DIR / "feature_boxplots_optimal.png")
    plot_cluster_radar(profiles_k3, FEATURES, "Cluster Profiles — k=3", OUTPUT_DIR / "cluster_radar_k3.png")
    plot_cluster_radar(profiles_opt, FEATURES, f"Cluster Profiles — k={optimal_k}", OUTPUT_DIR / "cluster_radar_optimal.png")

    # Report
    write_report(
        n_songs=len(df),
        n_participants=df["participant"].nunique(),
        results=results,
        optimal_k=optimal_k,
        profiles_k3=profiles_k3,
        profiles_opt=profiles_opt,
        sil_k3=results[3]["silhouette"],
        sil_opt=results[optimal_k]["silhouette"],
        output_path=OUTPUT_DIR / "comparison_report.txt",
    )

    print("\n" + "=" * 50)
    print("Done! Outputs in data/analysis/music_classification/")
    print("=" * 50)


if __name__ == "__main__":
    main()
