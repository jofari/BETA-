#!/usr/bin/env python3
"""Chasse aux données : on-chain (2009+) + basis futures (2019+), test de pouvoir prédictif."""
import csv, json, time, urllib.request
import numpy as np
import pandas as pd

OUT = "/root/arit_funding"

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def get_chart(name, outfile):
    d = get(f"https://api.blockchain.info/charts/{name}?timespan=all&format=json")
    vals = [(v["x"], v["y"]) for v in d["values"]]
    with open(f"{OUT}/{outfile}", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["ts", "value"])
        for x, y in vals: w.writerow([x, y])
    print(f"{name}: {len(vals)} pts")
    return vals

# ---- récupérer les métriques on-chain (full history) ----
METRICS = {
    "market-price": "onchain_price.csv",
    "hash-rate": "onchain_hashrate.csv",
    "n-unique-addresses": "onchain_addresses.csv",
    "n-transactions": "onchain_ntx.csv",
    "mempool-size": "onchain_mempool.csv",
    "difficulty": "onchain_difficulty.csv",
    "estimated-transaction-volume-usd": "onchain_txvol.csv",
}
for m, f in METRICS.items():
    try:
        get_chart(m, f)
    except Exception as e:
        print(f"{m}: ERROR {e}")

# ---- base prix (blockchain.com, 2009+) ----
price = pd.read_csv(f"{OUT}/onchain_price.csv")
price["date"] = pd.to_datetime(price["ts"], unit="s")
price = price.set_index("date")["value"].rename("price").resample("1D").last().dropna()
logr = np.log(price).diff().fillna(0.0)

def load_metric(fname):
    s = pd.read_csv(f"{OUT}/{fname}")
    s["date"] = pd.to_datetime(s["ts"], unit="s")
    return s.set_index("date")["value"].resample("1D").last().reindex(price.index).ffill()

def ic(feat, fwd_days):
    fwd = price.shift(-fwd_days) / price - 1
    sub = pd.concat([feat, fwd], axis=1).dropna()
    if len(sub) < 60:
        return np.nan
    return sub.corr(method="spearman").iloc[0, 1]

print("\n=== IC (Spearman) — on-chain vs retour futur (full history) ===")
print(f"{'feature':<34}{'transfo':<18}{'IC 7j':>8}{'IC 30j':>8}")

def report(name, feat, transfo):
    print(f"{name:<34}{transfo:<18}{ic(feat, 7):>+8.3f}{ic(feat, 30):>+8.3f}")

hashrate = load_metric("onchain_hashrate.csv")
addr = load_metric("onchain_addresses.csv")
ntx = load_metric("onchain_ntx.csv")
mempool = load_metric("onchain_mempool.csv")
diff = load_metric("onchain_difficulty.csv")
txvol = load_metric("onchain_txvol.csv")

# raw levels
report("hashrate (niveau)", hashrate, "niveau")
report("hashrate drawdown ATH", hashrate / hashrate.cummax() - 1, "drawdown")
report("hashrate growth 30j", hashrate.pct_change(30), "growth 30j")
report("unique addresses (niveau)", addr, "niveau")
report("unique addr growth 30j", addr.pct_change(30), "growth 30j")
report("n-transactions (niveau)", ntx, "niveau")
report("n-transactions growth 30j", ntx.pct_change(30), "growth 30j")
report("mempool size (niveau)", mempool, "niveau")
report("difficulty drawdown ATH", diff / diff.cummax() - 1, "drawdown")
report("tx volume USD (niveau)", txvol, "niveau")
report("tx volume growth 30j", txvol.pct_change(30), "growth 30j")

# ---- basis futures (2019+) ----
print("\n=== BASIS futures (fut - spot, annualisé) — IC vs retour (2019+) ===")
# spot depuis api.binance
def get_spot():
    kl, start = [], 1500000000000
    while True:
        url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=1000&startTime={start}"
        b = get(url)
        if not b: break
        kl.extend(b)
        if len(b) < 1000: break
        start = b[-1][0] + 1
        time.sleep(0.15)
    return [(k[0], float(k[4])) for k in kl]

spot_rows = get_spot()
spot = pd.Series({pd.to_datetime(ts, unit="ms").date(): p for ts, p in spot_rows}).sort_index()
spot.index = pd.to_datetime(spot.index)

fut = pd.read_csv(f"{OUT}/daily_BTCUSDT.csv")
fut["date"] = pd.to_datetime(fut["openTime"], unit="ms")
fut = fut.set_index("date")["close"]

aligned = pd.concat([fut.rename("fut"), spot.rename("spot")], axis=1).dropna()
basis = (aligned["fut"] - aligned["spot"]) / aligned["spot"] * 365 * 100  # % annualisé
# price du fut comme référence
p = aligned["fut"]
pl = np.log(p).diff().fillna(0.0)

def ic_basis(feat, fwd):
    f = p.shift(-fwd) / p - 1
    sub = pd.concat([feat, f], axis=1).dropna()
    return sub.corr(method="spearman").iloc[0, 1] if len(sub) > 60 else np.nan

print(f"{'feature':<30}{'IC 7j':>8}{'IC 30j':>8}")
print(f"{'basis niveau':<30}{ic_basis(basis, 7):>+8.3f}{ic_basis(basis, 30):>+8.3f}")
print(f"{'basis change 7j':<30}{ic_basis(basis.diff(7), 7):>+8.3f}{ic_basis(basis.diff(7), 30):>+8.3f}")
# extrêmes : basis > seuil
hi = basis.rolling(252, min_periods=30).quantile(0.8)
print(f"{'basis extrême (top 20%): niveau':<30}{ic_basis(basis - hi, 7):>+8.3f}{ic_basis(basis - hi, 30):>+8.3f}")

# stats descriptives du basis
print(f"\nbasis moyen: {basis.mean():+.2f}%/an, médian {basis.median():+.2f}%, min {basis.min():+.2f}%, max {basis.max():+.2f}%")
