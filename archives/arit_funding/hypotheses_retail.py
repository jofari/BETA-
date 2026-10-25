#!/usr/bin/env python3
"""Mesure BRUTE des 3 hypothèses 'retail' — dernier an (et 2019+ en référence).

Hyp 1 "achètent les sommets"  : F&G extrême haut  -> retournement baissier attendu
Hyp 2 "sur-levier"            : funding extrême (les deux sens) -> retournement
Hyp 3 "paniquent aux creux"   : F&G extrême bas + funding négatif -> rebond haussier
"""
import json, csv, time
import numpy as np
import pandas as pd

def load_daily_close():
    c = {}
    with open("/root/arit_funding/daily_BTCUSDT.csv") as fh:
        for r in csv.DictReader(fh):
            d = time.strftime("%Y-%m-%d", time.gmtime(int(r["openTime"]) / 1000))
            c[d] = float(r["close"])
    s = pd.Series(c).sort_index(); s.index = pd.to_datetime(s.index)
    return s

def load_fng():
    d = json.load(open("/root/ARIT2.0/user_data/data/macro/fear_greed.json"))
    rows = {}
    for x in d["data"]:
        day = time.strftime("%Y-%m-%d", time.gmtime(int(x["timestamp"])))
        rows[day] = int(x["value"])
    s = pd.Series(rows).sort_index(); s.index = pd.to_datetime(s.index)
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

close = load_daily_close()
fng = load_fng().reindex(close.index).ffill()
fund = load_funding().reindex(close.index).ffill()

fwd7 = close.shift(-7) / close - 1
fwd14 = close.shift(-14) / close - 1

# bornes de l'an dernier
last = close.index >= (close.index.max() - pd.Timedelta(days=365))

def mean_fwd(mask, horizon):
    m = mask & horizon.notna()
    if m.sum() == 0:
        return None, 0
    return horizon[m].mean(), int(m.sum())

print("=== BTC/USDT — mesure brute (moyenne du retour futur) ===\n")
print(f"{'signal':<42}{'fwd7':>9}{'fwd14':>9}{'n (1an)':>9}   {'fwd7 2019+':>10}")

def report(name, mask_last, mask_full):
    m7, n7 = mean_fwd(mask_last, fwd7)
    m14, n14 = mean_fwd(mask_last, fwd14)
    m7f, _ = mean_fwd(mask_full, fwd7)
    print(f"{name:<42}{f'{m7*100:+.2f}%':>9}{f'{m14*100:+.2f}%':>9}{n7:>9}   {f'{m7f*100:+.2f}%':>10}")

# baseline : retour moyen inconditionnel
report("BASELINE (tous les jours)", last & fwd7.notna(), fwd7.notna())

# seuils (percentiles sur l'an dernier pour être relatif)
fg_q_hi = fng >= fng[last].quantile(0.8)
fg_q_lo = fng <= fng[last].quantile(0.2)
fund_hi = fund >= fund[last].quantile(0.9)
fund_lo = fund <= fund[last].quantile(0.1)

print("\n--- Hyp 1 : achètent les sommets (F&G greed) ---")
report("F&G top 20% (euphorie)          ", last & fg_q_hi, fg_q_hi)
report("F&G top 10% (euphorie extrême)  ", last & (fng >= fng[last].quantile(0.9)),
       fng >= fng[last].quantile(0.9))

print("\n--- Hyp 2 : sur-levier (funding extrême) ---")
report("funding top 10% (longs bondés)  ", last & fund_hi, fund_hi)
report("funding bottom 10% (shorts bondés)", last & fund_lo, fund_lo)

print("\n--- Hyp 3 : paniquent aux creux (F&G peur) ---")
report("F&G bottom 20% (peur)           ", last & fg_q_lo, fg_q_lo)
report("F&G bottom 10% (peur extrême)   ", last & (fng <= fng[last].quantile(0.1)),
       fng <= fng[last].quantile(0.1))

print("\n--- combinaisons (brut, juste pour voir) ---")
report("F&G bas ET funding bas          ", last & fg_q_lo & fund_lo, fg_q_lo & fund_lo)
report("F&G haut ET funding haut        ", last & fg_q_hi & fund_hi, fg_q_hi & fund_hi)
