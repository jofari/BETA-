"""Rotation de regime or / SPX / BTC — strategie 'toujours investi'.

Regime (preenregistre, pas de tuning) : percentile glissant 180j du VIX (causal).
  risk-off : VIX >= p67  -> surponderer OR     (20/60/20)
  risk-on  : VIX <= p33  -> surponderer SP500  (20/20/60)
  neutre   : entre les deux -> equi-reparti (1/3,1/3,1/3)
  base de depart : 33/33/33, toujours 100% investi.

Ponder pes a t-1 applique au rendement de t => zero look-ahead. Poids fixes = pas de
degagement de liberte => un seul test regle contre le statique.
"""
import numpy as np
import pandas as pd

from beta.lake.lecture import load, macro_globales

ORDER = ["BTC", "XAUUSD", "SP500"]
W = {
    "risk_off": np.array([0.20, 0.60, 0.20]),  # [BTC, XAU, SPX] -> surpondere OR
    "risk_on":  np.array([0.20, 0.20, 0.60]),  # surpondere SPX
    "neutral":  np.array([1 / 3, 1 / 3, 1 / 3]),
}
STATIC = np.array([1 / 3, 1 / 3, 1 / 3])


def weights_for(qv):
    if pd.isna(qv):
        return np.full(3, np.nan)
    if qv >= 2 / 3:
        return W["risk_off"]
    if qv <= 1 / 3:
        return W["risk_on"]
    return W["neutral"]


def metrics(r):
    r = r.dropna()
    n = len(r)
    cagr = (1 + r).prod() ** (252 / n) - 1
    vol = r.std() * np.sqrt(252)
    sharpe = r.mean() * np.sqrt(252) / r.std()
    cum = (1 + r).cumprod()
    maxdd = (cum / cum.cummax() - 1).min()
    return cagr, vol, sharpe, maxdd


def main() -> int:
    rets = {a: load(a, "1d").set_index("date")["close"].pct_change() for a in ORDER}
    R = pd.DataFrame(rets).dropna()

    g = macro_globales()
    vix = g["vix"].reindex(R.index).ffill()
    q = vix.rolling(180, min_periods=60).apply(lambda x: (x <= x[-1]).mean(), raw=True)

    wmat = pd.DataFrame([weights_for(x) for x in q], index=q.index, columns=ORDER)
    wmat = wmat.shift(1)  # regime connu a t-1

    strat = (R * wmat.values).sum(axis=1)
    stat = (R * STATIC).sum(axis=1)

    def report(name, r):
        cagr, vol, sharpe, maxdd = metrics(r)
        print(f"{name:>22}: CAGR {cagr*100:+6.1f}%  vol {vol*100:4.1f}%  "
              f"Sharpe {sharpe:+.2f}  maxDD {maxdd*100:5.1f}%")

    print(f"couverture : {R.index.min().date()} -> {R.index.max().date()} ({len(R)} jours)\n")
    print("== PLEINE PERIODE ==")
    report("Rotation regime", strat)
    report("Statique 1/3-1/3-1/3", stat)
    for a in ORDER:
        report(f"Buy-and-lead {a}", R[a])

    split = pd.Timestamp("2024-06-30", tz="UTC")
    print(f"\n== OOS 2024-07 -> {R.index.max().date()} ==")
    report("Rotation regime", strat[strat.index > split])
    report("Statique", stat[stat.index > split])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())