"""Pagina 4 -- Aanbevelen: Bayesiaanse aanbeveling + live Ridge simulatie."""
import pandas as pd
import plotly.graph_objects as go
from shiny import module, reactive, render, ui as _ui
from shinywidgets import output_widget, render_widget

from utils.chart_helpers import ACCENT, GRID_COLOR, PLAYLIST_COLORS, TEXT_SECONDARY, ZERO_COLOR, chart_layout, empty_figure
from utils.data_loader import PARTICIPANTS, AppData, best_playlist_for, expected_stress, live_recommend, explain_live_prediction


_ISO_LABEL_NL = {
    "Calm":    "ISO — Afdaling",
    "Energy":  "ISO — Opstijging",
    "Neutral": "ISO — Stabiel",
}
_PLAYLIST_NL   = {"Calm": "KALM", "Neutral": "NEUTRAAL", "Energy": "ENERGIEK"}
_PLAYLIST_NL_L = {"Calm": "Kalm", "Neutral": "Neutraal", "Energy": "Energiek"}
_PL_COLORS     = {"Calm": "#56B4E9", "Neutral": "#009E73", "Energy": "#E69F00"}


def _posterior_chart(recs: dict) -> go.Figure:
    if not recs:
        return empty_figure("Geen Bayesiaanse data beschikbaar")

    playlists   = ["Calm", "Neutral", "Energy"]
    nl_labels   = {"Calm": "Kalm", "Neutral": "Neutraal", "Energy": "Energiek"}
    base_colors = [PLAYLIST_COLORS[p] for p in playlists]

    def _m(d): return d.get("mean_delta", d.get("mean", 0))
    means   = [_m(recs.get(p, {})) for p in playlists]
    ci_low  = [recs.get(p, {}).get("ci_low", 0) for p in playlists]
    ci_high = [recs.get(p, {}).get("ci_high", 0) for p in playlists]
    total   = sum(max(m, 0) for m in means)
    pcts    = [max(m, 0) / total * 100 if total > 0 else 0 for m in means]

    uncertain = [lo < 0 for lo in ci_low]
    colors    = ["rgba(120,120,120,0.5)" if u else c
                 for u, c in zip(uncertain, base_colors)]

    hover_texts = []
    for p, m, lo, hi, u in zip(playlists, means, ci_low, ci_high, uncertain):
        note = " ⚠ onzeker (CI omvat 0)" if u else ""
        hover_texts.append(
            f"<b>{nl_labels[p]}</b><br>"
            f"Gem. voorspeld: {m:.2f}<br>"
            f"89% CI: [{lo:.2f}, {hi:.2f}]{note}<extra></extra>"
        )

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=pcts,
        y=[nl_labels[p] for p in playlists],
        orientation="h",
        marker_color=colors,
        error_x=dict(
            type="data",
            arrayminus=[max(m - lo, 0) / total * 100 if total > 0 else 0
                        for m, lo in zip(means, ci_low)],
            array=[(hi - m) / total * 100 if total > 0 else 0
                   for m, hi in zip(means, ci_high)],
            color="rgba(255,255,255,0.45)",
            thickness=2.5,
            width=10,
        ),
        text=[f"{p:.0f}%{'  ⚠' if u else ''}" for p, u in zip(pcts, uncertain)],
        textposition="outside",
        textfont=dict(color=TEXT_SECONDARY, size=11),
        hovertemplate=hover_texts,
    ))

    fig.add_vline(x=0, line=dict(color=ZERO_COLOR, width=1, dash="dot"))
    x_max = max(pcts) * 1.45 if any(p > 0 for p in pcts) else 60
    fig.update_layout(**chart_layout(
        xaxis=dict(title="Relatieve voorkeur (%)", range=[0, x_max], gridcolor=GRID_COLOR),
        yaxis=dict(gridcolor="rgba(0,0,0,0)"),
        height=300,
        margin=dict(l=90, r=32, t=16, b=48),
        bargap=0.38,
    ))
    return fig


def _ranked_list(recs: dict) -> _ui.Tag:
    if not recs:
        return _ui.div("Geen posteriordata beschikbaar.", class_="mt-caption mt-secondary")

    playlists = ["Calm", "Neutral", "Energy"]
    def _m2(d): return d.get("mean_delta", d.get("mean", 0))
    means   = {p: _m2(recs.get(p, {})) for p in playlists}
    ci_low  = {p: recs.get(p, {}).get("ci_low", 0) for p in playlists}
    ci_high = {p: recs.get(p, {}).get("ci_high", 0) for p in playlists}
    total   = sum(max(m, 0) for m in means.values())
    pcts    = {p: max(means[p], 0) / total * 100 if total > 0 else 0 for p in playlists}

    ranked      = sorted(playlists, key=lambda p: means[p], reverse=True)
    rank_labels = ["1.", "2.", "3."]

    rows = []
    for rank_num, (rank_lbl, pl) in enumerate(zip(rank_labels, ranked), 1):
        color     = _PL_COLORS.get(pl, ACCENT)
        nl        = _PLAYLIST_NL_L.get(pl, pl)
        pct       = pcts[pl]
        uncertain = ci_low[pl] < 0
        lo        = ci_low[pl]
        hi        = ci_high[pl]

        badge_style = (
            f"display:inline-block; padding:3px 10px; border-radius:12px; "
            f"background:{color}22; color:{color}; font-weight:600; font-size:12px; "
            f"border:1px solid {color}55; margin-right:8px;"
        )
        pct_style = f"font-size:20px; font-weight:700; color:{'rgba(255,255,255,0.45)' if uncertain else color};"

        uncertainty_note = (
            _ui.span(" ⚠ CI omvat nul", style="font-size:11px; color:#f59e0b; margin-left:6px;")
            if uncertain else _ui.span()
        )
        ci_note = _ui.div(
            f"89% CI: [{lo:.2f}, {hi:.2f}]",
            style="font-size:11px; color:var(--text-tertiary); margin-top:2px;",
        )

        rows.append(_ui.div(
            _ui.span(rank_lbl, style="font-size:16px; font-weight:600; color:var(--text-secondary); margin-right:10px; min-width:20px;"),
            _ui.span(nl, style=badge_style),
            _ui.span(f"{pct:.0f}%", style=pct_style),
            uncertainty_note,
            ci_note,
            style=(
                "display:flex; align-items:center; padding:12px 0; "
                + ("border-bottom:1px solid var(--border-default);" if rank_num < 3 else "")
            ),
        ))

    return _ui.div(*rows)


# ---------------------------------------------------------------------------
# Module UI
# ---------------------------------------------------------------------------

@module.ui
def ui():
    return _ui.div(
        # Hero
        _ui.div(
            _ui.div("Muziekadvies", class_="mt-h1"),
            _ui.p(
                "Wat beveelt het model aan voor jou — en hoe zeker is het? "
                "Gebaseerd op Bayesiaanse inferentie over jouw historische sessies.",
                class_="mt-body mt-secondary",
                style="max-width:560px; margin:8px auto 0;",
            ),
            class_="mt-page-hero",
        ),

        # ── Sectie 1: Jouw Aanbeveling ──────────────────────────────────────
        _ui.div(
            _ui.div(
                _ui.div("Jouw Aanbeveling", class_="mt-h2",
                        style="text-align:center; margin-bottom:4px;"),
                _ui.div(
                    "Op basis van jouw historische sessies — berekend via MCMC (4.000 samples, 4 chains).",
                    class_="mt-caption mt-secondary",
                    style="text-align:center; margin-bottom:24px;",
                ),

                # Primary Bayesian badge — centred
                _ui.div(
                    _ui.output_ui("rec_badge"),
                    style="display:flex; justify-content:center; margin-bottom:28px;",
                ),

                # Ranked list — always visible
                _ui.div(
                    _ui.div("Ranglijst — verwacht stemmingseffect aandeel",
                            class_="mt-h3", style="margin-bottom:4px;"),
                    _ui.div(
                        "% = aandeel van het totale verwachte positieve effect · "
                        "grijs = 89% CI omvat nul (onvoldoende bewijs)",
                        class_="mt-caption mt-tertiary",
                        style="margin-bottom:12px;",
                    ),
                    _ui.output_ui("ranked_list_ui"),
                    style="max-width:480px; margin:0 auto 16px;",
                ),

                # Sample size + honesty (N is dynamic from feature matrix)
                _ui.div(
                    _ui.output_ui("sample_size_note"),
                    _ui.output_ui("honesty_note"),
                    style="max-width:480px; margin:0 auto;",
                ),

                class_="mt-section-card",
            ),
            style="padding:0 var(--page-margin) 56px;",
        ),

        # ── Sectie 2: Verwachte stemmingseffecten (posteriors) ──────────────
        _ui.div(
            _ui.div(
                _ui.div("Verwachte stemmingseffecten", class_="mt-h2",
                        style="margin-bottom:4px;"),
                _ui.div(
                    "Posterior-verdeling per afspeellijsttype — pre-berekend op historische sessies.",
                    class_="mt-caption mt-secondary",
                    style="margin-bottom:16px;",
                ),
                _ui.div(
                    _ui.span("Wat zie je hier? ", style="font-weight:600;"),
                    "Elke balk = het verwachte aandeel van het totale stemmingseffect voor dat type. "
                    "De foutbalken tonen het 89% geloofwaardigheidsinterval. "
                    "Grijze balken betekenen dat het CI nul omvat — het model heeft te weinig bewijs voor een positief effect.",
                    class_="mt-callout",
                    style="margin-bottom:16px; font-size:0.875rem;",
                ),
                output_widget("posterior_chart"),
                class_="mt-section-card",
            ),
            style="padding:0 var(--page-margin) 56px;",
        ),

        # ── Sectie 3: Simuleer jouw situatie (live Ridge demo) ──────────────
        _ui.div(
            _ui.div(
                _ui.div(
                    _ui.div("Simuleer jouw situatie", class_="mt-h2",
                            style="margin-bottom:4px;"),
                    _ui.div(
                        "Verken hoe het live Ridge-model reageert op verschillende invoer.",
                        class_="mt-caption mt-secondary",
                        style="margin-bottom:8px;",
                    ),
                    _ui.div(
                        _ui.span("ℹ Architectuurdemonstatie — ", style="font-weight:600; color:#f59e0b;"),
                        "bij N=82 sessies heeft geen van de biometrische invoeren een statistisch aantoonbaar effect (β ≈ 0). "
                        "De sliders tonen hoe het model is opgebouwd, niet een bewezen voorspelling.",
                        class_="mt-caption mt-secondary",
                        style="margin-bottom:20px; font-style:italic;",
                    ),
                    # Two-column layout
                    _ui.div(
                        # Links — invoer
                        _ui.div(
                            # Stress
                            _ui.div(
                                _ui.div(
                                    _ui.span("Stressniveau", class_="mt-body mt-secondary"),
                                    _ui.output_ui("stress_display"),
                                    style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;",
                                ),
                                _ui.input_slider("stress", None, min=0, max=100, value=55, step=1, width="100%"),
                                _ui.div(
                                    _ui.span("0 — ontspannen", class_="mt-caption mt-tertiary"),
                                    _ui.span("100 — zeer gestresseerd", class_="mt-caption mt-tertiary"),
                                    style="display:flex; justify-content:space-between; margin-top:4px;",
                                ),
                                style="margin-bottom:24px;",
                            ),

                            # Tijdstip
                            _ui.div(
                                _ui.div(
                                    _ui.span("Tijdstip", class_="mt-body mt-secondary"),
                                    _ui.output_ui("time_display"),
                                    style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;",
                                ),
                                _ui.input_slider("hour", None, min=0, max=23, value=17, step=1, width="100%"),
                                _ui.div(
                                    _ui.span("00:00", class_="mt-caption mt-tertiary"),
                                    _ui.span("23:00", class_="mt-caption mt-tertiary"),
                                    style="display:flex; justify-content:space-between; margin-top:4px;",
                                ),
                                style="margin-bottom:24px;",
                            ),

                            # Body Battery
                            _ui.div(
                                _ui.div(
                                    _ui.span("Body Battery", class_="mt-body mt-secondary"),
                                    _ui.output_ui("battery_display"),
                                    style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;",
                                ),
                                _ui.input_slider("battery", None, min=0, max=100, value=40, step=1, width="100%"),
                                _ui.div(
                                    "Garmin Body Battery — lager = meer vermoeid",
                                    class_="mt-caption mt-tertiary",
                                    style="margin-top:4px;",
                                ),
                                style="margin-bottom:24px;",
                            ),

                        ),

                        # Rechts — live uitvoer
                        _ui.div(
                            _ui.div("Live Ridge — uitkomst", class_="mt-h3",
                                    style="margin-bottom:4px;"),
                            _ui.div(
                                "Reageert direct op de sliders.",
                                class_="mt-caption mt-tertiary",
                                style="margin-bottom:16px;",
                            ),
                            _ui.output_ui("live_rec_badge"),
                            _ui.output_ui("live_confidence_strip"),

                            _ui.div(
                                _ui.div("Bijdrage per kenmerk", class_="mt-h3",
                                        style="margin-top:20px; margin-bottom:4px;"),
                                _ui.div(
                                    "Coëfficiënt × huidige waarde. "
                                    "Groen = positieve bijdrage aan stemmingswinst, rood = negatief.",
                                    class_="mt-caption mt-tertiary",
                                    style="margin-bottom:8px;",
                                ),
                                output_widget("feature_importance_chart"),
                            ),

                            # Ridge CI note — relevant here, not at the top of the page
                            _ui.output_ui("ridge_ci_note"),
                        ),

                        class_="rec-two-col",
                    ),
                ),
                class_="mt-section-card",
            ),
            style="padding:0 var(--page-margin) 64px;",
        ),
    )


# ---------------------------------------------------------------------------
# Module server
# ---------------------------------------------------------------------------

@module.server
def server(input, output, session, app_data: AppData, selected_participant=None):
    sel = selected_participant if selected_participant is not None else reactive.Value("bosbes")

    # ── Slider displays ─────────────────────────────────────────────────────

    @output
    @render.ui
    def stress_display():
        val = input.stress()
        color = "#ef4444" if val > 70 else ("#f59e0b" if val > 40 else "#22c55e")
        return _ui.div(str(val), class_="mt-slider-value", style=f"color:{color};")

    @output
    @render.ui
    def time_display():
        return _ui.div(f"{input.hour():02d}:00", class_="mt-slider-value")

    @output
    @render.ui
    def battery_display():
        val = input.battery()
        color = "#ef4444" if val < 30 else ("#f59e0b" if val < 50 else "#22c55e")
        return _ui.div(str(val), class_="mt-slider-value", style=f"color:{color};")

    # ── Core reactives ──────────────────────────────────────────────────────

    @reactive.Calc
    def baseline_deviation():
        exp, _ = expected_stress(app_data, sel(), input.hour())
        return None if exp is None else input.stress() - exp

    @reactive.Calc
    def recommendation():
        return best_playlist_for(app_data, sel())

    @reactive.Calc
    def live_recommendation():
        p      = sel()
        stress = float(input.stress())
        hour   = float(input.hour())
        batt   = float(input.battery())
        exp, _ = expected_stress(app_data, p, int(hour))
        baseline_dev = (stress - exp) if exp is not None else 0.0
        bio_row = pd.Series({
            "baseline_deviation_entry":  baseline_dev,
            "hr_baseline_deviation":     0.0,
            "mood_before_score":         5.0,
            "bb_start":                  batt,
            "days_since_last_session":   3.0,
            "pre_state_encoded":         2.0,   # fixed: "Licht" as neutral default
            "avg_resp_daily":            float("nan"),
            "session_number":            5.0,
            "start_local":               f"{int(hour):02d}:00",
            "day_of_week":               3.0,
        })
        return live_recommend(app_data, p, bio_row)

    # ── Section 1 outputs ───────────────────────────────────────────────────

    @output
    @render.ui
    def rec_badge():
        playlist, _ = recommendation()
        type_name = _PLAYLIST_NL.get(playlist, playlist.upper())
        iso_label = _ISO_LABEL_NL.get(playlist, "")
        return _ui.div(
            _ui.div("Aanbeveling", class_="mt-rec-hero-eyebrow"),
            _ui.div(type_name.upper(), class_=f"mt-rec-hero-type {playlist.lower()}"),
            _ui.div(iso_label, class_="mt-rec-hero-iso"),
            class_=f"mt-rec-badge-hero {playlist.lower()}",
        )

    @output
    @render.ui
    def ranked_list_ui():
        recs = app_data.recommendations.get(sel(), {})
        return _ranked_list(recs)

    @output
    @render.ui
    def sample_size_note():
        p  = sel()
        fm = app_data.feature_matrix
        if fm is not None and not fm.empty and "participant" in fm.columns:
            n = int((fm["participant"] == p).sum())
        else:
            bio = app_data.session_biometrics.get(p, None)
            n = len(bio) if bio is not None and not bio.empty else 0
        if n > 0:
            return _ui.p(
                f"N={n} sessies voor {p.capitalize()}. "
                "Posterior breedte neemt af naarmate meer sessies beschikbaar zijn.",
                class_="mt-caption mt-tertiary",
                style="margin:0;",
            )
        return _ui.div()

    @output
    @render.ui
    def honesty_note():
        fm  = app_data.feature_matrix
        n   = len(fm) if fm is not None and not fm.empty else "?"
        return _ui.div(
            f"⚠ Exploratief — N={n} sessies totaal. "
            "Alle resultaten zijn richting gevend, geen klinische conclusies.",
            class_="mt-caption",
            style="color:#f59e0b; margin-top:6px;",
        )

    # ── Section 2 outputs ───────────────────────────────────────────────────

    @output
    @render_widget
    def posterior_chart():
        recs = app_data.recommendations.get(sel(), {})
        return _posterior_chart(recs)

    # ── Section 3 outputs ───────────────────────────────────────────────────

    @output
    @render.ui
    def live_rec_badge():
        best_pl, preds = live_recommendation()
        if not preds:
            return _ui.div(
                "Live model niet beschikbaar.",
                class_="mt-caption mt-secondary",
                style="text-align:center; padding:16px;",
            )
        type_name = _PLAYLIST_NL.get(best_pl, best_pl.upper())
        iso_label = _ISO_LABEL_NL.get(best_pl, "")
        badge_cls = best_pl.lower()
        return _ui.div(
            _ui.div(type_name, class_="mt-rec-live-type"),
            _ui.div(iso_label, style="font-size:0.75rem; color:var(--text-secondary); margin-top:2px; font-style:italic;"),
            class_=f"mt-rec-badge-live {badge_cls}",
        )

    @output
    @render.ui
    def live_confidence_strip():
        _, preds = live_recommendation()
        if not preds or len(preds) < 2:
            return _ui.div()
        order    = ["Calm", "Neutral", "Energy"]
        present  = [p for p in order if p in preds]
        raw      = [max(preds[p], 0) for p in present]
        total    = sum(raw) or 1
        bars = []
        for pl, val in zip(present, raw):
            pct   = val / total * 100
            color = {"Calm": "#56B4E9", "Neutral": "#009E73", "Energy": "#E69F00"}.get(pl, "#aaa")
            nl    = {"Calm": "Kalm", "Neutral": "Neutraal", "Energy": "Energiek"}.get(pl, pl)
            bars.append(_ui.div(
                _ui.div(
                    _ui.div(style=(
                        f"width:{pct:.0f}%; height:6px; border-radius:3px; "
                        f"background:{color}; transition:width 0.35s ease;"
                    )),
                    style=(
                        "width:100%; height:6px; border-radius:3px; "
                        "background:var(--bg-elevated); overflow:hidden; margin-bottom:3px;"
                    ),
                ),
                _ui.div(
                    _ui.span(nl, style=f"color:{color}; font-size:0.7rem; font-weight:600;"),
                    _ui.span(f"{preds[pl]:+.2f} pt",
                             style="color:var(--text-tertiary); font-size:0.7rem; float:right;"),
                    style="overflow:hidden;",
                ),
                style="margin-bottom:8px;",
            ))
        return _ui.div(
            _ui.div("Relatieve modelscores", class_="mt-caption mt-tertiary",
                    style="margin-bottom:8px; margin-top:16px;"),
            *bars,
            style="margin-bottom:4px;",
        )

    @output
    @render_widget
    def feature_importance_chart():
        best_pl, _ = live_recommendation()
        p          = sel()
        stress     = float(input.stress())
        hour       = float(input.hour())
        batt       = float(input.battery())
        exp, _     = expected_stress(app_data, p, int(hour))
        bio_row    = pd.Series({
            "baseline_deviation_entry": (stress - exp) if exp is not None else 0.0,
            "hr_baseline_deviation":    0.0,
            "mood_before_score":        5.0,
            "bb_start":                 batt,
            "days_since_last_session":  3.0,
            "pre_state_encoded":        2.0,   # fixed neutral default
            "avg_resp_daily":           float("nan"),
            "session_number":           5.0,
            "start_local":              f"{int(hour):02d}:00",
            "day_of_week":              3.0,
        })
        attributions = explain_live_prediction(app_data, p, bio_row, best_pl)
        if not attributions:
            return empty_figure("Live model niet beschikbaar")
        names  = [a[0] for a in attributions]
        values = [a[1] for a in attributions]
        colors = ["#22c55e" if v >= 0 else "#ef4444" for v in values]
        fig = go.Figure(go.Bar(
            x=values, y=names, orientation="h",
            marker_color=colors,
            hovertemplate="%{y}: %{x:+.3f}<extra></extra>",
            text=[f"{v:+.3f}" for v in values],
            textposition="outside",
            textfont=dict(color=TEXT_SECONDARY, size=10),
        ))
        fig.add_vline(x=0, line=dict(color=ZERO_COLOR, width=1, dash="dot"))
        fig.update_layout(**chart_layout(
            xaxis=dict(title="Bijdrage aan voorspelde stemmingswinst", gridcolor=GRID_COLOR),
            yaxis=dict(gridcolor="rgba(0,0,0,0)"),
            height=220,
            margin=dict(l=180, r=60, t=16, b=40),
            bargap=0.4,
        ))
        return fig

    @output
    @render.ui
    def ridge_ci_note():
        fm  = app_data.feature_matrix
        n   = len(fm) if fm is not None and not fm.empty else "?"
        bci = app_data.bootstrap_ci.get("mood_delta", {})
        if bci:
            r2 = bci.get("r2_point", "?")
            lo = bci.get("r2_ci_low", "?")
            hi = bci.get("r2_ci_high", "?")
            txt = (
                f"Live Ridge R²={r2:.3f} (Bootstrap 95% CI: {lo:.3f}–{hi:.3f}). "
                f"Model getraind op eerdere snapshot; huidig feature matrix N={n} sessies."
            )
        else:
            txt = "Live Ridge R²=0.318 (Bootstrap 95% CI: zie Model & Data)."
        return _ui.div(txt, class_="mt-caption mt-tertiary",
                       style="margin-top:12px; font-style:italic;")
