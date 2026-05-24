"""Pagina 5 -- Afspelen: biometrische boog van een echte sessie."""
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
from shiny import module, reactive, render, ui as _ui
from shinywidgets import output_widget, render_widget

from utils.chart_helpers import ACCENT, GRID_COLOR, PLAYLIST_COLORS, STRESS_RED, TEXT_SECONDARY, dark_layout, empty_figure
from utils.data_loader import PARTICIPANTS, AppData

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


def _biometric_chart(trace_df: pd.DataFrame, playlist: str) -> go.Figure:
    if trace_df.empty or "minutes_relative" not in trace_df.columns:
        return empty_figure("Geen trace-data beschikbaar voor deze sessie")

    color = PLAYLIST_COLORS.get(playlist, ACCENT)
    t = trace_df["minutes_relative"]

    fig = go.Figure()

    # Tijdens-sessie kleurregio
    if "phase" in trace_df.columns:
        during = trace_df[trace_df["phase"] == "during"]
        if not during.empty:
            t0 = float(during["minutes_relative"].min())
            t1 = float(during["minutes_relative"].max())
            fig.add_vrect(x0=t0, x1=t1,
                          fillcolor="rgba(59,130,246,0.09)", line_width=0)
            fig.add_vline(x=t0, line_dash="dash", line_color=TEXT_SECONDARY, line_width=1)
            fig.add_vline(x=t1, line_dash="dash", line_color=TEXT_SECONDARY, line_width=1)

    if "stress" in trace_df.columns:
        fig.add_trace(go.Scatter(
            x=t, y=trace_df["stress"],
            mode="lines", name="Stress",
            line=dict(color=STRESS_RED, width=2),
            yaxis="y1",
            hovertemplate="Min %{x:.0f}: Stress %{y:.0f}<extra></extra>",
        ))

    if "heart_rate" in trace_df.columns:
        fig.add_trace(go.Scatter(
            x=t, y=trace_df["heart_rate"],
            mode="lines", name="Hartslag",
            line=dict(color=ACCENT, width=2),
            yaxis="y2",
            hovertemplate="Min %{x:.0f}: Hartslag %{y:.0f} bpm<extra></extra>",
        ))

    fig.update_layout(**dark_layout(
        xaxis=dict(title="Minuten t.o.v. sessiestart", gridcolor=GRID_COLOR, zeroline=False),
        yaxis=dict(title="Stress (0-100)", range=[0, 100], gridcolor=GRID_COLOR),
        yaxis2=dict(title="Hartslag (bpm)", overlaying="y", side="right",
                    range=[40, 130], showgrid=False),
        height=320,
        legend=dict(orientation="h", y=-0.25),
    ))
    return fig


def _phase_durations(trace_df: pd.DataFrame):
    if trace_df.empty or "phase" not in trace_df.columns:
        return 60, 30, 60
    phases = trace_df.groupby("phase")["minutes_relative"].agg(["min", "max"])

    def _dur(phase):
        if phase in phases.index:
            return max(5, int(phases.loc[phase, "max"] - phases.loc[phase, "min"]))
        return 30

    return _dur("pre"), _dur("during"), _dur("post")


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
        delta_col = ACCENT if delta > 0 else (STRESS_RED if delta < 0 else TEXT_SECONDARY)

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
    try:
        adv = float(row.get("tau_advantage", None))
    except (TypeError, ValueError):
        return _ui.div(
            "Hersteldata niet beschikbaar voor deze sessie.",
            class_="mt-body mt-secondary",
            style="text-align:center; padding:24px;",
        )

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

    badge_color = "#6b7280" if not r2_ok else color

    return _ui.div(
        _ui.div(
            f"{sign}{adv:.0f} minuten" if r2_ok else "? minuten",
            class_="mt-h2",
            style=f"color:{badge_color};",
        ),
        _ui.div(label, class_="mt-body mt-secondary", style="margin-top:6px;"),
        _ui.div(footnote, class_="mt-caption mt-secondary",
                style="margin-top:8px;") if footnote else _ui.div(),
        _ui.div(r2_warning, class_="mt-caption",
                style="color:#f59e0b; margin-top:4px;") if r2_warning else _ui.div(),
        class_="mt-card",
        style="text-align:center; max-width:480px; margin:0 auto;",
    )


# ---------------------------------------------------------------------------
# Module UI
# ---------------------------------------------------------------------------

@module.ui
def ui():
    return _ui.div(
        # Sessieselector
        _ui.div(
            _ui.div("Selecteer sessie", class_="mt-h3", style="margin-bottom:16px;"),
            _ui.div(
                _ui.output_ui("participant_pills"),
                style="margin-bottom:16px;",
            ),
            _ui.div(
                _ui.div(
                    _ui.input_action_button("prev_session", "< Vorige", class_="mt-session-nav-btn"),
                    _ui.input_select("session_date", None, choices=[], width="280px"),
                    _ui.input_action_button("next_session", "Volgende >", class_="mt-session-nav-btn"),
                    _ui.output_ui("session_badge"),
                    style="display:flex; align-items:center; gap:12px; flex-wrap:wrap;",
                ),
            ),
            class_="mt-section-card",
            style="margin:32px 80px; padding:24px 32px;",
        ),

        # Sessie-samenvatting
        _ui.div(
            _ui.output_ui("session_summary"),
            style="padding:0 80px 16px;",
        ),

        # Tijdlijnkoptekst
        _ui.div(
            _ui.output_ui("timeline_header"),
            style="margin:0 80px;",
        ),

        # Biometrische grafiek
        _ui.div(
            output_widget("biometric_chart"),
            class_="mt-section-card",
            style="margin:0 80px; border-radius:0 0 12px 12px;",
        ),

        # Stemming-arc
        _ui.output_ui("mood_arc_ui"),

        # Herstelbadge
        _ui.div(
            _ui.output_ui("recovery_badge_ui"),
            style="padding:8px 80px 32px;",
        ),

        # Transparantienota
        _ui.div(
            _ui.em("Dit zijn jouw werkelijke fysiologische gegevens. Niets is gesimuleerd of geinterpoleerd.",
                   class_="mt-caption mt-secondary"),
            style="text-align:center; padding-bottom:48px;",
        ),
    )


# ---------------------------------------------------------------------------
# Module server
# ---------------------------------------------------------------------------

@module.server
def server(input, output, session, app_data: AppData):
    selected_participant: reactive.Value = reactive.Value("bosbes")

    @output
    @render.ui
    def participant_pills():
        curr = selected_participant()
        pills = []
        for p in PARTICIPANTS:
            has       = app_data.has_traces.get(p, False)
            is_active = (p == curr)
            cls = "pill-btn"
            if is_active:
                cls += " active"
            if not has:
                cls += " disabled"
                if p in _NO_WEARABLES:
                    cls += " no-wearable"
            btn = _ui.input_action_button(f"rpill_{p}", p.capitalize(), class_=cls)
            if not has:
                tip = ("Geen biometrische data (alleen stemming-check-ins)"
                       if p in _NO_WEARABLES
                       else "Geen sessie-traces voor deze deelnemer")
                btn = _ui.tags.span(btn, title=tip)
            pills.append(btn)
        return _ui.div(*pills, class_="pill-group")

    for _p in PARTICIPANTS:
        def _make_obs(participant=_p):
            @reactive.Effect
            @reactive.event(input[f"rpill_{participant}"])
            def _():
                if app_data.has_traces.get(participant, False):
                    selected_participant.set(participant)
        _make_obs()

    @reactive.Calc
    def available_dates():
        p       = selected_participant()
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
    @reactive.event(input[f"rpill_{PARTICIPANTS[0]}"],
                    *[input[f"rpill_{p}"] for p in PARTICIPANTS])
    def _noop():
        pass  # Forces re-evaluation when participant changes (handled by pill observers)

    @reactive.Effect
    def _update_dates():
        _ = selected_participant()   # track dependency
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
        p    = selected_participant()
        date = input.session_date()
        if not date:
            return pd.DataFrame()
        return app_data.session_traces.get(p, {}).get(date, pd.DataFrame())

    @reactive.Calc
    def current_bio_row():
        p    = selected_participant()
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
            _item(_fmt_date_nl(date_str), "Datum"),
            _item(start, "Starttijd"),
            _item(dur_str, "Duur"),
            _ui.div(
                pl_badge,
                _ui.div("Afspeellijst", class_="mt-session-summary-label", style="margin-top:6px;"),
                class_="mt-session-summary-item",
            ),
            class_="mt-session-summary-card",
            style="margin:0 80px;",
        )

    @output
    @render.ui
    def timeline_header():
        trace = current_trace()
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
    @render_widget
    def biometric_chart():
        return _biometric_chart(current_trace(), current_playlist())

    @output
    @render.ui
    def mood_arc_ui():
        row = current_bio_row()
        return _mood_arc(row) if not row.empty else _ui.div()

    @output
    @render.ui
    def recovery_badge_ui():
        p    = selected_participant()
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
