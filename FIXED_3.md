# FIXED_3.md — MoodTune Feedback Resolution Plan
> Project R.E.M. · Regulation of Emotion through Music
> Branch: feat/app-shiny · Date: 2026-05-26

---

## Phase 1 — Quick UX Wins
*Presentation-layer fixes only. No model retraining.*

### 1A — Circadian tooltip enrichment
**Problem:** Session-dot tooltips on the Circadiaans Ritme chart only show `date, hour, pre-stress, playlist, mood_delta`. Missing: post-stress, mood label (moe/gespannen), before/after scores.

**Files:** `modules/circadian.py`

- [x] Enrich `session_df` in server: join `session_biometrics[p][["date","mood_before","mood_after","post_stress_mean"]]` on `date` before passing to `_build_circadian_chart()`.
- [x] Extend `customdata` in `_build_circadian_chart()` from 3 to 5 fields: add `mood_before_label` and `post_stress_str`.
- [x] Update `hovertemplate` to render 7 fields: datum, uur, pre-stress, post-stress, stemming voor (label), stemmingsdelta.
- [x] In `_on_click()` and `dot_detail_panel()`: add "Stemming voor" and "Post-stress" rows to the detail panel.

**Verification:** Click a session dot → 7 fields visible.

---

### 1B — "Laagste stress" sleep filter
**Problem:** `_compute_stats()` finds the minimum-stress hour across all 24 hours. Night hours (0–5) dominate because the watch is removed or the participant is sleeping → "Gouden uur = 1:00" is meaningless.

**Files:** `modules/circadian.py`, `modules/results.py`

- [x] In `modules/circadian.py`, `_compute_stats()`: filter `hb_df` to `hour.between(6, 23)` before `idxmin()` / `idxmax()`. Fallback to full df if empty.
- [x] In `modules/results.py`, `_compute_summary()` (~line 154): apply same `hour.between(6, 23)` filter before computing `golden_hour` and `peak_window`.
- [x] Add footnote text: "Beperkt tot uren 6–23 (wake-uren); nacht-metingen zijn uitgesloten."

**Verification:** For bosbes, "Gouden uur" changes from ~1:00 to ~23:00.

---

### 1C — Context-aware "Verbeterd/Gedaald"
**Problem:** All three call sites use `delta > 0 → Verbeterd`. For negative moods (moe, gespannen), lower score after = improvement, which gets incorrectly labelled "Gedaald".

**Scientific basis:** The mood scale (1-10) measures intensity of the current emotion. Improvement = `composite_after > composite_before` where `composite = valence × intensity` (same logic as the Bayesian recommender's `VALENCE_MAP`).

**Files:** `utils/mood_valence.py` (new), `modules/results.py`, `modules/session_replay.py`

- [x] Create `utils/mood_valence.py` with `VALENCE_MAP`, `emotion_valence()`, `composite_mood()`, `mood_is_improvement()`.
- [x] In `modules/results.py`, `_session_table()` (~line 265): replace `delta > 0` check with `mood_is_improvement(before_label, before_score, after_label, after_score)`. Add `mood_before` and `mood_after` columns to `df`.
- [x] In `modules/results.py`, `_compute_summary()` (~line 136): replace `avg_mood_lift` (raw delta mean) with composite-weighted lift.
- [x] In `modules/session_replay.py`, `outcome_banner()` (~line 557): replace raw delta comparison with `mood_is_improvement()`.
- [x] In `modules/session_replay.py`, `_mood_arc()` (~line 178): update `delta_col` color using `mood_is_improvement()`.
- [x] Add legend note: "✓ = verbetering op basis van emotievalentie (negatieve emoties: lagere intensiteit = beter)."

**Verification:**
- "Moe (7) → Neutraal (4)": composite_before = -7, composite_after = 0 → correctly shows "✓ Verbeterd".
- "Happy (3) → Relax (5)": composite_before = +3, composite_after = +5 → "✓ Verbeterd".
- "Neutraal (5) → Moe (6)": composite_before = 0, composite_after = -6 → "✗ Gedaald".

---

## Phase 2 — Data Validation

### 2A — Session replay gap display
**Problem:** Per-minute stress data has significant null rates (kokosnoot 33.9%, bosbes 83.3%, peer 78.2%). Unclear if Plotly renders gaps correctly (breaks vs. connected lines).

**Files:** `modules/session_replay.py`, `scripts/analysis/trace_gap_audit.py` (new)

- [x] In `_biometric_chart()`: explicitly add `connectgaps=False` to both Scatter traces so NaN rows show as line breaks, not interpolated gaps.
- [x] Add `_coverage_badge()` helper computing `stress.notna().mean()` for the "during" phase → color-coded "Stressdata: X% gevuld".
- [x] Add `_ui.output_ui("coverage_badge_ui")` below `output_widget("biometric_chart")` in module UI.
- [x] Add `@output @render.ui coverage_badge_ui` server renderer.
- [ ] Write `scripts/analysis/trace_gap_audit.py`: print gap ranges per participant × session to confirm gaps are genuine (watch removed / battery dead).

**Verification:** Kokosnoot chart shows clear stress line breaks. Coverage badge displays "33% gevuld" (approx.).

---

### 2B — Mood vs biometrics alignment panel
**Problem:** High biometric stress + "Neutraal" self-report is a meaningful mismatch not surfaced.

**Files:** `modules/session_replay.py`

- [ ] Add `_mood_bio_comparison()` helper comparing `pre_stress_mean` with `mood_before_score` + `mood_before_label`. Three outcomes: "Overeenkomst", "Onovereenkomst", "Onvoldoende data".
- [ ] Render inside `session_summary()` when `pre_stress_mean` is available.

---

## Phase 3 — Aanbevelingen Overhaul

### 3A — Surface live Ridge model
**Problem:** Sliders (stress, hour, battery, activity) collect input but don't feed any model. The Bayesian recommendation is static (pre-computed offline). `live_recommend()` exists in `data_loader.py` but is never called from the UI. Root cause of "Energy 90%": when Calm and Neutral have negative posterior means, Energy gets 100% share of positive-only denominator.

**Files:** `modules/recommendation.py`, `utils/data_loader.py`

- [x] Add `live_recommend` to imports in `modules/recommendation.py`.
- [x] Add `@reactive.Calc live_recommendation()` constructing a synthetic `bio_row` from slider values. Use `expected_stress()` to compute `baseline_deviation_entry`.
- [x] Add `@output @render.ui live_rec_panel` rendering a "Live" recommendation badge (dashed border, "LIVE" tag) distinct from the Bayesian badge.
- [x] Add `_ui.output_ui("live_rec_panel")` to module UI after `rec_badge`.
- [x] Fix percentage display: when only one playlist has positive mean, show note "Alleen {pl} heeft een positief historisch effect".
- [x] Update `explanation_callout`: show both Bayesian and Ridge recommendations when they agree/disagree.
- [x] Update `expanded_calc`: explain difference between Bayesian (MCMC posterior, historical) and Ridge (linear coefficients, current state).

**Verification:** Stress slider 30 → 90 changes Ridge recommendation. For peer, Bayesian always Energy but Ridge may differ at low body battery.

---

### 3B — Playlist "salt" (biometric-state-aware audio thresholds)
**Problem:** Playlists are deterministic (same songs every session). The ISO principle implies starting BPM/tension should reflect current participant state.

**Files:** `utils/playlist_salt.py` (new), `modules/recommendation.py`, `scripts/playlists/spotify_modules/generate.py`

- [x] Create `utils/playlist_salt.py` with `compute_salt_params(stress, body_battery, activity) -> dict`:
  - Stress >70 → calm playlist: raise `acousticness_min` from 0.3→0.5, lower `valence_min` threshold (ISO matching).
  - Battery <30 → energy playlist: raise `danceability_min` to 0.65, lower `tempo_min` to 110.
  - Battery >70 → energy playlist: raise `tempo_min` to 130.
- [x] Add `@output @render.ui salt_explanation_ui` rendering adjusted thresholds as a callout below the Ridge panel.
- [ ] In `scripts/playlists/spotify_modules/generate.py`, add `seed` parameter to filter functions so `df.sample(frac=1, random_state=seed)` before `head(PLAYLIST_SIZE)` adds session-specific variation.

**Verification:** Stress=90, battery=20 → callout shows adjusted acousticness/danceability thresholds.

---

### 3C — "Why this playlist" Ridge attribution
**Problem:** Recommendation doesn't explain which features drove the Ridge prediction for the current slider state.

**Files:** `utils/data_loader.py`, `modules/recommendation.py`

- [x] Add `explain_live_prediction(app_data, participant, bio_row, playlist_type) -> list[tuple[str, float]]` to `utils/data_loader.py`. Attribution = `coef_i × x_i` (linear Ridge, no SHAP needed). Return top 5 by |attribution|.
- [x] Add Dutch feature name mapping dict.
- [x] Add `@output @render_widget feature_importance_chart` in `modules/recommendation.py` rendering a horizontal bar chart of attributions.
- [x] Wrap in `<details>` labelled "Waarom deze aanbeveling? (Ridge-bijdragen)".

---

## Phase 4 — Background Pages Review

### 4A — Science page
**Files:** `modules/science.py`

- [x] Add full Thoma et al. (2013) DOI as clickable link: doi.org/10.1371/journal.pone.0070156.
- [x] Add Heiderscheit & Madson (2015) ISO principle citation in collapsible details block.
- [x] Add plain-Dutch `title` tooltip to each Spotify feature card explaining its effect on emotion regulation.
- [ ] Make ISO phase cards interactive: clicking a phase shows an expanded explanation + example BPM range.

### 4B — Model & Data page
**Files:** `modules/model.py`

- [x] Add HTML `title` tooltip to each `<th>` in `_model_table()`:
  - MAE: "Gemiddelde absolute fout — gemiddeld X stemmingspunten mis"
  - RMSE: "Gevoeliger voor grote fouten dan MAE"
  - R2 (LOO-KV): "Verklarende kracht; 0 = niet beter dan gemiddelde; negatief = slechter"
  - Overfittingverschil: "Verschil trainings-R² vs LOO-R²; laag = stabieler model"
- [x] Add plain-language interpretation paragraph below table.
- [x] Update power analysis note: "We hebben ~600 sessies nodig voor statistisch bewijs."

### 4C — Pipeline page
**Files:** `modules/pipeline.py`

- [x] Add file-existence status dot (green/amber/red) to each step button in `_step_btn()`.
- [ ] In `step_detail()`, add "Welke bestanden?" section with actual file sizes.

---

## Phase 5 — Infrastructure Idea (Design only, not urgent)

### 5A — PostgreSQL on Raspberry Pi
*Design documents only — no implementation required now.*

- [ ] Create `docs/infrastructure/raspberry-pi-postgres.md` with Docker Compose spec (postgres:16-alpine, pgAdmin, Caddy for HTTPS).
- [ ] Define DB schema: participants, sessions, songs, participant_songs tables.
- [ ] Document SSH tunnel approach for remote psql access.
- [ ] Sketch `scripts/migrate_to_postgres.py` migration script.
- [ ] Define cross-participant playlist query (songs rated well by similar participants).

---

## Implementation Summary

| # | Phase | Task | Status |
|---|-------|------|--------|
| 1 | 1B | Sleep filter on "laagste stress" | ✅ Done |
| 2 | 1A | Circadian tooltip enrichment | ✅ Done |
| 3 | 1C | Context-aware Verbeterd/Gedaald | ✅ Done |
| 4 | 2A | Session replay gap display + coverage badge | ✅ Done |
| 5 | 3A | Ridge in Aanbevelingen UI (live recommendation) | ✅ Done |
| 6 | 3B | Playlist salt explanation (utils/playlist_salt.py) | ✅ Done |
| 7 | 3C | Ridge attribution chart (feature importances) | ✅ Done |
| 8 | 4A | Science page: DOI link, ISO citation, feature tooltips | ✅ Done |
| 9 | 4B | Model table: header tooltips + plain-language note | ✅ Done |
| 10 | 4C | Pipeline: file existence status dots | ✅ Done |
| 11 | 2B | Mood vs biometrics alignment panel | ✅ Done |
| 12 | 2A | Gap audit script (trace_gap_audit.py) | ✅ Done |
| 13 | 3B | Playlist seed randomisation in generate.py | ✅ Done |
| 14 | 4A | ISO phase interactive cards | ✅ Done |
| 15 | 4C | Pipeline: step file sizes in detail panel | ✅ Done |
| 16 | 5A | Raspberry Pi postgres design docs | ✅ Done |
