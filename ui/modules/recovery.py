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


def _safe_cd(row: dict) -> list:
    """Convert a customdata row to plain Python types — avoids numpy JSON issues."""
    out = []
    for v in row:
        if hasattr(v, "item"):
            out.append(v.item())
        elif v != v:
            out.append("—")
        elif v is None or (isinstance(v, float) and not v == v):
            out.append("—")
        else:
            out.append(str(v) if isinstance(v, (pd.Timestamp, pd.NaT.__class__)) else v)
    return out


def _failure_reason(row: pd.Series) -> str:
    """Return a human-readable Dutch string explaining why a session is unreliable."""
    reasons = []
    r2 = row.get("r2_actual")
    pre = row.get("pre_stress_mean")
    asym = row.get("asymptote")

    if pd.isna(r2):
        reasons.append("herstelkromme kon niet worden berekend (te weinig data)")
    elif float(r2) <= 0.05:
        reasons.append(f"herstelkromme past slecht (R²={float(r2):.3f} ≤ 0.05)")

    if not pd.isna(pre) and not pd.isna(asym):
        if float(pre) < float(asym):
            reasons.append(
                f"stress niet hoog genoeg bij aanvang "
                f"({float(pre):.0f} < drempel {float(asym):.0f})"
            )

    return " · ".join(reasons) if reasons else "reden onbekend"


def _recovery_scatter(df: pd.DataFrame) -> go.Figure:
    """Per-session advantage scatter: x=session date, y=advantage (min), colour=playlist."""
    if df.empty or "advantage" not in df.columns:
        return empty_figure("Geen hersteldata beschikbaar")

    df = df.copy()
    df["_date_str"] = df["session_date"].astype(str).str[:10]
    df["_adv"]      = pd.to_numeric(df["advantage"], errors="coerce")
    df = df.dropna(subset=["_adv"]).sort_values("_date_str")

    if df.empty:
        return empty_figure("Geen hersteldata beschikbaar")

    adv_vals = df["_adv"]
    n_total  = len(adv_vals)
    if n_total >= 4:
        y_lo = float(adv_vals.quantile(0.05)) - 15
        y_hi = float(adv_vals.quantile(0.95)) + 15
    else:
        y_lo = float(adv_vals.min()) - 10
        y_hi = float(adv_vals.max()) + 10

    n_clipped = int(((adv_vals < y_lo) | (adv_vals > y_hi)).sum())

    x_all  = pd.to_datetime(df["_date_str"])
    x_pad  = pd.Timedelta(days=5)
    x_lo   = (x_all.min() - x_pad).strftime("%Y-%m-%d")
    x_hi   = (x_all.max() + x_pad).strftime("%Y-%m-%d")

    reliable   = df[df["reliable"] == True]   # noqa: E712
    unreliable = df[df["reliable"] != True]

    fig = go.Figure()
    fig.add_hline(y=0, line=dict(color="rgba(255,255,255,0.12)", width=1, dash="dot"))

    # Unreliable sessions — hollow, faded, with specific failure reason in tooltip
    for pl in ["Calm", "Neutral", "Energy"]:
        grp = unreliable[unreliable["playlist"] == pl] if "playlist" in unreliable.columns else pd.DataFrame()
        if grp.empty:
            continue
        cd = [
            [
                str(row["_date_str"]),
                _PLAYLIST_NL.get(str(row.get("playlist", "")), str(row.get("playlist", ""))),
                float(row.get("r2_actual", 0)) if pd.notna(row.get("r2_actual")) else "—",
                _failure_reason(row),
            ]
            for _, row in grp.iterrows()
        ]
        fig.add_trace(go.Scatter(
            x=grp["_date_str"].tolist(),
            y=[float(v) for v in grp["_adv"].tolist()],
            mode="markers",
            name=f"{_PLAYLIST_NL.get(pl, pl)} — niet meegeteld",
            marker=dict(
                size=9,
                color=_PL_COLORS.get(pl, ACCENT),
                opacity=0.30,
                line=dict(width=1.5, color=_PL_COLORS.get(pl, ACCENT)),
                symbol="circle-open",
            ),
            customdata=cd,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Playlist: %{customdata[1]}<br>"
                "Voordeel: %{y:+.1f} min<br>"
                "<span style='color:#f87171'>Niet meegeteld — %{customdata[3]}</span>"
                "<extra></extra>"
            ),
            showlegend=True,
        ))

    # Reliable sessions — filled, larger, full tooltip
    for pl in ["Calm", "Neutral", "Energy"]:
        grp = reliable[reliable["playlist"] == pl] if "playlist" in reliable.columns else pd.DataFrame()
        if grp.empty:
            continue
        cd = [
            [
                str(row["_date_str"]),
                _PLAYLIST_NL.get(str(row.get("playlist", "")), str(row.get("playlist", ""))),
                float(row.get("r2_actual", 0)) if pd.notna(row.get("r2_actual")) else "—",
                str(row.get("pre_state", "—")),
                float(row.get("pre_stress_mean", 0)) if pd.notna(row.get("pre_stress_mean")) else "—",
            ]
            for _, row in grp.iterrows()
        ]
        fig.add_trace(go.Scatter(
            x=grp["_date_str"].tolist(),
            y=[float(v) for v in grp["_adv"].tolist()],
            mode="markers",
            name=f"{_PLAYLIST_NL.get(pl, pl)} — betrouwbaar",
            marker=dict(
                size=14,
                color=_PL_COLORS.get(pl, ACCENT),
                opacity=0.9,
                line=dict(width=2, color="rgba(255,255,255,0.18)"),
            ),
            customdata=cd,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Playlist: %{customdata[1]}<br>"
                "Voordeel: %{y:+.1f} min<br>"
                "R² = %{customdata[2]:.3f} · Pre-staat: %{customdata[3]}<br>"
                "Pre-stress: %{customdata[4]}"
                "<extra></extra>"
            ),
        ))

    if n_clipped > 0:
        fig.add_annotation(
            text=(
                f"<i>{n_clipped} sessie(s) vallen buiten het weergegeven bereik "
                f"(uitschieters ingekort voor leesbaarheid)</i>"
            ),
            xref="paper", yref="paper",
            x=0.5, y=-0.30,
            showarrow=False,
            font=dict(size=10, color=TEXT_SECONDARY),
            align="center",
        )

    b_margin = 64 if n_clipped > 0 else 48
    fig.update_layout(**chart_layout(
        xaxis=dict(
            title="Sessiedatum",
            gridcolor=GRID_COLOR,
            tickformat="%d %b",
            range=[x_lo, x_hi],
        ),
        yaxis=dict(
            title="Herstelvoordeel (min)",
            gridcolor=GRID_COLOR,
            zeroline=False,
            range=[y_lo, y_hi],
        ),
        height=340,
        margin=dict(l=64, r=32, t=16, b=b_margin),
        legend=dict(
            orientation="h",
            y=-0.32 if n_clipped > 0 else -0.22,
            x=0.5,
            xanchor="center",
            font=dict(size=11),
        ),
    ))
    return fig


def _stat_card(label: str, value: str, sub: str = "", color: str = "var(--accent)") -> _ui.Tag:
    return _ui.div(
        _ui.div(value, class_="mt-stat-value", style=f"color:{color};"),
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
        # Page hero
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

        # Concept explanation + data funnel — always visible
        _ui.div(
            _ui.output_ui("concept_explanation"),
            class_="mt-page-pad-x", style="padding-bottom:48px;",
        ),

        # Stat row
        _ui.div(
            _ui.output_ui("recovery_stats"),
            class_="mt-page-pad-x", style="padding-bottom:56px;",
        ),

        # Per-session scatter chart
        _ui.div(
            _ui.div(
                _ui.div("Herstelvoordeel per sessie", class_="mt-h2", style="margin-bottom:4px;"),
                _ui.div(
                    "Grote gevulde stippen = betrouwbare sessies (goede kromme én stress hoog genoeg). "
                    "Holle stippen = niet meegeteld — zweef over een stip voor de reden.",
                    class_="mt-caption mt-secondary", style="margin-bottom:16px;",
                ),
                output_widget("recovery_chart"),
                _ui.output_ui("honest_framing"),
                class_="mt-section-card",
            ),
            class_="mt-page-pad-x", style="padding-bottom:56px;",
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
            class_="mt-page-pad-x", style="padding-bottom:56px;",
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
        if rf is None or not hasattr(rf, "empty") or rf.empty or "participant" not in rf.columns:
            return pd.DataFrame()
        df = rf[rf["participant"] == p].copy()
        if "advantage" not in df.columns and "tau_advantage" in df.columns:
            df = df.rename(columns={"tau_advantage": "advantage"})
        return df

    def _total_sessions(p: str) -> int | None:
        """Total biometric sessions recorded for participant p."""
        sb = app_data.session_biometrics.get(p)
        if sb is None or not hasattr(sb, "__len__"):
            return None
        return len(sb)

    def _group_stats():
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
    def concept_explanation():
        p = sel()
        df = _participant_data()
        total = _total_sessions(p)
        n_in_analysis = len(df) if not df.empty else 0
        n_reliable = int((df["reliable"] == True).sum()) if not df.empty and "reliable" in df.columns else 0  # noqa: E712

        total_str = f"Van {total}" if total is not None else "Van alle"

        return _ui.div(
            _ui.p(
                _ui.strong("Herstelvoordeel (min): "),
                "Na elke sessie modelleren we hoe snel jouw stress daalde (tijdconstante τ) en "
                "vergelijken dat met jouw normale herstelsnelheid op dat uur van de dag. "
                "Positief = sneller herstel dan normaal.",
                style="margin:0 0 10px;",
            ),
            _ui.p(
                _ui.strong("Een sessie telt alleen mee als: "),
                "(1) de stresscurve een duidelijke exponentiële daling volgde (R² > 0.05) "
                "én (2) de beginspanning hoog genoeg was boven het rustniveau. "
                "Holle stippen in de grafiek voldoen niet — zweef erover voor de reden.",
                style="margin:0 0 10px;",
            ),
            _ui.p(
                f"{total_str} totale sessies hadden ",
                _ui.strong(str(n_in_analysis)),
                " voldoende stressdata voor herstelberekening, waarvan ",
                _ui.strong(str(n_reliable)),
                " betrouwbaar.",
                style="margin:0; color:var(--text-tertiary);",
            ),
            class_="mt-callout",
        )

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

        n_total    = len(df)
        reliable   = df[df["reliable"] == True] if "reliable" in df.columns else pd.DataFrame()  # noqa: E712
        n_reliable = len(reliable)

        if n_reliable > 0 and "advantage" in reliable.columns:
            mean_adv  = pd.to_numeric(reliable["advantage"], errors="coerce").mean()
            adv_str   = f"+{mean_adv:.0f} min" if mean_adv >= 0 else f"{mean_adv:.0f} min"
            adv_color = "var(--accent)" if mean_adv >= 0 else STRESS_RED
        else:
            adv_str   = "—"
            adv_color = TEXT_SECONDARY

        # Count per failure mode for the subtitle
        unreliable = df[df["reliable"] != True] if "reliable" in df.columns else df
        n_bad_fit  = int((pd.to_numeric(df.get("r2_actual", pd.Series(dtype=float)), errors="coerce").fillna(-1) <= 0.05).sum()) if not df.empty else 0
        n_low_pre  = 0
        if "pre_stress_mean" in df.columns and "asymptote" in df.columns:
            n_low_pre = int((
                df["pre_stress_mean"].notna() & df["asymptote"].notna() &
                (df["pre_stress_mean"] < df["asymptote"])
            ).sum())

        # Group-level p-value
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
                f"gemiddeld over {n_reliable} betrouwbare sessies",
                color=adv_color,
            ),
            _stat_card(
                "Sessies met hersteldata",
                str(n_total),
                "sessies waarvoor τ kon worden berekend",
            ),
            _stat_card(
                "Betrouwbare sessies",
                f"{n_reliable}/{n_total}",
                f"slechte fit: {n_bad_fit} · stress te laag: {n_low_pre}",
            ),
            _stat_card(
                "p-waarde (groep)",
                p_str,
                p_sub,
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
                f"Kolom 'advantage' ontbreekt. Beschikbare kolommen: {available}."
            )
        return go.FigureWidget(_recovery_scatter(df))

    @output
    @render.ui
    def honest_framing():
        df = _participant_data()
        if df.empty:
            return _ui.div()

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
            f"Over alle deelnemers zijn {n_rel} van {n_tot} sessies betrouwbaar. "
            f"Gemiddeld groepsvoordeel: {adv_str} — {p_str}, {sig_str}. "
            "Interpreteer als richting, niet als bewijs — N is te klein voor conclusies.",
            class_="mt-callout",
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
