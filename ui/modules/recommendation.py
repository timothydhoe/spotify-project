"""Pagina 4 -- Aanbevelen: live interactieve demo van de aanbevelingsmotor."""
import pandas as pd
import plotly.graph_objects as go
from shiny import module, reactive, render, ui as _ui
from shinywidgets import output_widget, render_widget

from utils.chart_helpers import ACCENT, GRID_COLOR, PLAYLIST_COLORS, STRESS_RED, TEXT_SECONDARY, dark_layout, empty_figure
from utils.data_loader import PARTICIPANTS, AppData, best_playlist_for, expected_stress, live_recommend, explain_live_prediction
from utils.playlist_salt import compute_salt_params

_ACTIVITY_STATES = ["Slaap", "Rust", "Licht", "Matig", "Zwaar"]
_ACTIVITY_EN     = {"Slaap": "Sleep", "Rust": "Rest", "Licht": "Light",
                    "Matig": "Medium", "Zwaar": "Heavy"}


def _posterior_chart(recs: dict) -> go.Figure:
    if not recs:
        return empty_figure("Geen Bayesiaanse data beschikbaar")

    playlists  = ["Calm", "Neutral", "Energy"]
    nl_labels  = {"Calm": "Kalm", "Neutral": "Neutraal", "Energy": "Energiek"}
    base_colors = [PLAYLIST_COLORS[p] for p in playlists]
    means      = [recs.get(p, {}).get("mean", 0)   for p in playlists]
    ci_low     = [recs.get(p, {}).get("ci_low", 0) for p in playlists]
    ci_high    = [recs.get(p, {}).get("ci_high", 0) for p in playlists]
    total      = sum(max(m, 0) for m in means)
    pcts       = [max(m, 0) / total * 100 if total > 0 else 0 for m in means]

    # Bars where the CI lower-bound dips below zero are "uncertain"
    uncertain  = [lo < 0 for lo in ci_low]
    colors     = ["rgba(120,120,120,0.5)" if u else c
                  for u, c in zip(uncertain, base_colors)]

    hover_texts = []
    for p, m, lo, hi, u in zip(playlists, means, ci_low, ci_high, uncertain):
        note = " ⚠ onzeker (CI omvat 0)" if u else ""
        hover_texts.append(
            f"<b>{nl_labels[p]}</b><br>"
            f"Gem. voorspeld: {m:.2f}<br>"
            f"89% CI: [{lo:.2f}, {hi:.2f}]{note}<extra></extra>"
        )

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=pcts,
        y=[nl_labels[p] for p in playlists],
        orientation="h",
        marker_color=colors,
        error_x=dict(
            type="data",
            arrayminus=[max(m - lo, 0) / total * 100 if total > 0 else 0
                        for m, lo in zip(means, ci_low)],
            array=[(hi - m) / total * 100 if total > 0 else 0
                   for m, hi in zip(means, ci_high)],
            color=TEXT_SECONDARY,
            thickness=1.5,
            width=6,
        ),
        text=[f"{p:.0f}%{'  ⚠' if u else ''}" for p, u in zip(pcts, uncertain)],
        textposition="outside",
        textfont=dict(color=TEXT_SECONDARY, size=11),
        hovertemplate=hover_texts,
    ))

    # Zero-baseline reference line
    fig.add_vline(x=0, line=dict(color="rgba(255,255,255,0.25)", width=1, dash="dot"))

    fig.update_layout(**dark_layout(
        xaxis=dict(title="Relatieve voorkeur (%)", range=[0, 125], gridcolor=GRID_COLOR),
        yaxis=dict(gridcolor="rgba(0,0,0,0)"),
        height=200,
        margin=dict(l=80, r=32, t=16, b=40),
        bargap=0.35,
    ))
    return fig


def _activity_pills(selected: str) -> _ui.Tag:
    pills = [
        _ui.input_action_button(
            f"activity_{state}",
            state,
            class_="pill-btn" + (" active" if state == selected else ""),
        )
        for state in _ACTIVITY_STATES
    ]
    return _ui.div(*pills, class_="pill-group")


_ISO_LABEL_NL = {
    "Calm":    "ISO - Afdaling",
    "Energy":  "ISO - Opstijging",
    "Neutral": "ISO - Stabiel",
}
_PLAYLIST_NL   = {"Calm": "KALM", "Neutral": "NEUTRAAL", "Energy": "ENERGIEK"}
_PLAYLIST_NL_L = {"Calm": "Kalm", "Neutral": "Neutraal", "Energy": "Energiek"}
_PL_COLORS     = {"Calm": "#3b82f6", "Neutral": "#a855f7", "Energy": "#f97316"}


def _ranked_list(recs: dict) -> _ui.Tag:
    """Ranked 1/2/3 card instead of a bar chart."""
    if not recs:
        return _ui.div("Geen posteriordata beschikbaar.", class_="mt-caption mt-secondary")

    playlists = ["Calm", "Neutral", "Energy"]
    means     = {p: recs.get(p, {}).get("mean", 0)   for p in playlists}
    ci_low    = {p: recs.get(p, {}).get("ci_low", 0) for p in playlists}
    ci_high   = {p: recs.get(p, {}).get("ci_high", 0) for p in playlists}
    total     = sum(max(m, 0) for m in means.values())
    pcts      = {p: max(means[p], 0) / total * 100 if total > 0 else 0 for p in playlists}

    ranked = sorted(playlists, key=lambda p: means[p], reverse=True)
    rank_labels = ["1.", "2.", "3."]

    rows = []
    for rank_num, (rank_lbl, pl) in enumerate(zip(rank_labels, ranked), 1):
        color     = _PL_COLORS.get(pl, ACCENT)
        nl        = _PLAYLIST_NL_L.get(pl, pl)
        pct       = pcts[pl]
        uncertain = ci_low[pl] < 0
        lo        = ci_low[pl]
        hi        = ci_high[pl]

        badge_style = (
            f"display:inline-block; padding:3px 10px; border-radius:12px; "
            f"background:{color}22; color:{color}; font-weight:600; font-size:12px; "
            f"border:1px solid {color}55; margin-right:8px;"
        )
        pct_style = f"font-size:20px; font-weight:700; color:{'#6b7280' if uncertain else color};"

        uncertainty_note = (
            _ui.span(" ⚠ CI omvat nul", style="font-size:11px; color:#f59e0b; margin-left:6px;")
            if uncertain else _ui.span()
        )
        ci_note = _ui.div(
            f"89% CI: [{lo:.2f}, {hi:.2f}]",
            style="font-size:11px; color:var(--text-tertiary); margin-top:2px;",
        )

        rows.append(_ui.div(
            _ui.span(rank_lbl, style="font-size:16px; font-weight:600; color:var(--text-secondary); margin-right:10px; min-width:20px;"),
            _ui.span(nl, style=badge_style),
            _ui.span(f"{pct:.0f}%", style=pct_style),
            uncertainty_note,
            ci_note,
            style=(
                "display:flex; align-items:center; padding:12px 0; "
                + ("border-bottom:1px solid var(--border-default);" if rank_num < 3 else "")
            ),
        ))

    return _ui.div(*rows)


# ---------------------------------------------------------------------------
# Module UI
# ---------------------------------------------------------------------------

@module.ui
def ui():
    return _ui.div(
        # Koptekst
        _ui.div(
            _ui.div("Bayesiaanse Aanbevelingsmotor", class_="mt-h1"),
            _ui.p(
                "Verken hoe het hiërarchische Bayesiaanse model playlist-aanbevelingen maakt per deelnemer. "
                "De schuifregelaars geven context — de aanbeveling zelf is pre-berekend op historische sessies.",
                class_="mt-body mt-secondary",
                style="margin-top:8px;",
            ),
            style="text-align:center; padding:48px var(--page-margin) 32px;",
        ),

        # Twee kolommen: vaste linkerbreedte, rechts vult aan
        _ui.div(
            _ui.div(
                # Links — invoer
                _ui.div(
                    _ui.div("Jouw huidige situatie", class_="mt-h2", style="margin-bottom:20px;"),

                    # Stress
                    _ui.div(
                        _ui.div(
                            _ui.span("Kies je stressniveau", class_="mt-body mt-secondary"),
                            _ui.output_ui("stress_display"),
                            style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;",
                        ),
                        _ui.input_slider("stress", None, min=0, max=100, value=55, step=1, width="100%"),
                        _ui.div(
                            _ui.span("0 — ontspannen", class_="mt-caption mt-tertiary"),
                            _ui.span("100 — zeer gestresseerd", class_="mt-caption mt-tertiary"),
                            style="display:flex; justify-content:space-between; margin-top:4px;",
                        ),
                        style="margin-bottom:24px;",
                    ),

                    # Tijdstip
                    _ui.div(
                        _ui.div(
                            _ui.span("Huidig tijdstip", class_="mt-body mt-secondary"),
                            _ui.output_ui("time_display"),
                            style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;",
                        ),
                        _ui.input_slider("hour", None, min=0, max=23, value=17, step=1, width="100%"),
                        _ui.div(
                            _ui.span("00:00", class_="mt-caption mt-tertiary"),
                            _ui.span("23:00", class_="mt-caption mt-tertiary"),
                            style="display:flex; justify-content:space-between; margin-top:4px;",
                        ),
                        style="margin-bottom:24px;",
                    ),

                    # Body Battery
                    _ui.div(
                        _ui.div(
                            _ui.span("Body Battery", class_="mt-body mt-secondary"),
                            _ui.output_ui("battery_display"),
                            style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;",
                        ),
                        _ui.input_slider("battery", None, min=0, max=100, value=40, step=1, width="100%"),
                        _ui.div(
                            "Garmin Body Battery — lager = meer vermoeid",
                            class_="mt-caption mt-tertiary",
                            style="margin-top:4px;",
                        ),
                        style="margin-bottom:24px;",
                    ),

                    # Activiteitstoestand
                    _ui.div(
                        _ui.div("Activiteitstoestand", class_="mt-body mt-secondary",
                                style="margin-bottom:10px;"),
                        _ui.output_ui("activity_pills_ui"),
                        style="margin-bottom:20px;",
                    ),

                ),

                # Rechts — uitvoer
                _ui.div(
                    # Historical-data disclaimer — above the badge
                    _ui.div(
                        "Twee aanbevelingen: Bayesiaans (historisch) en Live Ridge (huidige staat). "
                        "Overeenstemming = robuustere aanbeveling.",
                        class_="mt-caption mt-secondary",
                        style=(
                            "border-left:3px solid var(--accent); padding:6px 10px; "
                            "margin-bottom:16px; background:var(--bg-elevated); "
                            "border-radius:0 4px 4px 0;"
                        ),
                    ),

                    # Hero badges — Bayesian + Live side by side
                    _ui.div(
                        _ui.div(
                            _ui.div("Bayesiaans (historisch)", class_="mt-caption mt-secondary",
                                    style="text-align:center; margin-bottom:6px;"),
                            _ui.output_ui("rec_badge"),
                            style="flex:1;",
                        ),
                        _ui.div(
                            _ui.div("Live Ridge (nu)", class_="mt-caption mt-secondary",
                                    style="text-align:center; margin-bottom:6px;"),
                            _ui.output_ui("live_rec_panel"),
                            style="flex:1;",
                        ),
                        style="display:flex; gap:16px; align-items:flex-start; margin-bottom:16px;",
                    ),

                    # Salt explanation
                    _ui.output_ui("salt_explanation_ui"),

                    # Verwacht effect aandeel
                    _ui.div(
                        _ui.div(
                            _ui.span("Verwacht effect aandeel", class_="mt-caption mt-secondary"),
                            _ui.output_ui("confidence_pct"),
                            style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:8px;",
                        ),
                        _ui.output_ui("confidence_bar"),
                        _ui.div(
                            "Aandeel van de totale voorspelde stemmingswinst — niet een kans",
                            class_="mt-caption mt-tertiary",
                            style="margin-top:4px;",
                        ),
                        style="margin-bottom:24px;",
                    ),

                    # Ranglijst posterior
                    _ui.div(
                        _ui.div("Posterior ranglijst — verwacht effect aandeel",
                                class_="mt-caption mt-secondary",
                                style="margin-bottom:4px;"),
                        _ui.div("89% CI via MCMC (4000 samples) · % = aandeel van totaal verwacht effect, geen kans",
                                class_="mt-caption mt-tertiary",
                                style="margin-bottom:12px; font-style:italic;"),
                        _ui.output_ui("ranked_list_ui"),
                        _ui.div(
                            "Grijs = 89% CI omvat nul (onvoldoende bewijs voor positief effect)",
                            class_="mt-caption",
                            style="color:#f59e0b; margin-top:8px;",
                        ),
                        _ui.output_ui("sample_size_note"),
                        style="margin-bottom:16px;",
                    ),

                    # Posterior-grafiek (opvouwbaar)
                    _ui.HTML(
                        '<details class="mt-details" style="margin-bottom:16px;">'
                        '<summary>Posterior details (foutenbalken)</summary>'
                        '<div class="mt-details-body" style="padding-top:8px;">'
                        '<p style="font-size:11px; color:var(--text-tertiary); margin-bottom:8px; font-style:italic;">'
                        'Pre-berekend per deelnemer · foutenbalken = 89% CI · ⚠ = CI omvat nul'
                        '</p>'
                    ),
                    output_widget("posterior_chart"),
                    _ui.HTML('</div></details>'),

                    # Ridge attribution chart (opvouwbaar)
                    _ui.HTML(
                        '<details class="mt-details" style="margin-bottom:16px;">'
                        '<summary>Waarom deze aanbeveling? (Ridge-bijdragen)</summary>'
                        '<div class="mt-details-body" style="padding-top:8px;">'
                        '<p style="font-size:11px; color:var(--text-tertiary); margin-bottom:8px; font-style:italic;">'
                        'Bijdrage per kenmerk = regressiecoëfficiënt × huidige waarde. '
                        'Groen = positieve bijdrage aan stemmingswinst, rood = negatief.'
                        '</p>'
                    ),
                    output_widget("feature_importance_chart"),
                    _ui.HTML('</div></details>'),

                    # Uitleg
                    _ui.output_ui("explanation_callout"),

                    # Hoe berekend (opvouwbaar)
                    _ui.div(
                        _ui.input_action_button("expand_calc", "Hoe is dit berekend? ↓",
                                                class_="mt-expand-trigger"),
                        _ui.output_ui("expanded_calc"),
                        style="margin-top:16px;",
                    ),
                ),

                class_="rec-two-col",
            ),
            class_="mt-section-card",
            style="margin:0 var(--page-margin) 64px;",
        ),
    )


# ---------------------------------------------------------------------------
# Module server
# ---------------------------------------------------------------------------

@module.server
def server(input, output, session, app_data: AppData, selected_participant=None):
    sel = selected_participant if selected_participant is not None else reactive.Value("bosbes")
    activity  = reactive.Value("Matig")
    show_calc = reactive.Value(False)

    for _state in _ACTIVITY_STATES:
        def _obs(s=_state):
            @reactive.Effect
            @reactive.event(input[f"activity_{s}"])
            def _():
                activity.set(s)
        _obs()

    @reactive.Effect
    @reactive.event(input.expand_calc)
    def _toggle():
        show_calc.set(not show_calc())

    @output
    @render.ui
    def stress_display():
        val = input.stress()
        color = "#ef4444" if val > 70 else ("#f59e0b" if val > 40 else "#22c55e")
        return _ui.div(str(val), class_="mt-slider-value", style=f"color:{color};")

    @output
    @render.ui
    def time_display():
        return _ui.div(f"{input.hour():02d}:00", class_="mt-slider-value")

    @output
    @render.ui
    def battery_display():
        val = input.battery()
        color = "#ef4444" if val < 30 else ("#f59e0b" if val < 50 else "#22c55e")
        return _ui.div(str(val), class_="mt-slider-value", style=f"color:{color};")

    @output
    @render.ui
    def activity_pills_ui():
        return _activity_pills(activity())

    @reactive.Calc
    def baseline_deviation():
        exp, _ = expected_stress(app_data, sel(), input.hour())
        return None if exp is None else input.stress() - exp

    @reactive.Calc
    def recommendation():
        return best_playlist_for(app_data, sel())

    @reactive.Calc
    def live_recommendation():
        """Build a synthetic bio_row from current slider values and call live_recommend()."""
        p      = sel()
        stress = float(input.stress())
        hour   = float(input.hour())
        batt   = float(input.battery())
        act_en = _ACTIVITY_EN.get(activity(), "Medium")
        exp, _ = expected_stress(app_data, p, int(hour))
        baseline_dev = (stress - exp) if exp is not None else 0.0
        activity_enc = {"Sleep": 0, "Rest": 1, "Light": 2, "Medium": 3, "Heavy": 4}.get(act_en, 2)
        bio_row = pd.Series({
            "baseline_deviation_entry":  baseline_dev,
            "hr_baseline_deviation":     0.0,
            "mood_before_score":         5.0,
            "bb_start":                  batt,
            "days_since_last_session":   3.0,
            "pre_state_encoded":         float(activity_enc),
            "avg_resp_daily":            float("nan"),
            "session_number":            5.0,
            "start_local":               f"{int(hour):02d}:00",
            "day_of_week":               3.0,
        })
        return live_recommend(app_data, p, bio_row)

    @output
    @render.ui
    def rec_badge():
        playlist, _ = recommendation()
        type_name = _PLAYLIST_NL.get(playlist, playlist.upper())
        iso_label = _ISO_LABEL_NL.get(playlist, "")
        return _ui.div(
            _ui.div("Aanbeveling", class_="mt-rec-hero-eyebrow"),
            _ui.div(type_name.upper(), class_=f"mt-rec-hero-type {playlist.lower()}"),
            _ui.div(iso_label, class_="mt-rec-hero-iso"),
            class_=f"mt-rec-badge-hero {playlist.lower()}",
        )

    @output
    @render.ui
    def confidence_pct():
        _, pct = recommendation()
        return _ui.div(f"{pct}%", class_="mt-h2 mt-green")

    @output
    @render.ui
    def confidence_bar():
        _, pct = recommendation()
        return _ui.div(
            _ui.div(style=f"width:{pct}%;", class_="mt-progress-fill"),
            class_="mt-progress-track",
        )

    @output
    @render.ui
    def ranked_list_ui():
        recs = app_data.recommendations.get(sel(), {})
        return _ranked_list(recs)

    @output
    @render.ui
    def live_rec_panel():
        best_pl, preds = live_recommendation()
        if not preds:
            return _ui.div(
                "Live model niet beschikbaar (onvoldoende trainingsdata).",
                class_="mt-caption mt-secondary",
            )
        type_name = _PLAYLIST_NL.get(best_pl, best_pl.upper())
        iso_label = _ISO_LABEL_NL.get(best_pl, "")
        pred_str  = " | ".join(
            f"{_PLAYLIST_NL_L.get(k, k)}: {v:+.2f}" for k, v in sorted(preds.items())
        )
        return _ui.div(
            _ui.div(
                _ui.div("LIVE", class_="mt-rec-hero-eyebrow"),
                _ui.div(type_name.upper(), class_=f"mt-rec-hero-type {best_pl.lower()}"),
                _ui.div(iso_label, class_="mt-rec-hero-iso"),
                class_=f"mt-rec-badge-hero {best_pl.lower()}",
                style="border-style:dashed;",
            ),
            _ui.div(pred_str, class_="mt-caption mt-tertiary", style="margin-top:6px; font-style:italic;"),
        )

    @output
    @render.ui
    def salt_explanation_ui():
        stress = float(input.stress())
        batt   = float(input.battery())
        act    = activity()
        params = compute_salt_params(stress, batt, act)
        if not params.context_notes:
            return _ui.div()
        items = [_ui.li(note, class_="mt-caption") for note in params.context_notes]
        return _ui.div(
            _ui.div("Audio-aanpassingen op basis van huidige staat", class_="mt-caption mt-secondary",
                    style="margin-bottom:6px; font-weight:600;"),
            _ui.tags.ul(*items, style="margin:0; padding-left:16px; list-style:disc;"),
            style=(
                "border-left:3px solid var(--energy); padding:8px 12px; "
                "background:var(--bg-elevated); border-radius:0 4px 4px 0; margin-bottom:16px;"
            ),
        )

    @output
    @render_widget
    def posterior_chart():
        recs = app_data.recommendations.get(sel(), {})
        return _posterior_chart(recs)

    @output
    @render_widget
    def feature_importance_chart():
        best_pl, _ = live_recommendation()
        p          = sel()
        stress     = float(input.stress())
        hour       = float(input.hour())
        batt       = float(input.battery())
        act_en     = _ACTIVITY_EN.get(activity(), "Medium")
        exp, _     = expected_stress(app_data, p, int(hour))
        bio_row    = pd.Series({
            "baseline_deviation_entry": (stress - exp) if exp is not None else 0.0,
            "hr_baseline_deviation":    0.0,
            "mood_before_score":        5.0,
            "bb_start":                 batt,
            "days_since_last_session":  3.0,
            "pre_state_encoded":        float({"Sleep":0,"Rest":1,"Light":2,"Medium":3,"Heavy":4}.get(act_en,2)),
            "avg_resp_daily":           float("nan"),
            "session_number":           5.0,
            "start_local":              f"{int(hour):02d}:00",
            "day_of_week":              3.0,
        })
        attributions = explain_live_prediction(app_data, p, bio_row, best_pl)
        if not attributions:
            return empty_figure("Live model niet beschikbaar")
        names  = [a[0] for a in attributions]
        values = [a[1] for a in attributions]
        colors = ["#22c55e" if v >= 0 else "#ef4444" for v in values]
        fig = go.Figure(go.Bar(
            x=values, y=names, orientation="h",
            marker_color=colors,
            hovertemplate="%{y}: %{x:+.3f}<extra></extra>",
            text=[f"{v:+.3f}" for v in values],
            textposition="outside",
            textfont=dict(color=TEXT_SECONDARY, size=10),
        ))
        fig.add_vline(x=0, line=dict(color="rgba(255,255,255,0.25)", width=1, dash="dot"))
        fig.update_layout(**dark_layout(
            xaxis=dict(title="Bijdrage aan voorspelde stemmingswinst", gridcolor=GRID_COLOR),
            yaxis=dict(gridcolor="rgba(0,0,0,0)"),
            height=220,
            margin=dict(l=180, r=60, t=16, b=40),
            bargap=0.4,
        ))
        return fig

    @output
    @render.ui
    def sample_size_note():
        p   = sel()
        fm  = app_data.feature_matrix
        if fm is not None and not fm.empty and "participant" in fm.columns:
            n = int((fm["participant"] == p).sum())
        else:
            bio = app_data.session_biometrics.get(p, None)
            n = len(bio) if bio is not None and not bio.empty else 0
        if n > 0:
            return _ui.div(
                _ui.p(f"N={n} sessies voor {p.capitalize()}. "
                      "Posterior breedte neemt af naarmate meer sessies beschikbaar zijn.",
                      class_="mt-caption mt-tertiary",
                      style="margin:4px 0 0;"),
            )
        return _ui.div()

    @output
    @render.ui
    def explanation_callout():
        bayes_pl, pct = recommendation()
        live_pl, _    = live_recommendation()
        hour  = input.hour()
        dev   = baseline_deviation()
        batt  = input.battery()
        act   = activity()
        p     = sel()

        dev_str = ""
        if dev is not None:
            sign = "+" if dev >= 0 else ""
            rel  = "boven" if dev >= 0 else "onder"
            dev_str = (
                f" Stress is {sign}{dev:.0f} pt {rel} basislijn op {hour:02d}:00."
            )

        batt_str = ""
        if batt < 40:
            batt_str = f" Body battery ({batt}%) wijst op vermoeidheid."
        elif batt > 70:
            batt_str = f" Body battery ({batt}%) is goed opgeladen."

        nl_bayes = {"Calm": "Kalm", "Neutral": "Neutraal", "Energy": "Energiek"}.get(bayes_pl, bayes_pl)
        nl_live  = {"Calm": "Kalm", "Neutral": "Neutraal", "Energy": "Energiek"}.get(live_pl,  live_pl)

        if bayes_pl == live_pl:
            coherence = f"Beide modellen bevelen {nl_bayes} aan — robuuste aanbeveling."
            callout_pl = bayes_pl
        else:
            coherence = (
                f"Bayesiaans (historisch): {nl_bayes} ({pct}% relatieve voorkeur). "
                f"Live Ridge (nu): {nl_live}. Modellen wijken af — gebruik de Live-badge voor de huidige situatie."
            )
            callout_pl = live_pl

        text = f"{coherence}{dev_str}{batt_str}"
        return _ui.div(text, class_=f"mt-callout {callout_pl.lower()}", style="margin-top:16px;")

    @output
    @render.ui
    def expanded_calc():
        if not show_calc():
            return _ui.div(style="height:1px; overflow:hidden;")
        dev    = baseline_deviation()
        hour   = input.hour()
        stress = input.stress()
        p      = sel()
        exp, _ = expected_stress(app_data, p, hour)
        exp_str   = f"{exp:.0f}" if exp is not None else "geen basislijn"
        dev_str   = f"{dev:+.0f}" if dev is not None else "n.v.t."
        sign_word = "boven" if (dev or 0) >= 0 else "onder"

        return _ui.div(
            _ui.div(
                _ui.div("Stressafwijking van basislijn:", class_="mt-caption mt-secondary",
                        style="margin-bottom:6px;"),
                _ui.div(
                    f"Stress: {stress}   Verwacht op {hour:02d}:00: {exp_str}",
                    class_="mt-code-block",
                    style="margin-bottom:6px;",
                ),
                _ui.div(
                    f"afwijking = {stress} - {exp_str} = {dev_str} pt {sign_word} basislijn",
                    class_="mt-code-block",
                ),
            ),
            _ui.div(
                _ui.div("Twee modellen:", class_="mt-caption mt-secondary",
                        style="margin-bottom:6px; margin-top:12px;"),
                _ui.div(
                    "Bayesiaans (historisch) — MCMC 4000 samples. Schat stemmingseffect per "
                    "afspeellijsttype op basis van alle historische sessies van deze deelnemer. "
                    "Vast per deelnemer; sliders veranderen het niet.",
                    class_="mt-caption mt-secondary",
                    style="margin-bottom:6px;",
                ),
                _ui.div(
                    "Ridge (live) — lineaire regressie op 16 kenmerken (stressafwijking, "
                    "body battery, activiteit, uur, circadiaanse encoding). "
                    "Reageert direct op de sliders en geeft een voorspelling voor de huidige situatie.",
                    class_="mt-caption mt-secondary",
                ),
            ),
            class_="mt-expand-content",
        )
