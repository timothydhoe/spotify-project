# Wham-Bam-Shang-A-Lang
### Project R.E.M. — Complete Walkthrough

---

## Contents

1. [Project Overview](#1-project-overview)
2. [Data Sources](#2-data-sources)
3. [Playlist Generation Pipeline](#3-playlist-generation-pipeline)
4. [Wearables Pipeline](#4-wearables-pipeline)
5. [Feature Engineering](#5-feature-engineering)
6. [ML Models](#6-ml-models)
7. [The Shiny App](#7-the-shiny-app)
8. [Research Questions](#8-research-questions)

---

## Overall Picture

**R.E.M.** (Regulation of Emotion through Music) asks: can a personalized music playlist measurably change how someone feels — and can we prove it with biometric data?

Participants wore a smartwatch, exported their Spotify library, and filled in mood check-ins before and after each listening session. The system generated three playlist types per person (Calm / Neutral / Energy), cross-referenced with their biometric data, and fed everything into ML models and a Bayesian recommender.

The final output is a Shiny for Python app styled like Spotify Wrapped — per-participant summaries, model explainability, and live recommendations.

---

## Full Data Flow

```
PARTICIPANT
    │
    ├─── Spotify Library ──► Exportify CSV export
    │                              │
    │                              ▼
    │                       [PLAYLIST PIPELINE]
    │                       prepare.py → generate.py → analyse.py
    │                              │
    │                              ▼
    │                       Calm / Neutral / Energy CSVs
    │                       (12 songs, ISO-ordered)
    │
    ├─── Smartwatch ────────► Garmin / Huawei GDPR export
    │   (Garmin / Huawei)          │
    │                              ▼
    │                       [WEARABLES PIPELINE]
    │                       garmin_pipeline.py / huawei_pipeline.py
    │                              │
    │                              ▼
    │                       Minute-level stress + HR
    │                       Session biometrics + traces
    │
    └─── Google Form ───────► Check-in CSV
         (mood before/after)       │
                                   │
                     ─────────────────────────────
                     JOIN KEY: codename + date + time
                     ─────────────────────────────
                                   │
                                   ▼
                          [FEATURE ENGINEERING]
                          Circadian baseline deviation
                          Session feature matrix (28 cols)
                          Recovery curve fitting (τ)
                                   │
                                   ▼
                          [ML MODELS]
                          ├── Circadian ML (Ridge / RF / GBR)
                          │     → Predict mood_delta / stress_delta
                          ├── Music Classification
                          │     → Arousal score (threshold) + GMM
                          ├── Bayesian Recommender
                          │     → Playlist recommendation per state
                          └── LSTM Arc (experimental)
                                   │
                                   ▼
                          [SHINY APP]
                          "MoodTune" — Spotify Wrapped style
                          Per-participant summaries + live demo
```

---

## 1. Project Overview

### What is R.E.M.?

R.E.M. stands for *Regulation of Emotion through Music*. The study asks whether personalized music playlists can regulate emotional states — and whether that effect shows up in both self-reported mood *and* objective biometric signals (heart rate, stress).

Participants are anonymized with fruit codenames: `bosbes`, `kiwi`, `kokosnoot`, `limoen`, `peer`, `watermeloen`. Each participant contributed their Spotify library, wore a smartwatch throughout the study, and submitted mood check-ins before and after every listening session.

### The Three Playlist Types

Each participant gets three playlist types, serving different purposes:

| Playlist | BPM Range | Energy  | ISO Direction  | Purpose            |
|----------|-----------|---------|----------------|--------------------|
| Calm     | 50–95     | < 0.9   | Descending BPM | Stress reduction   |
| Neutral  | 95–115    | 0.2–0.8 | Stable         | Control condition  |
| Energy   | 120–180   | > 0.7   | Ascending BPM  | Arousal / alertness|

Target: 12 songs (~30 min), minimum 10 songs to pass validation.

### The ISO Principle

The ISO principle is the scientific backbone of playlist construction. Instead of jumping straight to a target mood, it says: **meet the listener where they are, then guide them gradually.**

- A Calm playlist doesn't start with the most relaxing song. It starts near the listener's current arousal level and *descends* in BPM and energy.
- An Energy playlist *ascends*.
- A Neutral playlist stays flat — it's the control condition, no directional push.

This matters because abrupt transitions are less effective at emotion regulation than gradual ones. The *order* of songs is just as important as which songs are selected.

### Why Personal Music?

Self-chosen music is significantly more effective at emotion regulation than unfamiliar selections. The system is built around each participant's own Spotify library — the classifier has to work with whatever that person actually listens to, not a curated set.

---

## 2. Data Sources

Three data streams feed the entire project. They only become useful when joined together.

### Source 1: Exportify CSVs (Spotify)

Participants export their Spotify library using **Exportify**, which produces CSVs where each row is a track with audio features pre-attached. These features are **computed by Spotify** — R.E.M. uses them as-is.

| Feature | What it measures |
|---|---|
| `tempo` | BPM — primary filter for playlist type |
| `energy` | Perceptual intensity (0–1) |
| `valence` | Musical positivity / happiness (0–1) |
| `danceability` | Beat regularity (0–1) |
| `acousticness` | Acoustic vs. electronic (0–1) |
| `loudness` | Volume dynamics in dB |

A participant may export multiple playlists or their full library. `prepare.py` combines and deduplicates them into one clean file per participant.

### Source 2: Garmin / Huawei GDPR Exports

Participants request a full GDPR export from their smartwatch manufacturer. This contains:
- **JSON files** — daily aggregates (steps, Body Battery, sleep stages, resting HR)
- **FIT binary files** — proprietary Garmin format; minute-by-minute stress and heart rate

**Timezone gotcha:** FIT files store timestamps in UTC. Check-in times are in CET (UTC+1). If not corrected, the session extraction window shifts by one hour — the pipeline would extract pre-session noise as "during-session" data, and the actual session effect would fall out of scope entirely. The numbers would still look plausible, making it a silent bug.

### Source 3: Google Forms Check-ins

A single CSV: `data/checkins/Check-in_formulier_REM.csv`

Each row records participant codename, date + time, mood before, mood after, and playlist type used. This file is the **join key for the entire project** — without it, there's no way to link a biometric trace to a specific session or compute mood delta.

### How They Join

```
Exportify CSV  ──────────────────────► Playlist generation (standalone)

Garmin export ──┐
                ├──► JOIN on: codename + date + time
Check-in CSV  ──┘         │
                           ▼
                  session_biometrics.csv
                  mood_delta per session
```

---

## 3. Playlist Generation Pipeline

Entry point: `spotify_cli.py all [codename]` — runs three steps in sequence.

### A: `prepare.py` — Clean & Merge

Reads all Exportify CSVs for a participant, deduplicates tracks (same song in multiple playlists), and drops tracks with missing audio features. Outputs one clean library CSV per participant. Duplicates would inflate generation options and skew feature distributions.

### B: `generate.py` — Filter, Order, Smooth

**1. BPM/energy filtering** — Each song is assigned to a candidate pool:

| Playlist | Keep if... |
|----------|-----------|
| Calm | tempo 50–95 BPM AND energy < 0.9 |
| Neutral | tempo 95–115 BPM AND energy 0.2–0.8 |
| Energy | tempo 120–180 BPM AND energy > 0.7 |

**2. ISO ordering** — Songs are sorted to create a gradient across the arc:
- Calm: descending BPM (start higher, end lower)
- Energy: ascending BPM (start lower, end higher)
- Neutral: stable BPM (minimal variance)

12 songs are selected to represent the full arc — not just the 12 lowest BPM, but songs spread across the gradient.

**3. Loudness smoothing** — Adjacent songs are checked for volume jumps. Dramatic loudness swings break the gradual-transition effect, so ordering is adjusted slightly to smooth them.

### C: `analyse.py` — Validate (3 of 4 criteria)

| # | Criterion | What it checks |
|---|---|---|
| 1 | Tempo ranges | Songs fall within the target BPM range |
| 2 | Energy separation | Each playlist's mean energy is in the right zone |
| 3 | BPM gap | ≥ 15 BPM gap between calm and energy playlist means |
| 4 | Duration | Each playlist ≥ 25 minutes |

If validation fails, `analyse.py` reports which criteria failed and by how much. Parameters can be tuned and regenerated:

```bash
uv run python spotify_cli.py generate kokosnoot --calm-tempo-max 80 --upbeat-energy-min 0.7
```

**Why the BPM gap matters scientifically:** if calm and energy playlists overlap too much in tempo, you can't attribute any observed biometric or mood effect to playlist *type* — the experimental condition collapses.

---

## 4. Wearables Pipeline

Entry point: `garmin_pipeline.py [codename]` / `huawei_pipeline.py [codename]`

### The Raw Export

Participants request their full GDPR data export from Garmin Connect or Huawei Health. Two file types:

- **JSON files** — daily summaries: steps, Body Battery, sleep stages, resting HR
- **FIT files** — Garmin's proprietary binary format; stress + heart rate at one reading per minute, all day

### 7 Output Files

| File | Contents |
|---|---|
| `garmin_daily.csv` | Daily aggregates: steps, Body Battery, sleep, resting HR |
| `garmin_minute_stress.csv` | Minute-level stress (full study period) |
| `garmin_minute_hr.csv` | Minute-level heart rate |
| `session_biometrics.csv` | One row per session: pre/during/post window summaries |
| `session_traces_all.csv` | All sessions combined, minute-by-minute |
| `session_traces/[date].csv` | One CSV per individual session |
| PDF report | Visual summary of full participant data |

### Session Extraction

The pipeline reads the check-in CSV to know when each session happened. For each session it extracts three windows — **pre**, **during**, and **post** — and computes summary stats (mean stress, mean HR, Body Battery) per window. These summaries become the ML features later.

### Timezone Handling

FIT files store timestamps in **UTC**. Check-in times are **CET (UTC+1/+2)**. The pipeline converts before extracting windows. A one-hour error would shift every session window, extracting the wrong biometric slice for every session — silently, with plausible-looking numbers.

### Why Session Days Are Excluded from Baselines

The circadian baseline measures expected stress **per hour of day** on non-session days. Session days are excluded because music actively affects stress — including them would contaminate the hourly reference buckets. The baseline is only meaningful as a comparison if it's clean of intervention effects.

---

## 5. Feature Engineering

Raw stress values are nearly useless for ML — a reading of 45 means nothing without context. Feature engineering bakes that context in.

### The Core Problem

Stress is personal and circadian. Participant A may rest at stress=30; participant B at stress=55. On top of that, everyone fluctuates throughout the day. A model trained on raw values learns *who the participant is*, not the effect of music.

**Solution: don't model stress — model deviation from expected stress.**

### The Circadian Baseline

For each participant on non-session days only: *"What is this person's typical stress at each hour of the day?"* This produces a mean ± std per hour (0–23). Hours with fewer than 5 observations are flagged NaN.

### Baseline Deviation — The Key Feature

```
baseline_deviation = pre_stress_mean − expected_stress_at_hour
```

- `pre_stress_mean` — actual measured stress in the pre-session window
- `expected_stress_at_hour` — their circadian baseline at that same hour

Raw unit difference (not z-score). Positive = participant was more stressed than usual going into the session. This feature (`baseline_deviation_entry`) is the strongest biometric predictor in the ML models — it already controls for individual differences and time of day.

### Two Baselines, Two Purposes

| Baseline | Built from | Used for |
|---|---|---|
| **All-days baseline** | All non-session days | ML features — more data, more stable per-session estimates |
| **Pre-study baseline** | Days before the first session only | Long-term trend analysis — frozen "before photo", not contaminated by cumulative session effects |

### The Feature Matrix

28-column table, one row per session. Key columns:

| Column | What it is |
|---|---|
| `baseline_deviation_entry` | Stress deviation going into the session |
| `hr_baseline_deviation` | HR deviation going into the session |
| `pre/during/post_stress_mean` | Window averages |
| `mood_before_score` | Self-reported mood before session |
| `hour_of_day`, `day_of_week` | Time context |
| `playlist_type` | Calm / Neutral / Energy (dummy encoded) |

Target variables: `mood_delta` (mood_after − mood_before) and `stress_delta` (post − pre stress mean).

### Recovery Curve Fitting (τ)

Stress recovery is modelled as exponential decay. **τ (tau)** = minutes to 63% recovery. The pipeline fits this to the post-session trace and compares it to the expected recovery for that activity state:

```
recovery_advantage = τ_expected − τ_actual
```

**Positive advantage = the participant recovered faster than their baseline — music helped.** This is the primary measure for RQ1.

---

## 6. ML Models

### 6a — Circadian ML (Mood & Stress Delta Prediction)

**Question:** given everything we know about a participant going into a session, can we predict how much their mood or stress will change?

- **Input:** 28-column feature matrix (one row per session)
- **Targets:** `mood_delta`, `stress_delta`
- **N:** 82 sessions, 4 participants with biometric data

#### The Three Models

| Model | What it is | Risk at N=82 |
|---|---|---|
| **Ridge** | Linear model with L2 regularization — shrinks coefficients toward zero, penalizes over-reliance on any one feature | Low |
| Random Forest | Ensemble of decision trees, captures non-linear patterns | High (overfitting) |
| Gradient Boosting | Trees built sequentially, each correcting previous errors | Very high (overfitting) |

#### LOO-CV vs LOPO-CV

| Strategy | What it does | What it measures |
|---|---|---|
| **LOO-CV** | Train on 81 sessions, test on 1 | Can the model generalize to a new *session* from a known participant? |
| **LOPO-CV** | Train on 3 participants, test on 1 entirely | Can the model generalize to a participant it has *never seen*? |

LOPO-CV is the harder, more honest test for real-world deployment.

#### Results (mood_delta, LOO-CV)

| Model | MAE | R² | Notes |
|---|---|---|---|
| Dummy baseline | 1.817 | −0.025 | Floor |
| **Ridge** | **1.578** | **0.318** | Best |
| Random Forest | 1.666 | 0.233 | — |
| Gradient Boosting | 1.778 | 0.108 | Train R²=0.820 → overfit gap of 0.712 |

**Ridge wins.** For stress_delta: LOO R²=0.870, but LOPO MAE jumps from 2.866 → 5.868. Stress patterns are participant-specific and don't generalize to new people.

#### The Regression-to-Mean Confound

Top predictor in every model: `mood_before_score`. This is a problem — someone reporting a very low mood is statistically likely to report higher mood afterwards regardless of any intervention, because extreme scores naturally drift toward the mean. The model may be exploiting this artifact. R²=0.318 for mood_delta is real, but must be interpreted cautiously.

#### RQ3 Sidebar

Classifying *which playlist type* from biometrics alone: **42–44% accuracy on a 3-class problem** (33% = random chance). Biometrics alone do not distinguish which playlist was playing.

---

### 6b — Music Classification

**Question:** can we automatically sort a participant's Spotify library into Calm / Energy / Other without any manual labels?

#### Approach 1: Threshold Model (Notebook 3)

Rule-based — no training data, no labels. Three steps:

**1. Per-participant MinMax normalization (0–1)**
Each library is normalized independently. Without this, the same threshold means different things for different people — a tempo of 0.65 on a normalized scale represents a very different absolute BPM for someone whose library spans 60–180 BPM vs. 60–90 BPM.

**2. Arousal score per song**
```
arousal = 0.35×energy + 0.30×tempo + 0.20×loudness − 0.10×acousticness + 0.05×danceability
```

**3. Thresholds**

| Class | Condition |
|---|---|
| Calm | arousal < 0.35 AND valence ≥ 0.25 |
| Energy | arousal > 0.65 |
| Other | everything else |

Pre-filters remove live recordings (liveness > 0.80) and podcasts (speechiness > 0.66).

**Class distribution:** Calm 5–20%, Energy 8–28%, Other 60–80%. Most of any library lands in "Other."

**The validation gap:** Only 22% of songs from ISO-generated calm playlists are classified "calm" by this model. This doesn't mean either system is broken — the ISO generator uses BPM range + energy threshold, while the arousal score uses a weighted 6-feature formula. A song can pass the ISO BPM filter (50–95) but still have high loudness or energy that pushes its arousal score above 0.35. Two systems, overlapping but not identical criteria.

#### Approach 2: GMM Unsupervised (Notebook 4)

**Question:** does the audio feature space have natural clusters, or is it a continuum?

- 2,777 unique songs pooled across 7 participants
- StandardScaler normalization
- BIC sweep k=2 to k=10

**BIC** (Bayesian Information Criterion) — rewards fit, penalizes complexity. Lower = better.

| k | Result |
|---|---|
| k=9 | BIC-optimal — best statistical fit |
| k=9 | Silhouette ≈ −0.001 — clusters completely overlap, assignments arbitrary |
| k=3 | Silhouette = 0.101 — marginal separation, but interpretable |

**Conclusion:** the audio feature space is a **continuum, not discrete clusters**. No natural "calm" and "energy" islands exist. k=3 is kept as a practical compromise — not statistically optimal, but interpretable and aligned with the three-playlist structure of the study.

---

### 6c — Bayesian Recommender

**Question:** given a participant's current biometric state, which playlist type is most likely to produce the best mood outcome?

#### Why Bayesian?

With N=82 sessions and 4 participants, a standard classifier gives point predictions with no sense of uncertainty. Bayesian modelling gives a **full probability distribution** over possible outcomes — when data is thin, uncertainty shows up explicitly as wide intervals rather than false confidence.

#### Hierarchical Structure

```
Global level:   What works on average across all participants?
                        ↓  shrinkage
Participant level:  What works for THIS person?
```

**Shrinkage:** each participant's effect is pulled toward the global mean. If `peer` has only 5 Energy sessions, the model doesn't fully trust those 5 — it borrows strength from the other participants to stabilize the estimate. This prevents overconfident conclusions from small per-person samples.

#### The Model

For each participant × playlist combination:
```
mood_delta ~ Normal(μ, σ²)
```
Each participant's μ is drawn from a global distribution estimated across all participants. Fitted using **PyMC with NUTS sampler** (MCMC) — ~30 seconds to run.

#### Credible Intervals

Results are reported as **89% credible intervals**: "there's an 89% probability the true effect lies in this range." When the interval **includes zero**, the model cannot rule out a negative effect — the app flags uncertainty rather than making a confident recommendation.

Example: CI = [−0.5, +3.2] for Energy → crosses zero → do not confidently recommend, even though the mean looks positive.

The app loads pre-sampled posteriors (`--reuse-trace`) and updates recommendations live as you adjust activity state and stress level on the slider.

---

### 6d — LSTM Arc Predictor (Experimental)

#### What It Tries to Do

All other models use **summary statistics** as input — mean stress per window, baseline deviation. These collapse a 30-minute session into a handful of numbers.

The LSTM feeds in the **full minute-by-minute stress and HR trace during the session** and learns the shape of the arc directly:

```
[45, 44, 43, 41, 40, 38, 37, ...]  →  predict mood_delta
```

Instead of aggregates, it sees the actual trajectory.

#### Architecture

**1-layer LSTM, 32 hidden units** — deliberately small. An LSTM is a recurrent neural network that maintains a hidden state through the sequence, "remembering" what happened earlier in the trace when making its prediction.

#### The Data Problem

- 82 sessions, 4 participants → far too small for a neural network
- **5× data augmentation** applied: each trace is slightly perturbed to generate 5 synthetic variants → ~410 training examples
- This does not fully solve the problem — augmented data adds no new independent observations, just noise-perturbed copies. The model can still overfit to the original 82 sessions' patterns.

#### Gradient Saliency

The model produces a **saliency map** showing which minutes of the session trace most influenced the prediction — useful for understanding *when* during a session the mood outcome becomes predictable from biometrics.

#### Why It's Experimental

1. N=82 is too small for a neural network even with augmentation
2. Requires `torch` — a heavy dependency used nowhere else
3. At current scale, Ridge with interpretable features is more trustworthy

Included as a proof-of-concept, not a result to report. Would become viable if the study scaled to hundreds of participants.

---

## 7. The Shiny App

**MoodTune** — styled like Spotify Wrapped. Run with `uv run shiny run ui/app.py`.

### Page 1: Home

Live demo. Picks a random participant moment, runs the fitted **Ridge model** (`models/circadian_ml/models.pkl`) in real time, and displays:
- Current biometric state (stress, HR, Body Battery)
- Recommended playlist with track details (BPM, energy, acousticness, duration)
- **ISO sparkline** — BPM trend confirming the gradient direction is correct

Songs can be reshuffled within tempo tiers while preserving the ISO arc.

### Page 2: Jouw Profiel — 5 sub-panels

| Sub-panel | What it shows | Source |
|---|---|---|
| **Resultaten** | Mood improvement per playlist type, 95% CI. CI crossing zero → flagged as uncertain (data can't confirm the effect is positive) | `session_biometrics.csv` + check-in CSV |
| **Sessie-replay** | Full biometric arc for one session: stress trajectory, HR, mood before/after emoji, vs. circadian baseline | `session_traces/[date].csv` |
| **Circadiaans ritme** | Hourly stress curve ±1σ, session dots colored by playlist type | `circadian_baselines/` |
| **Herstelanalyse** | τ advantage scatter (RQ1): recovery minutes gained per session, reliable vs. unreliable fits, filterable by playlist | `session_effects.csv` |
| **Jouw Muziek** | Paginated song browser, arousal score 1–5 dots, class label, audio features, filterable by Calm/Energy/Other | `classified_songs.csv` |

### Page 3: Aanbevelingen

Interactive Bayesian recommender. Select activity state + stress slider → posterior probabilities per playlist update live. 89% credible intervals shown. CI including zero → flagged uncertain. Draws from pre-sampled PyMC trace.

**Sparse data behaviour:** if a participant has few sessions of one playlist type, the Bayesian model applies shrinkage — pulling that estimate toward the global mean across participants. The Recovery Analysis page, by contrast, shows raw session dots — few sessions means few dots, possibly marked unreliable.

### Page 4: Achtergrond

Three static sub-panels: research methodology (Science), ML model cards with LOO/LOPO metrics (Model & Data), and the full pipeline diagram (Pipeline).

---

## 8. Research Questions

### RQ1: Can ISO-ordered personalized playlists measurably reduce stress objectively?

**Answered by:** `session_effect.py` + Recovery Analysis page (τ advantage)

**Verdict:** Mixed. A recovery advantage is measurable in some sessions, but results are inconsistent. Sessions where the exponential decay fit didn't converge cleanly are marked unreliable — reliable fits are a subset of all sessions. The effect exists in the data but isn't strong enough for a universal claim.

---

### RQ2: Does reduced physiological stress correlate with improved self-reported mood?

**Answered by:** Circadian ML (Notebook 1) + Results page

**Verdict:** Correlation exists, but confounded. `mood_before_score` dominates as the top predictor — people who feel bad tend to report feeling better regardless of intervention (regression-to-mean). Biometric predictors add signal, but their independent contribution is modest. N=82 is too small to cleanly separate music effect from natural mood fluctuation.

---

### RQ3: Can we classify playlist type from biometric signals alone?

**Answered by:** Notebook 1, classification subsection

**Verdict:** No. **42–44% accuracy on a 3-class problem** — barely above 33% random chance. Stress and HR respond too similarly across playlist types to be distinguishable. This is itself a finding: physiological response to music is highly individual and context-dependent, not stereotyped by playlist type.

---

### RQ4: Can we predict mood outcome from physiological state + playlist type?

**Answered by:** Ridge regression, Notebook 1

**Verdict:** Partial. LOO R²=0.318 — better than chance, explains ~a third of variance. But LOPO MAE doubles — patterns are participant-specific and don't generalize to new people. The live app recommendation is reliable only for participants with established session history.

---

### RQ5: Can unsupervised music clustering optimize playlist generation?

**Answered by:** Notebooks 3 (threshold model) + 4 (GMM)

**Verdict:** No clear improvement over manual tuning. The GMM shows the audio feature space is a **continuum** — BIC-optimal k=9 has silhouette ≈ 0 (complete overlap). k=3 is interpretable but not meaningfully better than the manual BPM/energy thresholds already in `generate.py`. The threshold arousal score model works in practice, but only 22% of ISO-generated calm songs get labelled "calm" by it.

---

### Summary Table

| RQ | Verdict |
|---|---|
| RQ1 | Effect exists, inconsistent evidence |
| RQ2 | Correlation exists, confounded by regression-to-mean |
| RQ3 | No — biometrics can't classify playlist type |
| RQ4 | Partial — works within participants, not across |
| RQ5 | No clear improvement over manual tuning |

### Why Modest Results Are Expected — and Why the Project Is Still Valuable

Modest results at N=82, 4 participants, 10 weeks are statistically expected — sparse data produces more noise than signal, and reaching strong significance requires far larger samples.

The scientific contribution is the **methodology**: the circadian baseline deviation approach, ISO-ordered personalized playlists, and hierarchical Bayesian recommender form a complete, replicable framework. The pipeline runs end-to-end. At 40 participants instead of 4, several of these answers would likely be substantially stronger. That scalability is the real result.

---

## Presentation Notes

Three questions most likely to come from a jury — and how to handle them.

**1. "Why is mood_before_score your top predictor? Isn't that just regression to the mean?"**
Yes — and that's the honest answer. Someone who reports a very low mood before a session is statistically likely to report higher mood afterwards regardless of any intervention, because extreme scores drift toward the mean over time. The model exploits this. It doesn't invalidate the result, but it means R²=0.318 for mood_delta should be interpreted cautiously — the biometric features add signal on top of this effect, but their independent contribution is harder to isolate. An ablation test (removing `mood_before_score`) confirms the model degrades without it.

**2. "Does this generalize? Could you use this on a new participant?"**
Not yet. The LOPO-CV result is the honest answer: when you train on 3 participants and predict on the 4th, stress_delta MAE doubles (2.866 → 5.868). The model has learned participant-specific patterns, not universal ones. The Bayesian recommender handles this more gracefully — shrinkage toward the global mean gives a reasonable starting point for a new participant — but it's still an approximation until enough sessions accumulate. Generalization requires more participants, not more sessions per person.

**3. "The GMM found k=9 optimal but you're using k=3 — isn't that just ignoring the data?"**
No — this is a case where statistical optimality and practical interpretability diverge. BIC at k=9 is lower, but silhouette ≈ 0 means the 9 clusters completely overlap in feature space. Assignments at k=9 are essentially arbitrary. k=3 has marginal but non-zero separation (silhouette=0.101) and maps onto the three-playlist structure of the study. More importantly, the GMM result itself is the finding: the audio feature space is a continuum, not a set of discrete islands. That's a genuine empirical result, not a null result.
