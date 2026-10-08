"""R11 — stress crédit -> rebond crypto (contrarien, LONG seulement).

Hypothese : apres un episode de stress credit (spread dans sa queue haute sur un an), le
risque rebondit. Sens contrarien LONG : on achete quand le spread est en regime de stress.

Le spread utilise est le Baa10Y (Moody's Baa - 10y Treasury), fourni comme colonne `baa10y`
(quotidien, historique complet depuis 1986, decale d'un jour sans look-ahead). NOTE : la
premiere version utilisait `hy_oas`, mais FRED n'en sert que 3 ans (depuis 2023) — insuffisant
pour une fenetre glissante d'un an. Baa10Y a l'historique complet.

On normalise en z-score sur une fenetre glissante d'un an — les regimes de credit sont lents.
Causale : la fenetre n'utilise que le passe.

Seuil : z >= +1,0 -> LONG. Pas de short : la relation n'est pas symetrique.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from beta.moteur.contrats import Candidate

FENETRE_JOURS = 250          # un an : les regimes de credit sont lents
SEUIL_Z = 1.0


def signaux(df: pd.DataFrame, fenetre_jours: int = FENETRE_JOURS,
            seuil: float = SEUIL_Z) -> pd.DataFrame:
    if "baa10y" not in df.columns:
        return pd.DataFrame({"sens": pd.Series(0, index=df.index, dtype=int)})

    sp = df["baa10y"].astype(float)
    fenetre = fenetre_jours * 6      # 6 bougies 4h par jour
    mu = sp.rolling(fenetre, min_periods=fenetre).mean()
    sd = sp.rolling(fenetre, min_periods=fenetre).std(ddof=0)
    z = (sp - mu) / sd.replace(0, np.nan)

    sens = pd.Series(0, index=df.index, dtype=int)
    sens[z >= seuil] = 1             # stress credit -> rebond attendu -> long
    return pd.DataFrame({"sens": sens.fillna(0).astype(int), "force": z.fillna(0.0)})


def creer() -> Candidate:
    return Candidate(
        nom="r11_credit_contrarian",
        titre="Stress crédit -> rebond crypto (LONG)",
        hypothese="R11",
        signaux=signaux,
        parametres={"fenetre_jours": FENETRE_JOURS, "seuil_z": SEUIL_Z},
        description="long quand le Baa10Y est en stress (z-score annuel >= 1), sans short")
