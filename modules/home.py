"""Pagina 1 -- Home: emotionele hook, studieoverzicht en gepersonaliseerde afspeellijst."""
import random
from pathlib import Path

import pandas as pd
from shiny import module, reactive, render, ui as _ui

from utils.chart_helpers import ACCENT, PLAYLIST_COLORS
from utils.data_loader import PARTICIPANTS, AppData, best_playlist_for

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"

_ISO_LABEL = {
    "Calm":    ("Kalme Afspeellijst",     "Afdalend BPM",   "calm"),
    "Neutral": ("Neutrale Afspeellijst",  "Stabiel BPM",    "neutral"),
    "Energy":  ("Energieke Afspeellijst", "Stijgend BPM",   "energy"),
}

_DATA_LEVEL = {
    "bosbes":      ("vol",          "Volledige biometrische data"),
    "kokosnoot":   ("vol",          "Volledige biometrische data"),
    "limoen":      ("gedeeltelijk", "Gedeeltelijke data (geen stresssensor)"),
    "peer":        ("gedeeltelijk", "Gedeeltelijke data (geen biometrie)"),
    "kiwi":        ("geen",         "Alleen stemming-check-ins"),
    "watermeloen": ("geen",         "Alleen stemming-check-ins"),
}

_COVER_GRADIENT = {
    "Calm":    "linear-gradient(135deg, #1a2a4a, #0a1525)",
    "Neutral": "linear-gradient(135deg, #2a1a4a, #160a2f)",
    "Energy":  "linear-gradient(135deg, #4a2a1a, #2f1508)",
}

_DAYS_NL   = ["ma", "di", "wo", "do", "vr", "za", "zo"]
_MONTHS_NL = ["jan", "feb", "mrt", "apr", "mei", "jun",
               "jul", "aug", "sep", "okt", "nov", "dec"]


def _format_date_nl(date_str: str) -> str:
    from datetime import datetime
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return f"{_DAYS_NL[dt.weekday()]} {dt.day} {_MONTHS_NL[dt.month - 1]}. {dt.year}"
    except Exception:
        return date_str


def _load_playlist(participant: str, playlist_type: str) -> pd.DataFrame:
    t = playlist_type.lower()
    path = DATA / "playlists" / participant / "playlists_generated" / f"{participant}_{t}_playlist.csv"
    if path.exists():
        try:
            return pd.read_csv(path)
        except Exception:
            pass
    for alt in ["calm", "neutral", "energy"]:
        alt_path = DATA / "playlists" / participant / "playlists_generated" / f"{participant}_{alt}_playlist.csv"
        if alt_path.exists():
            try:
                return pd.read_csv(alt_path)
            except Exception:
                pass
    return pd.DataFrame()


def _track_duration(ms_val) -> str:
    try:
        ms = int(ms_val)
        return f"{ms // 60000}:{(ms % 60000) // 1000:02d}"
    except Exception:
        return "--"


def _track_row(i: int, row: pd.Series, is_playing: bool = False) -> _ui.Tag:
    name    = str(row.get("name",    "Onbekend"))[:40]
    artists = str(row.get("artists", ""))[:30]
    try:
        tempo = f"{float(row.get('tempo', 0)):.0f} BPM"
    except Exception:
        tempo = "--"
    try:
        energy_pct = int(float(row.get("energy", 0)) * 100)
    except Exception:
        energy_pct = 0
    dur = _track_duration(row.get("duration_ms", 0))

    row_class = "track-row" + (" playing" if is_playing else "")
    num_display = "♪" if is_playing else str(i + 1)

    # Cover art placeholder with gradient
    hue = (i * 47) % 360
    art_style = (
        f"width:48px; height:48px; border-radius:6px; flex-shrink:0; "
        f"background:linear-gradient(135deg, hsl({hue},40%,20%), hsl({(hue+60)%360},30%,12%));"
    )

    return _ui.div(
        _ui.div(num_display, class_="track-number"),
        _ui.div(style=art_style),
        _ui.div(
            _ui.div(name, class_="track-title"),
            _ui.div(artists, class_="track-artist"),
        ),
        _ui.div(tempo, class_="track-bpm"),
        _ui.div(
            _ui.div(style=f"width:{energy_pct}%; height:100%; border-radius:2px; background:var(--accent);"),
            class_="track-energy-bar",
        ),
        _ui.div(dur, class_="track-duration"),
        class_=row_class,
    )


def _total_duration(df: pd.DataFrame) -> str:
    try:
        total_ms = df["duration_ms"].sum()
        total_min = int(total_ms / 60000)
        return f"{total_min} min"
    except Exception:
        return "--"


def _build_playlist_view(df: pd.DataFrame, playlist_type: str, participant: str, date_str: str | None) -> _ui.Tag:
    if df.empty:
        return _ui.div(
            _ui.div("Geen afspeellijst beschikbaar voor deze deelnemer.", class_="mt-body mt-secondary"),
            class_="mt-card", style="text-align:center; padding:48px;",
        )

    type_name, iso_dir, badge_cls = _ISO_LABEL.get(playlist_type, ("Afspeellijst", "ISO", "calm"))
    cover_grad = _COVER_GRADIENT.get(playlist_type, _COVER_GRADIENT["Calm"])
    date_txt   = _format_date_nl(date_str) if date_str else "geselecteerde sessie"
    duration   = _total_duration(df)
    n_tracks   = len(df)

    # Playlist header card
    header = _ui.div(
        # Cover art
        _ui.div("🎵", class_="playlist-cover", style=f"background:{cover_grad};"),
        # Meta
        _ui.div(
            _ui.div(f"Gegenereerd voor {participant.capitalize()}", class_="overline"),
            _ui.tags.h1(type_name),
            _ui.p(
                f"ISO-geordende nummers om je arousal geleidelijk te begeleiden. "
                f"Gebaseerd op jouw sessie van {date_txt}.",
                class_="subtitle",
            ),
            _ui.div(
                _ui.span(playlist_type.upper(), class_=f"mt-badge mt-badge-{badge_cls}"),
                _ui.span(
                    _ui.tags.strong(str(n_tracks)), " nummers",
                    class_="meta-detail",
                ),
                _ui.span(
                    _ui.tags.strong(duration),
                    class_="meta-detail",
                ),
                _ui.span(f"ISO-richting: {iso_dir}", class_="meta-detail"),
                class_="playlist-meta-row",
            ),
            class_="playlist-meta",
        ),
        class_="playlist-header fade-in",
    )

    # Track list
    tracks = [_track_row(i, row, is_playing=(i == 0))
              for i, (_, row) in enumerate(df.iterrows())]

    iso_bars = _ui.div(
        _ui.span("ISO-richting", class_="iso-label"),
        _ui.div(
            _ui.div(style="width:60px; height:3px; border-radius:2px; background:var(--calm-color);"),
            _ui.div(style="width:40px; height:3px; border-radius:2px; background:rgba(59,130,246,0.5);"),
            _ui.div(style="width:24px; height:3px; border-radius:2px; background:rgba(59,130,246,0.25);"),
            _ui.span(f"- {iso_dir.lower()}",
                     style="color:var(--text-tertiary); font-size:0.8rem;"),
            style="display:flex; align-items:center; gap:6px;",
        ),
        class_="iso-indicator",
    )

    tracklist = _ui.div(
        _ui.div(
            _ui.span("#"),
            _ui.span(),
            _ui.span("Titel"),
            _ui.span("BPM"),
            _ui.span("Energie"),
            _ui.span("Duur"),
            class_="tracklist-header",
        ),
        *tracks,
        iso_bars,
        class_="tracklist-section fade-in-2",
    )

    return _ui.div(header, tracklist)


# ---------------------------------------------------------------------------
# Module UI
# ---------------------------------------------------------------------------

@module.ui
def ui():
    return _ui.div(
        # Page header
        _ui.div(
            _ui.div("PROJECT R.E.M.", class_="mt-eyebrow", style="margin-bottom:8px;"),
            _ui.div("MoodTune", class_="mt-h1", style="font-family:'Sora',sans-serif; font-size:2rem; margin-bottom:8px;"),
            _ui.p(
                "Genereer jouw gepersonaliseerde ISO-afspeellijst op basis van "
                "Bayesiaanse analyse van historische sessies.",
                class_="mt-body",
                style="color:var(--text-secondary); max-width:560px; margin-bottom:24px;",
            ),
            # Participant pills
            _ui.div(_ui.output_ui("home_participant_pills"), style="margin-bottom:16px;"),
            # Generate button
            _ui.input_action_button("generate_btn", "Genereer afspeellijst", class_="mt-btn-primary"),
            style="margin-bottom:32px;",
        ),

        # Stats row (always visible)
        _ui.output_ui("stats_row"),

        # Playlist (rendered after generate click)
        _ui.div(_ui.output_ui("player_ui")),

        class_="fade-in",
    )


# ---------------------------------------------------------------------------
# Module server
# ---------------------------------------------------------------------------

def _compute_study_stats(app_data: AppData) -> tuple[int, int, int]:
    """Return (n_sessions, n_weeks, n_participants_with_data) from actual data."""
    fm = app_data.feature_matrix
    if fm.empty:
        return 47, 8, 6
    n_sessions = len(fm)
    n_participants = fm["participant"].nunique() if "participant" in fm.columns else 6
    if "date" in fm.columns:
        dates = pd.to_datetime(fm["date"], errors="coerce").dropna()
        n_weeks = max(1, round((dates.max() - dates.min()).days / 7)) if len(dates) > 1 else 8
    else:
        n_weeks = 8
    return n_sessions, n_weeks, n_participants


@module.server
def server(input, output, session, app_data: AppData, now_playing=None):
    selected_participant: reactive.Value = reactive.Value("bosbes")
    player_state: reactive.Value = reactive.Value(None)

    for _p in PARTICIPANTS:
        def _make_obs(participant=_p):
            @reactive.Effect
            @reactive.event(input[f"pill_{participant}"])
            def _():
                selected_participant.set(participant)
                player_state.set(None)
        _make_obs()

    @reactive.Effect
    @reactive.event(input.generate_btn)
    def _generate():
        p = selected_participant()
        dates = list(app_data.session_traces.get(p, {}).keys())
        date  = random.choice(dates) if dates else None
        playlist_type, confidence = best_playlist_for(app_data, p)
        df = _load_playlist(p, playlist_type)
        state = {
            "df":            df,
            "playlist_type": playlist_type,
            "participant":   p,
            "date":          date,
            "confidence":    confidence,
        }
        player_state.set(state)
        if now_playing is not None:
            now_playing.set(state)

    @output
    @render.ui
    def home_participant_pills():
        curr = selected_participant()
        pills = []
        _level_dot = {"vol": "●", "gedeeltelijk": "◑", "geen": "○"}
        for p in PARTICIPANTS:
            cls  = "pill-btn" + (" active" if p == curr else "")
            lvl, tip = _DATA_LEVEL.get(p, ("geen", ""))
            dot  = _level_dot[lvl]
            label = f"{p.capitalize()} {dot}"
            btn = _ui.input_action_button(f"pill_{p}", label, class_=cls, title=tip)
            pills.append(btn)
        legend = _ui.div(
            _ui.span("● vol  ◑ gedeeltelijk  ○ geen biometrie",
                     class_="mt-caption mt-secondary",
                     style="font-size:11px;"),
            style="margin-top:8px;",
        )
        return _ui.div(*pills, legend, class_="pill-group")

    @output
    @render.ui
    def stats_row():
        n_sessions, n_weeks, n_with_data = _compute_study_stats(app_data)
        def _card(val, label, cls=""):
            return _ui.div(
                _ui.div(str(val), class_="mt-stat-value"),
                _ui.div(label, class_="mt-stat-label"),
                class_=f"mt-stat-card {cls}".strip(),
            )
        return _ui.div(
            _card(len(PARTICIPANTS), "Deelnemers",     "fade-in"),
            _card(n_sessions,        "Sessies",         "fade-in-1"),
            _card(n_weeks,           "Weken",           "fade-in-2"),
            _card(3,                 "Afspeellijsttypes","fade-in-3"),
            class_="stats-row",
            style="margin-bottom:32px;",
        )

    @output
    @render.ui
    def player_ui():
        state = player_state()
        if state is None:
            return _ui.div()
        view = _build_playlist_view(
            state["df"],
            state["playlist_type"],
            state["participant"],
            state.get("date"),
        )
        if state["df"].empty:
            return view
        conf_txt = f"{state['confidence']}% posterior-kans" if state["confidence"] else ""
        caption = _ui.div(
            f"Aanbevolen voor {state['participant'].capitalize()} "
            f"op basis van historische sessies. {conf_txt}",
            class_="mt-caption",
            style="color:var(--text-tertiary); margin-top:8px; text-align:center;",
        )
        cta = _ui.div(
            _ui.div(
                _ui.div("Wat nu?", class_="mt-caption mt-secondary", style="margin-bottom:8px;"),
                _ui.div(
                    _ui.div(
                        _ui.div("Bekijk een echte sessie", class_="mt-body"),
                        _ui.div("Biometrische boog + herstelcurve →", class_="mt-caption mt-secondary"),
                        _ui.div("Navigeer naar Afspelen", class_="mt-caption",
                                style="color:var(--accent); margin-top:4px;"),
                        class_="mt-card-elevated",
                        style="padding:16px; cursor:default;",
                    ),
                    _ui.div(
                        _ui.div("Persoonlijke aanbeveling", class_="mt-body"),
                        _ui.div("Bayesiaans model + circadiane context →", class_="mt-caption mt-secondary"),
                        _ui.div("Navigeer naar Aanbevelen", class_="mt-caption",
                                style="color:var(--accent); margin-top:4px;"),
                        class_="mt-card-elevated",
                        style="padding:16px; cursor:default;",
                    ),
                    style="display:grid; grid-template-columns:1fr 1fr; gap:12px;",
                ),
            ),
            style="margin-top:24px; max-width:640px;",
        )
        return _ui.div(view, caption, cta)
