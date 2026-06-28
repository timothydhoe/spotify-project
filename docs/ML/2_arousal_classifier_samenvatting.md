# Model 2 — Rule-based Arousal Classifier
**Project R.E.M. | Notebook: `notebooks/ml/3_music_class_supervised.ipynb`**

---

## Is dit machine learning?

**Nee — dit is geen getraind machine learning-model.**

Machine learning heeft één kerndefinitie: een systeem dat **leert van data** — het past zijn parameters aan op basis van voorbeelden. Dit model doet dat niet. De gewichten en drempelwaarden zijn handmatig ingesteld door de onderzoeker op basis van muziekpsychologische literatuur. Ze veranderen niet op basis van data. Elke keer dat je het draait met dezelfde input, krijg je exact dezelfde output.

Dit is **regelgebaseerde verwerking** — een deterministische feature engineering pipeline.

**Waarom staat het dan in de ML-sectie?**
Het notebook dient als **rule-based baseline**: een referentiepunt dat laat zien wat bereikbaar is zónder training, zodat de meerwaarde van het GMM-clusteringmodel (notebook 4) afgemeten kan worden. Als het GMM ook ~19% haalt op de ISO-validatie, heeft het niets verbeterd ten opzichte van de handmatige aanpak. Een goede baseline hoort bij verantwoord ML-onderzoek.

**Hoe verdedig je dit?**
> "Dit notebook bevat geen getraind ML-model. Het is een deterministische drempelwaarde-classifier gebaseerd op muziekpsychologische literatuur. Het is opgenomen als rule-based baseline voor vergelijking met het GMM-clusteringmodel. De handmatige aanpak is bij N=3 deelnemers wetenschappelijk verdedigbaar: een interpreteerbare regel is transparanter en controleerbaarder dan een datagedreven model dat overfit op zo weinig data."

---

## Wat lost dit model op?

Elk nummer in de Spotify-bibliotheek van een deelnemer krijgt een **arousal-score** — een getal dat uitdrukt hoe opwekkend of rustgevend het nummer klinkt. Op basis van die score wordt elk nummer ingedeeld als **CALM**, **ENERGY**, of **OTHER**.

Doel: automatisch een pool van geschikte nummers aanmaken per categorie, zodat de playlist-generator daar uit kan putten. Het is een genuanceerdere aanpak dan de losse BPM/energy-filters van `spotify_cli.py`.

---

## Hoe werkt het stap voor stap?

### Stap 1 — Voorfilter
Twee soorten nummers worden verwijderd vóór scoring (drempels uit Spotify API-documentatie):
- `liveness > 0.80` → waarschijnlijk een live-opname (ander geluidsprofiel dan studio)
- `speechiness > 0.66` → gesproken woord of podcast, geen muziek

### Stap 2 — Normalisatie per deelnemer (MinMaxScaler)
De vijf kenmerken hebben elk een andere schaal (tempo in BPM, energy 0–1, loudness in dB). Ze worden omgezet naar het bereik [0,1] via een **MinMaxScaler** — maar *per deelnemer apart*.

```
genormaliseerde waarde = (waarde − minimum van die deelnemer) / (maximum − minimum)
```

Waarom per deelnemer? Iemand die alleen elektronische muziek luistert heeft een heel andere min/max tempo dan een klassiekluisteraar. Per-deelnemer normalisatie zorgt dat de drempelwaarden dezelfde *relatieve* betekenis hebben voor iedereen: een score van 0.65 betekent altijd "in het bovenste deel van *jouw eigen* bibliotheek."

**Keerzijde 1:** nummers zijn na normalisatie niet meer vergelijkbaar over deelnemers heen.

**Keerzijde 2:** MinMaxScaler is gevoelig voor uitbijters. Eén nummer met extreem hoge BPM comprimeert de hele schaal — alle andere nummers worden dan relatief lager gescoord. De voorfilter vermindert dit deels, maar sluit het niet uit.

### Stap 3 — Arousal-score berekenen
```
arousal = 0.35 × energy
        + 0.30 × tempo
        + 0.20 × loudness
        − 0.10 × acousticness
        + 0.05 × danceability
```

Een **gewogen som** van de genormaliseerde kenmerken. De gewichten zijn gebaseerd op muziekpsychologisch onderzoek naar arousaldimensies — met name Russell's circumplex model (1980), dat arousal en valentie als de twee kerndimensies van emotie in muziek definieert.

De gewichten sommeren tot **0.80** (niet 1.0) — dit is bewust. Alleen de onderlinge verhouding is relevant voor de rangschikking van nummers. Maar let op: de absolute som beïnvloedt wel het effectieve bereik van de score, en daarmee de betekenis van de drempelwaarden (zie hieronder).

### Stap 4 — Drempelwaarden en het werkelijke score-bereik

Door de gewichten en het negatieve teken bij acousticness loopt de arousal-score in de praktijk van ongeveer **−0.10 tot 0.80** — niet van 0 tot 1 zoals je misschien zou verwachten.

De drempelwaarden 0.35 en 0.65 liggen daardoor niet op "35% en 65% van de schaal", maar eerder op respectievelijk ~50% en ~83% van het effectieve bereik. Dit is een bewuste keuze van de onderzoeker, geen fout — maar het is belangrijk te weten bij het interpreteren van de resultaten.

**Classificatieregels:**
```
arousal < 0.35  EN  valence_norm ≥ 0.25  →  CALM
arousal > 0.65                            →  ENERGY
al het overige                            →  OTHER
```

De **valence-vloer** bij CALM: rustige muziek met lage valentie (droeve nummers) wordt niet als CALM geclassificeerd. Voor stressreductie is een positieve emotionele toon wenselijk. Nummers in het middengebied en te droeve nummers belanden in OTHER.

---

## Sleutelbegrippen

| Term | Betekenis |
|------|-----------|
| **Arousal** | De mate van activering die muziek oproept. Hoog = energetisch, luid, snel. Laag = rustig, akoestisch, traag. Eén van de twee kerndimensies in muziekpsychologie volgens Russell's circumplex model (1980). De andere is valentie. |
| **MinMaxScaler** | Normalisatiemethode: `(waarde − min) / (max − min)`. Zet elke waarde om naar zijn relatieve positie in het bereik, altijd tussen 0 en 1. Gevoelig voor uitbijters: één extreem nummer comprimeert de hele schaal. |
| **Per-deelnemer normalisatie** | Scaler wordt apart gefittet op de bibliotheek van elke deelnemer. Maakt drempelwaarden relatief aan de eigen bibliotheek; nummers zijn daarna niet vergelijkbaar over deelnemers heen. |
| **Gewogen som** | Elke feature draagt bij naar evenredigheid van zijn gewicht. De onderlinge verhouding bepaalt het relatieve belang; de absolute som beïnvloedt het bereik van de score en daarmee de effectieve werking van de drempelwaarden. |
| **Valentie-vloer** | Minimumdrempel op genormaliseerde valentie voor de CALM-klasse. Voorkomt dat droeve, stille muziek als rustgevend wordt geclassificeerd. |
| **Deterministische classifier** | Geen kans, geen onzekerheid, geen leren. Dezelfde input geeft altijd hetzelfde label. |
| **OTHER** | Opvangklasse voor het middengebied en te droeve nummers — 77–79% van alle nummers. Dit is bewust conservatief: alleen hoge-zekerheid nummers krijgen een CALM of ENERGY label. Alleen CALM en ENERGY worden gebruikt als pool voor playlistgeneratie. |
| **Rule-based baseline** | Een niet-geleerd referentiemodel waartegen een ML-model vergeleken wordt. Laat zien wat bereikbaar is zonder training — de vergelijkingsvloer voor het GMM. |
| **ISO-validatie** | Controle of de classifier overeenkomt met handmatig gevalideerde ISO-playlists — de enige beschikbare grondwaarheid. Resultaat: 19% — nuttig als vergelijkingsvloer, niet als absolute prestatiescore. |

---

## Hoe lees je de resultaten?

**Klasseverdeling (sectie 5a):** Tabel met CALM/ENERGY/OTHER per deelnemer. Een grote OTHER-fractie (77–79%) is normaal en by design — conservatieve classificatie zorgt dat alleen duidelijk passende nummers een label krijgen. Waarschuwing bij < 5% CALM of ENERGY (watermeloen: 4% CALM).

**Gemiddelde kenmerken per klasse (sectie 5c):** Controle of klassen logisch van elkaar verschillen. Verwacht patroon: CALM heeft lage energy (~0.2) en hoog acousticness (~0.85); ENERGY heeft hoge energy (~0.89) en laag acousticness (~0.04). Als dit patroon ontbreekt, kloppen de drempelwaarden niet.

**Drempelwaarde-sweep (sectie 5e):** Toont hoe de klasseverdeling verschuift bij andere drempelwaarden. Helpt bepalen of de huidige instelling stabiel is of gevoelig voor kleine wijzigingen.

**Spot-check (sectie 5f):** 10 willekeurige nummers per klasse — de enige menselijke controle in het systeem. Klinkt een CALM-nummer ook echt rustig?

**ISO-validatie (sectie 5g):** Vergelijkt classifier-uitkomst met ISO-gegenereerde playlists. Gemiddeld **19% correctheid** — dit is een verwacht resultaat: de classifier is *relatief* (per-deelnemer normalisatie), de ISO-generator is *absoluut* (vaste BPM-grenzen). Het getal is primair nuttig als vergelijkingsvloer: als het GMM (notebook 4) ook rond 19% uitkomt, heeft datagedreven clustering niets toegevoegd.

---

## Koppeling aan onderzoeksvragen

| RQ | Relevantie |
|----|-----------|
| **RQ5** | *Kan automatische muziekclassificatie playlistgeneratie verbeteren voorbij handmatige BPM-drempels?* — Dit model is de rule-based variant van dat antwoord. De arousal-score maakt een genuanceerdere indeling dan losse BPM/energy-filters, maar stemt slecht overeen met ISO-playlists (19%). Het GMM (notebook 4) probeert dit te verbeteren via datagedreven clustering. |

---

## Huidige resultaten (3 deelnemers)

| Deelnemer | CALM | ENERGY | OTHER | Totaal |
|-----------|------|--------|-------|--------|
| courgette | 566 (10%) | 737 (13%) | 4417 (77%) | 5720 |
| peer | 53 (8%) | 96 (14%) | 542 (78%) | 691 |
| watermeloen | 25 (4%) ⚠️ | 103 (17%) | 492 (79%) | 620 |

**ISO-validatie:** gemiddeld 19% correctheid — verwacht door schaalverschil relatief vs. absoluut; dient als vergelijkingsvloer voor het GMM.
