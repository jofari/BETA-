#!/usr/bin/env python3
"""Test : RORO (appétit pour le risque, KC Fed) prédit-il le BTC ?
Hypothèse 'envie des marchés' : risk-on => argent vers le risque => BTC monte."""
import csv, time
import numpy as np
import pandas as pd

# KCRORO (2003+)
rro = pd.read_csv("/root/arit_funding/kcrro.csv")
rro["date"] = pd.to_datetime(rro["observation_date"])
rro = rro.set_index("date")["KCRORO"]

# BTC daily (Binance futures, 2019+, propre)
def load_close():
    c = {}
    with open("/root/arit_funding/daily_BTCUSDT.csv") as fh:
        for r in csv.DictReader(fh):
            d = time.strftime("%Y-%m-%d", time.gmtime(int(r["openTime"]) / 1000))
            c[d] = float(r["close"])
    s = pd.Series(c).sort_index(); s.index = pd.to_datetime(s.index)
    return s

price = load_close()

# aligner
df = pd.concat([rro.rename("rro"), price.rename("btc")], axis=1).dropna()
print(f"période alignée : {df.index.min().date()} -> {df.index.max().date()} ({len(df)} jours)")

btc = df["btc"]
fwd = {h: btc.shift(-h) / btc - 1 for h in (1, 3, 7, 14)}

def spear(a, b):
    sub = pd.concat([a, b], axis=1).dropna()
    return sub.corr(method="spearman").iloc[0, 1]

print("\n=== IC (Spearman) RORO vs retour BTC futur ===")
print(f"{'feature':<28}{'fwd1':>8}{'fwd3':>8}{'fwd7':>8}{'fwd14':>8}")
for name, f in [
    ("RORO niveau", df["rro"]),
    ("RORO change 7j", df["rro"].diff(7)),
    ("RORO change 30j", df["rro"].diff(30)),
]:
    print(f"{name:<28}" + "".join(f"{spear(f, fwd[h]):>+8.3f}" for h in (1, 3, 7, 14)))

# risk-on vs risk-off : RORO > 0 (risk-on) vs < 0 (risk-off)
print("\n=== RORO positif (risk-on) vs négatif (risk-off) -> retour BTC 7j ===")
ron = df["rro"] > 0
roff = df["rro"] < 0
def meanr(mask):
    m = mask & fwd[7].notna()
    return (fwd[7][m].mean()*100, int(m.sum()))
mr_on, n_on = meanr(ron)
mr_off, n_off = meanr(roff)
print(f"risk-on  (RORO>0): {mr_on:+.2f}% (n={n_on})")
print(f"risk-off (RORO<0): {mr_off:+.2f}% (n={n_off})")

# extrêmes : RORO très haut / très bas (quartiles)
q = df["rro"].quantile([0.1, 0.9])
hi = df["rro"] >= q[0.9]
lo = df["rro"] <= q[0.1]
mh, nh = meanr(hi)
ml, nl = meanr(lo)
print(f"RORO top 10% (euphorie risque): {mh:+.2f}% (n={nh})")
print(f"RORO bot 10% (panique risque): {ml:+.2f}% (n={nl})")
