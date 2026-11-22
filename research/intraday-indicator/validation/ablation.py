"""Ablations, parameter robustness grid and sub-period stability for the candidates.

Nothing here is used to *select* parameters: the a-priori values in features.P remain the
reported specification; the grid is shown in full so that parameter dependence is visible.

Usage: python ablation.py [--tfs 5 15] [--workers 3]
Outputs: results/ablation.csv, results/robustness.csv, results/subperiods.csv
"""
import argparse, os, warnings
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pandas as pd
import features as fe
import walkforward as wf
from run_study import DATA, RES, CRYPTO, REF

warnings.filterwarnings("ignore")


def load(sym, tf):
    d1 = fe.load_1m(os.path.join(DATA, f"{sym}_1m.parquet"))
    return fe.resample(d1, tf)


def known_cols(F):
    return list(fe.KNOWN_NOVOL) + (fe.VOL if "u" in F else [])


def ablation_job(job):
    sym, tf = job
    df = load(sym, tf)
    F = fe.build(df, tf)
    K = known_cols(F)
    # explicit "vol-of-vol" & tail-shape baselines that a sceptic would add
    x = F["x"]
    F["vov"] = x.rolling(120).std()
    F["xmax48"] = x.rolling(48).max()
    F["nshock288"] = F["shock"].rolling(288).sum()
    S = {"KNOWN": K,
         "K+rho_x": K + ["h2_rho_x"], "K+var_x": K + ["h2_var_x"], "K+drho": K + ["h2_drho"],
         "K+rho_r": K + ["h2_rho_r"], "K+H2": K + fe.H2,
         "K+H2-var_x": K + ["h2_rho_x", "h2_drho", "h2_rho_r"],
         "K+tailshape": K + ["vov", "xmax48", "nshock288"],
         "K+tailshape+H2": K + ["vov", "xmax48", "nshock288"] + fe.H2,
         "K+tailshape+H1mem": K + ["vov", "xmax48", "nshock288"] + fe.H1_MEM,
         "K+H1mem": K + fe.H1_MEM, "K+H1mem+B": K + fe.H1_MEM + ["h1_B"],
         "K+H1mem+BM": K + fe.H1_MEM + ["h1_BM"], "K+H1": K + fe.H1_MEM + fe.H1_ENDO,
         "K+tailshape+H1mem+H2": K + ["vov", "xmax48", "nshock288"] + fe.H1_MEM + fe.H2}
    rows, sub = [], []
    for target, kind in (("y_tail", "logit"), ("y_volL", "ols"), ("y_vol", "ols")):
        oos = wf.walk_forward(F, target, S, kind=kind, purge=48, max_train=(400_000 if kind == "logit" else None))
        for cand in S:
            if cand == "KNOWN":
                continue
            for base in ("KNOWN", "K+tailshape", "K+H1mem"):
                if base == cand or not set(S[base]) <= set(S[cand]):
                    continue
                r = wf.compare(oos, base, cand, kind)
                r.update(sym=sym, tf=tf, target=target, base=base, cand=cand)
                rows.append(r)
        # sub-periods (calendar year of the OOS row)
        yrs = oos.index.year
        for yr in np.unique(yrs):
            o = oos[yrs == yr]
            for base, cand in (("KNOWN", "K+H2"), ("K+tailshape", "K+tailshape+H2"),
                               ("KNOWN", "K+H1mem"), ("K+H1mem", "K+H1")):
                r = wf.compare(o, base, cand, kind)
                r.update(sym=sym, tf=tf, target=target, base=base, cand=cand, year=yr)
                sub.append(r)
    return rows, sub


GRID = {"csd_w": [60, 120, 240], "shock_theta": [np.log(3), np.log(4), np.log(5)],
        "pre_short": [6, 12, 24], "decay_p": [0.3, 0.5, 1.0]}


def robust_job(job):
    sym, tf, pname, val = job
    df = load(sym, tf)
    p = dict(fe.P)
    p[pname] = val
    F = fe.build(df, tf, p=p)
    K = known_cols(F)
    S = {"KNOWN": K, "K+H2": K + fe.H2, "K+H1mem": K + fe.H1_MEM, "K+H1": K + fe.H1_MEM + fe.H1_ENDO}
    rows = []
    # episode-row test of the endo/exo component (the population the hypothesis is about)
    ep = ((F["h1_live"] > 0) & (F["age"] >= 1)).to_numpy()
    o = wf.walk_forward(F, "y_vol", {"K+H1mem": S["K+H1mem"], "K+H1": S["K+H1"]}, kind="ols", purge=48, rows_mask=ep)
    r = wf.compare(o, "K+H1mem", "K+H1", "ols")
    r.update(sym=sym, tf=tf, target="y_vol|episode", base="K+H1mem", cand="K+H1", param=pname, value=val)
    rows.append(r)
    for target, kind in (("y_tail", "logit"), ("y_vol", "ols")):
        oos = wf.walk_forward(F, target, S, kind=kind, purge=48, max_train=(400_000 if kind == "logit" else None))
        for base, cand in (("KNOWN", "K+H2"), ("KNOWN", "K+H1mem"), ("K+H1mem", "K+H1")):
            r = wf.compare(oos, base, cand, kind)
            r.update(sym=sym, tf=tf, target=target, base=base, cand=cand, param=pname, value=val)
            rows.append(r)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tfs", nargs="+", type=int, default=[5, 15])
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--skip-grid", action="store_true")
    ap.add_argument("--skip-ablation", action="store_true")
    ap.add_argument("--grid-tf", type=int, default=15)
    ap.add_argument("--grid-syms", nargs="+", default=CRYPTO)
    ap.add_argument("--grid-params", nargs="+", default=list(GRID))
    ap.add_argument("--grid-out", default="robustness.csv")
    a = ap.parse_args()
    jobs = [(s, tf) for tf in a.tfs for s in CRYPTO]
    rows, sub = [], []
    if not a.skip_ablation:
        with ProcessPoolExecutor(a.workers) as ex:
            for (r, s), j in zip(ex.map(ablation_job, jobs), jobs):
                rows += r; sub += s
                print("ablation done", j, flush=True)
        pd.DataFrame(rows).to_csv(os.path.join(RES, "ablation.csv"), index=False)
        pd.DataFrame(sub).to_csv(os.path.join(RES, "subperiods.csv"), index=False)
    if not a.skip_grid:
        gj = [(s, a.grid_tf, k, v) for s in a.grid_syms for k in a.grid_params for v in GRID[k]]
        rr = []
        with ProcessPoolExecutor(a.workers) as ex:
            for r in ex.map(robust_job, gj):
                rr += r
        pd.DataFrame(rr).to_csv(os.path.join(RES, a.grid_out), index=False)
        print("grid done")


if __name__ == "__main__":
    main()
