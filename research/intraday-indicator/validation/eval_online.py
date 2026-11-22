"""Evaluate the indicator AS DEPLOYED: bar-by-bar online models (Python replica of the Pine
arithmetic) on chart-length windows, no offline fitting at all.

For each symbol/timeframe, several non-overlapping windows of N bars are processed from
scratch (as TradingView would on a chart with N bars of history). Predictions are scored
against labels only after they were made (the online model never sees a label early).

Reports per window: log-loss and Brier of FULL, BASE and the running base rate; FULL-vs-BASE
skill; and a pooled reliability table (calibration).
Usage: python eval_online.py [--bars 20000] [--windows 4]
Outputs: results/online_eval.csv, results/online_calibration.csv
"""
import argparse, os, warnings
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pandas as pd
import features as fe
from online_model import online_logit
from run_study import DATA, RES, CRYPTO

warnings.filterwarnings("ignore")
BASE_COLS = ["x", "m6", "m48", "m288", "zabs6", "u6", "u48", "vov", "xmax48", "nshock288"]
FULL_COLS = BASE_COLS + ["h1_live", "h1_M", "h1_B", "h1_BM"]


def ll(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def job(args):
    sym, tf, nbars, nwin = args
    df_all = fe.resample(fe.load_1m(os.path.join(DATA, f"{sym}_1m.parquet")), tf)
    starts = np.linspace(0, len(df_all) - nbars - 1, nwin).astype(int)
    rows, cal = [], []
    for w, s0 in enumerate(starts):
        df = df_all.iloc[s0:s0 + nbars]
        # the Pine script has no warm-up cut: replicate by building on the window itself
        p = dict(fe.P); p["warmup_days"] = 0
        F = fe.build(df, tf, p=p)
        x = F["x"]
        F["vov"] = x.rolling(120).std()
        F["xmax48"] = x.rolling(48).max()
        F["nshock288"] = F["shock"].rolling(288).sum()
        y = F["y_tail"].to_numpy()
        H = fe.P["H"]
        pB = online_logit(F[BASE_COLS].to_numpy(), y, H)
        pF = online_logit(F[FULL_COLS].to_numpy(), y, H)
        # running base rate from matured labels only
        ym = pd.Series(y).shift(H)
        br = ym.expanding().mean().to_numpy()
        ok = np.isfinite(pB) & np.isfinite(pF) & np.isfinite(y) & np.isfinite(br)
        if ok.sum() < 1000:
            continue
        yy = y[ok]
        LB, LF, LR = ll(pB[ok], yy).mean(), ll(pF[ok], yy).mean(), ll(br[ok], yy).mean()
        rows.append(dict(sym=sym, tf=tf, window=w, start=str(df.index[0]), n=int(ok.sum()),
                         base_rate=yy.mean(), ll_rate=LR, ll_base=LB, ll_full=LF,
                         skill_full_vs_base=1 - LF / LB, skill_base_vs_rate=1 - LB / LR,
                         brier_base=((pB[ok] - yy) ** 2).mean(), brier_full=((pF[ok] - yy) ** 2).mean()))
        q = pd.qcut(pF[ok], 10, labels=False, duplicates="drop")
        c = pd.DataFrame({"p": pF[ok], "y": yy, "b": q}).groupby("b").agg(p=("p", "mean"), y=("y", "mean"), n=("y", "size")).reset_index()
        c["sym"], c["tf"], c["window"] = sym, tf, w
        cal.append(c)
    return rows, (pd.concat(cal) if cal else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", type=int, default=20000)
    ap.add_argument("--windows", type=int, default=4)
    ap.add_argument("--workers", type=int, default=1)
    a = ap.parse_args()
    jobs = [(s, tf, a.bars, a.windows) for tf in (15, 5, 1) for s in CRYPTO]
    rows, cals = [], []
    with ProcessPoolExecutor(a.workers) as ex:
        for (r, c), j in zip(ex.map(job, jobs), jobs):
            rows += r
            if c is not None:
                cals.append(c)
            print("done", j[:2], flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(RES, "online_eval.csv"), index=False)
    pd.concat(cals).to_csv(os.path.join(RES, "online_calibration.csv"), index=False)


if __name__ == "__main__":
    main()
