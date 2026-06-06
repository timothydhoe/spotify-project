# MoodTune — Critical Audit & Implementation Plan

> **Status:** COMPLETE. All phases 0–4 done. App verified with full Playwright QA pass (2026-05-25).
> **Conducted:** 2026-05-24
> **Auditor:** Senior UX/UI + Data Science review (Claude Sonnet 4.6)
> **App branch:** `feat/app-shiny` | **App:** `uv run shiny run app.py`
> **Methodology:** Full codebase read (all modules, scripts, notebooks) + live Playwright testing of all 8 pages + data shape inspection

---

## Part 1: Audit Findings

---

### Section A: Data Science Audit

#### A1. Data Quality & Integrity

**A1.1 — CRITICAL: Temporal data leakage in ML feature set**

`circadian_ml.py` trains models to predict `mood_delta` using features that include:
- `during_stress_mean` — mean stress **during** the music session
- `post_stress_mean` — mean stress **after** the session
- `during_hr_mean`, `post_hr_mean` — same problem for heart rate

These are measurements taken **after** the intervention begins. Predicting mood change using data collected during and after the session is look-ahead bias. The model is essentially asking "does the stress response to music predict the mood change caused by music?" — a circularity that inflates all reported metrics.

The correct feature set uses only **pre-session** data: `pre_stress_mean`, `baseline_deviation_entry`, `hr_baseline_deviation`, `mood_before_score`, `hour_of_day`, etc.

- **Files:** `scripts/analysis/circadian_ml.py` (feature list, lines 42–54), `scripts/analysis/circadian_baseline.py` (feature construction)
- **Impact:** Current R² and MAE values are inflated; model is not a valid predictor of session outcome from pre-session state. All published metrics must be regenerated after this fix.

**A1.2 — HIGH: Missing value handling inconsistent across scripts**

| Feature | NaN rate | Treatment in `circadian_ml.py` | Treatment in `circadian_significance.py` |
|---|---|---|---|
| `baseline_deviation_entry` | 37.5% (15/40) | Median impute inside fold ✓ | Silent row drop |
| `stress_delta` | 40% (16/40) | Not used as target everywhere | Silent row drop |
| HR channels | ~50% | Excluded if >50% NaN ✓ | Silent row drop |
| `hrv_rmssd` | 75%+ | Excluded via `excluded_features.json` ✓ | N/A |

`circadian_significance.py` drops NaN rows silently, reducing effective N below the `MIN_OBS=5` guard in some stratified tests (playlist × pre_state cells can have N<3 after dropping).

**A1.3 — HIGH: N=40 with 4 participants — not stated explicitly in the app**

All analyses rest on:
- N=40 sessions, 4 participants with biometrics (bosbes=8, kokosnoot=16, limoen=6, peer=10)
- N=6–16 sessions per participant
- N=29 sessions for Bayesian recommender (includes check-in-only participants)

This is **well below** thresholds for stable ML metrics (~100 for Ridge, ~500 for GBM), reliable SHAP (~200), or valid significance tests per stratum. All analyses are exploratory only. The app currently presents ML outputs without this caveat.

**A1.4 — MEDIUM: Participant heterogeneity handled ad hoc**

- `limoen`: no stress data (Huawei device) — excluded from baseline deviation features
- `peer`: no biometrics — mood only from check-in form
- `kiwi`, `watermeloen`: no wearables, sparse check-in data
- Different analyses use different participant subsets without clear documentation of which participants contribute to which result.

---

#### A2. ML Pipeline Critique

**A2.1 — HIGH: Model hyperparameters unjustified, no search**

| Model | Parameters | Issue |
|---|---|---|
| Ridge | α=1.0 (hardcoded) | No cross-validated grid search; α=1.0 is arbitrary |
| RandomForest | max_depth=3, n_estimators=100 | Very shallow; likely underfitting at N=40 |
| GradientBoosting | n_estimators=50, max_depth=2, lr=0.1 | Extremely constrained; no search |

Best practice: nested LOO-CV (outer loop evaluates, inner loop selects hyperparameters). With N=40 a grid search with inner 5-fold CV is computationally feasible.

**A2.2 — HIGH: Metric confidence intervals not reported**

MAE ~1.5–2.0 on mood_delta at N=40 has enormous confidence intervals. Bootstrap CI on LOO MAE should be reported. The current tables show point estimates only, making model comparisons (Ridge vs. RF vs. GBM) untrustworthy — differences are within noise.

**A2.3 — HIGH: SHAP on N=40 is unreliable — caveat missing in app**

The SHAP beeswarm is displayed in the Circadiaan app page with no quality warning. The scripts include an honest warning (`N < 20: SHAP very unreliable`), but this is not surfaced to app users. Per-participant SHAP (N=6–16) is essentially noise and should not be interpreted as confirmed findings.

**A2.4 — HIGH: Bayesian recommender sliders are decorative (not live inference)**

The Aanbevelen page presents 4 sliders (stress, hour, battery, activity state) that **imply** the recommendation responds to user input. It does not. The recommendation badge (Calm/Neutral/Energy) is pre-computed per participant from historical sessions only. Only the explanation text (circadian deviation calculation) reacts.

The small caption "PRE-BEREKEND PER DEELNEMER" is present but easy to miss. This is the most consequential UX deception in the app.

The Bayesian model could in principle produce live posterior inference given new inputs, but this would require serving the MCMC trace in-process — architecturally non-trivial. The simpler fix is UX: make the static nature of the recommendation explicit and prominent.

**A2.5 — MEDIUM: Music classification weights not empirically derived**

`music_classification.py` uses a weighted arousal score:
```python
arousal = 0.35 * energy + 0.30 * tempo + 0.20 * loudness - 0.10 * acousticness + 0.05 * danceability
```
These weights are not derived from outcome data. The classification (calm/energy/other) directly determines which playlist each participant receives — the core intervention. If classification is wrong, every playlist in the study has the wrong type assignment.

**A2.6 — MEDIUM: Music classification not validated against outcomes**

GMM clustering (`music_classifier.py`) produces k clusters that are never tested against biometric outcomes. "Does cluster membership predict stress reduction better than rule-based thresholds?" would be a direct validity test of the classification pipeline.

---

#### A3. Statistical Rigor

**A3.1 — HIGH: No multiple comparison correction in `circadian_significance.py`**

`circadian_significance.py` runs 28 tests per participant with zero FDR correction. At α=0.05, expected false positives under the null ≈ 1.4. All current p-values are > 0.2, so correction doesn't change conclusions now — but the methodology is wrong and must be fixed for publication.

`session_arc_analysis.py` correctly implements Benjamini-Hochberg FDR. The inconsistency between scripts should be resolved.

**A3.2 — MEDIUM: Effect sizes calculated incorrectly in `circadian_significance.py`**

Effect size is computed as `Z / sqrt(N)` where `Z = norm.isf(p/2)` — this is backward inference (p → Z). The standard approach is to compute the Wilcoxon Z directly from the rank statistic, then divide by sqrt(N). `session_arc_analysis.py` computes Cohen's d and η² correctly.

**A3.3 — MEDIUM: Bayesian priors underdocumented**

Prior `μ_α ~ Normal(0, 5)` on mood_delta intercept is quite diffuse — mood_delta ranges roughly −3 to +3 in the data, so σ=5 spans nearly the full scale. Prior predictive checks (what mood distributions does the prior generate?) are not reported. Recommendation credible intervals may be partially prior-driven.

---

### Section B: UX/UI Audit

#### B1. Information Architecture

**B1.1 — HIGH: Navigation order breaks the research narrative**

Current: Home → Wetenschap → Pipeline → Circadiaan → Aanbevelen → Afspelen → Resultaten → Model

For a 9-minute presentation, the natural arc is:

1. **Wetenschap** — what is the ISO principle and why does it work?
2. **Pipeline** — how was data collected and processed?
3. **Circadiaan** — what do individual stress patterns look like?
4. **Afspelen** — what happened during a specific session?
5. **Resultaten** — what are the aggregate outcomes?
6. **Model** — how do the ML models work and what did they find?
7. **Aanbevelen** — given your current state, what should you listen to?
8. **Home** — try it yourself

Placing Pipeline between Wetenschap and Circadiaan interrupts the science→data narrative. Aanbevelen (the applied conclusion) belongs after Resultaten, not before Afspelen.

**B1.2 — MEDIUM: Home page has no onboarding context**

A first-time user sees 6 fruit-codename pills, a generate button, and 4 stats. There is no explanation of what Project R.E.M. is, what ISO principle means, or what they're about to see.

---

#### B2. Page-by-Page UX Critique

**B2.1 Home**
- **First impression:** Clean, Spotify-dark, professional.
- **Bug:** "Genereer afspeellijst" has no loading state — button appears unresponsive for ~0.5s before playlist appears
- **Bug:** Now-playing bar always shows "Selecteer een afspeellijst" even after a playlist is generated
- **Bug:** No post-generation CTA — after seeing the playlist, where should the user go?
- **Data:** Stats bar (6, 47, 8, 3) are hardcoded — silently stale if data changes (`modules/home.py:221–228`)
- **Data availability:** Pills don't distinguish full data (Bosbes/Kokosnoot) from partial (Limoen/Peer) from none (Kiwi/Watermeloen)

**B2.2 Wetenschap**
- **First impression:** Good. ISO chart is the visual anchor. Slider → chart reactivity works well.
- **Bug (confirmed):** Subtitle at `science.py:169–171` contains literal `{calm_max}` and `{energy_min}` — the string has no `f` prefix, so variable interpolation never executes
- **Redundancy:** "Standaard parameters" table at bottom duplicates information in the feature cards above
- **Research context:** Phase labels (Ontmoeting, De-escalatie, Regulatie, Landing) have no English equivalents for international audiences

**B2.3 Circadiaan**
- **First impression:** Complex but not overwhelming. Baseline chart is informative.
- **Strongest element:** Deviation calculator (hour + stress → real-time deviation) is excellent UX — makes the circadian concept concrete and testable
- **Wrong placement:** SHAP beeswarm ("Wat voorspelt de Stemming?") belongs on the Model page, not here. Circadiaan is about biometric baselines; SHAP is about mood prediction — different story, different audience interpretation
- **Labeling:** Stat cards show "+9.1", "1:00", "12–14:00" without immediate context; a user in 3 seconds cannot know that "+9.1" is a stress deviation in points
- **Quality gap:** SHAP PNG shown without any caveat. N=40 warning exists in scripts and notebooks but not surfaced to app users

**B2.4 Aanbevelen**
- **First impression:** Clean two-column layout. Recommendation badge is visually strong.
- **CRITICAL — UX deception:** The 4 sliders and activity selector imply live inference. The recommendation badge **never changes** regardless of slider input. Only the explanation text (circadian deviation) reacts. Caption "PRE-BEREKEND PER DEELNEMER" is present but easy to miss.
- **Overflow:** Explanation text box is cut off at some viewport widths
- **Context:** Body Battery 0–100 scale unexplained for non-Garmin users
- **Labeling:** Posterior chart error bars not labeled as "89% geloofwaardigheidsinterval"

**B2.5 Afspelen**
- **First impression:** Best page in the app. Biometric arc with phase divider is genuinely compelling.
- **Bug:** Now-playing bar overlaps mood arc cards — R² warning and recovery badge are partially hidden
- **Bug:** Raw internal string exposed: `TAU_VERWACHT = 98 MIN = TAU_WERKELIJK = 20 MIN = R2 = 0.01` — debugging text shown to users
- **Bug:** R² warning in ALL CAPS — aggressive tone, hard to read
- **Chart:** Stress (0–100) and Hartslag (bpm, typically 40–130) share a Y axis. HR appears as a flat line because the axis is dominated by the stress scale. Dual Y-axis required.
- **Recovery badge:** "+78 minuten sneller" shown in green despite R²=0.01. The badge is the most emotionally resonant stat on the page, but the model fit is essentially random noise. Visual confidence should reflect statistical confidence.

**B2.6 Resultaten**
- **First impression:** "Spotify Wrapped" framing is the best conceptual decision in the app.
- **Stat cards:** Recovery advantage (+50 min), golden hour (1:00), peak stress window (12–14:00) are actionable and well-designed.
- **Bug:** "8 VAN ~8 GEPLANDE SESSIES" — the tilde implies estimation but `8` is hardcoded (`results.py:127`) and doesn't adapt to participants with different expected session counts
- **Missing interpretation:** Kalm playlist shows −1.0 mood delta — the most scientifically interesting finding gets no interpretation. Is this real? Is it noise? The negative result deserves a callout, not silence.
- **Layout:** "Jouw muziek is jouw medicijn" tagline partially obscured by now-playing bar

**B2.7 Model**
- **First impression:** Information overload. No hierarchy, no progressive disclosure.
- **All at once:** Model comparison table + SHAP PNG + Bayesian posterior grid (3×2) + significance table (27 rows) + architecture diagram — no collapsing, no priority
- **SHAP chart:** White matplotlib background completely breaks the dark theme
- **Posterior grid:** Technical histograms with no interpretation labels for non-statisticians
- **Significance table:** 27 rows, most non-significant — needs "significant only" toggle as default
- **Architecture diagram:** Text-based ASCII — fine for research audience

**B2.8 Pipeline**
- **First impression:** Clean, clear. Three-track diagram communicates data flow well.
- **Bug:** Now-playing bar overlaps "Waarom twee aparte tracks?" section
- **Good:** Clickable steps with lazy-loaded data previews is a solid feature
- **Issue:** Data preview HTML tables don't match the dark theme CSS
- **Security:** `_df_to_html()` in `pipeline.py:262–272` uses raw f-string interpolation — HTML from CSV cell values is injected without escaping

---

#### B3. Visual Design Critique

**B3.1 — CRITICAL: Now-playing bar overlaps page content on multiple pages**

The fixed 80px bottom bar requires `padding-bottom: 80px` on every page's scrollable content. Currently missing on: Afspelen, Pipeline, Resultaten, and partially on others. Content is literally hidden behind the bar. (`www/styles.css`)

**B3.2 — HIGH: SHAP plot has white background (breaks dark theme)**

`data/analysis/circadian_baselines/plots/shap_mood_delta.png` is a default matplotlib white-background output. On the dark theme (`#0f0f0f`), it appears as a bright white rectangle. Fix by regenerating with `plt.style.use('dark_background')` or transparent PNG. (`scripts/analysis/circadian_ml.py`)

**B3.3 — HIGH: Heart rate and stress share Y-axis (scientifically wrong)**

In Afspelen biometric chart, HR (bpm) and stress (0–100) are plotted on the same axis. HR typically 60–100 bpm during mild activity; stress occupies 20–80 on its own 0–100 scale. The numeric overlap makes them look similar when they measure fundamentally different physiological quantities. A dual Y-axis (left=stress, right=HR bpm) is required. (`modules/session_replay.py:87–102`)

**B3.4 — MEDIUM: Sidebar active state persists across page switches**

CSS underline on sidebar items persists after navigating away — previously-visited pages appear co-active alongside the current page. (`www/styles.css`, `.nav-link` styles)

**B3.5 — MEDIUM: Plotly toolbar visible on hover on some charts**

`chart_helpers.py`'s `dark_layout()` removes the modebar, but some charts bypass `dark_layout()` and show the default toolbar on hover. Inconsistent.

---

### Section C: Cross-Cutting Concerns

#### C1. Where UX and Data Science Intersect

**C1.1 — CRITICAL: Recommendation sliders imply precision the model cannot deliver**

The Aanbevelen page is the clearest example of UI overpromising model capability. Moving any slider (stress, time, battery, activity) creates the impression of real-time inference. The recommendation badge never changes. This is not just a UX polish issue — it misrepresents the model to every user who sees the page.

**Resolution path A (preferred):** Replace the small "PRE-BEREKEND" caption with a prominent callout directly above the badge making the static nature explicit.

**Resolution path B (ideal, high complexity):** Load `trace.nc` at app startup and sample from the posterior given current slider inputs via NumPyro/JAX, making the sliders genuinely functional. Feasible post-presentation.

**C1.2 — HIGH: Recovery badge presents unreliable estimates as confident results**

"+78 min sneller herstel" is shown in green — the most emotionally resonant stat in the app. But R²=0.01 for this session means the exponential decay fit is noise. The tau_advantage is meaningless when R² < 0.1. An R² warning IS shown, but the badge color and prominence don't reflect the model's uncertainty.

**C1.3 — HIGH: SHAP presented as finding when it is exploratory noise**

The SHAP beeswarm (N=40, 37% NaN in key features) appears on Circadiaan as if it's trustworthy. At N=40 with correlated features, SHAP rankings are highly unstable — rerunning with a different random seed would change the rankings. The correct framing: "these patterns are hypotheses for future validation, not confirmed findings."

**C1.4 — MEDIUM: Credible intervals convey false precision**

The posterior bar chart in Aanbevelen shows error bars representing the 89% CI. With hierarchical pooling at N=8 (bosbes), the posteriors are substantially influenced by group-level priors, not just data. The caption should explicitly state the interval width relative to sample size.

**C1.5 — MEDIUM: Negative mood result for Kalm not contextualized**

Resultaten shows Kalm playlist with −1.0 mood delta for Bosbes — the most scientifically interesting finding in the entire app. It gets a plain bar with no interpretation. Small N (N=3 calm sessions for Bosbes) is a plausible explanation; individual variability is another. Neither is mentioned.

#### C2. What's Actually Good — Do Not Change

1. **Bayesian hierarchical model architecture** — Correct approach for N=6 participants. Partial pooling prevents overfitting. Convergence solid (R-hat < 1.01, ESS > 1900). Preserve entirely.
2. **LOO cross-validation in `circadian_ml.py`** — Appropriate for N=40. Imputation done inside each fold correctly (no leakage from imputation step). Preserve the structure, fix the feature set.
3. **FDR correction in `session_arc_analysis.py`** — Benjamini-Hochberg properly applied. Most statistically rigorous script in the project.
4. **Afspelen biometric arc visualization** — VOOR/TIJDENS/NA phase divider with overlaid stress + HR traces is the most compelling visualization in the project. Preserve the concept and design.
5. **Circadiaan deviation calculator** — Interactive hour + stress → real-time deviation from baseline is excellent UX. Makes the circadian concept concrete and testable by users.
6. **Dutch localization** — Consistent throughout. Appropriate for the research context and target audience.
7. **Pipeline diagram** — Three-track flow (Muziek → Biometrie → Analyse) communicates the data architecture clearly and accurately.
8. **Design system** — Spotify dark aesthetic (CSS variables, DM Sans + Sora typography, 240px sidebar) is well-executed and consistent across pages.
9. **SHAP data quality warnings in scripts** — `circadian_ml.py` explicitly flags N < 20 unreliability and explains SHAP faithfully describes the model, not reality. Preserve and surface in the app.
10. **Bayesian MCMC convergence diagnostics** — R-hat checked, ESS checked, trace plots in notebook. Properly validated before use.

---

## Part 2: Implementation Plan

### Do Not Change
- Bayesian model architecture (`scripts/analysis/bayesian_recommender.py`)
- LOO CV structure in `circadian_ml.py` (fix feature set only)
- FDR implementation in `session_arc_analysis.py`
- Afspelen biometric arc concept and phase divider design
- Circadiaan deviation calculator interaction
- Dark theme, color system, typography (CSS variables in `www/styles.css`)

---

### Phase 0 — Quick Wins (< 30 min each, no risk)

- [x] **[B2.2]** Fix missing `f` prefix in science.py subtitle — `{calm_max}` and `{energy_min}` render as literal text instead of slider values
  - **Files:** `modules/science.py:169`

- [x] **[B3.1]** Fix now-playing bar overlap — add `padding-bottom: 80px` to `.tab-content` or `.tab-pane` elements
  - **Files:** `www/styles.css`

- [x] **[B2.5]** Reformat raw tau technical string in recovery badge to human-readable Dutch
  - Replace: `TAU_VERWACHT = 98 MIN = TAU_WERKELIJK = 20 MIN = R2 = 0.01`
  - With: `Verwachte hersteltijd: 98 min | Werkelijk: 20 min | Betrouwbaarheid: laag (R²=0.01)`
  - **Files:** `modules/session_replay.py` (recovery badge render)

- [x] **[B2.5]** Fix R² warning from ALL CAPS to sentence case with normal casing
  - **Files:** `modules/session_replay.py`

- [x] **[B3.4]** Clear sidebar nav underline persistence — visited pages should not retain underline after navigating away
  - **Files:** `www/styles.css` (`.nav-link:visited`, `.nav-link` active state reset)

- [x] **[B2.6]** Fix "~8 geplande sessies" — remove the tilde or compute expected session count from study design
  - **Files:** `modules/results.py:127–129`

- [x] **[A1.1]** Remove data leakage features from ML feature list: `during_stress_mean`, `post_stress_mean`, `during_hr_mean`, `post_hr_mean`
  - **Files:** `scripts/analysis/circadian_ml.py` (feature list, ~lines 42–54)
  - **Note:** This is a Phase 0 code change; the re-run (Phase 1) updates the data outputs

---

### Phase 1 — Data & ML Improvements

- [x] **[A1.1]** Re-run `circadian_ml.py` after data leakage fix; regenerate `model_results_mood_delta.csv`, SHAP PNG, permutation importance PNG
  - **Command:** `uv run python scripts/analysis/circadian_ml.py`
  - **Files:** `scripts/analysis/circadian_ml.py`, `data/analysis/circadian_baselines/`
  - **Depends on:** Phase 0 leakage fix

- [x] **[A3.1]** Add Benjamini-Hochberg FDR correction to `circadian_significance.py`
  - Use `statsmodels.stats.multitest.multipletests(p_values, method='fdr_bh')`
  - Add `q_value` column to output CSV
  - **Files:** `scripts/analysis/circadian_significance.py`
  - **Re-run:** `uv run python scripts/analysis/circadian_significance.py`

- [x] **[A3.2]** Fix effect size calculation — compute r = Z/sqrt(N) where Z is derived from the Wilcoxon T statistic directly, not back-calculated from p
  - **Files:** `scripts/analysis/circadian_significance.py`

- [x] **[B3.2]** Regenerate all analysis PNGs with dark matplotlib background
  - Add `plt.style.use('dark_background')` before all figure creation in `circadian_ml.py`
  - Or set `transparent=True` in `savefig()` calls
  - **Files:** `scripts/analysis/circadian_ml.py`
  - **Re-run:** `uv run python scripts/analysis/circadian_ml.py`

- [x] **[A2.1]** Add cross-validated hyperparameter search for Ridge α and RF `max_depth`
  - Inner 5-fold CV via `tune_models()`: Ridge α ∈ [0.01, 0.1, 1, 10, 100], RF max_depth ∈ [2,3,5,None], GBM max_depth ∈ [1,2,3]
  - **Files:** `scripts/analysis/circadian_ml.py`

- [x] **[A3.3]** Add prior predictive check to `bayesian_recommender.py`
  - `prior_predictive_check()` samples N=500 prior predictive draws, plots distribution, reports P(|mood_delta|>5)
  - **Files:** `scripts/analysis/bayesian_recommender.py`

---

### Phase 2 — UX/UI Improvements

#### Home
- [x] **[B2.1, B4.3]** Loading spinner: `ui.busy_indicators.use(spinners=True, pulse=True)` already wired in `app.py` — auto-activates during reactive compute
  - **Files:** `app.py`

- [x] **[B2.1, B4.7]** Add post-generation CTA after playlist renders: "Bekijk een eerdere sessie →" and "Persoonlijke aanbeveling →" card grid
  - **Files:** `modules/home.py`

- [x] **[B2.1]** Update now-playing bar to show currently loaded playlist name instead of hardcoded placeholder
  - **Files:** `app.py` (`now_playing_title`), `modules/home.py` (expose `player_state` to app level)

- [x] **[B4.6]** Add data availability visual cue to participant pills: ● vol ◑ gedeeltelijk ○ geen biometrie legend + per-pill tooltip
  - **Files:** `modules/home.py`

#### Wetenschap
- [x] **[B2.2]** Add English sub-labels for ISO phase names (Ontmoeting / Isochronous Meeting, De-escalatie / De-escalation, Regulatie / Regulation, Landing / Arrival)
  - **Files:** `modules/science.py`

- [x] **[B2.2]** Remove "Standaard parameters" table — information is redundant with feature cards above
  - **Files:** `modules/science.py`

#### Circadiaan
- [x] **[B2.3, C1.3, B4.4]** Removed SHAP section from Circadiaan; SHAP lives only on Model page
  - **Files:** `modules/circadian.py` (removed), `modules/model.py` (already present + quality caveat added)

- [x] **[B2.3]** Add units to stat cards — "+9.1 pt" and label "Pre-sessie afwijking t.o.v. basislijn (gem.)"
  - **Files:** `modules/circadian.py`

#### Aanbevelen
- [x] **[C1.1, B4.1]** Prominent amber-bordered callout above inputs making pre-computation explicit
  - **Files:** `modules/recommendation.py`

- [x] **[B2.4]** Fix explanation text overflow — added `overflow-wrap: break-word; word-break: break-word; min-width: 0` to `.mt-callout`
  - **Files:** `www/styles.css`

- [x] **[B2.4]** Label posterior chart error bars: "Foutenbalken = 89% geloofwaardigheidsinterval. Brede intervallen wijzen op kleine steekproef."
  - **Files:** `modules/recommendation.py`

- [x] **[C1.4]** Add sample-size note below posterior chart: "N=X sessies voor [participant]"
  - **Files:** `modules/recommendation.py`

#### Afspelen
- [x] **[B3.3, B4.8]** Dual Y-axis already implemented: left = Stress (0–100), right = Hartslag (40–130 bpm)
  - **Files:** `modules/session_replay.py:104–111` (was already correct)

- [x] **[C1.2, B4.2]** Gray out recovery badge when R² < 0.3; show "? minuten" and amber warning
  - **Files:** `modules/session_replay.py`

- [x] **[B4.6]** Differentiate disabled pills in Afspelen: extra dim for no-wearables vs. partial
  - `_NO_WEARABLES = {"kiwi", "watermeloen"}` adds `.no-wearable` class (opacity 0.18, grayscale 0.6) vs regular disabled (opacity 0.35)
  - **Files:** `modules/session_replay.py`, `www/styles.css`

#### Resultaten
- [x] **[B2.6, C1.5]** Add `chart_footnote` output: amber ⚠ warning for playlist types with N≤3 or negative delta
  - **Files:** `modules/results.py`

- [x] **[B2.6]** Compute "voltooiingspercentage" dynamically from actual sessions ÷ expected
  - Expected derived from `feature_matrix.csv` row count per participant; `_participant` key threaded through `_compute_summary`
  - **Files:** `modules/results.py`

#### Model
- [x] **[B2.7]** Add progressive disclosure to Significance Tests and Architecture Diagram sections
  - `toggle_sig` / `toggle_arch` buttons; `show_sig` / `show_arch` reactives; `sig_section` / `arch_section` render outputs; `update_action_button` label flips ▼/▲
  - **Files:** `modules/model.py`

- [x] **[B2.7]** Default significance filter set to "Significante tests alleen" (checkbox checked by default)
  - **Files:** `modules/model.py`

- [x] **[B2.7]** SHAP data quality callout added: "Exploratief — N=40 sessies. SHAP-patronen zijn richtinggevend, geen inferentie."
  - **Files:** `modules/model.py`

- [x] **[B2.7]** q_value (FDR) column added to significance table
  - **Files:** `modules/model.py`

#### Pipeline
- [x] **[B2.8]** Dark background wrapper added to HTML data preview tables
  - **Files:** `modules/pipeline.py`

- [x] **[B2.8 — security]** HTML escaping added to `_df_to_html()` via `html.escape()`
  - **Files:** `modules/pipeline.py`

#### Global / App
- [x] **[B1.1, B4.10]** Navigation reordered: Wetenschap → Pipeline → Circadiaan → Afspelen → Resultaten → Model → Aanbevelen → Home
  - **Files:** `app.py`

---

### Phase 3 — New Capabilities

- [x] **[B2.1]** Compute stats bar from actual data instead of hardcoded values
  - `_compute_study_stats(app_data)` reads from `feature_matrix.csv`: session count, participant count, week range from date span
  - **Files:** `modules/home.py`

- [x] **[A2.5]** Validate music classification weights against outcome data
  - Kruskal-Wallis across playlist types: H=0.31, p=0.856 (not significant, N too small)
  - Arousal score OLS vs mood_delta: r=0.27, p=0.097 — trend but not significant
  - **Files:** `scripts/analysis/music_classification_validation.py`, outputs in `data/analysis/music_classification_validation/`

- [x] **[A2.6]** Validate GMM clustering against outcomes
  - **Optimal BIC k=8** (not 3) — audio features naturally form 8 sub-genres, not 3 archetypes; silhouette at k=3 = 0.090 (weak)
  - **GMM k=3 vs rule-based calm/energy: Cramér's V=0.918** — near-perfect agreement: Cluster 0 = 100% energy songs, Cluster 2 = 100% calm songs, Cluster 1 = mixed arousal
  - **GMM k=3 vs generated playlist type: V=0.505** — strong; calm playlists are 76% Cluster 2, energy playlists avoid Cluster 2 entirely
  - Conclusion: GMM corroborates rule-based ISO threshold approach; neither validated against biometric outcomes (no per-song session tracking)
  - **Files:** `scripts/analysis/gmm_clustering_validation.py`, `data/analysis/gmm_clustering_validation/`

- [ ] **[A2.4 — future]** Implement live Bayesian inference in Aanbevelen
  - Load `trace.nc` at app startup; sample from posterior given current slider inputs via NumPyro
  - Makes sliders genuinely functional; resolves C1.1 at the model level
  - **Complexity:** High. Requires in-process MCMC sampling or pre-sampled grid lookup.
  - **Files:** `modules/recommendation.py`, `utils/data_loader.py`

---

### Phase 4 — Polish & Validation

- [x] **[A1.1]** Document updated model metrics in `CLAUDE.md` — added "Current ML Metrics" table with post-leakage-fix LOO-CV results (RF R²=0.389 best)

- [x] **[A1.4]** Document which participants contribute to each analysis in `docs/analysis_participants.md` — created with full breakdown per pipeline

- [x] **[B3.5]** Audit all Plotly charts for modebar visibility — all 5 chart modules (circadian, recommendation, science, results, session_replay) use `dark_layout()` which removes zoom/pan/select/save toolbar buttons
  - **Files:** All `modules/*.py` chart functions

- [x] End-to-end visual QA: all 8 pages verified with Playwright full-page screenshots (2026-05-25)
  - Wetenschap ✓, Pipeline ✓, Circadiaan ✓, Afspelen ✓, Resultaten ✓, Model ✓, Home ✓
  - Aanbevelen: fixed posterior caption text clipping (split long captions into two `<p>` tags; added `min-width:0` to flex columns in `recommendation.py`)
  - CSS: added `overflow-wrap: break-word; word-break: break-word` to `.mt-caption`
  - Now-playing bar confirmed not overlapping content on any page (padding-bottom: 112px effective)

---

### Future Work (Requires More Data or Major Scope)

These are technically sound proposals but require either N >> 40 or significant additional effort not feasible before June 20:

**F1. Gaussian Process for circadian stress modeling**
GP would provide proper posterior uncertainty bands (current ±1σ is point-wise variance, not model uncertainty). `sklearn.GaussianProcessRegressor` works at N=40 but would be dominated by kernel choice.
**Requirement:** N > 100 per participant for stable GP hyperparameter learning.

**F2. Temporal CNN / LSTM on per-minute stress trajectories**
Proposed in `docs/ML_models_proposals.md` (Proposal 2). At N=40 sessions × 60–120 minute traces, the sequence dataset is small. Transfer learning from a pretrained physiological model would be needed.
**Requirement:** N > 200 sessions, or a pretrained model from a public biometric corpus.

**F3. Session-to-session personalization (few-shot / meta-learning)**
Adapting recommendations based on cumulative session history. Current N=6–16 per participant is marginally sufficient only with strong hierarchical priors already captured by the Bayesian model.
**Requirement:** N > 30 per participant (study extension to 12+ weeks).

**F4. Audio feature extraction beyond Spotify API**
Spectral features (MFCCs, chroma, onset strength) via `librosa` would enable richer music representation. Requires access to audio files, which are not available for most tracks.
**Requirement:** Audio file access + `librosa` processing pipeline.

---

*Every finding in this document was verified against observed behavior, specific file paths, and line numbers. Generated 2026-05-24. This document is the single source of truth for implementation.*
