#!/usr/bin/env python3
"""Funding x momentum : grille 3x3 (quintile funding relatif x signe momentum) -> fwd 7j, multi-actifs."""
import csv, time
import numpy as np
import pandas as pd

OUT = "/root/arit_funding"
SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]

def load(sym):
    c = {}
    with open(f"{OUT}/daily_{sym}.csv") as fh:
        for r in csv.DictReader(fh):
            d = time.strftime("%Y-%m-%d", time.gmtime(int(r["openTime"]) / 1000))
            c[d] = float(r["close"])
    s = pd.Series(c).sort_index(); s.index = pd.to_datetime(s.index)
    return s

for sym in SYMS:
    c = load(sym)
    fwd7 = c.shift(-7) / c - 1
    mom14 = c.pct_change(14)
    # funding journalier MOYEN (pas somme), reindexé
    fund = {}
    with open(f"{OUT}/funding_{sym}.csv") as fh:
        for r in csv.DictReader(fh):
            d = time.strftime("%Y-%m-%d", time.gmtime(int(r["fundingTime"]) / 1000))
            fund.setdefault(d, []).append(float(r["fundingRate"]))
    fmean = pd.Series({d: np.mean(v) for d, v in fund.items()}).sort_index()
    fmean.index = pd.to_datetime(fmean.index)
    fmean = fmean.reindex(c.index).ffill()

    df = pd.DataFrame({"fwd7": fwd7, "mom14": mom14, "fund": fmean}).dropna()
    # quintile relatif de funding (rolling 252j pour éviter le look-ahead)
    df["fund_q"] = pd.qcut(df["fund"].rolling(252, min_periods=60).rank(pct=True).shift(1),
                           [0, .2, .8, 1.0], labels=["fund bas", "fund moy", "fund haut"])
    df["mom_s"] = np.where(df["mom14"] > 0, "mom+", "mom-")
    piv = df.groupby(["fund_q", "mom_s"], observed=True)["fwd7"].agg(["mean", "count"])
    print(f"=== {sym} ===  fwd 7j (moyenne %, n)")
    print(piv.to_string())
    print()
