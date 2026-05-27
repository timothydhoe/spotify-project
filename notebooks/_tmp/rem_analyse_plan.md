# rem_analyse.ipynb — Bouwplan

Notebook: `notebooks/rem_analyse.ipynb`
Doel: één collectief analysenoverzicht voor Project R.E.M., presentatie-klaar voor 20 juni 2026.
Stijl: donker thema + Okabe-Ito palet, identiek aan `recovery_analysis.ipynb`.
Aanpak: load-only (geen herberekeningen), sectie per sectie gebouwd met goedkeuring per stap.

---

## Workflow per sectie

Voor elke sectie:
1. Vragen stellen over wat getoond moet worden
2. Mini-plan met redenering voorleggen
3. Wachten op goedkeuring
4. Bouwen
5. Ruimte voor feedback en aanpassingen

---

## Pre-flight ✅

- [x] `pipeline.py --participants kokosnoot bosbes` uitgevoerd
  - kokosnoot: 37 sessies, 26 geldige voordelen, gemiddeld +3.8 min
  - bosbes: 4 sessies, 3 geldige voordelen, gemiddeld +20.6 min
  - Output: `classified_minutes.csv`, `recovery_baselines.csv`, `session_effects.csv` aanwezig voor kokosnoot en bosbes
  - Let op: cosmetic KeyError in cross-participant print aan het einde — data is correct

---

## Databeschikbaarheid (samenvatting)

| Deelnemer | Apparaat | Sessies (FM) | Biometrie | Herstel | Check-ins |
|-----------|----------|-------------|-----------|---------|-----------|
| bosbes    | Garmin   | 4           | ✓         | ✓       | ✓         |
| kokosnoot | Garmin   | 40          | ✓         | ✓       | ✓         |
| limoen    | Huawei   | 8           | ✓         | ✗       | ✓         |
| peer      | Garmin   | 30          | ✓         | ✓       | ✓         |
| kiwi      | —        | 0           | ✗         | ✗       | ✓         |
| watermeloen | —      | 0           | ✗         | ✗       | ✓         |

Noten:
- limoen: Huawei → pipeline.py niet ondersteund → sectie 7 (herstelanalyse) uitgesloten
- kiwi, watermeloen: alleen check-in data, geen biometrie → meeste secties uitgesloten maar NIET permanent; meer data kan nog komen
- bosbes: 4 sessies — indicatief, niet conclusief

**Correcte check-in pad:** `data/check_in/check_in.csv` (niet `data/checkins/`)

---

## Secties

---

### ✅ Sectie 1 — Setup & stijl
**Status: VOLTOOID**

Gebouwde cellen:
- Titelpagina + inhoudsopgave (markdown)
- Sectie 1 header (markdown)
- Setup cel: imports (numpy, pandas, matplotlib, seaborn, scipy, arviz, json, pathlib), paden, Okabe-Ito palet, donker thema
- Databeschikbaarheidscheck: tabel met apparaat/sessies/biometrie/herstel/check-ins per deelnemer

Opmerking: CHECKIN_PATH in setup cel staat nog op `data/checkins/...` — moet gecorrigeerd worden naar `data/check_in/check_in.csv`

---

### ⬜ Sectie 2 — Deelnemersoverzicht
**Status: IN PROGRESS — goedgekeurd, nog niet gebouwd**

Goedgekeurd plan:
- **Plot 1 (boven):** Dot/lollipop tijdlijn
  - Y-as: deelnemers gesorteerd op N sessies (peer bovenaan)
  - X-as: datum (studieperiode jan–mei 2026)
  - Elk punt = één sessie, kleur = Calm/Neutral/Energy
  - Dunne verticale lijn van x-as naar punt (lollipop stijl)
  - Kiwi/watermeloen meegenomen waar check-in data bestaat
- **Plot 2 (onder):** Scorecard tabel als matplotlib figuur
  - Rijen = deelnemers, kolommen = N Calm / N Neutral / N Energy / N totaal / Apparaat / Biometrie / Herstel
  - Cellen voor ontbrekende data grijs gekleurd
  - Donker thema

Data bronnen:
- `data/analysis/circadian_baselines/feature_matrix.csv` — sessies + playlist voor deelnemers met biometrie
- `data/check_in/check_in.csv` — voor kiwi/watermeloen sessies (check participant kolom naam eerst!)

**TODO bij hervatten:** check kolom naam in `data/check_in/check_in.csv` voordat code wordt geschreven.

---

### ⬜ Sectie 3 — Circadiane baselines
**Status: GEPLAND**

Wat: 24u stress overlay — persoonlijke stresscurves per uur van de dag, alle deelnemers op één plot.

Data: `data/analysis/{participant}/circadian_baselines/hourly_baseline.csv`
Beschikbaar voor: bosbes, kokosnoot, peer (+ limoen als het bestaat)

Idee: één figuur met alle deelnemers overlaid, x-as = uur (0–23), y-as = gemiddelde stress, schaduwband = ±1 std. Elke deelnemer eigen kleur uit PARTICIPANTS dict.

Uitleg: wat een circadiane baseline is, waarom we hem nodig hebben als referentie voor alle andere analyses.

---

### ⬜ Sectie 4 — Ruwe sessietraces
**Status: GEPLAND**

Wat: 2–3 voorbeeldsessies tonen — stress in de minuten voor/tijdens/na de sessie vs de verwachte circadiane baseline op dat uur.

Data: `data/wearables/{participant}/processed/session_traces/trace_{datum}_{playlist}.csv`
Beste kandidaten: kokosnoot (meeste sessies, gevarieerd) + peer

Vragen bij hervatten:
- Welke sessies als voorbeeld? Automatisch selecteren (meest representatieve) of zelf kiezen?
- Pre/during/post windows tonen als gekleurde achtergrond?

---

### ⬜ Sectie 5 — Stemmingsdistributie
**Status: GEPLAND**

Wat: hoe verandert de stemming (mood_delta) per afspeellijsttype, per deelnemer?

Data: `data/analysis/circadian_baselines/feature_matrix.csv` kolommen: `mood_delta`, `playlist`, `participant`

Idee: boxplots of violin plots, x-as = playlist type, y-as = mood_delta, gefacetteerd per deelnemer of overlaid met kleur. Stippellijn bij 0 (geen verandering).

---

### ⬜ Sectie 6 — Lang-termijntrend
**Status: GEPLAND**

Wat: neemt stress (baseline deviation) af over de loop van de studie? Is er een cumulatief effect van de sessies?

Data: `data/analysis/circadian_baselines/feature_matrix.csv` kolommen: `pre_study_stress_deviation`, sessienummer (afleiden uit datum volgorde per deelnemer)

Tonen voor: peer (p=0.004, sterk signaal) en kokosnoot (p=0.016)
Uitleggen: OLS trendlijn + scatter, significantie vermelden.

---

### ⬜ Sectie 7 — Herstelanalyse
**Status: GEPLAND**

Wat: herstelt stress sneller tijdens muziekluistersessies dan verwacht op basis van de persoonlijke baseline? (tau-voordeel)

Data:
- `data/analysis/{participant}/session_effects.csv` — tau_actual, tau_expected, advantage, r2_actual
- `data/analysis/{participant}/recovery_baselines.csv` — persoonlijke baselines

Deelnemers: bosbes, kokosnoot, peer (limoen uitgesloten — geen pipeline.py output)

Idee: watervalgrafiek (verwachte vs werkelijke tau per sessie) + samenvatting voordeel per playlist type. Reliable filter (r² > 0.05 + pre_stress ≥ asymptoot) expliciet tonen.

Verwijzing naar `recovery_analysis.ipynb` voor volledige methodologie.

---

### ⬜ Sectie 8 — ML-modelresultaten
**Status: GEPLAND**

Wat: hoe goed kunnen we mood_delta en stress_delta voorspellen uit circadiane features + playlist type?

Data:
- `data/analysis/circadian_baselines/model_results_mood_delta.csv`
- `data/analysis/circadian_baselines/model_results_stress_delta.csv`

Plots:
- Modelsvergelijking: MAE per model (Ridge/RF/GBT/Dummy) voor beide targets
- Ridge coëfficiënten: welke features tellen het meest?

Eerlijk tonen: overfit warnings, SHAP betrouwbaarheid, wat we wel/niet kunnen concluderen.

---

### ⬜ Sectie 9 — Significantietoetsen
**Status: GEPLAND**

Wat: zijn de effecten statistisch aantoonbaar?

Data: `data/analysis/circadian_baselines/significance_tests.csv`

Plots:
- Heatmap: p-waarden per test per deelnemer (kleur = significant/niet, grootte = effect size)
- Uitgesplitst voor lange-termijn trend apart (OLS resultaten)

Significante bevindingen uitlichten:
- peer mood_delta_Calm: p=0.047 (verslechtering — onverwacht)
- peer stress lange-termijn trend: p=0.004
- kokosnoot stress lange-termijn trend: p=0.016

---

### ⬜ Sectie 10 — Bayesiaanse aanbeveling
**Status: GEPLAND**

Wat: welk afspeellijsttype past het beste bij welke deelnemer, op basis van een hiërarchisch Bayesiaans model?

Data:
- `data/analysis/bayesian_recommender/recommendations.json`
- `data/analysis/bayesian_recommender/trace.nc` (voor posterior distributies via arviz)
- `data/analysis/bayesian_recommender/parameter_summary.csv`

Plots:
- Posterior distributies per deelnemer (violin of KDE, drie playlists naast elkaar)
- Aanbevelingstabel met probabiliteit

Eerlijk tonen: waar credible intervals overlappen = onzekerheid, meer data nodig.

---

## Bestanden die het notebook gebruikt

```
data/analysis/circadian_baselines/feature_matrix.csv
data/analysis/circadian_baselines/significance_tests.csv
data/analysis/circadian_baselines/model_results_mood_delta.csv
data/analysis/circadian_baselines/model_results_stress_delta.csv
data/analysis/circadian_baselines/{participant}_hourly_baseline.csv
data/analysis/{participant}/circadian_baselines/hourly_baseline.csv
data/analysis/{participant}/session_effects.csv
data/analysis/{participant}/recovery_baselines.csv
data/analysis/bayesian_recommender/recommendations.json
data/analysis/bayesian_recommender/trace.nc
data/analysis/bayesian_recommender/parameter_summary.csv
data/wearables/{participant}/processed/session_traces_all.csv
data/check_in/check_in.csv
```

---

## Correcties nodig bij hervatten

1. **CHECKIN_PATH in sectie 1 setup cel** aanpassen: `data/checkins/Check-in_formulier_REM.csv` → `data/check_in/check_in.csv`
2. **Check kolom naam** in `data/check_in/check_in.csv` voor deelnemersnaam (was nog niet gecheckt)
3. **Sectie 2 bouwen** — alles goedgekeurd, nog niet geïmplementeerd
