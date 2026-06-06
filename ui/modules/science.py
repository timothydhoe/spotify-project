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


_FEATURE_TOOLTIPS: dict[str, str] = {
    "Tempo (BPM)":            "BPM bepaalt het 'tempo' van de ISO-overgang. Kalm start hoog en daalt; energiek start laag en stijgt.",
    "Energie (0-1)":          "Perceptuele intensiteit: hoe energiek klinkt het nummer? Hoge energie = pompende beats, lage energie = stille akoestiek.",
    "Valentie (0-1)":         "Muzikale positiviteit: 0.0 = somber/melancholisch, 1.0 = vrolijk/euforisch. Energieke lijst heeft een minimumdrempel.",
    "Dansbaarheid (0-1)":     "Ritmische regelmaat en beat-sterkte. Hoge dansbaarheid helpt bij motorische activatie (energieke lijst).",
    "Akoestiek (0-1)":        "Hoe 'akoestisch' klinkt het nummer? Hoge waarden = gitaar/piano zonder effecten. Rustgevend bij stress door warmere frequenties.",
    "Luidheid (dB)":          "Gemiddeld volume. Kalme lijst heeft een lager maximum; energieke lijst een hoger minimum om activatie te ondersteunen.",
    "Instrumentalheid (0-1)": "Hoe weinig gezongen tekst er is. Hoge instrumentalheid = geen vocalen. Nuttig als tekst afleidend is bij concentratie.",
    "Levendigheid (0-1)":     "Kans dat het een live-opname is. Hoge waarden duiden op publieksgeluiden — doorgaans uitgefilterd voor een consistente luisterervaring.",
    "Spraakheid (0-1)":       "Aanwezigheid van gesproken woord. Boven 0.66 = waarschijnlijk podcast of spoken word, geen muziek.",
}


def _feature_card(name: str, desc: str, calm: str = "", neutral: str = "", energy: str = "") -> _ui.Tag:
    badges = []
    if calm:
        badges.append(_ui.span(f"Kalm: {calm}", class_="mt-badge mt-badge-calm", style="margin-right:4px;"))
    if neutral:
        badges.append(_ui.span(f"Neutraal: {neutral}", class_="mt-badge mt-badge-neutral", style="margin-right:4px;"))
    if energy:
        badges.append(_ui.span(f"Energiek: {energy}", class_="mt-badge mt-badge-energy"))
    tooltip = _FEATURE_TOOLTIPS.get(name, "")
    return _ui.div(
        _ui.div(name, class_="mt-h3", style="margin-bottom:6px;"),
        _ui.div(desc, class_="mt-caption mt-secondary", style="margin-bottom:8px;"),
        _ui.div(*badges) if badges else _ui.div(),
        _ui.div(tooltip, class_="mt-caption mt-tertiary",
                style="margin-top:8px; font-style:italic;") if tooltip else _ui.div(),
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
                        _ui.div(
                            "— Thoma MV et al. (2013). The effect of music on the human stress response. ",
                            _ui.a("PLOS ONE 8(8):e70156",
                                  href="https://doi.org/10.1371/journal.pone.0070156",
                                  target="_blank",
                                  style="color:var(--accent); text-decoration:underline;"),
                            style="font-size:11px; color:var(--text-tertiary); margin-top:8px; font-style:normal;",
                        ),
                        class_="mt-callout",
                    ),
                    _ui.HTML(
                        '<details class="mt-details" style="margin-top:12px;">'
                        '<summary>ISO-principe oorsprong (Heiderscheit &amp; Madson, 2015)</summary>'
                        '<div class="mt-details-body" style="font-size:11px; color:var(--text-tertiary);">'
                        'Heiderscheit A, Madson A (2015). Use of the iso-principle as a central method '
                        'in mood management: a music psychotherapy clinical case study. '
                        '<em>Music Therapy Perspectives</em>, 33(1), 45–52. '
                        'Het ISO-principe is gebaseerd op het idee dat muziek die aansluit bij de '
                        'huidige emotionele toestand effectiever is als startpunt voor transitie dan '
                        'muziek die direct de doelstaat uitbeeldt.'
                        '</div>'
                        '</details>'
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

        # ISO-fasen uitlegger (interactief)
        _ui.div(
            _ui.div(
                _ui.div("De 4 Fasen van een Kalme Afspeellijst", class_="mt-h2",
                        style="text-align:center; margin-bottom:8px;"),
                _ui.div("Klik op een fase voor meer uitleg", class_="mt-caption mt-secondary",
                        style="text-align:center; margin-bottom:20px;"),
                _ui.div(
                    _ui.div(
                        _ui.input_action_button("iso_fase_1", "", class_="mt-iso-fase-btn"),
                        _ui.div(
                            _ui.div("Ontmoeting", class_="mt-h3", style="color:var(--calm-color); margin-bottom:2px;"),
                            _ui.div("Isochronous Meeting", class_="mt-caption", style="color:var(--text-tertiary); margin-bottom:6px;"),
                            _ui.div("0 – 7,5 min · ~80-95 BPM", class_="mt-eyebrow", style="font-size:10px; margin-bottom:8px;"),
                            _ui.p("Muziek matcht je huidige arousal.", class_="mt-caption mt-secondary"),
                        ),
                        class_="mt-card-elevated mt-iso-fase-card",
                        style="flex:1; padding:20px; cursor:pointer; position:relative;",
                        id="iso_card_1",
                    ),
                    _ui.div("→", class_="mt-flow-arrow"),
                    _ui.div(
                        _ui.input_action_button("iso_fase_2", "", class_="mt-iso-fase-btn"),
                        _ui.div(
                            _ui.div("De-escalatie", class_="mt-h3", style="color:var(--calm-color); margin-bottom:2px;"),
                            _ui.div("De-escalation", class_="mt-caption", style="color:var(--text-tertiary); margin-bottom:6px;"),
                            _ui.div("7,5 – 15 min · ~70-80 BPM", class_="mt-eyebrow", style="font-size:10px; margin-bottom:8px;"),
                            _ui.p("BPM daalt geleidelijk. Energie neemt af.", class_="mt-caption mt-secondary"),
                        ),
                        class_="mt-card-elevated mt-iso-fase-card",
                        style="flex:1; padding:20px; cursor:pointer; position:relative;",
                        id="iso_card_2",
                    ),
                    _ui.div("→", class_="mt-flow-arrow"),
                    _ui.div(
                        _ui.input_action_button("iso_fase_3", "", class_="mt-iso-fase-btn"),
                        _ui.div(
                            _ui.div("Regulatie", class_="mt-h3", style="color:var(--calm-color); margin-bottom:2px;"),
                            _ui.div("Regulation", class_="mt-caption", style="color:var(--text-tertiary); margin-bottom:6px;"),
                            _ui.div("15 – 22,5 min · ~60-70 BPM", class_="mt-eyebrow", style="font-size:10px; margin-bottom:8px;"),
                            _ui.p("Stressrespons stabiliseert. Zenuwstelsel herstelt.", class_="mt-caption mt-secondary"),
                        ),
                        class_="mt-card-elevated mt-iso-fase-card",
                        style="flex:1; padding:20px; cursor:pointer; position:relative;",
                        id="iso_card_3",
                    ),
                    _ui.div("→", class_="mt-flow-arrow"),
                    _ui.div(
                        _ui.input_action_button("iso_fase_4", "", class_="mt-iso-fase-btn"),
                        _ui.div(
                            _ui.div("Landing", class_="mt-h3", style="color:var(--calm-color); margin-bottom:2px;"),
                            _ui.div("Arrival / Rest", class_="mt-caption", style="color:var(--text-tertiary); margin-bottom:6px;"),
                            _ui.div("22,5 – 30 min · ~50-60 BPM", class_="mt-eyebrow", style="font-size:10px; margin-bottom:8px;"),
                            _ui.p("Doeltoestand bereikt. Lage BPM, hoge akoestiek.", class_="mt-caption mt-secondary"),
                        ),
                        class_="mt-card-elevated mt-iso-fase-card",
                        style="flex:1; padding:20px; cursor:pointer; position:relative;",
                        id="iso_card_4",
                    ),
                    style="display:flex; gap:12px; align-items:flex-start;",
                ),
                _ui.output_ui("iso_fase_detail"),
                class_="mt-section-card",
            ),
            class_="mt-section",
        ),

        # Audiokenmerken
        _ui.div(
            _ui.div(
                _ui.div("9 Spotify-audiokenmerken", class_="mt-h2",
                        style="text-align:center; margin-bottom:8px;"),
                _ui.div(
                    "Gebaseerd op 2.269 nummers van 6 deelnemers",
                    class_="mt-caption mt-secondary",
                    style="text-align:center; margin-bottom:24px;",
                ),
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
                    _feature_card("Instrumentalheid (0-1)", "Vocaal vs. instrumentaal — hoe dichter bij 1, hoe minder gezongen tekst",
                                  calm="verzameld"),
                    _feature_card("Levendigheid (0-1)",    "Studio vs. live-opname — hoge waarden duiden op publieksgeluiden",
                                  calm="verzameld"),
                    _feature_card("Spraakheid (0-1)",      "Aanwezigheid van gesproken woord — podcasts scoren hoog, muziek laag",
                                  calm="verzameld"),
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

_ISO_FASE_DETAILS = {
    1: {
        "title":   "Ontmoeting — Isochronous Meeting",
        "timing":  "0 – 7,5 minuten · ~80-95 BPM",
        "body": (
            "De eerste fase van het ISO-principe begint waar de luisteraar zich nu bevindt. "
            "Als iemand gestresseerd is, begint de afspeellijst met muziek die dat stressniveau weerspiegelt — "
            "niet met rustige muziek. Dit lijkt contra-intuïtief, maar direct rustige muziek bij een gespannen "
            "persoon werkt als een thermostaat die bruusk schakelt: het zenuwstelsel kan de overgang niet volgen. "
            "Door te beginnen bij de huidige staat creëer je een emotionele 'handdruk'."
        ),
        "bpm_range": "80-95 BPM",
        "kenmerken": "Hoge energie (0.6-0.8), gemiddelde akoestiek, hogere dansbaarheid",
    },
    2: {
        "title":   "De-escalatie — Gradual De-escalation",
        "timing":  "7,5 – 15 minuten · ~70-80 BPM",
        "body": (
            "Het BPM daalt geleidelijk. De hersenen volgen muzikale tempo-cues via entrainment: "
            "hartslag en ademhaling synchroniseren met het ritme (Thoma et al., 2013). "
            "De energieniveau van de nummers neemt af, akoestiek neemt toe. "
            "Sympathisch zenuwstelsel begint de-activering."
        ),
        "bpm_range": "70-80 BPM",
        "kenmerken": "Afnemende energie (0.4-0.6), stijgende akoestiek, rustigere beats",
    },
    3: {
        "title":   "Regulatie — Nervous System Regulation",
        "timing":  "15 – 22,5 minuten · ~60-70 BPM",
        "body": (
            "De stressrespons stabiliseert. Cortisol daalt, parasympathisch zenuwstelsel neemt het over. "
            "De muziek is nu duidelijk rustiger maar nog niet absent — het onderhoud van de ontspanning "
            "vereist continue auditieve begeleiding. Nummers in deze fase hebben hoge akoestiek "
            "(>0.5), lage energie (<0.4) en een tragere dansbaarheid."
        ),
        "bpm_range": "60-70 BPM",
        "kenmerken": "Lage energie (0.2-0.4), hoge akoestiek (>0.5), lagere valentie",
    },
    4: {
        "title":   "Landing — Arrival at Target State",
        "timing":  "22,5 – 30 minuten · ~50-60 BPM",
        "body": (
            "De doeltoestand is bereikt. BPM is op het laagste punt van de playlist (~50-60 BPM), "
            "vergelijkbaar met de rustende hartslag. Muziek met veel akoestiek en lage energie "
            "ondersteunt de voortgezette ontspanning. De overgang is compleet: van stress naar rust "
            "in vier geleidelijke stappen."
        ),
        "bpm_range": "50-60 BPM",
        "kenmerken": "Minimale energie (<0.25), maximale akoestiek, lage luidheid",
    },
}


@module.server
def server(input, output, session):
    selected_fase = reactive.Value(None)

    for _i in range(1, 5):
        def _make_obs(fase=_i):
            @reactive.Effect
            @reactive.event(input[f"iso_fase_{fase}"])
            def _():
                if selected_fase() == fase:
                    selected_fase.set(None)
                else:
                    selected_fase.set(fase)
        _make_obs()

    @render.ui
    def iso_fase_detail():
        fase = selected_fase()
        if fase is None:
            return _ui.div()
        detail = _ISO_FASE_DETAILS.get(fase, {})
        return _ui.div(
            _ui.div(
                _ui.div(detail.get("title", ""), class_="mt-h3", style="margin-bottom:6px;"),
                _ui.div(detail.get("timing", ""), class_="mt-caption mt-secondary",
                        style="margin-bottom:10px; font-weight:600;"),
                _ui.p(detail.get("body", ""), class_="mt-body mt-secondary",
                      style="margin-bottom:8px;"),
                _ui.div(
                    _ui.span("BPM-bereik: ", style="font-weight:600; color:var(--text-secondary);"),
                    _ui.span(detail.get("bpm_range", ""), class_="mt-caption"),
                    _ui.span("  |  Kenmerken: ", style="font-weight:600; color:var(--text-secondary); margin-left:8px;"),
                    _ui.span(detail.get("kenmerken", ""), class_="mt-caption mt-secondary"),
                    style="font-size:12px;",
                ),
            ),
            class_="mt-callout calm",
            style="margin-top:16px;",
        )

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
            _ui.div(
                "Drie afspeellijsten tonen het ISO-principe: elk begint bij de huidige toestand "
                "en beweegt geleidelijk naar het doelgevoel.",
                class_="mt-caption",
                style="margin-bottom:4px;",
            ),
            _ui.div(
                f"Kalm daalt van ~{cm} → ~{calm_end} BPM · "
                f"Neutraal stabiel · "
                f"Energiek stijgt van ~{em} → ~{energy_end} BPM over 30 minuten.",
                class_="mt-caption mt-secondary",
            ),
            _ui.div(
                "ISO-fasen zijn theoretisch — werkelijke grenzen variëren per afspeellijst en deelnemer.",
                class_="mt-caption",
                style="margin-top:4px; font-style:italic; color:var(--text-tertiary);",
            ),
            style="margin-top:8px; text-align:center;",
        )
