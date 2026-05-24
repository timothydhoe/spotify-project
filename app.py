"""MoodTune — Shiny for Python entrypoint."""
from pathlib import Path

from shiny import App, reactive, render, ui

from modules import circadian, home, model, pipeline, recommendation, results, science, session_replay
from utils.data_loader import APP_DATA

app_ui = ui.page_navbar(
    ui.nav_panel("Wetenschap", science.ui("science")),
    ui.nav_panel("Pipeline",   pipeline.ui("pipeline")),
    ui.nav_panel("Circadiaan", circadian.ui("circadian")),
    ui.nav_panel("Afspelen",   session_replay.ui("replay")),
    ui.nav_panel("Resultaten", results.ui("results")),
    ui.nav_panel("Model",      model.ui("model")),
    ui.nav_panel("Aanbevelen", recommendation.ui("rec")),
    ui.nav_panel("Home",       home.ui("home")),
    title="MoodTune",
    header=ui.tags.head(
        ui.tags.link(rel="icon", type="image/svg+xml", href="favicon.svg"),
        ui.tags.link(rel="stylesheet", href="styles.css"),
        ui.busy_indicators.use(spinners=True, pulse=True),
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
    now_playing = reactive.Value(None)

    home.server("home", app_data=APP_DATA, now_playing=now_playing)
    science.server("science")
    pipeline.server("pipeline", app_data=APP_DATA)
    circadian.server("circadian", app_data=APP_DATA)
    recommendation.server("rec", app_data=APP_DATA)
    session_replay.server("replay", app_data=APP_DATA)
    results.server("results", app_data=APP_DATA)
    model.server("model", app_data=APP_DATA)

    @output
    @render.ui
    def now_playing_title():
        state = now_playing()
        if state is None:
            return ui.div("Selecteer een afspeellijst", class_="now-playing-title")
        playlist_nl = {"Calm": "Kalme afspeellijst", "Neutral": "Neutrale afspeellijst",
                       "Energy": "Energieke afspeellijst"}.get(state["playlist_type"], state["playlist_type"])
        return ui.div(
            f"{playlist_nl} — {state['participant'].capitalize()}",
            class_="now-playing-title",
        )


app = App(app_ui, server, static_assets=Path(__file__).parent / "www")
