"""Pagina 3 -- Circadiaans ritme: uurlijkse stressbasislijn per deelnemer."""
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from shiny import module, reactive, render, ui as _ui
from shinywidgets import output_widget, render_widget

from utils.chart_helpers import ACCENT, GRID_COLOR, PLAYLIST_COLORS, TEXT_SECONDARY, dark_layout, empty_figure
from utils.data_loader import PARTICIPANTS, AppData, expected_stress


def _img_b64(path: Path) -> str:
    if not path.exists():
        return ""
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def _build_circadian_chart(hb_df, session_df) -> go.Figure:
    if hb_df is None or hb_df.empty:
        return empty_figure("Geen circadiane basislijn beschikbaar voor deze deelnemer")

    hours = hb_df["hour"].values
    mean  = hb_df["mean_stress"].values
    std   = hb_df["std_stress"].values

    fig = go.Figure()

    # +-1 sigma-band
    fig.add_trace(go.Scatter(
        x=np.concatenate([hours, hours[::-1]]),
        y=np.concatenate([mean + std, (mean - std)[::-1]]),
        fill="toself",
        fillcolor="rgba(34,197,94,0.10)",
        line=dict(width=0),
        showlegend=False,
        hoverinfo="skip",
    ))

    # Gemiddelde lijn
    fig.add_trace(go.Scatter(
        x=hours, y=mean,
        mode="lines",
        line=dict(color=ACCENT, width=2),
        name="Jouw gemiddelde stress",
        hovertemplate="Uur %{x}:00 - Gem. stress: %{y:.1f}<extra></extra>",
    ))

    # Sessie-overlay
    if session_df is not None and not session_df.empty and "hour_of_day" in session_df.columns:
        for playlist, color in PLAYLIST_COLORS.items():
            mask = session_df["playlist"].str.strip().str.capitalize() == playlist
            sub  = session_df[mask]
            if sub.empty:
                continue
            fig.add_trace(go.Scatter(
                x=sub["hour_of_day"],
                y=sub["pre_stress_mean"],
                mode="markers",
                marker=dict(color=color, size=9, line=dict(color="white", width=1.5)),
                name=f"{playlist}-sessie",
                hovertemplate=(
                    f"<b>{playlist}-sessie</b><br>"
                    "Uur: %{x}:00<br>"
                    "Pre-sessie stress: %{y:.1f}<extra></extra>"
                ),
            ))

    fig.update_layout(**dark_layout(
        xaxis=dict(
            title="Uur van de dag",
            tickvals=list(range(0, 24, 3)),
            ticktext=[f"{h}:00" for h in range(0, 24, 3)],
            range=[-0.5, 23.5],
            gridcolor=GRID_COLOR,
        ),
        yaxis=dict(title="Stress (0-100)", range=[0, 100], gridcolor=GRID_COLOR),
        height=360,
        legend=dict(orientation="h", y=-0.22),
    ))
    return fig


def _stat_card(value: str, label: str) -> _ui.Tag:
    return _ui.div(
        _ui.div(value, class_="mt-stat-value"),
        _ui.div(label, class_="mt-stat-label"),
        class_="mt-stat-card",
        style="flex:1;",
    )


def _compute_stats(hb_df, session_df):
    if hb_df is None or hb_df.empty:
        return "—", "—", "—"
    calmest_row  = hb_df.loc[hb_df["mean_stress"].idxmin()]
    calmest      = f"{int(calmest_row['hour'])}:00"
    stressed_row = hb_df.loc[hb_df["mean_stress"].idxmax()]
    peak_h       = int(stressed_row["hour"])
    peak         = f"{peak_h}-{peak_h + 2}:00"
    dev_str      = "—"
    if session_df is not None and not session_df.empty and "baseline_deviation_entry" in session_df.columns:
        import pandas as pd
        dev = pd.to_numeric(session_df["baseline_deviation_entry"], errors="coerce").mean()
        if not pd.isna(dev):
            dev_str = f"+{dev:.1f} pt" if dev >= 0 else f"{dev:.1f} pt"
    return calmest, peak, dev_str


# ---------------------------------------------------------------------------
# Module UI
# ---------------------------------------------------------------------------

@module.ui
def ui():
    return _ui.div(
        # Koptekst
        _ui.div(
            _ui.div("Jouw Circadiaans Ritme", class_="mt-h1"),
            _ui.p(
                "Hoe verhoudt jouw stressniveau zich tot jouw eigen basislijn op elk uur van de dag?",
                class_="mt-body mt-secondary",
                style="margin-top:8px;",
            ),
            style="text-align:center; padding:48px 80px 32px;",
        ),

        # Deelnemersselector
        _ui.div(
            _ui.output_ui("participant_pills"),
            style="padding:0 80px 32px; text-align:center;",
        ),

        # Hoofdgrafiek
        _ui.div(
            _ui.div(
                _ui.div(
                    _ui.output_text("chart_title"),
                    class_="mt-h3",
                    style="margin-bottom:4px;",
                ),
                _ui.div(
                    "Alleen niet-sessiedagen - +-1 sigma-band",
                    class_="mt-caption mt-secondary",
                    style="margin-bottom:20px;",
                ),
                output_widget("circadian_chart"),
                class_="mt-section-card",
                style="padding:32px 48px;",
            ),
            style="padding:0 80px;",
        ),

        # Statistiekenrij
        _ui.div(
            _ui.output_ui("stat_row"),
            style="padding:24px 80px; display:flex; gap:16px;",
        ),

        # Afwijkingscalculator
        _ui.div(
            _ui.div(
                _ui.div("Bereken jouw circadiane afwijking", class_="mt-h3", style="margin-bottom:12px;"),
                _ui.p(
                    "Vul het huidige uur en jouw huidige stressniveau in. "
                    "De app berekent dan hoeveel jij afwijkt van jouw normale stressniveau op dat uur.",
                    class_="mt-body mt-secondary",
                    style="margin-bottom:20px;",
                ),
                _ui.div(
                    _ui.div(
                        _ui.div(
                            _ui.span("Huidig uur:", class_="mt-body mt-secondary"),
                            _ui.output_text_verbatim("dev_hour_val", placeholder=True),
                            style="display:flex; justify-content:space-between; margin-bottom:4px;",
                        ),
                        _ui.input_slider("dev_hour", None, min=0, max=23, value=17, step=1, width="100%"),
                        style="margin-bottom:16px;",
                    ),
                    _ui.div(
                        _ui.div(
                            _ui.span("Huidig stressniveau:", class_="mt-body mt-secondary"),
                            _ui.output_text_verbatim("dev_stress_val", placeholder=True),
                            style="display:flex; justify-content:space-between; margin-bottom:4px;",
                        ),
                        _ui.input_slider("dev_stress", None, min=0, max=100, value=55, step=1, width="100%"),
                        style="margin-bottom:20px;",
                    ),
                    _ui.output_ui("dev_result"),
                    style="max-width:560px;",
                ),
                class_="mt-section-card",
            ),
            style="padding:0 80px 32px;",
        ),

        # Uitlegblok
        _ui.div(
            _ui.div(
                _ui.div("Wat is Circadiane Basislijnsafwijking?", class_="mt-h3", style="margin-bottom:12px;"),
                _ui.p(
                    "In plaats van jouw sessie-stress te vergelijken met een vast getal, "
                    "vergelijken we die met JOUW typische stress op datzelfde uur op niet-sessiedagen. "
                    "Dit corrigeert voor het natuurlijke circadiane ritme.",
                    class_="mt-body mt-secondary",
                    style="margin-bottom:16px;",
                ),
                _ui.div(
                    "afwijking = pre_stress_gemiddelde - verwachte_stress_op_dat_uur",
                    class_="mt-code-block",
                    style="margin-bottom:12px;",
                ),
                _ui.div(
                    "Een positieve afwijking betekent dat je meer gestresseerd was dan normaal voor dat uur.",
                    class_="mt-caption mt-secondary",
                ),
                class_="mt-section-card",
            ),
            style="padding:0 80px 32px;",
        ),

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
            has       = app_data.has_circadian.get(p, False)
            is_active = (p == selected())
            cls = "pill-btn"
            if is_active:
                cls += " active"
            if not has:
                cls += " disabled"
            btn = _ui.input_action_button(f"pill_{p}", p.capitalize(), class_=cls)
            if not has:
                btn = _ui.tags.span(btn, title="Geen circadiane data voor deze deelnemer")
            pills.append(btn)
        return _ui.div(*pills, class_="pill-group", style="justify-content:center;")

    for _p in PARTICIPANTS:
        def _make_obs(participant=_p):
            @reactive.Effect
            @reactive.event(input[f"pill_{participant}"])
            def _():
                if app_data.has_circadian.get(participant, False):
                    selected.set(participant)
        _make_obs()

    @reactive.Calc
    def current_data():
        p  = selected()
        hb = app_data.hourly_baselines.get(p)
        fm = app_data.feature_matrix
        if fm is not None and not fm.empty and "participant" in fm.columns:
            sf = fm[fm["participant"] == p]
        else:
            sf = app_data.session_features.get(p)
        return hb, sf

    @output
    @render.text
    def chart_title():
        return f"Uurlijkse stressbasislijn - {selected().capitalize()}"

    @output
    @render_widget
    def circadian_chart():
        hb, sf = current_data()
        if hb is None or (hasattr(hb, "empty") and hb.empty):
            return empty_figure(f"Geen data beschikbaar voor {selected()}")
        return _build_circadian_chart(hb, sf)

    @output
    @render.ui
    def stat_row():
        hb, sf   = current_data()
        calmest, peak, dev = _compute_stats(hb, sf)
        return _ui.TagList(
            _stat_card(calmest, "Rustste uur"),
            _stat_card(peak,    "Piekstressvenster"),
            _stat_card(dev,     "Pre-sessie afwijking t.o.v. basislijn (gem.)"),
        )

    @output
    @render.text
    def dev_hour_val():
        return f"{input.dev_hour():02d}:00"

    @output
    @render.text
    def dev_stress_val():
        return str(input.dev_stress())

    @output
    @render.ui
    def dev_result():
        p    = selected()
        hour = input.dev_hour()
        stress = input.dev_stress()
        exp, std = expected_stress(app_data, p, hour)

        if exp is None:
            return _ui.div(
                f"Geen basislijn beschikbaar voor {p.capitalize()} op {hour:02d}:00.",
                class_="mt-caption mt-secondary",
            )

        dev   = stress - exp
        sign  = "+" if dev >= 0 else ""
        color = "#ef4444" if dev > 5 else ("#22c55e" if dev < -5 else "rgba(255,255,255,0.4)")
        rel   = "boven" if dev >= 0 else "onder"

        return _ui.div(
            _ui.div(
                _ui.div("Verwachte stress op dit uur:", class_="mt-caption mt-secondary"),
                _ui.div(f"{exp:.1f} stresspunten (sigma: +-{std:.1f})", class_="mt-body"),
                style="margin-bottom:8px;",
            ),
            _ui.div(
                _ui.div("Jouw afwijking:", class_="mt-caption mt-secondary"),
                _ui.div(f"{sign}{dev:.1f} punten {rel} basislijn",
                        style=f"font-size:20px; font-weight:600; color:{color};"),
            ),
            _ui.div(
                f"afwijking = {stress} (huidig) - {exp:.1f} (verwacht op {hour:02d}:00) = {sign}{dev:.1f}",
                class_="mt-code-block",
                style="margin-top:12px;",
            ),
            class_="mt-callout",
        )

