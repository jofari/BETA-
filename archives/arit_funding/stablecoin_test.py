#!/usr/bin/env python3
"""Test historique : l'offre de stablecoins (poudre sèche) prédit-elle le BTC ?
Hypothèse : offre qui monte = argent prêt à être déployé = bullish."""
import json, csv, time
import numpy as np
import pandas as pd

# stablecoins (DefiLlama)
d = json.load(open("/root/ARIT2.0/user_data/data/macro/stablecoins.json"))
supp = {}
for x in d:
    day = time.strftime("%Y-%m-%d", time.gmtime(int(x["date"])))
    supp[day] = float(x["totalCirculating"]["peggedUSD"])
sup = pd.Series(supp).sort_index(); sup.index = pd.to_datetime(sup.index)

# BTC close
c = {}
with open("/root/arit_funding/daily_BTCUSDT.csv") as fh:
    for r in csv.DictReader(fh):
        dd = time.strftime("%Y-%m-%d", time.gmtime(int(r["openTime"]) / 1000))
        c[dd] = float(r["close"])
btc = pd.Series(c).sort_index(); btc.index = pd.to_datetime(btc.index)

df = pd.concat([sup.rename("supply"), btc.rename("btc")], axis=1).dropna()
print(f"période : {df.index.min().date()} -> {df.index.max().date()} ({len(df)} jours)")

fwd = {h: df["btc"].shift(-h) / df["btc"] - 1 for h in (3, 7, 14, 30)}

def spear(a, b):
    sub = pd.concat([a, b], axis=1).dropna()
    return sub.corr(method="spearman").iloc[0, 1] if len(sub) > 30 else np.nan

print("\n=== IC (Spearman) signal stablecoins vs retour BTC futur ===")
print(f"{'feature':<30}{'fwd3':>8}{'fwd7':>8}{'fwd14':>8}{'fwd30':>8}")
for name, f in [
    ("offre growth 7j", df["supply"].pct_change(7)),
    ("offre growth 14j", df["supply"].pct_change(14)),
    ("offre growth 30j", df["supply"].pct_change(30)),
    ("offre growth 90j", df["supply"].pct_change(90)),
    ("offre / prix BTC (niveau)", df["supply"] / df["btc"]),
]:
    print(f"{name:<30}" + "".join(f"{spear(f, fwd[h]):>+8.3f}" for h in (3, 7, 14, 30)))

# buckets par croissance 30j
print("\n=== croissance offre 30j en quintiles -> retour BTC 7j ===")
g30 = df["supply"].pct_change(30)
sub = pd.concat([g30.rename("g30"), fwd[7].rename("fwd7")], axis=1).dropna()
sub["q"] = pd.qcut(sub["g30"], 5, labels=["Q1 baisse", "Q2", "Q3", "Q4", "Q5 hausse"])
r = sub.groupby("q", observed=True)["fwd7"].agg(["mean", "count"])
for idx, row in r.iterrows():
    print(f"  {idx:<12} {row['mean']*100:+7.2f}%  (n={int(row['count'])})")

# --- LE test critique : indépendant du momentum, ou redondant ? ---
print("\n=== indépendance vs momentum ===")
mom30 = df["btc"].pct_change(30)
print(f"corr(offre growth 30j, momentum 30j) = {spear(g30, mom30):+.3f}")

# IC partiel : offre growth après contrôle du momentum
def partial_ic(feat, mom, horizon=30):
    sub2 = pd.concat([feat, mom, fwd[horizon]], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    X = sub2.iloc[:, :2].values.astype(float)
    y = sub2.iloc[:, 2].values.astype(float)
    A = np.column_stack([np.ones(len(X)), X[:, 1]])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    resid_y = y - A @ coef
    coef2, *_ = np.linalg.lstsq(A, X[:, 0], rcond=None)
    resid_x = X[:, 0] - A @ coef2
    return np.corrcoef(resid_x, resid_y)[0, 1]

print(f"IC offre growth 30j (brut)     : {spear(g30, fwd[30]):+.3f}")
print(f"IC offre growth 30j (après contrôle momentum) : {partial_ic(g30, mom30, 30):+.3f}")
