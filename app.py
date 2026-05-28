"""MoodTune — Shiny for Python entrypoint."""
from pathlib import Path

from shiny import App, reactive, render, ui

from modules import circadian, home, model, pipeline, recommendation, results, science, session_replay
from utils.data_loader import APP_DATA, PARTICIPANTS

_DATA_LEVEL = {
    "bosbes":      ("vol",          "Volledige biometrische data"),
    "kokosnoot":   ("vol",          "Volledige biometrische data"),
    "limoen":      ("gedeeltelijk", "Gedeeltelijke data (geen stresssensor)"),
    "peer":        ("gedeeltelijk", "Gedeeltelijke data (geen biometrie)"),
    "kiwi":        ("geen",         "Alleen stemming-check-ins"),
    "watermeloen": ("geen",         "Alleen stemming-check-ins"),
}

app_ui = ui.page_navbar(
    ui.nav_panel("Home", home.ui("home")),
    ui.nav_panel("Jouw Profiel",
        ui.navset_pill(
            ui.nav_panel("Resultaten",        results.ui("results")),
            ui.nav_panel("Sessie-replay",     session_replay.ui("replay")),
            ui.nav_panel("Circadiaans ritme", circadian.ui("circadian")),
        ),
    ),
    ui.nav_panel("Aanbevelingen", recommendation.ui("rec")),
    ui.nav_panel("Achtergrond",
        ui.navset_pill(
            ui.nav_panel("Wetenschap",   science.ui("science")),
            ui.nav_panel("Model & Data", model.ui("model")),
            ui.nav_panel("Pipeline",     pipeline.ui("pipeline")),
        ),
    ),
    title="MoodTune",
    header=ui.div(
        ui.tags.head(
            ui.tags.link(rel="icon", type="image/svg+xml", href="favicon.svg"),
            ui.tags.link(rel="stylesheet", href="styles.css"),
            ui.busy_indicators.use(spinners=True, pulse=True),
        ),
        ui.output_ui("global_participant_bar"),
    ),
    footer=ui.div(
        ui.div(
            ui.div(
                ui.div(class_="now-playing-art"),
                ui.div(
                    ui.output_ui("now_playing_title"),
                    ui.div("MoodTune", class_="now-playing-artist"),
                    style="min-width: 0;",
                ),
                class_="now-playing-track",
            ),
            ui.div(
                ui.div("- -", class_="now-playing-empty"),
                class_="now-playing-controls",
            ),
            ui.div(),
            class_="now-playing-bar",
        ),
    ),
)


def server(input, output, session):
    selected_participant = reactive.Value("bosbes")
    now_playing          = reactive.Value(None)

    for _p in PARTICIPANTS:
        def _make_obs(participant=_p):
            @reactive.Effect
            @reactive.event(input[f"g_pill_{participant}"])
            def _():
                selected_participant.set(participant)
        _make_obs()

    @output
    @render.ui
    def global_participant_bar():
        curr = selected_participant()
        _dot = {"vol": "●", "gedeeltelijk": "◑", "geen": "○"}
        pills = []
        for p in PARTICIPANTS:
            lvl, tip = _DATA_LEVEL.get(p, ("geen", ""))
            cls = "pill-btn pill-btn-sm" + (" active" if p == curr else "")
            pills.append(
                ui.input_action_button(f"g_pill_{p}", f"{p.capitalize()} {_dot[lvl]}",
                                       class_=cls, title=tip)
            )
        return ui.div(
            ui.span("Deelnemer:",
                    style="font-size:11px; font-weight:500; color:var(--text-secondary); "
                          "text-transform:uppercase; letter-spacing:0.08em; margin-right:4px; white-space:nowrap;"),
            *pills,
            ui.HTML(
                '<span style="font-size:10px; color:var(--text-tertiary); margin-left:4px; white-space:nowrap;">'
                "● vol &nbsp;◑ gedeeltelijk &nbsp;○ geen biometrie"
                ' &nbsp;<span title="'
                "● Vol — volledige Garmin biometrie (stress + hartslag per minuut)&#10;"
                "◑ Gedeeltelijk — gedeeltelijke data (ontbrekende sensor of beperkte export)&#10;"
                "○ Geen — alleen stemming-check-ins, geen wearable"
                '" style="cursor:help; font-style:normal;">ⓘ</span>'
                "</span>"
            ),
            style="display:flex; flex-wrap:wrap; align-items:center; gap:6px; "
                  "padding:8px var(--page-margin, 80px); "
                  "border-bottom:1px solid var(--border-default);",
        )

    home.server("home",       app_data=APP_DATA, now_playing=now_playing,
                              selected_participant=selected_participant)
    science.server("science")
    pipeline.server("pipeline",   app_data=APP_DATA)
    circadian.server("circadian", app_data=APP_DATA, selected_participant=selected_participant)
    recommendation.server("rec",  app_data=APP_DATA, selected_participant=selected_participant)
    session_replay.server("replay", app_data=APP_DATA, selected_participant=selected_participant)
    results.server("results",   app_data=APP_DATA, selected_participant=selected_participant)
    model.server("model",       app_data=APP_DATA)

    @output
    @render.ui
    def now_playing_title():
        state = now_playing()
        if state is None:
            return ui.div("Selecteer een afspeellijst", class_="now-playing-title")
        playlist_nl = {
            "Calm":    "Kalme afspeellijst",
            "Neutral": "Neutrale afspeellijst",
            "Energy":  "Energieke afspeellijst",
        }.get(state["playlist_type"], state["playlist_type"])
        return ui.div(
            f"{playlist_nl} — {state['participant'].capitalize()}",
            class_="now-playing-title",
        )


app = App(app_ui, server, static_assets=Path(__file__).parent / "www")
