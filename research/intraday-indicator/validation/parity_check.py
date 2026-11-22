"""Pine-vs-Python parity check on identical market data (BINANCE:BTCUSDT, 5m).

TradingView values (results/parity/tv_btc_5m_probe.json) were produced by a minimal probe
script containing the indicator's exact x / conc / range code, executed server-side on
TradingView. Python values are computed by features.py from the Binance public archive.
Raw range must agree exactly; x depends on how much history each side has seen (the
time-of-day EWMA is started at different dates), so close but not identical agreement is
expected; conc depends only on the bar's own 1-minute bars and must agree exactly.
"""
import json, os
import numpy as np, pandas as pd
import features as fe

ROOT = os.path.join(os.path.dirname(__file__), "..")
tv = json.load(open(os.path.join(ROOT, "results/parity/tv_btc_5m_probe.json")))
# each column is aligned from t0 on its own (columns were transcribed separately)
TV = pd.concat({c: pd.Series(tv[c], index=pd.to_datetime(tv["t0"] + tv["step"] * np.arange(len(tv[c])), unit="s", utc=True))
                for c in ("x", "conc", "range_bp")}, axis=1)
a = fe.load_1m(os.path.join(ROOT, "data/holdout/BTCUSDT_1m.parquet"))
b = fe.load_1m(os.path.join(ROOT, "data/parity/BTCUSDT_1m_2026-11.parquet"))
d1 = pd.concat([a, b[b.index > a.index[-1]]])
d1 = d1[d1.index >= d1.index[-1] - pd.Timedelta(days=70)]    # ~ TradingView 5m history depth
df = fe.resample(d1, 5)
F = fe.build(df, 5, intrabar=fe.intrabar_stats(d1, 5), p={**fe.P, "warmup_days": 0})
PY = pd.DataFrame({"x": F["x"], "conc": F["h4_conc"], "range_bp": np.log(df["h"] / df["l"]).reindex(F.index) * 1e4})
J0 = TV.join(PY, lsuffix="_tv", rsuffix="_py", how="inner")
out = {}
for c in ("range_bp", "conc", "x"):
    J = J0[[f"{c}_tv", f"{c}_py"]].dropna()
    d = (J[f"{c}_tv"] - J[f"{c}_py"]).abs()
    out[c] = dict(n=len(J), max_abs_diff=float(d.max()), mean_abs_diff=float(d.mean()),
                  corr=float(J[f"{c}_tv"].corr(J[f"{c}_py"])))
print(json.dumps(out, indent=1))
json.dump(out, open(os.path.join(ROOT, "results/parity/parity_summary.json"), "w"), indent=1)
