# Intraday-Forschungsprojekt: „Activity Persistence“ (APX)

> **Runde 2 (Diagnose für Kauf-/Verkaufssignale):** APX liefert **keine** Richtungsinformation
> (Trefferquote 50 %). Drei präregistrierte neue Richtungs-Hypothesen sind bereits in der
> Entwicklungsstufe nach Kosten gescheitert. **Entscheidung: Verwerfung als Signalgeber; kein
> Signalindikator ausgeliefert.** Details: `docs/DIAGNOSIS_FTA.md`.

**Status: experimentell. Kein nachgewiesener Handelsvorteil.**
Das Projekt untersucht, ob sich aus OHLCV-Daten eine bislang wenig genutzte, entscheidungs-
relevante Information über kurzfristige Marktaktivität gewinnen lässt, und setzt den am
besten belegten Ansatz als TradingView-Indikator (Pine Script v6) um.

Kurzfassung des Ergebnisses: Die einzige Hypothese, die mehrere skeptische Tests überstanden
hat, lautet **„abrupt eintreffende Aktivität klingt schneller ab als allmählich aufgebaute“**.
Ihr Informationsbeitrag ist **klein** (≈ 0.2–1 % MSE-Skill auf die Prognose der künftigen
Spanne, zusätzlich zu einer starken Baseline) und **richtungsneutral**. Richtung und
„Trendhaftigkeit“ waren mit keinem Kandidaten prognostizierbar. Details: `docs/RESEARCH_REPORT.md`.

## Verzeichnis

| Pfad | Inhalt |
|---|---|
| `docs/RESEARCH_REPORT.md` | Forschungsbericht: Kandidaten, Auswahl, Ergebnisse, Holdout, kritische Bewertung, Anwendungsfälle |
| `docs/SPECIFICATION.md` | Mathematische Spezifikation des Indikators |
| `docs/DIAGNOSIS_FTA.md` | Runde 2: forensische Diagnose, Fehlerbaum, Richtungstests, Entscheidung |
| `docs/PREREGISTRATION_DIRECTION.md` | Vorab festgelegte Richtungs-Hypothesen und Abbruchkriterien |
| `docs/LITERATURE.md` | Literatur- und Prior-Art-Recherche (mit DOIs, Verifikationsstatus) |
| `pine/ActivityPersistence.pine` | **Finaler Indikator** (Pine v6, kompiliert und auf TradingView ausgeführt) |
| `pine/archive/AftershockHazard.pine` | Verworfener erster Prototyp (dokumentiert, nicht verwenden) |
| `validation/` | Reproduzierbare Python-Pipeline (s. u.) |
| `results/` | Ergebnistabellen (CSV/JSON) aller Läufe |

## Reproduktion

Voraussetzungen: Python ≥ 3.11, `pip install numpy pandas scipy pyarrow`.

```bash
cd research/intraday-indicator
# 1) Daten (Binance-Spot 1m, öffentliches Archiv data.binance.vision; ~1.5 Mio. Bars/Asset)
python validation/download_binance.py --symbols BTCUSDT ETHUSDT SOLUSDT XRPUSDT BNBUSDT --start 2023-01 --end 2025-10 --out data
python validation/download_binance.py --symbols BTCUSDT ETHUSDT SOLUSDT XRPUSDT BNBUSDT --start 2025-11 --end 2026-10 --out data/holdout
python validation/download_binance.py --symbols DOGEUSDT ADAUSDT LTCUSDT LINKUSDT AVAXUSDT --start 2023-01 --end 2026-10 --out data/newassets
python validation/download_yahoo.py --symbols SPY QQQ IWM ES=F NQ=F GC=F CL=F EURUSD=X --out data   # kurze Zusatzstichprobe
cd validation
# 2) Kausalitätstest (keine Zukunftsdaten in Merkmalen)
python test_causality.py ../data/BTCUSDT_1m.parquet
# 3) Explorative Hauptstudie (4 Kandidaten, 3 Timeframes, Walk-Forward, Holm)
python run_study.py --workers 3
# 4) Ablationen / Teilperioden / Folgetests
python ablation.py --tfs 5 15 --skip-grid
python focus_h1_h4.py
python eval_online.py          # verworfener Logistik-Prototyp, wie auf dem Chart betrieben
# 5) Eingefrorene Spezifikation: Koeffizienten (nur Entwicklungsdaten) und Holdout
python holdout.py fit
python holdout.py test
# 6) Runde 2: Diagnose und präregistrierte Richtungsstudie
python download_binance.py --symbols BTCUSDT ETHUSDT SOLUSDT XRPUSDT BNBUSDT --start 2021-01 --end 2022-12 --out ../data/early
python download_binance.py --symbols TRXUSDT DOTUSDT ATOMUSDT BCHUSDT NEARUSDT --start 2023-01 --end 2026-10 --out ../data/fresh
python diagnose_apx.py
python direction_study.py --stage DEV
# 7) Parameter-Robustheit
python ablation.py --skip-ablation --grid-tf 5 --grid-params shock_theta pre_short decay_p --grid-out robustness_5m.csv
```

Laufzeit auf 4 Kernen: insgesamt einige Stunden (1-Minuten-Reihen dominieren). Alle Parameter
sind in `validation/features.py` (`P`) und `validation/final_spec.py` fixiert.

## Indikator verwenden

1. `pine/ActivityPersistence.pine` in den Pine-Editor kopieren, speichern, zum Chart hinzufügen.
2. Getestete Timeframes: 1, 5, 15 Minuten. Für 5/15 min werden 1-Min-Intrabars benötigt.
3. Die Tabelle zeigt **„running OOS MSE skill FULL vs BASE“** – die laufend auf *diesem* Chart
   gemessene Verbesserung durch die neue Komponente. Ist sie ≤ 0, liefert die Komponente auf
   diesem Markt derzeit keinen Mehrwert.
4. Mindestens 500 gereifte Targets sind nötig, bevor Prognosen erscheinen.

## Was ausdrücklich NICHT behauptet wird

* kein Kauf-/Verkaufssignal, keine Richtungsprognose, keine Profitabilität;
* keine Aussage über Orderflow oder „Smart Money“ – κ misst nur, wie gleichmäßig das *Volumen*
  der 1-Min-Bars innerhalb der Bar verteilt war;
* Gültigkeit außerhalb liquider Krypto-Spotmärkte ist nicht belegt (nur Einzelstichproben).
