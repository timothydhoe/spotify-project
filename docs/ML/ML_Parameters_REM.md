# ML Hyperparameter Reference — Project R.E.M.

> **Project R.E.M.** (Regulation of Emotion through Music)
> This document catalogues the hyperparameter choices for every ML model in the project,
> explains the rationale behind each setting, and flags known limitations.
> Intended as a reference for reproducibility and future tuning.

---

## Table of Contents

1. [Ridge Regression](#1-ridge-regression)
2. [Random Forest](#2-random-forest)
3. [Gradient Boosting](#3-gradient-boosting)
4. [LSTM Stress-Arc Model](#4-lstm-stress-arc-model)
5. [Bayesian Hierarchical Model](#5-bayesian-hierarchical-model)
6. [GMM Clustering](#6-gmm-clustering)
7. [Cross-Cutting Decisions](#7-cross-cutting-decisions)

---

## 1. Ridge Regression

**Source:** `notebooks/ml/1_circadian_ml.ipynb`
**Task:** Predict `mood_delta` and `stress_delta` from tabular session features
**Validation:** Leave-One-Out cross-validation (N=95 for mood_delta; N=75 for stress_delta)

| Parameter | Value | Default? | Rationale |
|-----------|-------|----------|-----------|
| `alpha` | 1.0 | Yes (sklearn) | L2 regularisation strength. Shrinks coefficients toward zero to prevent overfitting at small N. |

### Tuning performed

A sensitivity sweep was run over alpha ∈ {0.01, 0.1, 1.0, 10.0, 100.0} using explicit LOO-CV:

| alpha | mood_delta LOO MAE | stress_delta LOO MAE |
|------:|-------------------:|---------------------:|
| 0.01  | 1.548              | **2.642**            |
| 0.10  | 1.537              | 2.653                |
| 1.00  | 1.500              | 3.081                |
| 10.00 | **1.460**          | 3.378                |
| 100.00| 1.464              | 3.634                |

**Limitation:** alpha=1.0 is not optimal for either target. For mood_delta, alpha=10 yields 2.7% lower MAE (1.460 vs 1.500). For stress_delta, alpha=0.01 is substantially better (2.642 vs 3.081). The default alpha=1.0 was retained as the consistent baseline across analyses, but target-specific tuning would improve performance.

### Performance

- mood_delta: LOO MAE=1.500, R²=0.318 (train R²=0.552, gap=0.234)
- Bootstrap 95% CI on LOO MAE: [1.292, 1.746]
- Ridge was selected as the most reliable model at this sample size.

---

## 2. Random Forest

**Source:** `notebooks/ml/1_circadian_ml.ipynb`
**Task:** Same as Ridge (tabular mood/stress prediction)
**Validation:** LOO-CV

| Parameter | Value | Default? | Rationale |
|-----------|-------|----------|-----------|
| `n_estimators` | 100 | Yes (sklearn) | Number of trees. Default is sufficient; more trees add compute without meaningful variance reduction at small N. |
| `max_depth` | 3 | **No — tuned** | Caps tree depth to prevent memorising the training set. Code comment: *"beperkt boomdiepte tegen overfitting bij N<100"* (limits depth against overfitting at N<100). |
| `random_state` | 42 | No (reproducibility) | Fixed seed for deterministic results. |

### Tuning performed

`max_depth=3` was set manually — no cross-validated depth sweep was performed.

### Performance and limitation

- mood_delta: LOO MAE=1.617, R²=0.229 (train R²=0.649, gap=0.421)
- Overfitting gap is larger than Ridge despite depth limiting. Underperforms Ridge on both MAE and generalisation stability.

---

## 3. Gradient Boosting

**Source:** `notebooks/ml/1_circadian_ml.ipynb`
**Task:** Same as Ridge (tabular mood/stress prediction)
**Validation:** LOO-CV

| Parameter | Value | Default? | Rationale |
|-----------|-------|----------|-----------|
| `n_estimators` | 50 | **No — reduced** | Fewer boosting rounds to limit model capacity (sklearn default is 100). |
| `max_depth` | 2 | **No — reduced** | Shallower trees = weaker learners = slower fitting of noise (sklearn default is 3). |
| `learning_rate` | 0.1 | Yes (sklearn) | Step-size shrinkage per round. Default value retained. |
| `random_state` | 42 | No (reproducibility) | Fixed seed. |

Code comment: *"bewust klein voor betere generalisatie"* (deliberately small for better generalisation).

### Tuning performed

Parameters were set manually with a conservative philosophy. No automated hyperparameter search was performed.

### Known limitation

Despite conservative settings, Gradient Boosting still overfits severely:

- mood_delta: train R²=0.789 vs LOO R²=0.202 (gap=0.587)
- LOO MAE=1.609 — worse than Ridge (1.500)

**Conclusion:** The model memorises training data even with shallow trees and few estimators. At N=95, boosting is not viable for this problem without substantially more data.

---

## 4. LSTM Stress-Arc Model

**Source:** `scripts/analysis/lstm_arc.py`
**Task:** Sequence-to-scalar regression — per-minute stress/HR time series during a session → predicted `mood_delta`
**Validation:** LOO-CV (N=74 sessions with both wearable traces and mood scores)

| Parameter | Value | Default? | Rationale |
|-----------|-------|----------|-----------|
| `SEQ_LEN` | 35 | **No — data-driven** | Median during-phase length in minutes. Longer sessions are truncated; shorter ones are zero-padded to this length. |
| `HIDDEN_SIZE` | 32 | **No — deliberately small** | Limits representational capacity to prevent overfitting at N=74. |
| `N_LAYERS` | 1 | Minimal | Single LSTM layer. Deeper networks would overfit at this scale. |
| `DROPOUT` | 0.0 | N/A | Dropout disabled. Regularisation comes from data augmentation (jitter) instead. |
| `EPOCHS` | 80 | **No — manually set** | Training duration. No early stopping is implemented. |
| `LR` | 1e-3 | Yes (Adam default) | Adam optimiser learning rate. |
| `BATCH_SIZE` | 16 | **No — manually set** | Small batches add gradient noise, acting as implicit regularisation. |
| `AUGMENT_FACTOR` | 5 | **No — manually set** | Each training session generates 5 jittered copies, inflating effective training set from ~73 to ~365 per LOO fold. |
| `JITTER_STRESS` | 3.0 | **No — manually set** | Standard deviation of Gaussian noise added to the stress channel during augmentation. |
| `JITTER_HR` | 2.0 | **No — manually set** | Standard deviation of Gaussian noise added to the heart rate channel. Smaller than stress jitter because HR has a narrower natural within-session range. |
| `SEED` | 42 | No (reproducibility) | Fixed seed for Python random, NumPy, and PyTorch. |

### Design rationale

The LSTM tests the ISO principle hypothesis: the *temporal shape* of the stress arc (steep drop vs gradual decline, mid-session HR rebound) matters for mood outcomes — not just the session mean. Tabular models (Ridge, RF, GBR) discard this temporal information by using aggregated features. An LSTM reading the full 35-minute sequence can distinguish these patterns.

### Tuning performed

All parameters were set manually. No automated hyperparameter search was performed. Jitter magnitudes are heuristic, not cross-validated.

### Known limitation

- No early stopping: the model may train past optimal generalisation.
- Jitter magnitudes are not tuned via CV.
- N=74 is extremely small for a recurrent neural network. All results are exploratory.

---

## 5. Bayesian Hierarchical Model

**Source:** `notebooks/ml/2_bayesian_recommender.ipynb`
**Task:** Estimate participant-level and playlist-level effects on mood outcome with partial pooling across N=6 participants (~17 sessions each, N=82 total)
**Framework:** PyMC (NUTS sampler)

### Sampler settings

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `DRAWS` | 1000 | Posterior samples per chain. Standard for stable posterior mean estimates. |
| `TUNE` | 500 | NUTS warmup/burn-in steps. Allows the sampler to adapt step size and mass matrix before drawing posterior samples. |
| `CHAINS` | 4 | Four parallel Markov chains enable Gelman-Rubin (R-hat) convergence diagnostics (R-hat < 1.01 = converged). |
| `TARGET_ACCEPT` | 0.9 | Higher than the PyMC default of 0.8. More cautious step size in NUTS reduces divergences at the cost of slightly slower sampling. |

### Prior specification

| Parameter | Prior | Rationale |
|-----------|-------|-----------|
| `mu_alpha` | Normal(0, 5) | Weakly informative group-level intercept prior. Wide spread encodes little prior knowledge. |
| `sigma_alpha` | HalfNormal(2) | Participant-level intercept variance. HalfNormal enforces positivity. |
| `mu_playlist` | Normal(0, 5) | Group-level playlist effect. Wide prior. |
| `sigma_playlist` | HalfNormal(2) | Playlist-level variance across participants. |
| `beta_*` (covariates) | Normal(0, 2) | Regression coefficients for stress, body battery, HR, hour. Tighter than intercept priors — encodes mild shrinkage toward zero. |
| `sigma` (residual) | HalfNormal(5) | Observation noise. Wide to let the data determine residual variance. |

### Design rationale

With only 6 participants, fitting separate regression models per participant would overfit. A hierarchical model with partial pooling borrows strength across participants: individual estimates are pulled toward the group mean proportionally to how noisy each participant's data is. Participants with fewer sessions benefit more from the group prior. Non-centred parameterisation is used to prevent NUTS divergences in the funnel geometry typical of hierarchical models.

### Known limitation

- All 89% HDI intervals for biometric predictors include zero — no credible nonzero effects at this sample size.
- N=82 sessions across 6 participants is well below the ~600 sessions estimated as necessary for adequate power.
- Results are exploratory, not confirmatory.

---

## 6. GMM Clustering

**Source:** `notebooks/ml/4_music_class_unsupervised.ipynb`
**Task:** Discover latent groupings in Spotify audio features for playlist classification (calm / neutral / energy)

### Model settings

| Parameter | Value | Default? | Rationale |
|-----------|-------|----------|-----------|
| `n_components` | Swept 2–10 | N/A | Range of cluster counts evaluated via BIC. |
| `covariance_type` | `'full'` | Yes (sklearn) | Each cluster gets its own unconstrained covariance matrix. More flexible than `'tied'` or `'diag'`; appropriate when clusters may have different shapes and orientations in feature space. |
| `n_init` | 5 | **No — increased from 1** | Multiple random initialisations reduce sensitivity to poor starting conditions in the EM algorithm. |
| `random_state` | 42 | No (reproducibility) | Fixed seed. |

### Preprocessing

**StandardScaler** (z-score normalisation) is used instead of MinMaxScaler. GMM assumes Gaussian-distributed features; z-scores centre and scale each feature to mean=0, std=1. This prevents numeric scale dominance — for example, tempo in BPM (range ~60–200) vs energy in 0–1 would distort distance calculations without scaling.

### Model selection

BIC (Bayesian Information Criterion) is the primary selection criterion:

```
BIC = -2 × log-likelihood + k × log(n)
```

BIC rewards models that fit the data well but penalises unnecessary complexity (more clusters). AIC is computed as a secondary check.

**Important nuance:** BIC decreased monotonically from k=2 through k=10 — no true minimum was found within the search range. k=5 was selected as a pragmatic choice where the BIC curve begins to flatten (elbow heuristic), not as a statistical optimum.

| k | BIC    | Silhouette |
|--:|-------:|-----------:|
| 2 | 82,571 | 0.399      |
| 3 | 75,271 | 0.134      |
| 5 | 71,738 | 0.072      |

k=3 is also used for interpretability, aligning with the three predefined playlist categories (calm / neutral / energy), despite having a higher BIC.

### Known limitation

- No true BIC optimum exists in the tested range; the "optimal" k is a judgment call.
- Silhouette scores are very low (0.072 at k=5), indicating high cluster overlap. The audio feature space is a continuous spectrum, not discrete categories.
- k=3 forced clustering trades statistical fit for domain alignment with the ISO principle.

---

## 7. Cross-Cutting Decisions

### Random state

All models use `random_state=42` for reproducibility. This is a project-wide convention ensuring deterministic results across runs.

### Validation strategy

Leave-One-Out (LOO) cross-validation is used throughout all supervised models. At N<100, LOO maximises the training set size per fold and gives an unbiased (though high-variance) estimate of generalisation error. K-fold CV was not used because even k=5 would reduce training sets to ~76 samples, further limiting model fitting at small N.

### Sample sizes

| Model | N | Notes |
|-------|---|-------|
| Ridge / RF / GBR (mood_delta) | 95 | Sessions with check-in mood scores |
| Ridge / RF / GBR (stress_delta) | 75 | Sessions with usable stress data |
| LSTM | 74 | Sessions with minute-level wearable traces + mood scores |
| Bayesian hierarchical | 82 | 6 participants, ~17 sessions each |
| GMM | Full playlist catalogue | All tracks with Spotify audio features |

### Overall limitation

The dominant constraint across all models is sample size. Effect sizes may exist but cannot be confirmed at current N. The project treats all ML results as exploratory pattern-finding, not as confirmatory statistical evidence.

---

*Generated for Project R.E.M. — Last updated: 2026-06-19*
