"""Bar-by-bar replica of the online probability model used inside the Pine indicator.

The Pine script cannot be fitted offline per market, so it learns online:
  * features are standardised with slow EWMA means/variances (causal),
  * a logistic model is updated by a recursive Newton / extended-Kalman step,
  * the label of bar t-H (shock within bars t-H+1..t) becomes known only at the close of
    bar t, so the update at bar t uses (features[t-H], label[t-H]). Prediction at bar t uses
    the parameters available at the close of bar t. No label is used before it has matured.

This module re-implements exactly that arithmetic so the TradingView output can be
validated offline (and cross-checked against run_pine_indicator output).
"""
import numpy as np


def online_logit(X, y, H, lam=0.9995, std_alpha=1 / 2000, p0=1.0, warm=500, trace_bound=True):
    """X: (n,k) raw features; y: (n,) labels in {0,1} (NaN = unknown); returns p (n,)."""
    n, k = X.shape
    th = np.zeros(k + 1)
    P = np.eye(k + 1) * p0
    mu = np.zeros(k)
    var = np.ones(k)
    init = False
    out = np.full(n, np.nan)
    Z = np.full((n, k + 1), np.nan)           # standardised features as used at time t
    seen = 0
    for t in range(n):
        xt = X[t]
        ok = np.all(np.isfinite(xt))
        if ok:
            if not init:
                mu[:] = xt
                init = True
            # standardise with statistics BEFORE including x_t
            z = np.r_[1.0, np.clip((xt - mu) / np.sqrt(var + 1e-12), -6, 6)]
            Z[t] = z
            d = xt - mu
            mu += std_alpha * d
            var = (1 - std_alpha) * (var + std_alpha * d * d)
        # learn from the matured label of bar t-H
        j = t - H
        if j >= 0 and np.isfinite(y[j]) and np.all(np.isfinite(Z[j])):
            zj = Z[j]
            p = 1 / (1 + np.exp(-np.clip(zj @ th, -30, 30)))
            v = max(p * (1 - p), 1e-4)
            if not trace_bound or np.trace(P) < p0 * (k + 1):   # trace-bounded forgetting
                P /= lam
            Pz = P @ zj
            P -= np.outer(Pz, Pz) * (v / (1 + v * (zj @ Pz)))
            th += P @ zj * (y[j] - p)
            seen += 1
        if ok and seen >= warm:
            out[t] = 1 / (1 + np.exp(-np.clip(Z[t] @ th, -30, 30)))
    return out


def online_ols(X, y, H, lam=0.9995, std_alpha=1 / 2000, p0=100.0, warm=500, trace_bound=True):
    """Recursive least squares with forgetting, same maturing-label discipline.

    trace_bound=True: P is divided by lam only while trace(P) < p0*(k+1) (its initial value).
    Without it, directions that are rarely excited (e.g. mostly-zero episode features) wind
    up as lam^-n and the filter eventually explodes ("covariance wind-up"). The first holdout
    run (results/holdout_deployed_v1_windup_bug.csv) used trace_bound=False and diverged.
    """
    n, k = X.shape
    th = np.zeros(k + 1)
    P = np.eye(k + 1) * p0
    mu = np.zeros(k); var = np.ones(k); init = False
    out = np.full(n, np.nan); Z = np.full((n, k + 1), np.nan); seen = 0
    for t in range(n):
        xt = X[t]
        if np.all(np.isfinite(xt)):
            if not init:
                mu[:] = xt; init = True
            z = np.r_[1.0, np.clip((xt - mu) / np.sqrt(var + 1e-12), -6, 6)]
            Z[t] = z
            d = xt - mu; mu += std_alpha * d; var = (1 - std_alpha) * (var + std_alpha * d * d)
        j = t - H
        if j >= 0 and np.isfinite(y[j]) and np.all(np.isfinite(Z[j])):
            zj = Z[j]
            if not trace_bound or np.trace(P) < p0 * (k + 1):
                P /= lam
            Pz = P @ zj
            g = Pz / (1 + zj @ Pz)
            th += g * (y[j] - zj @ th)
            P -= np.outer(g, Pz)
            seen += 1
        if np.all(np.isfinite(Z[t])) and seen >= warm:
            out[t] = Z[t] @ th
    return out


def online_ridge(X, y, H, lam=0.9995, std_alpha=1 / 2000, rho=20.0, warm=500):
    """Exponentially weighted recursive RIDGE regression (deployed BASE estimator, v3).

    A_t = lam*A_{t-1} + z z',  b_t = lam*b_{t-1} + z y,  theta = (A + rho*D)^-1 b,
    D = diag(0, 1, ..., 1) (intercept not penalised). rho = 20 = 1 % of the effective sample
    1/(1-lam) = 2000 (fixed a priori). Unlike plain RLS with forgetting (v1/v2), theta stays
    bounded under collinear or rarely excited features. Same maturing-label discipline.
    """
    n, k = X.shape
    A = np.zeros((k + 1, k + 1)); b = np.zeros(k + 1)
    D = np.eye(k + 1); D[0, 0] = 1e-6
    mu = np.zeros(k); var = np.ones(k); init = False
    out = np.full(n, np.nan); Z = np.full((n, k + 1), np.nan); seen = 0
    th = np.zeros(k + 1)
    for t in range(n):
        xt = X[t]
        if np.all(np.isfinite(xt)):
            if not init:
                mu[:] = xt; init = True
            Z[t] = np.r_[1.0, np.clip((xt - mu) / np.sqrt(var + 1e-12), -6, 6)]
            d = xt - mu; mu += std_alpha * d; var = (1 - std_alpha) * (var + std_alpha * d * d)
        j = t - H
        if j >= 0 and np.isfinite(y[j]) and np.all(np.isfinite(Z[j])):
            zj = Z[j]
            A *= lam; b *= lam
            A += np.outer(zj, zj); b += zj * y[j]
            seen += 1
            th = np.linalg.solve(A + rho * D, b)
        if np.all(np.isfinite(Z[t])) and seen >= warm:
            out[t] = Z[t] @ th
    return out
