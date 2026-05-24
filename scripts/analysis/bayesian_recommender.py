"""
bayesian_recommender.py -- Hierarchical Bayesian playlist recommender for Project R.E.M.

Given a participant's current physiological state, predicts which playlist type
(Calm / Neutral / Energy) will produce the best mood outcome using partial pooling
across participants.

Mood scoring accounts for emotion valence:
    composite = valence(emotion) * intensity
    mood_delta = composite_after - composite_before

Usage:
    python scripts/analysis/bayesian_recommender.py
    python scripts/analysis/bayesian_recommender.py --participants peer bosbes
    python scripts/analysis/bayesian_recommender.py --draws 4000 --chains 4
"""

import argparse
import json
import sys
import warnings
from pathlib import Path

import arviz as az
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pymc as pm

warnings.filterwarnings("ignore", category=FutureWarning)

DATA_ROOT = Path(__file__).parent.parent.parent / "data"

# ── Emotion valence mapping ─────────────────────────────────────────────────

VALENCE_MAP = {
    # Negative (-1)
    "gestresseerd of gespannen": -1,
    "moe of ongemotiveerd": -1,
    "moe en gespannen...": -1,
    # Neutral (0)
    "neutraal": 0,
    "neutraal tot een goed gevoel": 0,
    # Positive (+1)
    "rustig": 1,
    "gemotiveerd": 1,
    "happy": 1,
    "happy - gemotiveerd": 1,
    "goed gevoel": 1,
}

PLAYLIST_MAP = {"Calm": 0, "Neutral": 1, "Energy": 2}
PLAYLIST_NAMES = ["Calm", "Neutral", "Energy"]


def emotion_valence(emotion: str) -> int:
    """Map an emotion string to its valence (-1, 0, +1)."""
    key = emotion.strip().lower()
    if key in VALENCE_MAP:
        return VALENCE_MAP[key]
    # Fuzzy fallback for unexpected values
    if any(w in key for w in ("stress", "gespannen", "moe", "ongemot")):
        return -1
    if any(w in key for w in ("happy", "goed", "gemotiv", "rustig", "blij")):
        return 1
    return 0


def composite_mood(emotion: str, intensity: float) -> float:
    """Compute valence-weighted mood score: valence * intensity.

    Negative emotions get negative composite scores, positive emotions get positive.
    Neutral emotions map to 0 regardless of intensity.
    """
    return emotion_valence(emotion) * intensity


# ── Data loading ─────────────────────────────────────────────────────────────

def load_biometric_sessions(codename: str) -> pd.DataFrame:
    """Load session_biometrics.csv for a participant with wearable data."""
    path = DATA_ROOT / "wearables" / codename / "processed" / "session_biometrics.csv"
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)
    df["participant"] = codename
    df["has_biometrics"] = True
    return df


def load_checkin_sessions() -> pd.DataFrame:
    """Load check-in CSV and compute mood scores for all participants."""
    # Try both known paths
    for checkin_path in [
        DATA_ROOT / "check_in" / "check_in.csv",
        DATA_ROOT / "checkins" / "Check-in_formulier_REM.csv",
    ]:
        if checkin_path.exists():
            break
    else:
        raise FileNotFoundError("No check-in CSV found")

    ci = pd.read_csv(checkin_path)

    rows = []
    for _, r in ci.iterrows():
        emotion_before = str(r["Welk gevoel had je?"])
        emotion_after = str(r["Welk gevoel had je?.1"])
        intensity_before = float(r["Score van de intensiteit van je gevoel"])
        intensity_after = float(r["Score van de intensiteit van je gevoel.1"])
        playlist_raw = str(r["Welke playlist luisterde je?"])

        # Standardise playlist name
        playlist = playlist_raw.strip().capitalize()
        if playlist not in PLAYLIST_MAP:
            continue

        # Parse hour from start time
        start_str = str(r.get("Starttijd?", ""))
        try:
            hour = pd.to_datetime(start_str, format="%H:%M:%S").hour
        except Exception:
            try:
                hour = int(start_str.split(":")[0])
            except Exception:
                hour = 12  # fallback

        rows.append({
            "participant": str(r["Deelnemerscode"]).strip().lower(),
            "playlist": playlist,
            "emotion_before": emotion_before,
            "emotion_after": emotion_after,
            "intensity_before": intensity_before,
            "intensity_after": intensity_after,
            "mood_before_composite": composite_mood(emotion_before, intensity_before),
            "mood_after_composite": composite_mood(emotion_after, intensity_after),
            "hour_of_day": hour,
        })

    df = pd.DataFrame(rows)
    df["mood_delta"] = df["mood_after_composite"] - df["mood_before_composite"]
    return df


def build_model_data(participants_with_bio: list[str] | None = None) -> pd.DataFrame:
    """Combine biometric sessions and check-in-only sessions into one DataFrame.

    Participants with biometrics get full feature vectors.
    Check-in-only participants contribute mood + playlist data (biometrics = NaN).
    """
    checkin_df = load_checkin_sessions()

    # Load biometric sessions and merge mood delta from biometrics where available
    bio_frames = []
    bio_participants = set()

    if participants_with_bio:
        for code in participants_with_bio:
            bio = load_biometric_sessions(code)
            if bio.empty:
                continue
            bio_participants.add(code)

            # Compute composite mood from biometric session data
            # session_biometrics has mood_before/mood_after as emotion strings
            # and mood_before_score/mood_after_score as intensity
            bio_rows = []
            for _, r in bio.iterrows():
                # Get matching check-in for this participant + date for emotion info
                ci_match = checkin_df[
                    (checkin_df["participant"] == code)
                    & (checkin_df["playlist"] == r["playlist"])
                ]

                if not ci_match.empty:
                    # Use check-in data (has emotion strings)
                    ci_row = ci_match.iloc[0]
                    mood_before_comp = ci_row["mood_before_composite"]
                    mood_after_comp = ci_row["mood_after_composite"]
                    mood_delta = ci_row["mood_delta"]
                else:
                    # Fallback: use raw intensity scores from biometrics (assume neutral)
                    mood_before_comp = 0.0
                    mood_after_comp = 0.0
                    mood_delta = float(r["mood_after_score"]) - float(r["mood_before_score"])

                bio_rows.append({
                    "participant": code,
                    "playlist": r["playlist"],
                    "mood_delta": mood_delta,
                    "mood_before_composite": mood_before_comp,
                    "mood_after_composite": mood_after_comp,
                    "pre_stress_mean": r.get("pre_stress_mean"),
                    "bb_start": r.get("bb_start"),
                    "pre_hr_mean": r.get("pre_hr_mean"),
                    "hour_of_day": pd.to_datetime(r.get("start_local", "12:00"), errors="coerce").hour
                        if pd.notna(r.get("start_local")) else 12,
                    "has_biometrics": True,
                })

            if bio_rows:
                bio_frames.append(pd.DataFrame(bio_rows))

    # Check-in-only participants (those not in bio_participants)
    ci_only = checkin_df[~checkin_df["participant"].isin(bio_participants)].copy()
    ci_only["has_biometrics"] = False
    ci_only["pre_stress_mean"] = np.nan
    ci_only["bb_start"] = np.nan
    ci_only["pre_hr_mean"] = np.nan

    # Combine
    all_frames = bio_frames + ([ci_only] if not ci_only.empty else [])
    if not all_frames:
        raise ValueError("No session data found")

    combined = pd.concat(all_frames, ignore_index=True)

    # Encode playlist as integer
    combined["playlist_idx"] = combined["playlist"].map(PLAYLIST_MAP)

    # Encode participant as integer
    participant_codes = sorted(combined["participant"].unique())
    participant_map = {p: i for i, p in enumerate(participant_codes)}
    combined["participant_idx"] = combined["participant"].map(participant_map)

    return combined, participant_codes


# ── Bayesian model ───────────────────────────────────────────────────────────

def build_hierarchical_model(data: pd.DataFrame, participant_codes: list[str]):
    """Build the hierarchical Bayesian regression model.

    Participants with biometrics contribute stress/BB/HR covariates.
    Check-in-only participants contribute mood + playlist effects to the group prior.
    Biometric features are set to 0 (group mean after z-scoring) for missing data.
    """
    n_participants = len(participant_codes)
    n_playlists = 3

    # Z-score biometric features (fill NaN with 0 = group mean)
    z_cols = {}
    for col in ["pre_stress_mean", "bb_start", "pre_hr_mean"]:
        vals = data[col].copy()
        mu, sd = vals.mean(), vals.std()
        if pd.isna(mu) or sd == 0 or pd.isna(sd):
            z_cols[f"{col}_z"] = np.zeros(len(data))
        else:
            z_cols[f"{col}_z"] = ((vals.fillna(mu) - mu) / sd).values

    # Z-score hour
    hour_mu, hour_sd = data["hour_of_day"].mean(), data["hour_of_day"].std()
    if hour_sd == 0:
        hour_sd = 1.0
    z_cols["hour_z"] = ((data["hour_of_day"] - hour_mu) / hour_sd).values

    # Mask: 1 if participant has biometrics, 0 otherwise
    # This scales biometric coefficients to zero for check-in-only participants
    bio_mask = data["has_biometrics"].astype(float).values

    # Observed data
    y = data["mood_delta"].values.astype(float)
    participant_idx = data["participant_idx"].values.astype(int)
    playlist_idx = data["playlist_idx"].values.astype(int)

    stress_z = z_cols["pre_stress_mean_z"]
    bb_z = z_cols["bb_start_z"]
    hr_z = z_cols["pre_hr_mean_z"]
    hour_z = z_cols["hour_z"]

    with pm.Model() as model:
        # Store metadata on model for later use
        model._participant_codes = participant_codes
        model._z_params = {
            "stress_mu": float(data["pre_stress_mean"].mean()) if data["pre_stress_mean"].notna().any() else 0,
            "stress_sd": float(data["pre_stress_mean"].std()) if data["pre_stress_mean"].notna().any() else 1,
            "bb_mu": float(data["bb_start"].mean()) if data["bb_start"].notna().any() else 0,
            "bb_sd": float(data["bb_start"].std()) if data["bb_start"].notna().any() else 1,
            "hr_mu": float(data["pre_hr_mean"].mean()) if data["pre_hr_mean"].notna().any() else 0,
            "hr_sd": float(data["pre_hr_mean"].std()) if data["pre_hr_mean"].notna().any() else 1,
            "hour_mu": float(hour_mu),
            "hour_sd": float(hour_sd),
        }

        # ── Hyperpriors (group-level) ────────────────────────────────────
        mu_alpha = pm.Normal("mu_alpha", mu=0, sigma=5)
        sigma_alpha = pm.HalfNormal("sigma_alpha", sigma=2)

        # Group-level playlist effects -- one per playlist type
        mu_playlist = pm.Normal("mu_playlist", mu=0, sigma=5, shape=n_playlists)
        sigma_playlist = pm.HalfNormal("sigma_playlist", sigma=2)

        # ── Participant-level (non-centered parameterization) ────────────
        # Non-centered helps NUTS explore when data is sparse per group
        alpha_offset = pm.Normal("alpha_offset", mu=0, sigma=1, shape=n_participants)
        alpha = pm.Deterministic("alpha", mu_alpha + sigma_alpha * alpha_offset)

        beta_playlist_offset = pm.Normal(
            "beta_playlist_offset", mu=0, sigma=1,
            shape=(n_participants, n_playlists),
        )
        beta_playlist = pm.Deterministic(
            "beta_playlist",
            mu_playlist + sigma_playlist * beta_playlist_offset,
        )

        # Biometric coefficients -- shared across participants (small sample)
        # These only affect participants with biometric data (via bio_mask)
        beta_stress = pm.Normal("beta_stress", mu=0, sigma=2)
        beta_bb = pm.Normal("beta_bb", mu=0, sigma=2)
        beta_hr = pm.Normal("beta_hr", mu=0, sigma=2)
        beta_hour = pm.Normal("beta_hour", mu=0, sigma=2)

        # ── Linear predictor ────────────────────────────────────────────
        mu = (
            alpha[participant_idx]
            + beta_playlist[participant_idx, playlist_idx]
            + bio_mask * (
                beta_stress * stress_z
                + beta_bb * bb_z
                + beta_hr * hr_z
            )
            + beta_hour * hour_z
        )

        sigma = pm.HalfNormal("sigma", sigma=5)

        # ── Likelihood ──────────────────────────────────────────────────
        pm.Normal("mood_delta_obs", mu=mu, sigma=sigma, observed=y)

    return model


def fit_model(model, draws=2000, tune=1000, chains=4, target_accept=0.9):
    """Run NUTS sampler via NumPyro/JAX (fast) with PyMC fallback."""
    import pymc.sampling.jax as pmjax

    with model:
        try:
            trace = pmjax.sample_numpyro_nuts(
                draws=draws, tune=tune, chains=chains,
                target_accept=target_accept,
                random_seed=42,
            )
        except Exception as e:
            print(f"  JAX sampling failed ({e}), falling back to PyMC NUTS...")
            trace = pm.sample(
                draws=draws, tune=tune, chains=chains,
                target_accept=target_accept,
                return_inferencedata=True,
                random_seed=42,
            )
    return trace


def check_convergence(trace):
    """Print convergence diagnostics: R-hat and effective sample size."""
    summary = az.summary(trace, hdi_prob=0.89)
    rhat_ok = (summary["r_hat"] < 1.01).all()
    ess_ok = (summary["ess_bulk"] > 400).all()

    print(f"\n  Convergence check:")
    print(f"    R-hat < 1.01: {'PASS' if rhat_ok else 'FAIL'}")
    print(f"    ESS > 400:    {'PASS' if ess_ok else 'FAIL'}")

    if not rhat_ok:
        bad = summary[summary["r_hat"] >= 1.01]
        print(f"    ⚠ High R-hat parameters: {list(bad.index)}")

    if not ess_ok:
        bad = summary[summary["ess_bulk"] <= 400]
        print(f"    ⚠ Low ESS parameters: {list(bad.index)}")

    return summary


# ── Recommendation ───────────────────────────────────────────────────────────

def recommend_playlist(
    trace, model, participant_id: str,
    pre_stress: float | None = None,
    bb_start: float | None = None,
    pre_hr: float | None = None,
    hour_of_day: int = 12,
    mood_before: float = 5.0,
) -> dict:
    """Predict mood_delta for each playlist type given current state.

    Returns dict with per-playlist predictions and a recommendation.
    """
    codes = model._participant_codes
    zp = model._z_params

    if participant_id not in codes:
        raise ValueError(f"Unknown participant '{participant_id}'. Known: {codes}")

    p_idx = codes.index(participant_id)
    has_bio = pre_stress is not None and bb_start is not None

    # Z-score inputs
    stress_z = (pre_stress - zp["stress_mu"]) / zp["stress_sd"] if pre_stress is not None else 0
    bb_z = (bb_start - zp["bb_mu"]) / zp["bb_sd"] if bb_start is not None else 0
    hr_z = (pre_hr - zp["hr_mu"]) / zp["hr_sd"] if pre_hr is not None else 0
    hour_z = (hour_of_day - zp["hour_mu"]) / zp["hour_sd"]
    bio_mask = 1.0 if has_bio else 0.0

    # Extract posterior samples
    posterior = trace.posterior
    alpha_samples = posterior["alpha"].values[:, :, p_idx].flatten()
    beta_stress_samples = posterior["beta_stress"].values.flatten()
    beta_bb_samples = posterior["beta_bb"].values.flatten()
    beta_hr_samples = posterior["beta_hr"].values.flatten()
    beta_hour_samples = posterior["beta_hour"].values.flatten()

    results = {}
    all_means = {}

    for k, name in enumerate(PLAYLIST_NAMES):
        bp_samples = posterior["beta_playlist"].values[:, :, p_idx, k].flatten()

        predicted_delta = (
            alpha_samples
            + bp_samples
            + bio_mask * (beta_stress_samples * stress_z + beta_bb_samples * bb_z + beta_hr_samples * hr_z)
            + beta_hour_samples * hour_z
        )

        mean_delta = float(np.mean(predicted_delta))
        ci_low, ci_high = np.percentile(predicted_delta, [5.5, 94.5])  # 89% CI

        results[name] = {
            "mean_delta": round(mean_delta, 2),
            "ci_low": round(float(ci_low), 2),
            "ci_high": round(float(ci_high), 2),
        }
        all_means[name] = mean_delta

    # Recommendation with confidence
    best = max(all_means, key=all_means.get)
    sorted_playlists = sorted(all_means, key=all_means.get, reverse=True)

    # Check overlap: if top two CIs substantially overlap, flag uncertainty
    if len(sorted_playlists) >= 2:
        best_ci = results[sorted_playlists[0]]
        second_ci = results[sorted_playlists[1]]
        overlap = min(best_ci["ci_high"], second_ci["ci_high"]) - max(best_ci["ci_low"], second_ci["ci_low"])
        best_width = best_ci["ci_high"] - best_ci["ci_low"]
        uncertain = overlap > 0.5 * best_width if best_width > 0 else True
    else:
        uncertain = True

    # Compute probability that best is actually best (from posterior samples)
    best_k = PLAYLIST_MAP[best]
    bp_best = posterior["beta_playlist"].values[:, :, p_idx, best_k].flatten()
    n_wins = 0
    n_total = len(bp_best)
    for k, name in enumerate(PLAYLIST_NAMES):
        if name == best:
            continue
        bp_other = posterior["beta_playlist"].values[:, :, p_idx, k].flatten()
        n_wins += np.sum(bp_best > bp_other)
    prob_best = n_wins / (n_total * (len(PLAYLIST_NAMES) - 1))

    if uncertain:
        recommendation = (
            f"{best} ({prob_best:.0%} probability of highest mood improvement) "
            f"-- but credible intervals overlap substantially; more data needed to personalise"
        )
    else:
        recommendation = f"{best} ({prob_best:.0%} probability of highest mood improvement)"

    return {
        "participant": participant_id,
        "predictions": results,
        "recommendation": recommendation,
        "recommended_playlist": best,
        "confidence": round(float(prob_best), 2),
        "uncertain": uncertain,
    }


# ── Visualization ────────────────────────────────────────────────────────────

def plot_posterior_panels(trace, model, participant_id: str, out_path: Path | None = None):
    """3-panel posterior plot showing expected mood_delta distribution per playlist."""
    codes = model._participant_codes
    p_idx = codes.index(participant_id)
    posterior = trace.posterior

    fig, axes = plt.subplots(1, 3, figsize=(14, 4), sharey=True)
    colors = {"Calm": "#4A90D9", "Neutral": "#7B7B7B", "Energy": "#E8913A"}

    for k, (name, ax) in enumerate(zip(PLAYLIST_NAMES, axes)):
        # Participant-level intercept + playlist effect
        alpha_samples = posterior["alpha"].values[:, :, p_idx].flatten()
        bp_samples = posterior["beta_playlist"].values[:, :, p_idx, k].flatten()
        predicted = alpha_samples + bp_samples

        mean_val = np.mean(predicted)
        ci_low, ci_high = np.percentile(predicted, [5.5, 94.5])

        ax.hist(predicted, bins=40, density=True, alpha=0.7, color=colors[name], edgecolor="white")
        ax.axvline(mean_val, color="black", linewidth=1.5, linestyle="-", label=f"Mean: {mean_val:.1f}")
        ax.axvline(ci_low, color="black", linewidth=1, linestyle="--", alpha=0.5)
        ax.axvline(ci_high, color="black", linewidth=1, linestyle="--", alpha=0.5)
        ax.axvline(0, color="red", linewidth=0.8, linestyle=":", alpha=0.5)

        ax.set_title(f"{name}\n[{ci_low:.1f}, {ci_high:.1f}]", fontsize=12)
        ax.set_xlabel("Expected mood delta")
        ax.legend(fontsize=9)

    axes[0].set_ylabel("Density")
    fig.suptitle(f"Posterior mood improvement -- {participant_id}", fontsize=14, y=1.02)
    plt.tight_layout()

    if out_path:
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        print(f"  -> {out_path}")
    plt.close(fig)
    return fig


def export_streamlit_json(trace, model, out_path: Path):
    """Export per-participant x playlist posterior summaries as JSON for Streamlit."""
    codes = model._participant_codes
    result = {}

    for p_idx, participant in enumerate(codes):
        result[participant] = {}
        posterior = trace.posterior

        for k, name in enumerate(PLAYLIST_NAMES):
            alpha_samples = posterior["alpha"].values[:, :, p_idx].flatten()
            bp_samples = posterior["beta_playlist"].values[:, :, p_idx, k].flatten()
            predicted = alpha_samples + bp_samples

            result[participant][name] = {
                "mean": round(float(np.mean(predicted)), 2),
                "ci_low": round(float(np.percentile(predicted, 5.5)), 2),
                "ci_high": round(float(np.percentile(predicted, 94.5)), 2),
            }

    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"  -> {out_path}")
    return result


def prior_predictive_check(model, out_dir: Path, n_samples: int = 500) -> None:
    """Draw prior predictive samples and plot the implied mood_delta distribution.

    Answers: what mood outcomes does our prior believe are plausible before seeing data?
    A prior that generates mood_delta ∈ [-20, +20] is too wide; ∈ [-5, +5] is reasonable.
    """
    with model:
        prior_pred = pm.sample_prior_predictive(samples=n_samples, random_seed=42)

    # The prior predictive distribution for mood_delta_obs
    if "prior_predictive" in prior_pred:
        samples = prior_pred.prior_predictive["mood_delta_obs"].values.flatten()
    elif "mood_delta_obs" in prior_pred:
        samples = np.array(prior_pred["mood_delta_obs"]).flatten()
    else:
        print("  Prior predictive check: mood_delta_obs not found in samples, skipping plot.")
        return

    # Clip extreme tails for display (keep 99th percentile)
    p1, p99 = np.percentile(samples, [1, 99])
    samples_clipped = samples[(samples >= p1) & (samples <= p99)]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(samples_clipped, bins=60, density=True, alpha=0.75, color="#4A90D9", edgecolor="none")
    ax.axvline(0, color="#E8913A", linewidth=1.5, linestyle="--", label="Zero (no change)")
    ax.axvline(-3, color="gray", linewidth=1, linestyle=":", alpha=0.7, label="±3 (plausible range)")
    ax.axvline(+3, color="gray", linewidth=1, linestyle=":", alpha=0.7)
    ax.set_xlabel("Prior predictive mood_delta")
    ax.set_ylabel("Density")
    ax.set_title(
        f"Prior Predictive Check — Mood Delta\n"
        f"N={len(samples_clipped):,} samples | 1–99th pct: [{p1:.1f}, {p99:.1f}]"
    )
    ax.legend(fontsize=9)

    out_path = out_dir / "prior_predictive_check.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"  -> {out_path} (prior predictive range: {p1:.1f} to {p99:.1f})")
    plt.close(fig)

    # Summary stats
    print(f"  Prior predictive summary:")
    print(f"    mean={np.mean(samples):.2f}, std={np.std(samples):.2f}")
    print(f"    P(mood_delta > 0) = {(samples > 0).mean():.2%}")
    print(f"    P(|mood_delta| > 5) = {(np.abs(samples) > 5).mean():.2%} (would suggest wide priors)")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Hierarchical Bayesian playlist recommender")
    parser.add_argument("--participants", nargs="+", default=None,
                        help="Participants with biometric data (default: auto-detect)")
    parser.add_argument("--draws", type=int, default=1000)
    parser.add_argument("--tune", type=int, default=500)
    parser.add_argument("--chains", type=int, default=4)
    parser.add_argument("--reuse-trace", action="store_true",
                        help="Load existing trace.nc instead of re-sampling")
    args = parser.parse_args()

    print("=" * 60)
    print("  Bayesian Playlist Recommender -- Project R.E.M.")
    print("=" * 60)

    # Auto-detect participants with processed wearable data
    if args.participants:
        bio_participants = args.participants
    else:
        bio_participants = []
        wearables_dir = DATA_ROOT / "wearables"
        if wearables_dir.exists():
            for d in sorted(wearables_dir.iterdir()):
                if (d / "processed" / "session_biometrics.csv").exists():
                    bio_participants.append(d.name)

    print(f"\n  Participants with biometrics: {bio_participants or '(none)'}")

    # Build dataset
    print("  Loading and merging session data...")
    data, participant_codes = build_model_data(bio_participants)
    print(f"  Total sessions: {len(data)}")
    print(f"  Participants: {participant_codes}")
    print(f"  Sessions with biometrics: {data['has_biometrics'].sum()}")
    print(f"  Check-in only: {(~data['has_biometrics']).sum()}")

    # Show mood delta summary
    print(f"\n  Mood delta summary (valence-weighted):")
    for playlist in PLAYLIST_NAMES:
        subset = data[data["playlist"] == playlist]
        if not subset.empty:
            print(f"    {playlist:8s}: n={len(subset):2d}, mean={subset['mood_delta'].mean():+.1f}, "
                  f"range=[{subset['mood_delta'].min():+.0f}, {subset['mood_delta'].max():+.0f}]")

    # Output directory
    out_dir = DATA_ROOT / "analysis" / "bayesian_recommender"
    out_dir.mkdir(parents=True, exist_ok=True)
    trace_path = out_dir / "trace.nc"

    # Build model
    print(f"\n  Building hierarchical model...")
    model = build_hierarchical_model(data, participant_codes)

    # Prior predictive check (always run — fast, doesn't touch posterior)
    print(f"\n  Running prior predictive check...")
    prior_predictive_check(model, out_dir)

    # Sample or reuse existing trace
    if args.reuse_trace and trace_path.exists():
        print(f"  Loading existing trace from {trace_path}...")
        trace = az.from_netcdf(str(trace_path))
    else:
        print(f"  Sampling ({args.chains} chains x {args.draws} draws, {args.tune} warmup)...")
        trace = fit_model(model, draws=args.draws, tune=args.tune, chains=args.chains)

    # Convergence
    summary = check_convergence(trace)

    # Save trace summary
    summary.to_csv(out_dir / "parameter_summary.csv")
    print(f"  -> parameter_summary.csv")

    # Per-participant recommendations and plots
    print(f"\n  Recommendations:")
    all_recs = {}
    for participant in participant_codes:
        has_bio = participant in bio_participants

        # Use participant's mean biometric values as defaults if available
        p_data = data[data["participant"] == participant]
        rec_kwargs = {"hour_of_day": int(p_data["hour_of_day"].median())}
        if has_bio:
            for col in ["pre_stress_mean", "bb_start", "pre_hr_mean"]:
                val = p_data[col].dropna().median()
                if pd.notna(val):
                    # Map column names to recommend_playlist parameter names
                    param_name = {"pre_stress_mean": "pre_stress", "bb_start": "bb_start", "pre_hr_mean": "pre_hr"}[col]
                    rec_kwargs[param_name] = float(val)

        rec = recommend_playlist(trace, model, participant, **rec_kwargs)
        all_recs[participant] = rec
        emoji = "?" if rec["uncertain"] else ">"
        print(f"    {participant:15s} {emoji} {rec['recommendation']}")

        # Per-participant posterior plot
        participant_plot_dir = DATA_ROOT / "analysis" / participant / "bayesian_recommender" / "plots"
        participant_plot_dir.mkdir(parents=True, exist_ok=True)
        plot_posterior_panels(trace, model, participant, participant_plot_dir / f"posterior_{participant}.png")

    # Export JSON for Streamlit
    export_streamlit_json(trace, model, out_dir / "recommendations.json")

    # Save full recommendations
    with open(out_dir / "all_recommendations.json", "w") as f:
        json.dump(all_recs, f, indent=2, default=str)
    print(f"  -> all_recommendations.json")

    # Save trace for reuse (skip if we loaded it from the same file)
    if not args.reuse_trace:
        trace.to_netcdf(str(out_dir / "trace.nc"))
        print(f"  -> trace.nc")

    print(f"\n{'='*60}")
    print(f"  Done. Outputs in {out_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
