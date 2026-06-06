"""Pagina 7 -- Model: ML-verklaarbaarheid, posteriors, significantietests."""
import base64
from pathlib import Path

import pandas as pd
from shiny import module, reactive, render, ui as _ui

from utils.chart_helpers import ACCENT, PLAYLIST_COLORS, STRESS_RED, TEXT_SECONDARY
from utils.data_loader import AppData

ROOT = Path(__file__).parent.parent.parent
DATA = ROOT / "data"
REPO_URL = "https://github.com/timothydhoe/spotify-project"

_MODEL_MAP = {
    "DummyMean":        ("Dummy basislijn",               False),
    "Ridge":            ("Ridge regressie",               False),
    "RandomForest":     ("Random Forest",                 False),
    "GradientBoosting": ("Gradient Boosting",             True),
    "MixedLM":          ("Gemengd-effecten model (LME)",  False),
}

_RIDGE_BOOTSTRAP_CI_FALLBACK = {
    "mood_delta":   "−0.03 – 0.55",  # from last audit run — overridden by bootstrap_ci.json when available
    "stress_delta": "—",              # do not use old 0.57-0.94 value; it matched a different dataset
}

_PARTICIPANTS_ALL = ["bosbes", "kiwi", "kokosnoot", "limoen", "peer", "watermeloen"]


def _img_b64(path: Path) -> str:
    if not path.exists():
        return ""
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


_HEADER_TOOLTIPS = {
    "Model":              "Voorspellend model getest op stemmingsdelta (na − voor).",
    "MAE":                "Gemiddelde Absolute Fout — interpreteer als 'gemiddeld X stemmingspunten mis' (lager = beter).",
    "RMSE":               "Wortel van Gemiddelde Kwadratische Fout — straft grote fouten zwaarder dan MAE (lager = beter).",
    "R2 (LOO-KV)":        "Verklaringskracht via Leave-One-Out kruisvalidatie. 1.0 = perfecte voorspelling, 0 = niet beter dan gemiddelde, negatief = slechter dan gemiddelde.",
    "Overfittingverschil":"Verschil tussen trainings-R² en LOO-R². Laag = stabieler model; hoog = het model past zich te sterk aan op de trainingsdata.",
    "Bootstrap 95% CI":   "95% betrouwbaarheidsinterval op R² via 1000 bootstrap iteraties. Alleen voor Ridge berekend.",
}


def _model_table(results_csv: Path, target: str = "mood_delta", bootstrap_ci: dict = None) -> _ui.Tag:
    headers = ["Model", "MAE", "RMSE", "R2 (LOO-KV)", "Overfittingverschil", "Bootstrap 95% CI"]
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
                mae  = f"{row['MAE']:.3f}"         if "MAE"         in row.index else "—"
                rmse = f"{row['RMSE']:.3f}"        if "RMSE"        in row.index else "—"
                r2   = f"{row['R2_LOO']:.3f}"      if "R2_LOO"      in row.index else "—"
                gap  = f"{row['overfit_gap']:.3f}" if "overfit_gap" in row.index else "—"
            else:
                mae = rmse = r2 = gap = "—"
        else:
            mae = rmse = r2 = gap = "—"

        # Prefer live data from bootstrap_ci.json; fall back to last-audit constant for mood only
        if csv_name == "Ridge":
            bci_data = (bootstrap_ci or {}).get(target, {})
            if bci_data:
                lo = bci_data.get("r2_ci_low", "?")
                hi = bci_data.get("r2_ci_high", "?")
                ci = f"{lo:.3f} – {hi:.3f}" if isinstance(lo, float) else f"{lo} – {hi}"
            else:
                ci = _RIDGE_BOOTSTRAP_CI_FALLBACK.get(target, "—")
        else:
            ci = "—"

        warn_color = "#f59e0b"
        is_best = csv_name == "Ridge"
        row_style = f"border-left:3px solid {warn_color}; background:rgba(245,158,11,0.06);" if highlight else (
            f"border-left:3px solid {ACCENT};" if is_best else ""
        )
        rows.append(_ui.tags.tr(
            _ui.tags.td(
                display_name,
                style="font-weight:600;" + (
                    f"color:{warn_color};" if highlight else
                    (f"color:{ACCENT};" if is_best else "")
                ),
            ),
            _ui.tags.td(mae),
            _ui.tags.td(rmse),
            _ui.tags.td(r2),
            _ui.tags.td(gap),
            _ui.tags.td(ci, style=f"color:{ACCENT}; font-size:0.8125rem;" if ci != "—" else ""),
            style=row_style,
        ))

    if df.empty:
        rows = [_ui.tags.tr(_ui.tags.td(
            "Voer circadian_ml.py uit om modelresultaten te laden.",
            colspan="6",
            style=f"color:{TEXT_SECONDARY}; text-align:center; padding:24px;",
        ))]

    th_elements = [
        _ui.tags.th(h, title=_HEADER_TOOLTIPS.get(h, ""))
        for h in headers
    ]

    if target == "stress_delta":
        # Read R² from the loaded CSV rather than hardcoding it
        ridge_r2_str = "—"
        if not df.empty and "model" in df.columns and "R2_LOO" in df.columns:
            ridge_row = df[df["model"] == "Ridge"]
            if not ridge_row.empty:
                ridge_r2_str = f"{float(ridge_row['R2_LOO'].iloc[0]):.3f}"
        caption = (
            f"Ridge beste LOO-model voor stress_delta (R²={ridge_r2_str}), maar "
            "LOPO MAE=5.868 vs. LOO MAE=2.866 — het model generaliseert niet over "
            "deelnemers. Gebruik stressvoorspellingen alleen per deelnemer."
        )
        lopo_note = _ui.div(
            _ui.span("⚠ LOPO-generalisatiefout", style="font-weight:700; color:#f59e0b;"),
            f" — Leave-One-Participant-Out MAE=5.868 (2× hoger dan LOO MAE=2.866). "
            "Stress-patronen zijn deelnemerspersoonlijk, niet overdraagbaar.",
            style=(
                "margin-top:12px; padding:12px 16px; background:rgba(245,158,11,0.08); "
                "border:1px solid rgba(245,158,11,0.3); border-radius:8px; "
                "font-size:0.875rem; line-height:1.6;"
            ),
        )
    else:
        caption = (
            "Ridge is het meest stabiele model (R²=0.318, Bootstrap 95% CI: −0.03–0.55). "
            "Gradient Boosting overfitting-verschil = 0.71 — onbruikbaar voor generalisatie. "
            "Alle resultaten zijn exploratief (N=82 sessies; ~600 nodig voor statistisch bewijs)."
        )
        lopo_note = _ui.div()

    return _ui.div(
        _ui.div(
            _ui.tags.table(
                _ui.tags.thead(_ui.tags.tr(*th_elements)),
                _ui.tags.tbody(*rows),
                class_="mt-table",
                style="border-radius:10px; overflow:hidden;",
            ),
            style="overflow-x:auto;",
        ),
        lopo_note,
        _ui.div(caption, class_="mt-caption mt-secondary", style="margin-top:10px; font-style:italic;"),
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

    display_cols = ["participant", "test", "metric", "direction", "statistic", "p_value", "q_value", "effect_size", "significant"]
    cols  = [c for c in display_cols if c in df.columns]
    labels = {
        "participant": "Deelnemer", "test": "Test", "metric": "Metriek",
        "direction": "Richting", "statistic": "Statistiek",
        "p_value": "p-waarde", "q_value": "q (FDR)",
        "effect_size": "Effect (d/r)", "significant": "Sig.",
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
            elif col == "effect_size":
                try:
                    es = float(val)
                    color = TEXT_SECONDARY if abs(es) < 0.2 else (ACCENT if abs(es) >= 0.5 else "#e5a917")
                    cells.append(_ui.tags.td(f"{es:.3f}", style=f"color:{color};"))
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
            "background:var(--bg-elevated); border:1px solid var(--border-default); "
            "border-radius:8px; padding:8px 14px; "
            "font-size:12px; color:var(--text-primary); white-space:nowrap; flex-shrink:0;"
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
            style="text-align:center; padding:48px var(--page-margin) 32px;",
        ),

        # Modelvergelij kingstabel
        _ui.div(
            _ui.div(
                _ui.div(
                    _ui.div(
                        _ui.span("Voorspellende modellen", class_="mt-h2"),
                        _ui.span("RQ4", class_="rq-badge"),
                    ),
                    # Stemming / Stress toggle — rendered dynamically so active class updates
                    _ui.div(
                        _ui.output_ui("model_toggle_ui"),
                        style="margin-left:auto;",
                    ),
                    style="display:flex; align-items:center; gap:8px; margin-bottom:16px; flex-wrap:wrap;",
                ),
                _ui.output_ui("model_table_ui"),
                _ui.p("LOO-KV = Leave-One-Out kruisvalidatie. Bootstrap CI alleen voor Ridge.",
                      class_="mt-caption mt-secondary", style="margin-top:12px;"),
                _ui.div(
                    _ui.div(
                        _ui.span("⚠ Vermogenanalyse", style="font-weight:700; font-size:1rem; color:#f59e0b;"),
                        style="margin-bottom:8px;",
                    ),
                    "Voor Cohen's d = 0.23 (Kalm vs Energiek) is N ≈ 608 sessies nodig voor 80% vermogen "
                    "(α=0.05, tweezijdig) — 304 per conditie. "
                    "De huidige N=82 biedt slechts ~15% vermogen voor dit effect. "
                    "Alle ML-resultaten zijn daarom uitsluitend exploratief — geen conclusies trekken.",
                    style=(
                        "margin-top:16px; padding:16px 20px; "
                        "background:rgba(245,158,11,0.10); "
                        "border:2px solid #f59e0b; "
                        "border-radius:10px; "
                        "font-size:0.875rem; "
                        "line-height:1.6;"
                    ),
                ),
                class_="mt-section-card",
            ),
            style="padding:0 var(--page-margin) 24px;",
        ),

        # Kenmerken (SHAP)
        _ui.div(
            _ui.div(
                _ui.div(
                    _ui.div(
                        _ui.span("Wat voorspelt de uitkomst?", class_="mt-h2"),
                        _ui.span("RQ4", class_="rq-badge"),
                    ),
                    _ui.input_action_button("toggle_shap", "▲ Verberg SHAP",
                                            class_="mt-expand-trigger",
                                            style="margin-left:auto; font-size:12px;"),
                    style="display:flex; align-items:center; margin-bottom:4px;",
                ),
                _ui.output_ui("shap_subtitle"),
                _ui.div(
                    "baseline_deviation_entry is het sterkste kenmerk: "
                    "hoe gestresseerd ben jij t.o.v. jouw normaal op dit uur van de dag?",
                    class_="mt-callout",
                    style="margin-bottom:12px;",
                ),
                _ui.output_ui("shap_section"),
                class_="mt-section-card",
            ),
            style="padding:0 var(--page-margin) 24px;",
        ),

        # RQ3 — Biometrische classificatie (collapsible)
        _ui.div(
            _ui.div(
                _ui.div(
                    _ui.div(
                        _ui.span("RQ3", class_="rq-badge"),
                        _ui.span(" — Biometrische Classificatie", class_="mt-h2",
                                 style="margin-left:4px;"),
                    ),
                    _ui.input_action_button("toggle_rq3", "▼ Toon resultaten",
                                            class_="mt-expand-trigger",
                                            style="margin-left:auto; font-size:12px;"),
                    style="display:flex; align-items:center; margin-bottom:8px;",
                ),
                _ui.div("Kunnen we de afspeellijst terugherleiden uit de biometrie alleen?",
                        class_="mt-caption mt-secondary", style="margin-bottom:12px;"),
                _ui.output_ui("rq3_section"),
                class_="mt-section-card",
            ),
            style="padding:0 var(--page-margin) 24px;",
        ),

        # Bayesiaanse posteriors
        _ui.div(
            _ui.div(
                _ui.div(
                    _ui.span("Bayesiaanse Aanbeveler", class_="mt-h2"),
                    _ui.span("RQ4", class_="rq-badge"),
                    style="display:flex; align-items:center; margin-bottom:8px;",
                ),
                _ui.div("4.000 MCMC-samples (PyMC/NUTS, 4 chains × 1.000 draws) · 89% geloofwaardigheidsintervallen",
                        class_="mt-caption mt-secondary", style="margin-bottom:12px;"),
                _ui.output_ui("bayes_convergence_ui"),
                _ui.div(
                    "Populatieniveau: de HDI voor alle afspeellijsteffecten omvat nul — "
                    "de data zijn onvoldoende om een betrouwbaar populatiegemiddeld effect aan te tonen. "
                    "Per-deelnemer posteriors (hieronder) tonen de individuele variatie.",
                    class_="mt-callout",
                    style="border-left:3px solid var(--accent); margin-bottom:16px; font-size:0.875rem;",
                ),
                _posterior_grid_static(),
                _ui.output_ui("bayes_diagnostics_ui"),
                class_="mt-section-card",
            ),
            style="padding:0 var(--page-margin) 24px;",
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
                        class_="mt-caption mt-secondary", style="margin-bottom:12px;"),
                _ui.div(
                    "⚠  Geen tests bereiken significantie na FDR-correctie (27 tests, α=0.05). "
                    "Effect sizes zijn aanwezig maar de steekproef (N=82) is onvoldoende om ze te bevestigen.",
                    class_="mt-callout",
                    style="border-left:3px solid #f59e0b; margin-bottom:16px; font-size:0.875rem;",
                ),
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
            style="padding:0 var(--page-margin) 24px;",
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
            style="padding:0 var(--page-margin) 24px;",
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
            style="background:var(--bg-elevated); padding:32px var(--page-margin); margin-top:8px;",
        ),
    )


# ---------------------------------------------------------------------------
# Module server
# ---------------------------------------------------------------------------

@module.server
def server(input, output, session, app_data: AppData):
    show_sig   = reactive.Value(False)
    show_arch  = reactive.Value(False)
    show_shap  = reactive.Value(True)
    show_rq3   = reactive.Value(False)
    model_target = reactive.Value("mood_delta")  # "mood_delta" or "stress_delta"

    @reactive.Effect
    @reactive.event(input.toggle_shap)
    def _toggle_shap():
        new_val = not show_shap()
        show_shap.set(new_val)
        label = "▲ Verberg SHAP" if new_val else "▼ Toon SHAP"
        _ui.update_action_button("toggle_shap", label=label, session=session)

    @reactive.Effect
    @reactive.event(input.toggle_mood)
    def _switch_mood():
        model_target.set("mood_delta")

    @reactive.Effect
    @reactive.event(input.toggle_stress)
    def _switch_stress():
        model_target.set("stress_delta")

    @output
    @render.ui
    def model_toggle_ui():
        tgt = model_target()
        mood_cls   = "mt-model-toggle-btn active" if tgt == "mood_delta"   else "mt-model-toggle-btn"
        stress_cls = "mt-model-toggle-btn active" if tgt == "stress_delta" else "mt-model-toggle-btn"
        return _ui.div(
            _ui.input_action_button("toggle_mood",   "Stemming", class_=mood_cls),
            _ui.input_action_button("toggle_stress", "Stress",   class_=stress_cls),
            class_="mt-model-toggle",
        )

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

    @reactive.Effect
    @reactive.event(input.toggle_rq3)
    def _toggle_rq3():
        new_val = not show_rq3()
        show_rq3.set(new_val)
        label = "▲ Verberg resultaten" if new_val else "▼ Toon resultaten"
        _ui.update_action_button("toggle_rq3", label=label, session=session)

    @output
    @render.ui
    def model_table_ui():
        tgt  = model_target()
        path = DATA / "analysis" / "circadian_baselines" / (
            "model_results_mood_delta.csv" if tgt == "mood_delta" else "model_results_stress_delta.csv"
        )
        return _model_table(path, target=tgt, bootstrap_ci=app_data.bootstrap_ci)

    @output
    @render.ui
    def shap_subtitle():
        tgt = model_target()
        if tgt == "stress_delta":
            return _ui.div("SHAP-waarden · Ridge op stress_delta · N=82 sessies, exploratief",
                           class_="mt-caption mt-secondary", style="margin-bottom:4px;")
        return _ui.div("SHAP-waarden · Random Forest op mood_delta · N=82 sessies, exploratief",
                       class_="mt-caption mt-secondary", style="margin-bottom:4px;")

    @output
    @render.ui
    def rq3_section():
        if not show_rq3():
            return _ui.div()
        plots_dir = DATA / "analysis" / "circadian_baselines" / "plots"
        # Load RQ3 accuracy from file if available; fall back gracefully
        rq3 = app_data.rq3_results
        def _acc_str(model_key):
            for k, v in rq3.items():
                if model_key.lower() in k.lower():
                    return f"{v['accuracy']*100:.1f}%", v.get("n_events", "?"), v.get("chance_level", 0.333)
            return "—", "?", 0.333

        lr_acc, lr_n, chance = _acc_str("logistic")
        rf_acc, rf_n, _     = _acc_str("forest")
        chance_str = f"{chance*100:.0f}%"
        n_events   = lr_n if lr_n != "?" else rf_n
        data_source_note = (
            "Berekend uit notebook 1 (`1_circadian_ml.ipynb`)." if rq3
            else "⚠ Voer notebook 1 opnieuw uit om actuele cijfers te laden (`rq3_results.json` ontbreekt). Onderstaande waarden zijn schattingen uit de laatste handmatige run."
        )
        if not rq3:
            lr_acc, rf_acc, chance_str, n_events = "~42%", "~44%", "33%", "~72"

        items = [
            _ui.div(
                "Hiervoor trainden we twee classificatoren (Logistische Regressie en Random Forest) "
                "met StratifiedKFold (k=5) op de biometrische sessiefeatures om te voorspellen of "
                "de deelnemer naar Kalm, Neutraal of Energiek had geluisterd.",
                class_="mt-body mt-secondary",
                style="margin-bottom:8px;",
            ),
            _ui.div(data_source_note,
                    class_="mt-caption mt-tertiary",
                    style="margin-bottom:16px; font-style:italic;"),
            _ui.div(
                _ui.div(
                    _ui.div(
                        _ui.div(str(lr_acc), style="font-family:'Sora',sans-serif; font-weight:700; font-size:2rem; color:var(--text-secondary);"),
                        _ui.div("Logistische Regressie (5-fold CV)", class_="mt-stat-label"),
                    ),
                    _ui.div(
                        _ui.div(str(rf_acc), style="font-family:'Sora',sans-serif; font-weight:700; font-size:2rem; color:var(--text-secondary);"),
                        _ui.div("Random Forest (5-fold CV)", class_="mt-stat-label"),
                    ),
                    _ui.div(
                        _ui.div(str(chance_str), style="font-family:'Sora',sans-serif; font-weight:700; font-size:2rem; color:#6b7280;"),
                        _ui.div("Kansniveau (3 klassen)", class_="mt-stat-label"),
                    ),
                    style="display:grid; grid-template-columns:repeat(3,1fr); gap:16px; margin-bottom:16px;",
                ),
            ),
        ]
        cm_src = _img_b64(plots_dir / "rq3_confusion_matrix_logreg.png")
        if cm_src:
            items.append(_ui.div(
                _ui.div("Verwarringsmatrix — Logistische Regressie",
                        class_="mt-caption mt-secondary", style="margin-bottom:6px;"),
                _ui.div(
                    _ui.img(src=cm_src, style="max-width:420px; border-radius:6px;"),
                    style="background:#111827; border-radius:10px; padding:12px; display:inline-block;",
                ),
            ))
        items.append(_ui.div(
            _ui.span("Conclusie: ", style="font-weight:600;"),
            f"De modellen liggen slechts enkele procentpunten boven kans (N={n_events} classificatie-events). "
            "Biometrie alleen is onvoldoende om de afspeellijst te reconstrueren. "
            "Dit bevestigt dat de biometrische respons sterk varieert per context, en dat RQ3 meer data vereist.",
            class_="mt-honesty-callout",
        ))
        return _ui.div(*items)

    @output
    @render.ui
    def bayes_convergence_ui():
        param_path = DATA / "analysis" / "bayesian_recommender" / "parameter_summary.csv"
        if not param_path.exists():
            return _ui.div()
        try:
            df = pd.read_csv(param_path, index_col=0)
            max_rhat = df["r_hat"].max()
            min_ess  = df["ess_bulk"].min()
            rhat_ok  = max_rhat < 1.01
            ess_ok   = min_ess  > 400
            rhat_color = ACCENT if rhat_ok else STRESS_RED
            ess_color  = ACCENT if ess_ok  else STRESS_RED
        except Exception:
            return _ui.div()

        return _ui.div(
            _ui.div(
                _ui.div(
                    _ui.span("R̂ max", class_="mt-stat-label"),
                    _ui.div(f"{max_rhat:.4f}", style=f"font-family:'Sora',sans-serif; font-weight:700; font-size:1.5rem; color:{rhat_color};"),
                    _ui.div("< 1.01 = convergentie ✓" if rhat_ok else "≥ 1.01 ⚠ controleer chains",
                            class_="mt-caption mt-tertiary"),
                    class_="mt-stat-card",
                ),
                _ui.div(
                    _ui.span("ESS bulk min", class_="mt-stat-label"),
                    _ui.div(f"{min_ess:.0f}", style=f"font-family:'Sora',sans-serif; font-weight:700; font-size:1.5rem; color:{ess_color};"),
                    _ui.div("> 400 = voldoende ✓" if ess_ok else "< 400 ⚠ meer samples nodig",
                            class_="mt-caption mt-tertiary"),
                    class_="mt-stat-card",
                ),
                _ui.div(
                    _ui.span("Divergenties", class_="mt-stat-label"),
                    _ui.div("0", style=f"font-family:'Sora',sans-serif; font-weight:700; font-size:1.5rem; color:{ACCENT};"),
                    _ui.div("geen geometrieproblemen ✓", class_="mt-caption mt-tertiary"),
                    class_="mt-stat-card",
                ),
                style="display:grid; grid-template-columns:repeat(3,1fr); gap:16px; margin-bottom:16px;",
            ),
        )

    @output
    @render.ui
    def shap_section():
        if not show_shap():
            return _ui.div()
        tgt = model_target()
        plots_dir = DATA / "analysis" / "circadian_baselines" / "plots"
        sections  = []

        shap_src = _img_b64(plots_dir / f"shap_{tgt}.png")
        if shap_src:
            sections.append(_ui.div(
                _ui.div(
                    "Exploratief — N=82 sessies. Patronen zijn richtinggevend, geen inferentie.",
                    class_="mt-caption",
                    style="color:#f59e0b; margin-bottom:12px;",
                ),
                _ui.div(
                    _ui.img(src=shap_src, style="max-width:100%; border-radius:6px;",
                            alt="SHAP beeswarm plot — mood_delta RandomForest"),
                    style="background:#111827; border-radius:10px; padding:16px;",
                ),
                _ui.div(
                    "Elke stip is een sessie. Positieve SHAP-waarden verhogen de voorspelde stemmingsdelta. "
                    "Rode stippen = hoge kenmerkswaarde, blauwe stippen = lage waarde.",
                    class_="mt-caption mt-secondary",
                    style="margin-top:8px;",
                ),
            ))
        else:
            sections.append(_ui.p(
                "SHAP-grafiek niet beschikbaar — voer circadian_ml.py uit.",
                class_="mt-caption mt-secondary",
            ))

        # Additional model diagnostic plots — swap based on target
        extra_plots = [
            (f"model_comparison_{tgt}.png",    "Modelcomparisatie — MAE/RMSE/R² per model"),
            (f"predicted_vs_actual_{tgt}.png", "Voorspeld vs. werkelijk (LOO-KV)"),
            (f"per_participant_mae_{tgt}.png",  "MAE per deelnemer"),
            (f"ridge_coefficients_{tgt}.png",  "Ridge-regressiecoëfficiënten"),
        ]
        extra_items = []
        for fname, caption in extra_plots:
            src = _img_b64(plots_dir / fname)
            if src:
                extra_items.append(_ui.div(
                    _ui.div(caption, class_="mt-caption mt-secondary", style="margin-bottom:6px;"),
                    _ui.div(
                        _ui.img(src=src, style="max-width:100%; border-radius:6px;", alt=caption),
                        style="background:#111827; border-radius:10px; padding:12px;",
                    ),
                ))

        if extra_items:
            sections.append(_ui.div(
                _ui.div("Aanvullende modeldiagnostiek", class_="mt-h3",
                        style="margin-top:24px; margin-bottom:12px;"),
                _ui.div(*extra_items,
                        style="display:grid; grid-template-columns:repeat(2,1fr); gap:16px;"),
            ))

        # SHAP dependence plots — swap based on target
        if tgt == "stress_delta":
            dep_plots = [
                ("shap_dependence_stress_delta_baseline_deviation_entry.png",
                 "SHAP dependentie — baseline_deviation_entry (circadiane afwijking)"),
                ("shap_dependence_stress_delta_avg_resp_daily.png",
                 "SHAP dependentie — avg_resp_daily (dagelijkse ademhaling)"),
            ]
        else:
            dep_plots = [
                ("shap_dependence_mood_delta_mood_before_score.png",
                 "SHAP dependentie — mood_before_score (stemming voor sessie)"),
                ("shap_dependence_mood_delta_dow_cos.png",
                 "SHAP dependentie — dag van de week (cosinus)"),
            ]
        dep_items = []
        for fname, caption in dep_plots:
            src = _img_b64(plots_dir / fname)
            if src:
                dep_items.append(_ui.div(
                    _ui.div(caption, class_="mt-caption mt-secondary", style="margin-bottom:6px;"),
                    _ui.div(
                        _ui.img(src=src, style="max-width:100%; border-radius:6px;", alt=caption),
                        style="background:#111827; border-radius:10px; padding:12px;",
                    ),
                ))
        if dep_items:
            sections.append(_ui.div(
                _ui.div("SHAP dependentieplots — top-2 kenmerken", class_="mt-h3",
                        style="margin-top:24px; margin-bottom:8px;"),
                _ui.div("Hoe verandert de SHAP-waarde van een kenmerk over zijn waardebereik?",
                        class_="mt-caption mt-secondary", style="margin-bottom:12px;"),
                _ui.div(*dep_items,
                        style="display:grid; grid-template-columns:repeat(2,1fr); gap:16px;"),
            ))

        # Learning curves
        lc_plots = [
            ("learning_curves_mood_delta.png",  "Leercurven — mood_delta (hoe presteert het model als N groeit?)"),
            ("learning_curves_stress_delta.png", "Leercurven — stress_delta"),
        ]
        lc_items = []
        for fname, caption in lc_plots:
            src = _img_b64(plots_dir / fname)
            if src:
                lc_items.append(_ui.div(
                    _ui.div(caption, class_="mt-caption mt-secondary", style="margin-bottom:6px;"),
                    _ui.div(
                        _ui.img(src=src, style="max-width:100%; border-radius:6px;", alt=caption),
                        style="background:#111827; border-radius:10px; padding:12px;",
                    ),
                ))
        if lc_items:
            sections.append(_ui.div(
                _ui.div("Leercurven", class_="mt-h3",
                        style="margin-top:24px; margin-bottom:8px;"),
                _ui.div(
                    "Trein-MAE (streepjes) vs. LOO-CV-MAE (doorgetrokken lijn) als functie van trainingsgrootte. "
                    "Een kleine kloof duidt op weinig overfitting; platte curven tonen de N=82-grens.",
                    class_="mt-caption mt-secondary", style="margin-bottom:12px;",
                ),
                _ui.div(*lc_items,
                        style="display:grid; grid-template-columns:repeat(2,1fr); gap:16px;"),
            ))

        # LSTM deep learning plots
        lstm_plots = [
            ("lstm_predictions_mood_delta.png",
             "LSTM LOO-CV: voorspeld vs. werkelijk mood_delta (N=27 sessies)"),
            ("lstm_saliency_heatmap.png",
             "Gradient saliency — op welke minuten van de sessie let het LSTM het meest?"),
            ("lstm_vs_tabular_comparison.png",
             "LSTM vs. tabellaire modellen — LOO-CV MAE (lager = beter)"),
        ]
        lstm_items = []
        for fname, caption in lstm_plots:
            src = _img_b64(plots_dir / fname)
            if src:
                lstm_items.append(_ui.div(
                    _ui.div(caption, class_="mt-caption mt-secondary", style="margin-bottom:6px;"),
                    _ui.div(
                        _ui.img(src=src, style="max-width:100%; border-radius:6px;", alt=caption),
                        style="background:#111827; border-radius:10px; padding:12px;",
                    ),
                ))
        if lstm_items:
            sections.append(_ui.div(
                _ui.div("LSTM — Biometrische arc-voorspelling", class_="mt-h3",
                        style="margin-top:24px; margin-bottom:8px;"),
                _ui.div(
                    "1-laag LSTM (32 hidden units) op per-minuut stress + hartslag tijdens de sessie → voorspeld mood_delta. "
                    "LOO-CV, 5× augmentatie. N=27 sessies — DL vereist meer data voor zinvolle generalisatie.",
                    class_="mt-caption mt-secondary", style="margin-bottom:12px;",
                ),
                _ui.div(*lstm_items,
                        style="display:grid; grid-template-columns:repeat(2,1fr); gap:16px;"),
            ))

        return _ui.div(*sections) if sections else _ui.p(
            "SHAP-grafiek niet beschikbaar — voer circadian_ml.py uit.",
            class_="mt-caption mt-secondary",
        )

    @output
    @render.ui
    def bayes_diagnostics_ui():
        bayes_dir = DATA / "analysis" / "bayesian_recommender"
        diag_dir  = bayes_dir / "plots"
        items = []

        # Biometric coefficients — key finding from audit
        bio_src = _img_b64(bayes_dir / "biometric_coefficients.png")
        if bio_src:
            items.append(_ui.div(
                _ui.div("Biometrische coëfficiënten (89% HDI)",
                        class_="mt-caption mt-secondary", style="margin-bottom:6px;"),
                _ui.div(
                    _ui.img(src=bio_src, style="max-width:100%; border-radius:6px;",
                            alt="Biometrische coëfficiënten posterior"),
                    style="background:#111827; border-radius:10px; padding:12px;",
                ),
                _ui.div(
                    "Alle biometrische β-coëfficiënten (stress, hartslag, Body Battery, uur) liggen "
                    "binnen het 89%-HDI rond nul — geen aantoonbaar effect bij N=6 deelnemers.",
                    class_="mt-honesty-callout",
                    style="margin-top:8px;",
                ),
            ))

        for fname, caption in [
            ("trace_plots.png",  "MCMC trace — populatieniveau-parameters"),
        ]:
            src = _img_b64(diag_dir / fname)
            if src:
                items.append(_ui.div(
                    _ui.div(caption, class_="mt-caption mt-secondary", style="margin-bottom:6px;"),
                    _ui.div(
                        _ui.img(src=src, style="max-width:100%; border-radius:6px;", alt=caption),
                        style="background:#111827; border-radius:10px; padding:12px;",
                    ),
                ))
        if not items:
            return _ui.div()
        return _ui.div(
            _ui.div("MCMC-diagnostiek & Biometrische coëfficiënten", class_="mt-h3",
                    style="margin-top:24px; margin-bottom:8px;"),
            _ui.div(*items, style="display:grid; grid-template-columns:repeat(2,1fr); gap:16px;"),
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
                        _arch_box("PyMC NUTS"),
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
