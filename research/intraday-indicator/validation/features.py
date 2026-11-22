"""Causal feature and target construction for the intraday research study.

Every feature at bar t uses only bars <= t (bar t is considered closed). Targets use bars
t+1..t+H only. `test_causality.py` verifies the no-lookahead property empirically by
recomputing all features on truncated histories.

All parameters below are fixed A PRIORI (chosen before looking at any test result) and
documented in docs/SPECIFICATION.md. They are not tuned on the data. The robustness
script reports how results change when they are varied.
"""
import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------------
# Fixed parameters (a priori)
# ----------------------------------------------------------------------------------
P = dict(
    diurnal_alpha=1 / 20,     # EWMA weight per day for the time-of-day profile (~14d half-life)
    warmup_days=20,           # rows before this are dropped (profile not yet informative)
    har=(6, 48, 288),         # HAR windows in bars
    H=12,                     # primary forecast horizon (bars)
    H_long=48,                # secondary horizon
    # --- H1: endogenous/exogenous shock fingerprint ---
    shock_theta=np.log(4.0),  # shock: bar log-range exceeds local level by factor 4
    shock_base=48,            # local level window for the shock definition
    pre_short=12,             # pre-shock build-up window
    pre_long=288,             # pre-shock reference window
    episode=48,               # bars after a shock during which the episode is "live"
    decay_p=0.5,              # a-priori relaxation exponent of the memory kernel
    # --- H2: critical slowing down ---
    csd_w=120,
    # --- H3: cross-asset systematic share ---
    xa_w=240,
    xa_k=6,
)


# ----------------------------------------------------------------------------------
# Loading / resampling
# ----------------------------------------------------------------------------------
def load_1m(path):
    df = pd.read_parquet(path)
    df["t"] = pd.to_datetime(df["t"], unit="ms", utc=True)
    return df.set_index("t")[["o", "h", "l", "c", "v"]].astype(float)


def resample(df1, minutes):
    if minutes == 1:
        return df1.copy()
    r = df1.resample(f"{minutes}min", label="left", closed="left")
    out = pd.DataFrame({"o": r["o"].first(), "h": r["h"].max(), "l": r["l"].min(),
                        "c": r["c"].last(), "v": r["v"].sum()})
    return out.dropna(subset=["c"])


def intrabar_stats(df1, minutes):
    """Intrabar (1-minute) statistics per higher-timeframe bar (candidate H4).

    Available in TradingView through request.security_lower_tf(). Computed only from the
    1m bars that make up the (closed) higher-timeframe bar.
    """
    g = df1.copy()
    g["lr"] = np.log(g["h"] / g["l"])
    g["v2"] = g["v"] ** 2
    r = g.resample(f"{minutes}min", label="left", closed="left")
    s = pd.DataFrame({"sum_lr": r["lr"].sum(), "V": r["v"].sum(), "V2": r["v2"].sum(),
                      "n": r["v"].count()})
    return s


# ----------------------------------------------------------------------------------
# Causal building blocks
# ----------------------------------------------------------------------------------
def ewm_by_bucket(values, bucket, alpha):
    """Per-bucket EWMA, value BEFORE incorporating the current observation.

    Equivalent to a Pine array indexed by time-of-day bucket that is read first and
    updated after. First observation of a bucket -> NaN.
    """
    s = pd.Series(values)
    out = s.groupby(np.asarray(bucket)).transform(
        lambda z: z.ewm(alpha=alpha, adjust=False).mean().shift(1))
    return out.to_numpy()


def roll_mean(x, w):
    return pd.Series(x).rolling(w, min_periods=w).mean().to_numpy()


def fwd_sum(x, H):
    """sum_{k=1..H} x[t+k] (NaN where not fully available)."""
    s = pd.Series(x)
    return s[::-1].rolling(H, min_periods=H).sum()[::-1].shift(-1).to_numpy()


def fwd_max(x, H):
    s = pd.Series(x)
    return s[::-1].rolling(H, min_periods=H).max()[::-1].shift(-1).to_numpy()


def bars_per_day(index):
    step = pd.Series(index).diff().median()
    return int(round(pd.Timedelta("1D") / step))


# ----------------------------------------------------------------------------------
# Main feature builder
# ----------------------------------------------------------------------------------
def build(df, tf_minutes, intrabar=None, ref=None, p=P):
    """Return DataFrame of features (causal) and targets (forward) for one series.

    df       : OHLCV bars at the analysis timeframe (UTC index)
    intrabar : optional output of intrabar_stats() aligned to df (candidate H4)
    ref      : optional reference-asset bars (same tf) for the cross-asset candidate H3
    """
    df = df.copy()
    idx = df.index
    o, h, l, c, v = (df[k].to_numpy() for k in "ohlcv")
    n = len(df)
    step = pd.Timedelta(minutes=tf_minutes)

    # session gaps (equity/futures data): a gap > 1.5 bars breaks return chains and targets
    gap = np.r_[True, np.diff(idx.asi8) > 1.5 * step.value]
    prev_c = np.r_[np.nan, c[:-1]]
    r = np.where(gap, np.log(c / o), np.log(c / prev_c))

    # range with a small causal floor (protects log against zero-range bars)
    rng = np.log(h / l)
    lvl = pd.Series(rng).ewm(alpha=1 / (bars_per_day(idx) * 5), adjust=False).mean().shift(1).to_numpy()
    eps = 0.1 * lvl
    lr = np.log(rng + eps)

    # time-of-day bucket and causal diurnal profiles
    mod = (idx.hour * 60 + idx.minute) // tf_minutes
    d_lr = ewm_by_bucket(lr, mod, p["diurnal_alpha"])
    x = lr - d_lr                                   # diurnally normalised log range
    has_v = np.nansum(v) > 0
    if has_v:
        lv = np.log(v + 0.01 * pd.Series(v).ewm(alpha=1 / (bars_per_day(idx) * 5), adjust=False).mean().shift(1).to_numpy() + 1e-12)
        u = lv - ewm_by_bucket(lv, mod, p["diurnal_alpha"])
    else:
        u = np.full(n, np.nan)
    # per-bar expected range from the profile (in price-log units) -> return scaling
    sig = np.exp(d_lr)
    z = r / sig                                     # range-normalised return

    F = pd.DataFrame(index=idx)
    F["x"] = x
    for w in p["har"]:
        F[f"m{w}"] = roll_mean(x, w)
    # leverage / absolute-return baseline features
    F["zneg"] = np.minimum(z, 0)
    F["zabs6"] = roll_mean(np.abs(z), 6)
    # volume (known information) -- treated as BASELINE, not as a candidate
    if has_v:
        F["u"] = u
        F["u6"] = roll_mean(u, 6)
        F["u48"] = roll_mean(u, 48)
    # established indicators as comparison features
    tr = np.maximum(h, prev_c) - np.minimum(l, prev_c)
    tr = np.where(np.isnan(tr), h - l, tr)
    atr14 = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
    atr100 = pd.Series(tr).ewm(alpha=1 / 100, adjust=False).mean().to_numpy()
    F["atr_ratio"] = np.log(atr14 / atr100)
    dc = np.diff(c, prepend=np.nan)
    up = pd.Series(np.maximum(dc, 0)).ewm(alpha=1 / 14, adjust=False).mean()
    dn = pd.Series(np.maximum(-dc, 0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = (100 - 100 / (1 + up / dn)).to_numpy()
    F["rsi_dev"] = (rsi - 50) / 50
    F["rsi_absdev"] = np.abs(F["rsi_dev"])
    # past efficiency (trend-quality baseline) and past return (momentum/reversal baseline)
    H = p["H"]
    r_ = pd.Series(r)
    net = r_.rolling(H).sum().to_numpy()
    rv = r_.pow(2).rolling(H).sum().to_numpy()
    F["eff_past"] = np.abs(net) / np.sqrt(rv + 1e-18)
    F["ret_past"] = net / (sig * np.sqrt(H))

    # ------------------------------------------------------------------------------
    # H1: endogenous / exogenous shock fingerprint
    # ------------------------------------------------------------------------------
    base = pd.Series(x).shift(1).rolling(p["shock_base"], min_periods=p["shock_base"]).mean().to_numpy()
    s = x - base                                    # surprise vs local level
    shock = s > p["shock_theta"]
    pre_s = pd.Series(x).shift(1).rolling(p["pre_short"]).mean().to_numpy()
    pre_l = pd.Series(x).shift(1 + p["pre_short"]).rolling(p["pre_long"] - p["pre_short"]).mean().to_numpy()
    build_up = pre_s - pre_l                        # B: activity build-up before the bar
    age = np.full(n, np.nan)
    M = np.full(n, np.nan)
    B = np.full(n, np.nan)
    last = -10 ** 9
    m_cur = b_cur = np.nan
    for i in range(n):                              # O(n) state machine, same as Pine
        if shock[i] and not np.isnan(build_up[i]):
            last, m_cur, b_cur = i, s[i], build_up[i]
        a = i - last
        if a <= p["episode"]:
            age[i], M[i], B[i] = a, m_cur, b_cur
    live = ~np.isnan(age)
    w = np.where(live, (1 + np.nan_to_num(age)) ** (-p["decay_p"]), 0.0)
    F["h1_live"] = live.astype(float)
    F["h1_M"] = np.where(live, np.nan_to_num(M) * w, 0.0)        # shock memory (Omori-type)
    F["h1_B"] = np.where(live, np.nan_to_num(B) * w, 0.0)        # build-up (endo-ness) memory
    F["h1_BM"] = np.where(live, np.nan_to_num(B) * np.nan_to_num(M) * w, 0.0)
    F["shock"] = shock.astype(float)
    F["age"] = age
    F["B_raw"] = B
    F["M_raw"] = M

    # ------------------------------------------------------------------------------
    # H2: critical slowing down (rolling AR(1) and variance of x, return autocorrelation)
    # ------------------------------------------------------------------------------
    W = p["csd_w"]
    xs, xl = pd.Series(x), pd.Series(x).shift(1)
    F["h2_rho_x"] = xs.rolling(W).corr(xl).to_numpy()
    F["h2_var_x"] = xs.rolling(W).var().to_numpy()
    F["h2_drho"] = F["h2_rho_x"] - F["h2_rho_x"].shift(W)
    zs = pd.Series(z)
    F["h2_rho_r"] = zs.rolling(W).corr(zs.shift(1)).to_numpy()

    # ------------------------------------------------------------------------------
    # H4: intrabar path / volume structure (requires lower-timeframe data)
    # ------------------------------------------------------------------------------
    if intrabar is not None:
        ib = intrabar.reindex(idx)
        conc = np.log(ib["n"] * ib["V2"] / (ib["V"] ** 2 + 1e-18) + 1e-12)   # 0 = uniform volume
        path = np.log(ib["sum_lr"] / (rng + 1e-12) + 1e-12)                 # intrabar path excess
        F["h4_conc"] = conc.to_numpy()
        F["h4_conc6"] = roll_mean(conc.to_numpy(), 6)
        F["h4_path"] = path.to_numpy()
        F["h4_path6"] = roll_mean(path.to_numpy(), 6)

    # ------------------------------------------------------------------------------
    # H3: cross-asset systematic share (reference asset, same timeframe)
    # ------------------------------------------------------------------------------
    if ref is not None:
        rb = ref.reindex(idx)
        rbr = np.log(rb["c"] / rb["c"].shift(1)).to_numpy()
        A, Bs = pd.Series(r), pd.Series(rbr)
        Wx = p["xa_w"]
        cov = A.rolling(Wx).cov(Bs)
        var = Bs.rolling(Wx).var()
        beta = (cov / var).shift(1)                 # beta estimated strictly before bar t
        corr = A.rolling(Wx).corr(Bs).shift(1)
        e = A - beta * Bs
        se = e.rolling(Wx).std().shift(1)
        k = p["xa_k"]
        ek = e.rolling(k).sum() / (se * np.sqrt(k))
        F["h3_R2"] = (corr ** 2).to_numpy()
        F["h3_e"] = ek.to_numpy()
        F["h3_eabs"] = np.abs(ek).to_numpy()
        F["h3_refret"] = (Bs.rolling(k).sum() / (Bs.rolling(Wx).std() * np.sqrt(k))).to_numpy()

    # ------------------------------------------------------------------------------
    # Targets (forward-looking; never used as features)
    # ------------------------------------------------------------------------------
    gapf = gap.astype(float)
    for HH, tag in ((p["H"], ""), (p["H_long"], "L")):
        crosses = fwd_sum(gapf, HH) > 0             # forward window crosses a session gap
        # profile value for future buckets as known at t: the profile entry for bucket
        # tau(t+k) was last updated one day earlier (< t) because HH < bars per day.
        f_rng = fwd_sum(rng, HH)
        f_exp = fwd_sum(sig, HH)
        # same causal floor as the features (eps known at t); protects flat/outage windows
        y = np.log((f_rng + HH * eps) / f_exp)
        y[crosses] = np.nan
        F[f"y_vol{tag}"] = y
        if tag == "":
            f_r = fwd_sum(r, HH)
            f_rv = fwd_sum(r ** 2, HH)
            eff = np.abs(f_r) / np.sqrt(f_rv + 1e-18)
            eff[crosses] = np.nan
            F["y_eff"] = eff
            yr = f_r / (sig * np.sqrt(HH))
            yr[crosses] = np.nan
            F["y_ret"] = yr
            F["y_ret_raw"] = np.where(crosses, np.nan, f_r)
            fx = fwd_max(x, HH)
            ev = (fx > p["shock_theta"]).astype(float)
            ev[np.isnan(fx) | crosses] = np.nan
            F["y_tail"] = ev
    F["rv_fwd"] = fwd_sum(r ** 2, p["H"])            # realised variance proxy for QLIKE
    F["sig"] = sig
    F["day"] = idx.floor("D")

    # warm-up
    start = idx[0] + pd.Timedelta(days=p["warmup_days"])
    return F[F.index >= start]


# feature groups ---------------------------------------------------------------------
HAR = ["x", "m6", "m48", "m288"]
KNOWN_NOVOL = HAR + ["zneg", "zabs6", "atr_ratio", "rsi_absdev", "eff_past"]
VOL = ["u", "u6", "u48"]
H1_MEM = ["h1_live", "h1_M"]                 # shock memory only (fair add-on to baseline)
H1_ENDO = ["h1_B", "h1_BM"]                  # the novel endo/exo component
H2 = ["h2_rho_x", "h2_var_x", "h2_drho", "h2_rho_r"]
H3 = ["h3_R2", "h3_eabs"]
H3_DIR = ["h3_e", "h3_refret"]
H4 = ["h4_conc", "h4_conc6", "h4_path", "h4_path6"]
