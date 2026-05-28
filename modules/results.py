"""Pagina 6 -- Resultaten: Spotify Wrapped-stijl samenvatting per deelnemer."""
import pandas as pd
import plotly.graph_objects as go
from shiny import module, reactive, render, ui as _ui
from shinywidgets import output_widget, render_widget

from utils.chart_helpers import ACCENT, GRID_COLOR, PLAYLIST_COLORS, STRESS_RED, TEXT_SECONDARY, ZERO_COLOR, dark_layout, empty_figure
from utils.data_loader import PARTICIPANTS, AppData, best_playlist_for
from utils.mood_valence import mood_is_improvement


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
    labels_nl = summary["playlist_nl"].tolist()

    # 95% CI = 1.96 × SEM; flag when CI crosses zero
    ci95 = [1.96 * s for s in sems]
    bar_texts = []
    for m, ci, n in zip(means, ci95, counts):
        sign = "+" if m >= 0 else ""
        uncertain = ci > 0 and ((m > 0 and m - ci < 0) or (m < 0 and m + ci > 0) or m == 0)
        suffix = "  ⚠ CI omvat 0" if uncertain else ""
        bar_texts.append(f"{sign}{m:.1f} pt  (N={n}){suffix}")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=means,
        y=labels_nl,
        orientation="h",
        marker=dict(color=[PLAYLIST_COLORS.get(p, ACCENT) for p in playlists]),
        error_x=dict(type="data", array=ci95, color=TEXT_SECONDARY, thickness=1.5, width=6),
        text=bar_texts,
        textposition="outside",
        textfont=dict(color=TEXT_SECONDARY, size=11),
        hovertemplate=(
            "<b>%{y}</b><br>Gem. stemmingsverbetering: %{x:.2f} pt<br>"
            "N=%{customdata} sessies<extra></extra>"
        ),
        customdata=counts,
    ))
    fig.add_vline(x=0, line_dash="dash", line_color="rgba(0,0,0,0.18)", line_width=1.5)

    fig.update_layout(**dark_layout(
        xaxis=dict(title="Gem. stemmingsverbetering (pt)", zeroline=False, gridcolor=GRID_COLOR),
        yaxis=dict(gridcolor="rgba(0,0,0,0)"),
        height=200,
        margin=dict(l=80, r=160, t=16, b=40),
        bargap=0.35,
    ))
    return fig


def _longitudinal_chart(p: str, feature_matrix: pd.DataFrame) -> go.Figure:
    if feature_matrix.empty or "participant" not in feature_matrix.columns:
        return empty_figure("Geen longitudinale data beschikbaar")

    df = feature_matrix[feature_matrix["participant"] == p].copy()
    if df.empty or "session_number" not in df.columns or "pre_study_stress_deviation" not in df.columns:
        return empty_figure("Geen longitudinale stressdata beschikbaar")

    df["pre_study_stress_deviation"] = pd.to_numeric(df["pre_study_stress_deviation"], errors="coerce")
    df = df.sort_values("session_number").dropna(subset=["pre_study_stress_deviation"])
    if df.empty:
        return empty_figure("Geen pre-studie stressafwijkingdata")

    pl_colors = {"Calm": "#3b82f6", "Neutral": "#a855f7", "Energy": "#f97316"}
    point_colors = [pl_colors.get(str(pl), ACCENT)
                    for pl in (df["playlist"] if "playlist" in df.columns else ["Energy"] * len(df))]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["session_number"],
        y=df["pre_study_stress_deviation"],
        mode="lines+markers",
        line=dict(color=TEXT_SECONDARY, width=1.5),
        marker=dict(size=10, color=point_colors, line=dict(width=1.5, color="rgba(0,0,0,0.15)")),
        hovertemplate="Sessie %{x}: %{y:+.1f} t.o.v. pre-studie basislijn<extra></extra>",
    ))
    fig.add_hline(y=0, line_dash="dash", line_color=ZERO_COLOR, line_width=1.5)

    fig.update_layout(**dark_layout(
        xaxis=dict(title="Sessienummer", dtick=1, gridcolor=GRID_COLOR),
        yaxis=dict(title="Stressafwijking (stresspunten)", gridcolor=GRID_COLOR, zeroline=False),
        height=260,
        margin=dict(l=80, r=48, t=16, b=40),
        showlegend=False,
    ))
    return fig


def _compute_summary(p: str, app_data: AppData) -> dict:
    bio = app_data.session_biometrics.get(p, pd.DataFrame())
    sf  = app_data.session_features.get(p, pd.DataFrame())
    hb  = app_data.hourly_baselines.get(p, pd.DataFrame())

    result = dict(sessions_completed=0, study_weeks=0, avg_mood_lift=None, best_playlist=None,
                  best_playlist_confidence=None, recovery_advantage=None,
                  golden_hour=None, peak_window=None, completion_pct=None,
                  _participant=p)

    if not bio.empty:
        result["sessions_completed"] = len(bio)
        if "date" in bio.columns:
            dates = pd.to_datetime(bio["date"], errors="coerce").dropna()
            if len(dates) > 1:
                result["study_weeks"] = max(1, round((dates.max() - dates.min()).days / 7))
            elif len(dates) == 1:
                result["study_weeks"] = 1
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
        # Restrict to waking hours (6-23) to exclude sleep/watch-removed readings
        hb_waking = hb[hb["hour"].between(6, 23)]
        if hb_waking.empty:
            hb_waking = hb
        result["golden_hour"] = f"{int(hb_waking.loc[hb_waking['mean_stress'].idxmin(), 'hour'])}:00"
        peak_h = int(hb_waking.loc[hb_waking["mean_stress"].idxmax(), "hour"])
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


def _stat_card_colored(label: str, value: str, sub: str = "", color: str = "var(--accent)") -> _ui.Tag:
    return _ui.div(
        _ui.div(value,
                style=f"font-family:'Sora',sans-serif; font-weight:700; font-size:2rem; "
                      f"color:{color}; line-height:1; margin-bottom:6px;"),
        _ui.div(label, class_="mt-stat-label"),
        _ui.div(sub, class_="mt-caption", style="color:var(--text-tertiary); margin-top:4px;") if sub else _ui.div(),
        class_="mt-stat-card",
        style=f"border-left-color:{color};",
    )


def _stat_grid(summary: dict, playlist_color: str, app_data=None) -> _ui.Tag:
    sessions = str(summary["sessions_completed"]) if summary["sessions_completed"] else "—"

    mood_val = "—"
    mood_color = "var(--accent)"
    if summary["avg_mood_lift"] is not None:
        m = summary["avg_mood_lift"]
        mood_val = f"+{m:.1f} pt" if m >= 0 else f"{m:.1f} pt"
        mood_color = "var(--accent)" if m >= 0 else "var(--stress-red)"

    bp     = summary["best_playlist"] or "—"
    bp_nl  = _PLAYLIST_NL.get(bp, bp)
    bp_conf = f"{summary['best_playlist_confidence']}% relatieve voorkeur" if summary["best_playlist_confidence"] else "pre-berekend"

    _PL_COLORS = {"Calm": "#3b82f6", "Neutral": "#a855f7", "Energy": "#f97316"}
    bp_color   = _PL_COLORS.get(bp, "var(--accent)")

    weeks     = summary.get("study_weeks", 0)
    weeks_str = f"{weeks} wk" if weeks else "—"

    return _ui.div(
        _stat_card_colored("Aanbevolen afspeellijst", bp_nl.upper() if bp != "—" else "—",
                           bp_conf, color=bp_color),
        _stat_card_colored("Gem. stemmingsverbetering", mood_val,
                           "per sessie gemiddeld", color=mood_color),
        _stat_card("Voltooide sessies", sessions, "totaal"),
        _stat_card("Studieduur", weeks_str, "weken actief"),
        style="display:grid; grid-template-columns:repeat(4,1fr); gap:16px;",
    )


def _session_table(bio_df: pd.DataFrame) -> _ui.Tag:
    """Per-session breakdown table."""
    if bio_df.empty:
        return _ui.div()

    df = bio_df.copy()
    needed = {"date", "playlist"}
    if not needed.issubset(df.columns):
        return _ui.div()

    for col in ("mood_before_score", "mood_after_score", "pre_stress_mean", "mood_before", "mood_after"):
        if col not in df.columns:
            df[col] = float("nan") if col.endswith("_score") or col == "pre_stress_mean" else "—"

    df["mood_before_score"] = pd.to_numeric(df["mood_before_score"], errors="coerce")
    df["mood_after_score"]  = pd.to_numeric(df["mood_after_score"],  errors="coerce")
    df["pre_stress_mean"]   = pd.to_numeric(df["pre_stress_mean"],   errors="coerce")
    df["_delta"] = df["mood_after_score"] - df["mood_before_score"]
    df = df.sort_values("date")

    header = _ui.tags.thead(
        _ui.tags.tr(
            _ui.tags.th("Datum"),
            _ui.tags.th("Afspeellijst"),
            _ui.tags.th("Stemming voor"),
            _ui.tags.th("Stemming na"),
            _ui.tags.th("Delta"),
            _ui.tags.th("Pre-stress"),
            _ui.tags.th("Resultaat"),
        )
    )

    rows = []
    for _, row in df.iterrows():
        pl_en   = str(row.get("playlist", "—")).strip()
        pl_nl   = _PLAYLIST_NL.get(pl_en, pl_en)
        _PL_COLORS = {"Calm": "#3b82f6", "Neutral": "#a855f7", "Energy": "#f97316"}
        pl_color   = _PL_COLORS.get(pl_en, "var(--accent)")

        date_str = str(row.get("date", ""))[:10]
        before   = row["mood_before_score"]
        after    = row["mood_after_score"]
        delta    = row["_delta"]
        stress   = row["pre_stress_mean"]

        def _fmt(v, fmt=".0f"):
            return f"{v:{fmt}}" if pd.notna(v) else "—"

        delta_str  = (f"+{delta:.1f}" if delta >= 0 else f"{delta:.1f}") if pd.notna(delta) else "—"
        # Use composite mood (valence × intensity) to determine improvement direction
        improved = mood_is_improvement(
            row.get("mood_before", ""), row["mood_before_score"],
            row.get("mood_after",  ""), row["mood_after_score"],
        )
        if improved is True:
            delta_color  = "#22c55e"
            result_str   = "✓ Verbeterd"
        elif improved is False:
            delta_color  = "#ef4444"
            result_str   = "✗ Gedaald"
        else:
            delta_color  = "rgba(255,255,255,0.4)"
            result_str   = "– Gelijk"
        result_color = delta_color

        rows.append(_ui.tags.tr(
            _ui.tags.td(date_str, style="color:var(--text-secondary);"),
            _ui.tags.td(_ui.span(pl_nl, style=f"color:{pl_color}; font-weight:500;")),
            _ui.tags.td(_fmt(before)),
            _ui.tags.td(_fmt(after)),
            _ui.tags.td(_ui.span(delta_str, style=f"color:{delta_color}; font-weight:600;")),
            _ui.tags.td(_fmt(stress)),
            _ui.tags.td(_ui.span(result_str, style=f"color:{result_color}; font-size:11px;")),
        ))

    return _ui.div(
        _ui.div("Sessieoverzicht", class_="mt-h2", style="margin-bottom:8px;"),
        _ui.div(
            "Elke sessie · stemming voor en na · delta = na − voor · "
            "✓/✗ gebaseerd op emotievalentie (negatieve emoties: lagere intensiteit = beter)",
            class_="mt-caption mt-secondary", style="margin-bottom:16px;",
        ),
        _ui.div(
            _ui.tags.table(header, _ui.tags.tbody(*rows), class_="mt-session-table"),
            style="overflow-x:auto;",
        ),
        class_="mt-section-card",
    )


# ---------------------------------------------------------------------------
# Module UI
# ---------------------------------------------------------------------------

@module.ui
def ui():
    return _ui.div(
        # Wrapped-hero koptekst
        _ui.div(
            _ui.output_ui("results_headline"),
            class_="mt-wrapped-hero",
        ),

        # Statistiekenraster
        _ui.div(
            _ui.output_ui("stat_grid_ui"),
            style="padding:0 var(--page-margin);",
        ),

        # Grafiek afspeellijsteffectiviteit
        _ui.div(
            _ui.div(
                _ui.div("Stemmingsverbetering per afspeellijsttype", class_="mt-h2",
                        style="margin-bottom:8px;"),
                _ui.div("Gemiddelde stemmingsdelta (na − voor) per afspeellijsttype",
                        class_="mt-caption mt-secondary", style="margin-bottom:4px;"),
                output_widget("effectiveness_chart"),
                _ui.div(
                    "Foutbalken = 95% betrouwbaarheidsinterval (1.96 × SEM). "
                    "⚠ CI omvat 0 = onvoldoende data voor positief effect. "
                    "Hover voor N sessies.",
                    class_="mt-caption mt-secondary",
                    style="margin-top:8px; font-style:italic;",
                ),
                _ui.output_ui("chart_footnote"),
                class_="mt-section-card",
            ),
            style="padding:24px var(--page-margin) 0;",
        ),

        # Longitudinale stresstrend
        _ui.div(
            _ui.div(
                _ui.div("Stressontwikkeling over de studieperiode", class_="mt-h2",
                        style="margin-bottom:8px;"),
                _ui.div(
                    "Stressafwijking t.o.v. pre-studie basislijn per sessie · "
                    "kleur = afspeellijsttype (blauw=kalm, paars=neutraal, oranje=energiek)",
                    class_="mt-caption mt-secondary", style="margin-bottom:16px;",
                ),
                output_widget("longitudinal_chart"),
                _ui.div(
                    "Een dalende trend suggereert dat herhaald gebruik de stressregulatie verbetert. "
                    "Hoge variatie of een stijgende trend duidt op grote dag-tot-dag fluctuatie.",
                    class_="mt-caption mt-secondary",
                    style="margin-top:8px; font-style:italic;",
                ),
                class_="mt-section-card",
            ),
            style="padding:16px var(--page-margin) 0;",
        ),

        # Sessieoverzicht tabel
        _ui.div(
            _ui.output_ui("session_table_ui"),
            style="padding:16px var(--page-margin) 0;",
        ),

        # Eerlijk beeld: betekenis van de resultaten
        _ui.div(
            _ui.output_ui("honest_framing_ui"),
            style="padding:16px var(--page-margin) 0;",
        ),

    )


# ---------------------------------------------------------------------------
# Module server
# ---------------------------------------------------------------------------

@module.server
def server(input, output, session, app_data: AppData, selected_participant=None):
    selected = selected_participant if selected_participant is not None else reactive.Value("bosbes")

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
    @render_widget
    def longitudinal_chart():
        return _longitudinal_chart(selected(), app_data.feature_matrix)

    @output
    @render.ui
    def session_table_ui():
        p   = selected()
        bio = app_data.session_biometrics.get(p, pd.DataFrame())
        return _session_table(bio)

    @output
    @render.ui
    def honest_framing_ui():
        p   = selected()
        bio = app_data.session_biometrics.get(p, pd.DataFrame())
        if bio.empty:
            return _ui.div()
        delta_vals = (
            pd.to_numeric(bio["mood_after_score"],  errors="coerce") -
            pd.to_numeric(bio["mood_before_score"], errors="coerce")
        ).dropna()
        if delta_vals.empty:
            return _ui.div()
        avg = delta_vals.mean()
        std = delta_vals.std()
        n   = len(delta_vals)
        sign = "+" if avg >= 0 else ""

        # Find best playlist by mean delta for this participant
        best_pl_str = ""
        if "playlist" in bio.columns and "mood_before_score" in bio.columns and "mood_after_score" in bio.columns:
            bio2 = bio.copy()
            bio2["_delta"] = (
                pd.to_numeric(bio2["mood_after_score"],  errors="coerce") -
                pd.to_numeric(bio2["mood_before_score"], errors="coerce")
            )
            pl_avgs = bio2.groupby("playlist")["_delta"].mean().dropna()
            if not pl_avgs.empty:
                best_pl_en = pl_avgs.idxmax()
                best_pl_nl = _PLAYLIST_NL.get(best_pl_en, best_pl_en)
                best_val   = pl_avgs[best_pl_en]
                best_sign  = "+" if best_val >= 0 else ""
                best_pl_str = (
                    f" Hoogste gemiddelde stemmingswinst voor {p.capitalize()}: "
                    f"{best_pl_nl} ({best_sign}{best_val:.1f} pt)."
                )

        return _ui.div(
            _ui.div("Wat betekent dit?", class_="mt-h3", style="margin-bottom:8px;"),
            _ui.div(
                f"Over {n} sessies gemiddeld: {sign}{avg:.1f} pt ± {std:.1f}.{best_pl_str}",
                class_="mt-body",
            ),
            _ui.div(
                "Het beste ML-model (Gradient Boosting, R²=0.41 op groepsniveau, N=40 sessies totaal) "
                "verklaart een deel van de stemmingsvariatie — maar N=40 is exploratief. "
                "Patronen zijn richtinggevend, geen bewijs.",
                class_="mt-body mt-secondary",
                style="margin-top:6px;",
            ),
            class_="mt-section-card",
            style="border-left:4px solid var(--accent); padding:16px 20px;",
        )

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
