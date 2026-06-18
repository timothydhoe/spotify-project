# Model 6 — Circadian ML
**Project R.E.M. | Notebook: `notebooks/ml/1_circadian_ml.ipynb`**

---

## Is dit machine learning?

**Ja — dit is getraind machine learning.**

Drie regressiemodellen (Ridge, Random Forest, Gradient Boosting) leren van ~95 sessies om `mood_delta` en `stress_delta` te voorspellen. Dit is het meest directe ML-model van het project.

---

## Wat lost dit model op?

Na elke luistersessie weten we hoeveel de stemming veranderde (`mood_delta`) en hoeveel de stress veranderde (`stress_delta`). De vraag: *kan je dat op voorhand voorspellen* — op basis van de context voor en tijdens de sessie?

**RQ3 — het omgekeerde probleem:** Kan je terugrekenen welk playlisttype iemand heeft geluisterd, puur op basis van biometrische respons?

---

## De feature matrix

Per sessie een rij met 20 features (16 inhoudelijk + 4 deelnemerdummies) in zes groepen:

**Groep 1 — Circadiane afwijking (sterkste signaal)**
```
baseline_deviation_entry = pre_stress_mean − expected_stress_at_hour
hr_baseline_deviation    = pre_hr_mean − expected_hr_at_hour
```
`expected_stress_at_hour` = gemiddelde stress van die persoon op niet-sessiedagen op hetzelfde uur. Rauwe stress van 45 betekent iets anders per persoon en per tijdstip — de afwijking controleert voor het persoonlijk ritme.

**Groep 2 — Biometrische context vóór de sessie**
`pre_stress_mean`, `pre_hr_mean`, `bb_start` (Body Battery bij start), `pre_state_encoded` (activiteitsklasse: 0=slaap…3=actief)

**Groep 3 — Biometrie tijdens en na de sessie**
`during_stress_mean`, `post_stress_mean`, `during_hr_mean`, `post_hr_mean`

> **Opgelet — gedeeltelijke leakage:** `stress_delta = post_stress − pre_stress`, dus `post_stress_mean` bevat al een deel van het antwoord. Het model leert deels de algebra van de target te reconstrueren. Dit verklaart mede de hoge R²=0.863 voor stress_delta. Voor mood_delta is dit minder problematisch — mood is zelfgerapporteerd en niet uit deze biometrische features berekend.

**Groep 4 — Tijdcontext**
`hour_of_day`, `day_of_week`, `days_since_last_session`

**Groep 5 — Playlisttype**
`playlist_calm`, `playlist_energy` (0 of 1). Neutral is de **referentiecategorie** — als beide 0 zijn, was het een Neutral-sessie. Twee dummies volstaan voor drie categorieën; drie zou collineariteit introduceren.

**Groep 6 — Stemming en overige**
`mood_before_score`, `hrv_rmssd` (HRV, hoog NaN-percentage), `avg_resp_daily` (ademhaling)

**Groep 7 — Deelnemerdummies**
4 kolommen voor 5 deelnemers (drop_first=True). Het model leert een basisniveau per persoon.

**NaN-aanpak:** Per-fold imputation — imputer gefit op de 94 trainingssessies, toegepast op de 1 testsessie. Voorkomt data leakage via imputatiewaarden.

---

## De vier modellen

**DummyMean** — voorspelt altijd het trainingsgemiddelde. Geen leerproces. Dient als vloer. In LOO is R² licht negatief omdat het trainingsgemiddelde per fold net verschilt van het totaalgemiddelde.

**Ridge** — gewogen som van features met L2-regularisatie:
```
verlies = MSE + α × Σ(wᵢ²)
```
Klein α = weinig regularisatie = gewichten vrij groot = risico op overfitting. Groot α = sterke regularisatie = gewichten richting nul = underfitting. α=1.0 is huidig — de alpha-sweep toont dat dit suboptimaal is.

**Random Forest** — gemiddelde van 100 beslissingsbomen, elk met willekeurige subset van data en features. `max_depth=3` beperkt diepte (regularisatie voor klein N).

**Gradient Boosting** — bouwt bomen sequentieel, elke boom corrigeert fouten van de vorige. Overfit ernstig hier: train R²=0.789 vs. LOO R²=0.202 (gap=0.587).

---

## Interpreteerbaarheid

**Ridge coëfficiënten** — direct leesbaar gewicht per feature.

**Permutation importance** — schud één feature door elkaar, meet MAE-stijging. Grote stijging = feature was belangrijk. Werkt voor elk modeltype.

**SHAP (SHapley Additive exPlanations)**
Per sessie: waarom voorspelde het model dit getal? Elke feature krijgt een bijdrage. Som van alle SHAP-waarden = voorspelling minus globaal gemiddelde. Gebaseerd op speltheorie: gemiddelde marginale bijdrage over alle mogelijke volgorden. Gegarandeerd additief en modelonafhankelijk.

**Beeswarm plot:** elke rij = feature, elk punt = sessie, x-positie = SHAP-waarde, kleur = featurewaarde (rood = hoog, blauw = laag). Rood rechts + blauw links = positief verband.

---

## Regressie naar het gemiddelde

`mood_before_score` is de sterkste predictor. Maar dit signaal bevat twee verstrengelde effecten:

**1. Regressie naar het gemiddelde** (statistisch artefact): extreme scores bevatten meetruis. Bij een tweede meting verdwijnt die ruis deels, waardoor extreme waarden vanzelf richting het gemiddelde bewegen — zonder enige interventie.

**2. Plafond/vloereffect** (schaalgebonden): wie al 9/10 scoort heeft weinig ruimte om te stijgen; wie 2/10 scoort heeft weinig ruimte om te dalen.

Beide zorgen dat `mood_delta` correleert met `mood_before_score` zonder dat de playlist de oorzaak hoeft te zijn.

De **ablation study** test dit met Gradient Boosting (niet Ridge): R² daalt van 0.202 naar −0.277 zonder `mood_before_score`. Het model was sterk afhankelijk van het startpunt-effect.

---

## LOPO — generaliseert het model?

**LOO** laat één sessie weg — het model kent de deelnemer al. **LOPO** laat één deelnemer volledig weg.

| Target | LOO MAE | LOPO MAE | Stijging |
|--------|---------|----------|----------|
| mood_delta (Ridge) | 1.500 | 2.429 | +62% |
| stress_delta (Ridge) | 3.081 | 6.531 | +112% |

- stress_delta generaliseert **niet** — hoge LOO R²=0.863 is deelnemersspecifiek én deels opgeblazen door leakage. Alle modellen falen in LOPO: RF (6.136), GB (5.697).
- mood_delta generaliseert matig.
- Random Forest generaliseert beter dan Ridge voor mood_delta in LOPO (MAE 1.571 vs 2.429) — Ridge heeft de deelnemerdummies te zwaar meegewogen.

---

## Alpha-gevoeligheidsanalyse — actieve bevinding

| Target | Huidig α=1.0 | Optimaal α | MAE verschil |
|--------|-------------|------------|--------------|
| mood_delta | MAE=1.500 | α=10 → MAE=1.460 | −0.040 |
| stress_delta | MAE=3.081 | α=0.01 → MAE=2.642 | −0.439 |

De twee targets willen tegengestelde regularisatie. stress_delta heeft via `post_stress_mean` directere toegang tot het antwoord en heeft minder regularisatie nodig. mood_delta heeft een zwakker signaal en baat bij meer ruis-onderdrukking. Aanpassing valt in Tier 2.

---

## RQ3 — het omgekeerde probleem

Features: alleen biometrie tijdens/na sessie. Geen mood, geen circadiane afwijking.

| Model | Accuracy | Kans baseline |
|-------|----------|---------------|
| Logistic Regression | 38.8% | 33.3% |
| Random Forest | 43.8% | 33.3% |

Neutral (n=13) volledig gemist — te weinig sessies én signaal te zwak. Energy (n=38) domineert de voorspellingen. Marginale verbetering boven kans is onvoldoende om te concluderen dat biometrie het playlisttype kan onderscheiden bij N=80.

---

## Sleutelbegrippen

| Term | Betekenis |
|------|-----------|
| **Circadiane afwijking** | Verschil tussen gemeten stress/HR en verwachte waarde op dat uur op niet-sessiedagen. |
| **LOO-CV** | Leave-one-session-out. Elke sessie is één keer testset. |
| **LOPO** | Leave-one-participant-out. Test overdraagbaarheid naar nieuwe deelnemer. |
| **Per-fold imputation** | Imputer gefit per trainingsset — voorkomt leakage via imputatiewaarden. |
| **Ridge / L2** | Lineaire regressie met straf op grote gewichten (som van kwadraten). α bepaalt sterkte. |
| **Overfitting gap** | Train R² minus LOO R². Groot gat = model generaliseert niet. |
| **SHAP** | Per-feature bijdrage aan een voorspelling via Shapley values. Additief en modelonafhankelijk. |
| **Permutation importance** | MAE-stijging bij het schudden van één feature. |
| **Regressie naar het gemiddelde** | Extreme meetwaarden bewegen bij herhaling richting het gemiddelde door meetruis — kan als effect worden gemeten zonder echte oorzaak. |
| **Plafond/vloereffect** | Op een begrensde schaal hebben extreme scores minder ruimte om verder te bewegen. |
| **Ablation study** | Model trainen zonder een specifieke feature om haar bijdrage te isoleren. |
| **Bootstrap CI** | Onzekerheidsinterval via 1000 hersamples van de LOO-residuelen — model wordt niet opnieuw getraind. |
| **Feature leakage** | Feature bevat (deels) al het antwoord. Hier: `post_stress_mean` in features voor `stress_delta`. |

---

## Koppeling aan onderzoeksvragen

| RQ | Relevantie |
|----|-----------|
| **RQ4** | Ridge R²=0.318 [CI: 0.023–0.508] voor mood_delta. Positief signaal, CI raakt bijna nul. Deels regressie naar het gemiddelde (ablation: R²=−0.277 zonder `mood_before_score`). |
| **RQ1** | stress_delta R²=0.863 deels opgeblazen door leakage, generaliseert niet (LOPO +112%). |
| **RQ3** | 39–44% vs 33% kans. Neutral volledig gemist. Onvoldoende bij N=80. |

---

## Huidige resultaten

### Mood delta (N=95)
| Model | MAE | R² (LOO) | Overfit gap |
|-------|-----|----------|-------------|
| DummyMean | 1.695 | −0.021 | 0.021 |
| **Ridge** | **1.500** | **0.318** | 0.234 |
| Random Forest | 1.617 | 0.229 | 0.421 |
| Gradient Boosting | 1.609 | 0.202 | 0.587 |

Bootstrap 95% CI Ridge: MAE [1.292–1.746], R² [0.023–0.508]

### Stress delta (N=75)
| Model | MAE | R² (LOO) | Overfit gap |
|-------|-----|----------|-------------|
| DummyMean | 10.467 | −0.027 | 0.027 |
| **Ridge** | **3.081** | **0.863** | 0.089 |
| Random Forest | 5.712 | 0.690 | 0.192 |
| Gradient Boosting | 4.762 | 0.773 | 0.185 |

Bootstrap 95% CI Ridge: MAE [2.467–4.024], R² [0.644–0.933]

**Conclusie:** Ridge beste model voor beide targets. mood_delta generaliseert matig (LOPO +62%). stress_delta generaliseert niet (LOPO +112%) en is deels opgeblazen door feature leakage. Alpha-sweep suggereert verbetering via α=10 (mood) en α=0.01 (stress) — Tier 2.
