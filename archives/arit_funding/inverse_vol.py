"""Ponderation mesuree (inverse-vol) vs 33/33/33 arbitraire.

w_i = (1/sigma_i) / sum(1/sigma_j), sigma_i = vol realisee glissante 180j (cause).
Le poids baisse automatiquement quand la vol de l'actif exact (risk-off) -> rotation
implicite sans signal VIX. Zero look-ahead (w a t-1 applique au rendement de t).
"""
import numpy as np
import pandas as pd

from beta.lake.lecture import load

ORDER = ["BTC", "XAUUSD", "SP500"]


def metrics(s):
    s = s.dropna()
    n = len(s)
    cagr = (1 + s).prod() ** (252 / n) - 1
    v = s.std() * np.sqrt(252)
    sh = s.mean() * np.sqrt(252) / s.std()
    cum = (1 + s).cumprod()
    md = (cum / cum.cummax() - 1).min()
    return cagr, v, sh, md


def rep(name, s):
    c, v, sh, md = metrics(s)
    print(f"{name:>12}: CAGR {c*100:+5.1f}%  vol {v*100:4.1f}%  Sharpe {sh:+.2f}  maxDD {md*100:5.1f}%")


def main() -> int:
    R = pd.DataFrame({a: load(a, "1d").set_index("date")["close"].pct_change() for a in ORDER}).dropna()

    vol = R.rolling(180, min_periods=60).std()
    inv = 1.0 / vol
    w_iv = inv.div(inv.sum(axis=1), axis=0).shift(1)
    w_eq = pd.DataFrame(1 / 3, index=R.index, columns=ORDER)

    print("poids MOYENS (inverse-vol, yoyen de la. periode):")
    print((w_iv.mean() * 100).round(1).to_string())
    print()

    strat_eq = (R * w_eq).sum(axis=1)
    strat_iv = (R * w_iv).sum(axis=1)

    print("== PLEINE PERIODE ==")
    rep("33/33/33", strat_eq)
    rep("inverse-vol", strat_iv)

    sp = R.index > pd.Timestamp("2024-06-30", tz="UTC")
    print("\n== OOS 2024-07 -> ==")
    rep("33/33/33", strat_eq[sp])
    rep("inverse-vol", strat_iv[sp])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())