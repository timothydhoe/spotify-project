# Application Idea: MoodTune

> *Spotify knows what you like. MoodTune knows what you need.*

---

## The Business Case

### The Problem

Every major streaming platform optimizes for the same metric: **engagement** — time spent listening. But engagement and wellbeing are not the same thing. An anxious person putting on high-energy music stays anxious. A demotivated person playing sad songs stays demotivated. The recommendation engine isn't working against you; it's just not working *for* you.

Meanwhile, 600 million people wear a smartwatch that continuously measures their physiological state — stress, heart rate, body battery — and does nothing with that signal beyond displaying it in a health app.

**The gap:** Nobody connects your biometric state to what you should be listening to.

### The Research Answers This

Project R.E.M. (Regulation of Emotion through Music) ran a controlled study:

- **6 participants**, **47 listening sessions**, **3 playlist types** (Calm / Neutral / Energy)
- Every session: smartwatch biometrics before, during, and after. Self-reported mood before and after.
- Playlists built from each participant's own Spotify library, ordered using the **ISO principle** — the same gradual emotional transition technique used in music therapy.

**Key findings:**
- Physiologically regulated stress recovery is measurable (exponential decay, τ = time constant)
- Participants listening to matched playlists recovered **up to 79 minutes faster** than their circadian baseline
- The Bayesian model can recommend the right playlist type with **83–100% posterior confidence** per participant
- The strongest predictive signal: **how stressed you are relative to your normal at that hour** — not absolute stress level, but the deviation from your personal circadian rhythm

### The Product Opportunity

| | Spotify Today | MoodTune |
|---|---|---|
| Recommends based on | Listening history, similar users | Your biometric state right now |
| Optimizes for | Time spent listening | Mood outcome, stress recovery |
| Learns from | Skips and replays | Before/after mood + physiological response |
| Personalization | Genre/artist taste | Individual circadian stress profile |

**Target markets:**
- B2C: Spotify / Apple Music premium add-on ("Wellness Mode")
- B2B: Workplace wellbeing platforms (Headspace for Business, Microsoft Viva)
- Clinical: Music therapy support tools (validated ISO protocol at scale)

---

## The Application: MoodTune Dashboard

A Shiny for Python web app styled in Spotify's visual language — dark background, green accents, bold data callouts. Functions as both a research results dashboard and a live product demo.

**Stack:** Shiny for Python + Plotly + existing project data (no new analysis needed for demo)

**Why Shiny over Streamlit:** Shiny uses a reactive graph — only the outputs that depend on a changed input re-execute. Streamlit reruns the entire script on every interaction. For a data-heavy dashboard with multiple CSVs and plots, Shiny is significantly faster and more responsive.

---

### Page 1 — Home: "The Problem"

**Purpose:** Set the stage. Establish the gap between what streaming does and what it could do.

**Layout:**
- Full-width headline: *"Your playlist shouldn't just sound good. It should work."*
- 3-panel animated flow: `Stress spike detected` → `Playlist prescribed` → `Stress recovered`
- Study stats bar: 6 participants · 47 sessions · 3 playlist types · 8 weeks

**Data source:** Static/hardcoded narrative content

---

### Page 2 — The Science: "ISO Principle"

**Purpose:** Establish scientific credibility without losing the audience.

**Layout:**
- Side-by-side BPM trajectory charts: Calm (descending), Neutral (flat), Energy (ascending)
- 4-phase labels for Calm playlist (Ontmoeting → De-escalatie → Regulatie → Landing)
- One-sentence explainer per phase
- Pull quote: *"Rather than jumping to a target emotion, ISO gradually transitions the listener — the way a thermostat ramps, not switches."*
- Mini-infographic: Spotify audio features used (tempo, energy, valence, acousticness)

**Data source:** `generate.py` ISO phase parameters (hardcoded thresholds), example playlist CSVs

---

### Page 3 — Your Circadian Signature

**Purpose:** Show that stress is not random — it follows a personal daily rhythm, and the app knows yours.

**Layout:**
- Participant selector (dropdown: bosbes / kiwi / kokosnoot / limoen / peer / watermeloen)
- Line chart: average stress by hour of day (0–23), with ±1 std band
- Overlay: session times marked as dots, colored by playlist type
- Stat callouts:
  - "Your least stressful hour: **9am** (avg stress: 32)"
  - "Your highest-stress window: **5–7pm** (avg stress: 61)"
  - "Circadian range: **29 points** across the day"
- Footnote: *"Baselines computed from non-session days only — your typical day, not your study days."*

**Data source:** `data/analysis/[codename]/circadian_baselines/hourly_baseline.csv`

**Why this matters for the pitch:** This chart is the core insight. It's what makes MoodTune different from any existing wellness app — it doesn't treat a stress score of 55 the same way at 9am as at 6pm. It knows whether 55 is above or below normal *for you, right now*.

---

### Page 4 — Recommendation Engine (Interactive Demo)

**Purpose:** The centerpiece. Live demo of the recommendation system.

**Layout:**
- Header: *"What should I listen to right now?"*
- Input panel (left column):
  - Participant selector
  - Stress level slider (0–100)
  - Time of day selector (hour)
  - Activity state selector (Sleep / Rest / Light / Medium / Heavy)
  - Body battery slider (0–100)
- Output panel (right column):
  - Big recommendation badge: `ENERGY PLAYLIST` (green) / `CALM PLAYLIST` (blue) / `NEUTRAL PLAYLIST` (grey)
  - Confidence bar: "87% posterior probability this is the optimal choice"
  - Why explanation: *"Your stress (68) is 14 points above your 3pm baseline. Energy playlists have historically improved your composite mood by +12.3 points in this state."*
  - Horizontal bar chart: posterior mean ± 89% CI for all three playlist types

**Implementation note:** The Bayesian recommender outputs are pre-computed in `recommendations.json`. For the demo, map slider inputs to the nearest matching session in the feature matrix and look up the posterior prediction. No live inference needed.

**Data source:**
- `data/analysis/bayesian_recommender/recommendations.json` (playlist posteriors per participant)
- `data/analysis/circadian_baselines/feature_matrix.csv` (to compute baseline deviation from slider inputs)

---

### Page 5 — Session Replay

**Purpose:** Show real data from a real session. Make the research tangible.

**Layout:**
- Participant + session selector (dropdown: "bosbes — 2026-02-04, Energy")
- Biometric arc chart (main panel):
  - Three-phase time series: PRE (−60 min) → DURING → POST (+60 min)
  - Two lines: stress (left axis, orange) + heart rate (right axis, red)
  - Vertical dashed lines marking session start/end
  - Shaded regions for each phase
- Stat row below chart:
  - Mood before: emotion badge + intensity score (e.g., "Gestresseerd 7/10")
  - Mood after: emotion badge + intensity score (e.g., "Neutraal 6/10")
  - Mood delta: +/− with arrow and color
  - Recovery advantage: "Recovered **+76 min faster** than your baseline"
- Optional: exponential recovery curve overlay (from `recovery_analysis.ipynb`)

**Data source:**
- `data/wearables/[codename]/processed/session_traces/` (minute-level per session)
- `data/wearables/[codename]/processed/session_biometrics.csv` (mood scores, deltas)

---

### Page 6 — Your Results ("Wrapped")

**Purpose:** The payoff. Per-participant summary styled like Spotify Wrapped — big numbers, dramatic reveals.

**Layout:**
- Participant selector
- Full-width summary card, dark background, grid of stat blocks:

```
┌─────────────────────────────────────────────────────────┐
│  bosbes · Project R.E.M. · 8 weeks                      │
├────────────┬────────────┬────────────┬──────────────────┤
│ SESSIONS   │ MOOD LIFT  │ RECOVERY   │ BEST PLAYLIST    │
│    19      │   +4.2 pts │  +76 min   │  ENERGY          │
│            │  avg/session│  avg saved │  83% confidence  │
├────────────┴────────────┴────────────┴──────────────────┤
│ YOUR CALMEST HOUR        │  YOUR PEAK STRESS WINDOW     │
│        9am               │         6pm                  │
├──────────────────────────┴──────────────────────────────┤
│ COMPLETION RATE: 89%    ·   AVG SESSION: 31 minutes     │
└─────────────────────────────────────────────────────────┘
```

- Mood flow sankey or before/after distribution (emotion labels + valence coloring)
- Tagline: *"Your music is your medicine."*

**Data source:**
- `data/analysis/circadian_baselines/feature_matrix.csv`
- `data/wearables/[codename]/processed/session_biometrics.csv`

---

### Page 7 — The Model: "How We Know"

**Purpose:** Satisfy the technical audience. Show the science behind the recommendation.

**Layout:**
- Section 1 — Bayesian Recommender:
  - Posterior distribution plots per participant (embed existing PNGs from `data/analysis/bayesian_recommender/`)
  - Shrinkage diagram: participants with few sessions pulled toward group mean
  - Quote: *"Partial pooling means even participants with only 3 sessions benefit from group-level evidence."*
  
- Section 2 — Circadian ML:
  - SHAP beeswarm (embed from `data/analysis/circadian_baselines/`)
  - Model comparison table: Dummy MAE vs Ridge vs RF vs GBR
  - Highlight: `baseline_deviation_entry` as top feature — "how stressed are you vs. your normal right now?"
  - LOO cross-validation note: "Validated on held-out sessions — no data leakage"

- Section 3 — Significance Tests:
  - Summary table: which participants showed significant stress reduction (p < 0.05)
  - From `data/analysis/circadian_baselines/significance_tests.csv`

---

## Technical Build Plan

### What to add

```bash
uv add shiny plotly
```

### File structure

Shiny for Python uses a module system — each page is a `module` with its own `ui` and `server` functions, wired together in a single `app.py` via `ui.page_navbar`.

```
spotify-project/
├── app.py                          # Shiny entrypoint: ui.page_navbar + App()
├── modules/
│   ├── home.py                     # Page 1 — static narrative
│   ├── science.py                  # Page 2 — ISO principle charts
│   ├── circadian.py                # Page 3 — hourly baseline, participant selector
│   ├── recommendation.py           # Page 4 — interactive recommendation engine
│   ├── session_replay.py           # Page 5 — biometric arc chart
│   ├── results.py                  # Page 6 — "Wrapped" summary card
│   └── model.py                    # Page 7 — SHAP, posteriors, significance
├── utils/
│   ├── data_loader.py              # Shared data loading (cached at module level)
│   └── styles.css                  # Spotify dark theme overrides
└── www/
    └── styles.css                  # Static assets served by Shiny
```

### Reactivity pattern

Shiny's reactive graph ensures efficiency — only re-renders what changed:

```python
# modules/circadian.py
@module.server
def circadian_server(input, output, session, data):

    @reactive.calc
    def baseline():
        # Re-runs only when input.participant() changes
        return data[input.participant()]

    @render_plotly
    def baseline_chart():
        # Re-renders only when baseline() changes
        df = baseline()
        return make_hourly_chart(df)
```

Contrast with Streamlit: the same interaction would re-execute the entire page script, reloading all DataFrames and rebuilding all plots from scratch.

### app.py skeleton

```python
from shiny import App, ui
from modules import home, science, circadian, recommendation, session_replay, results, model

app_ui = ui.page_navbar(
    ui.nav_panel("Home",            home.ui("home")),
    ui.nav_panel("The Science",     science.ui("science")),
    ui.nav_panel("Circadian",       circadian.ui("circadian")),
    ui.nav_panel("Recommendation",  recommendation.ui("rec")),
    ui.nav_panel("Session Replay",  session_replay.ui("replay")),
    ui.nav_panel("Your Results",    results.ui("results")),
    ui.nav_panel("The Model",       model.ui("model")),
    title="MoodTune",
    bg="#121212",
    inverse=True,
)

def server(input, output, session):
    home.server("home")
    science.server("science")
    circadian.server("circadian", data=circadian_data)
    recommendation.server("rec", features=feature_matrix, recs=recommendations)
    session_replay.server("replay", traces=session_traces, biometrics=session_biometrics)
    results.server("results", features=feature_matrix, biometrics=session_biometrics)
    model.server("model")

app = App(app_ui, server)
```

### Theme (custom CSS in `www/styles.css`)

```css
:root {
  --spotify-green: #1DB954;
  --bg-primary: #121212;
  --bg-secondary: #282828;
  --text-primary: #FFFFFF;
}

body { background-color: var(--bg-primary); color: var(--text-primary); }
.navbar { background-color: #000000 !important; }
.nav-link.active { color: var(--spotify-green) !important; }
.value-box { background-color: var(--bg-secondary); border-left: 4px solid var(--spotify-green); }
```

Load in `app_ui` with `ui.include_css("www/styles.css")`.

### Existing assets to reuse (no re-computation needed)

| Asset | Location | Used in |
|-------|----------|---------|
| Feature matrix | `data/analysis/circadian_baselines/feature_matrix.csv` | Pages 4, 6, 7 |
| Bayesian recommendations | `data/analysis/bayesian_recommender/recommendations.json` | Page 4 |
| Session biometrics | `data/wearables/[codename]/processed/session_biometrics.csv` | Pages 5, 6 |
| Session traces | `data/wearables/[codename]/processed/session_traces/*.csv` | Page 5 |
| Hourly baselines | `data/analysis/[codename]/circadian_baselines/` | Page 3 |
| Recovery PNGs | `data/analysis/*.png` | Pages 5, 7 |
| Posterior PNGs | `data/analysis/[codename]/bayesian_recommender/` | Page 7 |
| SHAP PNGs | `data/analysis/circadian_baselines/` | Page 7 |
| Significance tests CSV | `data/analysis/circadian_baselines/significance_tests.csv` | Page 7 |

### Run command

```bash
uv run shiny run app.py --reload
```

---

## Presentation Narrative (9 minutes)

### Act 1 — The Problem (1 min)
> *"Spotify knows what you like. But does it know what you need?"*

Open on the Home page. 600M users, 600M wearables, and the two have never spoken. You have a stress score on your wrist right now — and your playlist doesn't know about it.

### Act 2 — The Research (2 min)
> *"We ran the study. Here's what we found."*

Navigate to The Science. Explain ISO: music therapy's core principle, now data-driven. Navigate to Circadian Signature — show two participants' hourly stress curves side by side. "Everyone's stress rhythm is different. This is yours."

### Act 3 — The Demo (3 min)
> *"Let me show you how it works."*

Navigate to Recommendation Engine. Live input: it's 5pm, stress is 72, you just finished a moderate workout. Output: *"Calm playlist. 91% confidence. Your stress is 18 points above your 5pm baseline — you need de-escalation, not activation."*

Navigate to Session Replay. Pull up a real session — show the stress arc dropping during a Calm session, mood going from "Gestresseerd 8/10" to "Rustig 5/10". Recovery advantage: 76 minutes.

### Act 4 — The Potential (2 min)
> *"This is 6 people. Imagine 6 million."*

Navigate to Your Results — the "Wrapped" card for one participant. These numbers came from 8 weeks of real data. Now imagine Spotify running this model continuously, for every user, on every listening session.

The signal generalizes: the Bayesian model uses partial pooling — new users immediately benefit from group-level evidence. Cold start isn't a problem; the group's priors are your priors.

### Act 5 — What's Next (1 min)
> *"The research question is answered. The engineering question is next."*

- Real-time wearable streaming (Garmin Connect API / Apple HealthKit)
- Spotify API integration (generate and queue the playlist directly)
- Feedback loop: session outcomes improve the model per-user over time
- Expand to mood subtypes — not just intensity, but valence-aware prescription

---

## Why This Lands as a Business Case

1. **Proof of concept exists** — real biometric data, significance-tested results, Bayesian model with credible intervals. Not a prototype. Not a simulation.

2. **The novel signal** — circadian baseline deviation is genuinely new. Garmin doesn't use it. Spotify doesn't use it. It's the finding that makes the whole thing defensible.

3. **Personalization is structural** — the model doesn't just average across participants; it learns *your* response to *your* music. That's a moat.

4. **The ISO principle is validated clinical practice** — this isn't speculative. The recommendation engine has a 50-year-old theoretical foundation, now operationalized in code.

5. **Distribution is solved** — works on top of any music platform. Not dependent on creating content; dependent on understanding the listener.
