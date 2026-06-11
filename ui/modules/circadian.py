"""Pagina 3 -- Circadiaans ritme: uurlijkse stressbasislijn per deelnemer."""
import math
import numpy as np
import plotly.graph_objects as go
from shiny import module, reactive, render, ui as _ui
from shinywidgets import output_widget, render_widget

from utils.chart_helpers import ACCENT, GRID_COLOR, PLAYLIST_COLORS, TEXT_SECONDARY, chart_layout, empty_figure
from utils.data_loader import PARTICIPANTS, AppData, expected_stress


def _arc_path(h_start: float, h_end: float, r_outer: float, r_inner: float,
              cx: float = 180, cy: float = 180) -> str:
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


def _stress_color(normalized: float, alpha: float = 0.75) -> str:
    """Map 0.0 (calm) → 1.0 (peak stress) to a green→orange→red colour."""
    n = max(0.0, min(1.0, normalized))
    if n < 0.5:
        t = n * 2
        r = int(22  + (230 - 22)  * t)
        g = int(163 + (159 - 163) * t)
        b = int(74  + (0   - 74)  * t)
    else:
        t = (n - 0.5) * 2
        r = int(230 + (220 - 230) * t)
        g = int(159 + (38  - 159) * t)
        b = int(0   + (38  - 0)   * t)
    return f"rgba({r},{g},{b},{alpha})"


def _circadian_clock_svg(
    # TODO: extract onclick handlers — blocked by Python variable interpolation in SVG onclick attributes
    golden_hour: int, peak_hour: int,
    golden_stress: float | None = None,
    peak_stress: float | None = None,
    hb_df=None,
    sessions: list | None = None,
    active_arc: str | None = None,
) -> str:
    """
    SVG 24-hour clock with:
    - Full stress-gradient ring (heat map per hour, hover shows stress at that hour)
    - Golden-hour (green) and peak-stress (orange) highlight arcs
    - Per-session dots on the outer ring (clickable, coloured by playlist)
    - Clock face labels: 12 (midnight/top), 3 (6h/right), 6 (noon/bottom), 9 (18h/left)

    sessions: list of (hour, playlist, mood_delta, date, pre_stress, mood_before) tuples
    active_arc: 'golden' | 'peak' | None — highlights the clicked arc
    """
    cx = cy = 180
    size = 360
    r_outer, r_inner = 148, 118       # main arc band
    r_dot = 158                        # session dot radius
    r_tick_out, r_tick_in = 153, 143   # tick marks
    r_label = 170                      # clock face number radius

    parts: list[str] = []

    # ── Background track ring ────────────────────────────────────────────────
    parts.append(
        f'<circle cx="{cx}" cy="{cy}" r="{(r_outer+r_inner)//2}" fill="none" '
        f'stroke="rgba(255,255,255,0.06)" stroke-width="{r_outer-r_inner}"/>'
    )

    # ── Stress gradient ring (one arc per hour) ──────────────────────────────
    stress_vals: dict[int, float] = {}
    if hb_df is not None and not hb_df.empty and "mean_stress" in hb_df.columns:
        for _, row in hb_df.iterrows():
            stress_vals[int(row["hour"])] = float(row["mean_stress"])
        if stress_vals:
            mn = min(stress_vals.values())
            mx = max(stress_vals.values())
            rng = mx - mn if mx > mn else 1.0
            for h in range(24):
                if h not in stress_vals:
                    continue
                norm = (stress_vals[h] - mn) / rng
                col  = _stress_color(norm, alpha=0.55)
                p    = _arc_path(h, h + 1, r_outer, r_inner, cx, cy)
                parts.append(f'<path d="{p}" fill="{col}"/>')

    # ── Golden hour arc (1 h, bright green) ─────────────────────────────────
    green_path   = _arc_path(golden_hour, golden_hour + 1, r_outer, r_inner, cx, cy)
    green_glow   = "filter:drop-shadow(0 0 6px #16a34a);" if active_arc == "golden" else ""
    green_stroke = f'stroke="#86efac" stroke-width="2"' if active_arc == "golden" else ""
    parts.append(
        f'<path d="{green_path}" fill="#16a34a" opacity="0.95" '
        f'style="cursor:pointer;{green_glow}" {green_stroke} '
        f'onclick="Shiny.setInputValue(\'circadian-clock_click\',\'golden\',{{priority:\'event\'}})"/>'
    )

    # ── Peak stress arc (2 h, orange) ────────────────────────────────────────
    orange_path   = _arc_path(peak_hour, peak_hour + 2, r_outer, r_inner, cx, cy)
    orange_glow   = "filter:drop-shadow(0 0 6px #E69F00);" if active_arc == "peak" else ""
    orange_stroke = f'stroke="#fbbf24" stroke-width="2"' if active_arc == "peak" else ""
    parts.append(
        f'<path d="{orange_path}" fill="#E69F00" opacity="0.90" '
        f'style="cursor:pointer;{orange_glow}" {orange_stroke} '
        f'onclick="Shiny.setInputValue(\'circadian-clock_click\',\'peak\',{{priority:\'event\'}})"/>'
    )

    # ── Invisible hover overlays for each hour → update centre text ──────────
    if stress_vals:
        for h in range(24):
            if h not in stress_vals:
                continue
            sv   = stress_vals[h]
            p_hit = _arc_path(h, h + 1, r_outer, r_inner, cx, cy)
            t_str = f"{h:02d}:00"
            parts.append(
                f'<path d="{p_hit}" fill="transparent" style="cursor:default;" '
                f'onmouseover="'
                f'document.getElementById(\'mt-circ-t\').textContent=\'{t_str}\';'
                f'document.getElementById(\'mt-circ-s\').textContent=\'{sv:.0f} pt\';'
                f'document.getElementById(\'mt-circ-t\').style.fontSize=\'13px\';'
                f'" '
                f'onmouseout="'
                f'document.getElementById(\'mt-circ-t\').textContent=\'24-uurs\';'
                f'document.getElementById(\'mt-circ-s\').textContent=\'stressritme\';'
                f'document.getElementById(\'mt-circ-t\').style.fontSize=\'11px\';'
                f'"/>'
            )

    # ── Session dots (playlist colour, filled=positive delta, hollow=negative) ─
    _PL_COLS = {"Calm": "#56B4E9", "Neutral": "#009E73", "Energy": "#E69F00"}
    _PL_NL   = {"Calm": "Kalm", "Neutral": "Neutraal", "Energy": "Energiek"}
    if sessions:
        for sess in sessions:
            # Accepts (hour, playlist, mood_delta) or extended tuples/dicts
            hour, playlist, mood_delta = sess[0], sess[1], sess[2]
            date      = sess[3] if len(sess) > 3 else ""
            pre_stress = sess[4] if len(sess) > 4 else 0.0
            mood_before = sess[5] if len(sess) > 5 else ""

            angle   = (float(hour) / 24) * 2 * math.pi - math.pi / 2
            dx      = cx + r_dot * math.cos(angle)
            dy      = cy + r_dot * math.sin(angle)
            col     = _PL_COLS.get(str(playlist).capitalize(), "#86efac")
            pl_nl   = _PL_NL.get(str(playlist).capitalize(), playlist)
            positive = mood_delta is not None and float(mood_delta) > 0
            fill    = col if positive else "none"
            tip     = f"{int(float(hour)):02d}:00 · {pl_nl} · delta {mood_delta:+.1f}pt" if mood_delta is not None else f"{int(float(hour)):02d}:00 · {pl_nl}"

            # Encode click payload as JS object literal (safe for SVG attributes)
            md_js  = f"{mood_delta}" if mood_delta is not None else "null"
            ps_js  = f"{float(pre_stress):.1f}"
            mb_js  = str(mood_before).replace("'", "").replace('"', "")
            dt_js  = str(date)[:10]
            pl_js  = str(playlist).replace("'", "")
            onclick = (
                f"Shiny.setInputValue('circadian-clock_dot_click',"
                f"{{date:'{dt_js}',hour:{int(float(hour))},playlist:'{pl_js}',"
                f"mood_delta:{md_js},pre_stress:{ps_js},mood_before:'{mb_js}'}},"
                f"{{priority:'event'}})"
            )
            parts.append(
                f'<circle cx="{dx:.1f}" cy="{dy:.1f}" r="6" '
                f'fill="{fill}" stroke="{col}" stroke-width="2.5" opacity="0.9" '
                f'style="cursor:pointer;transition:r 0.1s;" '
                f'onmouseover="this.setAttribute(\'r\',\'9\');this.style.opacity=\'1\';" '
                f'onmouseout="this.setAttribute(\'r\',\'6\');this.style.opacity=\'0.9\';" '
                f'onclick="{onclick}">'
                f'<title>{tip}</title>'
                f'</circle>'
            )

    # ── Major tick marks every 6 h ───────────────────────────────────────────
    for h in range(0, 24, 6):
        angle = (h / 24) * 2 * math.pi - math.pi / 2
        xo = cx + r_tick_out * math.cos(angle)
        yo = cy + r_tick_out * math.sin(angle)
        xi = cx + r_tick_in  * math.cos(angle)
        yi = cy + r_tick_in  * math.sin(angle)
        parts.append(
            f'<line x1="{xi:.1f}" y1="{yi:.1f}" x2="{xo:.1f}" y2="{yo:.1f}" '
            f'stroke="rgba(255,255,255,0.30)" stroke-width="2.5" stroke-linecap="round"/>'
        )

    # ── Minor tick marks every 3 h (smaller) ────────────────────────────────
    for h in range(3, 24, 6):
        angle = (h / 24) * 2 * math.pi - math.pi / 2
        xo = cx + (r_tick_out - 2) * math.cos(angle)
        yo = cy + (r_tick_out - 2) * math.sin(angle)
        xi = cx + (r_tick_in  + 2) * math.cos(angle)
        yi = cy + (r_tick_in  + 2) * math.sin(angle)
        parts.append(
            f'<line x1="{xi:.1f}" y1="{yi:.1f}" x2="{xo:.1f}" y2="{yo:.1f}" '
            f'stroke="rgba(255,255,255,0.15)" stroke-width="1.5" stroke-linecap="round"/>'
        )

    # ── Clock face numbers: 12/3/6/9 (= 0h/6h/12h/18h) ──────────────────────
    face_labels = {
        0:  ("12", "midnight"),
        6:  ("3",  "06:00"),
        12: ("6",  "middag"),
        18: ("9",  "18:00"),
    }
    for h, (big_lbl, sub_lbl) in face_labels.items():
        angle = (h / 24) * 2 * math.pi - math.pi / 2
        lx = cx + r_label * math.cos(angle)
        ly = cy + r_label * math.sin(angle)
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" dominant-baseline="middle" '
            f'font-size="17" font-weight="600" font-family="Sora,sans-serif" '
            f'fill="rgba(255,255,255,0.70)">{big_lbl}</text>'
        )
        # Small sub-label slightly offset toward edge
        slx = cx + (r_label + 14) * math.cos(angle)
        sly = cy + (r_label + 14) * math.sin(angle)
        parts.append(
            f'<text x="{slx:.1f}" y="{sly:.1f}" text-anchor="middle" dominant-baseline="middle" '
            f'font-size="9" font-family="DM Sans,sans-serif" '
            f'fill="rgba(255,255,255,0.28)">{sub_lbl}</text>'
        )

    # ── Centre: participant-facing summary (IDs let hover JS update the text) ──
    parts.append(
        f'<text id="mt-circ-t" x="{cx}" y="{cy - 14}" text-anchor="middle" '
        f'dominant-baseline="middle" font-size="11" font-family="DM Sans,sans-serif" '
        f'fill="rgba(255,255,255,0.28)" style="pointer-events:none;transition:font-size 0.1s;">24-uurs</text>'
        f'<text id="mt-circ-s" x="{cx}" y="{cy + 4}" text-anchor="middle" '
        f'dominant-baseline="middle" font-size="11" font-family="DM Sans,sans-serif" '
        f'fill="rgba(255,255,255,0.20)" style="pointer-events:none;">stressritme</text>'
    )

    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" '
        f'xmlns="http://www.w3.org/2000/svg" style="display:block; overflow:visible;">'
        + "".join(parts)
        + "</svg>"
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
                    "background:var(--bg-elevated); "
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

        # 24-uur klok
        _ui.div(
            _ui.output_ui("clock_hero_ui"),
            style="padding:24px var(--page-margin) 8px;",
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
        sf = pd.DataFrame()
        if fm is not None and not fm.empty and "participant" in fm.columns:
            sf = fm[fm["participant"] == p].copy()
        if sf.empty:
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
        cc = input.clock_click()
        # Toggle: clicking the same arc again clears the highlight
        clock_click.set(None if clock_click() == cc else cc)

    @reactive.Effect
    @reactive.event(input.clock_dot_click)
    def _on_clock_dot_click():
        cd = input.clock_dot_click()
        if not cd:
            selected_dot.set(None)
            return
        md = cd.get("mood_delta")
        dot = {
            "date":        str(cd.get("date", ""))[:10],
            "hour":        int(float(cd.get("hour", 0))),
            "delta":       f"{float(md):+.1f} pt" if md is not None else "—",
            "mood_before": str(cd.get("mood_before", "—")),
            "post_stress": "—",
            "playlist":    str(cd.get("playlist", "")),
            "pre_stress":  float(cd.get("pre_stress") or 0),
        }
        selected_dot.set(None if selected_dot() == dot else dot)

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
        import pandas as pd
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

        # Average pre-session circadian deviation
        dev_val = None
        dev_str = "—"
        if not sf.empty and "baseline_deviation_entry" in sf.columns:
            dev = pd.to_numeric(sf["baseline_deviation_entry"], errors="coerce").mean()
            if not pd.isna(dev):
                dev_val = dev
                dev_str = f"+{dev:.1f} pt" if dev >= 0 else f"{dev:.1f} pt"

        # Build session dot list — 6-tuples for full click detail
        sessions = []
        if not sf.empty and "hour_of_day" in sf.columns and "playlist" in sf.columns:
            for _, row in sf.iterrows():
                h  = row.get("hour_of_day")
                pl = row.get("playlist", "")
                md = row.get("mood_delta")
                dt = str(row.get("date", ""))[:10]
                ps = row.get("pre_stress_mean", 0.0)
                mb = str(row.get("mood_before", "—"))
                if h is not None:
                    try:
                        md_f = float(md) if md is not None and str(md) not in ("", "nan") else None
                    except (TypeError, ValueError):
                        md_f = None
                    try:
                        ps_f = float(ps) if ps is not None and str(ps) not in ("", "nan") else 0.0
                    except (TypeError, ValueError):
                        ps_f = 0.0
                    sessions.append((float(h), str(pl).capitalize(), md_f, dt, ps_f, mb))

        svg = _circadian_clock_svg(
            golden_h, peak_h, golden_stress, peak_stress,
            hb_df=hb, sessions=sessions,
            active_arc=clock_click(),
        )

        # Session dot legend
        pl_dots = []
        seen = set()
        for sess in sessions:
            _, pl, md = sess[0], sess[1], sess[2]
            key = (pl, md is not None and md > 0)
            if key not in seen:
                seen.add(key)
                col = {"Calm": "#56B4E9", "Neutral": "#009E73", "Energy": "#E69F00"}.get(pl, "#86efac")
                nl  = {"Calm": "Kalm", "Neutral": "Neutraal", "Energy": "Energiek"}.get(pl, pl)
                fill_style = f"background:{col};" if (md is not None and md > 0) else f"background:none;border:2px solid {col};"
                pl_dots.append(_ui.span(
                    _ui.HTML(f'<span style="display:inline-block;width:9px;height:9px;border-radius:50%;{fill_style}margin-right:4px;vertical-align:middle;"></span>'),
                    nl + (" ↑" if (md is not None and md > 0) else " ↓/—"),
                    style="font-size:0.75rem; color:var(--text-tertiary); margin-right:12px; white-space:nowrap;",
                ))

        legend = _ui.div(
            *pl_dots,
            _ui.span("Gevuld = positieve stemmingsdelta",
                     style="font-size:0.7rem; color:var(--text-tertiary); opacity:0.7;"),
            style="display:flex; flex-wrap:wrap; align-items:center; gap:4px; margin-top:12px;",
        ) if pl_dots else _ui.div()

        # ── Right panel: always-visible info ─────────────────────────────────
        def _info_block(dot_color, label, time_str, stress_val, explanation, border_color):
            return _ui.div(
                _ui.div(
                    _ui.HTML(
                        f'<span style="display:inline-block;width:10px;height:10px;'
                        f'border-radius:50%;background:{dot_color};margin-right:6px;'
                        f'vertical-align:middle;flex-shrink:0;"></span>'
                    ),
                    _ui.span(label, style="font-size:0.6875rem; font-weight:600; text-transform:uppercase; letter-spacing:0.08em; color:var(--text-tertiary);"),
                    style="display:flex; align-items:center; margin-bottom:6px;",
                ),
                _ui.div(time_str, style="font-size:1.625rem; font-weight:700; font-family:'Sora',sans-serif; line-height:1; margin-bottom:4px;"),
                _ui.div(f"{stress_val:.0f} gem. stresspunten", style="font-size:0.8125rem; color:var(--text-secondary); margin-bottom:8px;"),
                _ui.p(explanation, style="font-size:0.8125rem; color:var(--text-tertiary); margin:0; line-height:1.55;"),
                style=(
                    f"padding:16px 18px; border-radius:calc(var(--radius-card) - 4px); "
                    f"background:var(--bg-elevated);"
                ),
            )

        golden_explanation = (
            f"Jouw stressniveau is hier het laagst van de dag. Ideaal voor ontspanning, "
            f"een kalme afspeellijst, of herstel. Gekleurde stippen op de klok tonen "
            f"wanneer je daadwerkelijk sessies had."
        )
        peak_explanation = (
            f"Jouw stress piek typisch hier. Een energieke afspeellijst sluit aan op "
            f"je verhoogde arousal — of een kalme lijst helpt af te schakelen."
        )

        dev_color  = "#22c55e" if (dev_val is not None and dev_val < -2) else \
                     "#ef4444" if (dev_val is not None and dev_val > 2) else "var(--text-primary)"
        dev_explanation = (
            "Gemiddeld verschil tussen jouw stress bij aanvang van een sessie "
            "en jouw eigen basislijn op dat uur. Positief = je zat gespannener dan normaal."
        )

        right_panel = _ui.div(
            _ui.div("Jouw 24-uurs stressritme", class_="mt-h2", style="margin-bottom:4px;"),
            _ui.p(
                "De ring toont jouw stressverloop over 24 uur: groen = laag, oranje/rood = hoog. "
                "Stippen zijn luistersessies. Groen arc = gouden uur, oranje arc = piekstressvenster.",
                style="font-size:0.8125rem; color:var(--text-tertiary); margin-bottom:20px; line-height:1.55;",
            ),
            _info_block("#16a34a", "Gouden uur",
                        f"{golden_h:02d}:00", golden_stress,
                        golden_explanation, "#16a34a"),
            _ui.div(style="height:10px;"),
            _info_block("#E69F00", "Piekstress",
                        f"{peak_h:02d}–{peak_h+2:02d}:00", peak_stress,
                        peak_explanation, "#E69F00"),
            _ui.div(style="height:10px;"),
            _ui.div(
                _ui.div("Pre-sessie afwijking", style="font-size:0.6875rem; font-weight:600; text-transform:uppercase; letter-spacing:0.08em; color:var(--text-tertiary); margin-bottom:6px;"),
                _ui.div(dev_str, style=f"font-size:1.625rem; font-weight:700; font-family:'Sora',sans-serif; color:{dev_color}; line-height:1; margin-bottom:4px;"),
                _ui.p(dev_explanation, style="font-size:0.8125rem; color:var(--text-tertiary); margin:0; line-height:1.55;"),
                style="padding:16px 18px; border-radius:10px; background:var(--bg-elevated); border:1px solid var(--border-subtle);",
            ),
            style="display:flex; flex-direction:column; justify-content:flex-start;",
        )

        return _ui.div(
            _ui.div(
                # Left: clock + legend
                _ui.div(
                    _ui.HTML(svg),
                    legend,
                    style="display:flex; flex-direction:column; align-items:center;",
                ),
                # Right: always-visible info
                right_panel,
                style=(
                    "display:grid; grid-template-columns:380px 1fr; "
                    "gap:40px; align-items:start;"
                ),
            ),
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
