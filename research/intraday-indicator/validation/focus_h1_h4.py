"""Focused follow-up tests after the main study (all comparisons pre-declared here).

1. H1 against the STRONGEST fair baseline (KNOWN + tail-shape + shock memory), at 1/5/15m.
2. H1 mechanism with an a-priori split (no data-driven cut points):
     built-up shock  : B > 0  (activity rose during the 12 bars before the shock)
     abrupt shock    : B <= 0
   Mean OOS residual of the strongest baseline WITHOUT the endo component, by age bucket.
   Theory (Sornette & Helmstetter 2003): built-up (endogenous-like) shocks relax more slowly
   -> positive residual at ages 1..12; abrupt shocks -> residual <= 0.
3. H2 at 1m against the tail-shape baseline (does critical slowing down survive?).
4. H4 decomposition at 5/15m: intrabar volume concentration vs intrabar path excess.

Usage: python focus_h1_h4.py --workers 3
Outputs: results/focus_tests.csv, results/focus_mechanism.csv
"""
import argparse, os, warnings
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pandas as pd
import features as fe
import walkforward as wf
from run_study import DATA, RES, CRYPTO

warnings.filterwarnings("ignore")
TAIL = ["vov", "xmax48", "nshock288"]


def add_tail(F):
    x = F["x"]
    F["vov"] = x.rolling(120).std()
    F["xmax48"] = x.rolling(48).max()
    F["nshock288"] = F["shock"].rolling(288).sum()
    return F


def job(args):
    sym, tf = args
    d1 = fe.load_1m(os.path.join(DATA, f"{sym}_1m.parquet"))
    df = fe.resample(d1, tf)
    ib = fe.intrabar_stats(d1, tf) if tf > 1 else None
    F = add_tail(fe.build(df, tf, intrabar=ib))
    K = list(fe.KNOWN_NOVOL) + fe.VOL + TAIL
    S = {"KT": K, "KT+mem": K + fe.H1_MEM, "KT+mem+endo": K + fe.H1_MEM + fe.H1_ENDO,
         "KT+H2": K + fe.H2}
    if ib is not None:
        S.update({"KT+conc": K + ["h4_conc", "h4_conc6"], "KT+path": K + ["h4_path", "h4_path6"],
                  "KT+path+conc": K + fe.H4})
    rows, mech = [], []
    for target in ("y_vol", "y_volL"):
        oos = wf.walk_forward(F, target, S, kind="ols", purge=48)
        pairs = [("KT", "KT+mem"), ("KT+mem", "KT+mem+endo"), ("KT", "KT+H2")]
        if ib is not None:
            pairs += [("KT", "KT+conc"), ("KT", "KT+path"), ("KT+path", "KT+path+conc")]
        for b, c in pairs:
            r = wf.compare(oos, b, c, "ols"); r.update(sym=sym, tf=tf, target=target, base=b, cand=c, rows="all")
            rows.append(r)
        # episode rows only (a >= 1): the population the endo/exo hypothesis is about
        ep = (F.loc[oos.index, "h1_live"] > 0) & (F.loc[oos.index, "age"] >= 1)
        o2 = oos[ep.to_numpy()]
        for b, c in (("KT+mem", "KT+mem+endo"),):
            r = wf.compare(o2, b, c, "ols"); r.update(sym=sym, tf=tf, target=target, base=b, cand=c, rows="episode")
            rows.append(r)
        # mechanism (a-priori split by sign of B)
        G = F.loc[oos.index, ["age", "B_raw", "h1_live"]].copy()
        G["res"] = oos["y"] - oos["KT+mem"]
        G = G[(G["h1_live"] > 0)].dropna()
        G["kind"] = np.where(G["B_raw"] > 0, "built-up (B>0)", "abrupt (B<=0)")
        G["ageb"] = pd.cut(G["age"], [-1, 0, 3, 12, 48], labels=["0", "1-3", "4-12", "13-48"])
        m = G.groupby(["kind", "ageb"], observed=True)["res"].agg(["mean", "count", "std"]).reset_index()
        m["se"] = m["std"] / np.sqrt(m["count"])
        m["sym"], m["tf"], m["target"] = sym, tf, target
        mech.append(m)
    return rows, pd.concat(mech)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    jobs = [(s, tf) for tf in (15, 5, 1) for s in CRYPTO]
    rows, mech = [], []
    with ProcessPoolExecutor(a.workers) as ex:
        for (r, m), j in zip(ex.map(job, jobs), jobs):
            rows += r; mech.append(m); print("done", j, flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(RES, "focus_tests.csv"), index=False)
    pd.concat(mech).to_csv(os.path.join(RES, "focus_mechanism.csv"), index=False)


if __name__ == "__main__":
    main()
