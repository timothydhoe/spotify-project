"""Pagina 6 -- Resultaten: Spotify Wrapped-stijl samenvatting per deelnemer."""
import pandas as pd
import plotly.graph_objects as go
from shiny import module, reactive, render, ui as _ui
from shinywidgets import output_widget, render_widget

from utils.chart_helpers import ACCENT, GRID_COLOR, PLAYLIST_COLORS, STRESS_RED, TEXT_SECONDARY, dark_layout, empty_figure
from utils.data_loader import PARTICIPANTS, AppData, best_playlist_for


def _effectiveness_chart(bio_df: pd.DataFrame) -> go.Figure:
    if bio_df.empty or "playlist" not in bio_df.columns:
        return empty_figure("Geen sessiedata beschikbaar")

    if "mood_delta" in bio_df.columns:
        delta_col = "mood_delta"
    elif "mood_before_score" in bio_df.columns and "mood_after_score" in bio_df.columns:
        bio_df = bio_df.copy()
        bio_df["mood_delta"] = (
            pd.to_numeric(bio_df["mood_after_score"],  errors="coerce") -
            pd.to_numeric(bio_df["mood_before_score"], errors="coerce")
        )
        delta_col = "mood_delta"
    else:
        return empty_figure("Geen stemmingsdata beschikbaar")

    summary = (
        bio_df.groupby("playlist")[delta_col]
        .agg(mean="mean", sem="sem", count="count")
        .reset_index()
        .sort_values("mean", ascending=True)
    )

    nl_map = {"Calm": "Kalm", "Neutral": "Neutraal", "Energy": "Energiek"}
    summary["playlist_nl"] = summary["playlist"].map(lambda x: nl_map.get(x, x))

    playlists = summary["playlist"].tolist()
    means     = summary["mean"].tolist()
    sems      = summary["sem"].fillna(0).tolist()
    counts    = summary["count"].tolist()
    colors    = [PLAYLIST_COLORS.get(p, ACCENT) for p in playlists]
    labels_nl = summary["playlist_nl"].tolist()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=means,
        y=labels_nl,
        orientation="h",
        marker_color=colors,
        error_x=dict(type="data", array=sems, color=TEXT_SECONDARY, thickness=1.5, width=6),
        text=[f"+{m:.1f}" if m >= 0 else f"{m:.1f}" for m in means],
        textposition="outside",
        textfont=dict(color=TEXT_SECONDARY, size=12),
        hovertemplate="<b>%{y}</b><br>Gem. stemmingsverbetering: %{x:.2f} pt<br>N=%{customdata} sessies<extra></extra>",
        customdata=counts,
    ))

    fig.update_layout(**dark_layout(
        xaxis=dict(title="Gem. stemmingsverbetering (pt)", zeroline=True,
                   zerolinecolor="rgba(255,255,255,0.15)", gridcolor=GRID_COLOR),
        yaxis=dict(gridcolor="rgba(0,0,0,0)"),
        height=200,
        margin=dict(l=80, r=48, t=16, b=40),
        bargap=0.35,
    ))
    return fig


def _compute_summary(p: str, app_data: AppData) -> dict:
    bio = app_data.session_biometrics.get(p, pd.DataFrame())
    sf  = app_data.session_features.get(p, pd.DataFrame())
    hb  = app_data.hourly_baselines.get(p, pd.DataFrame())

    result = dict(sessions_completed=0, avg_mood_lift=None, best_playlist=None,
                  best_playlist_confidence=None, recovery_advantage=None,
                  golden_hour=None, peak_window=None, completion_pct=None,
                  _participant=p)

    if not bio.empty:
        result["sessions_completed"] = len(bio)
        if "mood_before_score" in bio.columns and "mood_after_score" in bio.columns:
            delta = (
                pd.to_numeric(bio["mood_after_score"],  errors="coerce") -
                pd.to_numeric(bio["mood_before_score"], errors="coerce")
            )
            result["avg_mood_lift"] = delta.mean()

    if app_data.recommendations.get(p):
        playlist, conf = best_playlist_for(app_data, p)
        result["best_playlist"]            = playlist
        result["best_playlist_confidence"] = conf

    if not sf.empty and "tau_advantage" in sf.columns:
        ta = pd.to_numeric(sf["tau_advantage"], errors="coerce").dropna()
        if not ta.empty:
            result["recovery_advantage"] = ta.mean()

    if not hb.empty and "hour" in hb.columns and "mean_stress" in hb.columns:
        result["golden_hour"] = f"{int(hb.loc[hb['mean_stress'].idxmin(), 'hour'])}:00"
        peak_h = int(hb.loc[hb["mean_stress"].idxmax(), "hour"])
        result["peak_window"] = f"{peak_h}-{peak_h + 2}:00"

    return result


_PLAYLIST_NL = {"Calm": "Kalm", "Neutral": "Neutraal", "Energy": "Energiek"}


def _stat_card(label: str, value: str, sub: str = "", value_class: str = "mt-stat-value") -> _ui.Tag:
    return _ui.div(
        _ui.div(value, class_=value_class),
        _ui.div(label, class_="mt-stat-label"),
        _ui.div(sub, class_="mt-caption", style="color:var(--text-tertiary); margin-top:4px;") if sub else _ui.div(),
        class_="mt-stat-card",
    )


def _stat_grid(summary: dict, playlist_color: str, app_data=None) -> _ui.Tag:
    sessions = str(summary["sessions_completed"]) if summary["sessions_completed"] else "—"

    mood_val = "—"
    if summary["avg_mood_lift"] is not None:
        m = summary["avg_mood_lift"]
        mood_val = f"+{m:.1f} pt" if m >= 0 else f"{m:.1f} pt"

    n = summary["sessions_completed"]
    fm = app_data.feature_matrix
    p_name = summary.get("_participant", "")
    if not fm.empty and "participant" in fm.columns and p_name:
        expected = int(fm[fm["participant"] == p_name].shape[0])
    else:
        expected = n or 0
    comp_pct = f"{round(n / expected * 100)}%" if (n and expected) else "—"
    comp_sub = f"{n} van {expected} sessies" if (n and expected) else ""

    adv = "—"
    if summary["recovery_advantage"] is not None:
        a   = summary["recovery_advantage"]
        adv = f"+{a:.0f} min" if a >= 0 else f"{a:.0f} min"

    golden = summary["golden_hour"] or "—"
    peak   = summary["peak_window"]  or "—"

    bp    = summary["best_playlist"] or "—"
    bp_nl = _PLAYLIST_NL.get(bp, bp)
    bp_conf = f"{summary['best_playlist_confidence']}% posterior" if summary["best_playlist_confidence"] else ""

    return _ui.div(
        # Rij 1
        _ui.div(
            _stat_card("Voltooide sessies",        sessions,   "totaal"),
            _stat_card("Gem. stemmingsverbetering", mood_val,  "per sessie gemiddeld"),
            _stat_card("Voltooiingspercentage",     comp_pct,  comp_sub),
            style="display:grid; grid-template-columns:repeat(3,1fr); gap:16px;",
        ),
        # Rij 2
        _ui.div(
            _stat_card("Herstelvoordeel",       adv,    "sneller dan jouw basislijn"),
            _stat_card("Jouw Gouden Uur",       golden, "Laagste stress"),
            _stat_card("Piekstressvenster",     peak,   "Vermijd zware taken",
                       value_class="mt-h2 mt-red"),
            style="display:grid; grid-template-columns:repeat(3,1fr); gap:16px; margin-top:16px;",
        ),
    )


# ---------------------------------------------------------------------------
# Module UI
# ---------------------------------------------------------------------------

@module.ui
def ui():
    return _ui.div(
        # Deelnemersselector
        _ui.div(
            _ui.output_ui("participant_pills"),
            style="padding:48px 80px 0; text-align:center;",
        ),

        # Wrapped-hero koptekst
        _ui.div(
            _ui.output_ui("results_headline"),
            class_="mt-wrapped-hero",
        ),

        # Statistiekenraster
        _ui.div(
            _ui.output_ui("stat_grid_ui"),
            style="padding:0 80px;",
        ),

        # Grafiek afspeellijsteffectiviteit
        _ui.div(
            _ui.div(
                _ui.div("Stemmingsverbetering per afspeellijsttype", class_="mt-h2",
                        style="margin-bottom:8px;"),
                _ui.div("Gemiddelde stemmingsdelta (na - voor) per type - hover voor N sessies",
                        class_="mt-caption mt-secondary", style="margin-bottom:16px;"),
                output_widget("effectiveness_chart"),
                _ui.output_ui("chart_footnote"),
                class_="mt-section-card",
            ),
            style="padding:24px 80px 0;",
        ),

        # Wrapped-tagline
        _ui.div("\"Jouw muziek is jouw medicijn.\"", class_="mt-wrapped-tagline"),
    )


# ---------------------------------------------------------------------------
# Module server
# ---------------------------------------------------------------------------

@module.server
def server(input, output, session, app_data: AppData):
    selected = reactive.Value("bosbes")

    @output
    @render.ui
    def participant_pills():
        pills = []
        for p in PARTICIPANTS:
            has       = app_data.has_sessions.get(p) or app_data.has_features.get(p)
            is_active = (p == selected())
            cls = "pill-btn" + (" active" if is_active else "") + ("" if has else " disabled")
            btn = _ui.input_action_button(f"wpill_{p}", p.capitalize(), class_=cls)
            if not has:
                btn = _ui.tags.span(btn, title="Geen sessiedata voor deze deelnemer")
            pills.append(btn)
        return _ui.div(*pills, class_="pill-group", style="justify-content:center;")

    for _p in PARTICIPANTS:
        def _obs(participant=_p):
            @reactive.Effect
            @reactive.event(input[f"wpill_{participant}"])
            def _():
                selected.set(participant)
        _obs()

    @reactive.Calc
    def summary():
        return _compute_summary(selected(), app_data)

    @output
    @render.ui
    def results_headline():
        p   = selected()
        bio = app_data.session_biometrics.get(p, pd.DataFrame())
        n   = len(bio) if not bio.empty else 0
        return _ui.TagList(
            _ui.div(f"R.E.M.-profiel van {p.capitalize()}", class_="mt-h1"),
            _ui.div(f"{n} sessies - Project R.E.M.", class_="mt-body mt-secondary",
                    style="margin-top:6px;"),
        )

    @output
    @render.ui
    def stat_grid_ui():
        p = selected()
        if not app_data.has_sessions.get(p) and not app_data.has_features.get(p):
            return _ui.div(
                _ui.div("Geen data beschikbaar voor deze deelnemer.",
                        class_="mt-body mt-secondary"),
                class_="mt-no-data",
            )
        s = summary()
        return _stat_grid(s, PLAYLIST_COLORS.get(s.get("best_playlist") or "Energy", ACCENT), app_data=app_data)

    @output
    @render_widget
    def effectiveness_chart():
        p   = selected()
        bio = app_data.session_biometrics.get(p, pd.DataFrame())
        sf  = app_data.session_features.get(p, pd.DataFrame())
        return _effectiveness_chart(bio if not bio.empty else sf)

    @output
    @render.ui
    def chart_footnote():
        p   = selected()
        bio = app_data.session_biometrics.get(p, pd.DataFrame())
        sf  = app_data.session_features.get(p, pd.DataFrame())
        df  = bio if not bio.empty else sf
        if df.empty or "playlist" not in df.columns:
            return _ui.div()

        notes = []
        delta_col = None
        if "mood_delta" in df.columns:
            delta_col = "mood_delta"
        elif "mood_before_score" in df.columns and "mood_after_score" in df.columns:
            df = df.copy()
            df["mood_delta"] = (
                pd.to_numeric(df["mood_after_score"],  errors="coerce") -
                pd.to_numeric(df["mood_before_score"], errors="coerce")
            )
            delta_col = "mood_delta"

        if delta_col:
            for playlist, grp in df.groupby("playlist"):
                n   = grp[delta_col].notna().sum()
                avg = pd.to_numeric(grp[delta_col], errors="coerce").mean()
                nl  = {"Calm": "Kalm", "Neutral": "Neutraal", "Energy": "Energiek"}.get(playlist, playlist)
                if n <= 3:
                    notes.append(f"{nl}: N={n} — kleine steekproef, zorgvuldig interpreteren.")
                elif pd.notna(avg) and avg < -0.5:
                    notes.append(f"{nl}: negatieve delta ({avg:+.1f} pt) — mogelijke voorkeur voor dit type ontbreekt of N is klein.")

        if not notes:
            return _ui.div()

        return _ui.div(
            *[_ui.div(f"⚠ {note}", class_="mt-caption",
                      style="color:#f59e0b; margin-top:4px;") for note in notes],
            style="margin-top:8px;",
        )
