"""Pagina 4 -- Aanbevelen: live interactieve demo van de aanbevelingsmotor."""
import plotly.graph_objects as go
from shiny import module, reactive, render, ui as _ui
from shinywidgets import output_widget, render_widget

from utils.chart_helpers import ACCENT, GRID_COLOR, PLAYLIST_COLORS, STRESS_RED, TEXT_SECONDARY, dark_layout, empty_figure
from utils.data_loader import PARTICIPANTS, AppData, best_playlist_for, expected_stress

_ACTIVITY_STATES = ["Slaap", "Rust", "Licht", "Matig", "Zwaar"]
_ACTIVITY_EN     = {"Slaap": "Sleep", "Rust": "Rest", "Licht": "Light",
                    "Matig": "Medium", "Zwaar": "Heavy"}


def _posterior_chart(recs: dict) -> go.Figure:
    if not recs:
        return empty_figure("Geen Bayesiaanse data beschikbaar")

    playlists = ["Calm", "Neutral", "Energy"]
    nl_labels = {"Calm": "Kalm", "Neutral": "Neutraal", "Energy": "Energiek"}
    colors    = [PLAYLIST_COLORS[p] for p in playlists]
    means     = [recs.get(p, {}).get("mean", 0)   for p in playlists]
    ci_low    = [recs.get(p, {}).get("ci_low", 0) for p in playlists]
    ci_high   = [recs.get(p, {}).get("ci_high", 0) for p in playlists]
    total     = sum(means)
    pcts      = [m / total * 100 if total > 0 else 0 for m in means]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=pcts,
        y=[nl_labels[p] for p in playlists],
        orientation="h",
        marker_color=colors,
        error_x=dict(
            type="data",
            arrayminus=[(m - lo) / total * 100 for m, lo in zip(means, ci_low)],
            array=[(hi - m) / total * 100 for m, hi in zip(means, ci_high)],
            color=TEXT_SECONDARY,
            thickness=1.5,
            width=6,
        ),
        text=[f"{p:.0f}%" for p in pcts],
        textposition="outside",
        textfont=dict(color=TEXT_SECONDARY, size=12),
        hovertemplate="<b>%{y}</b><br>Posterior: %{x:.1f}%<extra></extra>",
    ))

    fig.update_layout(**dark_layout(
        xaxis=dict(title="Posterior kans (%)", range=[0, 120], gridcolor=GRID_COLOR),
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
_PLAYLIST_NL = {"Calm": "KALM", "Neutral": "NEUTRAAL", "Energy": "ENERGIEK"}


# ---------------------------------------------------------------------------
# Module UI
# ---------------------------------------------------------------------------

@module.ui
def ui():
    return _ui.div(
        # Koptekst
        _ui.div(
            _ui.div("Wat moet je nu luisteren?", class_="mt-h1"),
            _ui.p(
                "Voer jouw huidige toestand in en ontvang een gepersonaliseerde ISO-afspeellijstaanbeveling.",
                class_="mt-body mt-secondary",
                style="margin-top:8px;",
            ),
            style="text-align:center; padding:48px 80px 32px;",
        ),

        # Twee kolommen
        _ui.div(
            _ui.div(
                # Links - invoer
                _ui.div(
                    _ui.div("Jouw huidige situatie", class_="mt-h2", style="margin-bottom:8px;"),
                    _ui.div(
                        _ui.div(
                            "De schuifregelaars geven context voor de uitleg, "
                            "niet voor de aanbeveling zelf. "
                            "Het Bayesiaanse model is pre-berekend op basis van "
                            "historische sessies — de badge verandert niet met de invoer.",
                            class_="mt-body",
                            style="margin-bottom:4px;",
                        ),
                        class_="mt-callout",
                        style="margin-bottom:20px; border-left-color:#f59e0b;",
                    ),

                    # Stress
                    _ui.div(
                        _ui.div(
                            _ui.span("Stressniveau", class_="mt-body"),
                            _ui.output_text_verbatim("stress_value", placeholder=True),
                            style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;",
                        ),
                        _ui.input_slider("stress", None, min=0, max=100, value=55, step=1, width="100%"),
                        _ui.div(
                            _ui.span("0 - Ontspannen", class_="mt-caption mt-secondary"),
                            _ui.span("100 - Zeer gestresseerd", class_="mt-caption mt-secondary"),
                            style="display:flex; justify-content:space-between;",
                        ),
                        style="margin-bottom:24px;",
                    ),

                    # Uur
                    _ui.div(
                        _ui.div(
                            _ui.span("Tijdstip", class_="mt-body"),
                            _ui.output_text_verbatim("time_value", placeholder=True),
                            style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;",
                        ),
                        _ui.input_slider("hour", None, min=0, max=23, value=17, step=1, width="100%"),
                        _ui.div(
                            _ui.span("00:00", class_="mt-caption mt-secondary"),
                            _ui.span("23:00", class_="mt-caption mt-secondary"),
                            style="display:flex; justify-content:space-between;",
                        ),
                        style="margin-bottom:24px;",
                    ),

                    # Body battery
                    _ui.div(
                        _ui.div(
                            _ui.span("Body Battery", class_="mt-body"),
                            _ui.output_text_verbatim("battery_value", placeholder=True),
                            style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;",
                        ),
                        _ui.input_slider("battery", None, min=0, max=100, value=40, step=1, width="100%"),
                        _ui.div(
                            "Garmin Body Battery: 0 = volledig leeg - 100 = volledig uitgerust",
                            class_="mt-caption mt-secondary",
                        ),
                        style="margin-bottom:24px;",
                    ),

                    # Activiteitstoestand
                    _ui.div(
                        _ui.div("Activiteitstoestand", class_="mt-body", style="margin-bottom:10px;"),
                        _ui.output_ui("activity_pills_ui"),
                        style="margin-bottom:24px;",
                    ),

                    # Deelnemer
                    _ui.div(
                        _ui.div(
                            _ui.span("Deelnemer", class_="mt-body"),
                            _ui.span("(Onderzoeksmodus)", class_="mt-caption mt-secondary"),
                            style="display:flex; gap:8px; align-items:baseline; margin-bottom:8px;",
                        ),
                        _ui.input_select("participant", None, choices=PARTICIPANTS,
                                         selected="bosbes", width="200px"),
                    ),

                    style="flex:1; min-width:0; max-width:480px;",
                ),

                # Rechts - uitvoer
                _ui.div(
                    _ui.div("Aanbeveling", class_="mt-h2", style="margin-bottom:8px;"),
                    _ui.div(
                        "Gebaseerd op historische sessies (Bayesiaans MCMC-model, pre-berekend)",
                        class_="mt-caption mt-secondary",
                        style="margin-bottom:20px;",
                    ),
                    _ui.output_ui("rec_badge"),
                    _ui.div(
                        _ui.div(
                            _ui.span("Posterior-zekerheid", class_="mt-body mt-secondary"),
                            _ui.output_ui("confidence_pct"),
                            style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:8px;",
                        ),
                        _ui.output_ui("confidence_bar"),
                        style="margin:24px 0;",
                    ),
                    _ui.div(
                        _ui.div("Posterior per afspeellijsttype", class_="mt-caption mt-secondary",
                                style="margin-bottom:4px;"),
                        _ui.div("Pre-berekend per deelnemer - niet live bijgewerkt",
                                class_="mt-caption mt-secondary",
                                style="margin-bottom:8px; font-style:italic;"),
                        output_widget("posterior_chart"),
                    ),
                    _ui.p("Foutenbalken = 89% geloofwaardigheidsinterval.",
                          class_="mt-caption mt-secondary", style="margin-top:4px; margin-bottom:2px;"),
                    _ui.p("Brede intervallen wijzen op kleine steekproef.",
                          class_="mt-caption mt-secondary", style="margin-top:0;"),
                    _ui.output_ui("sample_size_note"),
                    _ui.output_ui("explanation_callout"),
                    _ui.div(
                        _ui.input_action_button("expand_calc", "Hoe is dit berekend? v",
                                                class_="mt-expand-trigger"),
                        _ui.output_ui("expanded_calc"),
                        style="margin-top:16px;",
                    ),
                    style="flex:1.2; min-width:0;",
                ),

                style="display:flex; gap:48px; flex-wrap:wrap;",
            ),
            class_="mt-section-card",
            style="margin:0 80px 64px;",
        ),
    )


# ---------------------------------------------------------------------------
# Module server
# ---------------------------------------------------------------------------

@module.server
def server(input, output, session, app_data: AppData):
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
    @render.text
    def stress_value():
        return str(input.stress())

    @output
    @render.text
    def time_value():
        return f"{input.hour():02d}:00"

    @output
    @render.text
    def battery_value():
        return str(input.battery())

    @output
    @render.ui
    def activity_pills_ui():
        return _activity_pills(activity())

    @reactive.Calc
    def baseline_deviation():
        exp, _ = expected_stress(app_data, input.participant(), input.hour())
        return None if exp is None else input.stress() - exp

    @reactive.Calc
    def recommendation():
        return best_playlist_for(app_data, input.participant())

    @output
    @render.ui
    def rec_badge():
        playlist, _ = recommendation()
        return _ui.div(
            _ui.div(_PLAYLIST_NL.get(playlist, playlist.upper()), class_="mt-h1"),
            _ui.div(_ISO_LABEL_NL.get(playlist, ""), class_="mt-body",
                    style="margin-top:4px;"),
            class_=f"mt-rec-badge {playlist.lower()}",
        )

    @output
    @render.ui
    def confidence_pct():
        _, pct = recommendation()
        return _ui.div(f"{pct}%", class_="mt-h1 mt-green")

    @output
    @render.ui
    def confidence_bar():
        _, pct = recommendation()
        return _ui.div(
            _ui.div(style=f"width:{pct}%;", class_="mt-progress-fill"),
            class_="mt-progress-track",
        )

    @output
    @render_widget
    def posterior_chart():
        recs = app_data.recommendations.get(input.participant(), {})
        return _posterior_chart(recs)

    @output
    @render.ui
    def sample_size_note():
        p   = input.participant()
        fm  = app_data.feature_matrix
        if fm is not None and not fm.empty and "participant" in fm.columns:
            n = int((fm["participant"] == p).sum())
        else:
            bio = app_data.session_biometrics.get(p, None)
            n = len(bio) if bio is not None and not bio.empty else 0
        if n > 0:
            return _ui.div(
                _ui.p(f"N={n} sessies voor {p.capitalize()}.",
                      class_="mt-caption mt-secondary",
                      style="margin:2px 0 0; font-style:italic;"),
                _ui.p("Posterior breedte neemt af naarmate meer sessies beschikbaar zijn.",
                      class_="mt-caption mt-secondary",
                      style="margin:0; font-style:italic;"),
            )
        return _ui.div()

    @output
    @render.ui
    def explanation_callout():
        playlist, pct = recommendation()
        hour  = input.hour()
        dev   = baseline_deviation()
        batt  = input.battery()
        act   = activity()
        p     = input.participant()

        dev_str = ""
        if dev is not None:
            sign = "+" if dev >= 0 else ""
            rel  = "boven" if dev >= 0 else "onder"
            dev_str = (
                f" Jouw stress is {sign}{dev:.0f} punten {rel} "
                f"jouw basislijn op {hour:02d}:00."
            )

        batt_str = ""
        if batt < 40:
            batt_str = f" Jouw body battery ({batt}%) wijst op vermoeidheid."
        elif batt > 70:
            batt_str = f" Jouw body battery ({batt}%) is goed opgeladen."

        nl_pl = {"Calm": "Kalm", "Neutral": "Neutraal", "Energy": "Energiek"}.get(playlist, playlist)
        text = (
            f"Op {hour:02d}:00 met activiteitstoestand '{act}' wordt "
            f"{nl_pl} aanbevolen "
            f"({pct}% posterior-kans voor {p.capitalize()}).{dev_str}{batt_str}"
        )
        return _ui.div(text, class_=f"mt-callout {playlist.lower()}", style="margin-top:16px;")

    @output
    @render.ui
    def expanded_calc():
        if not show_calc():
            return _ui.div(style="height:1px; overflow:hidden;")
        dev    = baseline_deviation()
        hour   = input.hour()
        stress = input.stress()
        p      = input.participant()
        exp, _ = expected_stress(app_data, p, hour)
        exp_str   = f"{exp:.0f}" if exp is not None else "geen basislijn"
        dev_str   = f"{dev:+.0f}" if dev is not None else "n.v.t."
        sign_word = "boven" if (dev or 0) >= 0 else "onder"

        return _ui.div(
            _ui.div(
                _ui.div("Berekening afwijking:", class_="mt-caption mt-secondary",
                        style="margin-bottom:6px;"),
                _ui.div(
                    f"Jouw stress: {stress}   "
                    f"Verwacht op {hour:02d}:00 (historische basislijn): {exp_str}",
                    class_="mt-code-block",
                    style="margin-bottom:6px;",
                ),
                _ui.div(
                    f"afwijking = {stress} - {exp_str} = {dev_str} punten {sign_word} basislijn",
                    class_="mt-code-block",
                ),
            ),
            _ui.p(
                f"Het Bayesiaanse model gebruikt de historische sessie-uitkomsten van "
                f"{p.capitalize()} om posterior-kansen te schatten voor elk type via "
                f"MCMC (2.000 samples). Deze posteriors zijn vast -- ze worden niet live bijgewerkt. "
                f"De afwijkingsscore legt uit waarom de aanbeveling nu logisch is.",
                class_="mt-caption mt-secondary",
                style="margin-top:12px;",
            ),
            class_="mt-expand-content",
        )
