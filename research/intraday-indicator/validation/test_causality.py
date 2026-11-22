"""Empirical no-lookahead test.

For a set of cut points T, features computed on the full history must equal features
computed on history truncated at T (for all bars <= T). Any difference means a feature
uses future information. Targets are excluded (they are forward-looking by design).

Usage: python test_causality.py data/BTCUSDT_1m.parquet
"""
import sys
import numpy as np
import pandas as pd
import features as fe


def main(path):
    d1 = fe.load_1m(path).iloc[: 60 * 24 * 45]          # 45 days of 1m data
    ref = None
    for tf in (1, 5, 15):
        df = fe.resample(d1, tf)
        ib = fe.intrabar_stats(d1, tf) if tf > 1 else None
        ref = df * 1.0  # use the asset itself shifted as a stand-in reference
        ref["c"] = ref["c"].shift(3).bfill()
        full = fe.build(df, tf, intrabar=ib, ref=ref)
        feat_cols = [c for c in full.columns if not c.startswith("y_") and c not in ("rv_fwd", "day")]
        worst = 0.0
        for frac in (0.6, 0.75, 0.9):
            T = df.index[int(len(df) * frac)]
            cut = fe.build(df[df.index <= T], tf,
                           intrabar=None if ib is None else ib[ib.index <= T],
                           ref=ref[ref.index <= T])
            a = full.loc[cut.index, feat_cols]
            b = cut[feat_cols]
            diff = (a - b).abs().where(~(a.isna() & b.isna()))
            worst = max(worst, float(np.nanmax(diff.to_numpy())) if diff.size else 0.0)
        status = "PASS" if worst < 1e-9 else "FAIL"
        print(f"tf={tf:>2}m  features={len(feat_cols)}  max|full-truncated|={worst:.3e}  {status}")
        if status == "FAIL":
            bad = diff.max().sort_values(ascending=False).head(5)
            print(bad)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/BTCUSDT_1m.parquet")
