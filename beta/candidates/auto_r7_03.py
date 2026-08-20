"""auto_r7_03 — R7 : declencheur a 3xATR(14) avec volume > 2xMMV(20)."""

from __future__ import annotations

import pandas as pd

from beta.moteur.contrats import Candidate

FENETRE_ATR = 14
FENETRE_VOL = 20


def signaux(df: pd.DataFrame, fenetre_atr: int = FENETRE_ATR,
            fenetre_vol: int = FENETRE_VOL) -> pd.DataFrame:
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    atr = (high - low).rolling(fenetre_atr, min_periods=fenetre_atr).mean()
    declencheur = 3 * atr

    mmv = volume.rolling(fenetre_vol, min_periods=fenetre_vol).mean()
    volume_sup = volume > 2 * mmv

    sens = pd.Series(0, index=df.index, dtype=int)
    sens[volume_sup & (close - close.shift(1) > declencheur)] = 1
    sens[volume_sup & (close - close.shift(1) < -declencheur)] = -1
    return pd.DataFrame({"sens": sens.fillna(0).astype(int)})


def creer() -> Candidate:
    return Candidate(
        nom="auto_r7_03",
        hypothese="R7",
        signaux=signaux,
        parametres={"fenetre_atr": FENETRE_ATR, "fenetre_vol": FENETRE_VOL},
        description="declencheur a 3xATR(14) avec volume > 2xMMV(20), sans filtre")
