"""
circadian_ml.py — ML pipeline for predicting mood and stress outcomes
from circadian baseline deviation and session context features.

Models: Ridge, Random Forest, Gradient Boosting (+ Dummy baseline).
Validation: Leave-one-session-out cross-validation.
Explainability: Ridge coefficients, permutation importance, SHAP.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.pipeline import Pipeline

# ── Configuration ────────────────────────────────────────────────────────────

# Features used in models (hrv_rmssd excluded — only 1 participant has it)
FEATURE_COLS = [
    "baseline_deviation_entry",
    "hr_baseline_deviation",
    "hour_of_day",
    "day_of_week",
    "playlist_calm",
    "playlist_energy",
    "mood_before_score",
    "bb_start",
    "days_since_last_session",
    "during_stress_mean",
    "post_stress_mean",
    "during_hr_mean",
    "post_hr_mean",
    "pre_state_encoded",
    "hrv_rmssd",
    "avg_resp_daily",
]

# Participant one-hot columns are added dynamically
TARGET_COLS = {"mood_delta": "Mood Delta", "stress_delta": "Stress Delta"}

MODELS = {
    "DummyMean": DummyRegressor(strategy="mean"),
    "Ridge": Ridge(alpha=1.0),
    "RandomForest": RandomForestRegressor(
        n_estimators=100, max_depth=3, random_state=42
    ),
    "GradientBoosting": GradientBoostingRegressor(
        n_estimators=50, max_depth=2, learning_rate=0.1, random_state=42
    ),
}


# ── Data preparation ─────────────────────────────────────────────────────────


def prepare_data(
    feature_matrix_path: Path, target: str
) -> tuple[pd.DataFrame, pd.Series, list[str], pd.Series]:
    """Load feature matrix, drop rows with NaN target, return X, y, feature names, participant groups.

    Imputation is NOT done here — it happens inside CV folds via sklearn Pipeline.
    """
    fm = pd.read_csv(feature_matrix_path)

    # Drop rows where target is NaN
    fm = fm.dropna(subset=[target]).reset_index(drop=True)

    # One-hot encode participant (drop_first to avoid collinearity)
    participant_dummies = pd.get_dummies(fm["participant"], prefix="p", drop_first=True)

    feature_cols = FEATURE_COLS + list(participant_dummies.columns)
    X = pd.concat([fm[FEATURE_COLS], participant_dummies], axis=1)
    y = fm[target]
    groups = fm["participant"]

    return X, y, feature_cols, groups


# ── Cross-validation ─────────────────────────────────────────────────────────


def run_loo_cv(X: pd.DataFrame, y: pd.Series, model, feature_names: list[str]) -> dict:
    """Run leave-one-session-out CV with imputation inside each fold.

    Returns dict with predictions, metrics, and train vs test score comparison.
    """
    loo = LeaveOneOut()
    y_pred = np.full(len(y), np.nan)
    train_scores = []

    for train_idx, test_idx in loo.split(X):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        # Impute per fold to prevent leakage
        pipe = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("model", _clone_model(model)),
        ])
        pipe.fit(X_train, y_train)
        y_pred[test_idx] = pipe.predict(X_test)

        # Train score for overfitting check
        train_scores.append(pipe.score(X_train, y_train))

    mae = mean_absolute_error(y, y_pred)
    rmse = np.sqrt(mean_squared_error(y, y_pred))
    r2 = r2_score(y, y_pred)
    train_r2_mean = np.mean(train_scores)

    return {
        "y_pred": y_pred,
        "MAE": mae,
        "RMSE": rmse,
        "R2_LOO": r2,
        "R2_train_mean": train_r2_mean,
        "overfit_gap": train_r2_mean - r2,
    }


def _clone_model(model):
    """Clone a sklearn estimator."""
    from sklearn.base import clone
    return clone(model)


# ── Model evaluation ─────────────────────────────────────────────────────────


def train_and_evaluate(
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    target_name: str,
) -> tuple[pd.DataFrame, dict]:
    """Run all models with LOO CV, return comparison DataFrame and per-model results."""
    results = {}
    rows = []

    for name, model in MODELS.items():
        res = run_loo_cv(X, y, model, list(X.columns))
        res["model_name"] = name
        results[name] = res

        row = {
            "model": name,
            "MAE": res["MAE"],
            "RMSE": res["RMSE"],
            "R2_LOO": res["R2_LOO"],
            "R2_train_mean": res["R2_train_mean"],
            "overfit_gap": res["overfit_gap"],
        }

        # Per-participant MAE
        for participant in groups.unique():
            mask = groups == participant
            if mask.sum() > 0:
                row[f"MAE_{participant}"] = mean_absolute_error(
                    y[mask], res["y_pred"][mask]
                )
        rows.append(row)

    comparison = pd.DataFrame(rows)
    return comparison, results


# ── Explainability ───────────────────────────────────────────────────────────


def compute_ridge_coefficients(
    X: pd.DataFrame, y: pd.Series, feature_names: list[str]
) -> pd.DataFrame:
    """Fit Ridge on full data (with imputation) and return coefficients."""
    pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", Ridge(alpha=1.0)),
    ])
    pipe.fit(X, y)
    coefs = pipe.named_steps["model"].coef_
    return pd.DataFrame({
        "feature": feature_names,
        "coefficient": coefs,
        "abs_coefficient": np.abs(coefs),
    }).sort_values("abs_coefficient", ascending=False)


def compute_permutation_importance(
    X: pd.DataFrame, y: pd.Series, model_name: str
) -> pd.DataFrame:
    """Compute permutation importance using full-data fit."""
    model = MODELS[model_name]
    pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", _clone_model(model)),
    ])
    pipe.fit(X, y)

    result = permutation_importance(
        pipe, X, y, n_repeats=30, random_state=42, scoring="neg_mean_absolute_error"
    )
    return pd.DataFrame({
        "feature": X.columns,
        "importance_mean": result.importances_mean,
        "importance_std": result.importances_std,
    }).sort_values("importance_mean", ascending=True)


def _shap_data_quality_warning(X: pd.DataFrame, target_name: str) -> str:
    """Generate a data quality warning string for SHAP outputs."""
    n = len(X)
    nan_fracs = X.isna().mean()
    nan_report = ", ".join(
        f"{col}: {frac:.0%}" for col, frac in nan_fracs.items() if frac > 0
    )

    if n < 20:
        reliability = "VERY LOW - interpret with extreme caution"
    elif n < 40:
        reliability = "LOW - use for directional insights only"
    else:
        reliability = "BORDERLINE - patterns may be meaningful but not robust"

    warning = f"SHAP reliability: {reliability} (N={n})"
    if nan_report:
        warning += f"\nNaN fractions: {nan_report}"
    warning += "\nWARNING: Garbage in, garbage out -- SHAP faithfully explains the model, not necessarily reality."
    return warning


def run_shap(
    X: pd.DataFrame,
    y: pd.Series,
    model_name: str,
    target_name: str,
    output_dir: Path,
    label: str = "",
) -> shap.Explanation | None:
    """Fit model on full data and compute SHAP values.

    Prints a data quality warning. Saves beeswarm plot to output_dir.
    Can be called for a subset of participants by pre-filtering X and y.
    """
    if model_name == "DummyMean":
        return None

    model = MODELS[model_name]
    pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", _clone_model(model)),
    ])
    pipe.fit(X, y)

    # SHAP needs the imputed data — handle columns dropped by imputer (all-NaN)
    imputer = pipe.named_steps["imputer"]
    X_transformed = imputer.transform(X)
    # imputer may drop columns that are entirely NaN in this subset
    kept_mask = ~np.isnan(imputer.statistics_)
    kept_cols = [c for c, keep in zip(X.columns, kept_mask) if keep]
    X_imputed = pd.DataFrame(X_transformed, columns=kept_cols)

    warning = _shap_data_quality_warning(X, target_name)
    print(f"\n{'='*60}")
    print(f"SHAP: {target_name} - {model_name} {label}")
    print(warning)
    print(f"{'='*60}")

    fitted_model = pipe.named_steps["model"]
    explainer = shap.Explainer(fitted_model, X_imputed)
    shap_values = explainer(X_imputed)

    # Save beeswarm plot
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_{label}" if label else ""
    fig_path = output_dir / f"shap_{target_name}{suffix}.png"

    fig, ax = plt.subplots(figsize=(10, 6))
    plt.sca(ax)
    shap.plots.beeswarm(shap_values, show=False)
    ax.set_title(f"SHAP — {target_name} ({model_name}, N={len(X)}){' — ' + label if label else ''}")
    fig.tight_layout()
    fig.savefig(fig_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {fig_path}")

    return shap_values


# ── Plotting ─────────────────────────────────────────────────────────────────


def plot_target_distribution(y: pd.Series, target_name: str, output_dir: Path) -> None:
    """Histogram of the target variable."""
    output_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(y, bins=range(int(y.min()) - 1, int(y.max()) + 2), edgecolor="black", alpha=0.7)
    ax.set_xlabel(target_name)
    ax.set_ylabel("Count")
    ax.set_title(f"Distribution of {target_name} (N={len(y)})")
    ax.axvline(y.mean(), color="red", linestyle="--", label=f"Mean = {y.mean():.2f}")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / f"target_distribution_{target_name}.png", dpi=150)
    plt.close(fig)


def plot_model_comparison(comparison: pd.DataFrame, target_name: str, output_dir: Path) -> None:
    """Bar chart of MAE per model."""
    output_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5))
    models = comparison["model"]
    mae_vals = comparison["MAE"]
    colors = ["#aaaaaa" if m == "DummyMean" else "#4c78a8" for m in models]
    ax.barh(models, mae_vals, color=colors, edgecolor="black")
    ax.set_xlabel("MAE (lower is better)")
    ax.set_title(f"Model Comparison — {target_name}")
    for i, v in enumerate(mae_vals):
        ax.text(v + 0.05, i, f"{v:.3f}", va="center")
    fig.tight_layout()
    fig.savefig(output_dir / f"model_comparison_{target_name}.png", dpi=150)
    plt.close(fig)


def plot_per_participant_mae(comparison: pd.DataFrame, target_name: str, output_dir: Path) -> None:
    """Grouped bar chart of MAE per model per participant."""
    output_dir.mkdir(parents=True, exist_ok=True)
    mae_cols = [c for c in comparison.columns if c.startswith("MAE_")]
    if not mae_cols:
        return

    participants = [c.replace("MAE_", "") for c in mae_cols]
    non_dummy = comparison[comparison["model"] != "DummyMean"]

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(participants))
    width = 0.8 / len(non_dummy)
    for i, (_, row) in enumerate(non_dummy.iterrows()):
        vals = [row[c] for c in mae_cols]
        ax.bar(x + i * width, vals, width, label=row["model"])
    ax.set_xticks(x + width * len(non_dummy) / 2)
    ax.set_xticklabels(participants)
    ax.set_ylabel("MAE")
    ax.set_title(f"Per-Participant MAE — {target_name}")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / f"per_participant_mae_{target_name}.png", dpi=150)
    plt.close(fig)


def plot_predicted_vs_actual(
    y: pd.Series, y_pred: np.ndarray, groups: pd.Series, target_name: str, model_name: str, output_dir: Path
) -> None:
    """Scatter plot of predicted vs actual, colored by participant."""
    output_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 7))
    for participant in groups.unique():
        mask = groups == participant
        ax.scatter(y[mask], y_pred[mask], label=participant, alpha=0.7, s=60)
    mn, mx = min(y.min(), y_pred.min()) - 1, max(y.max(), y_pred.max()) + 1
    ax.plot([mn, mx], [mn, mx], "k--", alpha=0.3, label="Perfect")
    ax.set_xlabel(f"Actual {target_name}")
    ax.set_ylabel(f"Predicted {target_name}")
    ax.set_title(f"Predicted vs Actual — {model_name} ({target_name})")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / f"predicted_vs_actual_{target_name}.png", dpi=150)
    plt.close(fig)


def plot_ridge_coefficients(coefs_df: pd.DataFrame, target_name: str, output_dir: Path) -> None:
    """Horizontal bar chart of Ridge coefficients."""
    output_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 6))
    sorted_df = coefs_df.sort_values("coefficient")
    colors = ["#e45756" if c < 0 else "#4c78a8" for c in sorted_df["coefficient"]]
    ax.barh(sorted_df["feature"], sorted_df["coefficient"], color=colors, edgecolor="black")
    ax.set_xlabel("Ridge Coefficient")
    ax.set_title(f"Ridge Coefficients — {target_name}")
    ax.axvline(0, color="black", linewidth=0.5)
    fig.tight_layout()
    fig.savefig(output_dir / f"ridge_coefficients_{target_name}.png", dpi=150)
    plt.close(fig)


def plot_permutation_importance(
    perm_df: pd.DataFrame, model_name: str, target_name: str, output_dir: Path
) -> None:
    """Bar chart of permutation importance."""
    output_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 6))
    # Sort descending by absolute importance (most negative = most important for neg_mae)
    sorted_df = perm_df.sort_values("importance_mean", ascending=True)
    ax.barh(sorted_df["feature"], -sorted_df["importance_mean"], color="#4c78a8", edgecolor="black")
    ax.set_xlabel("Importance (MAE increase when shuffled)")
    ax.set_title(f"Permutation Importance — {model_name} ({target_name})")
    fig.tight_layout()
    fig.savefig(output_dir / f"permutation_importance_{model_name}_{target_name}.png", dpi=150)
    plt.close(fig)


def plot_circadian_curve(participant: str, baseline_path: Path, output_dir: Path) -> None:
    """Plot a participant's 24-hour stress baseline with std bands."""
    output_dir.mkdir(parents=True, exist_ok=True)
    bl = pd.read_csv(baseline_path)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(bl["hour"], bl["mean_stress"], "o-", color="#4c78a8", linewidth=2)
    valid = bl["mean_stress"].notna()
    ax.fill_between(
        bl.loc[valid, "hour"],
        bl.loc[valid, "mean_stress"] - bl.loc[valid, "std_stress"],
        bl.loc[valid, "mean_stress"] + bl.loc[valid, "std_stress"],
        alpha=0.2, color="#4c78a8",
    )
    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("Mean Stress")
    ax.set_title(f"Circadian Stress Baseline — {participant}")
    ax.set_xticks(range(0, 24))
    ax.set_xlim(-0.5, 23.5)
    fig.tight_layout()
    fig.savefig(output_dir / "circadian_curve.png", dpi=150)
    plt.close(fig)


def plot_circadian_overlay(participants: list[str], analysis_dir: Path, output_dir: Path) -> None:
    """Overlay all participants' circadian curves on one plot."""
    output_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 5))
    for p in participants:
        bl_path = analysis_dir / p / "circadian_baselines" / "hourly_baseline.csv"
        if bl_path.exists():
            bl = pd.read_csv(bl_path)
            ax.plot(bl["hour"], bl["mean_stress"], "o-", label=p, linewidth=2, markersize=4)
    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("Mean Stress")
    ax.set_title("Circadian Stress Baselines — All Participants")
    ax.set_xticks(range(0, 24))
    ax.set_xlim(-0.5, 23.5)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_dir / "circadian_curves_overlay.png", dpi=150)
    plt.close(fig)


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    analysis_dir = Path(__file__).resolve().parents[2] / "data/analysis"
    combined_dir = analysis_dir / "circadian_baselines"
    combined_plots = combined_dir / "plots"
    feature_matrix_path = combined_dir / "feature_matrix.csv"

    participants = ["bosbes", "kokosnoot", "limoen", "peer"]

    # ── Circadian baseline plots ──
    print("Plotting circadian baselines...")
    for p in participants:
        bl_path = analysis_dir / p / "circadian_baselines" / "hourly_baseline.csv"
        plot_dir = analysis_dir / p / "circadian_baselines" / "plots"
        if bl_path.exists():
            plot_circadian_curve(p, bl_path, plot_dir)
    plot_circadian_overlay(participants, analysis_dir, combined_plots)

    # ── Run models for each target ──
    for target, label in TARGET_COLS.items():
        print(f"\n{'='*60}")
        print(f"TARGET: {label} ({target})")
        print(f"{'='*60}")

        X, y, feature_names, groups = prepare_data(feature_matrix_path, target)
        print(f"  Sessions: {len(y)}, Features: {len(feature_names)}")
        print(f"  Participants: {dict(groups.value_counts())}")

        # Target distribution
        plot_target_distribution(y, target, combined_plots)

        # Model comparison
        comparison, results = train_and_evaluate(X, y, groups, target)
        comparison.to_csv(combined_dir / f"model_results_{target}.csv", index=False)

        print(f"\n  Model comparison:")
        print(comparison[["model", "MAE", "RMSE", "R2_LOO", "R2_train_mean", "overfit_gap"]].to_string(index=False))

        # Flag overfitting
        for _, row in comparison.iterrows():
            if row["model"] != "DummyMean" and row["overfit_gap"] > 0.5:
                print(f"  OVERFIT WARNING: {row['model']} - train R2={row['R2_train_mean']:.3f} vs LOO R2={row['R2_LOO']:.3f}")

        # Plots
        plot_model_comparison(comparison, target, combined_plots)
        plot_per_participant_mae(comparison, target, combined_plots)

        # Best model (by MAE, excluding Dummy)
        non_dummy = comparison[comparison["model"] != "DummyMean"]
        best_name = non_dummy.loc[non_dummy["MAE"].idxmin(), "model"]
        best_result = results[best_name]
        print(f"\n  Best model: {best_name} (MAE={best_result['MAE']:.3f})")

        # Check if best beats dummy
        dummy_mae = comparison.loc[comparison["model"] == "DummyMean", "MAE"].values[0]
        if best_result["MAE"] >= dummy_mae:
            print(f"  NOTE: No model beats the DummyMean baseline (MAE={dummy_mae:.3f})")
            print(f"    With N={len(y)}, the features do not predict {target} better than the mean.")

        # Predicted vs actual
        plot_predicted_vs_actual(y, best_result["y_pred"], groups, target, best_name, combined_plots)

        # Ridge coefficients
        coefs = compute_ridge_coefficients(X, y, feature_names)
        print(f"\n  Ridge coefficients:")
        print(coefs[["feature", "coefficient"]].to_string(index=False))
        plot_ridge_coefficients(coefs, target, combined_plots)

        # Permutation importance for best model
        if best_name != "DummyMean":
            perm = compute_permutation_importance(X, y, best_name)
            plot_permutation_importance(perm, best_name, target, combined_plots)

        # SHAP — combined (with data quality warning)
        if best_name != "DummyMean":
            run_shap(X, y, best_name, target, combined_plots)

            # SHAP — per participant
            for p in participants:
                mask = groups == p
                if mask.sum() >= 3:  # Need at least 3 sessions for any pattern
                    run_shap(
                        X[mask], y[mask], best_name, target,
                        analysis_dir / p / "circadian_baselines" / "plots",
                        label=p,
                    )

    print("\nDone. Results saved to data/analysis/")


if __name__ == "__main__":
    main()
