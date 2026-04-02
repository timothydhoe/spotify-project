# ML Model Proposals — Project R.E.M.

## Task distribution

Astrid:

- [ ] Bayesian Per-Participant Playlist Recommender
- [ ] Circadian Baseline Deviation + Playlist Outcome Regression

Timothy:

- [ ] 1D-CNN on Per-Minute Pre-Session Stress Trajectories

Generated: 2026-04-02

## Data Overview

- **3 participants with wearables:** bosbes + kokosnoot (Garmin: stress + HR + Body
  Battery per minute), limoen (Huawei: HR only)
- **Session traces:** ~60-min pre + playing + 30-min post, per minute — richest signal
  available
- **~31 total sessions** across participants; 47 check-in responses from 7+
  participants (mood 1–10 + categorical, pre/post)
- **Daily aggregates** with 7-day rolling averages — good for circadian baseline
  computation
- **Key constraints:** small N (~31 sessions), device heterogeneity (Garmin vs Huawei),
  sporadic stress sampling

---

## Proposal 1 — Circadian Baseline Deviation + Playlist Outcome Regression

**Research questions addressed:** RQ1, RQ2
**Paradigm:** Classical ML (Ridge, Random Forest, Gradient Boosting) + SHAP
explainability

### Rationale

The strongest signal in the data isn't raw stress — it's *how much a participant
deviates from their own normal stress at that hour of day*. This controls for natural
circadian rhythms (you're always more tired at 9pm). Combined with playlist type and
pre-session mood, this feature set is interpretable and directly answers whether
personalized playlists measurably reduce stress (RQ1) and whether that correlates with
mood improvement (RQ2). Classical ML with SHAP explainability is ideal for a small N and
produces outputs that translate directly into the Streamlit presentation ("your calmest
hour is 14:00").

### Prompt for Claude Opus

> You are a data scientist working on Project R.E.M., a research study on music-based
> emotion regulation. Each participant wore a Garmin smartwatch throughout the study (
> December 2025 – March 2026). You have three data sources:
>
> **1. `garmin_daily.csv`** (per-participant, ~90 rows): columns include `date`,
`avg_stress`, `resting_hr`, `bb_highest`, `bb_lowest`, plus rolling 7-day averages. Use
> this to compute a per-participant, per-hour-of-day *stress baseline* from non-session
> days.
>
> **2. `session_biometrics.csv`** (per-participant, ~8–17 rows): columns include `date`,
`start_local`, `playlist` (Calm/Neutral/Energy), `pre_stress_mean` (60-min pre-session),
`stress_mean` (during), `post_stress_mean`, `pre_hr_mean`, `bb_start`, `bb_end`,
`stress_delta`, `mood_before_score` (1–10), `mood_after_score`, `mood_before` (
> categorical Dutch text).
>
> **3. `garmin_minute_stress.csv`** (per-participant, ~90 days × 1440 min): timestamp +
> stress value (0–100, sporadic). Use this to compute precise hour-of-day baseline stress
> distributions.
>
> **Your task:**
>
> 1. For each participant, compute a **circadian stress baseline**: the mean (and std)
     stress at each hour of day H, using only *non-session* days. This is their "
     expected" stress at time H.
> 2. Compute the **baseline deviation at session start**:
     `deviation = pre_stress_mean − baseline_stress[hour_of_day]`. A positive deviation
     means the participant was more stressed than usual going into the session.
> 3. Build a feature matrix with one row per session:
     >
- `baseline_deviation_entry` (computed above)
>    - `hour_of_day` (session start hour, 0–23)
>    - `day_of_week` (0=Monday)
>    - `playlist_type` (one-hot: Calm, Neutral, Energy)
>    - `mood_before_score` (1–10)
>    - `bb_start` (Body Battery at session start, 0–100)
>    - `days_since_last_session` (recency effect)
> 4. Fit three models to predict `mood_delta` (= mood_after_score − mood_before_score):
     >
- Ridge Regression (regularized linear baseline)
>    - Random Forest Regressor
>    - Gradient Boosting Regressor (XGBoost or sklearn)
> 5. Use leave-one-session-out cross-validation (given small N).
> 6. Compute SHAP values for the best model and plot feature importances.
> 7. Also fit models to predict `stress_delta` (= post_stress_mean − pre_stress_mean)
     with the same feature set.
>
> Participants: `bosbes`, `kokosnoot`. Pool data across participants (add
`participant_id` as a categorical feature). Paths:
`data/wearables/{codename}/processed/`. Write clean, documented Python using pandas,
> scikit-learn, shap, and matplotlib. Handle missing values explicitly (some
> post_stress_mean values are NaN — drop those rows or impute from session traces).

---

## Proposal 2 — 1D-CNN on Per-Minute Pre-Session Stress Trajectories

**Research questions addressed:** RQ3
**Paradigm:** Deep Learning (1D Convolutional Neural Network) + Grad-CAM
interpretability

### Rationale

The 60-minute pre-session per-minute trace is a time-series snapshot of arousal *right
before* the music intervention. A 1D-CNN can learn local patterns (sharp stress spikes,
gradual decline, plateau) that predict how well the participant responds. This addresses
RQ3 (classify playlist type from biometrics — flipped: predict outcome *from* the
pre-session physiology). With small N, a shallow CNN + data augmentation (window jitter,
Gaussian noise) is more appropriate than an LSTM. The architecture is also reusable once
more participants join the study.

### Prompt for Claude Opus

> You are a machine learning engineer working on Project R.E.M. You have per-minute
> smartwatch traces for Garmin participants (`bosbes`, `kokosnoot`). Each session has a
> file in
`data/wearables/{codename}/processed/session_traces/trace_YYYY-MM-DD_PLAYLIST.csv` with
> columns: `timestamp_utc`, `stress` (0–100), `body_battery` (0–100), `heart_rate` (BPM),
`phase` ("pre" / "playing" / "post"), `minutes_relative` (–60 to ~+60), `playlist`,
`session_date`.
>
> **Your task — build a 1D-CNN that predicts mood improvement from the pre-session
physiological trajectory:**
>
> 1. **Data preparation:**
     >
- Extract the `pre` phase rows (minutes_relative –60 to –1) for each session.
>    - Resample to exactly 60 time steps (1 per minute, forward-fill gaps).
>    - Build multivariate input tensor: shape `(n_sessions, 60, 3)` — channels are
       stress, body_battery, heart_rate.
>    - Normalize each channel per-participant (z-score using non-session daily data as
       reference).
>    - Target variable: `mood_delta` (mood_after_score − mood_before_score) from
       `session_biometrics.csv`. Binarize as: `improved` (delta > 0) vs `not improved` (
       delta ≤ 0).
>
> 2. **Data augmentation** (to compensate for ~20 sessions total):
     >
- Time-shift augmentation: randomly shift the 60-min window ±5 minutes.
>    - Gaussian noise injection (σ = 0.05 of feature std) on stress and HR channels.
>    - Synthetic minority oversampling if classes are imbalanced.
>    - Target 5× augmentation of the training set.
>
> 3. **Model architecture (PyTorch or Keras):**
     >    ```
>    Input: (batch, 60, 3)
>    Conv1D(filters=32, kernel=5, activation=relu) + BatchNorm + Dropout(0.3)
>    Conv1D(filters=64, kernel=3, activation=relu) + BatchNorm + Dropout(0.3)
>    GlobalAveragePooling1D
>    Dense(32, relu) + Dropout(0.2)
>    Dense(1, sigmoid)  → binary: improved / not improved
>    ```
>
> 4. **Training:** Leave-one-session-out cross-validation. Report ROC-AUC, precision,
     recall, and balanced accuracy for each fold. Plot the averaged ROC curve.
>
> 5. **Interpretability:** Use **Grad-CAM** (applied to 1D-CNN) to identify which
     minutes in the pre-session window are most predictive. Plot the attribution heatmap
     averaged across sessions for each class (improved vs. not improved).
>
> 6. **Ablation:** Train three variants — (a) stress only, (b) HR only, (c) all three
     channels — and compare AUC. This tells us which biometric is the dominant
     predictor.
>
> Pool sessions from both participants. Add `participant_id` as a one-hot vector
> concatenated after pooling. Handle sessions where `mood_after_score` is missing by
> dropping. Write clean Python with detailed comments.

---

## Proposal 3 — Bayesian Per-Participant Playlist Recommender

**Research questions addressed:** RQ4, RQ5
**Paradigm:** Hierarchical Bayesian regression (PyMC) with partial pooling

### Rationale

The most novel scientific contribution of the project (RQ5) is: *given your current
physiological state, which playlist type will produce the best mood outcome for you
specifically?* With only ~10 sessions per participant, a Bayesian model is the
principled choice — it quantifies uncertainty honestly ("we're 70% confident Calm works
better for you at high stress") rather than overfitting. Hierarchical partial pooling
means participants with fewer sessions borrow statistical strength from the group. This
produces credible intervals that translate directly into the Streamlit "Spotify Wrapped"
presentation.

### Prompt for Claude Opus

> You are a Bayesian statistician working on Project R.E.M. The goal is to build a *
*personalized playlist recommender**: given a participant's current physiological state,
> predict which playlist type (Calm / Neutral / Energy) will produce the best mood outcome
> for *that specific participant*.
>
> **Data:** `session_biometrics.csv` for participants `bosbes` and `kokosnoot` (paths:
`data/wearables/{codename}/processed/session_biometrics.csv`). Also load
`data/checkins/Check-in_formulier_REM.csv` for additional mood annotations from
> participants without wearables (peer, kiwi, watermeloen, etc.).
>
> **Feature set per session:**
> - `pre_stress_mean` (0–100, or NaN → drop)
> - `bb_start` (0–100, Body Battery)
> - `pre_hr_mean` (BPM)
> - `hour_of_day` (0–23, from start_local)
> - `mood_before_score` (1–10)
> - `playlist` → outcome grouping variable (Calm=0, Neutral=1, Energy=2)
> - Target: `mood_delta` = mood_after_score − mood_before_score
>
> **Your task — hierarchical Bayesian regression using PyMC:**
>
> 1. **Model design — partial pooling (hierarchical):**
     > Treat participants as groups in a hierarchical model so that participants with
     fewer sessions borrow statistical strength from the group. Each participant gets
     their own `β_playlist` coefficients, but these are drawn from a shared group-level
     prior.
     >    ```
>    mood_delta[i] ~ Normal(μ[i], σ)
>    μ[i] = α[participant[i]] + β_stress[participant[i]] * pre_stress_z[i]
>             + β_bb[participant[i]] * bb_z[i]
>             + β_playlist[participant[i], playlist[i]]
>             + β_hour * hour_z[i]
>
>    # Group-level priors (hyperpriors)
>    α[p] ~ Normal(μ_α, σ_α)
>    β_playlist[p, k] ~ Normal(μ_playlist[k], σ_playlist)  for k in {Calm, Neutral, Energy}
>    ```
>
> 2. **Inference:** Use NUTS sampler (4 chains, 2000 draws, 1000 warmup). Check
     convergence: R-hat < 1.01, effective sample size > 400.
>
> 3. **Posterior predictive check:** For each participant × playlist combination, plot
     the posterior distribution of expected mood_delta. Show 89% credible intervals.
>
> 4. **Recommendation function:**
     >    ```python
>    def recommend_playlist(participant_id, pre_stress, bb_start, pre_hr, hour_of_day, mood_before):
>        # Returns: dict of {playlist: (mean_delta, credible_interval_89)}
>        # and a recommendation with confidence:
>        # "Calm (72% probability of highest mood improvement)"
>    ```
>
> 5. **Decision under uncertainty:** Use expected utility — recommend the playlist with
     the highest posterior mean mood_delta, but flag when credible intervals
     substantially overlap (uncertainty > threshold → "not enough data yet to
     personalise").
>
> 6. **Include check-in-only participants** (peer, kiwi, etc.) in the hierarchical model
     using only mood scores (no biometrics) — they still inform the group-level playlist
     effect priors.
>
> 7. **Output for Streamlit:** For each participant, produce a 3-panel posterior plot (
     one per playlist type) showing the distribution of expected mood improvement.
     Export as JSON:
     `{participant: {playlist: {mean: float, ci_low: float, ci_high: float}}}`.
>
> Write in Python using PyMC ≥ 5.0 and ArviZ for diagnostics. Add detailed comments
> explaining each modelling choice.

---

## Additional Options

These are simpler or complementary approaches that are feasible within the current data
constraints.

---

### Option 4 — Survival Analysis: How Long Until Mood Recovers?

**Research questions addressed:** RQ1, RQ2 (extended)
**Paradigm:** Survival analysis (Kaplan-Meier + Cox Proportional Hazards)
**Effort:** Low-medium

Rather than predicting mood_delta as a point estimate, frame it as a *time-to-event*
problem: how many minutes into a session does physiological stress drop below a
threshold? The per-minute session traces give you exactly this censored time-series.
Kaplan-Meier curves, stratified by playlist type, would make a compelling visualization
for the Streamlit app ("Calm playlists cross the stress threshold 8 minutes faster on
average"). Cox regression adds covariates (pre_stress, hour_of_day). Works with the
existing small N; no augmentation needed.

**Key libraries:** `lifelines`

---

### Option 5 — Unsupervised Session Clustering (k-Means / UMAP)

**Research questions addressed:** RQ3 (exploratory)
**Paradigm:** Unsupervised clustering + dimensionality reduction
**Effort:** Low

Cluster all sessions by their biometric trajectory shape (pre + during + post
stress/HR), without using playlist labels. Then check: do the discovered clusters align
with Calm/Neutral/Energy? If yes, this validates that biometrics alone capture the
playlist effect. If no, it reveals confounders (time of day, participant state). Use
UMAP for 2D visualization — produces a publication-quality figure and a natural
Streamlit scatter plot. Feature engineering: summary statistics per phase (mean, slope,
std of stress), or use DTW-based distance for the clustering.

**Key libraries:** `scikit-learn`, `umap-learn`, `dtaidistance`

---

### Option 6 — N-of-1 Interrupted Time Series (ITS) per Participant

**Research questions addressed:** RQ1 (causal framing)
**Paradigm:** Segmented regression / interrupted time series (classical statistics)
**Effort:** Low

For each participant, treat the continuous daily stress time series (90 days from
`garmin_minute_stress.csv`) as a single long time series and model playlist sessions as
*interventions*. Fit a segmented regression that estimates: (a) the level change in
stress immediately after each session, and (b) whether the trend (slope) changes
post-session. This is the most causally defensible design given the lack of a formal
control group — it uses each participant as their own control. The small N is not a
problem here because inference is within-participant. Works especially well for
`kokosnoot` who has 17 sessions.

**Key libraries:** `statsmodels` (OLS with dummy variables for intervention points), or
the `causalimpact` Python port

---

### Option 7 — Audio Feature × Biometric Correlation Analysis

**Research questions addressed:** RQ3, RQ5 (feature discovery)
**Paradigm:** Correlation / multivariate regression
**Effort:** Low (good starting point before ML)

Join the generated playlist CSVs (which contain Spotify audio features: tempo, energy,
valence, danceability, acousticness per song) with the per-minute session traces. At
each minute, you know which song was approximately playing (given start time + track
duration). Correlate audio features of the currently-playing song with the biometric
reading at that minute. This could reveal: "valence > 0.7 correlates with HR decrease 2
minutes later" or "high danceability predicts Body Battery stability." Produces
actionable insights for playlist parameter tuning and feeds directly into RQ5 (which
audio features drive mood regulation?).

**Key libraries:** `pandas`, `scipy.stats`, `seaborn`

---

## Open Questions

1. **Priority order?** Which research question is most urgent — the Streamlit output (
   RQ5 → Proposal 3), the circadian analysis (RQ1/2 → Proposal 1), or the trajectory
   model (RQ3 → Proposal 2)?
2. **limoen inclusion:** limoen has no stress data (Huawei). Proposals 1 and 2 currently
   exclude limoen. Should they be adapted to work with HR-only as a degraded feature
   set?
3. **PyMC availability:** Is PyMC installed, or would a lighter Bayesian alternative be
   preferred (e.g., `statsmodels` Bayesian GLM, or `scipy` MCMC)?
4. **More participants incoming?** The study runs until June 2026. More Garmin
   participants would significantly improve the 1D-CNN (Proposal 2); the Bayesian
   model (Proposal 3) handles small N better by design and is the safer near-term bet.
