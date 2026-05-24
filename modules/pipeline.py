"""Pagina -- Pipeline: visuele doorloop van de datapipeline."""
import json
from pathlib import Path

import pandas as pd
from shiny import module, reactive, render, ui as _ui

from utils.chart_helpers import TEXT_SECONDARY
from utils.data_loader import AppData

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"

# ---------------------------------------------------------------------------
# Stap-definities
# ---------------------------------------------------------------------------

_STEPS = [
    {
        "id": "exportify",
        "label": "Exportify CSV",
        "icon": "🎵",
        "track": "muziek",
        "desc": (
            "Elke deelnemer exporteert zijn/haar volledige Spotify-bibliotheek via "
            "Exportify. Per nummer worden audiokenmerken opgehaald via de Spotify "
            "Audio Features API: tempo, energy, valence, acousticness, danceability, "
            "loudness en meer."
        ),
        "data_label": "Voorbeeld: gecombineerde Exportify-bibliotheek (bosbes)",
        "data_fn": "_preview_source",
    },
    {
        "id": "prepare",
        "label": "prepare.py",
        "icon": "🔧",
        "track": "muziek",
        "desc": (
            "Combineert meerdere Exportify-bestanden per deelnemer, verwijdert "
            "duplicaten op basis van Spotify-URI en normaliseert kolomnamen. "
            "Output: een schone bibliotheek-CSV klaar voor filtering."
        ),
        "data_label": "Geen live preview -- tussenresultaat in geheugen.",
        "data_fn": None,
    },
    {
        "id": "generate",
        "label": "generate.py",
        "icon": "⚙️",
        "track": "muziek",
        "desc": (
            "Filtert nummers per afspeellijsttype op tempo- en energiedrempels "
            "(kalm: 50-95 BPM, neutraal: 95-115 BPM, energiek: 120-180 BPM). "
            "Sorteert vervolgens op het ISO-principe: afdalend / stabiel / oplopend BPM. "
            "Past daarna loudness-smoothing toe voor vloeiende overgangen."
        ),
        "data_label": "Voorbeeld: kalme afspeellijst van bosbes",
        "data_fn": "_preview_calm",
    },
    {
        "id": "playlists",
        "label": "Afspeellijsten",
        "icon": "📋",
        "track": "muziek",
        "desc": (
            "Drie gegenereerde afspeellijsten per deelnemer, elk ~12 nummers (~30 min). "
            "Validatie controleert: temposcheidingen, energiescheidingen, "
            "minimaal 15 BPM-kloof tussen kalm en energiek, en minimale duur van 25 min."
        ),
        "data_label": "Bestand: data/playlists/{deelnemer}/playlists_generated/{deelnemer}_{type}_playlist.csv",
        "data_fn": "_preview_calm",
    },
    {
        "id": "garmin",
        "label": "Garmin FIT",
        "icon": "⌚",
        "track": "biometrie",
        "desc": (
            "Deelnemers met een Garmin-horloge exporteren hun data via GDPR-export. "
            "FIT-bestanden zijn binaire bestanden met per-minuut hartslag, stress en "
            "body battery, geconverteerd via de fitparse-bibliotheek."
        ),
        "data_label": "Formaat: binaire .FIT per dag. Geconverteerd via fitparse.",
        "data_fn": None,
    },
    {
        "id": "wearables",
        "label": "garmin_pipeline.py",
        "icon": "🔄",
        "track": "biometrie",
        "desc": (
            "Extraheert per-minuut stress, hartslag en body battery. "
            "Koppelt sessievensters via check-in-tijden (CET -> UTC omzetting). "
            "Berekent gemiddelden per fase (voor/tijdens/na) en herstelparameter tau."
        ),
        "data_label": "Produceert: session_biometrics.csv, session_traces/*.csv, garmin_minute_*.csv",
        "data_fn": None,
    },
    {
        "id": "traces",
        "label": "Biometrische CSV's",
        "icon": "📊",
        "track": "biometrie",
        "desc": (
            "Per-sessie tijdreeksen van stress en hartslag, opgesplitst in drie fasen: "
            "voor (-60 min), tijdens (sessie), en na (+60 min). "
            "Dit zijn de ruwe metingen zichtbaar op de Afspelen-pagina."
        ),
        "data_label": "Voorbeeld: sessiemeting bosbes (eerste 4 rijen)",
        "data_fn": "_preview_biometrics",
    },
    {
        "id": "checkins",
        "label": "Check-ins",
        "icon": "📝",
        "track": "analyse",
        "desc": (
            "Deelnemers vullen voor en na elke sessie een Google Formulier in: "
            "stemming als woord (bijv. 'Gestresseerd') en een intensiteitsscore (1-10). "
            "Doelvariabele: mood_delta = score_na - score_voor."
        ),
        "data_label": "Bestand: data/checkins/Check-in_formulier_REM.csv",
        "data_fn": None,
    },
    {
        "id": "feature_matrix",
        "label": "circadian_baseline.py",
        "icon": "🧮",
        "track": "analyse",
        "desc": (
            "Berekent de circadiane basislijn per deelnemer: gemiddelde stress per uur "
            "op niet-sessiedagen. Bouwt een feature-matrix van 28 kolommen per sessie, "
            "met als sterkste kenmerk: baseline_deviation_entry = gemeten_stress - "
            "verwachte_stress_op_dat_uur."
        ),
        "data_label": "Voorbeeld: feature-matrix (eerste 4 rijen)",
        "data_fn": "_preview_features",
    },
    {
        "id": "ml",
        "label": "circadian_ml.py",
        "icon": "🤖",
        "track": "analyse",
        "desc": (
            "Traint Ridge, Random Forest en Gradient Boosting op de feature-matrix om "
            "mood_delta te voorspellen. LOO-kruisvalidatie per deelnemer voorkomt "
            "datalek. SHAP-waarden tonen welke kenmerken het meeste bijdragen."
        ),
        "data_label": "Modelresultaten (LOO-kruisvalidatie)",
        "data_fn": "_preview_model",
    },
    {
        "id": "bayesian",
        "label": "bayesian_recommender.py",
        "icon": "📐",
        "track": "analyse",
        "desc": (
            "Hierarchisch Bayesiaans model via JAX/NumPyro (2.000 MCMC-samples). "
            "Gedeelde pooling over deelnemers zorgt dat ook deelnemers met weinig "
            "sessies profiteren van groepspatronen. "
            "Output: posterior-kansen voor elk afspeellijsttype per deelnemer."
        ),
        "data_label": "Posterior-aanbevelingen per deelnemer",
        "data_fn": "_preview_recs",
    },
]

_TRACK_LABELS = {
    "muziek":     ("🎵", "Muziektrack"),
    "biometrie":  ("⌚", "Biometrietrack"),
    "analyse":    ("🤖", "Analysetrack"),
}


# ---------------------------------------------------------------------------
# Data-preview helpers (lazy, called only when detail-modus actief is)
# ---------------------------------------------------------------------------

def _preview_source() -> pd.DataFrame:
    for p in ["bosbes", "kiwi", "kokosnoot", "limoen"]:
        for f in (DATA / "playlists" / p).glob("*.csv"):
            if "playlists_generated" not in str(f) and "_old" not in str(f):
                try:
                    df = pd.read_csv(f, nrows=4)
                    cols = [c for c in ["name", "artists", "tempo", "energy", "valence", "acousticness"] if c in df.columns]
                    return df[cols].head(4) if cols else pd.DataFrame()
                except Exception:
                    continue
    return pd.DataFrame()


def _preview_calm() -> pd.DataFrame:
    path = DATA / "playlists" / "bosbes" / "playlists_generated" / "bosbes_calm_playlist.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, nrows=5)
    cols = [c for c in ["name", "artists", "tempo", "energy", "valence"] if c in df.columns]
    return df[cols].head(5)


def _preview_biometrics() -> pd.DataFrame:
    path = DATA / "wearables" / "bosbes" / "processed" / "session_biometrics.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, nrows=4)
    cols = [c for c in ["date", "playlist", "pre_stress_mean", "during_stress_mean",
                         "post_stress_mean", "mood_before", "mood_after", "duration_min"] if c in df.columns]
    return df[cols].head(4)


def _preview_features() -> pd.DataFrame:
    path = DATA / "analysis" / "circadian_baselines" / "feature_matrix.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, nrows=4)
    cols = [c for c in ["participant", "date", "playlist", "baseline_deviation_entry",
                         "hour_of_day", "mood_delta", "pre_stress_mean"] if c in df.columns]
    return df[cols].head(4)


def _preview_model() -> pd.DataFrame:
    path = DATA / "analysis" / "circadian_baselines" / "model_results_mood_delta.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _preview_recs() -> pd.DataFrame:
    path = DATA / "analysis" / "bayesian_recommender" / "recommendations.json"
    if not path.exists():
        return pd.DataFrame()
    recs = json.loads(path.read_text())
    rows = []
    for p, playlists in recs.items():
        for playlist, vals in playlists.items():
            rows.append({
                "deelnemer": p,
                "type": playlist,
                "posterior": round(vals.get("mean", 0), 3),
                "ci_laag": round(vals.get("ci_low", 0), 3),
                "ci_hoog": round(vals.get("ci_high", 0), 3),
            })
    return pd.DataFrame(rows)


_PREVIEW_FNS = {
    "_preview_source":    _preview_source,
    "_preview_calm":      _preview_calm,
    "_preview_biometrics": _preview_biometrics,
    "_preview_features":  _preview_features,
    "_preview_model":     _preview_model,
    "_preview_recs":      _preview_recs,
}


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def _df_to_html(df: pd.DataFrame) -> str:
    import html as _html
    if df.empty:
        return f"<p style='color:{TEXT_SECONDARY}; font-size:13px; margin:0;'>Geen data beschikbaar.</p>"
    headers = "".join(f"<th>{_html.escape(str(c))}</th>" for c in df.columns)
    rows = "".join(
        "<tr>" + "".join(f"<td>{_html.escape(str(v)[:40])}</td>" for v in row) + "</tr>"
        for _, row in df.iterrows()
    )
    return (
        "<div style='background:var(--bg-surface,#1a1a1a); border-radius:8px; overflow:auto;'>"
        "<table class='mt-table' style='font-size:12px;'>"
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{rows}</tbody>"
        "</table>"
        "</div>"
    )


def _step_btn(step: dict, is_active: bool) -> _ui.Tag:
    cls = "mt-pipeline-box" + (" active" if is_active else "")
    return _ui.input_action_button(
        f"step_{step['id']}",
        f"{step['icon']} {step['label']}",
        class_=cls,
    )


def _arrow_el() -> _ui.Tag:
    return _ui.div("->", class_="mt-pipeline-arrow")


def _track_row(track_id: str, selected_id: str) -> _ui.Tag:
    icon, label = _TRACK_LABELS[track_id]
    steps = [s for s in _STEPS if s["track"] == track_id]
    elements: list = []
    for i, step in enumerate(steps):
        elements.append(_step_btn(step, step["id"] == selected_id))
        if i < len(steps) - 1:
            elements.append(_arrow_el())
    return _ui.div(
        _ui.div(
            f"{icon} {label}",
            class_="mt-eyebrow",
            style="margin-bottom:8px; font-size:10px; letter-spacing:1.5px;",
        ),
        _ui.div(*elements, class_="mt-pipeline-track"),
    )


# ---------------------------------------------------------------------------
# Module UI
# ---------------------------------------------------------------------------

@module.ui
def ui():
    return _ui.div(
        # Koptekst
        _ui.div(
            _ui.div("De Datapipeline", class_="mt-h1"),
            _ui.p(
                "Hoe ruwe Spotify- en Garmin-gegevens worden omgezet naar "
                "gepersonaliseerde afspeellijstaanbevelingen.",
                class_="mt-body mt-secondary",
                style="margin-top:8px; max-width:640px;",
            ),
            style="text-align:center; padding:48px 80px 32px;",
        ),

        # Hoofdkaart
        _ui.div(
            _ui.div(
                # Modus-schakelaar
                _ui.div(
                    _ui.output_ui("mode_pills"),
                    style="margin-bottom:32px;",
                ),

                # Diagram
                _ui.output_ui("pipeline_diagram"),

                # Detail-paneel
                _ui.output_ui("step_detail"),

                class_="mt-section-card",
                style="padding:48px 64px;",
            ),
            style="padding:0 80px 32px;",
        ),

        # Connector-uitleg
        _ui.div(
            _ui.div(
                _ui.div("Waarom twee aparte tracks?", class_="mt-h3", style="margin-bottom:12px;"),
                _ui.p(
                    "Muziek wordt gegenereerd op basis van audiokenmerken, "
                    "niet op basis van biometrische data. "
                    "Pas in de analysetrack worden beide samengevoegd via de feature-matrix -- "
                    "zodat we de effecten van elk afspeellijsttype op biometrie zuiver kunnen meten.",
                    class_="mt-body mt-secondary",
                    style="margin-bottom:16px;",
                ),
                _ui.div(
                    _ui.div("Klik op een stap in het diagram om de details te bekijken.", class_="mt-caption mt-secondary"),
                    class_="mt-callout",
                ),
                class_="mt-section-card",
            ),
            style="padding:0 80px 64px;",
        ),
    )


# ---------------------------------------------------------------------------
# Module server
# ---------------------------------------------------------------------------

@module.server
def server(input, output, session, app_data: AppData):
    selected_step: reactive.Value = reactive.Value(None)
    show_detail: reactive.Value = reactive.Value(False)

    @reactive.Effect
    @reactive.event(input.mode_overview)
    def _():
        show_detail.set(False)

    @reactive.Effect
    @reactive.event(input.mode_detail)
    def _():
        show_detail.set(True)

    for _s in _STEPS:
        def _make_obs(step=_s):
            @reactive.Effect
            @reactive.event(input[f"step_{step['id']}"])
            def _():
                selected_step.set(step["id"])
        _make_obs()

    @output
    @render.ui
    def mode_pills():
        show = show_detail()
        return _ui.div(
            _ui.input_action_button(
                "mode_overview", "Diagram",
                class_="pill-btn" + ("" if show else " active"),
            ),
            _ui.input_action_button(
                "mode_detail", "Gegevens",
                class_="pill-btn" + (" active" if show else ""),
            ),
            class_="pill-group",
        )

    @output
    @render.ui
    def pipeline_diagram():
        sel = selected_step() or ""
        connector = _ui.div(class_="mt-pipeline-connector")
        return _ui.div(
            _track_row("muziek",    sel),
            connector,
            _track_row("biometrie", sel),
            connector,
            _track_row("analyse",   sel),
            _ui.div(
                "Klik op een stap voor uitleg en een voorbeeld.",
                class_="mt-caption mt-secondary",
                style="margin-top:12px;",
            ) if not sel else _ui.div(),
            style="margin-bottom:8px;",
        )

    @output
    @render.ui
    def step_detail():
        sel = selected_step()
        if not sel:
            return _ui.div()
        step = next((s for s in _STEPS if s["id"] == sel), None)
        if not step:
            return _ui.div()

        show = show_detail()

        data_section = _ui.div()
        if show and step.get("data_fn"):
            fn = _PREVIEW_FNS.get(step["data_fn"])
            try:
                df = fn() if fn else pd.DataFrame()
                data_html = _df_to_html(df)
            except Exception as e:
                data_html = f"<p style='color:#B3B3B3;'>Fout: {e}</p>"
            data_section = _ui.div(
                _ui.div(step["data_label"], class_="mt-caption mt-secondary",
                        style="margin-bottom:8px; margin-top:16px;"),
                _ui.HTML(data_html),
            )
        elif show:
            data_section = _ui.div(
                step["data_label"],
                class_="mt-caption mt-secondary",
                style="margin-top:12px; font-style:italic;",
            )

        return _ui.div(
            _ui.div(
                _ui.div(
                    _ui.span(step["icon"], style="font-size:22px; margin-right:10px;"),
                    _ui.span(step["label"], class_="mt-h3"),
                    style="display:flex; align-items:center; margin-bottom:12px;",
                ),
                _ui.p(step["desc"], class_="mt-body mt-secondary", style="margin-bottom:0;"),
                data_section,
                class_="mt-pipeline-detail",
            ),
        )
