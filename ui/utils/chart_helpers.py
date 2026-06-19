"""Shared Plotly layout factories and color constants — warm-light theme."""
import plotly.graph_objects as go

# Design system tokens — warm-light v4 (matches tokens.css)
BG_BASE     = "#F4EFE6"
BG_CARD     = "#FFFFFF"
BG_ELEVATED = "#EDE8DE"
ACCENT      = "#059669"
TEXT_PRIMARY   = "rgba(26, 20, 18, 0.90)"
TEXT_SECONDARY = "rgba(26, 20, 18, 0.62)"
TEXT_TERTIARY  = "rgba(26, 20, 18, 0.40)"
STRESS_RED  = "#F43F5E"
GRID_COLOR  = "rgba(180, 140, 80, 0.18)"
ZERO_COLOR  = "rgba(28, 21, 18, 0.20)"

# Legacy aliases
BG_PRIMARY   = BG_BASE
ACCENT_GREEN = ACCENT
BORDER       = "rgba(180, 140, 80, 0.22)"

# Okabe-Ito colorblind-safe palette — deepened for light-bg readability
# Calm=#2196C3, Neutral=#009760, Energy=#D4850A
PLAYLIST_COLORS = {
    "Calm":    "#0EA5E9",   # sky-500
    "Neutral": "#10B981",   # emerald-400
    "Energy":  "#F59E0B",   # amber-400
}

# General Okabe-Ito sequence for non-playlist categorical charts
CHART_COLORS = ["#D4850A", "#2196C3", "#009760", "#8B5CF6", "#0072B2", "#D55E00", "#CC79A7"]

# Shared axis defaults — exported so callers can use them for secondary axes (yaxis2 etc.)
AXIS_DEFAULTS = dict(
    gridcolor=GRID_COLOR,
    zerolinecolor=ZERO_COLOR,
    linecolor="rgba(180, 140, 80, 0.20)",
    tickfont=dict(color=TEXT_SECONDARY, size=11),
    title_font=dict(color=TEXT_SECONDARY, family="Figtree, sans-serif", size=12),
)

# Standard layout to apply to all Plotly charts
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(
        family="Figtree, sans-serif",
        color=TEXT_SECONDARY,
        size=13,
    ),
    title_font=dict(
        family="Figtree, sans-serif",
        size=18,
        color=TEXT_PRIMARY,
    ),
    xaxis=dict(**AXIS_DEFAULTS),
    yaxis=dict(**AXIS_DEFAULTS),
    margin=dict(l=48, r=24, t=24, b=40),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT_SECONDARY, size=12),
        borderwidth=0,
    ),
    hoverlabel=dict(
        bgcolor="#1C1A17",
        font_color="rgba(240, 236, 227, 0.95)",
        bordercolor="rgba(255, 215, 160, 0.25)",
        font=dict(family="Figtree, sans-serif", size=13),
    ),
    modebar=dict(
        remove=[
            "zoom2d", "pan2d", "select2d", "lasso2d",
            "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d",
            "toImage",
        ],
        bgcolor="rgba(0,0,0,0)",
        color=TEXT_TERTIARY,
    ),
)


def chart_layout(**overrides) -> dict:
    """Base Plotly layout for all MoodTune charts.

    Dict-typed keys (xaxis, yaxis, legend, margin, …) are shallowly merged,
    so per-chart overrides extend rather than replace the base axis styling.
    """
    result = dict(PLOTLY_LAYOUT)
    for key, val in overrides.items():
        base_val = result.get(key)
        if isinstance(base_val, dict) and isinstance(val, dict):
            result[key] = {**base_val, **val}
        else:
            result[key] = val
    return result


def empty_figure(message: str = "Geen data beschikbaar") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        x=0.5, y=0.5, xref="paper", yref="paper",
        showarrow=False,
        font=dict(color=TEXT_SECONDARY, size=14),
    )
    fig.update_layout(**chart_layout(xaxis=dict(visible=False), yaxis=dict(visible=False)))
    return fig
