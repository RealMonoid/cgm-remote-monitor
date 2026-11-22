"""Download recent intraday bars from Yahoo Finance's public chart endpoint.

Used ONLY as a small cross-market replication sample (60 days of 5m, ~30 days of 1m).
Yahoo intraday history is short; results on it carry wide confidence intervals.
FX symbols have no volume on Yahoo -> volume-based features are skipped for them.

Usage: python download_yahoo.py --symbols SPY QQQ ES=F --out data
"""
import argparse, json, os, time, urllib.request
import pandas as pd

URL = "https://query1.finance.yahoo.com/v8/finance/chart/{s}?interval={i}&period1={a}&period2={b}&includePrePost=false"


def get(sym, interval, a, b):
    req = urllib.request.Request(URL.format(s=sym, i=interval, a=a, b=b), headers={"User-Agent": "Mozilla/5.0"})
    js = json.load(urllib.request.urlopen(req, timeout=60))
    r = js["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    df = pd.DataFrame({"t": pd.Series(r["timestamp"]) * 1000, "o": q["open"], "h": q["high"],
                       "l": q["low"], "c": q["close"], "v": q["volume"]})
    return df.dropna(subset=["o", "h", "l", "c"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", required=True)
    ap.add_argument("--out", default="data")
    a = ap.parse_args()
    now = int(time.time())
    for s in a.symbols:
        # 5m: one request covering the last 59 days
        d5 = get(s, "5m", now - 59 * 86400, now)
        # 1m: Yahoo allows 8-day windows within the last 30 days
        parts = []
        for k in range(4):
            b = now - k * 7 * 86400
            try:
                parts.append(get(s, "1m", b - 7 * 86400, b))
            except Exception as ex:
                print(s, "1m chunk", k, ex)
            time.sleep(1)
        d1 = pd.concat(parts).drop_duplicates("t").sort_values("t") if parts else None
        tag = s.replace("=", "_").replace("^", "")
        d5.reset_index(drop=True).to_parquet(os.path.join(a.out, f"YF_{tag}_5m.parquet"))
        if d1 is not None:
            d1.reset_index(drop=True).to_parquet(os.path.join(a.out, f"YF_{tag}_1m.parquet"))
        print(s, len(d5), "5m bars;", 0 if d1 is None else len(d1), "1m bars")
        time.sleep(1)


if __name__ == "__main__":
    main()
