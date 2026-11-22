"""Phase III diagnostics of the existing APX indicator (fault-tree tests DX1-DX3).

DX1 (F2/F6) Does APX's information carry DIRECTIONAL content? Walk-forward OLS of the
    signed forward 12-bar return (range-normalised) on (a) intercept, (b) a simple
    directional baseline (past return, RSI deviation, leverage term), (c) baseline + all APX
    inputs (x, m6, conc, conc6, B*w, B*M*w) + their interactions with the past return.
DX2 (F7) Cost geometry: mean |12-bar return| in bp, and the break-even hit rate
    p* = 0.5 + c / (2 E|R|) for round-trip costs c in {4, 10, 20} bp, overall and by decile
    of the APX activity forecast proxy (m6).
DX3 (F3) Information half-life of the abruptness features: y_vol skill when conc/B are
    lagged by k bars (k = 0, 1, 3, 6, 12) relative to the same baseline.
Development data only (2023-01..2025-10). Outputs: results/diag_dx1.csv, diag_dx2.csv, diag_dx3.csv
"""
import os, warnings
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pandas as pd
import features as fe
import walkforward as wf
import final_spec as fs

warnings.filterwarnings("ignore")
ROOT = os.path.join(os.path.dirname(__file__), "..")
RES = os.path.join(ROOT, "results")
SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]


def frame(sym, tf):
    d1 = fe.load_1m(os.path.join(ROOT, "data", f"{sym}_1m.parquet"))
    ib = fe.intrabar_stats(d1, tf) if tf > 1 else None
    return fs.add_tail(fe.build(fe.resample(d1, tf), tf, intrabar=ib))


def job(args):
    sym, tf = args
    F = frame(sym, tf)
    rows1, rows2, rows3 = [], [], []
    # ---------------- DX1 ----------------
    apx = ["x", "m6", "h1_B", "h1_BM"] + (["h4_conc", "h4_conc6"] if tf > 1 else [])
    for c in list(apx):
        F[f"i_{c}"] = F[c] * F["ret_past"]          # interaction with recent direction
    S = {"const": [], "DIR": ["ret_past", "rsi_dev", "zneg"],
         "DIR+APX": ["ret_past", "rsi_dev", "zneg"] + apx + [f"i_{c}" for c in apx]}
    o = wf.walk_forward(F, "y_ret", S, kind="ols", purge=48)
    for b, c in (("const", "DIR"), ("DIR", "DIR+APX"), ("const", "DIR+APX")):
        r = wf.compare(o, b, c, "ols"); r.update(sym=sym, tf=tf, base=b, cand=c)
        rows1.append(r)
    # hit rate of the sign of the DIR+APX prediction (all bars, overlapping)
    hit = (np.sign(o["DIR+APX"]) == np.sign(o["y"])).mean()
    rows1.append(dict(sym=sym, tf=tf, base="-", cand="hit_rate_DIR+APX", skill=hit))
    # ---------------- DX2 ----------------
    R = F["y_ret_raw"].abs() * 1e4
    dec = pd.qcut(F["m6"], 10, labels=False, duplicates="drop")
    for lab, mask in [("all", np.ones(len(F), bool))] + [(f"m6_decile_{d}", (dec == d).to_numpy()) for d in range(10)]:
        e = R[mask].mean()
        row = dict(sym=sym, tf=tf, group=lab, mean_abs_ret_bp=e)
        for c in (4, 10, 20):
            row[f"p_breakeven_{c}bp"] = 0.5 + c / (2 * e)
        rows2.append(row)
    # ---------------- DX3 (vol target, 5m/15m have conc) ----------------
    base = fs.base_cols(tf)
    abr = fs.abr_cols(tf)
    S3 = {"BASE": base}
    for k in (0, 1, 3, 6, 12):
        cols = []
        for c in abr:
            F[f"{c}_lag{k}"] = F[c].shift(k)
            cols.append(f"{c}_lag{k}")
        S3[f"lag{k}"] = base + cols
    o3 = wf.walk_forward(F, "y_vol", S3, kind="ols", purge=48)
    for k in (0, 1, 3, 6, 12):
        r = wf.compare(o3, "BASE", f"lag{k}", "ols"); r.update(sym=sym, tf=tf, lag=k)
        rows3.append(r)
    return rows1, rows2, rows3


def main():
    jobs = [(s, tf) for tf in (5, 15, 1) for s in SYMS]
    a, b, c = [], [], []
    with ProcessPoolExecutor(3) as ex:
        for (r1, r2, r3), j in zip(ex.map(job, jobs), jobs):
            a += r1; b += r2; c += r3
            print("done", j, flush=True)
    pd.DataFrame(a).to_csv(os.path.join(RES, "diag_dx1.csv"), index=False)
    pd.DataFrame(b).to_csv(os.path.join(RES, "diag_dx2.csv"), index=False)
    pd.DataFrame(c).to_csv(os.path.join(RES, "diag_dx3.csv"), index=False)


if __name__ == "__main__":
    main()
