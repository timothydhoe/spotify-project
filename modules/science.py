"""Pagina 2 -- Wetenschap: ISO-principe, BPM-grafieken, audiokenmerken."""
import numpy as np
import plotly.graph_objects as go
from shiny import module, reactive, render, ui as _ui
from shinywidgets import output_widget, render_widget

from utils.chart_helpers import GRID_COLOR, PLAYLIST_COLORS, TEXT_SECONDARY, dark_layout


_ISO_FASEN = [
    (0,    7.5,  "Ontmoeting",   "rgba(59,130,246,0.06)"),
    (7.5,  15,   "De-escalatie", "rgba(59,130,246,0.10)"),
    (15,   22.5, "Regulatie",    "rgba(59,130,246,0.14)"),
    (22.5, 30,   "Landing",      "rgba(59,130,246,0.18)"),
]


def _bpm_chart(calm_max: int = 95, energy_min: int = 120) -> go.Figure:
    x = np.linspace(0, 30, 200)

    calm_start = float(calm_max)
    calm_end   = max(45.0, calm_start - 45)
    calm   = calm_start - (calm_start - calm_end) * (x / 30)
    neutral = np.full_like(x, (calm_max + energy_min) / 2)
    energy  = float(energy_min) + 45 * (x / 30)

    fig = go.Figure()

    # ISO-faseregio's op de Calm-lijn
    for x0, x1, fase, fill in _ISO_FASEN:
        fig.add_vrect(
            x0=x0, x1=x1,
            fillcolor=fill,
            line_width=0,
            annotation_text=fase,
            annotation_position="top left",
            annotation_font_size=11,
            annotation_font_color=TEXT_SECONDARY,
        )

    fig.add_trace(go.Scatter(
        x=x, y=calm,
        name="Kalm",
        line=dict(color=PLAYLIST_COLORS["Calm"], width=2.5),
        hovertemplate="Kalm - min %{x:.0f}: %{y:.0f} BPM<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=neutral,
        name="Neutraal",
        line=dict(color=PLAYLIST_COLORS["Neutral"], width=2.5, dash="dot"),
        hovertemplate="Neutraal - min %{x:.0f}: %{y:.0f} BPM<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=energy,
        name="Energiek",
        line=dict(color=PLAYLIST_COLORS["Energy"], width=2.5),
        hovertemplate="Energiek - min %{x:.0f}: %{y:.0f} BPM<extra></extra>",
    ))

    # Tempodrempellijnen
    fig.add_hline(y=calm_max,   line_dash="dash", line_color=TEXT_SECONDARY,
                  line_width=1, annotation_text=f"Kalm max: {calm_max} BPM",
                  annotation_position="right", annotation_font_size=10,
                  annotation_font_color=TEXT_SECONDARY)
    fig.add_hline(y=energy_min, line_dash="dash", line_color=TEXT_SECONDARY,
                  line_width=1, annotation_text=f"Energiek min: {energy_min} BPM",
                  annotation_position="right", annotation_font_size=10,
                  annotation_font_color=TEXT_SECONDARY)

    fig.update_layout(**dark_layout(
        xaxis=dict(title="Minuten", range=[0, 30], gridcolor=GRID_COLOR),
        yaxis=dict(title="BPM", range=[35, 185], gridcolor=GRID_COLOR),
        height=380,
        legend=dict(orientation="h", y=-0.18),
    ))
    return fig


def _feature_card(name: str, desc: str, calm: str = "", neutral: str = "", energy: str = "") -> _ui.Tag:
    badges = []
    if calm:
        badges.append(_ui.span(f"Kalm: {calm}", class_="mt-badge mt-badge-calm", style="margin-right:4px;"))
    if neutral:
        badges.append(_ui.span(f"Neutraal: {neutral}", class_="mt-badge mt-badge-neutral", style="margin-right:4px;"))
    if energy:
        badges.append(_ui.span(f"Energiek: {energy}", class_="mt-badge mt-badge-energy"))
    return _ui.div(
        _ui.div(name, class_="mt-h3", style="margin-bottom:6px;"),
        _ui.div(desc, class_="mt-caption mt-secondary", style="margin-bottom:8px;"),
        _ui.div(*badges) if badges else _ui.div(),
        class_="mt-card-elevated",
        style="padding:20px;",
    )



# ---------------------------------------------------------------------------
# Module UI
# ---------------------------------------------------------------------------

@module.ui
def ui():
    return _ui.div(
        # Hero
        _ui.div(
            _ui.div("De Wetenschap Achter MoodTune", class_="mt-h1"),
            _ui.p(
                "Het ISO-principe uit muziektherapie - spring niet direct naar de doelstaat, "
                "maar begeleid de luisteraar er geleidelijk naartoe.",
                class_="mt-body mt-secondary",
                style="max-width:600px; margin-top:8px;",
            ),
            style="text-align:center; padding:64px 80px 48px;",
        ),

        # ISO-uitlegger - 2 kolommen
        _ui.div(
            _ui.div(
                _ui.div(
                    _ui.div("Het ISO-principe", class_="mt-h2", style="margin-bottom:16px;"),
                    _ui.p(
                        "Muziektherapie gebruikt geleidelijke BPM- en energie-afstemming om het "
                        "arousal-niveau van de luisteraar van de huidige toestand naar de doeltoestand "
                        "te leiden. In plaats van direct rustige muziek te spelen als iemand gestresseerd is, "
                        "begint het ISO-principe waar je nu bent en brengt je stap voor stap omlaag - "
                        "zoals een thermostaat geleidelijk regelt, niet bruusk schakelt.",
                        class_="mt-body mt-secondary",
                        style="margin-bottom:24px;",
                    ),
                    _ui.div(
                        _ui.em(
                            '"Zelfgekozen muziek is significant effectiever bij emotieregulatie '
                            'dan onbekende nummers."'
                        ),
                        class_="mt-callout",
                    ),
                    style="flex:1;",
                ),
                _ui.div(
                    # Interactieve parametersliders
                    _ui.div(
                        _ui.div(
                            _ui.span("Kalm max. BPM:", class_="mt-body mt-secondary"),
                            _ui.output_text_verbatim("calm_max_val", placeholder=True),
                            style="display:flex; justify-content:space-between; margin-bottom:4px;",
                        ),
                        _ui.input_slider("calm_max", None, min=70, max=115, value=95, step=5, width="100%"),
                        style="margin-bottom:12px;",
                    ),
                    _ui.div(
                        _ui.div(
                            _ui.span("Energiek min. BPM:", class_="mt-body mt-secondary"),
                            _ui.output_text_verbatim("energy_min_val", placeholder=True),
                            style="display:flex; justify-content:space-between; margin-bottom:4px;",
                        ),
                        _ui.input_slider("energy_min", None, min=110, max=145, value=120, step=5, width="100%"),
                        style="margin-bottom:16px;",
                    ),
                    output_widget("bpm_chart"),
                    _ui.output_ui("bpm_caption"),
                    style="flex:1.2;",
                ),
                style="display:flex; gap:48px; align-items:flex-start;",
            ),
            class_="mt-section",
        ),

        # ISO-fasen uitlegger
        _ui.div(
            _ui.div(
                _ui.div("De 4 Fasen van een Kalme Afspeellijst", class_="mt-h2",
                        style="text-align:center; margin-bottom:24px;"),
                _ui.div(
                    _ui.div(
                        _ui.div("Ontmoeting", class_="mt-h3", style="color:var(--calm-color); margin-bottom:2px;"),
                        _ui.div("Isochronous Meeting", class_="mt-caption", style="color:var(--text-tertiary); margin-bottom:6px;"),
                        _ui.div("0 - 7,5 min", class_="mt-eyebrow", style="font-size:10px; margin-bottom:8px;"),
                        _ui.p("Start bij je huidige stressniveau. Muziek matcht je huidige arousal.",
                              class_="mt-caption mt-secondary"),
                        class_="mt-card-elevated", style="flex:1; padding:20px;",
                    ),
                    _ui.div("->", class_="mt-flow-arrow"),
                    _ui.div(
                        _ui.div("De-escalatie", class_="mt-h3", style="color:var(--calm-color); margin-bottom:2px;"),
                        _ui.div("De-escalation", class_="mt-caption", style="color:var(--text-tertiary); margin-bottom:6px;"),
                        _ui.div("7,5 - 15 min", class_="mt-eyebrow", style="font-size:10px; margin-bottom:8px;"),
                        _ui.p("BPM begint te dalen. Energie neemt geleidelijk af.",
                              class_="mt-caption mt-secondary"),
                        class_="mt-card-elevated", style="flex:1; padding:20px;",
                    ),
                    _ui.div("->", class_="mt-flow-arrow"),
                    _ui.div(
                        _ui.div("Regulatie", class_="mt-h3", style="color:var(--calm-color); margin-bottom:2px;"),
                        _ui.div("Regulation", class_="mt-caption", style="color:var(--text-tertiary); margin-bottom:6px;"),
                        _ui.div("15 - 22,5 min", class_="mt-eyebrow", style="font-size:10px; margin-bottom:8px;"),
                        _ui.p("Stressrespons stabiliseert. Nerveus systeem begint te herstellen.",
                              class_="mt-caption mt-secondary"),
                        class_="mt-card-elevated", style="flex:1; padding:20px;",
                    ),
                    _ui.div("->", class_="mt-flow-arrow"),
                    _ui.div(
                        _ui.div("Landing", class_="mt-h3", style="color:var(--calm-color); margin-bottom:2px;"),
                        _ui.div("Arrival / Rest", class_="mt-caption", style="color:var(--text-tertiary); margin-bottom:6px;"),
                        _ui.div("22,5 - 30 min", class_="mt-eyebrow", style="font-size:10px; margin-bottom:8px;"),
                        _ui.p("Doeltoestand bereikt. Lage BPM, hoge akoestisch, lage energie.",
                              class_="mt-caption mt-secondary"),
                        class_="mt-card-elevated", style="flex:1; padding:20px;",
                    ),
                    style="display:flex; gap:12px; align-items:center;",
                ),
                class_="mt-section-card",
            ),
            class_="mt-section",
        ),

        # Audiokenmerken
        _ui.div(
            _ui.div(
                _ui.div("6 Spotify-audiokenmerken", class_="mt-h2",
                        style="text-align:center; margin-bottom:32px;"),
                _ui.div(
                    _feature_card("Tempo (BPM)",          "Primair filter - bepaalt de afspeellijstcategorie",
                                  calm="50-95", neutral="95-115", energy="120-180"),
                    _feature_card("Energie (0-1)",         "Perceptuele intensiteit - hoe energiek het aanvoelt",
                                  calm="< 0.9", neutral="0.2-0.8", energy="> 0.7"),
                    _feature_card("Valentie (0-1)",        "Muzikale positiviteit - minimumdrempel op energieke lijst",
                                  energy="> 0.3"),
                    _feature_card("Dansbaarheid (0-1)",    "Ritmische regelmaat - versterkt energieke lijst",
                                  energy="> 0.5"),
                    _feature_card("Akoestiek (0-1)",       "Akoestisch vs elektronisch - instelbaar voor kalme lijst",
                                  calm="bij voorkeur hoog"),
                    _feature_card("Luidheid (dB)",         "Volumedynamiek - min/max per afspeellijsttype",
                                  calm="> -20 dB", energy="> -12 dB"),
                    style="display:grid; grid-template-columns:repeat(3,1fr); gap:16px;",
                ),
                class_="mt-section-card",
            ),
            class_="mt-section",
        ),

    )


# ---------------------------------------------------------------------------
# Module server
# ---------------------------------------------------------------------------

@module.server
def server(input, output, session):
    @render.text
    def calm_max_val():
        return str(input.calm_max())

    @render.text
    def energy_min_val():
        return str(input.energy_min())

    @render_widget
    def bpm_chart():
        return _bpm_chart(
            calm_max=input.calm_max(),
            energy_min=input.energy_min(),
        )

    @render.ui
    def bpm_caption():
        cm = input.calm_max()
        em = input.energy_min()
        calm_end = max(45, cm - 45)
        energy_end = em + 45
        return _ui.div(
            f"Kalm daalt van ~{cm} → ~{calm_end} BPM. "
            f"Neutraal stabiel. Energiek stijgt van ~{em} → ~{energy_end} BPM "
            "over 30 minuten. Klik op de faselabels voor uitleg.",
            class_="mt-caption mt-secondary",
            style="margin-top:8px; text-align:center;",
        )
