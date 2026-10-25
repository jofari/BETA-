#!/usr/bin/env python3
"""Backtest momentum long vs momentum+squeeze (renfort funding bas) — daily BTC, frais inclus."""
import json, csv, time
import numpy as np
import pandas as pd

FEE = 0.0005  # taker futures 0.05%

def load_close():
    c = {}
    with open("/root/arit_funding/daily_BTCUSDT.csv") as fh:
        for r in csv.DictReader(fh):
            d = time.strftime("%Y-%m-%d", time.gmtime(int(r["openTime"]) / 1000))
            c[d] = float(r["close"])
    s = pd.Series(c).sort_index(); s.index = pd.to_datetime(s.index)
    return s

def load_funding():
    d = json.load(open("/root/ARIT2.0/user_data/data/macro/funding_BTCUSDT.json"))
    agg = {}
    for x in d:
        day = time.strftime("%Y-%m-%d", time.gmtime(int(x["fundingTime"]) / 1000))
        agg.setdefault(day, []).append(float(x["fundingRate"]))
    s = pd.Series({k: np.mean(v) for k, v in agg.items()}).sort_index()
    s.index = pd.to_datetime(s.index)
    return s

close = load_close()
logr = np.log(close).diff().fillna(0.0)
fund = load_funding().reindex(close.index).ffill()

mom30 = close.pct_change(30)
# décile de funding roulant (anti-look-ahead)
fund_rank = fund.rolling(252, min_periods=60).rank(pct=True)
squeeze = fund_rank <= 0.1   # shorts bondés

def bt(pos, logr=logr, fee=FEE):
    pos = pos.shift(1).fillna(0.0)
    ret = pos * logr - pos.diff().abs().fillna(0.0) * fee
    eq = ret.cumsum().apply(np.exp); eq = eq / eq.iloc[0]
    # win rate par "trade" (segments où pos != 0)
    n_trades = int((pos.diff().abs() > 0).sum())
    cagr = eq.iloc[-1] ** (365 / len(eq)) - 1
    sharpe = (ret.mean() / ret.std() * np.sqrt(365)) if ret.std() > 0 else 0
    dd = (eq / eq.cummax() - 1).min()
    return cagr, sharpe, dd, n_trades

# Version A : momentum long seul
posA = (mom30 > 0).astype(float)
# Version B : momentum long, renfort x2 quand shorts bondés (squeeze)
posB = (mom30 > 0).astype(float)
posB = posB.where(~squeeze, 2.0)   # x2 les jours de squeeze

for label, pos in [("A. momentum long seul", posA), ("B. + renfort x2 squeeze", posB)]:
    cagr, sh, dd, n = bt(pos)
    print(f"{label:<28} CAGR={cagr*100:+7.2f}%  Sharpe={sh:+5.2f}  MaxDD={dd*100:6.2f}%  trades={n}")

# split train/holdout
tr = close.index < "2023-01-01"; hd = close.index >= "2023-01-01"
print("\n--- train (<2023) / holdout (>=2023) ---")
for label, pos in [("A", posA), ("B", posB)]:
    c1, s1, d1, _ = bt(pos[tr], logr[tr])
    c2, s2, d2, _ = bt(pos[hd], logr[hd])
    print(f"{label}: train Sharpe {s1:+.2f} (DD {d1*100:.0f}%) | holdout Sharpe {s2:+.2f} (DD {d2*100:.0f}%)")

# RR et win rate de B vs A : retour moyen PAR JOUR EN POSITION (proxy)
def avg_ret_in_pos(pos):
    p = pos.shift(1).fillna(0.0)
    m = p != 0
    return logr[m].mean() * 365, (logr[m] > 0).mean()

for label, pos in [("A", posA), ("B", posB)]:
    ar, wr = avg_ret_in_pos(pos)
    print(f"{label}: retour annualisé EN POSITION {ar*100:+.2f}%, jours positifs {wr*100:.1f}%")
