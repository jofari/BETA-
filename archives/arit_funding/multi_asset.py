#!/usr/bin/env python3
"""Multi-actifs : momentum (robustesse lookback) + funding x momentum, train/holdout."""
import csv, time
import numpy as np
import pandas as pd

OUT = "/root/arit_funding"
FEE = 0.0005
SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
LOOKBACKS = [7, 14, 30, 60, 90]

def load(sym):
    c = {}
    with open(f"{OUT}/daily_{sym}.csv") as fh:
        for r in csv.DictReader(fh):
            d = time.strftime("%Y-%m-%d", time.gmtime(int(r["openTime"]) / 1000))
            c[d] = float(r["close"])
    s = pd.Series(c).sort_index()
    s.index = pd.to_datetime(s.index)
    return s

def bt(signal, logr, fee=FEE):
    signal = signal.reindex(logr.index).fillna(0.0)
    pos = signal.shift(1).fillna(0.0)
    ret = pos * logr - pos.diff().abs().fillna(0.0) * fee
    eq = ret.cumsum().apply(np.exp); eq = eq / eq.iloc[0]
    n = int((pos.diff().abs() > 0).sum())
    cagr = eq.iloc[-1] ** (365 / len(eq)) - 1
    sharpe = (ret.mean() / ret.std() * np.sqrt(365)) if ret.std() > 0 else 0
    dd = (eq / eq.cummax() - 1).min()
    return cagr, sharpe, dd, n

print("=== MOMENTUM long-only : Sharpe par lookback et par actif (full sample, frais 0.05%) ===\n")
for sym in SYMS:
    c = load(sym)
    logr = np.log(c).diff().fillna(0.0)
    line = f"{sym:<9}"
    for lb in LOOKBACKS:
        sig = (c.pct_change(lb) > 0).astype(float)
        _, sh, _, _ = bt(sig, logr)
        line += f"  L{lb:>2}={sh:+5.2f}"
    # buy & hold
    bh = (c.iloc[-1] / c.iloc[0]) ** (365 / len(c)) - 1
    bh_sh = bh / (logr.std() * np.sqrt(365))
    print(f"{line}   | B&H Sharpe {bh_sh:+.2f}")

print("\n=== TRAIN/HOLDOUT (train < 2023, holdout >= 2023) : Sharpe L30 ===\n")
print(f"{'sym':<9}{'train':>8}{'holdout':>9}{'trades tr/hd':>16}")
for sym in SYMS:
    c = load(sym)
    logr = np.log(c).diff().fillna(0.0)
    sig = (c.pct_change(30) > 0).astype(float)
    tr = c.index < "2023-01-01"; hd = c.index >= "2023-01-01"
    _, s_tr, _, n_tr = bt(sig[tr], logr[tr])
    _, s_hd, _, n_hd = bt(sig[hd], logr[hd])
    print(f"{sym:<9}{s_tr:>+8.2f}{s_hd:>+9.2f}{f'{n_tr}/{n_hd}':>16}")

print("\n=== IC (Spearman) momentum lookback -> fwd 7j, par actif ===\n")
print(f"{'sym':<9}" + "".join(f"{'L'+str(lb):>8}" for lb in LOOKBACKS))
for sym in SYMS:
    c = load(sym)
    fwd7 = c.shift(-7) / c - 1
    line = f"{sym:<9}"
    for lb in LOOKBACKS:
        mom = c.pct_change(lb)
        sub = pd.concat([mom, fwd7], axis=1).dropna()
        ic = sub.corr(method="spearman").iloc[0, 1]
        line += f"{ic:>+8.3f}"
    print(line)

print("\n=== DÉBLOQUEUR funding : LONG mom30>0 vs LONG mom30>0 & funding<0 (squeeze) ===\n")
for sym in SYMS:
    c = load(sym)
    logr = np.log(c).diff().fillna(0.0)
    fund = {}
    with open(f"{OUT}/funding_{sym}.csv") as fh:
        for r in csv.DictReader(fh):
            d = time.strftime("%Y-%m-%d", time.gmtime(int(r["fundingTime"]) / 1000))
            fund.setdefault(d, []).append(float(r["fundingRate"]))
    fsum = pd.Series({d: sum(v) for d, v in fund.items()}).reindex(c.index).fillna(0.0)
    fsum.index = pd.to_datetime(fsum.index)
    mom = c.pct_change(30)
    sig_base = (mom > 0).astype(float)
    sig_filt = ((mom > 0) & (fsum < 0)).astype(float)
    c0, s0, d0, n0 = bt(sig_base, logr)
    c1, s1, d1, n1 = bt(sig_filt, logr)
    print(f"{sym:<9} base: Sharpe {s0:+.2f} (n={n0})  |  +fund<0: Sharpe {s1:+.2f} (n={n1})  DD {d0*100:.0f}%->{d1*100:.0f}%")
