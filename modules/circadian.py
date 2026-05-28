"""Pagina 3 -- Circadiaans ritme: uurlijkse stressbasislijn per deelnemer."""
import numpy as np
import plotly.graph_objects as go
from shiny import module, reactive, render, ui as _ui
from shinywidgets import output_widget, render_widget

from utils.chart_helpers import ACCENT, GRID_COLOR, PLAYLIST_COLORS, TEXT_SECONDARY, dark_layout, empty_figure
from utils.data_loader import PARTICIPANTS, AppData, expected_stress



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
        import pandas as pd
        _NL = {"Calm": "Kalm", "Neutral": "Neutraal", "Energy": "Energiek"}
        for playlist, color in PLAYLIST_COLORS.items():
            mask = session_df["playlist"].str.strip().str.capitalize() == playlist
            sub  = session_df[mask]
            if sub.empty:
                continue
            rng = np.random.default_rng(seed=42)
            jitter = rng.uniform(-0.25, 0.25, len(sub))

            date_col   = sub["date"].astype(str).str[:10] if "date" in sub.columns else pd.Series(["—"] * len(sub), index=sub.index)
            delta_col  = pd.to_numeric(sub.get("mood_delta", pd.Series(dtype=float)), errors="coerce") if "mood_delta" in sub.columns else pd.Series([float("nan")] * len(sub), index=sub.index)
            delta_strs = [f"+{d:.1f} pt" if d >= 0 else f"{d:.1f} pt" if not pd.isna(d) else "—" for d in delta_col]

            # Mood label (e.g. "Moe of ongemotiveerd") — from enriched session_df
            if "mood_before" in sub.columns:
                mood_labels = sub["mood_before"].fillna("—").astype(str).tolist()
            else:
                mood_labels = ["—"] * len(sub)

            # Post-stress (after session)
            if "post_stress_mean" in sub.columns:
                post_stress_vals = pd.to_numeric(sub["post_stress_mean"], errors="coerce")
                post_stress_strs = [f"{v:.1f}" if not pd.isna(v) else "—" for v in post_stress_vals]
            else:
                post_stress_strs = ["—"] * len(sub)

            customdata = list(zip(
                sub["hour_of_day"].values,
                date_col.values,
                delta_strs,
                mood_labels,
                post_stress_strs,
            ))

            nl = _NL.get(playlist, playlist)
            fig.add_trace(go.Scatter(
                x=sub["hour_of_day"].values + jitter,
                y=sub["pre_stress_mean"],
                mode="markers",
                marker=dict(color=color, size=9, line=dict(color="white", width=1.5)),
                name=f"{nl}-sessie",
                hovertemplate=(
                    f"<b>{nl}-sessie</b><br>"
                    "Datum: %{customdata[1]}<br>"
                    "Uur: %{customdata[0]}:00<br>"
                    "Stemming: %{customdata[3]}<br>"
                    "Pre-stress: %{y:.1f}<br>"
                    "Post-stress: %{customdata[4]}<br>"
                    "Stemmingsdelta: %{customdata[2]}<extra></extra>"
                ),
                customdata=customdata,
            ))

    fig.update_layout(**dark_layout(
        xaxis=dict(
            title="Uur van de dag",
            tickvals=list(range(0, 24, 3)),
            ticktext=[f"{h}:00" for h in range(0, 24, 3)],
            range=[-0.5, 23.5],
            gridcolor=GRID_COLOR,
        ),
        yaxis=dict(title="Stress (0-100)", gridcolor=GRID_COLOR),
        height=360,
        legend=dict(orientation="h", y=-0.22),
    ))
    return fig


def _stat_card(value: str, label: str, sub: str = "") -> _ui.Tag:
    return _ui.div(
        _ui.div(value, class_="mt-stat-value"),
        _ui.div(label, class_="mt-stat-label"),
        _ui.div(sub, class_="mt-caption", style="color:var(--text-tertiary); margin-top:4px;") if sub else _ui.div(),
        class_="mt-stat-card",
        style="flex:1;",
    )


def _compute_stats(hb_df, session_df):
    if hb_df is None or hb_df.empty:
        return "—", "—", "—"
    # Restrict to waking hours (6-23) to exclude sleep/watch-removed readings
    waking = hb_df[hb_df["hour"].between(6, 23)]
    if waking.empty:
        waking = hb_df
    calmest_row  = waking.loc[waking["mean_stress"].idxmin()]
    calmest      = f"{int(calmest_row['hour'])}:00"
    stressed_row = waking.loc[waking["mean_stress"].idxmax()]
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
        # Koptekst + definitie (definitie direct na heading, vóór de grafiek)
        _ui.div(
            _ui.div("Jouw Circadiaans Ritme", class_="mt-h1"),
            _ui.p(
                "Hoe verhoudt jouw stressniveau zich tot jouw eigen basislijn op elk uur van de dag?",
                class_="mt-body mt-secondary",
                style="margin-top:8px; margin-bottom:16px;",
            ),
            _ui.div(
                _ui.div("Wat is dit?", class_="mt-caption", style="font-weight:600; margin-bottom:6px;"),
                _ui.p(
                    "We vergelijken jouw sessie-stress met JOUW typische stress op datzelfde uur "
                    "op niet-sessiedagen. Dit corrigeert voor je natuurlijke dagritme. "
                    "Formule: ",
                    class_="mt-caption mt-secondary",
                    style="margin-bottom:4px;",
                ),
                _ui.span(
                    "afwijking = pre_stress − verwacht_stress_op_dat_uur",
                    class_="mt-code-block",
                    style="font-size:0.8rem;",
                ),
                style=(
                    "background:rgba(255,255,255,0.04); border-left:3px solid var(--accent); "
                    "padding:12px 16px; border-radius:6px; max-width:600px; margin:0 auto;"
                ),
            ),
            style="text-align:center; padding:48px 80px 32px;",
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
                    "Grijs band = ±1σ variatie op niet-sessiedagen. Gekleurde stippen = sessies.",
                    class_="mt-caption mt-secondary",
                    style="margin-bottom:4px;",
                ),
                _ui.div(
                    "Klik op een sessie-punt voor sessiedetails ↓",
                    class_="mt-caption",
                    style="color:var(--accent); margin-bottom:16px; font-style:italic;",
                ),
                output_widget("circadian_chart"),
                _ui.output_ui("dot_detail_panel"),
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

        # Afwijkingscalculator (conditioneel: alleen als basislijn beschikbaar)
        _ui.output_ui("deviation_calculator_ui"),

    )


# ---------------------------------------------------------------------------
# Module server
# ---------------------------------------------------------------------------

@module.server
def server(input, output, session, app_data: AppData, selected_participant=None):
    selected = selected_participant if selected_participant is not None else reactive.Value("bosbes")
    selected_dot: reactive.Value[dict | None] = reactive.Value(None)

    @reactive.Calc
    def current_data():
        import pandas as pd
        p  = selected()
        hb = app_data.hourly_baselines.get(p)
        fm = app_data.feature_matrix
        if fm is not None and not fm.empty and "participant" in fm.columns:
            sf = fm[fm["participant"] == p].copy()
        else:
            sf_raw = app_data.session_features.get(p)
            sf = sf_raw.copy() if sf_raw is not None and not sf_raw.empty else pd.DataFrame()
        # Enrich with mood labels and post_stress from session_biometrics
        sb = app_data.session_biometrics.get(p, pd.DataFrame())
        if not sf.empty and not sb.empty and "date" in sf.columns and "date" in sb.columns:
            extra_cols = [c for c in ("mood_before", "mood_after", "post_stress_mean") if c in sb.columns]
            if extra_cols:
                sf = sf.merge(
                    sb[["date"] + extra_cols].drop_duplicates("date"),
                    on="date", how="left", suffixes=("", "_sb"),
                )
        return hb, sf

    @reactive.Effect
    def _clear_dot_on_participant_change():
        selected()
        selected_dot.set(None)

    @reactive.Effect
    @reactive.event(input.circadian_clear_dot)
    def _on_clear_dot():
        selected_dot.set(None)

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
        fw = go.FigureWidget(_build_circadian_chart(hb, sf))

        def _on_click(trace, points, selector):
            if not points.point_inds:
                return
            idx = points.point_inds[0]
            cd  = trace.customdata[idx]
            dot = {
                "date":        str(cd[1]),
                "hour":        int(float(cd[0])),
                "delta":       str(cd[2]),
                "mood_before": str(cd[3]) if len(cd) > 3 else "—",
                "post_stress": str(cd[4]) if len(cd) > 4 else "—",
                "playlist":    trace.name,
                "pre_stress":  float(trace.y[idx]),
            }
            if selected_dot() == dot:
                selected_dot.set(None)
            else:
                selected_dot.set(dot)

        for trace in fw.data:
            if hasattr(trace, "on_click"):
                trace.on_click(_on_click)

        return fw

    @output
    @render.ui
    def stat_row():
        hb, sf   = current_data()
        calmest, peak, dev = _compute_stats(hb, sf)
        return _ui.TagList(
            _stat_card(calmest, "Gouden uur (laagste stress)"),
            _stat_card(peak,    "Piekstressvenster"),
            _stat_card(dev,     "Pre-sessie afwijking (gem.)",
                       sub="stresspunten t.o.v. circadiane basislijn"),
        )

    @output
    @render.ui
    def dot_detail_panel():
        import pandas as pd
        dot = selected_dot()
        if dot is None:
            return _ui.div()

        p  = selected()
        sb = app_data.session_biometrics.get(p)
        date_str = dot["date"][:10]

        if sb is not None and not sb.empty and "date" in sb.columns:
            mask = sb["date"].astype(str).str[:10] == date_str
            rows = sb[mask]
        else:
            rows = None

        def _safe(row, col):
            v = row.get(col) if hasattr(row, "get") else getattr(row, col, None)
            if v is None:
                return "—"
            try:
                f = float(v)
                return "—" if pd.isna(f) else f"{f:.1f}"
            except (TypeError, ValueError):
                return str(v)

        playlist_nl = dot["playlist"].replace("-sessie", "")
        delta_str   = dot["delta"]
        delta_val   = None
        try:
            raw = delta_str.replace(" pt", "").replace("+", "")
            delta_val = float(raw)
        except ValueError:
            pass

        delta_color = (
            "#22c55e" if delta_val is not None and delta_val > 0
            else "#ef4444" if delta_val is not None and delta_val < 0
            else "rgba(255,255,255,0.4)"
        )

        if rows is not None and not rows.empty:
            row = rows.iloc[0]
            mood_voor       = _safe(row, "mood_before_score")
            mood_na         = _safe(row, "mood_after_score")
            mood_label_voor = str(row.get("mood_before", "—")) if hasattr(row, "get") else "—"
            mood_label_na   = str(row.get("mood_after",  "—")) if hasattr(row, "get") else "—"
            pre_stress      = _safe(row, "pre_stress_mean")
            post_stress     = _safe(row, "post_stress_mean")
        else:
            mood_voor       = "—"
            mood_na         = "—"
            mood_label_voor = dot.get("mood_before", "—")
            mood_label_na   = "—"
            pre_stress      = f"{dot['pre_stress']:.1f}"
            post_stress     = dot.get("post_stress", "—")

        def _detail_col(label, value, sub=""):
            return _ui.div(
                _ui.div(label, class_="mt-caption mt-secondary"),
                _ui.div(value, class_="mt-body"),
                _ui.div(sub,   class_="mt-caption mt-tertiary") if sub else _ui.div(),
                style="flex:1; min-width:90px;",
            )

        return _ui.div(
            _ui.div(
                _ui.div(
                    _ui.div(f"Sessie {date_str}", class_="mt-h3"),
                    _ui.input_action_button(
                        "circadian_clear_dot", "×",
                        style=(
                            "background:none; border:none; "
                            "color:rgba(255,255,255,0.5); font-size:20px; "
                            "cursor:pointer; line-height:1; padding:0;"
                        ),
                    ),
                    style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;",
                ),
                _ui.div(
                    _detail_col("Afspeellijst", playlist_nl),
                    _detail_col("Pre-stress", pre_stress, "Garmin stress voor sessie"),
                    _detail_col("Post-stress", post_stress, "Garmin stress na sessie"),
                    _detail_col("Stemming voor", f"{mood_label_voor} ({mood_voor})", "label (score/10)"),
                    _detail_col("Stemming na",   f"{mood_label_na} ({mood_na})",   "label (score/10)"),
                    _detail_col("Stemmingsdelta", delta_str if delta_str else "—"),
                    style="display:flex; gap:12px; flex-wrap:wrap;",
                ),
                class_="mt-callout",
                style="margin-top:16px;",
            ),
        )

    @output
    @render.ui
    def deviation_calculator_ui():
        p = selected()
        if not app_data.has_circadian.get(p, False):
            return _ui.div()
        return _ui.div(
            _ui.div(
                _ui.div("Bereken jouw circadiane afwijking", class_="mt-h3", style="margin-bottom:12px;"),
                _ui.p(
                    "Stel een hypothetisch stressniveau en uur in. "
                    "De app berekent dan hoeveel dit afwijkt van jouw normale stressniveau op dat uur.",
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
                            _ui.span("Hypothetisch stressniveau:", class_="mt-body mt-secondary"),
                            _ui.output_text_verbatim("dev_stress_val", placeholder=True),
                            style="display:flex; justify-content:space-between; margin-bottom:4px;",
                        ),
                        _ui.input_slider("dev_stress", None, min=0, max=100, value=55, step=1, width="100%"),
                        _ui.div(
                            "(Stel een waarde in om je circadiane afwijking te berekenen)",
                            class_="mt-caption",
                            style="color:var(--text-tertiary); margin-top:4px;",
                        ),
                        style="margin-bottom:20px;",
                    ),
                    _ui.output_ui("dev_result"),
                    style="max-width:560px;",
                ),
                class_="mt-section-card",
            ),
            style="padding:0 80px 32px;",
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

        if dev > 5:
            meaning = f"Dit betekent: je bent {dev:.1f} stresspunten méér gestresseerd dan gebruikelijk op {hour:02d}:00."
        elif dev < -5:
            meaning = f"Dit betekent: je bent {abs(dev):.1f} stresspunten mínder gestresseerd dan gebruikelijk op {hour:02d}:00."
        else:
            meaning = f"Dit betekent: je zit binnen ±5 pt van jouw normaal op {hour:02d}:00 — geen opvallende afwijking."

        return _ui.div(
            _ui.div(
                _ui.div("Verwachte stress op dit uur:", class_="mt-caption mt-secondary"),
                _ui.div(f"{exp:.1f} stresspunten (sigma: ±{std:.1f})", class_="mt-body"),
                style="margin-bottom:8px;",
            ),
            _ui.div(
                _ui.div("Jouw afwijking:", class_="mt-caption mt-secondary"),
                _ui.div(f"{sign}{dev:.1f} stresspunten",
                        style=f"font-size:20px; font-weight:600; color:{color};"),
                style="margin-bottom:8px;",
            ),
            _ui.div(meaning, class_="mt-body mt-secondary", style="margin-bottom:12px;"),
            _ui.div(
                f"afwijking = {stress} (huidig) − {exp:.1f} (verwacht op {hour:02d}:00) = {sign}{dev:.1f}",
                class_="mt-code-block",
            ),
            class_="mt-callout",
        )

