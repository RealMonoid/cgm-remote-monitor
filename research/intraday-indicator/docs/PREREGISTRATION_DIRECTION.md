# Präregistrierung: Richtungs-Hypothesen (Kauf-/Verkaufssignale)

Festgelegt am 2026-11-22, **bevor** irgendeine der unten genannten Richtungsregeln auf
irgendeinem Datensatz ausgewertet wurde. Dieses Dokument wird vor dem ersten Lauf committet;
nachträgliche Änderungen müssen als solche gekennzeichnet werden.

## 1. Gemeinsame Definitionen (unverändert aus `features.py`, nicht neu getunt)

* **Ereignis = Schock-Bar** an Bar t: $x_t-\bar x^{(48)}_{t-1} > \log 4$ (Spanne > 4× lokales,
  tageszeitbereinigtes Niveau). Richtung $d_t=\operatorname{sign}(r_t)$, $r_t$ = Log-Rendite
  der Bar; Ereignisse mit $r_t=0$ entfallen.
* **Einstieg** zum Schlusskurs der Schock-Bar (Signal ist erst dann bestätigt), **Ausstieg**
  nach H = 12 Bars zum Schlusskurs. Keine Stops, keine Ziele (reiner Informationstest).
* **Nicht überlappend:** Nach einem Einstieg werden Ereignisse in den nächsten 12 Bars
  ignoriert (pro Asset und Regel).
* **Kosten (Round-Trip):** primär **10 bp** (≈ Futures-Taker 2×0,05 %), optimistisch 4 bp
  (Maker), pessimistisch 20 bp (Spot-Taker). Slippage ist darin enthalten zu denken; Spread
  wird nicht separat modelliert (OHLCV enthält ihn nicht).
* **Schwellen** (Mediane/Terzile) werden ausschließlich aus Ereignissen **vor** dem jeweiligen
  Testmonat geschätzt (expandierend, Start nach 3 Monaten).
* Zeiteinheiten: 1, 5, 15 min.

## 2. Kandidaten

**Baseline U (unbedingte Schock-Reaktion):** immer folgen (+d) bzw. immer ausfaden (−d).
Ein Kandidat muss U im selben Datensatz schlagen, sonst ist seine Bedingung wertlos.

**C1 – Abruptheit → Umkehr, Aufbau → Fortsetzung** (Sornette & Helmstetter 2003;
Aubrun et al. 2024 unterscheiden umkehrende und trendende Sprünge).
abrupt: B ≤ 0 und (tf = 1 oder κ ≥ Median κ früherer Schocks) → Position −d;
aufgebaut: B > 0 und (tf = 1 oder κ < Median) → Position +d; sonst keine.

**C2 – Volumen-bedingte Schock-Reaktion** (Campbell, Grossman & Wang 1993; Bianchi et al.
2022: in Krypto stärkere Umkehr bei niedrigem Volumen). Volumenüberraschung u der Schock-Bar:
unteres Terzil → −d (dünne Bewegung wird ausgefadet); oberes Terzil → +d; Mitte: keine.

**C3 – Verzögerte Übertragung eines BTC-Schocks auf Altcoins** (Lead-Lag-Literatur).
Nur Nicht-BTC-Assets, Leitmarkt BTCUSDT gleicher Zeiteinheit. Ereignis = Schock-Bar in BTC;
$e_t=r_{A,t}-\hat\beta r_{B,t}$ ($\hat\beta$ aus 240 Bars bis t−1). Falls $d_B\,e_t<0$ (der
Altcoin ist BTC noch nicht voll gefolgt): Position $d_B$ im Altcoin; sonst keine.

## 3. Daten und Stufen (jede Stufe genau einmal)

| Stufe | Daten | Zweck |
|---|---|---|
| DEV | BTC/ETH/SOL/XRP/BNB, 2023-01…2025-10 | Entdeckung (für Richtung bisher nie ausgewertet) |
| A | dieselben 5 Assets 2025-11…2026-10 + DOGE/ADA/LTC/LINK/AVAX 2023-01…2026-10 | Bestätigung (Daten für Volatilität bereits genutzt, für Richtung nie) |
| B | dieselben 5 Assets **2021-01…2022-12** + TRX/DOT/ATOM/BCH/NEAR 2023-01…2026-10 | **finaler, völlig unberührter Holdout** |

## 4. Erfolgs- und Abbruchkriterien

Ein Kandidat × Zeiteinheit **besteht** nur, wenn ALLE Punkte erfüllt sind:
1. DEV: mittlerer Netto-Ertrag pro Trade bei **10 bp** > 0 mit einseitigem t > 2
   (Tagesblöcke, Newey-West) **nach Holm-Korrektur über 9 Tests** (3 Kandidaten × 3 TF);
2. DEV: brutto signifikant besser als die beste Variante von Baseline U;
3. A: Netto (10 bp) gepoolt > 0 **und** ≥ 60 % der Assets netto > 0;
4. B: dasselbe wie 3, einmalig ausgewertet.

Nur Kandidaten, die 1–2 bestehen, gehen in A; nur die, die A bestehen, in B.
**Abbruch:** Besteht kein Kandidat, wird **kein** Kauf-/Verkaufssignal als validiert
ausgeliefert; das Ergebnis wird als offenes Forschungsproblem dokumentiert. Es gibt keine
zweite Kandidatenrunde auf denselben Holdout-Daten.

## 5. Was ausdrücklich nicht passiert

Kein Nachjustieren von H, Schockschwelle, Terzilgrenzen oder Kosten nach Sicht auf Ergebnisse;
keine Stops/Targets-Optimierung; keine Auswahl von Assets nach Ergebnis.
