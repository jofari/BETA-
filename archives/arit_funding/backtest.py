#!/usr/bin/env python3
"""Backtest de la règle momentum x volatilité — train/holdout + frais, BTC/USDT daily 7 ans."""
import csv, time
import numpy as np
import pandas as pd

OUT = "/root/arit_funding"
FEE = 0.0005  # taker futures 0.05% par côté

# ---- chargement ----
rows = []
with open(f"{OUT}/daily.csv") as fh:
    for r in csv.DictReader(fh):
        rows.append((int(r["openTime"]), float(r["close"])))
rows.sort()
df = pd.DataFrame({"ts": [r[0] for r in rows], "close": [r[1] for r in rows]})
df["date"] = pd.to_datetime(df["ts"], unit="ms")
df = df.set_index("date")

c = df["close"]
logr = np.log(c).diff().fillna(0.0)          # 1er jour : 0

# ---- features (pas de look-ahead) ----
mom_30 = c.pct_change(30)
vol_30 = logr.rolling(30).std() * np.sqrt(365)          # vol réalisée annualisée
vol_med_252 = vol_30.rolling(252, min_periods=60).median()  # médiane mobile 1 an

def backtest(signal, fee=FEE, logr=None):
    """signal: +1 long, -1 short, 0 flat, décidé sur close(t), appliqué à partir de t+1."""
    if logr is None:
        logr = globals()["logr"]
    signal = signal.reindex(logr.index).fillna(0.0)
    pos = signal.shift(1).fillna(0.0)
    ret = pos * logr
    # frais sur changement de position
    turnover = pos.diff().abs().fillna(0.0)
    ret = ret - turnover * fee
    eq = ret.cumsum().apply(np.exp)
    eq = eq / eq.iloc[0]
    # métriques
    n_trades = int((pos.diff().abs() > 0).sum())
    ann_ret = eq.iloc[-1] ** (365 / len(eq)) - 1
    ann_vol = ret.std() * np.sqrt(365)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
    dd = (eq / eq.cummax() - 1).min()
    return dict(ann_ret=ann_ret, sharpe=sharpe, maxdd=dd, n_trades=n_trades,
                eq=eq, ret=ret, pos=pos)

def report(name, res):
    print(f"{name:<34} CAGR={res['ann_ret']*100:+7.2f}%  Sharpe={res['sharpe']:+5.2f}  "
          f"MaxDD={res['maxdd']*100:6.2f}%  trades={res['n_trades']:4d}")

# signaux
lowvol = vol_30 < vol_med_252
sig_mom_long = (mom_30 > 0).astype(float)
sig_mom_vol_long = ((mom_30 > 0) & lowvol).astype(float)
sig_longshort = pd.Series(np.where(mom_30 > 0, 1.0, np.where(mom_30 < 0, -1.0, 0.0)), index=mom_30.index)
sig_longshort_vol = pd.Series(np.where((mom_30 > 0) & lowvol, 1.0,
                                      np.where((mom_30 < 0) & lowvol, -1.0, 0.0)), index=mom_30.index)

# buy & hold
bh_ret = logr.sum()
bh_ann = (c.iloc[-1] / c.iloc[0]) ** (365 / len(c)) - 1
bh_dd = (c / c.cummax() - 1).min()
print("=== BTC/USDT daily 2019-09 -> 2026-09 (frais taker 0.05%/côté) ===")
print(f"{'BUY & HOLD':<34} CAGR={bh_ann*100:+7.2f}%  Sharpe={bh_ann/(logr.std()*np.sqrt(365)):+5.2f}  MaxDD={bh_dd*100:6.2f}%")
print()

for label, sig in [
    ("LONG mom30>0 (sans filtre vol)", sig_mom_long),
    ("LONG mom30>0 & vol basse", sig_mom_vol_long),
    ("LONG/SHORT mom30 (sans filtre)", sig_longshort),
    ("LONG/SHORT mom30 & vol basse", sig_longshort_vol),
]:
    report(label, backtest(sig))

# ---- split train/holdout ----
print("\n=== SPLIT : train 2019-09->2022-12 / holdout 2023-01->2026-09 ===")
train = df.index < "2023-01-01"
hold = df.index >= "2023-01-01"
for label, sig in [("LONG mom30>0", sig_mom_long),
                   ("LONG mom30>0 & vol basse", sig_mom_vol_long),
                   ("L/S mom30 & vol basse", sig_longshort_vol)]:
    rt = backtest(sig[train], logr=logr[train])
    rh = backtest(sig[hold], logr=logr[hold])
    print(f"{label:<28} TRAIN: CAGR={rt['ann_ret']*100:+6.2f}% Sharpe={rt['sharpe']:+5.2f} DD={rt['maxdd']*100:5.2f}% | "
          f"HOLD: CAGR={rh['ann_ret']*100:+6.2f}% Sharpe={rh['sharpe']:+5.2f} DD={rh['maxdd']*100:5.2f}%")

# ---- le rôle du filtre vol : delta ----
print("\n=== Contribution du filtre volatilité (LONG, full sample) ===")
r_nofilt = backtest(sig_mom_long)
r_filt = backtest(sig_mom_vol_long)
print(f"sans filtre vol : Sharpe {r_nofilt['sharpe']:+.2f}, MaxDD {r_nofilt['maxdd']*100:.2f}%, trades {r_nofilt['n_trades']}")
print(f"avec filtre vol : Sharpe {r_filt['sharpe']:+.2f}, MaxDD {r_filt['maxdd']*100:.2f}%, trades {r_filt['n_trades']}")

# exposition
print(f"\nexposition temporelle (fraction du temps en position) :")
print(f"  LONG mom30>0 seul        : {(sig_mom_long==1).mean()*100:.1f}%")
print(f"  LONG mom30>0 & vol basse : {(sig_mom_vol_long==1).mean()*100:.1f}%")
