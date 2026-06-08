"""Shared Plotly layout factories and color constants."""
import plotly.graph_objects as go

# Design system tokens — dark mode
BG_BASE     = "#090f0a"
BG_CARD     = "rgba(255,255,255,0.06)"
BG_ELEVATED = "rgba(255,255,255,0.08)"
ACCENT      = "#16a34a"
TEXT_PRIMARY   = "rgba(255,255,255,0.88)"
TEXT_SECONDARY = "rgba(255,255,255,0.52)"
TEXT_TERTIARY  = "rgba(255,255,255,0.32)"
STRESS_RED  = "#f87171"
GRID_COLOR  = "rgba(255,255,255,0.07)"
ZERO_COLOR  = "rgba(255,255,255,0.12)"

# Legacy aliases
BG_PRIMARY   = BG_BASE
ACCENT_GREEN = ACCENT
BORDER       = "rgba(255,255,255,0.10)"

# Okabe-Ito colorblind-safe palette — matches notebooks/ml/*.ipynb
# Calm=#56B4E9 (sky blue), Neutral=#009E73 (bluish green), Energy=#E69F00 (orange)
PLAYLIST_COLORS = {
    "Calm":    "#56B4E9",
    "Neutral": "#009E73",
    "Energy":  "#E69F00",
}

# General Okabe-Ito sequence for non-playlist categorical charts
CHART_COLORS = ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7"]

# Standard layout to apply to all Plotly charts
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(
        family="DM Sans, sans-serif",
        color=TEXT_SECONDARY,
        size=13,
    ),
    title_font=dict(
        family="Sora, sans-serif",
        size=18,
        color=TEXT_PRIMARY,
    ),
    xaxis=dict(
        gridcolor=GRID_COLOR,
        zerolinecolor=ZERO_COLOR,
        tickfont=dict(color=TEXT_TERTIARY, size=12),
        title_font=dict(color=TEXT_SECONDARY, family="DM Sans, sans-serif"),
    ),
    yaxis=dict(
        gridcolor=GRID_COLOR,
        zerolinecolor=ZERO_COLOR,
        tickfont=dict(color=TEXT_TERTIARY, size=12),
        title_font=dict(color=TEXT_SECONDARY, family="DM Sans, sans-serif"),
    ),
    margin=dict(l=48, r=24, t=48, b=40),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT_SECONDARY, size=12),
        borderwidth=0,
    ),
    hoverlabel=dict(
        bgcolor="#141f15",
        font_color="rgba(255,255,255,0.90)",
        bordercolor="rgba(255,255,255,0.18)",
        font=dict(family="DM Sans, sans-serif", size=13),
    ),
    modebar=dict(
        remove=[
            "zoom2d", "pan2d", "select2d", "lasso2d",
            "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d",
            "toImage",
        ],
        bgcolor="rgba(0,0,0,0)",
        color=TEXT_SECONDARY,
    ),
)


def chart_layout(**overrides) -> dict:
    """Base Plotly layout for all MoodTune charts."""
    base = dict(PLOTLY_LAYOUT)
    base.update(overrides)
    return base


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
