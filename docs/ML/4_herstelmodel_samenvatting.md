# Model 4 — Exponentieel Herstelmodel
**Project R.E.M. | Notebook: `notebooks/visualisation/recovery_analysis.ipynb`**

---

## Is dit machine learning?

**Nee — dit is curve fitting, geen ML.**

Het model leert geen parameters op basis van gelabelde voorbeelden. In plaats daarvan past het een vaste wiskundige formule aan op gemeten data. Dezelfde curve, andere getallen — afhankelijk van de sessie. Het is **wiskundige modellering van een fysisch patroon**, niet patroonherkenning.

---

## Wat lost dit model op?

Na een luistersessie daalt de stress van deelnemers geleidelijk terug naar rust. De vraag is: **hoe snel herstellen deelnemers na een sessie, en doet het playlisttype er toe?**

Het model meet herstel via **tau** — de tijdsconstante van de exponentiële daling. Een lage tau = snel herstel. Het vergelijkt tau_actual (gemeten herstel na een luistersessie) met tau_expected (typisch herstel op een gewone dag zonder sessie).

---

## Hoe werkt het algoritme?

### De formule

```
stress(t) = asymptote + (start − asymptote) × e^(−t/tau)
```

- `start` = stressniveau aan het begin van de post-sessie fase
- `asymptote` = het niveau waarop stress uiteindelijk stabiliseert (rustwaarde)
- `tau` = tijdsconstante — hoe snel de curve daalt
- `t` = tijd in minuten

**Tau in gewone taal:**
Na één tau-periode is **63%** van het verschil tussen start en asymptote overbrugd. Na 2.3× tau is **90%** van de daling afgerond. Kleine tau = steile curve = snel herstel.

**Waarom 63%?** Dit is een wiskundige eigenschap van de exponentiële functie: bij t = tau geldt altijd `e^(−1) ≈ 0.37`, dus 63% van het traject is afgelegd.

### Hoe wordt de curve gefit?

Via **scipy curve_fit** — een numerieke optimalisator (Levenberg-Marquardt algoritme). Die zoekt de waarden voor `asymptote`, `start`, en `tau` die de gekwadrateerde afwijkingen tussen de gemeten punten en de curve minimaliseren. Er is geen gradient descent of backpropagation — het is gewone niet-lineaire kleinste-kwadraten optimalisatie.

### Kwaliteitsfilters

Niet elke sessie levert een bruikbare curve op. Twee filters:

| Filter | Drempel | Reden |
|--------|---------|-------|
| **r²** | > 0.05 | Pragmatische drempel — bij ruis past geen curve. Laag maar verdedigbaar: weinig punten per sessie (20–60 min), ruwe stressdata |
| **pre_stress ≥ asymptote** | vereist | Als stress al onder de rustniveau zit, is er geen herstel te meten — de formule heeft geen zin |

Van 81 sessies voldoen er **18** (22%) aan beide filters. Dit is een harde bevinding: **78% van de sessies produceert geen bruikbare herstelcurve**.

---

## Sleutelbegrippen

| Term | Betekenis |
|------|-----------|
| **Tau (τ)** | Tijdsconstante van exponentieel herstel. Bij t=tau is 63% van de stressdaling afgerond. Bij t=2.3τ is 90% bereikt. Kleinere tau = sneller herstel. |
| **Asymptote** | Het niveau waarop stress na lange tijd stabiliseert. Wordt door scipy curve_fit *geschat* uit de data — het is geen vaste, vooraf ingestelde waarde. Bij ruisige data kan de fit een asymptote schatten die ver van de werkelijke rustwaarde ligt. |
| **tau_expected** | Mediaan tau berekend op niet-sessiedagen per deelnemer — de typische herstelsnelheid van die persoon zonder muziekinterventie. Dit is de baseline. |
| **tau_actual** | Tau per individuele sessie — gemeten herstelsnelheid na afloop van de luistersessie. |
| **r²** | Hoe goed de curve de gemeten punten volgt (0 = niets, 1 = perfect). Drempel 0.05 is pragmatisch: bij weinig en ruis­rijke datapunten zijn hoge r²-waarden zeldzaam. |
| **Selectiebias** | De 18 betrouwbare sessies zijn niet willekeurig: ze selecteren op hoge beginstress (pre_stress ≥ asymptote) en meetbare daling (r² > 0.05). Deelnemers die al ontspannen begonnen vallen weg. Het gemiddelde voordeel van +28.4 min geldt dus voor sessies waarbij herstel sowieso al aanwezig was. |
| **Anti-conservatief t-test** | Het model behandelt 18 sessies als 18 onafhankelijke observaties. Maar: meerdere sessies per deelnemer (4–5 deelnemers). Effectieve vrijheidsgraden ≈ 4, niet 17. De p-waarde van 0.003 is te optimistisch. Het resultaat is richtinggevend, niet statistisch hard. |
| **scipy curve_fit** | Niet-lineaire kleinste-kwadraten optimalisatie (Levenberg-Marquardt). Minimaliseert de som van gekwadrateerde residuen. Geen training, geen labels — puur wiskundige curve-aanpassing. |

---

## Hoe lees je de resultaten?

**Individuele curven (sectie 4–5):** Per sessie een scatter van stressmeting met de gefitte curve. Steile curve = kleine tau = snel herstel. Platte curve = langzaam of geen herstel.

**Tau-vergelijking (sectie 6):** Boxplot van tau_expected vs tau_actual. Als de boxen niet overlappen is er een zichtbaar verschil. Maar: n=18, selectiebias.

**Gemiddeld voordeel (sectie 7):** tau_expected − tau_actual gemiddeld = **+28.4 min** (p=0.003). Deelnemers herstellen na een luistersessie gemiddeld 28 minuten sneller dan normaal. Kanttekening: effectieve n ≈ 4 deelnemers, p-waarde anti-conservatief.

**Per-playlist breakdown (sectie 8):** Calm/Energy/Neutral elk met eigen tau-vergelijking. **Beschrijvend only** — Neutral heeft slechts n=1 betrouwbare sessie, elke numerieke vergelijking daar is zinloos. Calm en Energy hebben meer sessies, maar ook daar zijn n-waarden te klein voor inferentie. Gebruik dit als verkennende indicator, niet als bewijs.

**22% yield als bevinding op zich:** Dat slechts 1 op 5 sessies een betrouwbare herstelcurve oplevert, zegt al iets: exponentieel herstel is niet de standaard respons. Stress daalt niet altijd voorspelbaar. Dit is een resultaat, niet alleen een methodologisch probleem.

---

## Twee redenen voor voorzichtigheid

### 1. Selectiebias
De sessies die *wel* een bruikbare curve opleveren zijn niet representatief. Ze selecteren op:
- Hoge beginstress (pre_stress ≥ asymptote) — ontspannen deelnemers vallen weg
- Meetbare daling (r² > 0.05) — sessies met vlakke of chaotische stress vallen weg

Het voordeel van +28.4 min is dus: "voor sessies waarbij herstel al aanwezig was, herstellen deelnemers na muziek sneller." Dat is een andere en smallere claim dan "muziek versnelt herstel bij iedereen."

### 2. Niet-onafhankelijke observaties
Een t-test veronderstelt onafhankelijke observaties. Meerdere sessies van dezelfde deelnemer zijn dat niet — ze delen dezelfde biometrie, leefstijl, en studieperiode. De effectieve vrijheidsgraden zijn ≈ 4 (het aantal deelnemers met smartwatchdata), niet 17 (het aantal sessies). De p-waarde is daardoor te klein — het resultaat is richtinggevend, niet statistisch hard.

---

## Circulaire baseline

tau_expected wordt berekend op niet-sessiedagen. Die dagen zijn niet-sessiedagen *omdat* ze niet zijn geselecteerd voor het onderzoek — ze vormen dus geen volledig willekeurige steekproef van "gewone dagen". Bovendien overlapt de definitie van tau_expected (rustwaarde per deelnemer) gedeeltelijk met de selectiefilter (pre_stress ≥ asymptote). Dit is een subtiel methodologisch punt: de baseline en de filter zijn niet volledig onafhankelijk.

---

## Koppeling aan onderzoeksvragen

| RQ | Relevantie |
|----|-----------|
| **RQ1** | *Kunnen ISO-playlists stress objectief verlagen (smartwatch)?* — Direct. Uitkomst: +28.4 min sneller herstel bij 22% van de sessies. Voorzichtig positief signaal, te klein om hard te concluderen. |
| **RQ2** | *Correleert fysiologische stressdaling met betere stemming?* — Indirect. Dit model meet het fysiologische deel. De koppeling met mood_delta zit in model 1 (Bayesian). |

---

## Huidige resultaten (81 sessies)

| Maatstaf | Waarde |
|----------|--------|
| Betrouwbare sessies | 18 / 81 (22%) |
| Gemiddeld tau-voordeel | +28.4 min |
| p-waarde (t-test) | 0.003 (anti-conservatief: effectieve df ≈ 4) |
| Per-playlist | Calm en Energy vergelijkbaar; Neutral n=1 → niet vergelijkbaar |

**Conclusie:** Richtinggevend positief signaal — deelnemers lijken na een luistersessie sneller te herstellen. Maar 78% uitval, selectiebias, en niet-onafhankelijke observaties maken hard concluderen niet mogelijk bij deze steekproefomvang.
