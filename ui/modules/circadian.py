"""Pagina 3 -- Circadiaans ritme: uurlijkse stressbasislijn per deelnemer."""
import math
import numpy as np
import plotly.graph_objects as go
from shiny import module, reactive, render, ui as _ui
from shinywidgets import output_widget, render_widget

from utils.chart_helpers import ACCENT, GRID_COLOR, PLAYLIST_COLORS, TEXT_SECONDARY, chart_layout, empty_figure
from utils.data_loader import PARTICIPANTS, AppData, expected_stress


def _arc_path(h_start: float, h_end: float, r_outer: float, r_inner: float,
              cx: float = 120, cy: float = 120) -> str:
    """SVG path for a filled arc segment between two hours on a 24-hour clock."""
    def _pt(hour, r):
        angle = (hour / 24) * 2 * math.pi - math.pi / 2
        return cx + r * math.cos(angle), cy + r * math.sin(angle)

    span = h_end - h_start
    large = 1 if span > 12 else 0
    x1o, y1o = _pt(h_start, r_outer)
    x2o, y2o = _pt(h_end,   r_outer)
    x1i, y1i = _pt(h_end,   r_inner)
    x2i, y2i = _pt(h_start, r_inner)
    return (
        f"M {x1o:.2f} {y1o:.2f} "
        f"A {r_outer} {r_outer} 0 {large} 1 {x2o:.2f} {y2o:.2f} "
        f"L {x1i:.2f} {y1i:.2f} "
        f"A {r_inner} {r_inner} 0 {large} 0 {x2i:.2f} {y2i:.2f} Z"
    )


def _circadian_clock_svg(
    golden_hour: int, peak_hour: int,
    golden_stress: float | None = None, peak_stress: float | None = None,
) -> str:
    """Return an interactive SVG 24-hour clock with golden hour (green) and peak window (orange) arcs."""
    cx, cy, size = 120, 120, 240
    r_track, r_outer, r_inner = 102, 98, 80
    r_tick_outer, r_tick_inner = 105, 95

    # Track ring
    track = (
        f'<circle cx="{cx}" cy="{cy}" r="{r_track}" fill="none" '
        f'stroke="rgba(255,255,255,0.06)" stroke-width="{r_outer - r_inner}"/>'
    )

    # Golden hour arc (1 hour, green) — interactive
    green_path = _arc_path(golden_hour, golden_hour + 1, r_outer, r_inner, cx, cy)
    golden_title = (
        f"Gouden uur: {golden_hour:02d}:00 — laagste stress van de dag"
        + (f" ({golden_stress:.1f} pt)" if golden_stress is not None else "")
    )
    green_arc = (
        f'<path d="{green_path}" fill="#16a34a" opacity="0.9" '
        f'style="cursor:pointer;" class="mt-clock-arc" '
        f'onclick="Shiny.setInputValue(\'circadian-clock_click\', \'golden\', {{priority:\'event\'}})">'
        f'<title>{golden_title}</title></path>'
    )

    # Peak window arc (2 hours, orange) — interactive
    orange_path = _arc_path(peak_hour, peak_hour + 2, r_outer, r_inner, cx, cy)
    peak_title = (
        f"Piekstress: {peak_hour:02d}–{peak_hour+2:02d}:00 — hoogste stress van de dag"
        + (f" ({peak_stress:.1f} pt)" if peak_stress is not None else "")
    )
    orange_arc = (
        f'<path d="{orange_path}" fill="#E69F00" opacity="0.9" '
        f'style="cursor:pointer;" class="mt-clock-arc" '
        f'onclick="Shiny.setInputValue(\'circadian-clock_click\', \'peak\', {{priority:\'event\'}})">'
        f'<title>{peak_title}</title></path>'
    )

    # Hour tick marks at 0, 6, 12, 18
    ticks = ""
    labels = ""
    tick_hours = {0: "0h", 6: "6h", 12: "12h", 18: "18h"}
    for h, lbl in tick_hours.items():
        angle = (h / 24) * 2 * math.pi - math.pi / 2
        xo = cx + r_tick_outer * math.cos(angle)
        yo = cy + r_tick_outer * math.sin(angle)
        xi = cx + r_tick_inner * math.cos(angle)
        yi = cy + r_tick_inner * math.sin(angle)
        ticks += (
            f'<line x1="{xi:.1f}" y1="{yi:.1f}" x2="{xo:.1f}" y2="{yo:.1f}" '
            f'stroke="rgba(255,255,255,0.15)" stroke-width="2"/>'
        )
        lx = cx + (r_track + 16) * math.cos(angle)
        ly = cy + (r_track + 16) * math.sin(angle)
        labels += (
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" dominant-baseline="middle" '
            f'font-size="12" font-family="DM Sans,sans-serif" fill="rgba(255,255,255,0.35)">{lbl}</text>'
        )

    # Center label
    center = (
        f'<text x="{cx}" y="{cy - 10}" text-anchor="middle" font-size="13" '
        f'font-family="DM Sans,sans-serif" fill="rgba(255,255,255,0.4)">24h</text>'
        f'<text x="{cx}" y="{cy + 8}" text-anchor="middle" font-size="11" '
        f'font-family="DM Sans,sans-serif" fill="rgba(255,255,255,0.25)">klok</text>'
    )

    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" '
        f'xmlns="http://www.w3.org/2000/svg" style="display:block;">'
        f'{track}{green_arc}{orange_arc}{ticks}{labels}{center}'
        f'</svg>'
    )


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
        hovertemplate="Uur %{x}:00 — Gem. stress: %{y:.1f}<extra></extra>",
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
            rng    = np.random.default_rng(seed=42)
            jitter = rng.uniform(-0.25, 0.25, len(sub))

            date_col   = sub["date"].astype(str).str[:10] if "date" in sub.columns else pd.Series(["—"] * len(sub), index=sub.index)
            delta_col  = pd.to_numeric(sub.get("mood_delta", pd.Series(dtype=float)), errors="coerce") if "mood_delta" in sub.columns else pd.Series([float("nan")] * len(sub), index=sub.index)
            delta_strs = [f"+{d:.1f} pt" if d >= 0 else f"{d:.1f} pt" if not pd.isna(d) else "—" for d in delta_col]

            mood_labels = sub["mood_before"].fillna("—").astype(str).tolist() if "mood_before" in sub.columns else ["—"] * len(sub)

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
                marker=dict(color=color, size=10, line=dict(color="white", width=1.5)),
                name=f"{nl}-sessie",
                hovertemplate=(
                    f"<b>{nl}-sessie</b><br>"
                    "Datum: %{customdata[1]}<br>"
                    "Uur: %{customdata[0]}:00<br>"
                    "Stemming voor: %{customdata[3]}<br>"
                    "Pre-stress: %{y:.1f}<br>"
                    "Post-stress: %{customdata[4]}<br>"
                    "Stemmingsdelta: %{customdata[2]}<br>"
                    "<i>Klik voor meer details</i><extra></extra>"
                ),
                customdata=customdata,
            ))

    fig.update_layout(**chart_layout(
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


def _compute_stats(hb_df, session_df):
    if hb_df is None or hb_df.empty:
        return "—", "—", "—", None, None
    waking = hb_df[hb_df["hour"].between(6, 23)]
    if waking.empty:
        waking = hb_df
    calmest_row  = waking.loc[waking["mean_stress"].idxmin()]
    calmest      = f"{int(calmest_row['hour'])}:00"
    golden_stress = float(calmest_row["mean_stress"])
    stressed_row  = waking.loc[waking["mean_stress"].idxmax()]
    peak_h        = int(stressed_row["hour"])
    peak          = f"{peak_h}-{peak_h + 2}:00"
    peak_stress   = float(stressed_row["mean_stress"])
    dev_str       = "—"
    if session_df is not None and not session_df.empty and "baseline_deviation_entry" in session_df.columns:
        import pandas as pd
        dev = pd.to_numeric(session_df["baseline_deviation_entry"], errors="coerce").mean()
        if not pd.isna(dev):
            dev_str = f"+{dev:.1f} pt" if dev >= 0 else f"{dev:.1f} pt"
    return calmest, peak, dev_str, golden_stress, peak_stress


# ---------------------------------------------------------------------------
# Module UI
# ---------------------------------------------------------------------------

@module.ui
def ui():
    return _ui.div(
        # 1.1 Hero: full viewport height so chart is below the fold
        _ui.div(
            _ui.div("Jouw Circadiaans Ritme", class_="mt-h1"),
            _ui.p(
                "Hoe verhoudt jouw stressniveau zich tot jouw eigen basislijn op elk uur van de dag?",
                class_="mt-body mt-secondary",
                style="margin-top:8px; margin-bottom:24px; max-width:560px; margin-left:auto; margin-right:auto;",
            ),
            _ui.div(
                _ui.div("Wat is dit?", class_="mt-caption", style="font-weight:600; margin-bottom:6px;"),
                _ui.p(
                    "We vergelijken jouw sessie-stress met JOUW typische stress op datzelfde uur "
                    "op niet-sessiedagen. Dit corrigeert voor je natuurlijke dagritme.",
                    class_="mt-caption mt-secondary",
                    style="margin-bottom:4px;",
                ),
                _ui.span(
                    "afwijking = pre_stress − verwacht_stress_op_dat_uur",
                    style=(
                        "font-family:'JetBrains Mono','Roboto Mono',monospace; "
                        "font-size:0.8rem; color:var(--text-tertiary); font-style:italic;"
                    ),
                ),
                style=(
                    "background:var(--bg-elevated); border-left:3px solid var(--accent); "
                    "padding:12px 16px; border-radius:6px; max-width:600px; margin:0 auto;"
                ),
            ),
            # Scroll indicator
            _ui.div(
                "↓ jouw persoonlijk stressritme",
                style=(
                    "margin-top:auto; padding-top:56px; padding-bottom:32px; "
                    "color:var(--text-tertiary); font-size:0.8125rem; letter-spacing:0.07em;"
                ),
            ),
            style=(
                "text-align:center; padding:80px var(--page-margin) 0; "
                "min-height:calc(70vh - 64px); display:flex; flex-direction:column; "
                "justify-content:center; align-items:center;"
            ),
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
                    "Groen band = ±1σ normaalvariatie op niet-sessiedagen. Gekleurde stippen = sessies.",
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
            style="padding:0 var(--page-margin);",
        ),

        # 1.3 24-uur klok als hero — groot, gecentreerd, interactief
        _ui.div(
            _ui.output_ui("clock_hero_ui"),
            style="padding:40px var(--page-margin) 8px;",
        ),

        # Afwijkingscalculator
        _ui.output_ui("deviation_calculator_ui"),
    )


# ---------------------------------------------------------------------------
# Module server
# ---------------------------------------------------------------------------

@module.server
def server(input, output, session, app_data: AppData, selected_participant=None):
    selected     = selected_participant if selected_participant is not None else reactive.Value("bosbes")
    selected_dot: reactive.Value[dict | None] = reactive.Value(None)
    clock_click  = reactive.Value(None)

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
        clock_click.set(None)

    @reactive.Effect
    @reactive.event(input.circadian_clear_dot)
    def _on_clear_dot():
        selected_dot.set(None)

    @reactive.Effect
    @reactive.event(input.clock_click)
    def _on_clock_click():
        clock_click.set(input.clock_click())

    @output
    @render.text
    def chart_title():
        return f"Uurlijkse stressbasislijn — {selected().capitalize()}"

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
    def clock_hero_ui():
        hb, sf = current_data()
        if hb is None or (hasattr(hb, "empty") and hb.empty):
            return _ui.div()
        waking = hb[hb["hour"].between(6, 23)]
        if waking.empty:
            waking = hb

        golden_h      = int(waking.loc[waking["mean_stress"].idxmin(), "hour"])
        peak_h        = int(waking.loc[waking["mean_stress"].idxmax(), "hour"])
        golden_stress = float(waking.loc[waking["mean_stress"].idxmin(), "mean_stress"])
        peak_stress   = float(waking.loc[waking["mean_stress"].idxmax(), "mean_stress"])

        # Avg deviation
        import pandas as pd
        dev_str = "—"
        if not sf.empty and "baseline_deviation_entry" in sf.columns:
            dev = pd.to_numeric(sf["baseline_deviation_entry"], errors="coerce").mean()
            if not pd.isna(dev):
                dev_str = f"+{dev:.1f} pt" if dev >= 0 else f"{dev:.1f} pt"

        svg = _circadian_clock_svg(golden_h, peak_h, golden_stress, peak_stress)

        # Determine which arc is selected
        clicked = clock_click()

        def _kpi_callout(label, time_str, stress_val, color, which):
            is_active = clicked == which
            border_w  = "3px" if is_active else "1px"
            bg        = f"rgba({('22,163,74' if which=='golden' else '230,159,0')},0.12)" if is_active else "var(--bg-card)"
            return _ui.div(
                _ui.div(
                    _ui.HTML(f'<span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:{color};margin-right:6px;vertical-align:middle;"></span>'),
                    label,
                    style=f"font-size:0.75rem; color:var(--text-tertiary); font-weight:600; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:6px;",
                ),
                _ui.div(time_str, style="font-size:1.5rem; font-weight:700; font-family:'Sora',sans-serif; line-height:1;"),
                _ui.div(f"{stress_val:.1f} gemiddeld", style="font-size:0.8125rem; color:var(--text-secondary); margin-top:4px;"),
                style=(
                    f"flex:1; text-align:center; padding:16px 20px; border-radius:12px; "
                    f"background:{bg}; border:{border_w} solid {color}; "
                    "cursor:pointer; transition:all 0.15s ease;"
                ),
                onclick=f"Shiny.setInputValue('circadian-clock_click', '{which}', {{priority:'event'}})",
            )

        clock_section = _ui.div(
            # Clock
            _ui.div(
                _ui.HTML(svg),
                _ui.div(
                    "Klik op een arc voor details",
                    style="font-size:0.75rem; color:var(--text-tertiary); margin-top:8px; text-align:center;",
                ),
                style="flex-shrink:0; display:flex; flex-direction:column; align-items:center;",
            ),
            # KPI callouts
            _ui.div(
                _kpi_callout("Gouden uur", f"{golden_h:02d}:00", golden_stress, "#16a34a", "golden"),
                _kpi_callout("Piekstress", f"{peak_h:02d}–{peak_h+2:02d}:00", peak_stress, "#E69F00", "peak"),
                _ui.div(
                    _ui.div("Pre-sessie afwijking", style="font-size:0.75rem; color:var(--text-tertiary); font-weight:600; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:6px;"),
                    _ui.div(dev_str, style="font-size:1.5rem; font-weight:700; font-family:'Sora',sans-serif;"),
                    _ui.div("gemiddeld t.o.v. basislijn", style="font-size:0.8125rem; color:var(--text-secondary); margin-top:4px;"),
                    style="flex:1; text-align:center; padding:16px 20px; border-radius:12px; background:var(--bg-card); border:1px solid var(--border-subtle);",
                ),
                style="display:flex; flex-direction:column; gap:12px; flex:1; justify-content:center;",
            ),
            style="display:flex; gap:32px; align-items:center; max-width:700px; margin:0 auto;",
        )

        # Arc detail panel on click
        detail_panel = _ui.div()
        if clicked == "golden":
            exp_str = f"{golden_stress:.1f} stresspunten"
            detail_panel = _ui.div(
                _ui.div(
                    _ui.HTML('<span style="color:#16a34a; font-weight:700; margin-right:8px;">●</span>'),
                    _ui.span(f"Gouden uur — {golden_h:02d}:00", style="font-weight:600;"),
                    style="margin-bottom:8px;",
                ),
                _ui.p(
                    f"Op {golden_h:02d}:00 is jouw gemiddelde stress het laagst: {exp_str}. "
                    "Dit is jouw optimale moment voor ontspanning, herstel, of een kalme afspeellijst.",
                    class_="mt-body mt-secondary",
                    style="margin:0;",
                ),
                class_="mt-callout",
                style="max-width:600px; margin:16px auto 0; border-left-color:#16a34a;",
            )
        elif clicked == "peak":
            exp_str = f"{peak_stress:.1f} stresspunten"
            detail_panel = _ui.div(
                _ui.div(
                    _ui.HTML('<span style="color:#E69F00; font-weight:700; margin-right:8px;">●</span>'),
                    _ui.span(f"Piekstressvenster — {peak_h:02d}–{peak_h+2:02d}:00", style="font-weight:600;"),
                    style="margin-bottom:8px;",
                ),
                _ui.p(
                    f"Tussen {peak_h:02d}:00 en {peak_h+2:02d}:00 is jouw stress typisch het hoogst: {exp_str}. "
                    "Een energieke afspeellijst kan hier bewust inspelen op je verhoogde arousal — "
                    "of een kalme lijst kan helpen om af te schakelen.",
                    class_="mt-body mt-secondary",
                    style="margin:0;",
                ),
                class_="mt-callout",
                style="max-width:600px; margin:16px auto 0; border-left-color:#E69F00;",
            )

        return _ui.div(
            _ui.div(
                "Jouw 24-uurs stressritme",
                class_="mt-h2",
                style="text-align:center; margin-bottom:8px;",
            ),
            _ui.p(
                "Klik op het groene of oranje arc voor uitleg.",
                class_="mt-caption mt-secondary",
                style="text-align:center; margin-bottom:24px;",
            ),
            clock_section,
            detail_panel,
            class_="mt-section-card",
            style="padding:32px 40px;",
        )

    @output
    @render.ui
    def dot_detail_panel():
        import pandas as pd
        dot = selected_dot()
        if dot is None:
            return _ui.div()

        p        = selected()
        hb, sf   = current_data()
        sb       = app_data.session_biometrics.get(p)
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
            else "var(--text-tertiary)"
        )

        if rows is not None and not rows.empty:
            row             = rows.iloc[0]
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

        # 1.2 Compute circadian deviation for this session
        hour           = dot.get("hour", 17)
        pre_stress_val = dot.get("pre_stress")
        deviation_str  = "—"
        dev_color      = "var(--text-tertiary)"
        if pre_stress_val is not None:
            exp_val, _ = expected_stress(app_data, p, hour)
            if exp_val is not None:
                dev        = pre_stress_val - exp_val
                sign       = "+" if dev >= 0 else ""
                deviation_str = f"{sign}{dev:.1f} pt"
                dev_color  = "#ef4444" if dev > 5 else ("#22c55e" if dev < -5 else "var(--text-tertiary)")

        # Comparison to participant's average for this playlist type
        comparison_str = "—"
        pl_key = playlist_nl.strip()
        if not sf.empty and "playlist" in sf.columns and "pre_stress_mean" in sf.columns:
            pl_mask = sf["playlist"].str.strip().str.capitalize() == pl_key.capitalize()
            pl_mean = pd.to_numeric(sf.loc[pl_mask, "pre_stress_mean"], errors="coerce").mean()
            if not pd.isna(pl_mean) and pre_stress_val is not None:
                diff = pre_stress_val - pl_mean
                sign = "+" if diff >= 0 else ""
                comparison_str = f"{sign}{diff:.1f} pt vs. gem. {pl_key}-sessie"

        def _detail_col(label, value, sub="", value_style=""):
            return _ui.div(
                _ui.div(label, class_="mt-caption mt-secondary"),
                _ui.div(value, class_="mt-body",
                        style=value_style if value_style else ""),
                _ui.div(sub, class_="mt-caption mt-tertiary", style="color:var(--text-tertiary); margin-top:2px;") if sub else _ui.div(),
                style="flex:1; min-width:100px;",
            )

        return _ui.div(
            _ui.div(
                _ui.div(
                    _ui.div(f"Sessie {date_str}", class_="mt-h3"),
                    _ui.input_action_button(
                        "circadian_clear_dot", "×",
                        style=(
                            "background:none; border:none; "
                            "color:var(--text-tertiary); font-size:20px; "
                            "cursor:pointer; line-height:1; padding:0;"
                        ),
                    ),
                    style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;",
                ),
                _ui.div(
                    _detail_col("Afspeellijst", playlist_nl),
                    _detail_col("Pre-stress", pre_stress, "Garmin voor sessie"),
                    _detail_col("Post-stress", post_stress, "Garmin na sessie"),
                    _detail_col("Circad. afwijking", deviation_str, f"op {hour:02d}:00 vs. basislijn", value_style=f"color:{dev_color}; font-weight:600;"),
                    _detail_col("vs. gemiddelde", comparison_str),
                    _detail_col("Stemming voor", f"{mood_label_voor} ({mood_voor})", "label (score/10)"),
                    _detail_col("Stemming na",   f"{mood_label_na} ({mood_na})",   "label (score/10)"),
                    _detail_col("Stemmingsdelta", delta_str if delta_str else "—", value_style=f"color:{delta_color}; font-weight:600;"),
                    style="display:flex; gap:12px; flex-wrap:wrap; margin-bottom:12px;",
                ),
                _ui.div(
                    "→ Ga naar Sessie-replay voor de volledige minuut-grafiek",
                    style=(
                        "font-size:0.8125rem; color:var(--accent); cursor:pointer; "
                        "text-decoration:underline; text-underline-offset:3px;"
                    ),
                    onclick="mtNavTo('profiel','Sessie-replay')",
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
                _ui.div(
                    # Left — inputs
                    _ui.div(
                        _ui.div("Is mijn stress normaal voor dit uur?", class_="mt-h3",
                                style="margin-bottom:10px;"),
                        _ui.p(
                            "Vul je huidige stressniveau in en het uur van de dag — "
                            "dan zie je direct hoe dit zich verhoudt tot jouw typische stress op dat moment.",
                            class_="mt-body mt-secondary",
                            style="margin-bottom:20px;",
                        ),
                        _ui.div(
                            _ui.input_select(
                                "dev_hour", "Huidig uur",
                                choices={str(h): f"{h:02d}:00" for h in range(6, 24)},
                                selected="17",
                                width="160px",
                            ),
                            style="margin-bottom:16px;",
                        ),
                        _ui.div(
                            _ui.input_numeric(
                                "dev_stress", "Mijn stressniveau (0–100)",
                                value=55, min=0, max=100, step=1,
                                width="160px",
                            ),
                        ),
                        style="flex:1;",
                    ),
                    # Right — live result
                    _ui.div(
                        _ui.output_ui("dev_result"),
                        style="flex:1; min-width:220px;",
                    ),
                    style="display:flex; gap:48px; align-items:flex-start; flex-wrap:wrap;",
                ),
                class_="mt-section-card",
            ),
            style="padding:0 var(--page-margin) 32px;",
        )

    @output
    @render.ui
    def dev_result():
        p      = selected()
        try:
            hour   = int(input.dev_hour())
        except (TypeError, ValueError):
            hour = 17
        try:
            stress = float(input.dev_stress())
        except (TypeError, ValueError):
            return _ui.div()

        exp, std = expected_stress(app_data, p, hour)
        if exp is None:
            return _ui.div(
                f"Geen basislijn beschikbaar voor {p.capitalize()} op {hour:02d}:00.",
                class_="mt-caption mt-secondary",
            )

        dev   = stress - exp
        sign  = "+" if dev >= 0 else ""
        color = "#ef4444" if dev > 5 else ("#22c55e" if dev < -5 else "var(--text-tertiary)")

        if dev > 5:
            meaning = f"Je bent {dev:.1f} pt méér gespannen dan normaal op {hour:02d}:00. Een kalme afspeellijst kan helpen."
        elif dev < -5:
            meaning = f"Je bent {abs(dev):.1f} pt mínder gespannen dan normaal op {hour:02d}:00 — geen reden voor interventie."
        else:
            meaning = f"Je zit binnen ±5 pt van jouw normaal op {hour:02d}:00 — geen opvallende afwijking."

        return _ui.div(
            _ui.div(
                _ui.div("Verwachte stress op dit uur", class_="mt-caption mt-secondary",
                        style="margin-bottom:4px;"),
                _ui.div(
                    f"{exp:.1f}",
                    style=(
                        "font-family:'Sora',sans-serif; font-weight:700; font-size:2rem; "
                        "color:var(--text-primary); line-height:1;"
                    ),
                ),
                _ui.div(f"±{std:.1f} sigma — jouw normaal op {hour:02d}:00",
                        class_="mt-caption mt-tertiary", style="margin-top:4px;"),
                style="margin-bottom:20px;",
            ),
            _ui.div(
                _ui.div("Jouw afwijking", class_="mt-caption mt-secondary",
                        style="margin-bottom:4px;"),
                _ui.div(
                    f"{sign}{dev:.1f} pt",
                    style=f"font-family:'Sora',sans-serif; font-weight:700; font-size:2rem; color:{color}; line-height:1;",
                ),
                style="margin-bottom:16px;",
            ),
            _ui.div(meaning, class_="mt-body mt-secondary", style="margin-bottom:12px;"),
            _ui.div(
                f"afwijking = {stress:.0f} (huidig) − {exp:.1f} (verwacht op {hour:02d}:00) = {sign}{dev:.1f}",
                style=(
                    "font-family:'JetBrains Mono','Roboto Mono',monospace; "
                    "font-size:0.8rem; color:var(--text-tertiary); font-style:italic; margin-top:4px;"
                ),
            ),
        )
