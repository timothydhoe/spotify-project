# Model 3 — Gaussian Mixture Model (GMM)
**Project R.E.M. | Notebook: `notebooks/ml/4_music_class_unsupervised.ipynb`**

---

## Wat lost dit model op?

In tegenstelling tot model 2 stelt dit model geen regels op voorhand. Het krijgt alle nummers van alle deelnemers te zien — 6760 nummers beschreven door 6 audio-kenmerken — en wordt gevraagd: *"Welke muzikale groepen zitten er vanzelf in deze data?"*

Het model leert zelf patronen. Dat maakt het **ongesuperviseerde machine learning** — er zijn geen labels. Niemand zegt vooraf wat "CALM" of "ENERGY" is. De vraag is of de data die indeling zelf terugvindt.

Dit is een **clusteringprobleem**: groepeer nummers zo dat nummers binnen een groep op elkaar lijken, en nummers uit verschillende groepen van elkaar verschillen. De uitdaging: je weet niet op voorhand hoeveel groepen er zijn.

---

## Hoe werkt een Gaussian Mixture Model?

**In gewone taal:**
Stel je voor dat je een wolk van punten ziet (elk punt = een nummer in de 6D audio-ruimte). Een GMM probeert die wolk te verklaren als een mix van meerdere *bellen* — elke bel is een groep nummers die bij elkaar horen. De bellen mogen overlappen.

Wat het model leert:
- Waar elke bel zit (het gemiddelde)
- Hoe groot en welke vorm elke bel heeft (de covariantie)
- Hoe zwaar elke bel weegt (hoeveel nummers er in zitten)

**Technisch:**
Elke bel is een **multivariate Gaussische verdeling** — een normaalverdeling in meerdere dimensies tegelijk. In 6D beschrijft het een ellipsoïde wolk van punten.

Het model leert via **Expectation-Maximization (EM)**:
1. **E-stap:** Bereken voor elk nummer de kans dat het bij elke bel hoort
2. **M-stap:** Herbereken de bel-parameters op basis van die kansen
3. Herhaal tot convergentie

Resultaat: elk nummer krijgt niet één hard label maar een **probabilistische toewijzing** — bv. "75% kans op cluster 0, 20% op cluster 1, 5% op cluster 2."

**Waarom GMM en niet K-Means?**
K-Means veronderstelt dat clusters rond en even groot zijn. GMM maakt geen zulke aanname — bellen mogen langwerpig, schuin georiënteerd of overlappend zijn. Reëler voor muziek.

Het model gebruikt `covariance_type='full'`: elke bel krijgt een eigen, volledig vrije covariantiematrix. Dit is de meest flexibele optie, maar heeft ook de meeste parameters — wat deels verklaart waarom BIC blijft dalen bij meer clusters.

---

## Normalisatie: waarom StandardScaler?

Model 2 gebruikte MinMaxScaler per deelnemer. Dit model gebruikt een **globale StandardScaler**:
```
gestandaardiseerde waarde = (waarde − gemiddelde) / standaarddeviatie
```

Twee redenen:
1. Zonder schaling domineren kenmerken met een grote numerieke schaal (tempo in BPM) de covariantieberekening — alle andere kenmerken (energy 0–1, acousticness 0–1) wegen dan nauwelijks mee. StandardScaler brengt alles op gelijke voet. Let op: StandardScaler maakt data niet Gaussisch verdeeld — het centreert en schaalt alleen.
2. Dit model werkt op **alle deelnemers samen** — één globale scaler, geen per-deelnemer normalisatie.

---

## Hoe kies je het juiste aantal clusters?

Twee criteria worden naast elkaar gebruikt:

**BIC (Bayesian Information Criterion)**
```
BIC = −2 × log-likelihood + p × log(n)
```
- `log-likelihood` = hoe goed het model de data verklaart
- `p` = totaal aantal vrije parameters in het model (niet het aantal clusters)
- `n` = aantal datapunten

Lagere BIC = beter. Maar hier **daalt BIC monotoon van k=2 tot k=10** — er is geen duidelijk minimum. Het model wil steeds meer clusters, mede omdat `covariance_type='full'` bij elke extra cluster veel nieuwe parameters toevoegt die de likelihood verbeteren.

**Silhouette-score**
Meet hoe goed een nummer bij zijn eigen cluster past versus andere clusters. Waarde tussen −1 en 1:
- Dicht bij 1 = nummer zit duidelijk in het goede cluster
- Dicht bij 0 = clusters overlappen sterk
- Negatief = nummer zit waarschijnlijk in het verkeerde cluster

Gangbare drempel voor zwakke clusterstructuur: **0.25**. Zelfs bij k=3 scoort dit model slechts 0.134 — dat wijst al op een continu spectrum zonder scherpe grenzen. De projectkeuze was om k=5 te kiezen als laatste k boven de minimumdrempel van 0.05, wat betekent: nog net onderscheidbaar, maar nauwelijks.

**De spanning:**
BIC wil meer clusters (minimum ligt buiten het zoekbereik), silhouette zegt stop bij k=5. Het notebook kiest **k=5** als compromis: laatste k met nog marginale scheiding.

| Criterium | k=3 | k=5 | Betekenis |
|-----------|-----|-----|-----------|
| BIC | 75271 | 71738 | k=5 verklaart data statistisch beter |
| Silhouette | 0.134 | 0.072 | k=3 heeft beter gescheiden clusters |

---

## Sleutelbegrippen

| Term | Betekenis |
|------|-----------|
| **GMM** | Model dat een dataverdeling beschrijft als een mix van Gaussische bellen. Elk cluster is één bel met eigen gemiddelde, covariantie en gewicht. |
| **Multivariate Gaussische verdeling** | Normaalverdeling in meerdere dimensies tegelijk. In 6D een ellipsoïde wolk van punten. |
| **EM-algoritme** | Iteratief leeralgoritme: E-stap (kansen berekenen) en M-stap (parameters updaten) wisselen af tot convergentie. |
| **Probabilistische toewijzing** | Elk nummer krijgt een kans per cluster, geen hard label. Onderscheidt GMM van K-Means. |
| **BIC** | Bayesian Information Criterion: maatstaf voor modelfitskwaliteit die complexiteit straft (via aantal modelparameters `p`, niet aantal clusters `k`). Lager = beter. |
| **Silhouette-score** | Maatstaf voor clusterscheiding (−1 tot 1). Gangbare drempel voor zwakke structuur: 0.25. Hier 0.072–0.134 — de featureruimte is een continu spectrum. De drempel van 0.05 is een projectkeuze, niet een vaste standaard. |
| **PCA** | Dimensiereductie: 6 kenmerken → 2 assen voor visualisatie. Clusters die *goed gescheiden* zijn in de PCA-plot zijn dat ook echt. Overlap in 2D garandeert niet per se overlap in 6D — maar de lage silhouette bevestigt dat ze hier inderdaad overlappen. |
| **covariance_type='full'** | Elke bel krijgt een eigen vrije covariantiematrix — meest flexibel, meeste parameters. Verklaart mede waarom BIC blijft dalen. |
| **StandardScaler** | Normaliseert naar gemiddelde 0 en standaarddeviatie 1. Voorkomt dat kenmerken met grote schaal de covariantie domineren. Maakt data niet Gaussisch. |
| **Kruistabulatie** | Vergelijkingstabel GMM-clusters vs. model 2-labels. Toont of de twee modellen overeenkomen. |

---

## Hoe lees je de resultaten?

**BIC/silhouette curve (sectie 4):** BIC daalt monotoon — geen duidelijk optimum. Silhouette daalt na k=5 onder 0.05. Meer clusters beschrijven de data statistisch beter, maar zijn muzikaal niet meer onderscheidbaar.

**Clusterprofiel k=3 (sectie 11):** Cluster 0 = CALM-achtig (arousal 0.119, hoog acousticness). Cluster 1 en 2 = beide NEUTRAAL-achtig (arousal 0.447 en 0.618). Geen enkel cluster haalt de ENERGY-drempel van 0.65 — de featureruimte heeft geen scherpe ENERGY-pool.

**Kruistabulatie (sectie 11):** Alle drie GMM-clusters gedomineerd door OTHER (75–84%). Cluster 0 vangt 25% van de CALM-nummers, cluster 2 vangt 32% van de ENERGY-nummers. De twee modellen overlappen maar stemmen niet sterk overeen.

**PCA-scatter (sectie 7):** Bij k=3 zijn drie kleurgebieden zichtbaar maar overlappend. Bij k=5 is de overlap nog sterker. Wat je ziet in 2D wordt bevestigd door de silhouette in 6D: geen scherpe grenzen.

---

## Koppeling aan onderzoeksvragen

| RQ | Relevantie |
|----|-----------|
| **RQ5** | *Weerspiegelt de audio-featureruimte de calm/neutral/energy driedeling?* — Antwoord: **deels**. k=3 GMM vindt een CALM-cluster en twee NEUTRAAL-achtige clusters, maar geen zuiver ENERGY-cluster. De featureruimte is een continu spectrum. De driedeling is een nuttige approximatie, geen objectieve waarheid in de data. |

---

## Huidige resultaten (6760 nummers, 3 deelnemers)

| Model | k | BIC | Silhouette |
|-------|---|-----|-----------|
| Geforceerd | 3 | 75271 | 0.134 (zwakke structuur) |
| BIC-optimaal | 5 | 71738 | 0.072 (marginale structuur) |

Kruistabulatie k=3 vs. model 2: alle clusters gedomineerd door OTHER (75–84%). Geen sterke overeenkomst tussen GMM en rule-based labels.

---

## GMM vs. playlist-generator — wat betekent dit in de praktijk?

De playlist-generator (`spotify_cli.py`) werkt volledig **onafhankelijk van het GMM**. Hij gebruikt absolute BPM/energy-drempels: tempo > 120 EN energy > 0.7 → ENERGY-nummer. Die generator *kan* wel degelijk ENERGY-nummers vinden en correcte playlists genereren.

Wat het GMM-resultaat dan wél zegt: de nummers die als ENERGY geselecteerd worden, liggen in de featureruimte **niet in een aparte cluster** — ze overlappen met de rest. De grens tussen ENERGY en NEUTRAAL is willekeurig, niet door de data gemotiveerd.

Kortom: de playlist-generator **werkt**, maar het GMM toont aan dat de driedeling (CALM / NEUTRAL / ENERGY) een **door de mens opgelegd label is op een gradiënt**, geen objectief muzikaal gegeven. De categorie bestaat omdat we hem definiëren, niet omdat de muziek zichzelf zo organiseert.
