"""Download Binance spot 1-minute klines from the public archive (data.binance.vision).

Reproducible data acquisition for the validation study. Output: one parquet file per
symbol in DATA_DIR (default ./data, git-ignored). Columns: t (UTC ms open time),
o,h,l,c,v (base-asset volume), qv (quote volume), n (trade count).

Usage: python download_binance.py --symbols BTCUSDT ETHUSDT --start 2023-01 --end 2025-10
"""
import argparse, io, os, sys, zipfile, urllib.request
import pandas as pd

BASE = "https://data.binance.vision/data/spot/monthly/klines/{s}/1m/{s}-1m-{ym}.zip"
COLS = ["t", "o", "h", "l", "c", "v", "ct", "qv", "n", "tbv", "tqv", "ig"]


def months(start, end):
    p = pd.Period(start, "M")
    e = pd.Period(end, "M")
    while p <= e:
        yield str(p)
        p += 1


def fetch(sym, ym):
    url = BASE.format(s=sym, ym=ym)
    with urllib.request.urlopen(url, timeout=120) as r:
        raw = r.read()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        with z.open(z.namelist()[0]) as f:
            df = pd.read_csv(f, header=None, names=COLS)
    # Binance switched spot timestamps to microseconds in 2025
    if df["t"].iloc[0] > 1e14:
        df["t"] = df["t"] // 1000
    return df[["t", "o", "h", "l", "c", "v", "qv", "n"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", required=True)
    ap.add_argument("--start", default="2023-01")
    ap.add_argument("--end", default="2025-10")
    ap.add_argument("--out", default=os.environ.get("DATA_DIR", "data"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for s in a.symbols:
        parts = []
        for ym in months(a.start, a.end):
            try:
                parts.append(fetch(s, ym))
            except Exception as ex:  # missing month -> report, continue
                print(f"{s} {ym}: {ex}", file=sys.stderr)
        df = pd.concat(parts).drop_duplicates("t").sort_values("t").reset_index(drop=True)
        df.to_parquet(os.path.join(a.out, f"{s}_1m.parquet"))
        print(s, len(df), pd.to_datetime(df.t.iloc[0], unit="ms"), pd.to_datetime(df.t.iloc[-1], unit="ms"))


if __name__ == "__main__":
    main()
