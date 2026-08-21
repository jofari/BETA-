"""auto_r7_01 — R7 : entrer long ou short selon la meche et l'ATR."""

from __future__ import annotations

import pandas as pd
from beta.moteur.contrats import Candidate

FENETRE = 14
SEUIL_MECHE_BASSE = 3.0
SEUIL_MECHE_HAUTE = 3.0


def signaux(df: pd.DataFrame, fenetre: int = FENETRE,
            seuil_basse: float = SEUIL_MECHE_BASSE,
            seuil_haute: float = SEUIL_MECHE_HAUTE) -> pd.DataFrame:
    open_price = df["open"]
    close_price = df["close"]
    high_price = df["high"]
    low_price = df["low"]

    meche_basse = (open_price - close_price).abs().min() - low_price
    atr_precedent = meche_basse.shift(1)

    sens = pd.Series(0, index=df.index, dtype=int)
    sens[meche_basse > seuil_basse * atr_precedent] = 1
    sens[(high_price - close_price).abs().max() > seuil_haute * atr_precedent] = -1

    return pd.DataFrame({"sens": sens.fillna(0).astype(int)})


def creer() -> Candidate:
    return Candidate(
        nom="auto_r7_01",
        titre="Rejet de meche vs ATR",
        hypothese="R7",
        signaux=signaux,
        parametres={"fenetre": FENETRE, "seuil_basse": SEUIL_MECHE_BASSE, "seuil_haute": SEUIL_MECHE_HAUTE},
        description="entrer long ou short selon la meche et l'ATR sans filtre"
    )
