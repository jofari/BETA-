"""R10 — DISJONCTION : funding extrême OU F&G extrême.

L'une OU l'autre des deux conditions contrariennes suffit. Signal fréquent (union), donc
plus de trades, chacun plus faible si l'edge n'existe qu'aux extrêmes les plus nets.

- long  : funding z 90j <= -1,28  OU  F&G <= 20
- short : funding z 90j >= +1,28  OU  F&G >= 80
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from beta.moteur.contrats import Candidate

FENETRE_JOURS = 90
SEUIL_Z = 1.28
SEUIL_PEUR = 20.0
SEUIL_AVIDITE = 80.0


def _z_funding(fr: pd.Series, fenetre: int) -> pd.Series:
    mu = fr.rolling(fenetre, min_periods=fenetre).mean()
    sd = fr.rolling(fenetre, min_periods=fenetre).std(ddof=0)
    return (fr - mu) / sd.replace(0, np.nan)


def signaux(df: pd.DataFrame) -> pd.DataFrame:
    if "funding_rate" not in df.columns or "fng" not in df.columns:
        return pd.DataFrame({"sens": pd.Series(0, index=df.index, dtype=int)})

    z = _z_funding(df["funding_rate"].astype(float), FENETRE_JOURS * 6)
    fng = df["fng"].astype(float)

    funding_bas = z <= -SEUIL_Z
    funding_haut = z >= SEUIL_Z
    peur = fng <= SEUIL_PEUR
    avidite = fng >= SEUIL_AVIDITE

    sens = pd.Series(0, index=df.index, dtype=int)
    sens[funding_bas | peur] = 1
    sens[funding_haut | avidite] = -1
    return pd.DataFrame({"sens": sens.fillna(0).astype(int)})


def creer() -> Candidate:
    return Candidate(
        nom="r10_disjonction",
        titre="Funding OU F&G extrême (disjonction)",
        hypothese="R10",
        signaux=signaux,
        parametres={"fenetre_jours": FENETRE_JOURS, "seuil_z": SEUIL_Z,
                    "seuil_peur": SEUIL_PEUR, "seuil_avidite": SEUIL_AVIDITE},
        description="contrarien dès que funding OU F&G est extrême")
