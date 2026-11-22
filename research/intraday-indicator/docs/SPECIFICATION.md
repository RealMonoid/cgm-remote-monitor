# Mathematische Spezifikation – „Activity Persistence“ (APX)

Status: **experimentell**. Die Spezifikation wurde am 2026-11-22 *vor* der Holdout-Auswertung
eingefroren (`validation/final_spec.py`, `results/frozen_coefficients.json`).

## 1. Beantwortete Frage

> Wie groß wird die summierte High-Low-Spanne der nächsten *H* Bars relativ zu dem, was zu
> dieser Tageszeit normal ist – und ist die **aktuelle** Aktivität eher *abrupt eingetroffen*
> (→ klingt schneller ab) oder *allmählich aufgebaut* (→ hält länger an)?

Die Größe ist **richtungsneutral**. Sie sagt nichts über Long/Short.

## 2. Eingabedaten

Nur OHLCV der Chart-Zeitreihe sowie (für Charts ≥ 2 min) die 1-Minuten-Bars innerhalb jeder
Chart-Bar über `request.security_lower_tf`. Kein Orderbuch, keine Ticks, keine externen Dienste.

Notation: Bar *t* mit Open $o_t$, High $h_t$, Low $l_t$, Close $c_t$, Volumen $v_t$; Tageszeit-
Bucket $\tau(t)=\lfloor(\text{Minute des Tages UTC})/\Delta\rfloor$ bei Bar-Länge Δ Minuten;
$N_d = 1440/\Delta$ Bars pro Tag.

## 3. Bausteine (alle kausal: nur Bars ≤ t)

| Symbol | Definition | Kommentar |
|---|---|---|
| $\rho_t$ | $\log(h_t/l_t)$ | Log-Spanne der Bar |
| $\varepsilon_t$ | $0.1\cdot \bar\rho_{t-1}$, $\bar\rho$ = EWMA von ρ mit Gewicht $1/(5N_d)$ | Boden gegen Null-Spannen |
| $\ell_t$ | $\log(\rho_t+\varepsilon_t)$ | |
| $d_{\tau,t}$ | EWMA von $\ell$ **pro Tageszeit-Bucket**, Gewicht α = 1/20 pro Tag, Wert *vor* Einbezug von Bar t | kausales Tageszeitprofil (Andersen & Bollerslev 1997) |
| $x_t$ | $\ell_t-d_{\tau(t),t}$ | Log-Spanne relativ zur Tageszeit-Norm |
| $\sigma_t$ | $\exp(d_{\tau(t),t})$ | typische Bar-Spanne zu dieser Tageszeit |
| $u_t$ | analog mit $\log(v_t+0.01\bar v_{t-1})$ | Volumen-Überraschung |
| $z_t$ | $\log(c_t/c_{t-1})/\sigma_t$ (bei Session-Lücke $\log(c_t/o_t)$) | normierte Rendite |

## 4. Prognoseziel (Target)

$$y_t=\log\frac{\sum_{k=1}^{H}\rho_{t+k}+H\varepsilon_t}{\sum_{k=1}^{H}\sigma_{t+k}}$$

$\sigma_{t+k}$ ist das Profil des Buckets $\tau(t+k)$, das zuletzt einen Tag früher (< t)
aktualisiert wurde (H < Bars pro Tag). $y_t$ ist erst am Schluss von Bar $t+H$ bekannt und
wird **erst dann** zum Lernen benutzt. 0 bedeutet „normal für diese Tageszeit“, +0.69 = 2×.

## 5. BASE-Merkmale (bekannte Information)

HAR-Gedächtnis $x_t,\ \bar x^{(6)}_t,\ \bar x^{(48)}_t,\ \bar x^{(288)}_t$ (gleitende Mittel über
6/48/288 Bars) · $\overline{|z|}^{(6)}_t$ · $\bar u^{(6)}_t,\ \bar u^{(48)}_t$ ·
Tail-Shape: $\mathrm{sd}_{120}(x)$, $\max_{48}(x)$, Anzahl Schocks in 288 Bars ·
Schock-Gedächtnis (Omori-artig, Prior-Art): $\mathbb 1_{\text{live}}$, $M\cdot w(a)$ ·
Intrabar-Pfad (nur Δ ≥ 2): $\pi_t=\log\big(\sum_i \rho^{(1m)}_{t,i}/\rho_t\big)$ und $\bar\pi^{(6)}_t$.

**Schock:** $s_t=x_t-\overline{x}^{(48)}_{t-1} > \log 4$. Episode: $a = t - t_0 \le 48$ Bars nach dem
letzten Schock $t_0$; Gedächtniskern $w(a)=(1+a)^{-1/2}$ (a priori, nicht angepasst);
$M=s_{t_0}$.

## 6. Die neue Komponente: Abruptheit der Aktivitätsankunft

Hypothese H*: *Abrupt eingetroffene Aktivität ist transient; allmählich aufgebaute Aktivität ist
persistent* (Sornette & Helmstetter 2003: endogene vs. exogene Schocks in Systemen mit
Gedächtnis). Zwei kausale Operationalisierungen auf zwei Skalen:

1. **Intrabar-Volumenkonzentration** (Δ ≥ 2 min):
   $$\kappa_t=\log\Big(n_t\,\frac{\sum_i v_{t,i}^2}{(\sum_i v_{t,i})^2}\Big)\in[0,\log n_t]$$
   0 = Volumen gleichmäßig über die n 1-Min-Bars verteilt; $\log n_t$ = alles in einer Minute.
   Dazu $\bar\kappa^{(6)}_t$.
2. **Vorlauf-Aufbau vor einem Schock** (alle Δ):
   $$B_{t_0}=\bar x^{(12)}_{t_0-1}-\bar x^{(276)}_{t_0-13}$$
   B > 0: Aktivität stieg *vor* dem Schock bereits an („endogen-artig“); B ≤ 0: Schock kam
   aus der Ruhe („exogen-artig“). Merkmale während der Episode: $B\,w(a)$ und $B M w(a)$.

**Abruptheits-Anpassung** mit eingefrorenen Koeffizienten (pro Standardabweichung):

$$\delta_t=\sum_j \beta_j\, \tilde f_{j,t}$$

| Δ | κ | κ̄⁽⁶⁾ | B·w | B·M·w |
|---|---|---|---|---|
| 1 min | – | – | +0.0496 | −0.0244 |
| 5 min | −0.0046 | −0.0280 | +0.0432 | −0.0314 |
| 15 min | −0.0087 | −0.0362 | +0.0086 | −0.0038 |

Vorzeichen wie von H* vorhergesagt: Konzentration < 0, Aufbau > 0. Geschätzt per gepoolter
OLS auf den Entwicklungsdaten (5 Kryptowerte, 2023-01 bis 2025-10), mit derselben Online-
Standardisierung wie in Pine ($\tilde f$ = EWMA-standardisiert, Gewicht 1/2000, auf ±6 gekappt,
Statistik *vor* Einbezug der aktuellen Bar). Andere Timeframes verwenden den nächstgelegenen
Satz und werden als „nicht untersucht“ markiert.

## 7. Modell in TradingView

* **BASE:** exponentiell gewichtete Ridge-Regression (Vergessensfaktor λ = 0.9995, effektives
  Gedächtnis ≈ 2000 gereifte Targets):
  $A_t=\lambda A_{t-1}+\tilde f\tilde f^\top,\ b_t=\lambda b_{t-1}+\tilde f\,y,\
  \hat\theta_t=(A_t+\rho D)^{-1}b_t$, ρ = 20 (= 1 % des effektiven Stichprobenumfangs, a priori),
  D = diag(0,1,…,1). Update an Bar t mit $(\tilde f^{BASE}_{t-H}, y_{t-H})$; Ausgabe erst nach
  500 gereiften Targets.
  *Implementierungshistorie (nach Holdout-Läufen, transparent dokumentiert):*
  v1 = gewöhnliches RLS mit Vergessen → divergierte in langen Replays („covariance wind-up“,
  `results/holdout_deployed_v1_windup_bug.csv`); v2 = RLS mit spurbegrenztem Vergessen →
  divergierte weiterhin auf 1/5 min wegen Schlechtkonditionierung bei kollinearen Merkmalen
  (`results/holdout_deployed_v2_rls_illconditioned.csv`); v3 = Ridge (diese Version).
  Hypothese, Merkmale und eingefrorene δ-Koeffizienten blieben bei allen Korrekturen
  unverändert; betroffen war nur der Schätzer der bekannten Baseline.
* **FULL** $=\widehat{y}^{BASE}_t+\delta_t$.
* **Selbstprüfung:** laufende (EWMA 1/2000) Out-of-Sample-MSE von FULL und BASE, berechnet nur aus
  Prognosen, die gespeichert wurden, *bevor* ihr Target existierte; angezeigt als Skill
  $1-\text{MSE}_{FULL}/\text{MSE}_{BASE}$.

Rechenaufwand: O(15²) pro Bar + Schleife über ≤ 15 Intrabars; Speicher: 49 × 15-Ringpuffer.

## 8. Repainting-/Lookahead-Verhalten

* Alle persistenten Zustände (Profile, Standardisierung, RLS, Schockzustand) werden nur bei
  `barstate.isconfirmed` aktualisiert.
* Auf der unbestätigten Echtzeit-Bar werden Werte als **provisorisch** (Kreise) gezeichnet; sie
  verwenden die bisher gebildeten Intrabars und können sich bis zum Bar-Schluss ändern. Die
  bestätigte Linie ändert sich nachträglich nie.
* Alerts feuern nur auf bestätigten Bars.
* Python-Nachweis: `validation/test_causality.py` (Merkmale auf gekürzten Historien identisch).

## 9. Interpretation (was die Zahl bedeutet – und was nicht)

* `FULL = 0.41` → erwartete Summe der Spannen der nächsten H Bars ≈ exp(0.41) ≈ 1.5× Tageszeit-Norm
  (geometrische Erwartung, kein Mittelwert).
* `δ < 0` bei erhöhter Aktivität: das Modell erwartet *schnelleres Abklingen* als die
  bekannte Information allein. `δ > 0`: *längeres Anhalten*.
* Die Größe von δ liegt typischerweise bei ±0.02–0.08 Log-Einheiten (±2–8 %). Sie ist eine
  **kleine Korrektur**, keine Handelsampel.
