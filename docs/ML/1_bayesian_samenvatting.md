# Model 1 — Bayesiaans Hierarchisch Regressiemodel
**Project R.E.M. | Notebook: `notebooks/ml/2_bayesian_recommender.ipynb`**

---

## Wat lost dit model op?

Na elke luistersessie gaven deelnemers aan hoe hun stemming veranderd was (`mood_delta`). Het model probeert te voorspellen welke playlist (Calm / Neutral / Energy) de beste stemmingsverbetering geeft — per persoon, rekening houdend met hun fysiologische toestand vóór de sessie.

Het kernprobleem: sommige deelnemers hebben maar 5 sessies, anderen 40. Met zo weinig data per persoon zijn losse analyses onbetrouwbaar. Het model lost dit op via **partial pooling**: deelnemers delen informatie met elkaar, zodat iemand met weinig data steunt op het groepspatroon.

---

## Hoe werkt het algoritme?

### Stap 1 — Data combineren
Per sessie worden drie bronnen samengevoegd:
- **Check-in CSV** — stemming voor/na (emotie × intensiteit → valentie-gewogen `mood_delta`, zie §Sleutelbegrippen)
- **Session biometrics** — pre-sessie stress, hartslag, body battery
- **Feature matrix** — circadiane basisafwijkingen (gecorrigeerd voor tijdstip van dag)

Deelnemers zonder smartwatch dragen ook bij aan het model — via stemming en playlisteffect. Ze worden niet weggelaten. Alleen de biometrische termen worden voor hen uitgeschakeld via `bio_mask = 0` (zie §Sleutelbegrippen).

### Stap 2 — Modelformule
```
mood_delta ~ Normal(mu, sigma)

mu = alpha[deelnemer]
   + beta_playlist[deelnemer, playlisttype]
   + bio_mask × (beta_stress×stress_z + beta_bb×bb_z + beta_hr×hr_z)
   + beta_hour × hour_z
```

- `alpha` = basisniveau stemmingsverandering per deelnemer
- `beta_playlist` = extra effect van het playlisttype, per deelnemer
- `bio_mask` = schakelaar: 0 voor deelnemers zonder smartwatch
- `_z` = gestandaardiseerde waarden (z-scores): alle variabelen op dezelfde schaal gebracht

### Stap 3 — Bayesiaans schatten via MCMC/NUTS
In plaats van één getal per parameter geeft het model een **kans­verdeling** — de **posterior**. Die wordt berekend via **MCMC** (Markov Chain Monte Carlo): de sampler loopt door een wiskundige ruimte van mogelijke parameterwaarden en bouwt zo stap voor stap de posterior op.

De **NUTS-sampler** (No-U-Turn Sampler) is een variant van **Hamiltonian Monte Carlo**: het simuleert een bal die door het kanslandschap rolt, gebruik makend van de helling (gradient) om efficiënt te bewegen. De bal stopt automatisch wanneer hij dreigt terug te keren — vandaar "No-U-Turn". Dit vereist dat het model wiskundig differentieerbaar is, wat bij PyMC standaard het geval is dankzij automatische differentiatie.

Er worden 4 onafhankelijke runs van de sampler gestart, elk vanuit een ander startpunt — dit zijn de **chains**. Stel je voor: 4 wandelaars die elk apart het landschap verkennen. Als ze uiteindelijk allemaal dezelfde gebieden frequent bezoeken, weten we dat ze de echte posterior gevonden hebben. Dat is wat **R-hat** controleert.

### Stap 4 — Priors
Vóór de data worden **priors** ingesteld — aannames over waar parameters waarschijnlijk liggen. Dit model gebruikt brede, weinig-informerende priors:

```
mu_alpha        ~ Normal(0, 5)       # groepsgemiddeld basisniveau
mu_playlist     ~ Normal(0, 5)       # groepsgemiddeld playlisteffect per type
sigma_alpha     ~ HalfNormal(2)      # spreiding tussen deelnemers
sigma_playlist  ~ HalfNormal(2)      # spreiding van playlisteffecten
beta_stress/bb/hr/hour ~ Normal(0, 2)
sigma (ruis)    ~ HalfNormal(5)
```

Met N=100 sessies en maar 6 deelnemers beïnvloeden deze priors de posterior meetbaar — brede priors laten de data meer spreken, maar helemaal neutraal bestaat niet.

### Stap 5 — Partial pooling (hierarchisch)
Het model heeft twee niveaus:
- **Groepsniveau** — `mu_playlist`: gemiddeld effect van een playlisttype over alle deelnemers
- **Individueel niveau** — `beta_playlist[deelnemer]`: persoonlijke afwijking van dat groepsgemiddelde

Deelnemers met weinig sessies worden **geshrunk** richting het groepsgemiddelde. Deelnemers met veel data trekken meer hun eigen lijn.

### Stap 6 — Non-centered parameterisatie
Een technische stabiliteitsoptimalisatie. In plaats van `alpha[persoon]` direct te schatten:
```
alpha_offset[persoon] ~ Normal(0, 1)
alpha[persoon] = mu_alpha + sigma_alpha × alpha_offset[persoon]
```
Hierdoor werkt de sampler altijd in een brede, makkelijk te verkennen ruimte. De schaal (`sigma_alpha`) bepaalt achteraf hoeveel een deelnemer van het groepsgemiddelde mag afwijken. Wiskundig identiek aan de directe aanpak — maar numeriek veel stabieler bij kleine N, omdat de sampler niet in een smal dal vast komt te zitten.

---

## Sleutelbegrippen

| Term | Betekenis |
|------|-----------|
| **mood_delta** | Stemmingsverandering na sessie. Berekend als (valentie × intensiteit)_na − (valentie × intensiteit)_voor. Valentie: −1 = negatief (gestresseerd/moe), 0 = neutraal, +1 = positief (rustig/gemotiveerd). Intensiteit: schaal 1–10. Bereik in de data: −10 tot +15. |
| **Prior** | Aanname vóór de data — bv. "effect ligt waarschijnlijk rond nul, met wat ruimte." Brede priors laten de data meer sturen. |
| **Posterior** | Kans­verdeling ná de data — het eigenlijke resultaat. Geen enkelvoudig getal, maar een verdeling van plausibele waarden. |
| **HDI (89%)** | Hoogste-dichtheidsinterval: het smalste bereik dat 89% van de posterior omvat. Bayesiaans equivalent van een betrouwbaarheidsinterval. 89% is een gangbare keuze in Bayesiaanse statistiek (ipv 95%). |
| **R-hat** | Convergentiecheck. Berekend *over alle 4 chains samen* per parameter — niet per individuele chain. R-hat vergelijkt de spreiding *tussen* de chains met de spreiding *binnen* elke chain. Als die twee even groot zijn, hebben alle wandelaars hetzelfde gebied verkend: R-hat ≈ 1.0 = geconvergeerd. Als R-hat = 1.15 voor parameter `beta_stress`, betekent dat de 4 chains die parameter inconsistent schatten — niet dat één chain afwijkt, maar dat de chains onderling te ver uit elkaar liggen. Moderne drempel: < 1.01 (oudere literatuur gebruikt 1.1). |
| **ESS bulk/tail** | Effectieve steekproefomvang van de posterior — hoeveel onafhankelijke samples er effectief zijn. ArviZ rapporteert twee varianten: bulk (centrum van de verdeling) en tail (de uiterste staarten). Beide > 400 per chain = betrouwbaar. |
| **Divergenties** | Waarschuwing dat de sampler vastliep in lastige geometrie. 0 divergenties = model werkt correct. |
| **Shrinkage** | Trekken van onzekere schattingen richting groepsgemiddelde — sterker naarmate er minder sessies zijn. |
| **Partial pooling** | Informatie delen tussen deelnemers zonder ze samen te voegen: het compromis tussen volledig apart analyseren en alles op één hoop gooien. |
| **bio_mask** | Schakelaar per sessie: 1 = deelnemer heeft smartwatch (biometrische termen tellen mee), 0 = geen smartwatch. Deelnemers zonder smartwatch worden niet uitgesloten — ze dragen bij aan playlist- en basiseffecten, waardoor de effectieve steekproef groter blijft. |
| **z-score** | Gestandaardiseerde waarde: (waarde − gemiddelde) / standaard­deviatie. Zorgt dat variabelen met verschillende eenheden (bv. stressscore vs. hartslag) vergelijkbaar zijn in het model. |

---

## Hoe lees je de resultaten?

**Posterior grid (sectie 8):** Per deelnemer × playlist een histogram van verwachte `mood_delta`. Hoe verder rechts van de rode stippellijn (= nul), hoe sterker het positieve effect. Hoe breder de verdeling, hoe onzekerder.

**Forest plot groepsniveau (sectie 9):** `mu_playlist` per playlisttype met 89% HDI. Kruist de lijn nul → groepseffect onzeker. Gekleurd = sluit nul uit; grijs = overlapt nul.

**Shrinkage plot (sectie 10):** X-as = ruwe gemiddelde `mood_delta`. Y-as = posterior schatting (alpha). Punten op de diagonaal = geen shrinkage. Punten richting de horizontale lijn = sterk geshrunk (weinig sessies).

**Biometrische coëfficiënten (sectie 11):** Forest plot van stress, hartslag, body battery, uur. Alle ≈ 0 met brede HDI → het model vindt onvoldoende bewijs voor een effect bij deze steekproef. Belangrijk: een breed HDI dat nul overlapt bewijst *niet* dat stress geen invloed heeft — het betekent dat het model met N=4 deelnemers met smartwatchdata het signaal niet van de ruis kan onderscheiden. *Absence of evidence is not evidence of absence.* Een smal interval rondom nul zou pas echt zeggen "het effect is klein"; een breed interval zegt "ik heb onvoldoende informatie."

**Aanbevelingen (sectie 12):** Per deelnemer: aanbevolen playlist, kans (% posterior samples waarbij dit type het beste scoort), en onzekerheidsvlag als intervallen sterk overlappen.

**Gevoeligheidsanalyse (sectie 13):** Drie lijnen over een stressbereik. Omdat bio-coëfficiënten ≈ 0, liggen de lijnen vrijwel plat — stressniveau verandert de aanbeveling nauwelijks.

---

## Koppeling aan onderzoeksvragen

| RQ | Relevantie |
|----|-----------|
| **RQ4** | *Kan fysiologische toestand + playlisttype de stemmingsuitkomst voorspellen?* — Direct. Uitkomst: playlisttype voorspelt wel, biometrie niet (bij N=6). De `recommend_playlist`-functie is de praktische toepassing: per deelnemer een gepersonaliseerde aanbeveling met onzekerheidsinterval. |

---

## Huidige resultaten (N=100 sessies, 6 deelnemers)

- Energy wordt voor alle 6 deelnemers aanbevolen (76–100% kans)
- Gemiddelde mood_delta: Energy +9.0, Calm +2.3, Neutral +2.3
- Alle biometrische coëfficiënten ≈ 0 binnen 89% HDI
- Diagnostiek: R-hat PASS, ESS PASS, 0 divergenties

**Kanttekening — voorzichtig interpreteren:** Energy heeft de meeste sessies (n=46 vs Neutral n=20). Meer sessies = smaller posteriorinterval = Energy *lijkt zekerder*, ook als het werkelijke verschil klein is. Bovendien is er mogelijk **selectiebias**: deelnemers kozen wellicht vaker Energy wanneer ze zich al beter voelden. De unanime aanbeveling "Energy voor iedereen" is daardoor mede een artefact van het studiedesign, niet puur een modelbevinding.
