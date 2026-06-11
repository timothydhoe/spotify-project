"""Pagina 6 -- Resultaten: Spotify Wrapped-stijl samenvatting per deelnemer."""
import pandas as pd
import plotly.graph_objects as go
from shiny import module, reactive, render, ui as _ui
from shinywidgets import output_widget, render_widget

from utils.chart_helpers import ACCENT, GRID_COLOR, PLAYLIST_COLORS, STRESS_RED, TEXT_SECONDARY, ZERO_COLOR, chart_layout, empty_figure
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

    ci95 = [1.96 * s for s in sems]
    bar_texts = []
    for m, ci, n in zip(means, ci95, counts):
        sign = "+" if m >= 0 else ""
        uncertain = ci > 0 and ((m > 0 and m - ci < 0) or (m < 0 and m + ci > 0) or m == 0)
        suffix = "  ⚠ CI omvat 0" if uncertain else ""
        bar_texts.append(f"{sign}{m:.1f} pt  (N={n}){suffix}")

    fig = go.Figure()

    # 3.2 Color zones — negative (red tint) and positive (green tint) regions
    x_max = max(abs(m) for m in means) * 1.6 + 1
    fig.add_vrect(x0=-x_max, x1=0, fillcolor="rgba(239,68,68,0.04)", line_width=0)
    fig.add_vrect(x0=0, x1=x_max, fillcolor="rgba(34,197,94,0.04)", line_width=0)

    # Mean bars
    fig.add_trace(go.Bar(
        x=means,
        y=labels_nl,
        orientation="h",
        marker=dict(
            color=[PLAYLIST_COLORS.get(p, ACCENT) for p in playlists],
            opacity=0.55,
        ),
        error_x=dict(type="data", array=ci95, color=TEXT_SECONDARY, thickness=1.5, width=6),
        text=bar_texts,
        textposition="outside",
        textfont=dict(color=TEXT_SECONDARY, size=11),
        hovertemplate=(
            "<b>%{y}</b><br>Gem. stemmingsverbetering: %{x:.2f} pt<br>"
            "N=%{customdata} sessies<extra></extra>"
        ),
        customdata=counts,
        name="Gemiddelde",
        showlegend=False,
    ))

    # 3.2 Individual session dots (jittered along y-axis within each bar)
    import numpy as np
    rng = np.random.default_rng(seed=42)
    for pl, nl in zip(playlists, labels_nl):
        pl_data = bio_df[bio_df["playlist"] == pl][delta_col].dropna()
        if pl_data.empty:
            continue
        jitter = rng.uniform(-0.2, 0.2, len(pl_data))
        color  = PLAYLIST_COLORS.get(pl, ACCENT)
        date_col = bio_df[bio_df["playlist"] == pl]["date"].astype(str).str[:10] if "date" in bio_df.columns else ["—"] * len(pl_data)
        fig.add_trace(go.Scatter(
            x=pl_data.values,
            y=[nl] * len(pl_data),
            mode="markers",
            marker=dict(
                color=color, size=8, opacity=0.85,
                line=dict(color="rgba(255,255,255,0.20)", width=1),
                symbol="circle",
            ),
            yaxis="y",
            name=nl,
            showlegend=False,
            hovertemplate=(
                f"<b>{nl}</b> — %{{x:+.1f}} pt<extra></extra>"
            ),
            customdata=list(date_col) if hasattr(date_col, '__iter__') else ["—"] * len(pl_data),
        ))

    fig.add_vline(x=0, line_dash="dash", line_color="rgba(255,255,255,0.18)", line_width=1.5)

    fig.update_layout(**chart_layout(
        xaxis=dict(title="Stemmingsverbetering (pt)", zeroline=False, gridcolor=GRID_COLOR, range=[-x_max, x_max]),
        yaxis=dict(gridcolor="rgba(0,0,0,0)"),
        height=220,
        margin=dict(l=80, r=160, t=16, b=40),
        bargap=0.4,
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

    pl_colors = {"Calm": "#56B4E9", "Neutral": "#009E73", "Energy": "#E69F00"}
    nl_map    = {"Calm": "Kalm", "Neutral": "Neutraal", "Energy": "Energiek"}
    playlists = df["playlist"].tolist() if "playlist" in df.columns else ["Energy"] * len(df)
    point_colors = [pl_colors.get(str(pl), ACCENT) for pl in playlists]

    # 3.3 Add date + playlist + mood_delta to customdata for click interactions
    dates  = df["date"].astype(str).str[:10].tolist() if "date" in df.columns else ["—"] * len(df)
    deltas = (
        pd.to_numeric(df["mood_delta"], errors="coerce").tolist()
        if "mood_delta" in df.columns
        else [float("nan")] * len(df)
    )
    pl_nl  = [nl_map.get(str(pl), str(pl)) for pl in playlists]

    customdata = list(zip(dates, pl_nl, deltas, df["session_number"].tolist()))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["session_number"],
        y=df["pre_study_stress_deviation"],
        mode="lines+markers",
        line=dict(color=TEXT_SECONDARY, width=1.5),
        marker=dict(size=11, color=point_colors, line=dict(width=1.5, color="rgba(255,255,255,0.15)")),
        customdata=customdata,
        hovertemplate=(
            "<b>Sessie %{customdata[3]}</b> — %{customdata[0]}<br>"
            "Afspeellijst: %{customdata[1]}<br>"
            "Stressafwijking: %{y:+.1f} pt<br>"
            "Stemmingsdelta: %{customdata[2]:+.1f} pt<br>"
            "<i>Klik voor details</i><extra></extra>"
        ),
    ))
    fig.add_hline(y=0, line_dash="dash", line_color=ZERO_COLOR, line_width=1.5)

    fig.update_layout(**chart_layout(
        xaxis=dict(title="Sessienummer", dtick=1, gridcolor=GRID_COLOR),
        yaxis=dict(title="Stressafwijking (stresspunten)", gridcolor=GRID_COLOR, zeroline=False),
        height=280,
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
        _ui.div(value, class_="mt-stat-value", style=f"color:{color};"),
        _ui.div(label, class_="mt-stat-label"),
        _ui.div(sub, class_="mt-caption mt-tertiary", style="margin-top:4px;") if sub else _ui.div(),
        class_="mt-stat-card",
    )


def _metric_chip(label: str, value: str, sub: str = "", color: str = "var(--text-primary)") -> _ui.Tag:
    return _ui.div(
        _ui.div(value, class_="mt-metric-chip-value", style=f"color:{color};"),
        _ui.div(label, class_="mt-metric-chip-label"),
        _ui.div(sub,   class_="mt-metric-chip-sub") if sub else _ui.div(),
        class_="mt-metric-chip",
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

    _PL_COLORS = {"Calm": "var(--calm-color)", "Neutral": "var(--neutral-color)", "Energy": "var(--energy-color)"}
    bp_color   = _PL_COLORS.get(bp, "var(--accent)")

    weeks     = summary.get("study_weeks", 0)
    weeks_str = f"{weeks} wk" if weeks else "—"

    recovery_val = "—"
    recovery_sub = "herstel t.o.v. basislijn"
    p = summary.get("_participant")
    if app_data and p:
        sf = app_data.session_features.get(p, pd.DataFrame())
        if not sf.empty and "tau_advantage" in sf.columns and "r2_actual" in sf.columns:
            valid = sf[pd.to_numeric(sf["r2_actual"], errors="coerce") > 0.05]["tau_advantage"]
            valid = pd.to_numeric(valid, errors="coerce").dropna()
            if not valid.empty:
                adv = valid.mean()
                recovery_val = f"+{adv:.0f} min" if adv >= 0 else f"{adv:.0f} min"
                recovery_sub = f"n={len(valid)} betrouwbare sessies (r²>0.05)"
            else:
                recovery_sub = "onvoldoende betrouwbare sessies"

    return _ui.div(
        _metric_chip("Aanbevolen playlist", bp_nl.upper() if bp != "—" else "—", bp_conf, color=bp_color),
        _metric_chip("Gem. stemmingswinst", mood_val, "per sessie gemiddeld", color=mood_color),
        _metric_chip("Sessies", sessions, "voltooide sessies"),
        _metric_chip("Studieduur", weeks_str, "weken actief"),
        _metric_chip("Herstelvoordeel", recovery_val, recovery_sub),
        class_="mt-metric-strip",
    )


_PAGE_SIZE = 10
_PL_COLORS_SESSION = {"Calm": "#56B4E9", "Neutral": "#009E73", "Energy": "#E69F00"}


def _prepare_session_df(bio_df: pd.DataFrame) -> pd.DataFrame:
    """Clean and sort the session dataframe; returns empty df if unusable."""
    if bio_df.empty:
        return pd.DataFrame()
    df = bio_df.copy()
    if not {"date", "playlist"}.issubset(df.columns):
        return pd.DataFrame()
    for col in ("mood_before_score", "mood_after_score", "pre_stress_mean", "mood_before", "mood_after"):
        if col not in df.columns:
            df[col] = float("nan") if col.endswith("_score") or col == "pre_stress_mean" else "—"
    df["mood_before_score"] = pd.to_numeric(df["mood_before_score"], errors="coerce")
    df["mood_after_score"]  = pd.to_numeric(df["mood_after_score"],  errors="coerce")
    df["pre_stress_mean"]   = pd.to_numeric(df["pre_stress_mean"],   errors="coerce")
    df["_delta"] = df["mood_after_score"] - df["mood_before_score"]
    return df.sort_values("date").reset_index(drop=True)


def _delta_cell(delta, improved: "bool | None" = None) -> _ui.Tag:
    """Delta value + inline proportional bar.

    Color is driven by whether the mood direction was an improvement
    (per mood_is_improvement), not by the raw sign of the delta — because
    some emotion scales are inverted (lower score = better).
    """
    if not pd.notna(delta):
        return _ui.tags.td("—")
    delta_str = f"+{delta:.1f}" if delta >= 0 else f"{delta:.1f}"
    if improved is True:
        bar_color = "#22c55e"
    elif improved is False:
        bar_color = "#ef4444"
    else:
        bar_color = "#9ca3af" if delta == 0 else ("#22c55e" if delta > 0 else "#ef4444")
    bar_width = min(abs(delta) / 5 * 100, 100)
    return _ui.tags.td(
        _ui.div(
            _ui.span(delta_str, style=f"font-weight:600; color:{bar_color}; font-size:0.8125rem;"),
            _ui.div(
                _ui.div(style=(
                    f"width:{bar_width:.0f}%; height:3px; border-radius:2px; "
                    f"background:{bar_color};"
                )),
                style=(
                    "width:56px; height:3px; border-radius:2px; "
                    "background:var(--bg-elevated); overflow:hidden; margin-top:3px;"
                ),
            ),
        ),
        style="min-width:70px;",
    )


def _session_table_rows(df_page: pd.DataFrame) -> list:
    rows = []
    for _, row in df_page.iterrows():
        pl_en    = str(row.get("playlist", "—")).strip()
        pl_nl    = _PLAYLIST_NL.get(pl_en, pl_en)
        pl_color = _PL_COLORS_SESSION.get(pl_en, "var(--accent)")
        date_str = str(row.get("date", ""))[:10]
        before   = row["mood_before_score"]
        after    = row["mood_after_score"]
        delta    = row["_delta"]
        stress   = row["pre_stress_mean"]

        def _fmt(v):
            return f"{v:.0f}" if pd.notna(v) else "—"

        improved = mood_is_improvement(
            row.get("mood_before", ""), row["mood_before_score"],
            row.get("mood_after",  ""), row["mood_after_score"],
        )
        result_str   = "✓ Verbeterd" if improved is True else ("✗ Gedaald" if improved is False else "– Gelijk")
        result_color = "#22c55e"     if improved is True else ("#ef4444"  if improved is False else "#9ca3af")

        rows.append(_ui.tags.tr(
            # Left border coloured by playlist type (Image #8 / #9 pattern)
            _ui.tags.td(date_str, style=(
                f"color:var(--text-secondary); border-left:3px solid {pl_color}; padding-left:12px;"
            )),
            _ui.tags.td(_ui.span(pl_nl, style=f"color:{pl_color}; font-weight:500;")),
            _ui.tags.td(_fmt(before)),
            _ui.tags.td(_fmt(after)),
            _delta_cell(delta, improved),
            _ui.tags.td(_fmt(stress)),
            _ui.tags.td(_ui.span(result_str, style=f"color:{result_color}; font-size:11px;")),
        ))
    return rows


def _session_table(df: pd.DataFrame, page: int) -> _ui.Tag:
    """Per-session breakdown table with pagination (Phase 2-B)."""
    if df.empty:
        return _ui.div()

    total     = len(df)
    n_pages   = max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE)
    page      = max(0, min(page, n_pages - 1))
    start     = page * _PAGE_SIZE
    end       = min(start + _PAGE_SIZE, total)
    df_page   = df.iloc[start:end]

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

    pagination = _ui.div(
        _ui.input_action_button(
            "prev_page", "← Vorige",
            class_="mt-pagination-btn",
            disabled=page == 0,
        ),
        _ui.div(
            f"Sessie {start + 1}–{end} van {total}",
            class_="mt-pagination-info",
        ),
        _ui.input_action_button(
            "next_page", "Volgende →",
            class_="mt-pagination-btn",
            disabled=page >= n_pages - 1,
        ),
        class_="mt-pagination",
    )

    return _ui.div(
        _ui.div(
            _ui.div(
                _ui.div("Sessieoverzicht", class_="mt-h2 mt-section-header-title"),
                _ui.div(
                    "Elke sessie · stemming voor en na · delta = na − voor · "
                    "✓/✗ gebaseerd op emotievalentie",
                    class_="mt-section-header-sub",
                ),
                class_="mt-section-header-left",
            ),
            class_="mt-section-header",
        ),
        _ui.div(
            _ui.tags.table(
                header,
                _ui.tags.tbody(*_session_table_rows(df_page)),
                class_="mt-session-table",
            ),
            style="overflow-x:auto;",
        ),
        pagination,
        class_="mt-section-card",
    )


# ---------------------------------------------------------------------------
# Module UI
# ---------------------------------------------------------------------------

@module.ui
def ui():
    return _ui.div(
        # Hero — transparent, emoji shows through from body-level background
        _ui.div(
            _ui.output_ui("results_headline"),
            class_="mt-page-hero",
            style="padding:0;",
        ),

        # Statistiekenraster
        _ui.div(
            _ui.output_ui("stat_grid_ui"),
            style="padding:0 var(--page-margin);",
        ),

        # Grafiek afspeellijsteffectiviteit (3.2 — beeswarm over bar)
        _ui.div(
            _ui.div(
                _ui.div(
                    _ui.div(
                        _ui.div("Stemmingsverbetering per afspeellijsttype", class_="mt-h2 mt-section-header-title"),
                        _ui.div("Elke stip = één sessie · balk = gemiddelde · foutbalken = 95% BI", class_="mt-section-header-sub"),
                        class_="mt-section-header-left",
                    ),
                    class_="mt-section-header",
                ),
                output_widget("effectiveness_chart"),
                _ui.output_ui("chart_footnote"),
                class_="mt-section-card",
            ),
            style="padding:24px var(--page-margin) 0;",
        ),

        # Longitudinale stresstrend (3.3 — clickable)
        _ui.div(
            _ui.div(
                _ui.div(
                    _ui.div(
                        _ui.div("Stressontwikkeling over de studieperiode", class_="mt-h2 mt-section-header-title"),
                        _ui.div("Stressafwijking t.o.v. pre-studie basislijn · kleur = afspeellijsttype · klik voor sessiedetails", class_="mt-section-header-sub"),
                        class_="mt-section-header-left",
                    ),
                    class_="mt-section-header",
                ),
                _ui.div(
                    output_widget("longitudinal_chart"),
                    id="mt-lon-chart-wrapper",
                ),
                # JS: forward Plotly click → Shiny input (more reliable than FigureWidget.on_click)
                _ui.tags.script(src="js/results.js"),
                _ui.output_ui("lon_session_detail"),
                _ui.div(
                    "Een dalende trend suggereert dat herhaald gebruik de stressregulatie verbetert.",
                    class_="mt-caption mt-secondary",
                    style="margin-top:8px; font-style:italic;",
                ),
                class_="mt-section-card",
            ),
            style="padding:16px var(--page-margin) 0;",
        ),

        # Sessieoverzicht tabel (3.4)
        _ui.div(
            _ui.output_ui("best_session_callout"),
            _ui.output_ui("session_table_ui"),
            style="padding:16px var(--page-margin) 0;",
        ),

        # Persoonlijk beeld (3.5)
        _ui.div(
            _ui.output_ui("honest_framing_ui"),
            style="padding:16px var(--page-margin) 32px;",
        ),
    )


# ---------------------------------------------------------------------------
# Module server
# ---------------------------------------------------------------------------

@module.server
def server(input, output, session, app_data: AppData, selected_participant=None):
    selected         = selected_participant if selected_participant is not None else reactive.Value("bosbes")
    _page            = reactive.Value(0)
    _selected_lon    = reactive.Value(None)   # clicked longitudinal session

    @reactive.Effect
    def _reset_page():
        selected()
        _page.set(0)
        _selected_lon.set(None)

    # ── Longitudinal chart click via JS (Shiny.setInputValue) ──────────────
    @reactive.Effect
    @reactive.event(input.lon_click)
    def _on_lon_click():
        data = input.lon_click()
        if not isinstance(data, dict):
            return
        try:
            _selected_lon.set({
                "date":    str(data.get("date", "—")),
                "pl_nl":   str(data.get("pl_nl", "—")),
                "delta":   float(data["delta"]) if data.get("delta") == data.get("delta") and data.get("delta") is not None else None,
                "session": int(data.get("session", 0)),
                "stress":  float(data.get("stress", 0)),
            })
        except (TypeError, ValueError):
            pass

    @reactive.Effect
    @reactive.event(input.prev_page)
    def _go_prev():
        _page.set(max(0, _page() - 1))

    @reactive.Effect
    @reactive.event(input.next_page)
    def _go_next():
        bio = app_data.session_biometrics.get(selected(), pd.DataFrame())
        df  = _prepare_session_df(bio)
        n_pages = max(1, (len(df) + _PAGE_SIZE - 1) // _PAGE_SIZE)
        _page.set(min(_page() + 1, n_pages - 1))

    @reactive.Calc
    def summary():
        return _compute_summary(selected(), app_data)

    @output
    @render.ui
    def results_headline():
        p   = selected()
        bio = app_data.session_biometrics.get(p, pd.DataFrame())
        n   = len(bio) if not bio.empty else 0
        s   = summary()

        _PL_COLORS = {"Calm": "#56B4E9", "Neutral": "#009E73", "Energy": "#E69F00"}
        _EMOJI     = {"bosbes": "🫐", "kokosnoot": "🥥", "limoen": "🍋",
                      "peer": "🍐", "kiwi": "🥝", "watermeloen": "🍉"}
        bp    = s.get("best_playlist") or "Energy"
        color = _PL_COLORS.get(bp, "var(--text-accent)")
        emoji = _EMOJI.get(p, "🎵")

        mood_hero = _ui.div()
        if s.get("avg_mood_lift") is not None:
            m = s["avg_mood_lift"]
            sign = "+" if m >= 0 else ""
            mood_hero = _ui.div(
                _ui.div(
                    f"{sign}{m:.1f}",
                    style=(
                        f"font-family:'Sora',sans-serif; font-weight:700; font-size:3.5rem; "
                        f"line-height:1; letter-spacing:-0.03em; color:{color};"
                    ),
                ),
                _ui.div(
                    "gem. stemmingsverbetering per sessie",
                    style="font-size:0.8125rem; color:var(--text-secondary); margin-top:4px;",
                ),
                style="margin-top:16px;",
            )

        # 3.1 Emoji background
        return _ui.div(
            _ui.div(
                emoji,
                style=(
                    "position:absolute; font-size:12rem; opacity:0.07; "
                    "top:50%; left:50%; transform:translate(-50%,-50%); "
                    "pointer-events:none; user-select:none;"
                ),
            ),
            _ui.div(
                _ui.div(f"R.E.M.-profiel van {p.capitalize()}", class_="mt-h1"),
                _ui.div(f"{n} sessies · Project R.E.M.", class_="mt-body mt-secondary",
                        style="margin-top:6px;"),
                mood_hero,
                style="position:relative; z-index:1;",
            ),
            style=(
                "position:relative; overflow:hidden; text-align:center; "
                "padding:80px var(--page-margin) 64px;"
            ),
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
        import plotly.graph_objects as go
        fig = _longitudinal_chart(selected(), app_data.feature_matrix)
        fw  = go.FigureWidget(fig)

        def _on_click(trace, points, selector):
            if not points.point_inds:
                return
            idx = points.point_inds[0]
            cd  = trace.customdata[idx]
            _selected_lon.set({
                "date":    str(cd[0]),
                "pl_nl":   str(cd[1]),
                "delta":   float(cd[2]) if cd[2] == cd[2] else None,
                "session": int(cd[3]),
                "stress":  float(trace.y[idx]),
            })

        for tr in fw.data:
            if hasattr(tr, "on_click"):
                tr.on_click(_on_click)
        return fw

    @output
    @render.ui
    def lon_session_detail():
        sel_s = _selected_lon()
        if sel_s is None:
            return _ui.div()
        delta_str = f"{sel_s['delta']:+.1f} pt" if sel_s.get("delta") is not None else "—"
        delta_color = (
            "#22c55e" if sel_s.get("delta") and sel_s["delta"] > 0
            else "#ef4444" if sel_s.get("delta") and sel_s["delta"] < 0
            else "var(--text-tertiary)"
        )
        sign = "+" if sel_s["stress"] >= 0 else ""
        return _ui.div(
            _ui.div(
                _ui.span(f"Sessie {sel_s['session']} — {sel_s['date']}", style="font-weight:600;"),
                _ui.span(f"  ·  {sel_s['pl_nl']}", style="color:var(--text-secondary);"),
                style="margin-bottom:6px;",
            ),
            _ui.div(
                _ui.span("Stressafwijking: ", style="color:var(--text-secondary); font-size:0.875rem;"),
                _ui.span(f"{sign}{sel_s['stress']:+.1f} pt t.o.v. pre-studie basislijn",
                         style="font-weight:600; font-size:0.875rem;"),
                _ui.span("  |  Stemmingsdelta: ", style="color:var(--text-secondary); font-size:0.875rem;"),
                _ui.span(delta_str, style=f"font-weight:600; color:{delta_color}; font-size:0.875rem;"),
            ),
            class_="mt-callout",
            style="margin-top:12px;",
        )

    @output
    @render.ui
    def best_session_callout():
        """3.4 — Highlight the session with the highest mood delta."""
        p   = selected()
        bio = app_data.session_biometrics.get(p, pd.DataFrame())
        df  = _prepare_session_df(bio)
        if df.empty or "_delta" not in df.columns:
            return _ui.div()
        best = df.loc[df["_delta"].idxmax()]
        if pd.isna(best["_delta"]) or best["_delta"] <= 0:
            return _ui.div()
        pl_en    = str(best.get("playlist", "—")).strip()
        pl_nl    = _PLAYLIST_NL.get(pl_en, pl_en)
        pl_color = _PL_COLORS_SESSION.get(pl_en, "var(--accent)")
        sign     = "+" if best["_delta"] >= 0 else ""
        return _ui.div(
            _ui.span("★ Beste sessie: ", style="font-weight:700; color:var(--accent);"),
            _ui.span(str(best.get("date", ""))[:10], style="font-weight:600;"),
            _ui.span(f"  ·  ", style="color:var(--text-tertiary);"),
            _ui.span(pl_nl, style=f"color:{pl_color}; font-weight:600;"),
            _ui.span(f"  ·  stemmingsdelta {sign}{best['_delta']:.1f} pt",
                     style="color:var(--text-secondary);"),
            style=(
                "display:flex; align-items:center; flex-wrap:wrap; gap:4px; "
                "padding:10px 16px; background:var(--bg-elevated); "
                "border-radius:8px; margin-bottom:12px; font-size:0.875rem;"
            ),
        )

    @output
    @render.ui
    def session_table_ui():
        p   = selected()
        bio = app_data.session_biometrics.get(p, pd.DataFrame())
        df  = _prepare_session_df(bio)
        return _session_table(df, _page())

    @output
    @render.ui
    def honest_framing_ui():
        """3.5 — Personal, data-driven interpretation."""
        p   = selected()
        bio = app_data.session_biometrics.get(p, pd.DataFrame())
        if bio.empty:
            return _ui.div()

        if "mood_before_score" not in bio.columns or "mood_after_score" not in bio.columns:
            return _ui.div()

        bio2 = bio.copy()
        bio2["_delta"] = (
            pd.to_numeric(bio2["mood_after_score"],  errors="coerce") -
            pd.to_numeric(bio2["mood_before_score"], errors="coerce")
        )
        delta_vals = bio2["_delta"].dropna()
        if delta_vals.empty:
            return _ui.div()

        n   = len(delta_vals)
        avg = delta_vals.mean()

        # % of sessions where mood improved (delta > 0)
        pct_improved = (delta_vals > 0).mean() * 100

        # Best playlist by mean delta
        best_pl_nl  = "—"
        best_val    = None
        n_best      = 0
        if "playlist" in bio2.columns:
            pl_avgs = bio2.groupby("playlist")["_delta"].agg(["mean", "count"]).dropna(subset=["mean"])
            if not pl_avgs.empty:
                best_pl_en = pl_avgs["mean"].idxmax()
                best_pl_nl = _PLAYLIST_NL.get(best_pl_en, best_pl_en)
                best_val   = pl_avgs.loc[best_pl_en, "mean"]
                n_best     = int(pl_avgs.loc[best_pl_en, "count"])

        # Personalized observation
        if avg > 1.5:
            observation = "Dat is een opvallend sterk effect voor een muziekinterventie."
        elif avg > 0:
            observation = "Een positief patroon — de variatie per sessie is groot, maar de richting klopt."
        else:
            observation = "De data laat een gemengd beeld zien. De variatie per sessie is groot."

        best_str = (
            f"{best_pl_nl} ({best_val:+.1f} pt gem. · {n_best} sessies)"
            if best_val is not None else "—"
        )

        return _ui.div(
            _ui.div("Wat betekent dit voor jou?", class_="mt-h3", style="margin-bottom:12px;"),
            _ui.p(
                f"{p.capitalize()} reageerde het best op {best_pl_nl}-muziek ({best_str}). "
                f"Van de {n} sessies verbeterde de stemming in {pct_improved:.0f}% van de gevallen. "
                f"{observation}",
                class_="mt-body",
                style="margin:0;",
            ),
            class_="mt-section-card",
            style="padding:20px 24px;",
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
