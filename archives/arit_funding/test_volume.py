"""Volume acceleration — test du 2e declencheur de Jonas.

Q cible : l'acceleration du volume predit-elle la DIRECTION (rendement signe)
ou seulement la MAGNITUDE (volatilite) ?

Methode (causale, sans look-ahead) :
- V_t = volume quotidien.
- accel_t = V_t / moyenne(V des 30 jours PRECEDENTS)  -> baseline exclut aujourd'hui.
- q_t = percentile CAUSAL de accel sur fenetre glissante 180j.
- forward h = P_{t+h}/P_t - 1 ; |ret| = magnitude.
"""
import numpy as np
import pandas as pd

from beta.lake.lecture import load


def main() -> int:
    df = load("BTC", "1d").set_index("date")
    close, vol = df["close"], df["volume"]

    accel = vol / vol.rolling(30).mean().shift(1)
    q = accel.rolling(180, min_periods=60).apply(lambda x: (x <= x[-1]).mean(), raw=True)
    qb = pd.cut(q, np.arange(0, 1.0001, 0.1), labels=False).astype("Int64") + 1

    def grp(x):
        if pd.isna(x):
            return np.nan
        if x <= 2:
            return "bas"
        if x >= 9:
            return "haut"
        if 4 <= x <= 7:
            return "milieu"
        return np.nan

    g = qb.map(grp)

    print("Rendement forward MOYEN (%) par decile d'acceleration de volume :")
    print(f"{'h':>3} | {'bas':>9} | {'milieu':>9} | {'haut':>9} | {'hold':>9} | {'|ret| haut':>10}")
    for h in (1, 3, 5, 7):
        rf = (close.shift(-h) / close - 1) * 100
        d = pd.DataFrame({"g": g, "rf": rf, "arf": rf.abs()}).dropna()
        m = d.groupby("g")["rf"].mean()
        bh = d["rf"].mean()
        mag_haut = d[d.g == "haut"]["arf"].mean()
        print(f"{h:>3} | {m.get('bas',0):>+9.3f} | {m.get('milieu',0):>+9.3f} | "
              f"{m.get('haut',0):>+9.3f} | {bh:>+9.3f} | {mag_haut:>10.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())