"""R9 — funding extreme -> retournement contrarien.

Hypothese : un funding dans le decile bas de sa distribution glissante sur 90 jours
(positionnement long degonfle) precede un rebond ; un funding dans le decile haut (longs
sur-leveres) precede un retournement. Sens contrarien : long quand le funding est ecrase,
short quand il est euphorique.

Le funding est fourni par le pipeline comme colonne `funding_rate` (chantier D5), deja
joint sans look-ahead (reglement strictement anterieur a la bougie). La candidate ne fait
que le lire et le normaliser en z-score sur une fenetre glissante de 90 jours — causale :
la fenetre n'utilise que le passe.

Seuil : z <= -1,28 (long) et z >= +1,28 (short), soit ~10 % de chaque queue sous une
distribution normale — l'operationalisation du « decile bas/haut » du preenregistrement.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from beta.moteur.contrats import Candidate

FENETRE_JOURS = 90
SEUIL_Z = 1.28


def signaux(df: pd.DataFrame, fenetre_jours: int = FENETRE_JOURS,
            seuil: float = SEUIL_Z) -> pd.DataFrame:
    if "funding_rate" not in df.columns:
        # Paire sans funding : pas de signal. On ne suppose jamais une colonne absente.
        return pd.DataFrame({"sens": pd.Series(0, index=df.index, dtype=int),
                             "force": pd.Series(0.0, index=df.index)})

    fr = df["funding_rate"].astype(float)
    # 90 jours en 4h = 540 bougies. min_periods = fenetre : pas de signal avant le warm-up.
    fenetre = fenetre_jours * 6
    mu = fr.rolling(fenetre, min_periods=fenetre).mean()
    sd = fr.rolling(fenetre, min_periods=fenetre).std(ddof=0)
    z = (fr - mu) / sd.replace(0, np.nan)

    sens = pd.Series(0, index=df.index, dtype=int)
    sens[z <= -seuil] = 1        # funding ecrase -> rebond attendu -> long
    sens[z >= seuil] = -1        # funding euphorique -> retournement -> short
    return pd.DataFrame({"sens": sens.fillna(0).astype(int), "force": z.abs().fillna(0.0)})


def creer() -> Candidate:
    return Candidate(
        nom="r9_funding_contrarian",
        titre="Funding extreme -> retournement (contrarien)",
        hypothese="R9",
        signaux=signaux,
        parametres={"fenetre_jours": FENETRE_JOURS, "seuil_z": SEUIL_Z},
        description="long quand le funding 90j est dans sa queue basse, short dans sa queue "
                    "haute, sans aucun filtre")
