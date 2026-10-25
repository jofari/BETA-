#!/usr/bin/env python3
"""Test : momentum (direction) + retail bondé (timing/ajustement).

Question de Jonas : en position long (momentum>0), le fait que les retail soient bondés
change-t-il la suite ?  ->  bondés AVEC nous = trim (prendre son cash) ?
                            bondés CONTRE nous = add (renforcer, squeeze) ?
"""
import json, csv, time
import numpy as np
import pandas as pd

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
fund = load_funding().reindex(close.index).ffill()

mom30 = close.pct_change(30)
fwd7 = close.shift(-7) / close - 1
long = mom30 > 0

# déciles de funding ROULANTS (252j) pour éviter le look-ahead
fund_rank = fund.rolling(252, min_periods=60).rank(pct=True)
fund_hi = fund_rank >= 0.9      # retail bondés long (avec nous, si on est long)
fund_lo = fund_rank <= 0.1      # retail bondés short (contre nous)

last = close.index >= (close.index.max() - pd.Timedelta(days=365))

def m(mask, h):
    m2 = mask & h.notna()
    return (h[m2].mean(), int(m2.sum())) if m2.sum() else (None, 0)

print("=== BTC — position LONG (momentum 30j > 0), retour 7j selon le positionnement retail ===\n")
print(f"{'cas':<44}{'fwd7':>9}{'n':>6}")

for label, mask_l in [
    ("LONG seul (baseline)", long & last),
    ("LONG + retail bondés AVEC (fund haut)", long & fund_hi & last),
    ("LONG + retail bondés CONTRE (fund bas)", long & fund_lo & last),
]:
    m7, n = m(mask_l, fwd7)
    print(f"{label:<44}{f'{m7*100:+.2f}%':>9}{n:>6}")

# full-history (2019+), mêmes masques sans le filtre "last"
print("\n--- référence 2019+ (marché complet, bull inclus) ---")
for label, mask_f in [
    ("LONG seul", long),
    ("LONG + retail bondés AVEC (fund haut)", long & fund_hi),
    ("LONG + retail bondés CONTRE (fund bas)", long & fund_lo),
]:
    m7, n = m(mask_f, fwd7)
    print(f"{label:<44}{f'{m7*100:+.2f}%':>9}{n:>6}")
