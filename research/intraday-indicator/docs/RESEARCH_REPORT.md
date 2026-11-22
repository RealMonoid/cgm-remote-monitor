# Forschungsbericht: Gibt es aus OHLCV ableitbare, zusätzliche Intraday-Entscheidungsinformation?

Datum: 2026-11-22 · Status des Ergebnisses: **experimentell** · Kein nachgewiesener Handelsvorteil.

---

## 0. Zusammenfassung für Eilige

1. **Vier substanziell verschiedene Kandidaten** wurden vorab definiert und mit identischer
   Walk-Forward-Methodik gegen starke Baselines (HAR-Spannengedächtnis, Volumen, ATR/RSI,
   Effizienz, später zusätzlich Vol-of-Vol/Extremwerte/Schockzählung) getestet –
   5 Krypto-Assets × 1/5/15 min × 34 Monate (≈ 1,5 Mio. 1-Min-Bars je Asset) plus eine
   kurze Zusatzstichprobe aus Aktien-ETFs, Futures, Gold und FX.
2. **Richtung und „Trendhaftigkeit“ (künftige Effizienz) waren mit keinem Kandidaten und keiner
   Baseline prognostizierbar.** Die einzige richtungsbezogene Idee (Cross-Asset-Lead-Lag)
   liefert 0–5 bp brutto je Trade und ist nach 10 bp Kosten überall negativ.
3. **Kritische Verlangsamung (H2)** wirkte zunächst stark, war aber vollständig durch
   Vol-of-Vol erklärbar – eine bekannte Größe. Verworfen.
4. Übrig blieb eine **theoriegeleitete, kleine, aber replizierte** Regelmäßigkeit:
   **„Abrupt eintreffende Aktivität klingt schneller ab als allmählich aufgebaute.“**
   Operationalisiert auf zwei Skalen (Intrabar-Volumenkonzentration; Vorlauf-Aufbau vor
   Schocks), Vorzeichen auf allen Assets wie theoretisch vorhergesagt.
5. Nach **Einfrieren der Spezifikation** wurde auf unberührten Daten getestet
   (2025-11…2026-10 sowie 5 nie betrachtete Assets): Batch-Walk-Forward **19/30 Tests
   Holm-signifikant, 29/30 Punktschätzer positiv**, Effektgröße +0.1 % bis +1.3 % MSE-Skill.
6. Als **TradingView-Indikator, wie er tatsächlich läuft** (online gelernte Baseline +
   eingefrorene Abruptheits-Korrektur), ist der Gewinn **kleiner**: +0.09 % (1 min), +0.39 %
   (5 min); auf 15 min **negativ** (−0.62 %) → dort abgeschaltet.
7. Ökonomische Relevanz: unbewiesen. Ein Prognosegewinn von < 1 % MSE auf die künftige
   Spanne ist statistisch real, aber für einzelne Trades kaum spürbar.

---

## 1. Forschungsfrage und Erkenntnisgrenze

Gesucht war eine *eigenständige* Größe, die über Kurs-, Volumen- und Standardindikator-
Information hinaus entscheidungsrelevant ist. Da jede deterministische Transformation von
OHLCV keine neue Rohinformation erzeugt, wurde „Neuheit“ operationalisiert als:
**bedingter Out-of-Sample-Prognosegewinn gegenüber einer starken Baseline aus bekannten
Merkmalen**, gemessen auf einem *entscheidungsrelevanten* Ziel.

Primäre Prognoseziele (alle kausal definiert, `validation/features.py`):

| Ziel | Definition | Entscheidungsbezug |
|---|---|---|
| `y_vol` | log(Σ Spannen der nächsten H = 12 Bars / Tageszeit-Norm) | Stop-Weite, Positionsgröße, „lohnt sich ein Trade nach Kosten?“ |
| `y_volL` | dto. mit H = 48 | längerer Haltehorizont |
| `y_tail` | Tritt in den nächsten 12 Bars eine Schock-Bar auf (Spanne > 4× lokales Niveau)? | Vermeidung von Einstiegen vor Turbulenz |
| `y_eff` | \|Netto-Bewegung\| / √(Σ r²) über 12 Bars | Trend- vs. Range-Regime (Wahl der Strategieart) |
| `y_ret` | Richtung/Größe der 12-Bar-Rendite | Richtungshandel |

---

## 2. Literatur und Prior-Art

Siehe `docs/LITERATURE.md` (17 Grundlagen-, 4 Methodikquellen, DOIs mit Verifikationsstatus).
Wichtigste Befunde für die Auswahl:

* **Endogene vs. exogene Schocks** (Sornette & Helmstetter 2003; Sornette, Malevergne &
  Muzy 2002; Marcaccioli, Bouchaud & Benzaquen 2022): exogene Schocks setzen abrupt ein und
  klingen schnell ab, endogene bauen sich auf und relaxieren langsamer. Die bisherigen
  Arbeiten klassifizieren **ex post** (anhand des ganzen Profils oder mit News-Daten).
* **Omori-Abklingen** (Lillo & Mantegna 2003; Petersen et al. 2010) ist etabliert; auf
  TradingView existieren beschreibende Skripte („Omori Law Recovery Phases“, „Volatility
  Shock Half-Life Monitor“, „Volatility Shock Memory Curve“) → **Schock-Gedächtnis gilt hier
  als bekannte Information**, nicht als Neuheit.
* **Kritische Verlangsamung** (Scheffer et al. 2009) wurde für Finanzkrisen nur schwach
  bestätigt (Diks, Hommes & Wang 2019).
* **HAR** (Corsi 2009) und Tageszeit-Normalisierung (Andersen & Bollerslev 1997) sind
  Pflicht-Baselines; Volumen ist laut MDH (Tauchen & Pitts 1983) bekannte Volatilitäts-
  information und gehört in die Baseline.

Nicht gefunden (Websuche, kein Vollzugriff auf kommerzielle Bibliotheken): eine **kausale**,
zum Schockzeitpunkt verfügbare Endo/Exo-Klassifikation aus OHLCV bzw. eine Intrabar-
Volumenkonzentrations-Größe mit nachgewiesenem Zusatznutzen gegenüber HAR. Weltweite
Neuheit wird **nicht** beansprucht.

---

## 3. Kandidaten (vor jeder Auswertung festgelegt)

| | H1 Endo/Exo-Fingerabdruck | H2 Kritische Verlangsamung | H3 Cross-Asset-Systemanteil | H4 Intrabar-Struktur |
|---|---|---|---|---|
| Phänomen | Relaxation nach Schocks hängt davon ab, ob Aktivität sich vorher aufbaute | Steigende Autokorrelation/Varianz vor Regimewechsel | Anteil der Bewegung, der durch den Leitmarkt (BTC) erklärt ist; idiosynkratische Abweichungen | Wie Volumen und Pfad *innerhalb* einer Bar verteilt sind |
| Theorie | Sornette & Helmstetter 2003 | Scheffer et al. 2009 | Faktormodelle, Lead-Lag | MDH / Endo-Exo auf Intrabar-Skala |
| Daten | OHLC | OHLC | OHLC zweier Märkte (`request.security`) | 1-Min-Intrabars (`request.security_lower_tf`) |
| Bekannte Verfahren | Omori-Abklingen, HAR | rollierende AC, Vol-of-Vol | Beta/Korrelation, Pairs | Realized Volatility, Volumenprofile |
| Originäre Komponente | Kausale Vorlauf-Größe B zum Schockzeitpunkt | AR(1)-Trend der Log-Spanne | Systemanteil R² als Zustandsgröße | Volumen-Konzentration κ |
| Hypothese | B > 0 → höhere Folgevolatilität als Baseline | ρ↑ → Schock-/Vol-Anstieg | idiosynkr. Schock → Reversion/andere Vol | κ hoch → schnelleres Abklingen |
| Scheitern, wenn | kein OOS-Gewinn ggü. Baseline + Schock-Gedächtnis | Gewinn verschwindet bei Vol-of-Vol-Kontrolle | kein Gewinn ggü. Richtungs-Baseline / nach Kosten | Gewinn durch Pfad (bekannte RV-Logik) erklärt |
| Pine-kausal | ja | ja | ja | ja (nur abgeschlossene Intrabars) |

Bewertung a priori (1–5): Originalität H1 4, H2 2, H3 2, H4 3; Plausibilität H1 4, H2 2,
H3 3, H4 3; Interpretierbarkeit H1 4, H2 3, H3 4, H4 4. Rechenaufwand bei allen gering.

---

## 4. Methodik

* **Kausalität:** `test_causality.py` berechnet alle Merkmale auf gekürzten Historien neu –
  max. Abweichung 0.0 für 1/5/15 min (31–35 Merkmale). Tageszeit-Profile werden pro Bucket
  nur mit früheren Tagen geschätzt.
* **Walk-Forward:** monatliche Folds, expandierendes Training, **Purge von 48 Bars** vor jedem
  Testmonat (überlappende Zielhorizonte), Standardisierung nur auf Trainingsdaten.
* **Tests:** Verlustdifferenz pro Kalendertag gemittelt, **Newey-West-t** (HAC, 5 Lags) auf
  der Tagesreihe (Diebold-Mariano-artig; Giacomini-White-Logik: Methode inkl. Schätzfehler).
  Skill = 1 − MSE_Kandidat/MSE_Baseline. **Holm-Korrektur** über die Primärfamilie.
* **Parameter** a priori fixiert (`features.P`), kein Tuning; Raster werden vollständig
  berichtet (§7.4).
* **Daten:** Binance-Spot 1m (öffentliches Archiv), BTC/ETH/SOL/XRP/BNB 2023-01…2025-10
  (Entwicklung). Yahoo 5m (60 Tage) für SPY/QQQ/IWM/ES/NQ/GC/CL/EURUSD (Zusatz).

---

## 5. Ergebnisse der explorativen Hauptstudie (Entwicklungsdaten)

Mittlerer OOS-Skill gegenüber `KNOWN` (HAR + Volumen + ATR-Ratio + |RSI−50| + Effizienz +
Leverage-Term), 5 Assets (`results/study_results.csv`):

| Ziel / Kandidat | 1 min | 5 min | 15 min |
|---|---|---|---|
| HAR vs. Konstante (`y_vol`) | +72.7 % | +66.7 % | +59.9 % |
| KNOWN vs. HAR (`y_vol`) | +6.1 % | +3.5 % | +2.0 % |
| **y_eff: irgendein Modell** | ≈ 0 | ≈ 0 | ≈ 0 |
| **y_ret: Richtungsmodelle** | ≈ 0 | ≈ 0 | ≈ 0 |
| H2 (`y_tail`) | +2.2 % (5/5 sig.) | +0.7 % | +0.4 % |
| H1 Schock-Gedächtnis (`y_vol`) | +1.0 % | +0.4 % | +0.15 % |
| H1 Endo-Komponente (`y_vol`, Episoden) | +0.7 % (5/5) | +0.2 % | −0.2 % |
| H3 (`y_vol`) | +0.15 % | +0.1 % | ≈ 0 |
| H4 (`y_vol`) | – | +0.8 % (4/5) | +1.0 % (5/5) |
| Yahoo-Stichprobe (alle) | – | negativ | – |

Richtung (Kosten, `results/direction_trading.csv`): bestes Signal 0–5 bp brutto pro Trade,
**netto bei 10 bp Round-Trip überall negativ**; bei 2 bp (Maker) einzelne Werte leicht
positiv, aber t < 2.

Yahoo: Mit nur 3–4 Testwochen verlieren sogar die *bekannten* Merkmale gegen HAR
(Schätzrauschen). Die Stichprobe ist für Aussagen über Zusatzinformation **zu klein**.

### 5.1 Ablation – was steckt wirklich dahinter? (`ablation_5m.csv`, `ablation_15m.csv`)

* **H2 zerfällt:** Der gesamte H2-Effekt kommt aus `var_x` (Varianz der Log-Spanne =
  Vol-of-Vol). Die eigentlichen CSD-Größen (ρ_x, Δρ, ρ_r) liefern ≤ 0. Mit einer
  „Tail-Shape“-Baseline (Vol-of-Vol, 48-Bar-Max, Schockzählung) bleibt von H2 nichts übrig
  (5 min `y_vol`: −0.07 %). **H2 verworfen** – einfachere Erklärung: bekannte Streuung der
  Volatilität erhöht mechanisch die Schockwahrscheinlichkeit.
* **H4 zerfällt in zwei Teile:** Intrabar-Pfad (`path`, Summe der 1-Min-Spannen / Bar-Spanne)
  ist eine feinere Aktivitätsmessung (bekannte RV-Logik → Baseline). Die **Volumen-
  konzentration κ** liefert *zusätzlich* zum Pfad +0.75 % (5 min) bzw. +0.85 % (15 min),
  5/5 Assets signifikant (`focus_tests.csv`). Vorzeichen auf allen Assets **negativ**.
* **H1:** Gegen die stärkste Baseline (KNOWN + Tail-Shape + Schock-Gedächtnis) liefert die
  Endo-Komponente B auf 1 min +0.22 % (alle Zeilen) bzw. **+0.57 % in Schock-Episoden**,
  5/5 Assets signifikant; auf 5/15 min ≈ 0.
* **H3:** klein, inkonsistent; richtungsbezogen nach Kosten negativ. Verworfen.

### 5.2 Mechanismus-Test (a priori: Vorzeichen von B, `focus_mechanism.csv`)

Mittleres OOS-Residuum der Baseline *inklusive* Schock-Gedächtnis, Alter 4–12 Bars:

| | 1 min aufgebaut (B>0) | 1 min abrupt (B≤0) | 5 min aufgebaut | 5 min abrupt |
|---|---|---|---|---|
| Mittel | +0.036 | −0.018 | +0.037 | −0.028 |
| Spanne über 5 Assets | [+0.020, +0.042] | [−0.051, −0.005] | [+0.033, +0.040] | [−0.054, −0.003] |

Das Vorzeichen stimmt **auf jedem Asset** mit der Theorie überein: abrupte Schocks klingen
schneller ab, aufgebaute langsamer, als die Baseline erwartet. Auf 15 min ist das Muster
schwächer und uneinheitlich.

### 5.3 Synthese und Auswahl

H1-Endo und H4-κ messen dasselbe theoretische Konstrukt – die **zeitliche Konzentration der
Aktivitätsankunft** – auf zwei Skalen, mit theoriekonformen Vorzeichen (Konzentration −,
Aufbau +). Ausgewählt wurde daher die vereinigte Hypothese **H\***: *abrupt eintreffende
Aktivität ist transient*. Die Auswahl erfolgte **nach** Sichtung der Entwicklungsergebnisse
(Selektion!) → zwingend separater Holdout.

---

## 6. Eingefrorene Spezifikation und Holdout

Am 2026-11-22 vor jedem Holdout-Zugriff fixiert (`final_spec.py`, Koeffizienten aus
Entwicklungsdaten in `frozen_coefficients.json`; Details `SPECIFICATION.md`).
Holdout: (a) **2025-11…2026-10** für die 5 Entwicklungs-Assets (12 neue Monate);
(b) **DOGE, ADA, LTC, LINK, AVAX** (nie betrachtet), 2023-01…2026-10.

### 6.1 Primärtest (Batch-Walk-Forward FULL vs. BASE, `y_vol`, Holm über 30 Tests)

BASE = HAR + Volumen + Tail-Shape + Schock-Gedächtnis (+ Intrabar-Pfad ab 5 min);
FULL = BASE + κ, κ̄⁽⁶⁾ (ab 5 min) + B·w, B·M·w. (`results/holdout_tests.csv`)

| | 1 min | 5 min | 15 min |
|---|---|---|---|
| Entwicklungs-Assets, neuer Zeitraum | **5/5** sig., +0.18…+0.39 % | **5/5**, +0.77…+1.19 % | 3/5, +0.36…+1.34 % |
| Neue Assets | 2/5, −0.05…+0.19 % | 2/5, +0.02…+1.13 % | 2/5, +0.12…+1.01 % |

→ **Zeitliche Replikation: stark. Replikation über Assets: schwach** (ADA, AVAX, LINK ≈ 0).
`y_volL` (sekundär): durchweg positiv bei den Entwicklungs-Assets, ≈ 0 bei neuen Assets.

### 6.2 Der Indikator, wie er wirklich läuft (`results/holdout_deployed.csv`)

Python-Replik der Pine-Arithmetik, online ab 30 Tagen vor Holdout-Beginn; BASE = online
gelernte Ridge-Regression; FULL = BASE + eingefrorenes δ.

| BASE + δ vs. BASE | 1 min | 5 min | 15 min |
|---|---|---|---|
| mittlerer Skill | +0.09 % | +0.39 % | **−0.62 %** |
| Assets > 0 | 7/10 | 9/10 | 1/10 |
| einzeln sig. (5 %, einseitig) | 4/10 | 1/10 | 0/10 |
| Stouffer-z (überschätzt, Assets korreliert) | +3.3 | +2.3 | −3.2 |
| zum Vergleich: alles online lernen | −0.08 % | +0.10 % | −0.04 % |

Konsequenz: **δ auf Charts ≥ 10 min abgeschaltet** (konservative Entfernung einer im
Holdout gescheiterten Komponente). Die Online-BASE selbst schlägt eine Konstante auf allen
30 Reihen um 53–72 % (bekannte Information, nicht neu).

**Implementierungshistorie (offen gelegt):** Die erste Python-Replik (gewöhnliches RLS mit
Vergessen, wie im ersten Pine-Entwurf) divergierte in den 12-Monats-Replays
(„covariance wind-up“), eine zweite (spurbegrenzt) wegen Schlechtkonditionierung. Erst die
Ridge-Version (v3, ρ a priori 1 % des effektiven Stichprobenumfangs) ist stabil. Betroffen
war nur der Baseline-Schätzer; Hypothese, Merkmale und δ-Koeffizienten blieben unverändert.
Beide fehlerhaften Läufe liegen in `results/holdout_deployed_v1_*.csv`, `…_v2_*.csv`.

### 6.3 Live-Prüfung auf TradingView (Einzelschnappschüsse, 2026-11-22)

Mit dem TradingView-Rechenserver ausgeführt (`run_pine_indicator`), aktuelle Daten:

* BINANCE:BTCUSDT 5m, 19 435 gelernte Targets: laufender OOS-Skill FULL vs. BASE **+1.28 %**.
* CME_MINI:ES1! 5m (RTH, *nicht untersuchte Assetklasse*): **+0.88 %** (frühere Version).
* BINANCE:ETHUSDT 15m: δ aus → Skill 0 (FULL = BASE).
* Verworfener Logistik-Prototyp auf BTC 5m: **−0.87 %** (deckt sich mit §7.2).

Der „laufende Skill“ ist ein EWMA über ≈ 2000 Prognosen (~1 Woche auf 5 min) – einzelne
Schnappschüsse sind **anekdotisch**.

### 6.4 Pine-vs-Python-Parität (`results/parity/`)

Auf 150 identischen BTC-5m-Bars (TradingView-Server vs. Binance-Archiv): Bar-Spanne und κ
stimmen bis auf Rundung überein (max. 5·10⁻⁵); x (tageszeitnormiert) korreliert zu 0.9986
(Abweichung durch unterschiedlichen Historienbeginn des Tageszeitprofils).

---

## 7. Kritische Begutachtung (Rolle: skeptischer Gutachter)

### 7.1 Ist das Signal originär?
*Teilweise.* Das Phänomen (endo vs. exo) ist **nicht neu** (L1–L4). Neu ist allenfalls die
kausale OHLCV-Operationalisierung (B zum Schockzeitpunkt, κ innerhalb der Bar) mit OOS-
Nachweis gegen eine starke Baseline. κ ist mathematisch ein normierter Herfindahl-Index der
Intrabar-Volumina – eine einfache Größe; ihre *Verwendung als Persistenzindikator* fanden
wir nicht, können aber Prior-Art nicht ausschließen.

### 7.2 Liefert es Zusatzinformation gegenüber Rohdaten und Vergleichsmodellen?
Ja, aber **klein**: +0.2 % bis +1.2 % MSE-Skill im Batch-Holdout. Zum Vergleich: HAR allein
erklärt 60–73 %, die bekannten Zusatzmerkmale weitere 2–6 %. Die neue Komponente ist eine
Korrektur zweiter Ordnung.

### 7.3 Verschwindet der Effekt außerhalb der Entwicklungsstichprobe?
Zeitlich **nein** (12 neue Monate, 13/15 Holm-signifikant). Über Assets **teilweise**
(6/15). Über Assetklassen **unbekannt** (Yahoo-Stichprobe zu kurz; ES-Schnappschuss
anekdotisch). Als laufender Indikator: auf 15 min **ja** (negativ) → abgeschaltet.

### 7.4 Hängt der Effekt an Parametern?
Raster auf 5 min, 5 Entwicklungs-Assets, alle Werte berichtet (`results/robustness_5m.csv`),
Skill auf `y_vol`:

| Parameter | Wert | Schock-Gedächtnis vs. KNOWN | Endo-Komponente B (alle Zeilen) | B (nur Episoden) |
|---|---|---|---|---|
| Schockschwelle | log 3 | +0.46 % (5/5 > 0) | +0.09 % (5/5) | +0.29 % (5/5) |
| | **log 4** (a priori) | +0.42 % (5/5) | +0.03 % (5/5) | +0.16 % (3/5) |
| | log 5 | +0.37 % (5/5) | −0.02 % (1/5) | −0.27 % (2/5) |
| Vorlauffenster | 6 | – | +0.04 % (5/5) | +0.16 % (3/5) |
| | **12** | – | +0.03 % (5/5) | +0.16 % (3/5) |
| | 24 | – | −0.01 % (2/5) | −0.03 % (2/5) |
| Abklingexponent | 0.3 / **0.5** / 1.0 | +0.37 / +0.42 / +0.39 % | +0.03 / +0.03 / +0.02 % | +0.15 / +0.16 / +0.11 % |

Bewertung: Das (bekannte) Schock-Gedächtnis ist **parameterrobust**. Die Endo-Komponente B
ist auf 5 min **klein und parameterabhängig** (verschwindet bei seltenen Schocks bzw. langem
Vorlauffenster) – ein Warnsignal; ihre stärkere Evidenz liegt auf 1 min (dort kein Raster
gerechnet: Rechenzeit). Die κ-Komponente hat außer dem 6-Bar-Mittel keine Parameter. Die
extremen negativen `y_tail`-Werte bei log 5 sind Konvergenzfehler der Logistik bei seltenen
Ereignissen, keine Information.

### 7.5 Versteckte Informationslecks?
Geprüft: Merkmals-Kausalität (Trunkierungstest), Tageszeitprofil nur aus Vortagen, Purge
48 Bars, Standardisierung nur auf Training, Online-Modell lernt Target t−H erst bei t.
Restrisiko: Die *Auswahl* von H\* erfolgte nach Sichtung der Entwicklungsdaten – deshalb
der Holdout. Die beiden Implementierungskorrekturen der Baseline erfolgten nach Holdout-
Läufen; sie betreffen nicht δ, sind aber Freiheitsgrade des Forschers (offengelegt). Das
Abschalten von δ ab 10 min ist ebenfalls eine Holdout-informierte Entscheidung (nur
konservativ: Entfernen, nicht Hinzufügen).

### 7.6 Handelbar oder Artefakt?
Statistisch kein Artefakt (Replikation über Zeit, theoriekonforme Vorzeichen auf jedem
Asset). Aber: Es handelt sich um eine Prognose der **Spanne**, nicht der Richtung. Ein
Handelsvorteil entsteht nur indirekt (Sizing, Stops, Trade-Auswahl) und wurde **nicht**
gemessen. Kosten betreffen die Prognose nicht direkt; ob +0.4 % MSE-Skill nach Kosten
ökonomisch etwas ändert, ist offen und eher unwahrscheinlich als wahrscheinlich.

### 7.7 Nur ein Markt?
Nur liquide Krypto-Spotmärkte sind belastbar untersucht. Auf Krypto 24/7 gibt es keine
Session-Struktur; auf Aktienindizes könnten Eröffnung/Schluss das Bild dominieren.

### 7.8 Ist die Komplexität gerechtfertigt?
Die neue Komponente ist **einfach** (κ: ein Herfindahl-Index; B: Differenz zweier
Mittelwerte). Die Komplexität des Indikators steckt in der *Baseline* (Tageszeit-
Normalisierung, Online-Ridge) – sie ist nötig, damit δ fair beurteilt werden kann, und sie
macht die Selbstprüfung möglich.

### 7.9 Einfachere Erklärungen?
* Für H2: ja (Vol-of-Vol) → verworfen.
* Für κ: Konzentriertes Volumen könnte einfach große Einzelorders/Liquidationen anzeigen,
  deren Preiswirkung transient ist (Mikrostruktur-Erklärung). Das ist mit H\* vereinbar,
  aber nicht identisch mit „exogen“ – wir können News-Exogenität **nicht** beobachten.
* Für B: Mean-Reversion der Volatilität ist in HAR bereits enthalten; B wirkt zusätzlich nur
  innerhalb von Episoden – eine Nichtlinearität, die lineares HAR nicht abbildet.

### 7.10 Urteil
**Experimentell.** Eine interessante, theoretisch fundierte und zeitlich replizierte
Regelmäßigkeit mit sehr kleiner Effektgröße; als laufender Indikator nur auf 1–5 min
schwach positiv; Assetklassen-Übertragbarkeit offen; kein nachgewiesener Handelsvorteil.

---

## 8. Anwendungsfälle (hypothetisch – nicht empirisch als Vorteil belegt)

| Situation | Was der Indikator zeigt | Mögliche andere Entscheidung | Status |
|---|---|---|---|
| Volatilitätsspitze, κ hoch (Volumen in 1–2 Minuten konzentriert), δ < 0 | FULL < BASE: Aktivität dürfte schneller abklingen | Engere Stops nach Beruhigung früher wieder zulassen; Range-Strategie früher reaktivieren | Prognosegewinn belegt (klein), Handelsnutzen hypothetisch |
| Schock nach bereits steigender Aktivität (B > 0), δ > 0 | FULL > BASE: Turbulenz hält länger an | Positionsgröße länger reduziert halten, breitere Stops, keine frühe Gegenbewegung handeln | dto. |
| Ruhige Phase, FULL ≈ 0 | normale Tageszeit-Aktivität erwartet | Kosten/erwartete Spanne prüfen: Lohnt sich ein Scalp überhaupt? | Baseline-Information (bekannt), nicht neu |
| Tabelle zeigt „OOS skill ≤ 0“ | Komponente hilft auf diesem Markt derzeit nicht | δ ignorieren, nur BASE nutzen | Selbstprüfung |

Ausdrücklich **nicht** möglich: Richtung, Einstiegssignale, Aussagen über Käufer/Verkäufer.

---

## 9. Was offen bleibt

1. Assetklassen außerhalb Krypto mit ausreichend langen 1-Min-Historien (Aktienindizes,
   FX, Rohstoffe) – nicht verfügbar in dieser Umgebung (Dukascopy rate-limitiert,
   Yahoo nur 60 Tage).
2. Ökonomische Bewertung über einen definierten Entscheidungsprozess (z. B. Volatilitäts-
   Targeting mit Kosten).
3. Ein zweistufiges δ (auf Residuen der *online* BASE geschätzt) könnte das 15-min-Problem
   beheben – müsste aber auf **neuen** Daten validiert werden.
4. Feinere Intrabar-Daten (Sekunden) auf 1-min-Charts.
5. TradingView-Grenze: Intrabar-Historie ist begrenzt (15m-Chart: ≈ 6 600 Bars mit
   1-Min-Daten), daher lernt die BASE auf höheren Timeframes mit weniger Daten.
