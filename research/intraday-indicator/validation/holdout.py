"""Holdout evaluation of the FROZEN specification (final_spec.py).

Step 1  python holdout.py fit
        Estimates the frozen abruptness coefficients (delta) on DEVELOPMENT data only
        (2023-01..2025-10, BTC/ETH/SOL/XRP/BNB), using exactly the Pine standardisation.
        -> results/frozen_coefficients.json (these numbers are hard-coded in the Pine script)

Step 2  python holdout.py test
        (a) batch walk-forward FULL vs BASE, evaluated only on holdout rows
            - original assets: test months 2025-11..2026-10 (never used before)
            - new assets (DOGE/ADA/LTC/LINK/AVAX): all test months 2023-04..2026-10
        (b) deployed model: online RLS BASE (Pine replica) vs online BASE + frozen delta,
            on 2025-11..2026-10 for all ten assets (30-day online warm-up before).
        -> results/holdout_tests.csv, results/holdout_deployed.csv
"""
import json, os, sys, warnings
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pandas as pd
from scipy import stats
import features as fe
import walkforward as wf
import final_spec as fs
from online_model import online_ols, online_ridge

warnings.filterwarnings("ignore")
ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data")
RES = os.path.join(ROOT, "results")
ORIG = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]
NEW = ["DOGEUSDT", "ADAUSDT", "LTCUSDT", "LINKUSDT", "AVAXUSDT"]
HOLD_START = pd.Timestamp("2025-11-01", tz="UTC")
TFS = (1, 5, 15)


def load_series(sym, which):
    if which == "dev":
        return fe.load_1m(os.path.join(DATA, f"{sym}_1m.parquet"))
    if sym in ORIG:
        a = fe.load_1m(os.path.join(DATA, f"{sym}_1m.parquet"))
        b = fe.load_1m(os.path.join(DATA, "holdout", f"{sym}_1m.parquet"))
        return pd.concat([a, b[b.index > a.index[-1]]])
    return fe.load_1m(os.path.join(DATA, "newassets", f"{sym}_1m.parquet"))


def frame(d1, tf):
    df = fe.resample(d1, tf)
    ib = fe.intrabar_stats(d1, tf) if tf > 1 else None
    return fs.add_tail(fe.build(df, tf, intrabar=ib))


# ------------------------------------------------------------------------------------
def fit_job(args):
    sym, tf = args
    F = frame(load_series(sym, "dev"), tf)
    cols = fs.full_cols(tf)
    Z = fs.ewma_standardise(F[cols].to_numpy())
    y = F["y_vol"].to_numpy()
    ok = np.all(np.isfinite(Z), 1) & np.isfinite(y)
    return tf, Z[ok], y[ok]


def fit():
    jobs = [(s, tf) for tf in TFS for s in ORIG]
    acc = {tf: [] for tf in TFS}
    with ProcessPoolExecutor(3) as ex:
        for tf, Z, y in ex.map(fit_job, jobs):
            acc[tf].append((Z, y))
    out = {}
    for tf in TFS:
        Z = np.vstack([a for a, _ in acc[tf]]); y = np.concatenate([b for _, b in acc[tf]])
        X = np.column_stack([np.ones(len(Z)), Z])
        b = np.linalg.lstsq(X, y, rcond=None)[0]
        cols = fs.full_cols(tf)
        coef = dict(zip(cols, b[1:]))
        out[str(tf)] = {"abr": {c: float(coef[c]) for c in fs.abr_cols(tf)},
                        "all": {c: float(v) for c, v in coef.items()}, "n": int(len(y))}
        print(tf, {c: round(coef[c], 4) for c in fs.abr_cols(tf)})
    json.dump(out, open(os.path.join(RES, "frozen_coefficients.json"), "w"), indent=1)


# ------------------------------------------------------------------------------------
def test_job(args):
    sym, tf, coefs, deployed_only = args
    d1 = load_series(sym, "full")
    F = frame(d1, tf)
    B, Fu = fs.base_cols(tf), fs.full_cols(tf)
    rows, dep = [], []
    for target in (() if deployed_only else ("y_vol", "y_volL")):
        oos = wf.walk_forward(F, target, {"BASE": B, "FULL": Fu}, kind="ols", purge=48)
        if sym in ORIG:
            oos = oos[oos.index >= HOLD_START]
        r = wf.compare(oos, "BASE", "FULL", "ols")
        r.update(sym=sym, tf=tf, target=target, group="orig-holdout-period" if sym in ORIG else "new-asset")
        rows.append(r)
    # deployed online model on 2025-11..2026-10 (30 days warm-up)
    W = F[F.index >= HOLD_START - pd.Timedelta(days=30)]
    y = W["y_vol"].to_numpy()
    pB = online_ridge(W[B].to_numpy(), y, fe.P["H"])
    pF = online_ridge(W[Fu].to_numpy(), y, fe.P["H"])
    Za = fs.ewma_standardise(W[fs.abr_cols(tf)].to_numpy())
    c = np.array([coefs[str(tf)]["abr"][k] for k in fs.abr_cols(tf)])
    pD = pB + Za @ c
    D = pd.DataFrame({"BASE": pB, "BASE+delta": pD, "FULL_online": pF, "y": y}, index=W.index)
    D = D[(D.index >= HOLD_START)].dropna()
    D["fold"] = D.index.to_period("M").astype(str)
    for cand in ("BASE+delta", "FULL_online"):
        r = wf.compare(D, "BASE", cand, "ols")
        r.update(sym=sym, tf=tf, cand=cand)
        dep.append(r)
    # absolute sanity: online BASE vs a constant (intercept-only) forecast
    D["CONST"] = pd.Series(y, index=W.index).shift(fe.P["H"]).expanding().mean().reindex(D.index)
    r = wf.compare(D.dropna(), "CONST", "BASE", "ols"); r.update(sym=sym, tf=tf, cand="BASE_vs_const")
    dep.append(r)
    return rows, dep


def test(deployed_only=False):
    coefs = json.load(open(os.path.join(RES, "frozen_coefficients.json")))
    jobs = [(s, tf, coefs, deployed_only) for tf in TFS for s in ORIG + NEW]
    rows, dep = [], []
    with ProcessPoolExecutor(3) as ex:
        for (r, d), j in zip(ex.map(test_job, jobs), jobs):
            rows += r; dep += d
            print("done", j[:2], flush=True)
    if deployed_only:
        D = pd.DataFrame(dep)
        D["p_one_sided"] = stats.norm.sf(D["t"])
        D.to_csv(os.path.join(RES, "holdout_deployed.csv"), index=False)
        return
    R = pd.DataFrame(rows)
    R["p_one_sided"] = stats.norm.sf(R["t"])
    prim = R["target"] == "y_vol"
    R.loc[prim, "p_holm"] = wf.holm(R.loc[prim, "p_one_sided"].to_numpy())
    R.to_csv(os.path.join(RES, "holdout_tests.csv"), index=False)
    D = pd.DataFrame(dep)
    D["p_one_sided"] = stats.norm.sf(D["t"])
    D.to_csv(os.path.join(RES, "holdout_deployed.csv"), index=False)


if __name__ == "__main__":
    {"fit": fit, "test": test, "test-deployed": lambda: test(deployed_only=True)}[sys.argv[1]]()
