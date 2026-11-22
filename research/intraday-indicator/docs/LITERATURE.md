# Literatur- und Prior-Art-Recherche

Stand: 2026-11-22. Bibliographische Angaben wurden – soweit hier angegeben – per Websuche
gegen Verlags-, arXiv-, RePEc- oder Repository-Einträge abgeglichen. Wo ein DOI **nicht**
verifiziert werden konnte, steht das ausdrücklich dabei. Es wurden nur Abstracts bzw.
Repository-Zusammenfassungen gelesen, keine vollständigen Volltexte aller Arbeiten; die
"Relevanz"-Spalte gibt deshalb nur die im Abstract belegte Kernaussage wieder.

## 1. Grundlagen, auf denen die Kandidaten aufbauen

| # | Quelle | DOI / URL | Für dieses Projekt relevante Erkenntnis |
|---|---|---|---|
| L1 | Sornette, D., Helmstetter, A. (2003): *Endogenous versus exogenous shocks in systems with memory.* Physica A 318(3–4), 577–591 | 10.1016/S0378-4371(02)01371-7 · arXiv:cond-mat/0206047 | In Systemen mit Langzeitgedächtnis erholen sich **endogene** Schocks (konstruktive Akkumulation vieler kleiner Fluktuationen) anfangs langsamer als **exogene**; das Vorläuferverhalten unterscheidet sich. Theoretische Grundlage von H1. |
| L2 | Sornette, D., Malevergne, Y., Muzy, J.-F. (2002): *Volatility fingerprints of large shocks: Endogeneous versus exogeneous.* | arXiv:cond-mat/0204626 | Auf Tagesdaten: Unterscheidungsmerkmal ist die Relaxation der Volatilität zum Mittelwert (log-Volatilitäts-Prozess mit Langzeitgedächtnis). Wenige Ereignisse, ex-post-Klassifikation. |
| L3 | Johansen, A., Sornette, D. (2002/2010): *Endogenous versus Exogenous Crashes in Financial Markets.* | arXiv:cond-mat/0210509 | Endogene Crashs haben Vorläufer, exogene folgen starken externen Störungen. |
| L4 | Marcaccioli, R., Bouchaud, J.-P., Benzaquen, M. (2022): *Exogenous and endogenous price jumps belong to different dynamical classes.* J. Stat. Mech. | 10.1088/1742-5468/ac498c · arXiv:2106.07040 | **Wichtigste Prior-Art für H1.** 300 Aktien, 5 Jahre Orderbuch + News: exogene Sprünge abrupt mit Potenzgesetz-Abklingen, endogene mit progressiv beschleunigtem Volatilitätsanstieg. Klassifikation über Anpassung von Potenzgesetzen an das **gesamte** (auch nachfolgende) Volatilitätsprofil, d. h. ex post. |
| L5 | Lillo, F., Mantegna, R. N. (2003): *Power-law relaxation in a complex system: Omori law after a financial market crash.* Phys. Rev. E 68, 016119 | 10.1103/PhysRevE.68.016119 | Anzahl der Schwellenüberschreitungen nach einem Crash fällt nach einem Potenzgesetz (Omori); mit einfachen stochastischen Volatilitätsmodellen nicht erklärbar. |
| L6 | Petersen, A. M., Wang, F., Havlin, S., Stanley, H. E. (2010): *Market dynamics immediately before and after financial shocks: quantifying the Omori, productivity and Bath laws.* Phys. Rev. E 82, 036114 | arXiv:1006.1882 | 219 Marktschocks, 1-Min-Daten: quantitative Beziehungen zwischen Schockgröße und Abklingparametern (Omori, Produktivität, Båth). |
| L7 | Filimonov, V., Sornette, D. (2012): *Quantifying reflexivity in financial markets: towards a prediction of flash crashes.* Phys. Rev. E 85, 056108 | 10.1103/PhysRevE.85.056108 | Hawkes-Verzweigungsrate als Maß der Endogenität. |
| L8 | Hardiman, S. J., Bercot, N., Bouchaud, J.-P. (2013): *Critical reflexivity in financial markets: a Hawkes process analysis.* | arXiv:1302.1405 | Widerspruch zu L7: Märkte durchgehend nahe Kritikalität; Ergebnis hängt an Kernel-/Fensterwahl. Mahnung zur Vorsicht bei Endogenitätsmaßen. |
| L9 | Bacry, E., Mastromatteo, I., Muzy, J.-F. (2015): *Hawkes processes in finance.* | 10.48550/arXiv.1502.04592 | Übersicht Selbsterregung in Mikrostruktur-Daten. |
| L10 | Scheffer, M. et al. (2009): *Early-warning signals for critical transitions.* Nature 461, 53–59 | 10.1038/nature08227 | Kritische Verlangsamung: steigende Autokorrelation und Varianz vor Kipppunkten. Grundlage von H2. |
| L11 | Diks, C., Hommes, C., Wang, J. (2019): *Critical slowing down as an early warning signal for financial crises?* Empirical Economics 57(4), 1201–1228 | 10.1007/s00181-018-1527-3 | Evidenz nur vor 1987, gemischt/insignifikant für spätere Krisen; Finanzdynamik nicht zwingend ODE-artig. Dämpft a-priori-Erwartung an H2. |
| L12 | Corsi, F. (2009): *A simple approximate long-memory model of realized volatility.* J. Financial Econometrics 7(2), 174–196 | 10.1093/jjfinec/nbp001 | HAR-Modell – unsere zentrale Vergleichs-Baseline. |
| L13 | Andersen, T. G., Bollerslev, T. (1997): *Intraday periodicity and volatility persistence in financial markets.* J. Empirical Finance 4(2–3), 115–158 | 10.1016/S0927-5398(97)00004-2 | Tageszeit-Periodizität verzerrt Intraday-Dynamik massiv → kausale Tageszeit-Normalisierung ist Pflicht. |
| L14 | Tauchen, G., Pitts, M. (1983): *The price variability-volume relationship on speculative markets.* Econometrica 51(2), 485–506 | Legacy-DOI laut Econometric Society (nicht aufgelöst geprüft) | Mixture-of-Distributions-Hypothese: Volumen und Volatilität teilen einen latenten Informationsfluss → Volumen gehört in die Baseline. |
| L15 | Andersen, T. G. (1996): *Return volatility and trading volume: an information flow interpretation of stochastic volatility.* J. Finance 51(1), 169–204 | DOI nicht verifiziert | Modifizierte MDH; Volumen als Volatilitätsinformation. |
| L16 | Llorente, G., Michaely, R., Saar, G., Wang, J. (2002): *Dynamic volume-return relation of individual stocks.* RFS 15(4), 1005–1047 | NBER-WP-DOI 10.3386/w8312 (Journal-DOI nicht verifiziert) | Volumen-bedingte Rendite-Autokorrelation (Hedging vs. spekulativ). Prior-Art für richtungsbezogene Volumen-Ideen, daher verworfen. |
| L17 | Abdi, F., Ranaldo, A. (2017): *A simple estimation of bid-ask spreads from daily close, high, and low prices.* RFS 30(12), 4437–4480 | 10.1093/rfs/hhx084 | OHLC-basierte Spread-Schätzer existieren bereits → "Friktions-Kandidat" wäre keine neue Information. |

## 2. Methodik der Validierung

| # | Quelle | DOI / URL | Verwendung |
|---|---|---|---|
| M1 | Diebold, F. X., Mariano, R. S. (1995): *Comparing predictive accuracy.* JBES 13(3), 253–263 | DOI nicht verifiziert (vermutl. 10.1080/07350015.1995.10524599) | Verlustdifferenzen-Test mit HAC-Varianz. |
| M2 | Giacomini, R., White, H. (2006): *Tests of conditional predictive ability.* Econometrica 74(6), 1545–1578 | 10.1111/j.1468-0262.2006.00718.x | Begründet Test der Prognose*methode* (inkl. Schätzunsicherheit) im rollierenden OOS-Design – passt zu unserem Walk-Forward-Vergleich. |
| M3 | Patton, A. J. (2011): *Volatility forecast comparison using imperfect volatility proxies.* J. Econometrics 160(1), 246–256 | 10.1016/j.jeconom.2010.03.034 | Verlustfunktionen bei verrauschten Volatilitätsproxys. Wir umgehen das Problem, indem das Prognoseziel selbst eine beobachtbare Größe ist (log. Range-Summe), nicht latente Volatilität. |
| M4 | Bailey, D. H., Borwein, J., López de Prado, M., Zhu, Q. J. (2017): *The probability of backtest overfitting.* J. Computational Finance 20(4) | 10.21314/JCF.2016.322 | Data-Snooping-Bewusstsein; Begründung, Parameter a priori festzulegen und Raster vollständig zu berichten. |

## 3. Prior-Art im TradingView-/Retail-Umfeld (Neuheitsprüfung)

Per Websuche gefundene öffentliche TradingView-Skripte (nur Beschreibungstexte gelesen, Code nicht geprüft):

* **"Omori Law Recovery Phases"** (Open Source, tradingview.com/script/cUuEL8Wk) – wendet Omori-Abklingen beschreibend auf Crash-Erholung an (Phaseneinteilung).
* **"Volatility Shock Half-Life Monitor"** – zählt Bars, bis Überschuss-Volatilität nach einem Schock abgeklungen ist (beobachtete Halbwertszeit, nicht prognostisch).
* **"Volatility Shock Memory Curve [Pineify]"** – exponentiell geglättetes Abklingen eines True-Range-Schocks; Beschreibung betont selbst, keine Risikoprognose zu liefern.

**Konsequenz:** "Schock-Gedächtnis" bzw. Omori-artiges Abklingen ist auf TradingView **nicht neu** (beschreibend vorhanden). Ebenso sind kritische Verlangsamung (rollierende Autokorrelation), Volumen-Volatilitäts-Beziehung, Hawkes-Intensitäten und OHLC-Spreadschätzer bekannt. Was wir in keiner gefundenen Quelle gesehen haben, ist die Kombination aus
(a) einer **kausalen** Endo/Exo-Klassifikation im Moment des Schocks allein aus dem Vorlauf,
(b) einer **online kalibrierten Wahrscheinlichkeit** für Folgeschocks und
(c) einem **Out-of-Sample-Nachweis des Zusatznutzens gegenüber HAR + Volumen + etablierten Indikatoren**.
Weltweite Neuheit wird ausdrücklich **nicht** beansprucht; die Suche war auf Websuche beschränkt (kein Zugriff auf kommerzielle Indikatorbibliotheken, kein Volltextzugang zu allen Arbeiten).
