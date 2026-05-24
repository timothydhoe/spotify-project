"""Pagina 7 -- Model: ML-verklaarbaarheid, posteriors, significantietests."""
import base64
from pathlib import Path

import pandas as pd
from shiny import module, reactive, render, ui as _ui

from utils.chart_helpers import ACCENT, PLAYLIST_COLORS, STRESS_RED, TEXT_SECONDARY
from utils.data_loader import AppData

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
REPO_URL = "https://github.com/timothydhoe/spotify-project"

_MODEL_MAP = {
    "DummyMean":        ("Dummy basislijn",       False),
    "Ridge":            ("Ridge regressie",       False),
    "RandomForest":     ("Random Forest",         False),
    "GradientBoosting": ("Gradient Boosting",     True),
}

_PARTICIPANTS_ALL = ["bosbes", "kiwi", "kokosnoot", "limoen", "peer", "watermeloen"]


def _img_b64(path: Path) -> str:
    if not path.exists():
        return ""
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def _model_table(results_csv: Path) -> _ui.Tag:
    headers = ["Model", "MAE", "RMSE", "R2 (LOO-KV)", "Overfittingverschil"]
    df = pd.DataFrame()
    if results_csv.exists():
        try:
            df = pd.read_csv(results_csv)
        except Exception:
            pass

    rows = []
    for csv_name, (display_name, highlight) in _MODEL_MAP.items():
        if not df.empty and "model" in df.columns:
            match = df[df["model"] == csv_name]
            if not match.empty:
                row  = match.iloc[0]
                mae  = f"{row['MAE']:.3f}"       if "MAE"         in row.index else "—"
                rmse = f"{row['RMSE']:.3f}"      if "RMSE"        in row.index else "—"
                r2   = f"{row['R2_LOO']:.3f}"    if "R2_LOO"      in row.index else "—"
                gap  = f"{row['overfit_gap']:.3f}" if "overfit_gap" in row.index else "—"
            else:
                mae = rmse = r2 = gap = "—"
        else:
            mae = rmse = r2 = gap = "—"

        style = f"border-left:3px solid {ACCENT};" if highlight else ""
        rows.append(_ui.tags.tr(
            _ui.tags.td(
                display_name,
                style="font-weight:600;" + (f"color:{ACCENT};" if highlight else ""),
            ),
            _ui.tags.td(mae),
            _ui.tags.td(rmse),
            _ui.tags.td(r2),
            _ui.tags.td(gap),
            style=style,
        ))

    if df.empty:
        rows = [_ui.tags.tr(_ui.tags.td(
            "Voer circadian_ml.py uit om modelresultaten te laden.",
            colspan="5",
            style=f"color:{TEXT_SECONDARY}; text-align:center; padding:24px;",
        ))]

    return _ui.tags.table(
        _ui.tags.thead(_ui.tags.tr(*[_ui.tags.th(h) for h in headers])),
        _ui.tags.tbody(*rows),
        class_="mt-table",
    )


def _significance_table(sig_df: pd.DataFrame, filter_p: str, only_sig: bool) -> _ui.Tag:
    if sig_df.empty:
        return _ui.p("Significantiedata niet beschikbaar.", class_="mt-body mt-secondary")

    df = sig_df.copy()
    if "test_name" in df.columns and "test" not in df.columns:
        df["test"] = df.get("test_category", "").astype(str) + " - " + df["test_name"].astype(str)
    if "significant_05" in df.columns and "significant" not in df.columns:
        df["significant"] = df["significant_05"]
    if "p_value" not in df.columns and "p-value" in df.columns:
        df["p_value"] = df["p-value"]

    # Filters toepassen
    if filter_p and filter_p != "Allemaal" and "participant" in df.columns:
        df = df[df["participant"] == filter_p]
    if only_sig and "significant" in df.columns:
        df = df[df["significant"].astype(str).str.lower().isin(["true", "yes", "1"])]

    display_cols = ["participant", "test", "metric", "direction", "statistic", "p_value", "q_value", "significant"]
    cols  = [c for c in display_cols if c in df.columns]
    labels = {
        "participant": "Deelnemer", "test": "Test", "metric": "Metriek",
        "direction": "Richting", "statistic": "Statistiek",
        "p_value": "p-waarde", "q_value": "q (FDR)", "significant": "Sig.",
    }

    preview = df.head(30)
    rows = []
    for _, row in preview.iterrows():
        cells = []
        for col in cols:
            val = row.get(col, "—")
            if col == "significant":
                is_sig = str(val).lower() in ("true", "yes", "1")
                cells.append(_ui.tags.td(
                    _ui.span("v", style=f"color:{ACCENT}; font-weight:700;")
                    if is_sig else
                    _ui.span("—", style=f"color:{TEXT_SECONDARY};")
                ))
            elif col == "p_value":
                try:
                    pval  = float(val)
                    color = ACCENT if pval < 0.05 else TEXT_SECONDARY
                    cells.append(_ui.tags.td(f"{pval:.4f}", style=f"color:{color};"))
                except (ValueError, TypeError):
                    cells.append(_ui.tags.td(str(val)))
            else:
                cells.append(_ui.tags.td(str(val)[:42]))
        rows.append(_ui.tags.tr(*cells))

    total = len(df)
    note  = _ui.p(
        f"{min(30, total)} van {total} rijen getoond.",
        class_="mt-caption mt-secondary",
        style="margin-top:8px;",
    ) if total > 30 else _ui.div()

    return _ui.TagList(
        _ui.tags.table(
            _ui.tags.thead(_ui.tags.tr(*[_ui.tags.th(labels.get(c, c)) for c in cols])),
            _ui.tags.tbody(*rows),
            class_="mt-table",
        ),
        note,
    )


def _posterior_grid_static() -> _ui.Tag:
    imgs = []
    for p in _PARTICIPANTS_ALL:
        img_path = DATA / "analysis" / p / "bayesian_recommender" / "plots" / f"posterior_{p}.png"
        src = _img_b64(img_path)
        if src:
            imgs.append(_ui.div(
                _ui.div(p.capitalize(), class_="mt-caption mt-secondary",
                        style="margin-bottom:6px; font-weight:500;"),
                _ui.img(src=src, style="width:100%; border-radius:8px;"),
            ))
        else:
            imgs.append(_ui.div(
                _ui.div(p.capitalize(), class_="mt-caption mt-secondary",
                        style="margin-bottom:6px; font-weight:500;"),
                _ui.div(
                    f"Posterior-grafiek ontbreekt voor {p.capitalize()}.",
                    style=f"color:{TEXT_SECONDARY}; font-size:12px; padding:24px; "
                          "text-align:center; background:var(--bg-surface); border-radius:8px;",
                ),
            ))
    if not imgs:
        return _ui.p("Posterior-grafieken niet beschikbaar.", class_="mt-caption mt-secondary")
    return _ui.div(*imgs, style="display:grid; grid-template-columns:repeat(2,1fr); gap:16px;")


def _arch_box(label: str) -> _ui.Tag:
    return _ui.div(
        label,
        style=(
            "background:var(--bg-elevated); border-radius:8px; padding:8px 14px; "
            "font-size:12px; color:#fff; white-space:nowrap; flex-shrink:0;"
        ),
    )


def _arch_arrow() -> _ui.Tag:
    return _ui.div("->", style=f"color:{ACCENT}; font-weight:700; flex-shrink:0;")


# ---------------------------------------------------------------------------
# Module UI
# ---------------------------------------------------------------------------

@module.ui
def ui():
    participants_keuze = ["Allemaal"] + _PARTICIPANTS_ALL
    return _ui.div(
        # Koptekst
        _ui.div(
            _ui.div("Binnenin het Model", class_="mt-h1"),
            _ui.p(
                "Volledige transparantie over elk model, kenmerk en posterior "
                "die gebruikt worden om de aanbevelingen te genereren.",
                class_="mt-body mt-secondary",
                style="margin-top:8px; max-width:640px;",
            ),
            style="text-align:center; padding:48px 80px 32px;",
        ),

        # Modelvergelij kingstabel
        _ui.div(
            _ui.div(
                _ui.div("Voorspellende modellen - Stemmingsdelta", class_="mt-h2",
                        style="margin-bottom:16px;"),
                _ui.output_ui("model_table_ui"),
                _ui.p("LOO-KV = Leave-One-Out kruisvalidatie. Per deelnemer geevalueerd.",
                      class_="mt-caption mt-secondary", style="margin-top:12px;"),
                class_="mt-section-card",
            ),
            style="padding:0 80px 24px;",
        ),

        # Kenmerken (SHAP)
        _ui.div(
            _ui.div(
                _ui.div("Wat voorspelt de stemming?", class_="mt-h2", style="margin-bottom:8px;"),
                _ui.div("SHAP-waarden - Random Forest op mood_delta",
                        class_="mt-caption mt-secondary", style="margin-bottom:4px;"),
                _ui.div(
                    "baseline_deviation_entry is het sterkste kenmerk: "
                    "hoe gestresseerd ben jij t.o.v. jouw normaal op dit uur van de dag?",
                    class_="mt-callout",
                    style="margin-bottom:12px;",
                ),
                _ui.div(
                    "Exploratief — N=40 sessies. SHAP-patronen zijn richtinggevend, geen inferentie. "
                    "Per deelnemer: N=6-16 (zeer lage stabiliteit).",
                    class_="mt-caption",
                    style="color:#f59e0b; margin-bottom:16px;",
                ),
                _ui.output_ui("shap_section"),
                class_="mt-section-card",
            ),
            style="padding:0 80px 24px;",
        ),

        # Bayesiaanse posteriors
        _ui.div(
            _ui.div(
                _ui.div("Bayesiaanse aanbeveler - Posterior-verdelingen", class_="mt-h2",
                        style="margin-bottom:8px;"),
                _ui.div("2.000 MCMC-samples via JAX/NumPyro - 89% geloofwaardigheidsintervallen",
                        class_="mt-caption mt-secondary", style="margin-bottom:16px;"),
                _posterior_grid_static(),
                class_="mt-section-card",
            ),
            style="padding:0 80px 24px;",
        ),

        # Significantietests (collapsible)
        _ui.div(
            _ui.div(
                _ui.div(
                    _ui.div("Sessie-effecten - Statistische significantie", class_="mt-h2",
                            style="margin-bottom:4px;"),
                    _ui.input_action_button("toggle_sig", "▼ Toon tabel",
                                            class_="mt-expand-trigger",
                                            style="margin-left:12px; font-size:12px;"),
                    style="display:flex; align-items:center; gap:0;",
                ),
                _ui.div("Wilcoxon signed-rank, tweezijdig - N>=5 vereist - Per deelnemer",
                        class_="mt-caption mt-secondary", style="margin-bottom:16px;"),
                # Filter controls — always present, table toggled below
                _ui.div(
                    _ui.input_select(
                        "sig_participant", "Deelnemer",
                        choices=participants_keuze, selected="Allemaal",
                        width="180px",
                    ),
                    _ui.input_checkbox("sig_only_sig", "Alleen significant", value=True),
                    style="display:flex; gap:16px; align-items:center; margin-bottom:16px; flex-wrap:wrap;",
                ),
                _ui.output_ui("sig_section"),
                class_="mt-section-card",
            ),
            style="padding:0 80px 24px;",
        ),

        # Architectuurdiagram (collapsible)
        _ui.div(
            _ui.div(
                _ui.div(
                    _ui.div("Hoe alles samenhangt", class_="mt-h2", style="margin-bottom:4px;"),
                    _ui.input_action_button("toggle_arch", "▼ Toon diagram",
                                            class_="mt-expand-trigger",
                                            style="margin-left:12px; font-size:12px;"),
                    style="display:flex; align-items:center; gap:0;",
                ),
                _ui.output_ui("arch_section"),
                class_="mt-section-card",
            ),
            style="padding:0 80px 24px;",
        ),

        # Open-data-voettekst
        _ui.div(
            _ui.div(
                _ui.div(
                    "Alle modelcode, ruwe data en MCMC-traces zijn beschikbaar in de open-source repository.",
                    class_="mt-caption mt-secondary",
                ),
                _ui.a("Bekijk op GitHub ->", href=REPO_URL, target="_blank",
                      class_="mt-caption mt-green", style="margin-top:4px; display:inline-block;"),
                style="text-align:center;",
            ),
            style="background:var(--bg-elevated); padding:32px 80px; margin-top:8px;",
        ),
    )


# ---------------------------------------------------------------------------
# Module server
# ---------------------------------------------------------------------------

@module.server
def server(input, output, session, app_data: AppData):
    show_sig  = reactive.Value(False)
    show_arch = reactive.Value(False)

    @reactive.Effect
    @reactive.event(input.toggle_sig)
    def _toggle_sig():
        new_val = not show_sig()
        show_sig.set(new_val)
        label = "▲ Verberg tabel" if new_val else "▼ Toon tabel"
        _ui.update_action_button("toggle_sig", label=label, session=session)

    @reactive.Effect
    @reactive.event(input.toggle_arch)
    def _toggle_arch():
        new_val = not show_arch()
        show_arch.set(new_val)
        label = "▲ Verberg diagram" if new_val else "▼ Toon diagram"
        _ui.update_action_button("toggle_arch", label=label, session=session)

    @output
    @render.ui
    def model_table_ui():
        path = DATA / "analysis" / "circadian_baselines" / "model_results_mood_delta.csv"
        return _model_table(path)

    @output
    @render.ui
    def shap_section():
        path = DATA / "analysis" / "circadian_baselines" / "plots" / "shap_mood_delta.png"
        src  = _img_b64(path)
        if src:
            return _ui.div(
                _ui.img(src=src, style="max-width:100%; border-radius:8px;"),
                _ui.div(
                    "Elke stip is een sessie. Positieve SHAP-waarden verhogen de voorspelde stemmingsdelta. "
                    "Rode stippen = hoge kenmerkswaarde, blauwe stippen = lage waarde.",
                    class_="mt-caption mt-secondary",
                    style="margin-top:8px;",
                ),
            )
        return _ui.p(
            "SHAP-grafiek niet beschikbaar - voer circadian_ml.py uit.",
            class_="mt-caption mt-secondary",
        )

    @output
    @render.ui
    def sig_section():
        if not show_sig():
            return _ui.div()
        try:
            filter_p = input.sig_participant()
        except Exception:
            filter_p = "Allemaal"
        try:
            only_sig = input.sig_only_sig()
        except Exception:
            only_sig = True
        return _significance_table(
            app_data.significance_tests,
            filter_p=filter_p,
            only_sig=only_sig,
        )

    @output
    @render.ui
    def arch_section():
        if not show_arch():
            return _ui.div()
        return _ui.div(
            _ui.div(
                # Row 1: Data ingest
                _ui.div(
                    _ui.div("Participant Data", style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:16px;"),
                    _ui.div(
                        _arch_box("Exportify CSV"),
                        _arch_arrow(),
                        _arch_box("prepare.py"),
                        _arch_arrow(),
                        _arch_box("Spotify audio-kenmerken"),
                        style="display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:8px;",
                    ),
                    _ui.div(
                        _arch_box("Garmin GDPR export"),
                        _arch_arrow(),
                        _arch_box("garmin_pipeline.py"),
                        _arch_arrow(),
                        _arch_box("Minuut-stress + HR CSV"),
                        style="display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:8px;",
                    ),
                    _ui.div(
                        _arch_box("Google Forms check-in"),
                        _arch_arrow(),
                        _arch_box("checkins CSV"),
                        _arch_arrow(),
                        _arch_box("mood_before / mood_after"),
                        style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;",
                    ),
                ),
                # Divider
                _ui.div(style="border-top:1px solid var(--border-color); margin:16px 0;"),
                # Row 2: Analysis
                _ui.div(
                    _ui.div(
                        _arch_box("circadian_baseline.py"),
                        _arch_arrow(),
                        _arch_box("feature_matrix.csv"),
                        _arch_arrow(),
                        _arch_box("circadian_ml.py"),
                        _arch_arrow(),
                        _arch_box("SHAP + LOO-KV"),
                        style="display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:8px;",
                    ),
                    _ui.div(
                        _arch_box("feature_matrix.csv"),
                        _arch_arrow(),
                        _arch_box("bayesian_recommender.py"),
                        _arch_arrow(),
                        _arch_box("NumPyro NUTS"),
                        _arch_arrow(),
                        _arch_box("trace.nc + posteriors"),
                        style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;",
                    ),
                ),
                # Divider
                _ui.div(style="border-top:1px solid var(--border-color); margin:16px 0;"),
                # Row 3: App output
                _ui.div(
                    _arch_box("ISO playlists (calm/neutral/energy)"),
                    _arch_arrow(),
                    _arch_box("Bayesiaanse aanbeveling"),
                    _arch_arrow(),
                    _arch_box("MoodTune app"),
                    style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;",
                ),
            ),
            style="padding:8px 0;",
        )
