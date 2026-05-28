"""
lstm_arc.py — LSTM for biometric arc prediction.

Sequence-to-scalar regression: per-minute stress/HR time series during a
session → predicted mood_delta.

Rationale: tabular models discard the temporal shape of the stress arc.
An LSTM can capture whether stress dropped steeply vs. gradually, or whether
HR rebounded mid-session — the exact temporal pattern the ISO principle predicts.

N=27 sessions (participants with both traces and mood scores). Mitigations:
- 1-layer LSTM (32 hidden units)
- LOO cross-validation
- 5× Gaussian jitter augmentation during training (N_train × 5 synthetic copies)
- Gradient saliency shows which minutes the model attends to

Outputs (all in data/analysis/circadian_baselines/plots/):
  lstm_predictions_mood_delta.png   scatter: LOO predicted vs actual
  lstm_saliency_heatmap.png         mean gradient saliency across sessions
  lstm_vs_tabular_comparison.png    MAE bar chart: LSTM vs RF vs Ridge vs Dummy
"""

from __future__ import annotations

import random
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.style.use("dark_background")
matplotlib.rcParams["figure.facecolor"] = "#111827"
matplotlib.rcParams["axes.facecolor"]   = "#111827"
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

# ── Config ────────────────────────────────────────────────────────────────────

WEARABLES_DIR  = Path(__file__).parent.parent.parent / "data" / "wearables"
ANALYSIS_DIR   = Path(__file__).parent.parent.parent / "data" / "analysis"
PLOTS_DIR      = ANALYSIS_DIR / "circadian_baselines" / "plots"
PARTICIPANTS   = ["bosbes", "kokosnoot", "limoen", "peer"]

SEQ_LEN        = 35    # minutes — median during-phase length; longer is padded/truncated
FEATURES       = ["stress", "heart_rate"]
N_FEATURES     = len(FEATURES)
HIDDEN_SIZE    = 32
N_LAYERS       = 1
DROPOUT        = 0.0   # no dropout at this N
EPOCHS         = 80
LR             = 1e-3
AUGMENT_FACTOR = 5     # synthetic copies per training session
JITTER_STRESS  = 3.0   # ±σ for stress jitter
JITTER_HR      = 2.0   # ±σ for HR jitter

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)


# ── Data loading ──────────────────────────────────────────────────────────────

def load_sessions() -> list[dict]:
    """Return list of {participant, date, playlist, sequence, mood_delta}."""
    sessions = []
    for p in PARTICIPANTS:
        sb_path = WEARABLES_DIR / p / "processed" / "session_biometrics.csv"
        trace_dir = WEARABLES_DIR / p / "processed" / "session_traces"
        if not sb_path.exists() or not trace_dir.exists():
            continue

        sb = pd.read_csv(sb_path)
        sb["mood_delta"] = sb["mood_after_score"] - sb["mood_before_score"]
        sb_valid = sb.dropna(subset=["mood_before_score", "mood_after_score"])

        for trace_path in sorted(trace_dir.glob("trace_*.csv")):
            date_str = trace_path.stem.split("trace_")[1].split("_")[0]
            row = sb_valid[sb_valid["date"] == date_str]
            if row.empty:
                continue

            df = pd.read_csv(trace_path)
            during = df[df["phase"] == "during"].sort_values("minutes_relative")
            if during.empty or len(during) < 5:
                continue

            # Extract feature matrix, fill NaN with forward-fill then zero
            seq = during[FEATURES].ffill().fillna(0).values.astype(np.float32)

            # Pad or truncate to SEQ_LEN
            if len(seq) > SEQ_LEN:
                seq = seq[:SEQ_LEN]
            elif len(seq) < SEQ_LEN:
                pad = np.zeros((SEQ_LEN - len(seq), N_FEATURES), dtype=np.float32)
                seq = np.vstack([seq, pad])

            sessions.append({
                "participant": p,
                "date":        date_str,
                "playlist":    row.iloc[0]["playlist"],
                "sequence":    seq,
                "mood_delta":  float(row.iloc[0]["mood_delta"]),
                "actual_len":  min(len(during), SEQ_LEN),
            })

    return sessions


def normalize_sessions(sessions: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """Global z-score normalization across all sessions."""
    X = np.stack([s["sequence"] for s in sessions])     # (N, SEQ_LEN, F)
    y = np.array([s["mood_delta"] for s in sessions])   # (N,)

    mean = X.reshape(-1, N_FEATURES).mean(axis=0)
    std  = X.reshape(-1, N_FEATURES).std(axis=0) + 1e-8
    X_norm = (X - mean) / std

    return X_norm, y, mean, std


def augment(X_batch: np.ndarray, y_batch: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Return n synthetic copies with Gaussian jitter per feature."""
    jitter_std = np.array([JITTER_STRESS, JITTER_HR], dtype=np.float32)
    copies_X, copies_y = [X_batch], [y_batch]
    for _ in range(n):
        noise = np.random.normal(0, jitter_std, X_batch.shape).astype(np.float32)
        copies_X.append(X_batch + noise)
        copies_y.append(y_batch)
    return np.vstack(copies_X), np.concatenate(copies_y)


# ── Model ─────────────────────────────────────────────────────────────────────

class ArcLSTM(nn.Module):
    def __init__(self):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=N_FEATURES,
            hidden_size=HIDDEN_SIZE,
            num_layers=N_LAYERS,
            batch_first=True,
            dropout=DROPOUT,
        )
        self.head = nn.Linear(HIDDEN_SIZE, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :]).squeeze(-1)


def train_model(X_train: np.ndarray, y_train: np.ndarray) -> ArcLSTM:
    X_aug, y_aug = augment(X_train, y_train, AUGMENT_FACTOR)
    Xt = torch.from_numpy(X_aug)
    yt = torch.from_numpy(y_aug.astype(np.float32))

    dataset = TensorDataset(Xt, yt)
    loader  = DataLoader(dataset, batch_size=16, shuffle=True)

    model = ArcLSTM()
    optim = torch.optim.Adam(model.parameters(), lr=LR)
    loss_fn = nn.MSELoss()

    model.train()
    for _ in range(EPOCHS):
        for xb, yb in loader:
            optim.zero_grad()
            pred = model(xb)
            loss_fn(pred, yb).backward()
            optim.step()

    model.eval()
    return model


def predict_with_saliency(model: ArcLSTM, x: np.ndarray) -> tuple[float, np.ndarray]:
    """Return (prediction, per-timestep saliency via input gradients)."""
    xt = torch.from_numpy(x[np.newaxis]).requires_grad_(True)
    pred = model(xt)
    pred.backward()
    saliency = xt.grad.detach().numpy()[0]          # (SEQ_LEN, N_FEATURES)
    saliency_mag = np.linalg.norm(saliency, axis=1) # (SEQ_LEN,)
    return float(pred.detach().item()), saliency_mag


# ── Evaluation ────────────────────────────────────────────────────────────────

def run_loo(sessions: list[dict], X_norm: np.ndarray, y: np.ndarray) -> dict:
    """LOO cross-validation. Returns predictions, saliencies, metrics."""
    n = len(sessions)
    preds     = np.zeros(n)
    saliencies = np.zeros((n, SEQ_LEN))

    for i in range(n):
        mask_train = np.array([j != i for j in range(n)])
        X_train = X_norm[mask_train]
        y_train = y[mask_train]

        model = train_model(X_train, y_train)
        pred, sal = predict_with_saliency(model, X_norm[i])
        preds[i] = pred
        saliencies[i] = sal

        # Mask padding steps for saliency mean
        actual_len = sessions[i]["actual_len"]
        if actual_len < SEQ_LEN:
            saliencies[i, actual_len:] = 0.0

        print(f"  LOO [{i+1:2d}/{n}] {sessions[i]['participant']} {sessions[i]['date']} "
              f"actual={y[i]:+.1f} pred={pred:+.1f}")

    mae  = np.abs(preds - y).mean()
    rmse = np.sqrt(((preds - y) ** 2).mean())
    ss_res = ((preds - y) ** 2).sum()
    ss_tot = ((y - y.mean()) ** 2).sum()
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")

    return {"preds": preds, "actuals": y, "saliencies": saliencies, "MAE": mae, "RMSE": rmse, "R2": r2}


# ── Plotting ──────────────────────────────────────────────────────────────────

def plot_predictions(results: dict, sessions: list[dict], out_dir: Path) -> None:
    preds, actuals = results["preds"], results["actuals"]
    mae, r2 = results["MAE"], results["R2"]

    playlists = [s["playlist"] for s in sessions]
    colors = {"Calm": "#3b82f6", "Energy": "#f97316", "Neutral": "#a855f7"}

    fig, ax = plt.subplots(figsize=(7, 6))
    for pl, c in colors.items():
        mask = np.array([p == pl for p in playlists])
        if mask.any():
            ax.scatter(actuals[mask], preds[mask], color=c, s=70, alpha=0.85,
                       edgecolors="white", linewidths=0.7, label=pl, zorder=3)

    lo = min(actuals.min(), preds.min()) - 0.5
    hi = max(actuals.max(), preds.max()) + 0.5
    ax.plot([lo, hi], [lo, hi], "--", color=(1, 1, 1, 0.35), linewidth=1)
    ax.set_xlabel("Werkelijk mood_delta")
    ax.set_ylabel("Voorspeld mood_delta (LSTM LOO-CV)")
    ax.set_title(f"LSTM arc-voorspelling — LOO-CV\nMAE={mae:.2f}  R²={r2:.3f}  N={len(actuals)}")
    ax.legend(fontsize=9)
    fig.tight_layout()
    path = out_dir / "lstm_predictions_mood_delta.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


def plot_saliency(results: dict, out_dir: Path) -> None:
    saliencies = results["saliencies"]
    mean_sal = saliencies.mean(axis=0)
    mean_sal = mean_sal / (mean_sal.max() + 1e-8)

    fig, ax = plt.subplots(figsize=(10, 3))
    ax.bar(range(SEQ_LEN), mean_sal, color="#22c55e", alpha=0.8)
    ax.set_xlabel("Minuut van sessie (0 = start during-fase)")
    ax.set_ylabel("Genormaliseerde gradiënt-saliency")
    ax.set_title("LSTM gradient saliency — gemiddeld over alle sessies\n"
                 "Hoge waarden = model let hier meer op")
    ax.set_xlim(-0.5, SEQ_LEN - 0.5)
    fig.tight_layout()
    path = out_dir / "lstm_saliency_heatmap.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


def plot_comparison(lstm_mae: float, out_dir: Path) -> None:
    results_path = ANALYSIS_DIR / "circadian_baselines" / "model_results_mood_delta.csv"
    if not results_path.exists():
        print("  Skipping comparison: model_results_mood_delta.csv not found")
        return

    df = pd.read_csv(results_path)
    model_names = df["model"].tolist() + ["LSTM (arc)"]
    maes        = df["MAE"].tolist() + [lstm_mae]

    colors = ["#6b7280" if "Dummy" in n else
              "#22c55e" if "LSTM" in n else
              "#3b82f6"
              for n in model_names]

    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.barh(model_names, maes, color=colors, alpha=0.85, edgecolor="none")
    for bar, val in zip(bars, maes):
        ax.text(val + 0.02, bar.get_y() + bar.get_height() / 2,
                f"{val:.2f}", va="center", fontsize=9)
    ax.set_xlabel("MAE (lager = beter)")
    ax.set_title("Modelcomparisatie — mood_delta LOO-CV MAE\n"
                 "LSTM gebruikt temporele arc; andere modellen alleen fase-gemiddelden")
    ax.invert_yaxis()
    fig.tight_layout()
    path = out_dir / "lstm_vs_tabular_comparison.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading sessions …")
    sessions = load_sessions()
    print(f"  {len(sessions)} sessions with biometric traces + mood scores")

    if len(sessions) < 5:
        print("  Insufficient data — need at least 5 sessions. Exiting.")
        return

    X_norm, y, _mean, _std = normalize_sessions(sessions)
    print(f"  X shape: {X_norm.shape}, y range: {y.min():.1f}–{y.max():.1f}")

    print("\nRunning LOO cross-validation …")
    results = run_loo(sessions, X_norm, y)
    print(f"\nLSTM LOO-CV results:")
    print(f"  MAE  = {results['MAE']:.3f}")
    print(f"  RMSE = {results['RMSE']:.3f}")
    print(f"  R²   = {results['R2']:.3f}")

    print("\nGenerating plots …")
    plot_predictions(results, sessions, PLOTS_DIR)
    plot_saliency(results, PLOTS_DIR)
    plot_comparison(results["MAE"], PLOTS_DIR)

    print("\nDone.")


if __name__ == "__main__":
    main()
