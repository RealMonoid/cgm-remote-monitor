"""Main study: walk-forward OOS comparison of all candidates against known-information baselines.

Outputs (results/):
  oos_<SYM>_<tf>.parquet      OOS predictions (git-ignored)
  study_results.csv           all comparisons (skill, HAC t, p, fold win share, ...)
  h1_mechanism.csv            event study: post-shock HAR residual by build-up tercile
  direction_trading.csv       cost-aware evaluation of the only directional candidate
Usage: python run_study.py [--quick]
"""
import argparse, os, warnings
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pandas as pd
from scipy import stats
import features as fe
import walkforward as wf

warnings.filterwarnings("ignore")
DATA = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
RES = os.path.join(os.path.dirname(__file__), "..", "results")
CRYPTO = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]
REF = {"BTCUSDT": "ETHUSDT"}  # all other crypto -> BTCUSDT
YAHOO = {"SPY": None, "QQQ": "SPY", "IWM": "SPY", "ES_F": None, "NQ_F": "ES_F",
         "GC_F": None, "CL_F": None, "EURUSD_X": None}


def feature_sets(F, target_kind):
    known = list(fe.KNOWN_NOVOL) + (fe.VOL if "u" in F else [])
    S = {"const": [], "HAR": list(fe.HAR), "KNOWN": known,
         "KNOWN+H1mem": known + fe.H1_MEM,
         "KNOWN+H1": known + fe.H1_MEM + fe.H1_ENDO,
         "KNOWN+H2": known + fe.H2}
    if "h4_conc" in F:
        S["KNOWN+H4"] = known + fe.H4
    if "h3_R2" in F:
        S["KNOWN+H3"] = known + fe.H3
    return S


# primary comparisons (family for Holm correction): candidate vs its fair baseline
PRIMARY = [("KNOWN+H1mem", "KNOWN+H1", "H1 endo/exo component"),
           ("KNOWN", "KNOWN+H2", "H2 critical slowing down"),
           ("KNOWN", "KNOWN+H3", "H3 cross-asset share"),
           ("KNOWN", "KNOWN+H4", "H4 intrabar structure")]
SECONDARY = [("const", "HAR", "HAR vs const"), ("HAR", "KNOWN", "known features vs HAR"),
             ("KNOWN", "KNOWN+H1mem", "H1 shock memory"), ("KNOWN", "KNOWN+H1", "H1 total")]
TARGETS = [("y_vol", "ols"), ("y_volL", "ols"), ("y_eff", "ols"), ("y_tail", "logit")]


def run_series(job):
    sym, tf, src = job
    try:
        if src == "binance":
            d1 = fe.load_1m(os.path.join(DATA, f"{sym}_1m.parquet"))
            df = fe.resample(d1, tf)
            ib = fe.intrabar_stats(d1, tf) if tf > 1 else None
            rsym = REF.get(sym, "BTCUSDT")
            ref = fe.resample(fe.load_1m(os.path.join(DATA, f"{rsym}_1m.parquet")), tf)
            freq, mtf = "M", 3
        else:
            df = fe.load_1m(os.path.join(DATA, f"YF_{sym}_{tf}m.parquet"))
            ib = None
            r = YAHOO[sym]
            ref = fe.load_1m(os.path.join(DATA, f"YF_{r}_{tf}m.parquet")) if r else None
            freq, mtf = "W", 2
        F = fe.build(df, tf, intrabar=ib, ref=ref)
        rows, oos_keep = [], {}
        for target, kind in TARGETS:
            S = feature_sets(F, kind)
            oos = wf.walk_forward(F, target, S, kind=kind, freq=freq, purge=fe.P["H_long"],
                                  min_train_folds=mtf,
                                  max_train=(400_000 if kind == "logit" else None))
            oos_keep[target] = oos
            for base, cand, label in PRIMARY + SECONDARY:
                if base in S and cand in S:
                    r_ = wf.compare(oos, base, cand, kind)
                    r_.update(sym=sym, tf=tf, src=src, target=target, base=base, cand=cand,
                              label=label, primary=(base, cand, label) in PRIMARY)
                    rows.append(r_)
        # ---- event-conditional H1 analysis (episode rows only, a >= 1) ----
        mask = (F["h1_live"].to_numpy() > 0) & (np.nan_to_num(F["age"].to_numpy()) >= 1)
        known = feature_sets(F, "ols")["KNOWN"]
        Sx = {"KNOWN": known, "KNOWN+H1mem": known + fe.H1_MEM, "KNOWN+H1": known + fe.H1_MEM + fe.H1_ENDO}
        for target in ("y_vol", "y_volL"):
            oos = wf.walk_forward(F, target, Sx, kind="ols", freq=freq, purge=fe.P["H_long"],
                                  min_train_folds=mtf, rows_mask=mask)
            if len(oos) > 200:
                for base, cand in (("KNOWN", "KNOWN+H1mem"), ("KNOWN+H1mem", "KNOWN+H1"), ("KNOWN", "KNOWN+H1")):
                    r_ = wf.compare(oos, base, cand, "ols")
                    r_.update(sym=sym, tf=tf, src=src, target=target + "|episode", base=base, cand=cand,
                              label="H1 (episode rows)", primary=(cand == "KNOWN+H1" and base == "KNOWN+H1mem"))
                    rows.append(r_)
        # ---- mechanism table: HAR/KNOWN residual after shocks by build-up tercile ----
        o = oos_keep["y_vol"]
        res = (o["y"] - o["KNOWN"]).rename("res")
        G = F.loc[o.index, ["age", "B_raw", "h1_live"]].join(res)
        G = G[G["h1_live"] > 0].dropna()
        mech = None
        if len(G) > 300:
            G["Bq"] = pd.qcut(G["B_raw"], 3, labels=["exo-like (low B)", "mid", "endo-like (high B)"])
            G["ageb"] = pd.cut(G["age"], [-1, 0, 3, 12, 48], labels=["0", "1-3", "4-12", "13-48"])
            mech = G.groupby(["Bq", "ageb"], observed=True)["res"].agg(["mean", "count"]).reset_index()
            mech["sym"], mech["tf"], mech["src"] = sym, tf, src
        # ---- directional evaluation (H3 directional features; costs) ----
        dirrows = []
        if "h3_e" in F:
            Sd = {"const": [], "DIR_KNOWN": ["ret_past", "rsi_dev", "zneg"],
                  "DIR_KNOWN+H3": ["ret_past", "rsi_dev", "zneg"] + fe.H3_DIR}
            od = wf.walk_forward(F, "y_ret", Sd, kind="ols", freq=freq, purge=fe.P["H_long"], min_train_folds=mtf)
            for base, cand in (("const", "DIR_KNOWN"), ("DIR_KNOWN", "DIR_KNOWN+H3")):
                r_ = wf.compare(od, base, cand, "ols")
                r_.update(sym=sym, tf=tf, src=src, target="y_ret", base=base, cand=cand,
                          label="direction", primary=False)
                rows.append(r_)
            raw = F.loc[od.index, "y_ret_raw"].to_numpy()
            for name in ("DIR_KNOWN", "DIR_KNOWN+H3"):
                pr = od[name].to_numpy()
                # threshold = 90th pct of |prediction| in the *previous* fold (causal)
                thr = pd.Series(np.abs(pr)).groupby(od["fold"].to_numpy()).transform("quantile", 0.9)
                thr = thr.groupby(od["fold"].to_numpy()).transform("first")
                folds_ = od["fold"].unique()
                prev = {f: np.nan for f in folds_}
                q = pd.Series(np.abs(pr)).groupby(od["fold"].to_numpy()).quantile(0.9)
                for a, b in zip(folds_[1:], folds_[:-1]):
                    prev[a] = q[b]
                th = np.array([prev[f] for f in od["fold"].to_numpy()])
                sel = np.abs(pr) > th
                # non-overlapping trades: take every H-th selected signal
                sel_idx = np.flatnonzero(sel)
                keep, last = [], -10 ** 9
                for i in sel_idx:
                    if i - last >= fe.P["H"]:
                        keep.append(i); last = i
                keep = np.array(keep, dtype=int)
                if len(keep) > 30:
                    g = np.sign(pr[keep]) * raw[keep] * 1e4
                    dirrows.append(dict(sym=sym, tf=tf, src=src, model=name, trades=len(keep),
                                        gross_bps=g.mean(), gross_t=g.mean() / (g.std() / np.sqrt(len(g))),
                                        net_bps_2=g.mean() - 2, net_bps_10=g.mean() - 10, hit=(g > 0).mean()))
        return rows, mech, dirrows
    except Exception as ex:
        import traceback; traceback.print_exc()
        return [], None, []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    os.makedirs(RES, exist_ok=True)
    jobs = []
    tfs = (5,) if a.quick else (15, 5, 1)
    syms = CRYPTO[:2] if a.quick else CRYPTO
    for tf in tfs:
        for s in syms:
            jobs.append((s, tf, "binance"))
    if not a.quick:
        for s in YAHOO:
            jobs.append((s, 5, "yahoo"))
    rows, mechs, dirs = [], [], []
    with ProcessPoolExecutor(a.workers) as ex:
        for (r, m, d), job in zip(ex.map(run_series, jobs), jobs):
            print("done", job, len(r), flush=True)
            rows += r; dirs += d
            if m is not None:
                mechs.append(m)
    R = pd.DataFrame(rows)
    R["p"] = 2 * stats.norm.sf(np.abs(R["t"]))
    R["p_one_sided"] = stats.norm.sf(R["t"])            # H_A: candidate improves
    prim = R["primary"] & R["p_one_sided"].notna()
    R.loc[prim, "p_holm"] = wf.holm(R.loc[prim, "p_one_sided"].to_numpy())
    R.to_csv(os.path.join(RES, "study_results.csv"), index=False)
    if mechs:
        pd.concat(mechs).to_csv(os.path.join(RES, "h1_mechanism.csv"), index=False)
    if dirs:
        pd.DataFrame(dirs).to_csv(os.path.join(RES, "direction_trading.csv"), index=False)
    print("primary tests:", prim.sum())


if __name__ == "__main__":
    main()
