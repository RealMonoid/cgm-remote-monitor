"""FROZEN final specification (written BEFORE touching the holdout data).

Frozen on 2026-11-22 after the exploratory study on 2023-01..2025-10 for BTC/ETH/SOL/XRP/BNB.
The holdout consists of (a) 2025-11..2026-10 for the same five assets and (b) five assets
never examined before (DOGE/ADA/LTC/LINK/AVAX, full period). Nothing below may be changed
after looking at holdout results; changes would have to be reported as new exploration.

Hypothesis (H*): "Abruptly arriving activity is transient." Conditional on the strong
baseline (HAR + volume + tail shape + shock memory + intrabar path), features describing the
TEMPORAL CONCENTRATION of activity improve the forecast of the next-H-bar range relative
to its time-of-day norm (y_vol). Predicted signs: intrabar volume concentration (conc) < 0,
pre-shock build-up (B) > 0.

Primary test family (one-sided, Holm-corrected): y_vol, FULL vs BASE, batch walk-forward,
for every (asset, timeframe) in the holdout. Secondary: y_volL; deployed online model.
"""
import numpy as np
import pandas as pd

TAIL = ["vov", "xmax48", "nshock288"]
BASE_CORE = ["x", "m6", "m48", "m288", "zabs6", "u6", "u48"] + TAIL + ["h1_live", "h1_M"]
PATH = ["h4_path", "h4_path6"]           # intrabar path excess (finer activity measurement)
ABR_INTRA = ["h4_conc", "h4_conc6"]      # intrabar volume concentration (abruptness)
ABR_INTER = ["h1_B", "h1_BM"]            # pre-shock build-up (abruptness, inter-bar)


def add_tail(F):
    x = F["x"]
    F["vov"] = x.rolling(120).std()
    F["xmax48"] = x.rolling(48).max()
    F["nshock288"] = F["shock"].rolling(288).sum()
    return F


def base_cols(tf):
    return BASE_CORE + (PATH if tf > 1 else [])


def abr_cols(tf):
    return (ABR_INTRA if tf > 1 else []) + ABR_INTER


def full_cols(tf):
    return base_cols(tf) + abr_cols(tf)


def ewma_standardise(X, alpha=1 / 2000, clip=6.0):
    """Exactly the Pine standardisation: statistics BEFORE including the current row."""
    X = np.asarray(X, float)
    n, k = X.shape
    Z = np.full((n, k), np.nan)
    mu = np.full(k, np.nan)
    var = np.ones(k)
    for t in range(n):
        xt = X[t]
        if not np.all(np.isfinite(xt)):
            continue
        first = np.isnan(mu)
        z = np.where(first, 0.0, (xt - np.nan_to_num(mu)) / np.sqrt(var + 1e-12))
        Z[t] = np.clip(z, -clip, clip)
        d = xt - np.nan_to_num(mu)
        mu = np.where(first, xt, mu + alpha * d)
        var = np.where(first, var, (1 - alpha) * (var + alpha * d * d))
    return Z
