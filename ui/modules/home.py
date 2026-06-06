"""Pagina 1 -- Home: willekeurig moment uit wearables-data, live ML-aanbeveling."""
import datetime
import random
from pathlib import Path

import pandas as pd
from shiny import module, reactive, render, ui as _ui

from utils.chart_helpers import ACCENT, PLAYLIST_COLORS
from utils.data_loader import PARTICIPANTS, AppData, best_playlist_for, live_recommend

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"

_ISO_LABEL = {
    "Calm":    ("Kalme Afspeellijst",     "Afdalend BPM",   "calm"),
    "Neutral": ("Neutrale Afspeellijst",  "Stabiel BPM",    "neutral"),
    "Energy":  ("Energieke Afspeellijst", "Stijgend BPM",   "energy"),
}

_COVER_GRADIENT = {
    "Calm":    "linear-gradient(135deg, #1a2a4a, #0a1525)",
    "Neutral": "linear-gradient(135deg, #2a1a4a, #160a2f)",
    "Energy":  "linear-gradient(135deg, #4a2a1a, #2f1508)",
}

_DAYS_NL   = ["ma", "di", "wo", "do", "vr", "za", "zo"]
_MONTHS_NL = ["jan", "feb", "mrt", "apr", "mei", "jun",
               "jul", "aug", "sep", "okt", "nov", "dec"]

_PLAYLIST_NL = {"Calm": "Kalm", "Neutral": "Neutraal", "Energy": "Energiek"}


def _format_date_nl(date_str: str) -> str:
    try:
        dt = datetime.datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
        return f"{_DAYS_NL[dt.weekday()]} {dt.day} {_MONTHS_NL[dt.month - 1]}. {dt.year}"
    except Exception:
        return str(date_str)


def _shuffle_iso_tiers(df: pd.DataFrame, playlist_type: str) -> pd.DataFrame:
    """Shuffle within ~5-BPM tiers while preserving the ISO direction across tiers."""
    if df.empty or "tempo" not in df.columns:
        return df
    df = df.copy()
    df["_tempo_num"] = pd.to_numeric(df["tempo"], errors="coerce")
    df["_tier"] = (df["_tempo_num"] / 5).round() * 5

    parts = []
    for _, grp in df.groupby("_tier", sort=False):
        parts.append(grp.sample(frac=1))

    if not parts:
        return df.drop(columns=["_tempo_num", "_tier"], errors="ignore")

    result = pd.concat(parts)
    if playlist_type == "Neutral":
        result = result.sample(frac=1)
    else:
        ascending = playlist_type == "Energy"
        result = result.sort_values("_tier", ascending=ascending)

    return result.drop(columns=["_tempo_num", "_tier"], errors="ignore").reset_index(drop=True)


def _load_playlist(participant: str, playlist_type: str) -> pd.DataFrame:
    t = playlist_type.lower()
    path = DATA / "playlists" / participant / "playlists_generated" / f"{participant}_{t}_playlist.csv"
    if path.exists():
        try:
            return _shuffle_iso_tiers(pd.read_csv(path), playlist_type)
        except Exception:
            pass
    for alt in ["calm", "neutral", "energy"]:
        alt_path = DATA / "playlists" / participant / "playlists_generated" / f"{participant}_{alt}_playlist.csv"
        if alt_path.exists():
            try:
                return _shuffle_iso_tiers(pd.read_csv(alt_path), alt.capitalize())
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
    try:
        acousticness_pct = int(float(row.get("acousticness", 0)) * 100)
    except Exception:
        acousticness_pct = 0
    try:
        valence_pct = int(float(row.get("valence", 0)) * 100)
    except Exception:
        valence_pct = 0
    dur = _track_duration(row.get("duration_ms", 0))

    row_class = "track-row" + (" playing" if is_playing else "")
    num_display = "♪" if is_playing else str(i + 1)

    hue = (i * 47) % 360
    art_style = (
        f"width:48px; height:48px; border-radius:6px; flex-shrink:0; "
        f"background:linear-gradient(135deg, hsl({hue},40%,20%), hsl({(hue+60)%360},30%,12%));"
    )

    audio_badges = _ui.div(
        _ui.span(f"♦ {acousticness_pct}% akoestisch",
                 style="font-size:10px; color:var(--text-tertiary); margin-right:8px;"),
        _ui.span(f"♡ {valence_pct}% valentie",
                 style="font-size:10px; color:var(--text-tertiary);"),
        style="margin-top:2px;",
    ) if (acousticness_pct > 0 or valence_pct > 0) else _ui.div()

    return _ui.div(
        _ui.div(num_display, class_="track-number"),
        _ui.div(style=art_style),
        _ui.div(
            _ui.div(name, class_="track-title"),
            _ui.div(artists, class_="track-artist"),
            audio_badges,
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


def _bpm_sparkline(df: pd.DataFrame, playlist_type: str) -> _ui.Tag:
    """Tiny SVG BPM trend line for the playlist header."""
    if df.empty or "tempo" not in df.columns:
        return _ui.div()
    tempos = pd.to_numeric(df["tempo"], errors="coerce").dropna().tolist()
    if len(tempos) < 2:
        return _ui.div()
    w, h, pad = 120, 28, 3
    lo, hi = min(tempos), max(tempos)
    rng = hi - lo if hi != lo else 1
    xs = [pad + (i / (len(tempos) - 1)) * (w - 2 * pad) for i in range(len(tempos))]
    ys = [h - pad - ((t - lo) / rng) * (h - 2 * pad) for t in tempos]
    points = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    color_map = {"Calm": "#3b82f6", "Neutral": "#a855f7", "Energy": "#f97316"}
    color = color_map.get(playlist_type, "#22c55e")
    return _ui.HTML(
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'style="display:block; overflow:visible;">'
        f'<polyline points="{points}" fill="none" stroke="{color}" '
        f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" opacity="0.85"/>'
        f'<circle cx="{xs[0]:.1f}" cy="{ys[0]:.1f}" r="3" fill="{color}" opacity="0.7"/>'
        f'<circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="3" fill="{color}"/>'
        f'</svg>'
    )


def _build_playlist_view(df: pd.DataFrame, playlist_type: str, participant: str, date_str: str | None) -> _ui.Tag:
    if df.empty:
        return _ui.div(
            _ui.div("Geen afspeellijst beschikbaar voor deze deelnemer.", class_="mt-body mt-secondary"),
            class_="mt-card", style="text-align:center; padding:48px;",
        )

    type_name, iso_dir, badge_cls = _ISO_LABEL.get(playlist_type, ("Afspeellijst", "ISO", "calm"))
    cover_grad = _COVER_GRADIENT.get(playlist_type, _COVER_GRADIENT["Calm"])
    date_txt   = _format_date_nl(date_str) if date_str else "geselecteerd moment"
    duration   = _total_duration(df)
    n_tracks   = len(df)

    header = _ui.div(
        _ui.div("🎵", class_="playlist-cover", style=f"background:{cover_grad};"),
        _ui.div(
            _ui.div(f"Gegenereerd voor {participant.capitalize()}", class_="overline"),
            _ui.tags.h1(type_name),
            _ui.p(
                f"ISO-geordende nummers om je arousal geleidelijk te begeleiden. "
                f"Gebaseerd op jouw biometrische staat op {date_txt}.",
                class_="subtitle",
            ),
            _ui.div(
                _ui.span(playlist_type.upper(), class_=f"mt-badge mt-badge-{badge_cls}"),
                _ui.span(_ui.tags.strong(str(n_tracks)), " nummers", class_="meta-detail"),
                _ui.span(_ui.tags.strong(duration), class_="meta-detail"),
                _ui.span(f"ISO-richting: {iso_dir}", class_="meta-detail"),
                _ui.span(
                    _bpm_sparkline(df, playlist_type),
                    class_="meta-detail",
                    style="display:inline-flex; align-items:center; vertical-align:middle;",
                ),
                class_="playlist-meta-row",
            ),
            class_="playlist-meta",
        ),
        class_="playlist-header fade-in",
    )

    tracks = [_track_row(i, row, is_playing=(i == 0))
              for i, (_, row) in enumerate(df.iterrows())]

    iso_bars = _ui.div(
        _ui.span("ISO-richting", class_="iso-label"),
        _ui.div(
            _ui.div(style="width:60px; height:3px; border-radius:2px; background:var(--calm-color);"),
            _ui.div(style="width:40px; height:3px; border-radius:2px; background:rgba(59,130,246,0.5);"),
            _ui.div(style="width:24px; height:3px; border-radius:2px; background:rgba(59,130,246,0.25);"),
            _ui.span(f"- {iso_dir.lower()}", style="color:var(--text-tertiary); font-size:0.8rem;"),
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
            _ui.div("MoodTune", class_="mt-h1",
                    style="font-family:'Sora',sans-serif; font-size:2rem; margin-bottom:8px;"),
            _ui.p(
                "Kies een willekeurig moment uit de wearables-data. Het ML-model berekent op "
                "basis van de biometrische staat op dat moment welk afspeellijsttype de beste "
                "stemmingsverbetering zou opleveren.",
                class_="mt-body",
                style="color:var(--text-secondary); max-width:560px; margin-bottom:24px;",
            ),
        ),

        # Two-column panel: moment selector (left) + recommendation (right)
        _ui.div(
            # Left: date/hour picker + biometric state
            _ui.div(
                _ui.div("Kies een moment", class_="mt-h3", style="margin-bottom:8px;"),
                _ui.p(
                    "Selecteer een datum en uur. Het model zoekt de werkelijke biometrische "
                    "waarden op uit de wearables-data.",
                    class_="mt-caption mt-secondary",
                    style="margin-bottom:16px;",
                ),
                _ui.input_date(
                    "home_date", "Datum",
                    value="2026-01-01",
                    width="100%",
                ),
                _ui.div(style="height:12px;"),
                _ui.input_slider(
                    "home_hour", "Uur van de dag",
                    min=0, max=23, value=8, step=1,
                    post="h",
                    width="100%",
                ),
                _ui.div(
                    _ui.input_action_button(
                        "random_btn", "Willekeurig moment",
                        class_="mt-btn-secondary",
                        style="width:100%; margin-top:12px;",
                    ),
                ),
                _ui.output_ui("moment_state_ui"),
                class_="mt-card-elevated",
                style="flex:1; min-width:0; padding:24px;",
            ),
            # Right: recommendation panel
            _ui.div(
                _ui.output_ui("rec_panel_ui"),
                class_="mt-card-elevated",
                style="flex:1; min-width:0; padding:24px;",
            ),
            style="display:flex; gap:16px; margin-bottom:24px; align-items:flex-start;",
        ),

        # Generate button
        _ui.div(
            _ui.input_action_button("generate_btn", "Genereer afspeellijst",
                                    class_="mt-btn-primary"),
            style="margin-bottom:32px;",
        ),

        # Playlist (appears after generate click)
        _ui.div(_ui.output_ui("player_ui")),

        class_="fade-in",
    )


# ---------------------------------------------------------------------------
# Module server
# ---------------------------------------------------------------------------

@module.server
def server(input, output, session, app_data: AppData, now_playing=None, selected_participant=None):
    sel = selected_participant if selected_participant is not None else reactive.Value("bosbes")
    player_state: reactive.Value = reactive.Value(None)

    @reactive.Effect
    def _reset_on_participant_change():
        sel()
        player_state.set(None)

    # ── Garmin per-minute data ────────────────────────────────────────────

    @reactive.Calc
    def _garmin_df():
        return app_data.garmin_minute.get(sel(), pd.DataFrame())

    @reactive.Calc
    def _date_range():
        """Return (min_date_str, max_date_str) for the current participant's garmin data."""
        gm = _garmin_df()
        if gm.empty or "timestamp" not in gm.columns:
            return "2026-01-01", "2026-12-31"
        dates = gm["timestamp"].dt.date
        return str(dates.min()), str(dates.max())

    @reactive.Effect
    def _init_date():
        """Update date picker bounds + initial value whenever participant changes."""
        min_d, max_d = _date_range()
        _ui.update_date("home_date", min=min_d, max=max_d, value=max_d, session=session)

    @reactive.Effect
    @reactive.event(input.random_btn)
    def _pick_random():
        gm = _garmin_df()
        if gm.empty or "timestamp" not in gm.columns:
            return
        # Pick from rows that have at least stress or heart_rate
        for col in ("stress", "heart_rate"):
            if col in gm.columns:
                valid = gm[gm[col].notna()]
                if not valid.empty:
                    ts = valid.iloc[random.randint(0, len(valid) - 1)]["timestamp"]
                    _ui.update_date("home_date", value=str(ts.date()), session=session)
                    _ui.update_slider("home_hour", value=int(ts.hour), session=session)
                    return
        # fallback: pick any row
        ts = gm.iloc[random.randint(0, len(gm) - 1)]["timestamp"]
        _ui.update_date("home_date", value=str(ts.date()), session=session)
        _ui.update_slider("home_hour", value=int(ts.hour), session=session)

    # ── Moment biometric lookup ───────────────────────────────────────────

    @reactive.Calc
    def _moment_bio():
        """Look up real garmin biometrics for the selected date+hour window."""
        p        = sel()
        gm       = _garmin_df()
        date_val = input.home_date()
        hour_val = int(input.home_hour())

        if date_val is None:
            return pd.Series(dtype=object)

        # Normalise to datetime.date
        if isinstance(date_val, datetime.date) and not isinstance(date_val, datetime.datetime):
            date_dt = date_val
        else:
            try:
                date_dt = datetime.date.fromisoformat(str(date_val)[:10])
            except Exception:
                return pd.Series(dtype=object)

        date_str = str(date_dt)

        base = {"_date_str": date_str, "_hour": hour_val}

        if gm.empty or "timestamp" not in gm.columns:
            return pd.Series({**base, "_no_data": True})

        mask   = (gm["timestamp"].dt.date == date_dt) & (gm["timestamp"].dt.hour == hour_val)
        window = gm[mask]

        if window.empty:
            return pd.Series({**base, "_no_data": True})

        result = {**base, "_no_data": False}

        if "stress" in window.columns:
            vals = window["stress"].dropna()
            if not vals.empty:
                result["pre_stress_mean"] = float(vals.mean())

        if "heart_rate" in window.columns:
            vals = window["heart_rate"].dropna()
            if not vals.empty:
                result["pre_hr_mean"] = float(vals.mean())

        if "body_battery" in window.columns:
            vals = window["body_battery"].dropna()
            if not vals.empty:
                result["bb_start"] = float(vals.mean())

        # Circadian deviation vs. hourly baseline
        hb = app_data.hourly_baselines.get(p, pd.DataFrame())
        if not hb.empty and "hour" in hb.columns:
            hb_row = hb[hb["hour"] == hour_val]
            if not hb_row.empty:
                if "pre_stress_mean" in result and "mean_stress" in hb_row.columns:
                    exp_s = float(hb_row["mean_stress"].iloc[0])
                    result["baseline_deviation_entry"] = result["pre_stress_mean"] - exp_s
                if "pre_hr_mean" in result and "mean_hr" in hb_row.columns:
                    exp_hr = float(hb_row["mean_hr"].iloc[0])
                    result["hr_baseline_deviation"] = result["pre_hr_mean"] - exp_hr

        result["hour_of_day"]  = float(hour_val)
        result["start_local"]  = f"{hour_val:02d}:00"
        result["day_of_week"]  = float(date_dt.weekday())

        return pd.Series(result)

    # ── Moment state display ──────────────────────────────────────────────

    @output
    @render.ui
    def moment_state_ui():
        p   = sel()
        bio = _moment_bio()

        if bio.empty:
            return _ui.div(
                "Selecteer een datum om de biometrische staat te zien.",
                class_="mt-caption mt-secondary",
                style="margin-top:16px;",
            )

        date_str = str(bio.get("_date_str", ""))
        hour_val = int(bio.get("_hour", 0))

        if bio.get("_no_data", True):
            return _ui.div(
                _ui.div(
                    f"Geen wearables-data op {_format_date_nl(date_str)} om {hour_val:02d}:00.",
                    class_="mt-caption mt-secondary",
                ),
                _ui.div(
                    "Kies een ander tijdstip of gebruik 'Willekeurig moment'.",
                    class_="mt-caption mt-tertiary",
                    style="margin-top:4px;",
                ),
                style="margin-top:16px;",
            )

        items = []
        pre_stress   = bio.get("pre_stress_mean")
        pre_hr       = bio.get("pre_hr_mean")
        bb           = bio.get("bb_start")
        baseline_dev = bio.get("baseline_deviation_entry")

        if pre_stress is not None and not pd.isna(pre_stress):
            v = float(pre_stress)
            c = "#ef4444" if v > 60 else ("#f59e0b" if v > 40 else "#22c55e")
            items.append(("Stress", f"{v:.0f}/100", c))
        if pre_hr is not None and not pd.isna(pre_hr):
            items.append(("Hartslag", f"{float(pre_hr):.0f} bpm", "var(--text-primary)"))
        if bb is not None and not pd.isna(bb):
            v = float(bb)
            c = "#ef4444" if v < 30 else ("#f59e0b" if v < 50 else "#22c55e")
            items.append(("Body Battery", f"{v:.0f}%", c))
        if baseline_dev is not None and not pd.isna(baseline_dev):
            v   = float(baseline_dev)
            sgn = "+" if v >= 0 else ""
            c   = "#ef4444" if v > 10 else ("#f59e0b" if v > 5 else "#22c55e")
            items.append(("Circad. afwijking", f"{sgn}{v:.1f}", c))

        if not items:
            return _ui.div(
                "Geen meetwaarden beschikbaar voor dit tijdstip.",
                class_="mt-caption mt-secondary",
                style="margin-top:16px;",
            )

        stat_els = [
            _ui.div(
                _ui.div(val, style=f"font-weight:700; color:{color}; font-size:1.05rem; line-height:1;"),
                _ui.div(label, class_="mt-caption mt-secondary", style="font-size:11px; margin-top:3px;"),
            )
            for label, val, color in items
        ]

        return _ui.div(
            _ui.div(
                _ui.span(f"Staat van {p.capitalize()} op ", class_="mt-caption mt-secondary"),
                _ui.span(
                    f"{_format_date_nl(date_str)} om {hour_val:02d}:00",
                    style="font-weight:600; font-size:0.8125rem;",
                ),
            ),
            _ui.div(
                *stat_els,
                style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-top:12px;",
            ),
            style="margin-top:16px;",
        )

    # ── Recommendation panel ──────────────────────────────────────────────

    @output
    @render.ui
    def rec_panel_ui():
        p       = sel()
        bio_row = _moment_bio()
        no_data = bio_row.empty or bio_row.get("_no_data", True)

        if not no_data and app_data.live_model is not None:
            playlist_type, predictions = live_recommend(app_data, p, bio_row)
            source_label = "ML-aanbeveling (Ridge)"
        else:
            playlist_type, _ = best_playlist_for(app_data, p)
            predictions = {}
            source_label = "Bayesiaanse aanbeveling" if not no_data else "Geen data — standaard"

        nl_name  = _PLAYLIST_NL.get(playlist_type, playlist_type)
        _, iso_dir, badge_cls = _ISO_LABEL.get(playlist_type, ("Afspeellijst", "ISO", "calm"))
        color_map = {"calm": "#3b82f6", "neutral": "#a855f7", "energy": "#f97316"}
        color = color_map.get(badge_cls, "#22c55e")

        reason_parts = []
        if predictions:
            nl = {"Calm": "Kalm", "Neutral": "Neutraal", "Energy": "Energiek"}
            sorted_types = sorted(predictions, key=lambda k: predictions[k], reverse=True)
            preds_str = "  ·  ".join(
                f"{nl.get(t, t)}: {'+' if predictions[t] >= 0 else ''}{predictions[t]:.1f} pt"
                for t in sorted_types
            )
            reason_parts.append(f"Voorspelde stemmingswinst — {preds_str}")
        elif no_data:
            reason_parts.append("Geen wearables-data op dit tijdstip — standaard Bayesiaanse aanbeveling.")
        else:
            reason_parts.append(f"Bayesiaans model op basis van alle sessies van {p.capitalize()}.")

        return _ui.div(
            _ui.div(source_label, class_="mt-eyebrow", style="margin-bottom:12px;"),
            _ui.div(
                _ui.div(
                    nl_name.upper(),
                    style=(
                        f"font-family:'Sora',sans-serif; font-weight:700; font-size:2rem; "
                        f"letter-spacing:-0.02em; color:{color}; line-height:1;"
                    ),
                ),
                _ui.div(f"ISO — {iso_dir}", class_="mt-body mt-secondary", style="margin-top:4px;"),
                style="margin-bottom:10px;",
            ),
            _ui.div(
                " ".join(reason_parts),
                class_="mt-caption mt-secondary",
                style=(
                    "border-left:2px solid var(--border-default); padding-left:8px; "
                    "font-style:italic;"
                ),
            ),
        )

    # ── Generate ──────────────────────────────────────────────────────────

    @reactive.Effect
    @reactive.event(input.generate_btn)
    def _generate():
        p        = sel()
        bio_row  = _moment_bio()
        date_str = str(bio_row.get("_date_str", "")) if not bio_row.empty else ""

        no_data = bio_row.empty or bio_row.get("_no_data", True)
        if not no_data and app_data.live_model is not None:
            playlist_type, _ = live_recommend(app_data, p, bio_row)
            confidence = 0
        else:
            playlist_type, confidence = best_playlist_for(app_data, p)

        df = _load_playlist(p, playlist_type)
        state = {
            "df":            df,
            "playlist_type": playlist_type,
            "participant":   p,
            "date":          date_str,
            "confidence":    confidence,
        }
        player_state.set(state)
        if now_playing is not None:
            now_playing.set(state)

    # ── Playlist view ─────────────────────────────────────────────────────

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

        caption = _ui.div(
            f"Aanbevolen voor {state['participant'].capitalize()} "
            f"op basis van de biometrische staat op het geselecteerde moment.",
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
                        _ui.div("Navigeer naar Sessie-replay", class_="mt-caption",
                                style="color:var(--accent); margin-top:4px;"),
                        class_="mt-card-elevated",
                        style="padding:16px; cursor:default;",
                    ),
                    _ui.div(
                        _ui.div("Persoonlijke aanbeveling", class_="mt-body"),
                        _ui.div("Bayesiaans model + circadiane context →", class_="mt-caption mt-secondary"),
                        _ui.div("Navigeer naar Aanbevelingen", class_="mt-caption",
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
