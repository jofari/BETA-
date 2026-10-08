"""R10 — CONJONCTION : funding extrême ET F&G extrême, alignés.

Les deux conditions contrariennes doivent etre simultanément dans leur zone extrême, dans
le même sens. Signal rare (conjonction), donc censé être plus fort si l'edge existe.

- long  : funding z 90j <= -1,28  ET  F&G <= 20   (deux signaux de peur alignés)
- short : funding z 90j >= +1,28  ET  F&G >= 80   (deux signaux d'avidité alignés)

Les colonnes funding_rate et fng sont jointes par le pipeline (sans look-ahead).
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
    sens[funding_bas & peur] = 1
    sens[funding_haut & avidite] = -1
    return pd.DataFrame({"sens": sens.fillna(0).astype(int)})


def creer() -> Candidate:
    return Candidate(
        nom="r10_conjonction",
        titre="Funding ET F&G extrêmes alignés (conjonction)",
        hypothese="R10",
        signaux=signaux,
        parametres={"fenetre_jours": FENETRE_JOURS, "seuil_z": SEUIL_Z,
                    "seuil_peur": SEUIL_PEUR, "seuil_avidite": SEUIL_AVIDITE},
        description="contrarien uniquement quand funding et F&G sont extrêmes ensemble, "
                    "même sens")
