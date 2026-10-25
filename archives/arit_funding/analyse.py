#!/usr/bin/env python3
"""Analyse : le funding rate prédit-il le retour futur du BTC ?"""
import csv, statistics, time
from collections import defaultdict

OUT = "/root/arit_funding"

def load_daily():
    closes = {}  # date(YYYY-MM-DD) -> close
    with open(f"{OUT}/daily.csv") as fh:
        for r in csv.DictReader(fh):
            d = time.strftime("%Y-%m-%d", time.gmtime(int(r["openTime"]) / 1000))
            closes[d] = float(r["close"])
    return closes

def load_funding():
    rows = []  # (ts_ms, rate)
    with open(f"{OUT}/funding.csv") as fh:
        for r in csv.DictReader(fh):
            rows.append((int(r["fundingTime"]), float(r["fundingRate"])))
    rows.sort()
    return rows

closes = load_daily()
funding = load_funding()
dates = sorted(closes.keys())
closes_list = [closes[d] for d in dates]
idx = {d: i for i, d in enumerate(dates)}

# Agréger le funding par jour (les 3 règlements 8h du jour UTC)
daily_funding = defaultdict(list)  # date -> [rates]
for ts, rate in funding:
    d = time.strftime("%Y-%m-%d", time.gmtime(ts / 1000))
    if d in idx:
        daily_funding[d].append(rate)

# Série alignée : date, close, funding_moyen_jour
days = [d for d in dates if d in daily_funding]
print(f"jours alignés funding+prix: {len(days)}")

def fwd_ret(day_idx, n):
    if day_idx + n >= len(closes_list):
        return None
    return closes_list[day_idx + n] / closes_list[day_idx] - 1.0

# ---- Test 1 : buckets par quintile de funding journalier ----
records = []  # (funding_mean, fwd1, fwd3, fwd7, fwd14)
for d in days:
    fm = statistics.mean(daily_funding[d])
    di = idx[d]
    records.append((fm, fwd_ret(di, 1), fwd_ret(di, 3), fwd_ret(di, 7), fwd_ret(di, 14)))

records.sort(key=lambda x: x[0])
n = len(records)
q = n // 5

def mean(xs):
    xs = [x for x in xs if x is not None]
    return (statistics.mean(xs), len(xs)) if xs else (None, 0)

def pct(x):
    return f"{x*100:+.2f}%" if x is not None else "  n/a "

print("\n=== Forward return par QUINTILE de funding journalier ===")
print(f"{'bucket':<22}{'funding moy':>12}{'n':>5}{'fwd 1j':>10}{'fwd 3j':>10}{'fwd 7j':>10}{'fwd 14j':>10}")
labels = ["Q1 (très bas)", "Q2", "Q3", "Q4", "Q5 (très haut)"]
for k in range(5):
    lo = k * q
    hi = (k + 1) * q if k < 4 else n
    chunk = records[lo:hi]
    fm = statistics.mean([r[0] for r in chunk])
    f1 = mean([r[1] for r in chunk])
    f3 = mean([r[2] for r in chunk])
    f7 = mean([r[3] for r in chunk])
    f14 = mean([r[4] for r in chunk])
    print(f"{labels[k]:<22}{fm*100:>10.4f}%{f7[1]:>5}"
          f"{pct(f1[0]):>10}{pct(f3[0]):>10}{pct(f7[0]):>10}{pct(f14[0]):>10}")

# ---- Test 2 : extrema ----
print("\n=== Extrêmes de funding ===")
def bucket_desc(lo, hi):
    return [r for r in records if lo <= r[0] < hi]

# funding négatif vs positif
neg = [r for r in records if r[0] < 0]
pos = [r for r in records if r[0] >= 0]
top5 = records[-max(1, n // 20):]
bot5 = records[:max(1, n // 20)]
print(f"funding NEGATIF  : n={len(neg):4}  fwd3j={pct(mean([r[2] for r in neg])[0])}  fwd7j={pct(mean([r[3] for r in neg])[0])}")
print(f"funding POSITIF  : n={len(pos):4}  fwd3j={pct(mean([r[2] for r in pos])[0])}  fwd7j={pct(mean([r[3] for r in pos])[0])}")
print(f"TOP 5%  funding  : n={len(top5):4}  fwd3j={pct(mean([r[2] for r in top5])[0])}  fwd7j={pct(mean([r[3] for r in top5])[0])}")
print(f"BOT 5%  funding  : n={len(bot5):4}  fwd3j={pct(mean([r[2] for r in bot5])[0])}  fwd7j={pct(mean([r[3] for r in bot5])[0])}")

# ---- Test 3 : corrélation linéaire funding vs fwd return ----
def pearson(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 10:
        return None, 0
    mx = statistics.mean([p[0] for p in pairs])
    my = statistics.mean([p[1] for p in pairs])
    num = sum((p[0]-mx)*(p[1]-my) for p in pairs)
    dx = sum((p[0]-mx)**2 for p in pairs)**0.5
    dy = sum((p[1]-my)**2 for p in pairs)**0.5
    return num/(dx*dy) if dx and dy else None, len(pairs)

for horizon, j in [("1j",1),("3j",2),("7j",3),("14j",4)]:
    c, nn = pearson([r[0] for r in records], [r[j] for r in records])
    print(f"corr(funding, fwd{horizon}) = {c:+.3f}  (n={nn})")

# ---- Test 4 : rendement annualisé équivalent du funding (contexte) ----
rates = [r[0] for r in records]
print(f"\nfunding moyen/an (raw, par 8h): {statistics.mean(rates)*3*365*100:+.2f}%")
print(f"funding médian: {statistics.median(rates)*100:+.4f}%")
