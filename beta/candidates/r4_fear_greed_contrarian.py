"""R4 — la macro seule suffit-elle ? Operationalisation : Fear & Greed contrarien.

Hypothese (R4) : les seules variables macro, sans aucune couche technique, suffisent a
produire une esperance en R positive. Ici, la variable macro est le Fear & Greed Index,
fourni par le pipeline comme colonne `fng` (deja decale d'un jour, sans look-ahead).

Regle contrarienne, nue : peur extreme (fng <= 20) -> long, avidite extreme (fng >= 80)
-> short. Ce sont les seuils de classification de la source elle-meme (CNN/alternative.me).
Aucune donnee de prix n'est lue : c'est de la macro pure.
"""

from __future__ import annotations

import pandas as pd

from beta.moteur.contrats import Candidate

SEUIL_PEUR = 20.0
SEUIL_AVIDITE = 80.0


def signaux(df: pd.DataFrame, seuil_peur: float = SEUIL_PEUR,
            seuil_avidite: float = SEUIL_AVIDITE) -> pd.DataFrame:
    if "fng" not in df.columns:
        return pd.DataFrame({"sens": pd.Series(0, index=df.index, dtype=int),
                             "force": pd.Series(0.0, index=df.index)})
    fng = df["fng"].astype(float)
    sens = pd.Series(0, index=df.index, dtype=int)
    sens[fng <= seuil_peur] = 1        # peur extreme -> achat contrarien
    sens[fng >= seuil_avidite] = -1    # avidite extreme -> vente contrarienne
    force = ((fng - 50.0).abs()).fillna(0.0)
    return pd.DataFrame({"sens": sens.fillna(0).astype(int), "force": force})


def creer() -> Candidate:
    return Candidate(
        nom="r4_fear_greed_contrarian",
        titre="Macro seule : F&G contrarien",
        hypothese="R4",
        signaux=signaux,
        parametres={"seuil_peur": SEUIL_PEUR, "seuil_avidite": SEUIL_AVIDITE},
        description="long si peur extreme, short si avidite extreme, sans aucune donnee de "
                    "prix ni couche technique")
