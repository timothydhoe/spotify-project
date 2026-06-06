# MoodTune UX Improvement Plan

Screenshots referenced: `audit/screenshots/`

---

## Critical (blocks usability)

- [ ] **Broken images in Model tab — absolute filesystem paths used as `src` attributes.**
  Where: `modules/model.py` → `_shap_section()` and `_posterior_grid()`. Both construct paths like
  `/Users/timothydhoe/Code/spotify-project/data/analysis/...` and pass them directly to `ui.img(src=...)`.
  These are never reachable by the browser. Fix: copy or symlink the relevant plot files under `www/plots/`
  on generation, and reference them as relative URLs (`/plots/...`). See `07_model_tab.png` — SHAP section
  shows fallback text; all 4 posterior images are invisible.

- [ ] **"See the Science →" CTA on Home is a dead link.**
  Where: `modules/home.py` line 41 — `href="#"`. It should navigate to the Science tab. Shiny `page_navbar`
  uses Bootstrap tab IDs; use `ui.tags.a(..., onclick="...")` with a JS click on the tab, or replace with
  `ui.input_action_button` wired to a `session.send_custom_message` call that switches tabs. See `01_initial_load.png`.

- [ ] **Recommendation sliders don't change the recommendation — misleading interaction.**
  Where: `modules/recommendation.py`, `recommendation()` reactive — it calls `best_playlist_for(app_data, participant)`
  with no reference to the stress/hour/battery/activity inputs. A user dragging the stress slider to 0 still
  sees the same "ENERGY" badge. The posteriors are pre-sampled per participant and fixed.
  Fix: either (a) make the inputs actually modulate the recommendation (e.g., override the posterior if
  deviation is extreme), or (b) add a clear callout: *"Your recommendation is based on your historical session
  outcomes — the sliders show how your current state compares to that baseline"*, and visually separate the
  "context" inputs from the fixed recommendation. The current layout implies causation that doesn't exist.
  See `04_recommend_tab.png`.

- [ ] **Model comparison table is entirely empty ("—" for every cell).**
  Where: `modules/model.py` `_model_table()` — file `data/analysis/circadian_baselines/model_results_mood_delta.csv`
  does not exist yet. This section promises "full transparency on every model" but delivers a blank table.
  Either run `circadian_ml.py` to generate the file before the presentation, or replace the empty table with
  a `mt-no-data` placeholder that says "Run `circadian_ml.py` to populate model metrics." — a blank table
  implies the models ran and produced no results, which is worse than a clear "not yet run" state.
  See `07_model_tab.png`.

---

## High (significantly improves experience)

- [ ] **Disabled participant pills (Kiwi, Watermeloen) have no explanation.**
  Where: Circadian tab (`modules/circadian.py` line 191) and Results tab (`modules/results.py` line 198) —
  `.pill-btn.disabled` pills render but are `pointer-events:none` with no tooltip or note.
  A presenter clicking "Kiwi" gets no feedback. Fix: add a `title` attribute ("No data collected for this
  participant") or render a `ui.tooltip()` wrapper. See `03_circadian_tab_default.png`.

- [ ] **"View on GitHub →" link in Model tab is unclickable — no href.**
  Where: `modules/model.py` line 226 — it's a `div` with `cursor:pointer`, not an `<a>` tag.
  Replace with `ui.a("View on GitHub →", href="<repo-url>", target="_blank", class_="mt-caption mt-green")`.

- [ ] **Significance table in Model tab is missing the "test" column — rows are uninterpretable.**
  Where: `modules/model.py` `_significance_table()` line 63 — `wanted` columns include `test` but the
  `significance_tests.csv` column ordering puts multiple rows per participant with no indication of
  *what* is being tested (pre vs during stress? HR? mood delta? per playlist?). Each row currently shows
  only participant + statistic + p-value, making the table unreadable without context.
  Fix: ensure `test` column is rendered (verify it exists in the CSV), and truncate long test names to 30
  chars with `title` tooltip. Also display a `head(20)` note: "Showing 20 of N rows." See `07_model_tab.png`.

- [ ] **Recommend tab: "Participant (Research Mode)" label is confusing in a presentation context.**
  Where: `modules/recommendation.py` line 132 — the "(Research Mode)" badge next to "Participant" implies
  this is an internal debug control, not a participant-facing feature. For the June 20 presentation, either
  hide this selector and default to a single participant, or rename the label to "Whose data?" and explain
  that each participant can only see their own profile.

- [ ] **Recovery badge R² = 0.01 is displayed without caveat — it signals a bad model fit.**
  Where: `modules/session_replay.py` `_recovery_badge()` line 153 — the footnote
  `τ_expected = 98 min · τ_actual = 20 min · R² = 0.01` is technically accurate but R² = 0.01 means the
  exponential decay model explains almost none of the variance in this session. Showing it raw risks
  audience questions about model validity. Fix: add a conditional note when R² < 0.3:
  *"Low R² — recovery curve noisy; τ estimate approximate."* See `05_replay_tab_default.png`.

- [ ] **No loading feedback when switching participants or sessions in reactive outputs.**
  Where: All reactive chart outputs across Circadian, Recommend, Replay, Results. Shiny renders charts
  synchronously here so flicker is brief, but on slower machines a brief blank state appears with no
  indicator. Add `ui.output_ui("...")` with a spinner fallback, or use Shiny's built-in
  `busy_indicators.use()` to show a progress bar during re-render.

---

## Medium (polish & delight)

- [ ] **Plotly toolbar is visible on every chart — it clutters the data science aesthetic.**
  Where: every `render_widget` / `go.Figure` output across all tabs. The full toolbar (zoom, pan, box
  select, lasso, autoscale, reset, plotly logo) is prominent and primarily used during development.
  For presentation mode, hide it with `fig.update_layout(modebar_remove=["select", "lasso2d", "pan",
  "zoom", "autoscale", "resetscale", "toImage"])` or add `config={"displayModeBar": False}` to the
  widget. Leave only the download button if needed. See any screenshot.

- [ ] **"[Name]'s Year in Music Therapy" framing is inaccurate — this is an 8-week study.**
  Where: `modules/results.py` line 221. "Year in Music Therapy" mirrors "Spotify Wrapped" framing but
  the study is ~8 weeks. Use "8 Weeks in Music Therapy" or "[Name]'s Project R.E.M. Summary" instead.

- [ ] **Mood arc in Session Replay shows unchanged emoji even when mood improves.**
  Where: `modules/session_replay.py` `_mood_arc()` — emoji is driven by the raw mood label, so "Stressed
  8/10 → Stressed 6/10" shows two identical 😟 faces even though there was a measurable improvement.
  Fix: map the emoji to the *after* state dynamically, or show a directional delta emoji (⬇️ stress) next
  to the arrow when there's a positive mood delta.

- [ ] **Session Replay timeline header (PRE / DURING / POST) is evenly divided but chart windows are not.**
  Where: `modules/session_replay.py` UI — `.mt-timeline-header` uses `grid-template-columns: 1fr 1fr 1fr`
  (equal thirds), but the biometric chart shows pre-session at −60 to 0, during at 0 to ~30, and post
  extending to +80. The timeline header proportions don't match the data. Either make the grid proportional
  to the actual window widths, or drop the CSS grid and position the labels over the chart's vlines instead.
  See `05_replay_tab_default.png`.

- [ ] **Circadian tab: "Pre-session deviation (mean)" stat card shows "+9.1" with no units or context.**
  Where: `modules/circadian.py` `_compute_stats()` — the deviation card shows a raw number with no
  explanation of what units it's in (stress points, 0–100 scale) or whether +9.1 is large or small.
  Add a sub-label: "stress pts above baseline" to match the formula shown in the explainer section.

- [ ] **Science tab: BPM trajectory chart has no caption explaining the ISO principle visually.**
  Where: `modules/science.py` — the chart shows 3 lines with a legend (Calm/Neutral/Energy) but no title
  or subtitle indicating what the chart demonstrates. Add a `ui.div` caption beneath it:
  *"BPM trajectory over a 30-minute playlist — calm descends from ~95 to ~55 BPM, energy ascends from
  ~120 to ~165 BPM."* See `02_science_tab.png`.

- [ ] **Results tab lacks any long-term trend view — the study's most compelling story.**
  Where: `modules/results.py` — the current stat grid and mood lift chart are session-level averages.
  The longitudinal story (does stress baseline deviation change over the 8-week study?) is exactly what
  `circadian_significance.py` generates but it's not surfaced here. Add a simple line chart of
  `pre_study_baseline_deviation` over session number per participant. This is the "Are we getting better?"
  chart that will land with the audience.

- [ ] **"Body Battery" in Recommend tab has no explanation for lay users.**
  Where: `modules/recommendation.py` line 116 — the slider has no tooltip or caption. Add a
  `mt-caption mt-secondary` note below: *"Garmin Body Battery: 0–100, where 100 = fully rested."*

---

## Low (nice-to-have)

- [ ] **No favicon — browser tab shows a blank icon and logs a 404.**
  Where: `app.py` — no favicon linked. Add a simple `ui.tags.link(rel="icon", href="favicon.ico")` in the
  `header` and drop a `www/favicon.ico` (16×16 green circle would match the navbar dot).

- [ ] **"See the Science →" button should have a down-arrow or different affordance on the Home tab.**
  Where: `modules/home.py` — beyond fixing the dead link (see Critical), the arrow "→" suggests horizontal
  navigation but the user needs to understand they're switching tabs, not scrolling. Use "↗" or
  "Explore the Science" to set clearer expectations.

- [ ] **Recommend tab expanded calc shows raw Python variable names.**
  Where: `modules/recommendation.py` line 289 — `expected_stress_at_17h` is a code-style name. Replace
  with: *"Your expected stress at 17:00 (from your hourly baseline): 26 · Your input: 55 · Deviation: +29"*
  in a human-readable layout.

- [ ] **Significance table is limited to 20 rows with no indication of total count.**
  Where: `modules/model.py` line 69 — `sig_df.head(20)` silently truncates. Add a note after the table:
  *"Showing 20 of {len(sig_df)} rows."*

---

## Design System Alignment

| Area | Current state | Delta vs. reference | Proposed fix |
|------|--------------|---------------------|--------------|
| **Dark theme** | ✓ `#121212` background, `#282828` cards | Matches reference muted dark | No change needed |
| **Typography** | ✓ Inter loaded, correct weight scale | Reference uses generous line-height; `.mt-display` at 52px is correct | No change needed |
| **Card structure** | ✓ `mt-card`, `mt-section-card` used consistently | `mt-section-card` padding is 48px 80px — very generous, charts feel small inside them | Reduce inner padding to 32px 48px for content-heavy cards |
| **Spacing** | Some inconsistency — Circadian stat row uses inline `padding:24px 80px` not a CSS class | Reference uses a strict 8pt grid | Audit `style=` inline padding instances and convert to spacing tokens |
| **Color accents** | ✓ Green/blue/orange/red correctly applied to playlist types | — | No change |
| **Plotly chart styling** | ✓ Dark background, matching colors, Inter-like font via layout | Plotly's default toolbar breaks the clean reference aesthetic (see Medium item above) | Hide toolbar on all production charts |
| **Sidebar** | N/A — tabbed not sidebar layout | Reference has a left sidebar; this app uses top nav instead, which works for 7 sections | No change — top nav is appropriate for a presentation deck |
| **Whitespace** | Good at macro level; individual components like the mood arc have too much vertical padding (`padding: var(--space-6) var(--space-8)` = 48px 64px) | Reference uses generous but not excessive padding | Reduce `.mt-mood-arc` padding to 32px 48px |
| **Restrained color** | ✓ Data ink only — accents used for signal not decoration | — | No change |
| **Onboarding/welcome** | Home tab serves as onboarding but the "HOW IT WORKS" flow diagram uses emojis and informal labels | Reference favors text + subtle icon | Replace emoji icons in flow panels with minimal SVG icons or remove — the text alone is sufficient |

---

## What Works Well

- **Science tab** — The ISO explainer with live BPM trajectory chart next to the prose is exactly right. It demonstrates the principle, doesn't just describe it.
- **Circadian tab** — Session overlay dots (playlist-colored) on the hourly baseline chart is a strong analytical visualization. The deviation explainer box with the formula is well placed and educational.
- **Session Replay tab** — The biometric chart with pre/during/post phase shading is the app's most compelling individual view. The mood arc and recovery badge beneath it tell a complete session story.
- **Recommend tab** — The "How was this calculated?" expandable is good transparency UX. The explanation callout that contextualizes the deviation in plain English is the right instinct.
- **CSS design system** — The token-based `styles.css` is clean and well-structured. Design tokens are applied consistently; no inline style overrides fighting the system. This is a solid foundation.
- **Participant pills** — The pill selector pattern is superior to a dropdown for 6 participants on a presentation screen. Reusing it across Circadian, Results works well.
