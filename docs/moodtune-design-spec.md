# MoodTune — Design Specification

**Project R.E.M.** (Regulation of Emotion through Music)  
Target implementation: Shiny for Python  
Presentation deadline: June 20, 2026

---

## Design System Tokens

### Colors

| Name | Hex | Use |
|------|-----|-----|
| `bg-primary` | `#121212` | Page backgrounds |
| `bg-card` | `#282828` | Cards, panels, sections |
| `bg-elevated` | `#383838` | Hover states, tooltips, inputs |
| `accent-green` | `#1DB954` | CTAs, active nav, highlights |
| `text-primary` | `#FFFFFF` | Headlines, labels |
| `text-secondary` | `#B3B3B3` | Subtext, captions, metadata |
| `calm-blue` | `#5B8FD6` | Calm playlist accent |
| `neutral-grey` | `#9B9B9B` | Neutral playlist accent |
| `energy-orange` | `#E8834A` | Energy playlist accent |
| `stress-red` | `#E84A4A` | High-stress data points |
| `border` | `#3A3A3A` | Dividers, card borders |

### Typography — Font: Inter (Google Fonts)

| Style | Weight | Size | Line Height |
|-------|--------|------|-------------|
| Display | Bold | 52px | 60px |
| H1 | Semi Bold | 32px | 40px |
| H2 | Semi Bold | 24px | 32px |
| H3 | Medium | 18px | 26px |
| Body | Regular | 16px | 24px |
| Caption | Regular | 13px | 18px |
| Mono | Regular | 13px | 20px — JetBrains Mono or Roboto Mono |

### Spacing
8px grid. Common values: 8, 16, 24, 32, 48, 64, 96px

### Border Radius
- Cards: 12px
- Buttons: 24px (pill)
- Badges: 20px
- Inputs: 8px

### Canvas
1440px wide per page, height to content.

---

## Shared Component: NavBar

Sticky, full-width, `bg-card` (#282828) background, 64px height, 1px bottom border in `border` color.

- **Left:** "MoodTune" logotype — `accent-green` dot + white text, H3 weight
- **Right:** 7 nav items as text links, `text-secondary` default, `text-primary` on hover, `accent-green` with green pill background when active

Nav items (left to right): `Home · Science · Circadian · Recommend · Replay · Results · Model`

---

## Page 1 — Home

**Purpose:** Emotional hook + study overview. First page the audience sees.

### Layout (top to bottom)

**NavBar** — "Home" active

**Hero Section** — Full-width, 560px tall, `bg-primary`
- Centered vertically and horizontally
- Eyebrow label: Caption, `accent-green`, uppercase, letter-spaced — `PROJECT R.E.M.`
- Headline: Display, white — `"What if music could regulate your stress?"`
- Sub-headline: Body, `text-secondary`, max-width 600px — `"We tested whether ISO-ordered, personalized Spotify playlists can measurably reduce physiological stress — and tracked every heartbeat to find out."`
- CTA button: pill shape, `accent-green` fill, white text — `"See the Science →"` — 48px height, 24px horizontal padding

**Flow Section** — `bg-card`, 200px tall, full-width
- Title: Caption, `text-secondary`, centered above — `"HOW IT WORKS"`
- 3 panels side by side, equal width, separated by `→` arrows in `accent-green`:
  - Panel 1: Icon (stress wave / heart), H3 white — `"Stress Detected"`, Caption grey — `"Smartwatch measures your HRV & stress level"`
  - Panel 2: Icon (music note), H3 white — `"ISO Playlist Generated"`, Caption grey — `"Songs ordered to gradually guide your arousal toward calm"`
  - Panel 3: Icon (downward trend), H3 white — `"Recovery Measured"`, Caption grey — `"Biometrics tracked 60 min post-session"`

**Stats Bar** — `bg-elevated`, 96px tall, full-width
- 4 stats centered in a row, each: large number in `accent-green` (H1), label in Caption grey below
- `6` Participants · `47` Sessions · `8` Weeks · `3` Playlist Types

**Footer** — `bg-primary`, 64px, `text-secondary` Caption centered
- `"All analysis is open-source. Data anonymized with fruit codenames."`

---

## Page 2 — The Science

**Purpose:** Explain the ISO principle. Credibility before the demo.

### Layout

**NavBar** — "Science" active

**Hero** — 200px, centered
- H1 white: `"The Science Behind MoodTune"`
- Body `text-secondary`: `"ISO principle from music therapy — don't jump to the target state, gradually transition toward it"`

**ISO Explainer** — 2-column layout, 80px padding each side, 64px gap

Left column (prose):
- H2 white: `"The ISO Principle"`
- Body grey: Explain that music therapy uses gradual BPM/energy matching to lead the listener's arousal from current state toward target state
- Callout box (`bg-card`, 12px radius, `accent-green` left border 3px wide): `"Self-chosen music is significantly more effective at emotion regulation than unfamiliar selections"`

Right column (chart):
- Three stacked BPM trajectory line charts:
  - **Calm** (`calm-blue`): BPM line descends from ~95 to ~55 over 30 minutes
  - **Neutral** (`neutral-grey`): BPM line stays flat at ~105
  - **Energy** (`energy-orange`): BPM line ascends from ~120 to ~165
- Label each with playlist name + BPM range

**Audio Features Grid** — `bg-card`, full-width, 80px padding
- H2 white centered: `"6 Spotify Audio Features Used"`
- 3×2 grid of feature cards (`bg-elevated`, 12px radius, 24px padding):
  - `Tempo (BPM)` — `"Primary filter — defines playlist category boundary"`
  - `Energy (0–1)` — `"Perceptual intensity — how energetic it feels"`
  - `Valence (0–1)` — `"Musical positivity — minimum threshold on energy playlist"`
  - `Danceability (0–1)` — `"Beat regularity — used to reinforce energy playlist"`
  - `Acousticness (0–1)` — `"Acoustic vs electronic — tunable for calm"`
  - `Loudness (dB)` — `"Volume dynamics — min/max per playlist type"`

**Parameter Table** — `bg-card`, 80px padding
- H2 white: `"Default Parameters"`
- Table with 3 rows, columns: Playlist · Tempo Range · Energy Range · ISO Order
  - Calm: 50–95 BPM · < 0.9 · Descending BPM
  - Neutral: 95–115 BPM · 0.2–0.8 · Stable
  - Energy: 120–180 BPM · > 0.7 · Ascending BPM
- Color-coded row headers (blue / grey / orange)

---

## Page 3 — Circadian Signature

**Purpose:** Show each participant's personal stress rhythm — the key novel insight.

### Layout

**NavBar** — "Circadian" active

**Header** — 160px, centered
- H1 white: `"Your Circadian Signature"`
- Body grey: `"How does your stress level compare to your own baseline at each hour of the day?"`

**Participant Selector** — row of 6 pill tabs, centered, 48px padding top/bottom
- Pills: `bosbes · kiwi · kokosnoot · limoen · peer · watermeloen`
- Default: `bg-elevated`, white text, 8px radius
- Active: `accent-green` background, white text
- Show "bosbes" as active by default

**Main Chart Area** — `bg-card`, 12px radius, 80px horizontal padding, 48px vertical padding
- Label top-left: H3 white — `"Hourly Stress Baseline — bosbes"`
- Caption grey below label: `"Non-session days only · ±1σ band"`
- Area chart (800px wide × 320px tall):
  - X-axis: 0–23 hours, labeled every 3 hours
  - Y-axis: Stress 0–100
  - Shaded band (`accent-green` at 15% opacity) between ±1σ lines
  - Mean line in `accent-green`, 2px stroke
  - 6–8 session dots scattered: blue=calm, orange=energy, grey=neutral, 8px diameter circles
- Legend: 3 colored dots (Calm / Energy / Neutral session) + green line "Your mean stress"

**Stat Row** — 3 stat cards side by side, `bg-elevated`, 12px radius
- `"9am"` — Caption grey: `"Calmest hour"`
- `"5–7pm"` — Caption grey: `"Peak stress window"`
- `"+8.3 units"` — Caption grey: `"Pre-session deviation (mean)"`

**Explainer Block** — `bg-card`, 12px radius, 80px horizontal padding, 48px vertical
- H3 white: `"What is Circadian Baseline Deviation?"`
- Body grey: `"Rather than comparing your session stress to a fixed number, we compare it to YOUR typical stress at that same hour on non-session days. This controls for natural circadian rhythm."`
- Mono code box (`bg-elevated`, 8px radius, 16px padding):
  ```
  deviation = pre_stress_mean − expected_stress_at_hour
  ```
- Caption grey: `"A positive deviation means you were more stressed than usual for that time of day"`

---

## Page 4 — Recommendation Engine

**Purpose:** Live demo centerpiece. Left inputs → Right recommendation output.

### Layout

**NavBar** — "Recommend" active

**Header** — 120px, centered
- H1 white: `"What Should You Listen To Right Now?"`
- Body grey: `"Enter your current state and get a personalized ISO playlist recommendation"`

**Two-Column Main Panel** — `bg-card`, 12px radius, 80px padding, 48px column gap

**Left column — Inputs (~480px wide):**

H2 white: `"Your Current State"`

*Stress Level*
- Label: Body white `"Stress Level"` + Mono `"72"` value right-aligned
- Slider: `bg-elevated` track 4px height, filled portion `stress-red`, white thumb 18px
- Range labels: Caption grey `"0 — Relaxed"` left · `"100 — Highly Stressed"` right

*Time of Day*
- Label: Body white `"Time of Day"` + Mono `"17:00"` right-aligned
- Slider: filled portion `accent-green`
- Range labels: `"00:00"` left · `"23:00"` right

*Body Battery*
- Label: Body white `"Body Battery"` + Mono `"38"` right-aligned
- Slider: filled portion `calm-blue`

*Activity State*
- Label: Body white `"Activity State"`
- 5 pill buttons: `Sleep · Rest · Light · Medium · Heavy`
- Active (Medium): `accent-green` fill, white text. Others: `bg-elevated`, `text-secondary`

*Participant (Research Mode)*
- Label: Body white `"Participant"` + Caption grey `"(Research Mode)"`
- Dropdown: `bg-elevated`, 8px radius, shows `"bosbes"`, caret icon right

**Right column — Output (~640px wide):**

H2 white: `"Recommendation"`

*Recommended Badge* — centered, 200×80px, `calm-blue` background, 24px radius
- H1 white: `"CALM"`
- Body white below: `"ISO Descending"`

*Confidence Meter*
- Label: Body grey `"Posterior Confidence"`
- Large number: H1 `accent-green` `"83%"`
- Progress bar: 400px wide, 8px tall, 4px radius, `bg-elevated` track, `accent-green` fill to 83%

*Posterior Chart* — Horizontal bar chart
- 3 rows: Calm (`calm-blue`) · Neutral (`neutral-grey`) · Energy (`energy-orange`)
- Bars: Calm 83%, Neutral 11%, Energy 6%
- Each row: label left, bar in middle, CI whisker at right end
- Caption grey: `"Posterior mean ± 89% credible interval"`

*Explanation callout* — `bg-elevated`, 8px radius, `calm-blue` left border 3px
- Body grey: `"At 5pm with Medium activity and elevated stress (+12 units above your circadian baseline), Calm is recommended. Your body battery (38%) suggests fatigue — descending BPM will help your nervous system down-regulate."`

*Expandable* — Caption `accent-green` link-style: `"How was this calculated? ↓"` (collapsed by default, shows Bayesian formula in mono when expanded)

---

## Page 5 — Session Replay

**Purpose:** Show one real biometric session arc.

### Layout

**NavBar** — "Replay" active

**Session Picker** — `bg-card`, 64px tall, full-width, horizontal row
- Label: Body grey `"Select Session:"`
- Participant dropdown (`bg-elevated`): `"bosbes"`
- Date dropdown: `"2026-02-04"`
- Playlist badge (inline small pill): `calm-blue` — `"CALM"`
- Caption grey right-aligned: `"Session #4 · 31 min"`

**Timeline Header** — 3 labeled columns with vertical dividers
- **PRE** (30 min before) | **DURING SESSION** (31 min) | **POST** (60 min after)
- Column headers: Caption `text-secondary` uppercase, centered
- Background tints: PRE = `bg-elevated` 30% opacity · DURING = `calm-blue` 15% · POST = `bg-card`

**Biometric Chart** — `bg-card`, 12px radius, 80px horizontal padding (900×280px)
- X-axis: −30 to +90 min relative to session start
- Left Y-axis: Stress 0–100 · Right Y-axis: HR 50–120 bpm
- Stress line: `stress-red`, 2px · HR line: `accent-green`, 2px
- Two vertical dashed lines at t=0 and t=31, `text-secondary`
- Shaded region between them: `calm-blue` at 10% opacity
- Legend: red dot "Stress" + green dot "Heart Rate"

**Mood Arc** — row of 3 elements centered, 80px padding
- Left card (`bg-elevated`, 120×80px, 12px radius): Caption grey `"Before"` · emoji `"😟"` · Body white `"3 / 10"`
- Center: `"→"` in `accent-green` · Caption `accent-green` `"↑ +5 pts"`
- Right card: Caption grey `"After"` · emoji `"😊"` · Body white `"8 / 10"`

**Recovery Badge** — centered, `bg-card`, 480px wide, 12px radius, 32px padding
- H2 `accent-green`: `"+76 minutes"`
- Body grey: `"faster recovery than your circadian baseline for this time of day"`
- Caption grey: `"τ_actual = 28 min · τ_expected = 104 min · R² = 0.87"`

**Transparency Note** — Caption `text-secondary` centered, italic
- `"This is your actual physiological data. Nothing is simulated or interpolated."`

---

## Page 6 — Your Results

**Purpose:** Spotify Wrapped-style emotional payoff. Most visual page.

### Layout

**NavBar** — "Results" active

**Participant Selector** — same 6-pill row as Page 3, "bosbes" active, 48px padding

**Results Headline** — centered, 120px tall
- H1 white: `"bosbes's Year in Music Therapy"`
- Body grey: `"8 sessions · February to April 2026"`

**Stat Grid** — 2×3 grid of stat cards, 80px horizontal padding, 24px gaps
Each card: `bg-card`, 12px radius, 32px padding, `accent-green` 3px left border

| Card | Label | Value | Sub-label |
|------|-------|-------|-----------|
| 1 | Sessions Completed | `"8"` (H1 white) | `"out of 9 scheduled (89%)"` |
| 2 | Avg Mood Lift | `"+5.2 pts"` (H1 `accent-green`) | `"per session on average"` |
| 3 | Best Playlist | `"Calm"` (H2 white) + blue badge | `"83% posterior confidence"` |
| 4 | Recovery Advantage | `"+76 min"` (H1 `accent-green`) | `"faster than your baseline"` |
| 5 | Your Golden Hour | `"9am"` (H2 white) | `"Lowest stress, highest body battery"` |
| 6 | Peak Stress Window | `"5–7pm"` (H2 `stress-red`) | `"Avoid heavy tasks — prioritize Calm playlist"` |

**Playlist Effectiveness Chart** — `bg-card`, 12px radius, 80px padding
- H2 white: `"Mood Lift by Playlist Type"`
- 3 horizontal bars, color-coded, labels left:
  - Calm (`calm-blue`): +5.2
  - Energy (`energy-orange`): +3.8
  - Neutral (`neutral-grey`): +2.1
- Each value has a small (i) icon — reveals calculation method on hover

**Share Teaser** — Caption grey centered: `"Share feature — coming soon"`

---

## Page 7 — The Model

**Purpose:** Technical transparency. ML explainability for the literate audience.

### Layout

**NavBar** — "Model" active

**Header** — 160px, centered
- H1 white: `"Inside the Model"`
- Body grey: `"Full transparency on every model, feature, and posterior used to generate these recommendations"`

**Model Comparison Table** — `bg-card`, 80px padding, 12px radius
- H2 white: `"Predictive Models — Mood Delta"`
- Table header row (`bg-elevated`): Model · MAE · RMSE · R² · LOO-CV
- Rows: Dummy Baseline · Ridge Regression · Random Forest · Gradient Boosting
- Best row (GBR) highlighted with `accent-green` left border
- Caption grey: `"LOO-CV = Leave-One-Out cross-validation. Evaluated per participant."`

**Feature Importance** — `bg-card`, 80px padding, 12px radius
- H2 white: `"What Predicts Mood Outcome?"`
- Caption grey: `"Ridge regression coefficients · Permutation importance (Random Forest)"`
- Horizontal bar chart, top 8 features (approximate rank order):
  1. `baseline_deviation_entry`
  2. `hour_of_day`
  3. `playlist_calm`
  4. `pre_stress_mean`
  5. `body_battery`
  6. `hr_baseline_deviation`
  7. `day_of_week`
  8. `days_since_last_session`
- Positive bars: `accent-green` · Negative bars: `stress-red`
- `accent-green` left border on top feature

**Bayesian Posteriors** — `bg-card`, 80px padding
- H2 white: `"Bayesian Recommender — Posterior Distributions"`
- Caption grey: `"2,000 MCMC samples via JAX/NumPyro · 89% credible intervals shown"`
- 3×2 grid (6 participants):
  - Each block: Caption white participant name + 3 horizontal bar-with-whisker charts (Calm / Neutral / Energy posterior means ± CI)

**Significance Tests** — `bg-card`, 80px padding
- H2 white: `"Session Effects — Statistical Significance"`
- Caption grey: `"Wilcoxon signed-rank, two-tailed · N≥5 guard · Per-participant"`
- Table columns: Participant · Test · Statistic · p-value · Significant
- Significant rows: `accent-green` checkmark · Non-significant: `text-secondary` dash

**Architecture Diagram** — `bg-card`, 80px padding
- H2 white: `"How It All Connects"`
- Horizontal flow diagram (boxes with `accent-green` arrows):
  ```
  Spotify CSV → Playlist Generator → 3 Playlist Types ──────────────────────┐
                                                                              ↓
  Garmin FIT  → Wearables Pipeline → Biometric CSVs → Feature Matrix → Circadian ML → Mood Prediction
                                                             │
                                                             └──→ Bayesian Model → Playlist Recommendation
  ```
- Each box: `bg-elevated`, 8px radius, Caption white label

**Open Data Footer** — full-width, `bg-elevated`, 48px, centered
- Caption grey: `"All model code, raw data, and MCMC traces are available in the open-source repository."`
- Caption `accent-green`: `"View on GitHub →"`

---

## Figma File Structure

Create 7 pages, one per screen:

```
1. Home
2. The Science
3. Circadian
4. Recommend
5. Replay
6. Results
7. Model
```

Each page: one 1440px-wide frame, height to content.  
NavBar is reused across all frames with the active item changed per page.

---

## Open Data / Open Science UX Principles

Applied consistently across all pages:

1. **Data provenance labels** — small caption showing which script/file produced each chart
2. **Expandable "How was this calculated?" sections** — collapsed by default
3. **Raw data access links** — footer links to GitHub / data export
4. **Confidence indicators** — every number shown with its uncertainty
5. **Plain-language explanations** — every chart has a one-sentence "What this means" label
