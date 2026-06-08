"""Pagina — Herstelanalyse (RQ1): per-sessie stressherstel vs. basislijn."""
import base64
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from shiny import module, reactive, render, ui as _ui
from shinywidgets import output_widget, render_widget

try:
    from scipy.stats import ttest_1samp as _ttest
    _SCIPY_OK = True
except ImportError:
    _SCIPY_OK = False

from utils.chart_helpers import (
    ACCENT, GRID_COLOR, PLAYLIST_COLORS, STRESS_RED, TEXT_SECONDARY,
    chart_layout, empty_figure,
)
from utils.data_loader import AppData

ROOT = Path(__file__).parent.parent.parent
DATA = ROOT / "data"

_PLAYLIST_NL = {"Calm": "Kalm", "Neutral": "Neutraal", "Energy": "Energiek"}
_PL_COLORS   = {"Calm": "#56B4E9", "Neutral": "#009E73", "Energy": "#E69F00"}


def _img_b64(path: Path) -> str:
    if not path.exists():
        return ""
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def _recovery_scatter(df: pd.DataFrame) -> go.Figure:
    """Per-session advantage scatter: x=session date, y=advantage (min), colour=playlist."""
    if df.empty or "advantage" not in df.columns:
        return empty_figure("Geen hersteldata beschikbaar")

    df = df.copy()
    df["_date"] = pd.to_datetime(df["session_date"], errors="coerce")
    # Drop rows with NaN advantage — Plotly's JSON encoder rejects float nan
    df = df.dropna(subset=["advantage"]).sort_values("_date")

    # Compute a sensible y-axis range that clips extreme outliers for readability.
    # Sessions outside the range are still plotted but the axis is trimmed.
    adv_vals    = pd.to_numeric(df["advantage"], errors="coerce").dropna()
    n_total     = len(adv_vals)
    if n_total >= 4:
        y_lo = float(adv_vals.quantile(0.05)) - 15
        y_hi = float(adv_vals.quantile(0.95)) + 15
    else:
        y_lo, y_hi = None, None

    n_clipped = int(((adv_vals < y_lo) | (adv_vals > y_hi)).sum()) if y_lo is not None else 0

    reliable    = df[df["reliable"] == True]   # noqa: E712
    unreliable  = df[df["reliable"] != True]

    fig = go.Figure()

    # Reference line at 0
    fig.add_hline(y=0, line=dict(color="rgba(0,0,0,0.12)", width=1, dash="dot"))

    # Unreliable sessions (faded)
    for pl in ["Calm", "Neutral", "Energy"]:
        grp = unreliable[unreliable["playlist"] == pl] if "playlist" in unreliable.columns else pd.DataFrame()
        if grp.empty:
            continue
        fig.add_trace(go.Scatter(
            x=grp["_date"],
            y=grp["advantage"],
            mode="markers",
            name=f"{_PLAYLIST_NL.get(pl, pl)} (lage r²)",
            marker=dict(
                size=9,
                color=_PL_COLORS.get(pl, ACCENT),
                opacity=0.25,
                line=dict(width=1.5, color=_PL_COLORS.get(pl, ACCENT)),
                symbol="circle-open",
            ),
            customdata=grp[["session_date", "playlist", "r2_actual"]].values,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Playlist: %{customdata[1]}<br>"
                "Voordeel: %{y:+.1f} min<br>"
                "r² = %{customdata[2]:.3f} (laag, onbetrouwbaar)<extra></extra>"
            ),
            showlegend=True,
        ))

    # Reliable sessions (opaque)
    for pl in ["Calm", "Neutral", "Energy"]:
        grp = reliable[reliable["playlist"] == pl] if "playlist" in reliable.columns else pd.DataFrame()
        if grp.empty:
            continue
        fig.add_trace(go.Scatter(
            x=grp["_date"],
            y=grp["advantage"],
            mode="markers",
            name=_PLAYLIST_NL.get(pl, pl),
            marker=dict(
                size=13,
                color=_PL_COLORS.get(pl, ACCENT),
                opacity=0.9,
                line=dict(width=2, color="rgba(0,0,0,0.2)"),
            ),
            customdata=grp[["session_date", "playlist", "r2_actual", "pre_state"]].fillna("—").values,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Playlist: %{customdata[1]}<br>"
                "Voordeel: %{y:+.1f} min<br>"
                "r² = %{customdata[2]:.3f} · "
                "Pre-staat: %{customdata[3]}<extra></extra>"
            ),
        ))

    yaxis_cfg = dict(title="Herstelvoordeel (min)", gridcolor=GRID_COLOR, zeroline=False)
    if y_lo is not None:
        yaxis_cfg["range"] = [y_lo, y_hi]

    clip_note = ""
    if n_clipped > 0:
        clip_note = (
            f"<i>{n_clipped} sessie(s) vallen buiten het weergegeven bereik "
            f"(uitschieters ingekort voor leesbaarheid)</i>"
        )
        fig.add_annotation(
            text=clip_note,
            xref="paper", yref="paper",
            x=0.5, y=-0.28,
            showarrow=False,
            font=dict(size=10, color=TEXT_SECONDARY),
            align="center",
        )

    fig.update_layout(**chart_layout(
        xaxis=dict(
            title="Sessiedatum",
            gridcolor=GRID_COLOR,
            type="date",
            tickformat="%d %b",
        ),
        yaxis=yaxis_cfg,
        height=320,
        margin=dict(l=64, r=32, t=16, b=56 if n_clipped > 0 else 48),
        legend=dict(
            orientation="h",
            y=-0.30 if n_clipped > 0 else -0.22,
            x=0.5,
            xanchor="center",
            font=dict(size=11),
        ),
    ))
    return fig


def _stat_card(label: str, value: str, sub: str = "", color: str = "var(--accent)") -> _ui.Tag:
    return _ui.div(
        _ui.div(value, style=(
            f"font-family:'Sora',sans-serif; font-weight:700; font-size:2rem; "
            f"color:{color}; line-height:1; margin-bottom:6px;"
        )),
        _ui.div(label, class_="mt-stat-label"),
        _ui.div(sub, class_="mt-caption mt-tertiary", style="margin-top:4px;") if sub else _ui.div(),
        class_="mt-stat-card",
    )


# ---------------------------------------------------------------------------
# Module UI
# ---------------------------------------------------------------------------

@module.ui
def ui():
    return _ui.div(
        # Page hero — aligns to home page pattern
        _ui.div(
            _ui.div(
                _ui.span("Herstelanalyse", class_="mt-h1"),
                _ui.span("RQ1 · RQ2", class_="rq-badge", style="vertical-align:middle;"),
                style="display:inline-flex; align-items:center; gap:8px; justify-content:center;",
            ),
            _ui.p(
                "Herstelt het lichaam sneller als je naar muziek luistert? "
                "Herstelvoordeel = verwachte τ (basislijn) − werkelijke τ (sessie). "
                "Positief = sneller herstel.",
                class_="mt-body mt-secondary",
                style="margin-top:8px; max-width:560px; margin-left:auto; margin-right:auto;",
            ),
            class_="mt-page-hero",
        ),

        # 4.1 "Hoe lees ik dit?" uitleg
        _ui.div(
            _ui.HTML(
                '<details class="mt-details" style="margin-bottom:8px;">'
                '<summary style="font-size:0.875rem; font-weight:600; cursor:pointer;">Hoe lees ik dit?</summary>'
                '<div class="mt-details-body" style="font-size:0.875rem; color:var(--text-secondary); margin-top:8px; line-height:1.7;">'
                '<b>Herstelvoordeel (min):</b> Hoeveel minuten sneller jij herstelde na een muziekluistersessie, '
                'vergeleken met hoe lang herstel normaal duurt op dat tijdstip (circadiane basislijn). '
                'Positief = muziek hielp sneller te herstellen.<br>'
                '<b>Betrouwbare sessies:</b> Alleen sessies waarbij het wiskundige herstelmodel goed paste (R²>0.05) '
                'én de stressmeting hoog genoeg was om herstel te kunnen meten.<br>'
                '<b>p-waarde:</b> De statistische kans dat het gemeten voordeel puur door toeval is. '
                'Kleiner dan 0.05 = statistisch significant (maar N is klein — voorzichtig interpreteren).'
                '</div></details>'
            ),
            style="padding:0 var(--page-margin) 8px;",
        ),

        # Stat row
        _ui.div(
            _ui.output_ui("recovery_stats"),
            style="padding:0 var(--page-margin) 24px;",
        ),

        # Per-session scatter chart
        _ui.div(
            _ui.div(
                _ui.div("Herstelvoordeel per sessie", class_="mt-h2", style="margin-bottom:8px;"),
                _ui.div(
                    "Grote gevulde stippen = betrouwbare sessies (R²>0.05 én pre-stress hoog genoeg). "
                    "Holle stippen = lage modelfit — toon als referentie, niet als meting.",
                    class_="mt-caption mt-secondary", style="margin-bottom:16px;",
                ),
                output_widget("recovery_chart"),
                _ui.output_ui("honest_framing"),
                class_="mt-section-card",
            ),
            style="padding:0 var(--page-margin) 24px;",
        ),

        # Combined group PNGs (collapsible)
        _ui.div(
            _ui.div(
                _ui.div(
                    _ui.div("Groepsoverzicht", class_="mt-h2", style="margin-bottom:4px;"),
                    _ui.input_action_button("toggle_group", "▼ Toon grafieken",
                                            class_="mt-expand-trigger",
                                            style="margin-left:auto; font-size:12px;"),
                    style="display:flex; align-items:center; margin-bottom:8px;",
                ),
                _ui.div("Gecombineerde recovery-visualisaties over alle deelnemers.",
                        class_="mt-caption mt-secondary", style="margin-bottom:12px;"),
                _ui.output_ui("group_plots"),
                class_="mt-section-card",
            ),
            style="padding:0 var(--page-margin) 24px;",
        ),
    )


# ---------------------------------------------------------------------------
# Module server
# ---------------------------------------------------------------------------

@module.server
def server(input, output, session, app_data: AppData, selected_participant=None):
    sel = selected_participant if selected_participant is not None else reactive.Value("bosbes")
    show_group = reactive.Value(False)

    @reactive.Effect
    @reactive.event(input.toggle_group)
    def _toggle():
        show_group.set(not show_group())
        label = "▲ Verberg grafieken" if show_group() else "▼ Toon grafieken"
        _ui.update_action_button("toggle_group", label=label, session=session)

    @reactive.Calc
    def _participant_data():
        p  = sel()
        rf = app_data.recovery_features
        if rf is None:
            return pd.DataFrame()
        if not hasattr(rf, "empty"):
            return pd.DataFrame()
        if rf.empty or "participant" not in rf.columns:
            return pd.DataFrame()
        df = rf[rf["participant"] == p].copy()
        # Normalise column name: tau_advantage → advantage
        if "advantage" not in df.columns and "tau_advantage" in df.columns:
            df = df.rename(columns={"tau_advantage": "advantage"})
        return df

    def _group_stats():
        """Compute group-wide recovery stats across all participants from the loaded data."""
        rf = app_data.recovery_features
        if rf.empty:
            return None
        rel = rf[rf["reliable"] == True] if "reliable" in rf.columns else pd.DataFrame()  # noqa: E712
        adv = pd.to_numeric(rel["advantage"], errors="coerce").dropna() if not rel.empty else pd.Series([], dtype=float)
        p_val = None
        if _SCIPY_OK and len(adv) >= 5:
            _, p_val = _ttest(adv, 0)
        return {
            "n_total":    len(rf),
            "n_reliable": len(rel),
            "mean_adv":   float(adv.mean()) if len(adv) > 0 else float("nan"),
            "p_val":      p_val,
        }

    @output
    @render.ui
    def recovery_stats():
        df = _participant_data()
        if df.empty:
            return _ui.div(
                "Geen hersteldata beschikbaar voor deze deelnemer.",
                class_="mt-body mt-secondary mt-no-data",
                style="min-height:80px;",
            )

        # Per-participant stats (shown in cards)
        n_total    = len(df)
        reliable   = df[df["reliable"] == True] if "reliable" in df.columns else pd.DataFrame()  # noqa: E712
        n_reliable = len(reliable)

        if n_reliable > 0 and "advantage" in reliable.columns:
            mean_adv  = pd.to_numeric(reliable["advantage"], errors="coerce").mean()
            adv_str   = f"+{mean_adv:.0f} min" if mean_adv >= 0 else f"{mean_adv:.0f} min"
            adv_color = ACCENT if mean_adv >= 0 else STRESS_RED
        else:
            adv_str   = "—"
            adv_color = TEXT_SECONDARY

        # Group-level p-value (computed from full recovery_features.csv across all participants)
        gs = _group_stats()
        if gs and gs["p_val"] is not None:
            p_str = f"{gs['p_val']:.4f}"
            p_sub = f"groep: n={gs['n_reliable']} betrouwbaar, t-test vs. 0"
        else:
            p_str = "—"
            p_sub = "scipy niet beschikbaar"

        return _ui.div(
            _stat_card(
                "Gem. herstelvoordeel",
                adv_str,
                f"minuten sneller herstel dan basislijn · {n_reliable} betrouwbare sessies",
                color=adv_color,
            ),
            _stat_card(
                "Geldige sessies",
                str(n_total),
                "sessies met voldoende stressdata (R²>0.05)",
            ),
            _stat_card(
                "Betrouwbare sessies",
                f"{n_reliable}/{n_total}",
                "herstelcurve past én pre-stress hoog genoeg",
            ),
            _stat_card(
                "p-waarde (groep)",
                p_str,
                "kans dat voordeel door toeval is · t-test vs. 0 min",
                color=TEXT_SECONDARY,
            ),
            class_="mt-recovery-stat-row",
        )

    @output
    @render_widget
    def recovery_chart():
        df = _participant_data()
        if df.empty:
            return empty_figure(
                "Hersteldata niet beschikbaar voor deze deelnemer. "
                "Herstelanalyse vereist een Garmin stresssensor — "
                "alleen beschikbaar voor bosbes, kokosnoot en limoen."
            )
        if "advantage" not in df.columns:
            available = ", ".join(df.columns.tolist()[:8])
            return empty_figure(
                f"Kolom 'advantage' ontbreekt. Beschikbare kolommen: {available}. "
                "Controleer of recovery_features correct is geladen."
            )
        return _recovery_scatter(df)

    @output
    @render.ui
    def honest_framing():
        df = _participant_data()
        if df.empty:
            return _ui.div()

        # Compute all figures from the actual data — no hardcoded values
        gs = _group_stats()
        if gs:
            n_rel   = gs["n_reliable"]
            n_tot   = gs["n_total"]
            m_adv   = gs["mean_adv"]
            adv_str = f"+{m_adv:.1f} min" if m_adv >= 0 else f"{m_adv:.1f} min"
            p_str   = f"p={gs['p_val']:.4f}" if gs["p_val"] is not None else "p=n.v.t."
            sig_str = "niet significant (α=0.05)" if gs["p_val"] is None or gs["p_val"] >= 0.05 else "significant (α=0.05)"
        else:
            n_rel, n_tot, adv_str, p_str, sig_str = "?", "?", "?", "?", "?"

        return _ui.div(
            _ui.span("Eerlijk beeld (groep): ", style="font-weight:600;"),
            f"Over alle deelnemers zijn {n_rel} van {n_tot} geldige sessies betrouwbaar "
            f"(r²>0.05 én pre_stress≥asymptoot). "
            f"Gemiddeld groepsvoordeel: {adv_str} — {p_str}, {sig_str}. "
            "De deelnemerspecifieke kaart hierboven toont het voordeel voor deze deelnemer. "
            "Interpreteer als richting, niet als bewijs.",
            class_="mt-honesty-callout",
            style="margin-top:16px;",
        )

    @output
    @render.ui
    def group_plots():
        if not show_group():
            return _ui.div()
        fnames = [
            ("tau_waterfall.png",    "τ-waterval — verwacht vs. werkelijk herstel per sessie"),
            ("recovery_vs_mood.png", "Herstelvoordeel vs. stemmingsdelta (RQ2: r ≈ 0.3)"),
            ("recovery_advantage.png", "Herstelvoordeel per deelnemer"),
        ]
        items = []
        for fname, caption in fnames:
            src = _img_b64(DATA / "analysis" / fname)
            if src:
                items.append(_ui.div(
                    _ui.div(caption, class_="mt-caption mt-secondary", style="margin-bottom:6px;"),
                    _ui.div(
                        _ui.img(src=src, style="max-width:100%; border-radius:6px;"),
                        class_="data-terminal",
                    ),
                ))
        if not items:
            return _ui.div(
                "Groepsgrafieken niet gevonden — voer recovery_analysis.ipynb uit.",
                class_="mt-caption mt-secondary",
            )
        return _ui.div(*items, style="display:grid; grid-template-columns:repeat(2,1fr); gap:16px;")
