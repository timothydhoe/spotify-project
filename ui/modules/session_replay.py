"""Pagina 5 -- Afspelen: biometrische boog van een echte sessie."""
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
from shiny import module, reactive, render, ui as _ui
from shinywidgets import output_widget, render_widget

from utils.chart_helpers import ACCENT, AXIS_DEFAULTS, GRID_COLOR, PLAYLIST_COLORS, STRESS_RED, TEXT_SECONDARY, chart_layout, empty_figure
from utils.data_loader import PARTICIPANTS, AppData
from utils.mood_valence import mood_is_improvement

_DAYS_NL      = ["ma", "di", "wo", "do", "vr", "za", "zo"]
_MONTHS_NL    = ["jan", "feb", "mrt", "apr", "mei", "jun",
                 "jul", "aug", "sep", "okt", "nov", "dec"]
_NO_WEARABLES = {"kiwi", "watermeloen"}

_MOOD_EMOJI = {
    "gestresseerd":  "😟",
    "moe":           "😔",
    "ongemotiveerd": "😔",
    "neutraal":      "😐",
    "rustig":        "😌",
    "happy":         "😊",
    "gemotiveerd":   "💪",
    "blij":          "😄",
}
_MOOD_ORDER = ["gestresseerd", "moe", "ongemotiveerd", "neutraal",
               "rustig", "happy", "gemotiveerd", "blij"]
_MOOD_RANK  = {m: i for i, m in enumerate(_MOOD_ORDER)}

_PLAYLIST_NL = {"Calm": "Kalm", "Neutral": "Neutraal", "Energy": "Energiek"}


def _fmt_date_nl(date_str: str) -> str:
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return f"{_DAYS_NL[dt.weekday()]} {dt.day} {_MONTHS_NL[dt.month - 1]}. {dt.year}"
    except Exception:
        return date_str


def _emoji_for(mood: str) -> str:
    if not isinstance(mood, str):
        return "😐"
    lower = mood.lower()
    for key, emoji in _MOOD_EMOJI.items():
        if key in lower:
            return emoji
    return "😐"


def _shift_emoji(label: str, delta: float) -> str:
    if delta == 0:
        return _emoji_for(label)
    lower = label.lower()
    rank = None
    for key in _MOOD_ORDER:
        if key in lower:
            rank = _MOOD_RANK[key]
            break
    if rank is None:
        return _emoji_for(label)
    shifted = max(0, min(len(_MOOD_ORDER) - 1, rank + (1 if delta > 0 else -1)))
    return _emoji_for(_MOOD_ORDER[shifted])


_ISO_FASE_LABELS = ["Ontmoeting", "De-escalatie", "Regulatie", "Landing"]
_ISO_FASE_FILLS  = [
    "rgba(59,130,246,0.08)",
    "rgba(59,130,246,0.13)",
    "rgba(59,130,246,0.18)",
    "rgba(59,130,246,0.24)",
]


def _biometric_chart(
    trace_df: pd.DataFrame, playlist: str,
    baseline_stress: float | None = None,
    baseline_std: float | None = None,
    session_hour: int | None = None,
) -> go.Figure:
    if trace_df.empty or "minutes_relative" not in trace_df.columns:
        return empty_figure(
            "Geen per-minuut trace beschikbaar — "
            "controleer of het FIT-bestand voor deze sessie verwerkt is."
        )

    color = PLAYLIST_COLORS.get(playlist, ACCENT)
    t     = trace_df["minutes_relative"]

    fig = go.Figure()

    # Baseline stress band (2.4) — drawn first so it appears behind the data
    if baseline_stress is not None and baseline_std is not None:
        fig.add_hrect(
            y0=max(0, baseline_stress - baseline_std),
            y1=min(100, baseline_stress + baseline_std),
            fillcolor="rgba(34,197,94,0.10)", line_width=0,
        )
        hour_label = f" {session_hour:02d}:00" if session_hour is not None else ""
        fig.add_hline(
            y=baseline_stress,
            line_dash="dot",
            line_color="rgba(34,197,94,0.45)",
            line_width=1.5,
            annotation_text=f"Jouw basislijn{hour_label} ({baseline_stress:.0f} pt)",
            annotation_position="top right",
            annotation_font_size=10,
            annotation_font_color="rgba(34,197,94,0.8)",
        )

    # Tijdens-sessie: ISO fase-overlay (4 gelijke segmenten)
    during_end = None
    if "phase" in trace_df.columns:
        during = trace_df[trace_df["phase"] == "during"]
        if not during.empty:
            t0  = float(during["minutes_relative"].min())
            t1  = float(during["minutes_relative"].max())
            dur = t1 - t0
            during_end = t1
            for i, (label, fill) in enumerate(zip(_ISO_FASE_LABELS, _ISO_FASE_FILLS)):
                seg_t0 = t0 + i * dur / 4
                seg_t1 = t0 + (i + 1) * dur / 4
                fig.add_vrect(
                    x0=seg_t0, x1=seg_t1,
                    fillcolor=fill, line_width=0,
                    annotation_text=label,
                    annotation_position="top left",
                    annotation_font_size=10,
                    annotation_font_color=TEXT_SECONDARY,
                )
            fig.add_vline(x=t0, line_dash="dash", line_color=TEXT_SECONDARY, line_width=1)
            fig.add_vline(x=t1, line_dash="dash", line_color=TEXT_SECONDARY, line_width=1)

    if "stress" in trace_df.columns:
        fig.add_trace(go.Scatter(
            x=t, y=trace_df["stress"],
            mode="lines", name="Stress",
            line=dict(color=STRESS_RED, width=2),
            connectgaps=False,
            yaxis="y1",
            hovertemplate="Min %{x:.0f}: Stress %{y:.0f}<extra></extra>",
        ))

    if "heart_rate" in trace_df.columns:
        fig.add_trace(go.Scatter(
            x=t, y=trace_df["heart_rate"],
            mode="lines", name="Hartslag",
            line=dict(color=ACCENT, width=2),
            connectgaps=False,
            yaxis="y2",
            hovertemplate="Min %{x:.0f}: Hartslag %{y:.0f} bpm<extra></extra>",
        ))

    has_stress = "stress" in trace_df.columns
    has_hr     = "heart_rate" in trace_df.columns

    yaxis1_title = "Stress (0-100)" if has_stress else "—"
    yaxis2_cfg   = dict(
        **AXIS_DEFAULTS,
        title="Hartslag (bpm)", overlaying="y", side="right",
        range=[40, 130], showgrid=False,
    ) if has_hr else dict(visible=False, overlaying="y", side="right", showgrid=False)

    # 2.2 Set x-axis to ±30 min around the session
    x_range = None
    if during_end is not None:
        x_range = [-30, during_end + 30]
    elif not t.empty:
        x_range = [max(t.min(), t.min()), t.max()]

    fig.update_layout(**chart_layout(
        xaxis=dict(
            title="Minuten t.o.v. sessiestart (tijdvenster: ±30 min)",
            gridcolor=GRID_COLOR, zeroline=False,
            **({"range": x_range} if x_range else {}),
        ),
        yaxis=dict(title=yaxis1_title, range=[0, 100] if has_stress else None,
                   gridcolor=GRID_COLOR, visible=has_stress),
        yaxis2=yaxis2_cfg,
        height=340,
        legend=dict(orientation="h", y=-0.25),
    ))
    return fig


def _data_quality_note(trace_df: pd.DataFrame) -> _ui.Tag:
    """2.3 — Explain data coverage and gap causes for the biometric chart."""
    if trace_df.empty:
        return _ui.div()

    has_stress = "stress" in trace_df.columns
    has_hr     = "heart_rate" in trace_df.columns
    during     = trace_df[trace_df["phase"] == "during"] if "phase" in trace_df.columns else trace_df

    lines = []

    # Stress coverage
    if not has_stress:
        lines.append(_ui.div(
            "⚠ Stressdata volledig afwezig — dit Garmin-model beschikt mogelijk niet over een stresssensor, "
            "of het horloge is niet gedragen tijdens deze sessie.",
            style="color:#f59e0b; font-size:11px;",
        ))
    elif not during.empty:
        filled_pct = during["stress"].notna().mean() * 100
        color = "#22c55e" if filled_pct > 80 else ("#f59e0b" if filled_pct > 50 else "#ef4444")
        if filled_pct < 90:
            reason = "horloge afgedaan of aan het opladen" if filled_pct < 50 else "korte onderbrekingen in sensorcontact"
            lines.append(_ui.div(
                f"Stressdata: {filled_pct:.0f}% beschikbaar — gaten door {reason}.",
                style=f"color:{color}; font-size:11px;",
            ))
        else:
            lines.append(_ui.div(
                f"Stressdata: volledig ({filled_pct:.0f}%)",
                style="color:#22c55e; font-size:11px;",
            ))

    # HR coverage
    if not has_hr:
        lines.append(_ui.div(
            "⚠ Hartslagdata afwezig voor deze sessie.",
            style="color:#f59e0b; font-size:11px;",
        ))

    # Data transparency details (always shown, collapsed)
    details_html = (
        '<details class="mt-details" style="margin-top:8px;">'
        '<summary style="font-size:11px; color:var(--text-tertiary); cursor:pointer;">Over de datakwaliteit</summary>'
        '<div class="mt-details-body" style="font-size:11px; color:var(--text-tertiary); margin-top:6px; line-height:1.6;">'
        '<b>Stress:</b> Berekend op basis van hartslagvariabiliteit (HRV) — vereist een meetvenster van ≈3 minuten. '
        'Tussen twee berekeningen is er geen stresswaarde; niets wordt geschat of aangevuld. '
        'Bij afdoen of opladen ontstaan langere gaten.<br>'
        '<b>Hartslag:</b> Continu gemeten maar kan ontbreken bij slechte huidcontact of intense beweging.<br>'
        '<b>Geen interpolatie:</b> Alle waarden zijn exact zoals gemeten — de data is nooit gesimuleerd of bijgeschat.'
        '</div></details>'
    )

    if not lines:
        return _ui.div(
            _ui.HTML(details_html),
            style="margin-top:6px;",
        )

    return _ui.div(
        *lines,
        _ui.HTML(details_html),
        style="margin-top:8px;",
    )


def _mood_bio_comparison(bio_row: pd.Series) -> _ui.Tag:
    """Compare self-reported mood state to biometric pre-session stress."""
    try:
        pre_stress = float(bio_row.get("pre_stress_mean"))
        mood_score = float(bio_row.get("mood_before_score"))
        mood_label = str(bio_row.get("mood_before", "")).lower().strip()
    except (TypeError, ValueError):
        return _ui.div()
    import math
    if math.isnan(pre_stress) or math.isnan(mood_score):
        return _ui.div()

    # Determine expected stress direction from mood label
    from utils.mood_valence import emotion_valence
    valence = emotion_valence(mood_label)
    # Negative mood label = expect higher stress; positive = expect lower stress
    stress_high = pre_stress > 55
    mood_negative = valence < 0
    mood_positive = valence > 0

    if mood_negative and stress_high:
        status  = "Overeenkomst"
        detail  = f"Hoge biometrische stress ({pre_stress:.0f}) stemt overeen met negatieve stemming '{mood_label}' (score {mood_score:.0f}/10)."
        color   = "#22c55e"
    elif mood_positive and not stress_high:
        status  = "Overeenkomst"
        detail  = f"Lage biometrische stress ({pre_stress:.0f}) stemt overeen met positieve stemming '{mood_label}' (score {mood_score:.0f}/10)."
        color   = "#22c55e"
    elif mood_negative and not stress_high:
        status  = "Onovereenkomst"
        detail  = (
            f"Biometrische stress is laag ({pre_stress:.0f}) maar stemming is negatief "
            f"('{mood_label}', score {mood_score:.0f}/10). Mogelijk emotionele vermoeidheid "
            "zonder fysieke activatie, of horloge droeg niet goed."
        )
        color   = "#f59e0b"
    elif mood_positive and stress_high:
        status  = "Onovereenkomst"
        detail  = (
            f"Biometrische stress is hoog ({pre_stress:.0f}) maar stemming is positief "
            f"('{mood_label}', score {mood_score:.0f}/10). Mogelijk cognitieve uitdaging zonder "
            "negatief affect, of verhoogde alertheid."
        )
        color   = "#f59e0b"
    else:
        # Neutral mood or borderline stress — no clear mismatch
        return _ui.div()

    return _ui.div(
        _ui.span(status, style=f"font-weight:700; color:{color}; margin-right:8px;"),
        _ui.span(detail, style="font-size:12px; color:var(--text-secondary);"),
        style=(
            f"border-left:3px solid {color}; padding:8px 12px; "
            "background:var(--bg-elevated); border-radius:0 4px 4px 0; "
            "margin-top:12px; font-size:12px;"
        ),
    )


def _phase_durations(trace_df: pd.DataFrame):
    """Return (pre, during, post) visible window durations for the timeline header.

    The chart always shows ±30 min on each side of the session, so VOOR and NA
    are always 30 min in the visible window — matching the chart x-axis range
    [-30, during_end + 30]. Using actual data durations (e.g. 59 min) caused
    TIJDENS SESSIE to appear narrower than the blue zone inside the chart.
    """
    if trace_df.empty or "phase" not in trace_df.columns:
        return 30, 30, 30
    during = trace_df[trace_df["phase"] == "during"]
    if during.empty:
        return 30, 30, 30
    dur_dur = max(5, int(during["minutes_relative"].max() - during["minutes_relative"].min()))
    return 30, dur_dur, 30


def _mood_arc(bio_row: pd.Series) -> _ui.Tag:
    before_label = str(bio_row.get("mood_before", "—"))
    after_label  = str(bio_row.get("mood_after",  "—"))
    try:
        before_score = float(bio_row.get("mood_before_score", None))
    except (TypeError, ValueError):
        before_score = None
    try:
        after_score = float(bio_row.get("mood_after_score", None))
    except (TypeError, ValueError):
        after_score = None

    delta     = (after_score - before_score) if (before_score is not None and after_score is not None) else 0
    delta_str = "—"
    delta_col = TEXT_SECONDARY
    if before_score is not None and after_score is not None:
        sign      = "+" if delta >= 0 else ""
        delta_str = f"{sign}{delta:.0f} pt"
        # Use composite-based improvement rather than raw delta direction
        improved = mood_is_improvement(before_label, before_score, after_label, after_score)
        delta_col = ACCENT if improved is True else (STRESS_RED if improved is False else TEXT_SECONDARY)

    def _card(label, score, side, shifted=False):
        score_str = f"{int(score)}/10" if score is not None else ""
        emoji = _shift_emoji(label, delta) if shifted else _emoji_for(label)
        return _ui.div(
            _ui.div(side, class_="mt-caption mt-secondary"),
            _ui.div(emoji, style="font-size:32px; margin:6px 0;"),
            _ui.div(label.capitalize() if label != "—" else "—",
                    class_="mt-body", style="font-weight:500;"),
            _ui.div(score_str, class_="mt-caption mt-secondary") if score_str else _ui.div(),
            class_="mt-mood-card",
        )

    return _ui.div(
        _card(before_label, before_score, "Voor"),
        _ui.div(
            _ui.div("->", style=f"color:{ACCENT}; font-size:24px; font-weight:700;"),
            _ui.div(delta_str, class_="mt-caption", style=f"color:{delta_col}; margin-top:4px;"),
            style="text-align:center; min-width:64px;",
        ),
        _card(after_label, after_score, "Na", shifted=True),
        class_="mt-mood-arc",
    )


def _recovery_badge(row: pd.Series) -> _ui.Tag:
    import math as _math
    try:
        adv = float(row.get("tau_advantage", None))
        if _math.isnan(adv):
            raise ValueError
    except (TypeError, ValueError):
        return _ui.div()  # no badge frame when data is absent

    sign  = "+" if adv > 0 else ""
    color = ACCENT if adv > 0 else STRESS_RED
    label = "sneller herstel dan jouw circadiane basislijn" if adv > 0 else "trager herstel dan basislijn"

    footnote   = ""
    r2_warning = ""
    r2_ok      = True
    try:
        tau_exp  = float(row.get("tau_expected"))
        tau_act  = float(row.get("tau_actual"))
        r2       = float(row.get("r2_actual"))
        footnote = (
            f"Verwachte hersteltijd: {tau_exp:.0f} min | "
            f"Werkelijk: {tau_act:.0f} min | "
            f"Betrouwbaarheid: {'laag' if r2 < 0.3 else 'voldoende'} (R²={r2:.2f})"
        )
        if r2 < 0.3:
            r2_ok = False
            r2_warning = "Herstelcurve is ruis bij lage R² — schatting van tau is benaderend."
    except (TypeError, ValueError):
        pass

    badge_color = "rgba(255,255,255,0.45)" if not r2_ok else color

    # Build technical footnote as a collapsible details element
    if footnote:
        r2_note = (
            f'<p style="color:#f59e0b; margin:6px 0 0; font-size:0.8125rem;">'
            f"⚠ {r2_warning}</p>" if r2_warning else ""
        )
        details_html = (
            '<details class="mt-details" style="margin-top:12px;">'
            '<summary>Technische details</summary>'
            f'<div class="mt-details-body">{footnote}{r2_note}</div>'
            '</details>'
        )
    else:
        details_html = ""

    card_style = "text-align:center; max-width:480px; margin:0 auto;"
    if not r2_ok:
        card_style += " border:2px solid #f59e0b;"

    return _ui.div(
        _ui.div(
            f"{sign}{adv:.0f} minuten" if r2_ok else "~ minuten",
            class_="mt-h2",
            style=f"color:{badge_color};",
        ),
        _ui.div(label, class_="mt-body mt-secondary", style="margin-top:6px;"),
        _ui.HTML(details_html) if details_html else _ui.div(),
        class_="mt-card",
        style=card_style,
    )


# ---------------------------------------------------------------------------
# Module UI
# ---------------------------------------------------------------------------

@module.ui
def ui():
    return _ui.div(
        # ── Slim header: navigator + compact session stats ────────────────────
        # All key identifiers in one tight row — no standalone card title
        _ui.div(
            _ui.div(
                _ui.output_ui("nav_prev_btn"),
                _ui.input_select("session_date", None, choices=[], width="240px"),
                _ui.output_ui("nav_next_btn"),
                _ui.output_ui("session_badge"),
                style=(
                    "display:flex; align-items:center; gap:10px; flex-wrap:wrap; "
                    "padding-bottom:10px; border-bottom:1px solid var(--border-subtle); "
                    "margin-bottom:10px;"
                ),
            ),
            # Session stats row: date · starttime · duration (compact)
            _ui.output_ui("session_summary"),
            class_="mt-section-card mt-replay-header",
            style="margin:8px var(--page-margin) 0; padding:14px 20px 12px;",
        ),

        # ── THE STAR: chart card, full width, immediately visible ─────────────
        _ui.div(
            _ui.output_ui("timeline_header"),   # VOOR / TIJDENS SESSIE / NA
            output_widget("biometric_chart"),
            class_="mt-section-card mt-replay-chart",
            style="margin:8px var(--page-margin) 0; padding:12px 24px 16px;",
        ),

        # ── Unified result card: outcome + mood + data quality in ONE box ────────
        _ui.div(
            _ui.div(
                _ui.output_ui("outcome_banner"),
                _ui.output_ui("mood_arc_ui"),
                _ui.output_ui("data_quality_ui"),
                class_="mt-replay-context",
            ),
            style="padding:0 var(--page-margin) 16px;",
        ),
    )


# ---------------------------------------------------------------------------
# Module server
# ---------------------------------------------------------------------------

@module.server
def server(input, output, session, app_data: AppData, selected_participant=None):
    sel = selected_participant if selected_participant is not None else reactive.Value("bosbes")

    @reactive.Calc
    def available_dates():
        p       = sel()
        traces  = app_data.session_traces.get(p, {})
        bio     = app_data.session_biometrics.get(p, pd.DataFrame())
        sorted_dates = sorted(traces.keys(), reverse=True)

        # Bouw gelabelde choices: "vr 3 jan. 2026 - Kalm"
        choices = {}
        for d in sorted_dates:
            lbl = _fmt_date_nl(d)
            pl  = "—"
            if not bio.empty and "date" in bio.columns and "playlist" in bio.columns:
                mask = bio["date"].astype(str).str[:10] == d
                if mask.any():
                    raw = bio[mask].iloc[0].get("playlist", "—")
                    pl  = _PLAYLIST_NL.get(str(raw).strip(), str(raw))
            choices[d] = f"{lbl}   {pl}"
        return sorted_dates, choices

    @reactive.Effect
    def _update_dates():
        _ = sel()   # track dependency
        dates, choices = available_dates()
        _ui.update_select("session_date",
                          choices=choices,
                          selected=dates[0] if dates else None,
                          session=session)

    @reactive.Calc
    def session_index_val():
        dates, _ = available_dates()
        current  = input.session_date()
        if current in dates:
            return dates.index(current)
        return 0

    @output
    @render.ui
    def nav_prev_btn():
        dates, _ = available_dates()
        at_end = session_index_val() >= len(dates) - 1
        style = "opacity:0.35; pointer-events:none;" if at_end else ""
        return _ui.input_action_button(
            "prev_session", "< Vorige", class_="mt-session-nav-btn", style=style
        )

    @output
    @render.ui
    def nav_next_btn():
        idx = session_index_val()
        style = "opacity:0.35; pointer-events:none;" if idx <= 0 else ""
        return _ui.input_action_button(
            "next_session", "Volgende >", class_="mt-session-nav-btn", style=style
        )

    @reactive.Effect
    @reactive.event(input.prev_session)
    def _go_prev():
        dates, choices = available_dates()
        idx = session_index_val()
        if idx < len(dates) - 1:
            _ui.update_select("session_date", selected=dates[idx + 1],
                              choices=choices, session=session)

    @reactive.Effect
    @reactive.event(input.next_session)
    def _go_next():
        dates, choices = available_dates()
        idx = session_index_val()
        if idx > 0:
            _ui.update_select("session_date", selected=dates[idx - 1],
                              choices=choices, session=session)

    @reactive.Calc
    def current_trace():
        p    = sel()
        date = input.session_date()
        if not date:
            return pd.DataFrame()
        return app_data.session_traces.get(p, {}).get(date, pd.DataFrame())

    @reactive.Calc
    def current_bio_row():
        p    = sel()
        date = (input.session_date() or "")[:10]
        bio  = app_data.session_biometrics.get(p, pd.DataFrame())
        if bio.empty:
            return pd.Series(dtype=object)
        mask = bio["date"].astype(str).str[:10] == date
        if not mask.any():
            return pd.Series(dtype=object)
        return bio[mask].iloc[0]

    @reactive.Calc
    def current_playlist():
        trace = current_trace()
        if not trace.empty and "playlist" in trace.columns:
            vals = trace["playlist"].dropna()
            if not vals.empty:
                return str(vals.iloc[0])
        row = current_bio_row()
        return str(row.get("playlist", "Calm")) if not row.empty else "Calm"

    @output
    @render.ui
    def session_badge():
        pl    = current_playlist()
        color = PLAYLIST_COLORS.get(pl, ACCENT)
        nl    = _PLAYLIST_NL.get(pl, pl)
        dates, _ = available_dates()
        idx   = session_index_val()
        total = len(dates)
        badge_num = _ui.span(
            f"Sessie {total - idx} van {total}",
            style="color:#B3B3B3; font-size:13px;",
        ) if total > 0 else _ui.div()
        return _ui.div(
            _ui.span(
                nl.upper(),
                style=(
                    f"background:{color}; color:#000; font-weight:600; font-size:11px;"
                    "padding:4px 12px; border-radius:20px; letter-spacing:1px;"
                ),
            ),
            badge_num,
            style="display:flex; align-items:center; gap:10px;",
        )

    @output
    @render.ui
    def session_summary():
        row = current_bio_row()
        if row.empty:
            return _ui.div()

        pl    = current_playlist()
        color = PLAYLIST_COLORS.get(pl, ACCENT)
        nl    = _PLAYLIST_NL.get(pl, pl)

        date_str = str(row.get("date", ""))[:10]
        start    = str(row.get("start_local", "—"))
        dur      = row.get("duration_min", "—")
        dur_str  = f"{int(dur)} min" if dur != "—" else "—"

        def _item(val, label):
            return _ui.div(
                _ui.div(str(val), class_="mt-session-summary-value"),
                _ui.div(label, class_="mt-session-summary-label"),
                class_="mt-session-summary-item",
            )

        pl_badge = _ui.span(
            nl.upper(),
            style=f"background:{color}; color:#000; font-weight:700; font-size:13px; "
                  "padding:3px 10px; border-radius:12px; letter-spacing:0.5px;",
        )

        return _ui.div(
            _ui.div(
                _item(_fmt_date_nl(date_str), "Datum"),
                _item(start, "Starttijd"),
                _item(dur_str, "Duur"),
                _ui.div(
                    pl_badge,
                    _ui.div("Afspeellijst", class_="mt-session-summary-label", style="margin-top:6px;"),
                    class_="mt-session-summary-item",
                ),
                class_=f"mt-session-summary-card mt-card-{pl.lower()}",
            ),
            _mood_bio_comparison(row),
            style="margin:0 var(--page-margin);",
        )

    @output
    @render.ui
    def timeline_header():
        trace = current_trace()
        if trace.empty:
            return _ui.div(
                "Fase-tijdlijn niet beschikbaar voor deze sessie.",
                class_="mt-caption mt-secondary",
                style="text-align:center; padding:8px 0;",
            )
        pre_dur, dur_dur, post_dur = _phase_durations(trace)

        def _phase_cell(label, dur_min, extra_cls):
            return _ui.div(
                _ui.div(label, class_=f"mt-timeline-phase {extra_cls}",
                        style="flex:1;"),
                _ui.div(f"{dur_min} min", class_="mt-caption mt-secondary",
                        style="text-align:center; font-size:10px; padding-bottom:4px;"),
                style="display:flex; flex-direction:column;",
            )

        return _ui.div(
            _phase_cell("VOOR", pre_dur, "pre"),
            _phase_cell("TIJDENS SESSIE", dur_dur, "during"),
            _phase_cell("NA", post_dur, "post"),
            class_="mt-timeline-header",
            style=f"grid-template-columns:{pre_dur}fr {dur_dur}fr {post_dur}fr;",
        )

    @output
    @render.ui
    def outcome_banner():
        row = current_bio_row()
        if row.empty:
            return _ui.div()
        try:
            before = float(row.get("mood_before_score"))
            after  = float(row.get("mood_after_score"))
        except (TypeError, ValueError):
            return _ui.div()
        import math
        if math.isnan(before) or math.isnan(after):
            return _ui.div()
        delta         = after - before
        before_label  = str(row.get("mood_before", ""))
        after_label   = str(row.get("mood_after",  ""))
        improved      = mood_is_improvement(before_label, before, after_label, after)
        sign          = f"+{delta:.0f}" if delta >= 0 else f"{delta:.0f}"
        if improved is True:
            bg     = "rgba(34,197,94,0.15)"
            border = "#22c55e"
            icon   = "✓"
            txt    = f"Stemming verbeterd ({sign} pt)"
        elif improved is False:
            bg     = "rgba(239,68,68,0.12)"
            border = "#ef4444"
            icon   = "✗"
            txt    = f"Stemming gedaald ({sign} pt)"
        else:
            bg     = "var(--bg-elevated)"
            border = "var(--text-tertiary)"
            icon   = "–"
            txt    = "Stemming onveranderd"
        return _ui.div(
            _ui.span(icon, style=f"font-size:20px; color:{border}; margin-right:10px; font-weight:700;"),
            _ui.span(txt,  style=f"font-size:16px; font-weight:600; color:{border};"),
            style=(
                f"display:flex; align-items:center; padding:12px 20px; "
                f"background:{bg}; border:1px solid {border}; "
                "border-radius:10px;"
            ),
        )

    @output
    @render_widget
    def biometric_chart():
        from utils.data_loader import expected_stress
        trace = current_trace()
        row   = current_bio_row()
        bl_mean, bl_std, hour = None, None, None
        if not row.empty:
            try:
                hour = int(row.get("hour_of_day", 17))
            except (TypeError, ValueError):
                hour = None
            if hour is not None:
                bl_mean, bl_std = expected_stress(app_data, sel(), hour)
        return _biometric_chart(trace, current_playlist(), bl_mean, bl_std, hour)

    @output
    @render.ui
    def data_quality_ui():
        return _data_quality_note(current_trace())

    @output
    @render.ui
    def mood_arc_ui():
        row = current_bio_row()
        return _mood_arc(row) if not row.empty else _ui.div()

    @output
    @render.ui
    def recovery_badge_ui():
        p    = sel()
        date = (input.session_date() or "")[:10]
        sf   = app_data.session_features.get(p, pd.DataFrame())
        if not sf.empty and "date" in sf.columns:
            mask = sf["date"].astype(str).str[:10] == date
            if mask.any():
                return _recovery_badge(sf[mask].iloc[0])
        row = current_bio_row()
        if not row.empty:
            return _recovery_badge(row)
        return _ui.div(
            "Hersteldata niet beschikbaar voor deze sessie.",
            class_="mt-body mt-secondary",
            style="text-align:center; padding:24px;",
        )
