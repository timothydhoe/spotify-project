# Model 5 — LSTM Arc Predictor
**Project R.E.M. | Script: `scripts/analysis/lstm_arc.py`**

---

## Is dit machine learning?

**Ja — dit is getraind machine learning.**

Een LSTM is een neuraal netwerk dat zijn gewichten aanpast op basis van data via backpropagation. Het leert patronen uit tijdreeksen. Dit onderscheidt het van model 2 (deterministische drempelwaarden) en model 4 (curve fitting met vaste formule).

---

## Wat lost dit model op?

De tabellaire modellen (Ridge, Random Forest, Gradient Boosting) gebruiken alleen fase-gemiddelden van stress en hartslag — ze gooien de tijdsvorm weg. Maar het ISO-principe zegt dat die vorm ertoe doet: een Calm-playlist moet stress geleidelijk doen dalen, een Energy-playlist moet hartslag stapsgewijs omhoog brengen.

Dit model bekijkt de **biometrische tijdreeks per minuut** tijdens de sessie en probeert daar `mood_delta` uit te voorspellen.

**Technisch:** Sequence-to-scalar regressie. Input: tijdreeks van 35 tijdstappen (minuten), elke tijdstap heeft 2 waarden (stress + hartslag). Output: één getal — de voorspelde `mood_delta`.

---

## Hoe werkt het algoritme?

### Stap 1 — Data voorbereiden

Per sessie wordt de **during-fase** geladen: de per-minuut stress en hartslag tijdens de luistersessie. Alle reeksen worden bijgesneden of aangevuld tot precies **35 tijdstappen** — de mediane sessielengte in de data. Kortere sessies worden met nullen aangevuld (zero-padding).

Normalisatie: globale z-score over alle sessies. Let op: de padding-nullen worden meegenormaliseerd — na z-score zijn ze niet meer precies nul. Het model ziet dus geen schone nullen voor de gepadde tijdstappen.

### Stap 2 — Wat is een LSTM?

**In gewone taal:**
Een gewoon neuraal netwerk heeft geen geheugen. Als je het minuut 1 geeft, dan minuut 2, dan minuut 3 — het weet niet dat er een verband is. Het behandelt elk punt afzonderlijk.

Een **LSTM** (Long Short-Term Memory) heeft wel geheugen via twee interne toestanden:
- **Cell state** — het langetermijngeheugen: een vector van 32 getallen die informatie over vele tijdstappen kan bewaren
- **Hidden state** — het kortetermijngeheugen: eveneens 32 getallen, dient als output voor de huidige tijdstap

Via drie **poorten** beslist het netwerk elke tijdstap:
- **Forget gate** — hoeveel van de cell state te bewaren (welke langetermijninformatie te vergeten)
- **Input gate** — welke nieuwe informatie aan de cell state toe te voegen
- **Output gate** — welk deel van de cell state door te geven naar de hidden state

Na de laatste tijdstap (minuut 35) geeft de finale hidden state één getal via een lineaire laag: de voorspelde `mood_delta`.

### Stap 3 — Hoe wordt het getraind?

**Backpropagation:**
Het netwerk maakt een voorspelling, vergelijkt die met de werkelijkheid via MSE, en past zijn gewichten aan om de fout te verkleinen. Voor elk gewicht wordt via de **kettingregel** berekend hoe de fout verandert als dat gewicht een klein beetje wijzigt — de **gradient**. Gewichten worden in de richting van de *negatieve* gradient aangepast (richting die de fout verkleint).

**Backpropagation Through Time (BPTT):**
Bij een LSTM moet de fout teruggerold worden door alle 35 tijdstappen. Het netwerk wordt "opengerold" — elke tijdstap is een aparte laag in een 35 lagen diep netwerk. Omdat hetzelfde LSTM-netwerk op elke tijdstap wordt hergebruikt, worden gradients van alle tijdstappen opgeteld.

**Probleem — vanishing gradients:**
Bij 35 tijdstappen worden gradients herhaaldelijk vermenigvuldigd. Als waarden kleiner zijn dan 1, krimpt de gradient exponentieel — vroege tijdstappen krijgen bijna geen update. De LSTM lost dit op via de **cell state**: de forget gate werkt additief — in plaats van herhaald vermenigvuldigen kan informatie ongewijzigd doorstromen, waardoor gradients niet wegsmelten.

**Adam optimizer:**
In plaats van één vaste leersnelheid voor alle gewichten, past Adam de leersnelheid **per gewicht automatisch aan** op basis van de geschiedenis van gradients:
- Gewichten met grote, consistente gradients → leren snel
- Gewichten met kleine of wisselende gradients → leren voorzichtig

Standaardwaarden (lr=0.001, β₁=0.9, β₂=0.999) — universele PyTorch defaults.

### Stap 4 — Omgaan met kleine N

N=74 sessies is weinig voor een neuraal netwerk. Twee mitigaties:

**LOO cross-validation:** Elke sessie is exact één keer testset. Het model wordt 74 keer opnieuw getraind. Eerlijke schatting van generalisatie.

**Gaussian jitter augmentatie (6×):** Tijdens training worden 5 extra kopieën van elke sessie gemaakt plus het origineel — in totaal 6×. Dit levert ~438 trainingssessies per fold. De jitter wordt toegepast op de al **genormaliseerde data** (z-scores), met standaarddeviatie 3.0 voor stress en 2.0 voor hartslag. Dat zijn standaarddeviaties op z-score schaal — ±3.0 komt overeen met ±3 standaarddeviaties van de stressverdeling. Dit is een potentieel agressieve keuze, maar bij N=74 is het effect moeilijk te isoleren.

### Stap 5 — Gradient saliency

Na training: op welke minuten let het model het meest?

Per tijdstap wordt de **L2-norm** over beide features genomen — dit geeft de totale gevoeligheid als één getal, ongeacht de richting (positief of negatief effect wordt samengevoegd). Grote saliency op minuut t = kleine verandering op dat moment heeft veel effect op de voorspelling.

De saliency plot toont dit gemiddeld over alle sessies. Pieken vroeg of laat in de sessie zouden wijzen op een begin- of eindeffect.

---

## Modelparameters — standaard of onderzocht?

| Parameter | Waarde | Onderzocht? | Reden |
|-----------|--------|-------------|-------|
| `HIDDEN_SIZE` | 32 | Nee | Klein model voor klein N |
| `N_LAYERS` | 1 | Nee | Conservatief voor klein N |
| `DROPOUT` | 0.0 | Nee | Dropout voegt ruis toe bij klein N |
| `EPOCHS` | 80 | Nee | Gekozen getal, geen early stopping |
| `LR` | 1e-3 | Nee | PyTorch Adam default |
| `BATCH_SIZE` | 16 | Nee | Standaard, niet getuned |
| `SEQ_LEN` | 35 | Ja (data) | Mediane sessielengte uit de data |
| `AUGMENT_FACTOR` | 5 | Nee | Vuistregel (levert 6× totaal) |
| `JITTER_STRESS/HR` | 3.0 / 2.0 | Nee | Op z-score schaal — potentieel agressief |

**Geen hyperparameter search** — bewuste keuze: een sweep op N=74 zou zelf overfitting introduceren. Doel is testen *of* er een tijdssignaal is, niet een optimaal model bouwen.

---

## Sleutelbegrippen

| Term | Betekenis |
|------|-----------|
| **LSTM** | Long Short-Term Memory. Neuraal netwerk met twee interne toestanden (cell state + hidden state) dat tijdreeksen verwerkt via drie poorten: forget, input, output. |
| **Cell state** | Langetermijngeheugen van het LSTM. De forget gate bepaalt wat behouden blijft via een additief pad — dit voorkomt vanishing gradients. |
| **Hidden state** | Kortetermijn-output van het LSTM per tijdstap. Dient als input voor de volgende stap en als basis voor de eindvoorspelling. |
| **Backpropagation** | Berekent gradients via de kettingregel. Bepaalt hoeveel elk gewicht moet veranderen om de fout te verkleinen. |
| **BPTT** | Backpropagation Through Time. Gradient terugpropageren door alle tijdstappen van de reeks. |
| **Vanishing gradient** | Gradients krimpen exponentieel bij terugpropageren door veel tijdstappen. De LSTM cell state (additief pad) mitigeert dit. |
| **Adam** | Adaptive optimizer: past leersnelheid per gewicht aan op basis van gradient-geschiedenis. Standaard lr=0.001. |
| **MSE** | Mean Squared Error: gemiddelde van (voorspeld − werkelijk)². Straft grote fouten kwadratisch zwaarder. |
| **LOO-CV** | Leave-One-Out cross-validation. Elke sessie is één keer testset; model getraind op de overige N−1. |
| **Gaussian jitter** | Data-augmentatie: kopieën met Gaussische ruis op z-score schaal. Vergroot trainingsset, vermindert overfitting. |
| **Gradient saliency** | Totale gevoeligheid per tijdstap — L2-norm van de inputgradient over beide features. Richting wordt weggegooid, alleen grootte telt. |
| **Sequence-to-scalar** | Modeltype: tijdreeks als input → één getal als output. |
| **R²** | Verklaarde variantie. R²=0 = even goed als altijd het globale gemiddelde voorspellen. R² negatief = slechter dan het gemiddelde. |

---

## Hoe lees je de resultaten?

**Scatter plot (lstm_predictions_mood_delta.png):** X-as = werkelijk mood_delta, Y-as = voorspeld. Punten op de diagonaal = perfecte voorspelling. Punten gegroepeerd rond een horizontale lijn = model voorspelt altijd hetzelfde getal.

**Saliency plot (lstm_saliency_heatmap.png):** Welke minuten zijn informatief? Vlak = nergens houvast. Pieken = patroon gevonden in een specifiek tijdvenster.

**Vergelijkingsplot (lstm_vs_tabular_comparison.png):** MAE per model. Lager = beter.

---

## Koppeling aan onderzoeksvragen

| RQ | Relevantie |
|----|-----------|
| **RQ4** | *Kan fysiologische toestand + playlisttype de stemmingsuitkomst voorspellen?* — Het LSTM test of de **tijdsvorm** van de fysiologische respons voorspellend is bovenop fase-gemiddelden. Uitkomst: nee, niet bij N=74. Ridge blijft het beste model. |

---

## Huidige resultaten (N=74 sessies, 4 deelnemers)

| Maatstaf | Waarde |
|----------|--------|
| MAE | 2.157 |
| RMSE | 2.848 |
| R² (LOO-CV) | −0.361 |

Ter vergelijking: Ridge MAE=1.578, R²=0.318. Dummy baseline MAE=1.817.

**Conclusie:** De LSTM presteert slechter dan de dummy baseline. De temporele vorm van stress en hartslag voegt niets toe bovenop fase-gemiddelden. Twee bevestigende bevindingen: R²=−0.361 én een vlakke saliency plot — het model heeft geen consistent tijdssignaal gevonden. Dit is een negatief maar informatief resultaat: de hypothese dat de tijdsvorm van de biometrische respons voorspellend is voor stemming wordt niet bevestigd bij deze steekproefomvang.
