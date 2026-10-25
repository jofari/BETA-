"""Combinaison — test du SCHEMA TYPE (la maison, pas la brique).

Hypothese (theorie de Jonas) : le signal 'crowded short' (funding bas) est plus fort en
CONJONCTION avec un filtre de sentiment (F&G pas en greed extreme : on n'achete pas un top).

On compare : hold (toujours) vs A seul (funding bas) vs A&B (la combinaison).

Methode (causale, sans look-ahead) :
- q_funding_t = percentile glissant 180j du funding quotidien.
- q_fng_t     = percentile glissant 180j du F&G quotidien.
- A = q_funding <= 0.20  (crowded shorts)
- B = q_fng     <= 0.80  (pas greed top)
- forward h = P_{t+h}/P_t - 1
"""
import numpy as np
import pandas as pd

from beta.lake.lecture import fear_greed, funding, load


def pct(s: pd.Series, w: int = 180, mp: int = 60) -> pd.Series:
    return s.rolling(w, min_periods=mp).apply(lambda x: (x <= x[-1]).mean(), raw=True)


def main() -> int:
    close = load("BTC", "1d").set_index("date")["close"]
    f = funding("BTC").set_index("date")["funding_rate"].resample("1D").mean().dropna()
    f = f.reindex(close.index).ffill()
    fng = fear_greed().set_index("date")["fng"].reindex(close.index).ffill()

    qf = pct(f)
    qn = pct(fng)

    A = qf <= 0.20
    B = qn <= 0.80

    print("Forward return MOYEN (%) : hold vs brique vs maison")
    print(f"{'h':>3} | {'hold':>9} | {'A (fund bas)':>12} | {'B (fng pas top)':>15} | {'A&B (maison)':>13} | {'n(A&B)':>6}")
    for h in (1, 3, 5, 7):
        rf = (close.shift(-h) / close - 1) * 100
        valid = rf.notna() & qf.notna() & qn.notna()
        mhold = rf[valid].mean()
        ma = rf[valid & A].mean()
        mb = rf[valid & B].mean()
        mab = rf[valid & A & B].mean()
        n = (valid & A & B).sum()
        print(f"{h:>3} | {mhold:>+9.3f} | {ma:>+12.3f} | {mb:>+15.3f} | {mab:>+13.3f} | {n:>6}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())