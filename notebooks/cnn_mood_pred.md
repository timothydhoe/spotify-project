# CNN Pre-Session Mood Prediction — Analysis & Roadmap

**Notebook:** `cnn_pre_session_trajectory.ipynb`
**Date:** 2026-04-07

---

## What the notebook does

Trains a 1D CNN to predict, from biometrics alone, whether a music session will improve mood — using the 60 minutes of physiological data *before* the session starts (stress, body battery, heart rate).

**Data:** 2 participants (`bosbes`, `kokosnoot`), 13 usable sessions, nearly balanced classes (6 improved / 7 not improved).
**Evaluation:** Leave-One-Session-Out (LOSO) cross-validation.

---

## Current results

**Full model (all 3 channels):**

| Metric | Score |
|--------|-------|
| ROC-AUC | 0.76 |
| Precision | 0.57 |
| Recall | 0.67 |
| Balanced Accuracy | 0.62 |

AUC 0.76 is in the "moderate signal worth investigating" range. With N=13, the confidence interval is roughly ±0.15.

**Ablation — which channel matters?**

| Channel(s) | AUC |
|------------|-----|
| All 3 | 0.59* |
| Stress only | 0.59 |
| HR only | 0.43 (worse than random) |

*The ablation run returned a lower AUC than the main LOSO run — a known instability with N≈13. See improvement suggestions below.

**Grad-CAM:** The model weights the most recent minutes (near t=0) most heavily. Physiological state *just before* the session matters more than what happened 30–50 minutes earlier.

---

## How Garmin calculates stress

Garmin stress (0–100) is derived from **Heart Rate Variability (HRV)**. Low HRV → high stress. The autonomic nervous system suppresses beat-to-beat variation under stress, which Garmin detects from R-R intervals in the optical HR sensor. The ~4-minute sampling interval is how often the device has enough R-R data to compute a stable HRV estimate. Proprietary implementation, but HRV-derived stress is well-validated scientifically.

---

## HR-only devices

Since Garmin's stress *is* derived from HR/HRV, the best path for HR-only devices is to reconstruct a stress proxy:

1. **HRV proxy** — if the wearable exports inter-beat intervals (IBIs), compute RMSSD or SDNN over a rolling window. This is essentially what Garmin does internally.
2. **HR-derived features** — if only per-minute HR is available: rolling variance, rate of change (slope), deviation from personal resting HR. Coarser but meaningful.
3. **RMSSD from HR** — some wearables export enough resolution for this even without raw IBI data.

The ablation showed raw per-minute HR was worse than chance as a standalone channel. That's expected — HR magnitude is noisy and person-dependent. HRV/variance is the signal that maps to arousal.

---

## Path to generalisation

The notebook already injects participant ID as a one-hot input (good architectural choice). The realistic progression:

**Short term (2–4 participants):** Keep person-specific learning. The model asks "for this person, does this pre-session profile predict improvement?" — which is valid and arguably the most clinically useful thing anyway.

**Medium term (5–10 participants):** The one-hot participant embedding becomes meaningful. Run LOSO at the *participant* level (hold out all sessions from one person), not just session level — this is the real generalisation test.

**Longer term:**
- **Mixed-effects / hierarchical model** — treat participant as a random effect. Less exciting than CNN but more honest at small N, and gives proper uncertainty estimates.
- **Meta-learning / fine-tuning** — train a shared model across participants, then fine-tune per-person with a few sessions. Requires ~5+ participants to be worth it.

The honest ceiling: with only 2–3 participants you cannot separate "what generalises" from "what's person-specific." More participants is the only real fix.

---

## Suggested improvements

### Correctness / robustness

- **Repeat LOSO with multiple seeds, report mean ± std.** The single-run AUC of 0.76 vs ablation AUC of 0.59 reveals stochastic variance — a single number is misleading at N=13.
- **Add a dummy classifier baseline** (predict majority class = "not improved"). You need to know what 0.62 balanced accuracy is actually beating.

### Interpretability

- **Add a logistic regression baseline on handcrafted features** — mean stress, stress slope, mean HR in final 10 minutes. If LR matches CNN, the temporal convolution is adding no value. That's an important negative result worth knowing.
- **Label Grad-CAM clearly as illustrative.** It's trained in-sample on all data — useful for exploration, not evidence of generalisation.

### Towards the bigger picture

- **Add participant-level LOSO** (hold out all sessions from one person) as a second evaluation alongside session-level LOSO. Even with N=2 this establishes the framework you'll need as more participants are added.
- **Track playlist type per session in results.** The model might be implicitly learning to predict playlist type (calm sessions may produce different pre-session profiles than energy sessions), which would confound mood improvement. Check for this.

---

## The bigger picture

The end goal is a model that, given a participant's physiological state right now, recommends: *"given your current state, a calm/energy/neutral playlist is most likely to improve your mood."*

This CNN is a building block — it validates that the pre-session window contains predictive signal. Once confirmed with more data, it feeds into a full recommender:

```
biometric state → playlist type recommendation → predicted mood delta
```

This is the "combined mood model" described in the research questions — the most novel contribution of Project R.E.M.
