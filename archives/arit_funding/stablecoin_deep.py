#!/usr/bin/env python3
"""Analyse approfondie stablecoins : délais optimaux, train/holdout, combo momentum."""
import json, csv, time
import numpy as np
import pandas as pd

def load_supply():
    d = json.load(open("/root/ARIT2.0/user_data/data/macro/stablecoins.json"))
    supp = {}
    for x in d:
        day = time.strftime("%Y-%m-%d", time.gmtime(int(x["date"])))
        supp[day] = float(x["totalCirculating"]["peggedUSD"])
    s = pd.Series(supp).sort_index(); s.index = pd.to_datetime(s.index)
    return s

def load_close():
    c = {}
    with open("/root/arit_funding/daily_BTCUSDT.csv") as fh:
        for r in csv.DictReader(fh):
            d = time.strftime("%Y-%m-%d", time.gmtime(int(r["openTime"]) / 1000))
            c[d] = float(r["close"])
    s = pd.Series(c).sort_index(); s.index = pd.to_datetime(s.index)
    return s

sup = load_supply()
btc = load_close()
df = pd.concat([sup.rename("supply"), btc.rename("btc")], axis=1).dropna()

g30 = df["supply"].pct_change(30)
mom30 = df["btc"].pct_change(30)
logr = np.log(df["btc"]).diff().fillna(0.0)

# --- 1. Structure des délais : IC(g30, retour sur horizon h) ---
print("=== IC(offre growth 30j, retour BTC horizon h) ===")
for h in [3, 7, 14, 30, 60, 90]:
    f = df["btc"].shift(-h) / df["btc"] - 1
    sub = pd.concat([g30, f], axis=1).dropna()
    ic = sub.corr(method="spearman").iloc[0, 1]
    print(f"  horizon {h:>2}j : IC = {ic:+.3f}")

# --- 2. Train / holdout (le test de robustesse) ---
print("\n=== train (<2023) vs holdout (>=2023) : IC(offre growth 30j, retour 30j) ===")
tr = df.index < "2023-01-01"; hd = df.index >= "2023-01-01"
for label, mask in [("train", tr), ("holdout", hd)]:
    f30 = df["btc"].shift(-30) / df["btc"] - 1
    sub = pd.concat([g30[mask], f30[mask]], axis=1).dropna()
    ic = sub.corr(method="spearman").iloc[0, 1]
    print(f"  {label:<8}: IC = {ic:+.3f} (n={len(sub)})")

# --- 3. Combo : stablecoin growth + momentum (long quand les DEUX positifs) ---
print("\n=== combo (long = offre growth 30j > 0 ET momentum 30j > 0), retour 7j ===")
def meanr(mask):
    m = mask & (df["btc"].shift(-7).notna())
    return df["btc"].shift(-7)[m].mean() / df["btc"][m].mean(), int(m.sum())

for label, mask in [
    ("baseline (tous les jours)", pd.Series(True, index=df.index)),
    ("momentum seul (>0)", mom30 > 0),
    ("offre growth seul (>0)", g30 > 0),
    ("LES DEUX (>0)", (mom30 > 0) & (g30 > 0)),
    ("momentum>0 ET offre qui ACCELERE", (mom30 > 0) & (g30 > g30.rolling(30).mean())),
]:
    r7 = df["btc"].shift(-7) / df["btc"] - 1
    m = mask & r7.notna()
    print(f"  {label:<38} {r7[m].mean()*100:+6.2f}%  (n={int(m.sum())})")

# --- 4. backtest simple : long si les deux positifs, cash sinon ---
print("\n=== backtest simple (frais 0.05%) : momentum vs momentum+stablecoins ===")
FEE = 0.0005
def bt(signal):
    pos = signal.shift(1).fillna(0.0).astype(float)
    ret = pos * logr - pos.diff().abs().fillna(0.0) * FEE
    eq = ret.cumsum().apply(np.exp); eq = eq / eq.iloc[0]
    sharpe = (ret.mean() / ret.std() * np.sqrt(365)) if ret.std() > 0 else 0
    dd = (eq / eq.cummax() - 1).min()
    return sharpe, dd, eq.iloc[-1]** (365/len(eq)) - 1

sig_mom = (mom30 > 0).astype(float)
sig_both = ((mom30 > 0) & (g30 > 0)).astype(float)
for label, sig in [("momentum seul", sig_mom), ("momentum + stablecoins", sig_both)]:
    sh, dd, cagr = bt(sig)
    print(f"  {label:<22} Sharpe={sh:+.2f}  DD={dd*100:6.1f}%  CAGR={cagr*100:+6.1f}%")
