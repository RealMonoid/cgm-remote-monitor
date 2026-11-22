"""Directional event study, implemented exactly as pre-registered in
docs/PREREGISTRATION_DIRECTION.md (commit 800db6f, written before any evaluation).

Usage:
  python direction_study.py --stage DEV
  python direction_study.py --stage A --only C1-5 C2-1     # only candidates that passed DEV
  python direction_study.py --stage B --only ...           # only candidates that passed A
Outputs: results/direction_<stage>_trades.parquet, results/direction_<stage>_summary.csv
"""
import argparse, os, warnings
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pandas as pd
from scipy import stats
import features as fe
import walkforward as wf

warnings.filterwarnings("ignore")
ROOT = os.path.join(os.path.dirname(__file__), "..")
D = os.path.join(ROOT, "data")
RES = os.path.join(ROOT, "results")
H = 12
COSTS = (4, 10, 20)
ORIG = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]
NEW = ["DOGEUSDT", "ADAUSDT", "LTCUSDT", "LINKUSDT", "AVAXUSDT"]
FRESH = ["TRXUSDT", "DOTUSDT", "ATOMUSDT", "BCHUSDT", "NEARUSDT"]
HOLD_A_START = pd.Timestamp("2025-11-01", tz="UTC")


def load(sym, stage):
    """Return (1m data, evaluation start or None)."""
    if stage == "DEV":
        return fe.load_1m(os.path.join(D, f"{sym}_1m.parquet")), None
    if stage == "A":
        if sym in ORIG:
            a = fe.load_1m(os.path.join(D, f"{sym}_1m.parquet"))
            b = fe.load_1m(os.path.join(D, "holdout", f"{sym}_1m.parquet"))
            return pd.concat([a, b[b.index > a.index[-1]]]), HOLD_A_START
        return fe.load_1m(os.path.join(D, "newassets", f"{sym}_1m.parquet")), None
    if stage == "B":
        if sym in ORIG:
            return fe.load_1m(os.path.join(D, "early", f"{sym}_1m.parquet")), None
        return fe.load_1m(os.path.join(D, "fresh", f"{sym}_1m.parquet")), None
    raise ValueError(stage)


def btc_for(sym, stage):
    if stage == "B" and sym in ORIG:
        return load("BTCUSDT", "B")[0]
    if stage == "DEV":
        return load("BTCUSDT", "DEV")[0]
    return load("BTCUSDT", "A")[0]      # 2023-01..2026-10 continuous


def expanding_thr(ev_month, values, q, min_months=3):
    """Threshold per event from events in strictly earlier months (>= min_months history)."""
    months = pd.Index(sorted(ev_month.unique()))
    out = pd.Series(np.nan, index=ev_month.index)
    first = months[0]
    for m in months:
        if (m - first).n < min_months:
            continue
        prior = values[ev_month < m].dropna()
        if len(prior) >= 30:
            out[ev_month == m] = prior.quantile(q)
    return out


def take_nonoverlap(pos_idx):
    keep, last = [], -10 ** 9
    for i in pos_idx:
        if i - last >= H:
            keep.append(i); last = i
    return keep


def job(args):
    sym, tf, stage = args
    d1, eval_start = load(sym, stage)
    df = fe.resample(d1, tf)
    ib = fe.intrabar_stats(d1, tf) if tf > 1 else None
    F = fe.build(df, tf, intrabar=ib)
    r = np.log(F.index.to_series().map(df["c"]) / F.index.to_series().map(df["c"].shift(1))).to_numpy()
    n = len(F)
    pos_bar = np.arange(n)
    R = F["y_ret_raw"].to_numpy()
    month = pd.Series(F.index.to_period("M"), index=F.index)
    trades = []

    def record(rule, idx_list, posdir):
        for i in take_nonoverlap(idx_list):
            if not np.isfinite(R[i]):
                continue
            t = F.index[i]
            if eval_start is not None and t < eval_start:
                continue
            trades.append(dict(sym=sym, tf=tf, rule=rule, t=t, pos=posdir[i], gross_bp=posdir[i] * R[i] * 1e4))

    # ---------------- own-shock events ----------------
    ev = (F["shock"].to_numpy() > 0) & (r != 0) & np.isfinite(r)
    d = np.sign(r)
    evi = np.flatnonzero(ev)
    E = pd.DataFrame({"i": evi, "B": F["B_raw"].to_numpy()[evi], "u": F["u"].to_numpy()[evi] if "u" in F else np.nan,
                      "conc": F["h4_conc"].to_numpy()[evi] if "h4_conc" in F else np.nan},
                     index=F.index[evi])
    em = month.iloc[evi]
    # baselines U
    record("U+", evi, d)
    record("U-", evi, -d)
    # C1
    if tf > 1:
        thr = expanding_thr(em, E["conc"], 0.5)
        ok = thr.notna().to_numpy()
        abrupt = ok & (E["B"].to_numpy() <= 0) & (E["conc"].to_numpy() >= thr.to_numpy())
        built = ok & (E["B"].to_numpy() > 0) & (E["conc"].to_numpy() < thr.to_numpy())
    else:
        ok = expanding_thr(em, E["B"], 0.5).notna().to_numpy()      # same 3-month start rule
        abrupt = ok & (E["B"].to_numpy() <= 0)
        built = ok & (E["B"].to_numpy() > 0)
    p1 = np.zeros(n)
    p1[E["i"][abrupt]] = -d[E["i"][abrupt]]
    p1[E["i"][built]] = d[E["i"][built]]
    record("C1", np.flatnonzero(p1 != 0), p1)
    # C2
    lo = expanding_thr(em, E["u"], 1 / 3).to_numpy()
    hi = expanding_thr(em, E["u"], 2 / 3).to_numpy()
    uu = E["u"].to_numpy()
    low = np.isfinite(lo) & (uu <= lo)
    high = np.isfinite(hi) & (uu >= hi)
    p2 = np.zeros(n)
    p2[E["i"][low]] = -d[E["i"][low]]
    p2[E["i"][high]] = d[E["i"][high]]
    record("C2", np.flatnonzero(p2 != 0), p2)
    # C3 (alts only)
    if sym != "BTCUSDT":
        b1 = btc_for(sym, stage)
        Fb = fe.build(fe.resample(b1, tf), tf)
        Fb = Fb.reindex(F.index)
        cb = fe.resample(b1, tf)["c"]
        rb = np.log(cb / cb.shift(1)).reindex(F.index).to_numpy()
        A_ = pd.Series(r, index=F.index); B_ = pd.Series(rb, index=F.index)
        beta = (A_.rolling(240).cov(B_) / B_.rolling(240).var()).shift(1).to_numpy()
        e = r - beta * rb
        evb = (Fb["shock"].to_numpy() > 0) & np.isfinite(e) & (rb != 0) & np.isfinite(rb)
        dB = np.sign(rb)
        sel = evb & (dB * e < 0)
        p3 = np.where(sel, dB, 0.0)
        record("C3", np.flatnonzero(p3 != 0), p3)
    return trades


def nw_t(x, lags=5):
    m, t = wf.nw_tstat(np.asarray(x, float), lags)
    return m, t


def summarise(T, stage):
    rows = []
    for (rule, tf), g in T.groupby(["rule", "tf"]):
        daily = g.groupby(g["t"].dt.floor("D"))["gross_bp"].mean()
        row = dict(stage=stage, rule=rule, tf=tf, trades=len(g), assets=g["sym"].nunique(),
                   gross_bp=g["gross_bp"].mean(), hit=(g["gross_bp"] > 0).mean())
        for c in COSTS:
            m, t = nw_t(daily.to_numpy() - c)
            row[f"net{c}_bp"] = g["gross_bp"].mean() - c
            row[f"t_net{c}"] = t
            row[f"assets_pos_net{c}"] = (g.groupby("sym")["gross_bp"].mean() - c > 0).mean()
        rows.append(row)
    S = pd.DataFrame(rows)
    # criterion 2: candidate gross vs best U (same tf), daily paired difference
    for i, row in S.iterrows():
        if row["rule"].startswith("C"):
            g = T[(T.rule == row["rule"]) & (T.tf == row["tf"])]
            best = None
            for u in ("U+", "U-"):
                gu = T[(T.rule == u) & (T.tf == row["tf"])]
                if best is None or gu["gross_bp"].mean() > best[1]:
                    best = (u, gu["gross_bp"].mean(), gu)
            dc = g.groupby(g["t"].dt.floor("D"))["gross_bp"].mean()
            du = best[2].groupby(best[2]["t"].dt.floor("D"))["gross_bp"].mean()
            j = pd.concat([dc, du], axis=1, keys=["c", "u"]).dropna()
            m, t = nw_t((j["c"] - j["u"]).to_numpy())
            S.loc[i, "best_U"] = best[0]
            S.loc[i, "diff_vs_U_bp"] = m
            S.loc[i, "t_diff_vs_U"] = t
    S["p_net10"] = stats.norm.sf(S["t_net10"])
    cand = S["rule"].str.startswith("C")
    S.loc[cand, "p_net10_holm"] = wf.holm(S.loc[cand, "p_net10"].fillna(1).to_numpy())
    return S


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["DEV", "A", "B"])
    ap.add_argument("--only", nargs="*", default=None, help="e.g. C1-5 C2-1 (rule-tf)")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    syms = {"DEV": ORIG, "A": ORIG + NEW, "B": ORIG + FRESH}[a.stage]
    tfs = (1, 5, 15)
    if a.only:
        tfs = tuple(sorted({int(x.split("-")[1]) for x in a.only}))
    jobs = [(s, tf, a.stage) for tf in tfs for s in syms]
    allt = []
    with ProcessPoolExecutor(a.workers) as ex:
        for tr, j in zip(ex.map(job, jobs), jobs):
            allt += tr
            print("done", j, len(tr), flush=True)
    T = pd.DataFrame(allt)
    if a.only:
        keep = set(a.only) | {f"U+-{tf}" for tf in tfs} | {f"U--{tf}" for tf in tfs}
        T = T[(T["rule"] + "-" + T["tf"].astype(str)).isin(keep)]
    T.to_parquet(os.path.join(RES, f"direction_{a.stage}_trades.parquet"))
    S = summarise(T, a.stage)
    S.to_csv(os.path.join(RES, f"direction_{a.stage}_summary.csv"), index=False)
    pd.set_option("display.width", 250)
    print(S.round(3).to_string())


if __name__ == "__main__":
    main()
