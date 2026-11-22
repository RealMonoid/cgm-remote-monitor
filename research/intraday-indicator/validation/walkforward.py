"""Walk-forward out-of-sample evaluation with purging, and robust comparison tests.

Design
------
* Folds: calendar months (crypto) or calendar weeks (short Yahoo samples).
* Training set for fold k: all rows strictly before the fold start (expanding window),
  minus a purge zone of `purge` bars before the fold start, because those rows have
  targets that overlap the test period. Rows inside the test fold are never used to fit.
* Feature standardisation is fitted on the training set only.
* Models: OLS (continuous targets) and logistic regression (binary target).
* Comparison: per-row loss differential d_t = L_base - L_cand on OOS rows. Because
  forecast horizons overlap, rows are NOT independent; we average d_t per calendar day
  and use a Newey-West (HAC) t-statistic on the daily series (Diebold-Mariano style).
"""
import numpy as np
import pandas as pd


def _fit_ols(X, y):
    X1 = np.column_stack([np.ones(len(X)), X])
    # small ridge for numerical stability only (lambda negligible vs n)
    A = X1.T @ X1 + 1e-6 * np.eye(X1.shape[1])
    return np.linalg.solve(A, X1.T @ y)


def _pred_ols(b, X):
    return b[0] + X @ b[1:]


def _fit_logit(X, y, iters=25):
    """Plain Newton-Raphson logistic regression with tiny L2 (deterministic, fast)."""
    X1 = np.column_stack([np.ones(len(X)), X])
    b = np.zeros(X1.shape[1])
    pbar = np.clip(y.mean(), 1e-4, 1 - 1e-4)
    b[0] = np.log(pbar / (1 - pbar))
    lam = 1e-4 * len(y)
    for _ in range(iters):
        eta = np.clip(X1 @ b, -30, 30)
        p = 1 / (1 + np.exp(-eta))
        g = X1.T @ (y - p) - lam * np.r_[0, b[1:]]
        Wd = p * (1 - p)
        Hm = (X1 * Wd[:, None]).T @ X1 + lam * np.diag(np.r_[0, np.ones(len(b) - 1)])
        step = np.linalg.solve(Hm, g)
        b += step
        if np.max(np.abs(step)) < 1e-7:
            break
    return b


def _pred_logit(b, X):
    eta = np.clip(b[0] + X @ b[1:], -30, 30)
    return 1 / (1 + np.exp(-eta))


def folds(index, freq="M", min_train_folds=3):
    per = index.to_period(freq) if freq != "W" else index.to_period("W")
    uniq = per.unique()
    for k in range(min_train_folds, len(uniq)):
        yield uniq[k], (per == uniq[k])


def walk_forward(F, target, feature_sets, kind="ols", freq="M", purge=12,
                 min_train_folds=3, max_train=None, rows_mask=None):
    """Return DataFrame of OOS predictions, one column per feature set.

    feature_sets: dict name -> list of columns ([] = intercept only)
    rows_mask: optional boolean array; if given, models are fitted AND evaluated only on
               these rows (used for the event-conditional H1 analysis).
    """
    cols = sorted({c for fs in feature_sets.values() for c in fs})
    need = cols + [target]
    ok = F[need].notna().all(axis=1).to_numpy()
    if rows_mask is not None:
        ok = ok & np.asarray(rows_mask)
    D = F.loc[ok, need]
    idx = D.index
    pos = np.arange(len(F))[ok]                 # original bar positions (for purging)
    preds = {name: np.full(len(idx), np.nan) for name in feature_sets}
    fold_lab = np.array([""] * len(idx), dtype=object)
    y_all = D[target].to_numpy()
    Xall = {name: D[fs].to_numpy() for name, fs in feature_sets.items() if fs}
    per = idx.to_period(freq)
    uniq = per.unique()
    for k in range(min_train_folds, len(uniq)):
        te = np.asarray(per == uniq[k])
        if te.sum() == 0:
            continue
        first_pos = pos[te].min()
        tr = (pos < first_pos - purge)
        if max_train is not None and tr.sum() > max_train:   # deterministic thinning
            tr_idx = np.flatnonzero(tr)
            tr = np.zeros_like(tr)
            tr[tr_idx[:: int(np.ceil(len(tr_idx) / max_train))]] = True
        if tr.sum() < 500:
            continue
        fold_lab[te] = str(uniq[k])
        for name, fs in feature_sets.items():
            if fs:
                Xtr = Xall[name][tr]
                mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-12
                Xtr = (Xtr - mu) / sd
                Xte = (Xall[name][te] - mu) / sd
            else:
                Xtr = np.zeros((tr.sum(), 0))
                Xte = np.zeros((te.sum(), 0))
            if kind == "ols":
                preds[name][te] = _pred_ols(_fit_ols(Xtr, y_all[tr]), Xte)
            else:
                preds[name][te] = _pred_logit(_fit_logit(Xtr, y_all[tr]), Xte)
    out = pd.DataFrame(preds, index=idx)
    out["y"] = y_all
    out["fold"] = fold_lab
    return out[out["fold"] != ""]


# ----------------------------------------------------------------------------------
# Losses and tests
# ----------------------------------------------------------------------------------
def loss(pred, y, kind):
    if kind == "ols":
        return (y - pred) ** 2
    p = np.clip(pred, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def nw_tstat(d, lags=5):
    d = np.asarray(d, float)
    d = d[~np.isnan(d)]
    T = len(d)
    if T < 10:
        return np.nan, np.nan
    m = d.mean()
    e = d - m
    g0 = e @ e / T
    s = g0
    for L in range(1, lags + 1):
        gL = e[L:] @ e[:-L] / T
        s += 2 * (1 - L / (lags + 1)) * gL
    se = np.sqrt(s / T)
    return m, m / se if se > 0 else np.nan


def compare(oos, base, cand, kind):
    """Relative OOS improvement and day-block HAC t-stat of loss differential."""
    y = oos["y"].to_numpy()
    lb = loss(oos[base].to_numpy(), y, kind)
    lc = loss(oos[cand].to_numpy(), y, kind)
    rel = 1 - lc.mean() / lb.mean()             # OOS "R^2 vs base" (skill score)
    daily = pd.Series(lb - lc, index=oos.index).groupby(oos.index.floor("D")).mean()
    m, t = nw_tstat(daily.to_numpy(), lags=5)
    # per-fold stability: share of folds in which the candidate wins
    fold_gain = pd.Series(lb - lc).groupby(oos["fold"].to_numpy()).mean()
    return dict(skill=rel, t=t, n=len(y), days=len(daily),
                fold_win=(fold_gain > 0).mean(), nfolds=len(fold_gain))


def holm(pvals):
    p = np.asarray(pvals, float)
    order = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    run = 0
    for rank, i in enumerate(order):
        run = max(run, (m - rank) * p[i])
        adj[i] = min(1.0, run)
    return adj


def calibration_table(pred, y, bins=10):
    q = pd.qcut(pred, bins, labels=False, duplicates="drop")
    t = pd.DataFrame({"p": pred, "y": y, "b": q}).groupby("b").agg(p=("p", "mean"), y=("y", "mean"), n=("y", "size"))
    return t
