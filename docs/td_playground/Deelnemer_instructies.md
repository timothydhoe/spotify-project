# Deelnemer Instructies: Data Export per Smartwatch Type

## Overzicht

Deze gids helpt u om uw smartwatch data te exporteren voor ons onderzoek. Omdat deelnemers verschillende merken smartwatches gebruiken, hebben we instructies per merk/platform opgenomen.

**Selecteer uw smartwatch merk:**
- [Apple Watch](#apple-watch)
- [Fitbit](#fitbit)
- [Garmin](#garmin)
- [Samsung Galaxy Watch](#samsung-galaxy-watch)
- [Andere / Onbekend](#andere-smartwatches)

**Export frequentie**: Om de [X] weken (we sturen u een herinnering)

---

## Apple Watch

### Benodigde data
Via de Apple Health app exporteren we:
- Hartslag (Heart Rate)
- Hartslagvariabiliteit (Heart Rate Variability / HRV)
- Slaap (Sleep Analysis)
- Stappen (Steps)
- Bloedzuurstof (Blood Oxygen / O₂, indien beschikbaar)
- Ademhalingsfrequentie (Respiratory Rate, indien beschikbaar)

### Stap-voor-stap export

#### Optie 1: Via Health Auto Export app (AANBEVOLEN)
Deze app automatiseert de export voor u.

1. **Download app**:
   - App Store → zoek "Health Auto Export"
   - Installeer de app (gratis, of betaalde versie voor extra functies)

2. **Configuratie**:
   - Open Health Auto Export
   - Selecteer data types:
     - ✅ Heart Rate
     - ✅ Heart Rate Variability (HRV)
     - ✅ Sleep Analysis
     - ✅ Steps
     - ✅ Blood Oxygen (indien beschikbaar)
     - ✅ Respiratory Rate (indien beschikbaar)
   
3. **Export instellingen**:
   - Format: **CSV**
   - Date range: **Custom** (vanaf startdatum onderzoek tot nu)
   - File name: `P[UW CODE]_applehealth_[DATUM].csv`
   
4. **Export uitvoeren**:
   - Tap "Export Automations" → "Manual Export"
   - Kies "Save to Files" → selecteer een lokale map (NIET iCloud)
   - Stuur het bestand naar ons via [UPLOAD METHODE]

#### Optie 2: Handmatig via Health app
Als u geen externe app wilt gebruiken.

1. **Open Health app** op uw iPhone
2. **Tap uw profielfoto** (rechtsboven)
3. **Scroll naar beneden** → tap "Export All Health Data"
4. **Wacht** tot export compleet is (kan enkele minuten duren)
5. **Deel** het export.zip bestand:
   - Let op: dit bestand bevat ALLE health data (niet alleen wat we nodig hebben)
   - Stuur naar ons via [UPLOAD METHODE]
   - Wij filteren de relevante data eruit en verwijderen de rest

**Let op**: Dit bestand kan groot zijn (50-200 MB). Gebruik bij voorkeur WiFi.

### Privacy tips
- Gebruik optie 1 als u alleen relevante data wilt delen
- Gebruik optie 2 als u het makkelijker vindt (wij filteren de data)
- Controleer altijd de bestandsnaam: bevat deze geen naam of persoonlijke info?

---

## Fitbit

### Benodigde data
- Hartslag (Heart Rate)
- Hartslagvariabiliteit (HRV)
- Slaap (Sleep Stages)
- Stappen (Steps)
- Bloedzuurstof (SpO2, indien beschikbaar)
- Stress Score (indien beschikbaar)

### Methode 1: Via Fitbit Dashboard (Web)

1. **Log in op Fitbit.com**:
   - Ga naar https://www.fitbit.com
   - Log in met uw account

2. **Ga naar Data Export**:
   - Klik op uw profielfoto (rechtsboven)
   - Kies "Settings"
   - Scroll naar "Data Export"
   - Of direct naar: https://www.fitbit.com/settings/data/export

3. **Request Data**:
   - Selecteer date range: **Vanaf startdatum onderzoek tot vandaag**
   - Selecteer data types:
     - ✅ Heart Rate
     - ✅ Sleep
     - ✅ Activities
     - ✅ SpO2 (indien beschikbaar)
   - Klik "Request Data"

4. **Download**:
   - Fitbit stuurt een e-mail (kan 1-3 dagen duren)
   - Download het ZIP bestand via de link in de e-mail
   - Extract het ZIP bestand

5. **Delen**:
   - Stuur de volgende bestanden naar ons:
     - `heart_rate-[date].json`
     - `sleep-[date].json`
     - `steps-[date].json`
     - `resting_heart_rate-[date].json`
   - Upload via [UPLOAD METHODE]

### Methode 2: Via FitbitExporter (community tool)

Voor gevorderde gebruikers die vaker willen exporteren.

1. **Download tool**: https://github.com/orcasgit/fitbit-exporter
2. **Volg README instructies** voor installatie
3. **Run export commando**:
   ```bash
   fitbit-exporter --start-date [STARTDATE] --end-date [TODAY]
   ```
4. **Resultaat**: CSV bestanden in output folder
5. **Delen**: Upload alle CSV's via [UPLOAD METHODE]

---

## Garmin

### Benodigde data
- Hartslag (Heart Rate)
- Hartslagvariabiliteit (HRV)
- Slaap (Sleep)
- Stappen (Steps)
- Stress Level
- Body Battery (indien beschikbaar)
- Pulse Ox (SpO2, indien beschikbaar)

### Via Garmin Connect (Web)

1. **Log in op Garmin Connect**:
   - Ga naar https://connect.garmin.com
   - Log in met uw account

2. **Navigeer naar Activities**:
   - Klik op "Activities" in het menu (links)
   - Selecteer "All Activities"

3. **Export per dag** (helaas geen bulk export):
   - Klik op een activiteit
   - Klik op het tandwiel icoon (⚙️) rechtsboven
   - Kies "Export to CSV" of "Export Original"
   - Format: **CSV** (niet TCX of GPX)

4. **Alternatief: Via Health Stats**:
   - Ga naar "Health Stats"
   - Selecteer metric (bijv. "Heart Rate")
   - Klik op het export icoon
   - Download als CSV

### Via Garmin Health API (voor tech-savvy deelnemers)

Als u comfortabel bent met API's en Python:

1. **Download ons script**:
   - [LINK NAAR SCRIPT - TODO]
   - Het script haalt automatisch data op via Garmin API

2. **Installatie**:
   ```bash
   pip install garminconnect
   python garmin_export.py --username [UW USERNAME] --participant-code P[CODE]
   ```

3. **Output**: CSV bestanden in `exports/` folder

4. **Delen**: Upload via [UPLOAD METHODE]

**Let op**: Voor deze methode moet u uw Garmin username/password delen met het script. Het script slaat deze NIET op.

---

## Samsung Galaxy Watch

### Benodigde data
- Hartslag (Heart Rate)
- Slaap (Sleep)
- Stappen (Steps)
- Stress (Stress Level)
- Bloedzuurstof (Blood Oxygen / SpO2)

### Via Samsung Health app

#### Op uw telefoon:

1. **Open Samsung Health app**

2. **Ga naar Menu**:
   - Tap de drie horizontale lijnen (☰) rechtsboven
   - Kies "Settings" (Instellingen)

3. **Download Data**:
   - Scroll naar beneden
   - Tap "Download personal data"
   - Tap "Request data download"

4. **Selecteer data**:
   - ✅ Heart rate
   - ✅ Sleep
   - ✅ Steps
   - ✅ Stress
   - ✅ Blood oxygen
   - ✅ Exercise (optioneel)

5. **Wacht op notificatie**:
   - Samsung Health verstuurt notificatie (1-24 uur)
   - Of check: Settings → Download personal data → "Download list"

6. **Download & delen**:
   - Tap "Download" in de notificatie
   - Bestand wordt opgeslagen in Downloads folder
   - Upload via [UPLOAD METHODE]

**File format**: JSON (wij converteren dit naar CSV)

---

## Andere Smartwatches

Heeft u een ander merk smartwatch (Amazfit, Huawei, Xiaomi, Polar, etc.)?

### Algemene export stappen

1. **Check de companion app**:
   - Bijna alle smartwatches hebben een telefoon app
   - Zoek in de app naar: "Export", "Data", "Settings", "Privacy", "Download data"

2. **Welke data formats zijn OK**:
   - ✅ CSV (beste)
   - ✅ JSON (goed)
   - ✅ XML (acceptabel)
   - ✅ GPX/TCX (voor activiteiten)
   - ❌ Proprietary formats (vraag ons eerst)

3. **Minimum data points**:
   We hebben minstens nodig:
   - Timestamp (datum + tijd)
   - Heart rate (BPM)
   - Optioneel maar gewenst: sleep, steps, stress

4. **Neem contact op**:
   Als u niet weet hoe te exporteren, stuur ons:
   - Merk en model van uw smartwatch
   - Screenshot van de app instellingen
   - Wij helpen u verder!

### Workaround: Screenshot methode
Als export echt niet mogelijk is:

1. Open de app elke dag/week
2. Maak screenshots van:
   - Heart rate graph (met datum/tijd zichtbaar)
   - Sleep summary
   - Daily stats
3. Stuur screenshots via [UPLOAD METHODE]
4. Wij extraheren de data handmatig (minder nauwkeurig, maar beter dan niets)

---

## Spotify Data Export

### Optie 1: Via Spotify Account (AANBEVOLEN)

1. **Log in op Spotify**:
   - Ga naar https://www.spotify.com/account
   - Log in met uw account

2. **Privacy Settings**:
   - Scroll naar "Privacy settings"
   - Klik "Download your data"

3. **Select data**:
   - ✅ **Account data** (voor listening history)
   - ❌ Extended streaming history (niet nodig, te groot)
   - Tap "Request"

4. **Wacht op e-mail**:
   - Spotify stuurt link binnen 30 dagen (meestal binnen 1 week)
   - Download het ZIP bestand

5. **Extract & delen**:
   - Unzip het bestand
   - Stuur deze bestanden:
     - `StreamingHistory0.json`
     - `StreamingHistory1.json` (indien aanwezig)
   - Upload via [UPLOAD METHODE]

### Optie 2: Via Stats for Spotify (third-party)

Voor real-time tracking tijdens onderzoek:

1. **Ga naar**: https://www.statsforspotify.com/
2. **Log in** met Spotify account
3. **Export**: "Download my data" → CSV format
4. **Delen**: Upload via [UPLOAD METHODE]

**Let op**: Deze dienst heeft beperkte history (max 50 tracks).

---

## Data Upload Procedure

### Bestandsnaam conventie
Gebruik ALTIJD deze naming:
```
P[UW CODE]_[DATABRON]_[DATUM].csv

Voorbeelden:
P001_applehealth_2024-01-15.csv
P042_fitbit_2024-01-15.json
P007_spotify_2024-01-15.json
```

### Upload opties

#### Optie A: Email (voor kleine bestanden < 10 MB)
- Stuur naar: [EMAIL ADRES - TODO]
- Subject: "Data Upload - P[UW CODE]"
- Body: vermeld exportdatum en eventuele bijzonderheden

#### Optie B: WeTransfer (voor grote bestanden)
- Ga naar: https://wetransfer.com/
- Upload uw bestanden
- Stuur naar: [EMAIL ADRES]
- Voeg bericht toe met uw deelnemerscode

#### Optie C: [ANDERE METHODE - TODO]
[Wordt ingevuld als jullie een upload portal maken]

---

## Hulp nodig?

### Voordat u vraagt
Controleer:
- [ ] Heb ik de juiste sectie voor mijn smartwatch gelezen?
- [ ] Heb ik de stappen gevolgd?
- [ ] Gebruik ik de juiste bestandsnaam?

### Contact
- **Astrid Verschraege**: astrid.verschraege@hotmail.com
- **Timothy D'hoe**: timothy.dhoe@gmail.com

Vermeld altijd:
- Uw deelnemerscode
- Merk en model smartwatch
- Screenshot van de foutmelding (indien van toepassing)

---

## FAQ

**Q: Moet ik mijn complete health history delen?**  
A: Nee, alleen vanaf de startdatum van het onderzoek.

**Q: Kan ik bepaalde metrics uitsluiten?**  
A: Ja, maar hartslag is verplicht. De rest is optioneel maar helpt ons onderzoek.

**Q: Hoe vaak moet ik exporteren?**  
A: Om de [X] weken. We sturen een herinnering.

**Q: Wat als ik vergeet te exporteren?**  
A: Geen probleem, de data blijft bewaard in uw apparaat. Export gewoon bij de volgende reminder.

**Q: Is mijn data veilig?**  
A: Ja, zie onze [Privacyverklaring](privacy_statement.md) voor details.

**Q: Ik heb geen smartphone, kan ik meedoen?**  
A: Helaas niet, de smartwatch data export vereist een smartphone.

**Q: Mijn smartwatch heeft geen HRV sensor**  
A: Geen probleem, deel wat beschikbaar is. Hartslag alleen is ook OK.

---

**Laatste update**: [DATUM]  
**Volgende review**: [DATUM + 3 maanden]