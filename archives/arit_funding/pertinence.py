#!/usr/bin/env python3
"""Étude de pertinence des features : IC (Spearman) feature vs retour futur, + combinaisons."""
import csv, time
import numpy as np
import pandas as pd
from scipy import stats

OUT = "/root/arit_funding"

# ---- chargement ----
closes = {}
with open(f"{OUT}/daily.csv") as fh:
    for r in csv.DictReader(fh):
        d = time.strftime("%Y-%m-%d", time.gmtime(int(r["openTime"]) / 1000))
        closes[d] = float(r["close"])

fund = {}
with open(f"{OUT}/funding.csv") as fh:
    for r in csv.DictReader(fh):
        ts = int(r["fundingTime"])
        d = time.strftime("%Y-%m-%d", time.gmtime(ts / 1000))
        fund.setdefault(d, []).append(float(r["fundingRate"]))

df = pd.DataFrame({"date": sorted(closes.keys())})
df["close"] = df["date"].map(closes)
df["funding_sum"] = df["date"].map(lambda d: sum(fund.get(d, [])))
df["funding_mean"] = df["date"].map(lambda d: np.mean(fund.get(d, [])) if fund.get(d) else np.nan)

c = df["close"]
logr = np.log(c).diff()

# ---- features dérivées OHLCV ----
for n in (7, 14, 30):
    df[f"mom_{n}d"] = c.pct_change(n)
df["ema50"] = c.ewm(span=50, adjust=False).mean()
df["ema200"] = c.ewm(span=200, adjust=False).mean()
df["trend_ema"] = (df["ema50"] - df["ema200"]) / df["ema200"]      # pente tendance
df["pos_vs_ema200"] = (c - df["ema200"]) / df["ema200"]            # position vs tendance longue
# RSI(14) Wilder
delta = c.diff()
gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
df["rsi14"] = 100 - 100 / (1 + gain / loss)
# volatilité réalisée 30j
df["vol_30d"] = logr.rolling(30).std() * np.sqrt(365)
# range 14j (ATR proxy sur daily)
df["range_14d"] = (c.rolling(14).max() - c.rolling(14).min()) / c.rolling(14).mean()
# distance aux extrêmes 30j (mean-reversion)
df["dist_high_30"] = c / c.rolling(30).max() - 1
df["dist_low_30"] = c / c.rolling(30).min() - 1
# volume — pas de colonne volume daily chargée en float ici, on la relit
vol = {}
with open(f"{OUT}/daily.csv") as fh:
    for r in csv.DictReader(fh):
        d = time.strftime("%Y-%m-%d", time.gmtime(int(r["openTime"]) / 1000))
        vol[d] = float(r["volume"])
df["volume"] = df["date"].map(vol)
df["rel_vol"] = df["volume"] / df["volume"].rolling(20).mean()
# funding features
df["fund_roll7"] = df["funding_sum"].rolling(7).sum()   # crowding persistante 7j
df["fund_chg"] = df["funding_mean"].diff(7)             # accélération

# ---- retours futurs ----
for h in (1, 3, 7, 14):
    df[f"fwd_{h}d"] = c.shift(-h) / c - 1

FEATURES = ["mom_7d", "mom_14d", "mom_30d", "trend_ema", "pos_vs_ema200", "rsi14",
            "vol_30d", "range_14d", "dist_high_30", "dist_low_30", "rel_vol",
            "funding_sum", "funding_mean", "fund_roll7", "fund_chg"]

# ---- IC (Spearman) feature x horizon ----
print("=== IC (Spearman) feature vs retour futur — 7 ans BTC/USDT daily ===")
print(f"{'feature':<16}" + "".join(f"{'fwd'+str(h)+'d':>10}" for h in (1,3,7,14)) + f"{'|IC| max':>10}")
rows = []
for f in FEATURES:
    line = [f]
    ics = []
    for h in (1, 3, 7, 14):
        sub = df[[f, f"fwd_{h}d"]].dropna()
        ic = stats.spearmanr(sub[f], sub[f"fwd_{h}d"]).correlation
        ics.append(ic)
        line.append(f"{ic:+.3f}")
    best = max(ics, key=abs)
    line.append(f"{abs(best):.3f}")
    print(f"{f:<16}" + "".join(f"{ic:>+10.3f}" for ic in ics) + f"{abs(best):>10.3f}")
    rows.append((f, ics))

# note sur tests multiples
n_tests = len(FEATURES) * 4
print(f"\nNB: {n_tests} tests IC — seuil de significativité naïf |IC|≈0.05; "
      f"corrigé Bonferroni |IC|≈{2.58/np.sqrt(2500):.3f} (n~2500). "
      f"Beaucoup de petits IC = bruit, pas du signal.")

# ---- combinaisons : conditionner une feature par une autre ----
print("\n=== COMBINAISONS (IC d'une feature CONDITIONNÉE par une autre) ===")

def cond_ic(feat, cond, q_low, q_high, horizon=7):
    sub = df[[feat, cond, f"fwd_{horizon}d"]].dropna()
    lo = sub[cond].quantile(q_low)
    hi = sub[cond].quantile(q_high)
    low_part = sub[sub[cond] <= lo]
    high_part = sub[sub[cond] >= hi]
    ic_lo = stats.spearmanr(low_part[feat], low_part[f"fwd_{horizon}d"]).correlation if len(low_part) > 30 else np.nan
    ic_hi = stats.spearmanr(high_part[feat], high_part[f"fwd_{horizon}d"]).correlation if len(high_part) > 30 else np.nan
    return ic_lo, ic_hi, len(low_part), len(high_part)

combos = [
    ("mom_7d", "vol_30d", "momentum 7j conditionné par volatilité"),
    ("fund_roll7", "mom_7d", "funding 7j conditionné par momentum"),
    ("dist_low_30", "vol_30d", "distance au plus-bas 30j conditionné par vol"),
    ("rsi14", "vol_30d", "RSI conditionné par volatilité"),
    ("mom_30d", "vol_30d", "momentum 30j conditionné par volatilité"),
]
for feat, cond, label in combos:
    ic_lo, ic_hi, n_lo, n_hi = cond_ic(feat, cond, 0.25, 0.75)
    print(f"{label:<45} | IC(vol basse)={ic_lo:+.3f} (n={n_lo})  IC(vol haute)={ic_hi:+.3f} (n={n_hi})")

# ---- grille 3x3 : funding extrême x momentum ----
print("\n=== Grille : funding 7j (crowding) x momentum 14j → fwd 7j ===")
g = df[["fund_roll7", "mom_14d", "fwd_7d"]].dropna()
gf = pd.qcut(g["fund_roll7"], 3, labels=["fund bas", "fund moy", "fund haut"])
gm = pd.qcut(g["mom_14d"], 3, labels=["mom bas", "mom moy", "mom haut"])
piv = g.groupby([gf, gm], observed=True)["fwd_7d"].agg(["mean", "count"])
print(piv.to_string())
