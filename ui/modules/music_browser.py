"""Pagina — Jouw Muziek (RQ5): opvraagbare songclassificatie per deelnemer."""
import base64
import math
from pathlib import Path

import pandas as pd
from shiny import module, reactive, render, ui as _ui

from utils.chart_helpers import ACCENT, TEXT_SECONDARY
from utils.data_loader import AppData

ROOT = Path(__file__).parent.parent.parent
DATA = ROOT / "data"

_PAGE_SIZE   = 25
_CLASS_NL    = {"calm": "Kalm", "energy": "Energiek", "other": "Overig"}
_CLASS_COLOR = {"calm": "var(--calm-color)", "energy": "var(--energy-color)", "other": "var(--text-secondary)"}
_CLASS_BG    = {"calm": "rgba(86,180,233,0.06)",  "energy": "rgba(230,159,0,0.06)",  "other": "rgba(156,163,175,0.04)"}
_CLASS_BORDER = {"calm": "rgba(86,180,233,0.20)", "energy": "rgba(230,159,0,0.20)", "other": "rgba(156,163,175,0.14)"}


def _img_b64(path: Path) -> str:
    if not path.exists():
        return ""
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def _class_pill(cls: str) -> _ui.Tag:
    nl  = _CLASS_NL.get(cls, cls.capitalize())
    col = _CLASS_COLOR.get(cls, TEXT_SECONDARY)
    bg  = _CLASS_BG.get(cls, "transparent")
    brd = _CLASS_BORDER.get(cls, "transparent")
    return _ui.span(
        nl,
        style=(
            f"display:inline-flex; align-items:center; padding:2px 10px; "
            f"border-radius:999px; font-size:0.6875rem; font-weight:600; "
            f"letter-spacing:0.04em; text-transform:uppercase; white-space:nowrap; "
            f"background:{bg}; color:{col}; border:1px solid {brd};"
        ),
    )


def _arousal_dots(score: float, n_dots: int = 5) -> _ui.Tag:
    """Render arousal score as filled/empty dots."""
    score = max(0.0, min(1.0, score)) if isinstance(score, (int, float)) and not math.isnan(score) else 0.0
    filled  = int(score * n_dots)
    partial = (score * n_dots - filled) >= 0.5

    dots = []
    for i in range(n_dots):
        if i < filled:
            style = "width:8px; height:8px; border-radius:50%; background:var(--accent);"
        elif i == filled and partial:
            style = (
                "width:8px; height:8px; border-radius:50%; "
                "background:linear-gradient(90deg, var(--accent) 50%, var(--bg-elevated) 50%);"
            )
        else:
            style = (
                "width:8px; height:8px; border-radius:50%; "
                "background:var(--bg-elevated); border:1px solid var(--border-default);"
            )
        dots.append(_ui.span(style=style))

    return _ui.div(*dots, style="display:inline-flex; gap:3px; align-items:center;")


def _song_table(df: pd.DataFrame, page: int) -> _ui.Tag:
    if df.empty:
        return _ui.div(
            "Geen nummers gevonden voor dit filter.",
            class_="mt-caption mt-secondary",
            style="padding:24px; text-align:center;",
        )

    total_pages = max(1, math.ceil(len(df) / _PAGE_SIZE))
    page = max(1, min(page, total_pages))
    start = (page - 1) * _PAGE_SIZE
    chunk = df.iloc[start:start + _PAGE_SIZE]

    header = _ui.tags.thead(
        _ui.tags.tr(
            _ui.tags.th("#"),
            _ui.tags.th("Nummer"),
            _ui.tags.th("Artiest"),
            _ui.tags.th("Klasse"),
            _ui.tags.th("Arousal"),
            _ui.tags.th("Tempo"),
            _ui.tags.th("Energie"),
        )
    )
    rows = []
    for i, (_, row) in enumerate(chunk.iterrows(), start=start + 1):
        name    = str(row.get("name",    "—"))[:40]
        artist  = str(row.get("artists", "—"))[:32]
        cls     = str(row.get("class",   "other")).lower()
        arousal = row.get("arousal_score", 0.0)
        try:
            arousal_f = float(arousal)
        except (TypeError, ValueError):
            arousal_f = 0.0
        try:
            tempo = f"{float(row.get('tempo', 0)):.0f}"
        except (TypeError, ValueError):
            tempo = "—"
        try:
            energy = f"{float(row.get('energy', 0)) * 100:.0f}%"
        except (TypeError, ValueError):
            energy = "—"

        rows.append(_ui.tags.tr(
            _ui.tags.td(str(i), style=f"color:{TEXT_SECONDARY}; font-size:0.8125rem;"),
            _ui.tags.td(name, style="font-weight:500; max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;"),
            _ui.tags.td(artist, style=f"color:{TEXT_SECONDARY}; max-width:160px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;"),
            _ui.tags.td(_class_pill(cls)),
            _ui.tags.td(_arousal_dots(arousal_f)),
            _ui.tags.td(tempo, style=f"color:{TEXT_SECONDARY}; font-variant-numeric:tabular-nums;"),
            _ui.tags.td(energy, style=f"color:{TEXT_SECONDARY};"),
        ))

    return _ui.div(
        _ui.tags.table(
            header,
            _ui.tags.tbody(*rows),
            class_="mt-music-table",
        ),
        style="overflow-x:auto;",
    )


# ---------------------------------------------------------------------------
# Module UI
# ---------------------------------------------------------------------------

@module.ui
def ui():
    return _ui.div(
        # Header — aligned to home page hero pattern
        _ui.div(
            _ui.div(
                _ui.span("Jouw Muziek", class_="mt-h1"),
                _ui.span("RQ5", class_="rq-badge", style="vertical-align:middle;"),
                style="display:inline-flex; align-items:center; gap:8px; justify-content:center;",
            ),
            _ui.p(
                "Jouw Spotify-bibliotheek geclassificeerd via een deterministisch arousal-score model. "
                "Kalm / Energiek / Overig — score = 35% energie + 30% tempo + 20% loudness "
                "− 10% acousticness + 5% danceability (MinMaxScaler per deelnemer).",
                class_="mt-body mt-secondary",
                style="margin-top:8px; max-width:560px; margin-left:auto; margin-right:auto;",
            ),
            class_="mt-page-hero",
        ),

        # 5.2 Muziekmix-samenvatting (vervangt de collapsible clustering-sectie)
        _ui.div(
            _ui.output_ui("music_mix_summary"),
            style="padding:0 var(--page-margin) 56px;",
        ),

        # Class distribution pills + controls
        _ui.div(
            _ui.output_ui("class_summary"),
            style="padding:0 var(--page-margin) 48px;",
        ),

        # Filter + sort row
        _ui.div(
            _ui.div(
                _ui.input_select(
                    "class_filter", "Klasse",
                    choices={"all": "Alle nummers", "calm": "Kalm", "energy": "Energiek", "other": "Overig"},
                    selected="all",
                    width="160px",
                ),
                _ui.input_select(
                    "sort_order", "Sorteren",
                    choices={
                        "arousal_desc": "Arousal (hoog → laag)",
                        "arousal_asc":  "Arousal (laag → hoog)",
                        "name_asc":     "Naam A → Z",
                    },
                    selected="arousal_desc",
                    width="200px",
                ),
                style="display:flex; gap:16px; align-items:flex-end; flex-wrap:wrap; margin-bottom:16px;",
            ),
            _ui.div(
                _ui.input_action_button("song_prev", "← Vorige", class_="mt-pagination-btn"),
                _ui.output_ui("page_info"),
                _ui.input_action_button("song_next", "Volgende →", class_="mt-pagination-btn"),
                class_="mt-pagination",
                style="margin-bottom:12px;",
            ),
            style="padding:0 var(--page-margin);",
        ),

        # Song table
        _ui.div(
            _ui.div(
                _ui.output_ui("song_table_ui"),
                class_="mt-section-card",
                style="padding:0;",
            ),
            style="padding:0 var(--page-margin) 32px;",
        ),
    )


# ---------------------------------------------------------------------------
# Module server
# ---------------------------------------------------------------------------

@module.server
def server(input, output, session, app_data: AppData, selected_participant=None):
    sel      = selected_participant if selected_participant is not None else reactive.Value("bosbes")
    page_num = reactive.Value(1)

    @reactive.Effect
    @reactive.event(input.song_prev)
    def _prev():
        p = max(1, page_num() - 1)
        page_num.set(p)

    @reactive.Effect
    @reactive.event(input.song_next)
    def _next():
        df = _filtered_df()
        total = max(1, math.ceil(len(df) / _PAGE_SIZE))
        page_num.set(min(total, page_num() + 1))

    # Reset page on filter/sort/participant change
    @reactive.Effect
    def _reset_page():
        _ = input.class_filter()
        _ = input.sort_order()
        _ = sel()
        page_num.set(1)

    @reactive.Calc
    def _base_df() -> pd.DataFrame:
        p  = sel()
        df = app_data.classified_songs.get(p, pd.DataFrame())
        return df.copy() if not df.empty else pd.DataFrame()

    @reactive.Calc
    def _filtered_df() -> pd.DataFrame:
        df = _base_df()
        if df.empty:
            return df

        filt = input.class_filter()
        if filt != "all" and "class" in df.columns:
            df = df[df["class"].str.lower() == filt]

        sort = input.sort_order()
        if "arousal_score" in df.columns:
            df["_arousal_num"] = pd.to_numeric(df["arousal_score"], errors="coerce")
            if sort == "arousal_desc":
                df = df.sort_values("_arousal_num", ascending=False)
            elif sort == "arousal_asc":
                df = df.sort_values("_arousal_num", ascending=True)
        if sort == "name_asc" and "name" in df.columns:
            df = df.sort_values("name")

        return df.reset_index(drop=True)

    @output
    @render.ui
    def class_summary():
        df = _base_df()
        p  = sel()
        if df.empty:
            return _ui.div(
                f"Muziekclassificatie niet beschikbaar voor {p.capitalize()}.",
                class_="mt-caption mt-secondary mt-no-data",
                style="min-height:60px;",
            )
        if "class" not in df.columns:
            return _ui.div()

        counts = df["class"].str.lower().value_counts().to_dict()
        pills = []
        for cls in ["calm", "energy", "other"]:
            n   = counts.get(cls, 0)
            col = _CLASS_COLOR.get(cls, TEXT_SECONDARY)
            bg  = _CLASS_BG.get(cls, "transparent")
            brd = _CLASS_BORDER.get(cls, "transparent")
            pills.append(_ui.span(
                f"{_CLASS_NL.get(cls, cls)}: {n}",
                style=(
                    f"display:inline-flex; padding:6px 16px; border-radius:999px; "
                    f"font-weight:600; font-size:0.875rem; "
                    f"background:{bg}; color:{col}; border:1px solid {brd}; "
                    f"transition: transform 0.15s ease;"
                ),
            ))
        return _ui.div(
            *pills,
            _ui.span(f"· {len(df)} nummers totaal",
                     style=f"font-size:0.875rem; color:{TEXT_SECONDARY}; margin-left:8px;"),
            style="display:flex; flex-wrap:wrap; gap:8px; align-items:center;",
        )

    @output
    @render.ui
    def page_info():
        df = _filtered_df()
        total = max(1, math.ceil(len(df) / _PAGE_SIZE))
        p = page_num()
        return _ui.div(
            f"pagina {p} van {total}",
            class_="mt-pagination-info",
        )

    @output
    @render.ui
    def song_table_ui():
        df = _filtered_df()
        if df.empty and not _base_df().empty:
            return _ui.div(
                "Geen nummers gevonden voor dit filter.",
                class_="mt-caption mt-secondary",
                style="padding:32px; text-align:center;",
            )
        if _base_df().empty:
            return _ui.div(
                f"Muziekclassificatie niet beschikbaar voor {sel().capitalize()}.",
                class_="mt-body mt-secondary",
                style="padding:32px; text-align:center;",
            )
        return _song_table(df, page_num())

    @output
    @render.ui
    def music_mix_summary():
        """5.2 — Replace clustering section with a personal music mix overview."""
        df = _base_df()
        p  = sel()

        if df.empty or "class" not in df.columns:
            return _ui.div()

        counts = df["class"].str.lower().value_counts().to_dict()
        total  = len(df)

        def _class_stat(cls, icon):
            n   = counts.get(cls, 0)
            pct = n / total * 100 if total > 0 else 0
            col = _CLASS_COLOR.get(cls, TEXT_SECONDARY)
            bg  = _CLASS_BG.get(cls, "transparent")
            brd = _CLASS_BORDER.get(cls, "transparent")
            nl  = _CLASS_NL.get(cls, cls.capitalize())
            return _ui.div(
                _ui.div(icon, style="font-size:2rem; margin-bottom:8px;"),
                _ui.div(str(n), class_="mt-stat-value", style=f"color:{col};"),
                _ui.div(nl, style="font-size:var(--font-size-sm); font-weight:600; text-transform:uppercase; letter-spacing:0.04em; margin-top:4px; color:var(--text-secondary);"),
                _ui.div(f"{pct:.0f}% van bibliotheek", class_="mt-caption mt-tertiary", style="margin-top:2px;"),
                style=(
                    f"flex:1; text-align:center; padding:20px 16px; border-radius:calc(var(--radius-card) - 4px); "
                    f"background:{bg}; border:1px solid {brd};"
                ),
            )

        # PCA scatter PNG — shown inline, no dropdown
        pca_src = _img_b64(DATA / "analysis" / "music_classification" / "pca_scatter_k3.png")
        pca_block = _ui.div()
        if pca_src:
            pca_block = _ui.div(
                _ui.div(
                    _ui.img(
                        src=pca_src,
                        style="max-width:100%; border-radius:8px; display:block; margin:0 auto;",
                    ),
                    style="background:#111827; border-radius:10px; padding:16px; margin-top:20px;",
                ),
                _ui.p(
                    "k=3 clustering op alle nummers (PCA-projectie). "
                    "Elke stip is één nummer. Kleur = GMM-cluster. "
                    "De overlap laat zien dat muziek een continu spectrum is — "
                    "de arousal-classifier kiest de meest passende groep.",
                    class_="mt-caption mt-secondary",
                    style="margin-top:10px; text-align:center;",
                ),
            )

        return _ui.div(
            _ui.div("Jouw muziekmix", class_="mt-h2", style="margin-bottom:12px;"),
            _ui.div(
                _class_stat("calm",   "🎵"),
                _class_stat("energy", "⚡"),
                _class_stat("other",  "○"),
                style="display:flex; gap:16px; flex-wrap:wrap; margin-bottom:16px;",
            ),
            _ui.p(
                "Arousal-score per nummer: 35% energie + 30% tempo + 20% loudness − 10% acousticness + 5% danceability "
                "(genormaliseerd op jouw bibliotheekreeks). "
                "Score < 0.35 (én valence ≥ 0.25) → Kalm. Score > 0.65 → Energiek. Tussenin → Overig.",
                class_="mt-body mt-secondary",
                style="margin:0;",
            ),
            pca_block,
            class_="mt-section-card",
            style="padding:24px 32px;",
        )
