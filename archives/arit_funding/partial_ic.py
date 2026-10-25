#!/usr/bin/env python3
"""Vérifie si l'on-chain ajoute du signal AU-DELÀ du momentum (corrélation partielle)."""
import numpy as np
import pandas as pd

OUT = "/root/arit_funding"

price = pd.read_csv(f"{OUT}/onchain_price.csv")
price["date"] = pd.to_datetime(price["ts"], unit="s")
price = price.set_index("date")["value"].rename("price").resample("1D").last().dropna()

def load_metric(fname):
    s = pd.read_csv(f"{OUT}/{fname}")
    s["date"] = pd.to_datetime(s["ts"], unit="s")
    return s.set_index("date")["value"].resample("1D").last().reindex(price.index).ffill()

addr = load_metric("onchain_addresses.csv")
mempool = load_metric("onchain_mempool.csv")
ntx = load_metric("onchain_ntx.csv")

mom30 = price.pct_change(30)           # momentum 30j
addr_g = addr.pct_change(30)           # croissance adresses 30j
mempool_g = mempool.pct_change(30)
ntx_g = ntx.pct_change(30)

# corrélation feature<->momentum (sont-ils redondants ?)
def spear(a, b):
    sub = pd.concat([a, b], axis=1).dropna()
    return sub.corr(method="spearman").iloc[0, 1]

print("=== Redondance avec le momentum (Spearman) ===")
print(f"addr_growth  vs momentum30 : {spear(addr_g, mom30):+.3f}")
print(f"mempool_growth vs momentum30: {spear(mempool_g, mom30):+.3f}")
print(f"ntx_growth   vs momentum30 : {spear(ntx_g, mom30):+.3f}")

# IC partiel : corrélation du résidu de feature (après régression sur momentum) vs fwd return
from numpy.linalg import lstsq

def partial_ic(feat, mom, fwd_days):
    fwd = price.shift(-fwd_days) / price - 1
    sub = pd.concat([feat, mom, fwd], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    X = sub.iloc[:, :2].values.astype(float)
    y = sub.iloc[:, 2].values.astype(float)
    A = np.column_stack([np.ones(len(X)), X[:, 1]])
    coef, *_ = lstsq(A, y, rcond=None)
    resid_y = y - A @ coef
    coef2, *_ = lstsq(A, X[:, 0], rcond=None)
    resid_x = X[:, 0] - A @ coef2
    return np.corrcoef(resid_x, resid_y)[0, 1], len(X)

print("\n=== IC partiel (feature APRES contrôle du momentum) vs fwd return ===")
for name, feat in [("addr growth 30j", addr_g), ("mempool growth 30j", mempool_g),
                   ("ntx growth 30j", ntx_g)]:
    p7, n7 = partial_ic(feat, mom30, 7)
    p30, n30 = partial_ic(feat, mom30, 30)
    print(f"{name:<20} IC partiel 7j={p7:+.3f}  30j={p30:+.3f}  (n={n7})")

# taille d'échantillon
print(f"\nn (jours full history) = {len(price)}")
