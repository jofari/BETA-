"""Funding extremes — test contrarien (premiere mesure, esprit BETA).

Hypothese : le funding EXTREME est contrarien. Decile bas (crowded shorts) -> rendements
forward POSITIFS ; decile haut (crowded longs) -> NEGATIFS. Teste "smart vs dumb money".

Null : rendement forward independant du percentile de funding.

Methode (sans look-ahead) :
- funding quotidien = moyenne des 3 reglements 8h du jour.
- q_t = percentile CAUSAL : rang de f_t dans la fenetre glissante 180j (jusqu'a t inclus).
- forward h = P_{t+h}/P_t - 1  (rendement simple sur h jours).

Caveat honnete : pour h>1, les rendements forward se chevauchent (correlation dans les
residus) -> les SE/tes sont nominaux, pas a double aveugle ; la batterie BETA (bootstrap
par blocs, walk-forward) tranchera la significativite proprement.
"""
import numpy as np
import pandas as pd

from beta.lake.lecture import funding, load

WINDOW = 180


def main() -> int:
    close = load("BTC", "1d").set_index("date")["close"]
    f = funding("BTC").set_index("date")["funding_rate"].resample("1D").mean().dropna()
    f = f.reindex(close.index).ffill()

    # percentile causal glissant : fraction des 180 derniers jours <= valeur du jour
    q = f.rolling(WINDOW, min_periods=60).apply(lambda x: (x <= x[-1]).mean(), raw=True)

    # groupes : bas = deciles 1-2 (crowded short), haut = 9-10 (crowded long), milieu = 4-7
    qbins = pd.cut(q, np.arange(0, 1.0001, 0.1), labels=False).astype("Int64") + 1

    def grp(x):
        if pd.isna(x):
            return np.nan
        if x <= 2:
            return "bas(short)"
        if x >= 9:
            return "haut(long)"
        if 4 <= x <= 7:
            return "milieu"
        return np.nan

    g = qbins.map(grp)

    print(f"n={len(f)} jours, percentile glissant {WINDOW}j (causal, jusqu'a t inclus).\n")
    print("Rendement forward MOYEN (%), par regime de funding :")
    hdr = (f"{'horizon':>8} | {'bas(short)':>11} | {'milieu':>11} | {'haut(long)':>11} "
           f"| {'hold':>10} | {'spread haut-bas':>15} | n(bas|haut)")
    print(hdr)
    for h in (1, 3, 5, 7):
        rf = (close.shift(-h) / close - 1) * 100
        df = pd.DataFrame({"g": g, "rf": rf}).dropna()
        m = df.groupby("g")["rf"].mean()
        bh = df["rf"].mean()
        nb = (df.g == "bas(short)").sum()
        nh = (df.g == "haut(long)").sum()
        spread = m.get("haut(long)", 0) - m.get("bas(short)", 0)
        print(f"{h:>8} | {m.get('bas(short)',0):>+11.3f} | {m.get('milieu',0):>+11.3f} | "
              f"{m.get('haut(long)',0):>+11.3f} | {bh:>+10.3f} | {spread:>+15.3f} | {nb}|{nh}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())