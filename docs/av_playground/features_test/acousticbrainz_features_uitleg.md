🎧 1. Spectral features
Deze beschrijven de vorm van het geluidsspectrum — dus hoe de energie verdeeld is over lage vs. hoge frequenties.
🎵 spectral_centroid.mean
•	“zwaartepunt” van het geluid
•	lage waarde → warm, bas rijk, mellow
•	hoge waarde → helder, scherp, veel hoge tonen
Interpretatie:
•	hoge centroid → hi hats, akoestische gitaren, pop
•	lage centroid → bas, ambient, ballads
🎵 spectral_spread.mean
•	hoe breed het spectrum is
•	hoge waarde → veel variatie in frequenties
•	lage waarde → smal, gefocust geluid
Interpretatie:
•	hoge spread → rock, elektronische muziek
•	lage spread → solo instrumenten, rustige tracks
🎵 spectral_skewness / spectral_kurtosis
Dit zijn statistieken over de vorm van het spectrum.
•	skewness: of het spectrum meer naar lage of hoge frequenties helt
•	kurtosis: hoe “piekerig” het spectrum is
Interpretatie:
•	hoge skewness → veel hoge tonen
•	lage skewness → veel lage tonen
•	hoge kurtosis → scherpe pieken (bijv. percussie)
•	lage kurtosis → vlakker geluid
🎧 2. MFCC features (mfcc.mean[x])
MFCC’s zijn de standaard in audio analyse.
Ze vatten het volledige spectrum samen in 13 getallen.
Wat betekenen ze?
•	MFCC’s zijn een soort compacte handtekening van de klankkleur
•	MFCC 0 → globale energie
•	MFCC 1–3 → vorm van de lage frequenties
•	MFCC 4–13 → fijnere details van de klank
Interpretatie:
Je hoeft MFCC’s niet “inhoudelijk” te interpreteren zoals spectral centroid.
Ze zijn vooral:
•	extreem informatief voor clustering
•	robuust
•	ideaal voor PCA
•	goed voor similarity search
Ze gedragen zich als een embedding van de klankkleur.
🎧 3. dynamic_complexity
Dit is een Essentia feature die aangeeft:
•	hoe complex de dynamiek is
•	hoeveel variatie er zit in volume en energie
Interpretatie:
•	hoge waarde → veel dynamische variatie (rock, live muziek, orkest)
•	lage waarde → vlakke dynamiek (lofi, ambient, elektronische muziek)
🎧 4. key_key en key_scale
Dit zijn de muzikale toonaarden:
•	key_key → C, D, E, F#, …
•	key_scale → major / minor
In jouw dataset staan ze vaak op "unknown" omdat AcousticBrainz deze niet altijd detecteert.
Interpretatie:
•	minor → vaak melancholischer
•	major → vaak vrolijker
Maar:
→ in jouw dataset is dit vooral metadata, niet een sterke feature.
🎛️ 5. Wat betekenen de genormaliseerde waarden (Z scores)?
Je ziet nu waarden zoals:
-0.32 1.76 0.08 -1.20 
Dat betekent:
•	0 = gemiddelde waarde over alle tracks
•	positief = boven het gemiddelde
•	negatief = onder het gemiddelde
•	grootte = hoe ver van het gemiddelde (in standaarddeviaties)
Voorbeeld:
spectral_centroid.mean = 1.76
→ deze track is heel helder vergeleken met de rest
mfcc.mean[3] = -0.95
→ deze track heeft minder energie in dat MFCC gebied dan gemiddeld

