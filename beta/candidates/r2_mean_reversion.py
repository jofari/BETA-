"""R2 — mean-reversion : l'oppose structurel d'AritV1, qui est un suiveur de tendance.

Hypothese : apres un ecart marque a sa moyenne recente, le prix revient vers elle plus
souvent qu'il ne poursuit. Si elle est vraie, elle produit un edge NON CORRELE a celui
qu'AritV1 cherchait — c'est la moitie qui compte de la demande F1 (« diversifier les formes
d'investissement »), l'autre moitie etant le rendement.

Regle, volontairement nue :

    z = (close - moyenne(close, fenetre)) / ecart-type(close, fenetre)
    z <= -seuil  =>  long        z >= +seuil  =>  short

Pas de filtre de regime, pas de confirmation, pas de porte macro. Une candidate riche ne se
teste pas : quand elle echoue on ne sait pas laquelle de ses six regles a echoue, et quand
elle reussit on ne sait pas laquelle a reussi. Les raffinements viendront APRES un verdict
sur la forme nue, et chacun sera une candidate distincte avec son propre preenregistrement.

Le z-score est calcule sur les bougies CLOSES uniquement : la moyenne mobile inclut la
bougie courante, dont le close est connu au moment ou l'on decide d'entrer au close. Aucun
decalage n'est donc necessaire, mais aucune donnee future n'est utilisee non plus.
"""

from __future__ import annotations

import pandas as pd

from beta.moteur.contrats import Candidate

FENETRE = 48
SEUIL_Z = 2.0


def signaux(df: pd.DataFrame, fenetre: int = FENETRE, seuil: float = SEUIL_Z
            ) -> pd.DataFrame:
    close = df["close"]
    moyenne = close.rolling(fenetre, min_periods=fenetre).mean()
    ecart = close.rolling(fenetre, min_periods=fenetre).std(ddof=1)
    z = (close - moyenne) / ecart.where(ecart > 0)
    sens = pd.Series(0, index=df.index, dtype=int)
    sens[z <= -seuil] = 1
    sens[z >= seuil] = -1
    return pd.DataFrame({"sens": sens.fillna(0).astype(int), "force": z.abs()})


def creer() -> Candidate:
    return Candidate(
        nom="mean_reversion_z",
        hypothese="R2",
        signaux=signaux,
        parametres={"fenetre": FENETRE, "seuil_z": SEUIL_Z},
        description="retour a la moyenne sur ecart de z-score, sans aucun filtre")
