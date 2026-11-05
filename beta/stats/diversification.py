"""S9 — correlation des courbes d'equity entre candidates.

Deux strategies rentables et correlees a 0,9 n'en font pas deux : elles en font une, testee
deux fois. Les tenir toutes les deux double l'exposition au meme facteur en croyant
diversifier — c'est exactement l'erreur que F1 demande d'eviter (« diversifier les formes
d'investissement »), et elle ne se voit sur aucune metrique individuelle.

La correlation se mesure sur le P&L JOURNALIER des courbes d'equity, pas sur les R par
trade : deux candidates qui ne tradent pas aux memes moments n'ont pas de trades
appariables, alors que leurs courbes le sont toujours. P&L du jour = variation de l'equity
(`diff`), comme S8 : la courbe du moteur est a risque fixe, non composee, et un `pct_change`
la deformait (audit du 05/11/2026) — son denominateur, l'equity de la veille, n'est pas le
meme d'une candidate a l'autre et devient absurde pres de zero.

La correlation se lit avec son SIGNE (audit du 05/11/2026). Jusque-la, la porte testait
|rho| >= SEUIL : une candidate anticorrelee a -0,96, le meilleur diversificateur possible,
echouait pour la meme raison qu'une copie. Une redondance, c'est rho >= SEUIL.

Le seuil est une decision, pas une statistique : au-dela de `SEUIL`, on considere que la
seconde candidate n'apporte rien. Il est ecrit ici pour ne pas etre choisi apres coup.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SEUIL = 0.70


def _rendements_journaliers(equity: pd.DataFrame) -> pd.Series:
    """Le P&L de chaque jour, en unites d'equity (variation, pas pourcentage)."""
    if equity.empty:
        return pd.Series(dtype=float)
    courbe = (equity.set_index(pd.to_datetime(equity["ts"], utc=True))["equity"]
              .resample("1D").last().ffill().dropna())
    return courbe.diff().dropna()


def matrice(equities: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Matrice de correlation des candidates. Index et colonnes = noms de candidates."""
    series = {nom: _rendements_journaliers(eq) for nom, eq in equities.items()}
    series = {n: s for n, s in series.items() if len(s) > 2}
    if len(series) < 2:
        return pd.DataFrame()
    return pd.DataFrame(series).dropna(how="all").corr(min_periods=10)


def redondances(equities: dict[str, pd.DataFrame], seuil: float = SEUIL) -> list[dict]:
    """Les paires de candidates trop correlees pour compter double. Triees par correlation."""
    corr = matrice(equities)
    if corr.empty:
        return []
    trouvees = []
    noms = list(corr.columns)
    for i, a in enumerate(noms):
        for b in noms[i + 1:]:
            valeur = corr.loc[a, b]
            if np.isfinite(valeur) and valeur >= seuil:
                trouvees.append({"a": a, "b": b, "correlation": float(valeur)})
    return sorted(trouvees, key=lambda d: -d["correlation"])


def porte(nom: str, equities: dict[str, pd.DataFrame], seuil: float = SEUIL) -> dict:
    """La porte S9 pour UNE candidate : est-elle une copie d'une candidate deja retenue ?

    `passe` est vrai si la candidate n'est trop correlee a AUCUNE autre. Avec une seule
    candidate au registre, la porte passe faute d'objet — et le dit, plutot que de laisser
    croire a une diversification verifiee.
    """
    autres = {n: eq for n, eq in equities.items() if n != nom}
    if not autres:
        return {"passe": True, "correlation_max": float("nan"), "avec": None,
                "reserve": "aucune autre candidate : diversification non verifiee"}
    liens = redondances({nom: equities[nom], **autres}, seuil=-np.inf)
    liens = [l for l in liens if nom in (l["a"], l["b"])]
    if not liens:
        return {"passe": True, "correlation_max": float("nan"), "avec": None,
                "reserve": "aucun recouvrement temporel exploitable"}
    pire = liens[0]
    return {"passe": pire["correlation"] < seuil,
            "correlation_max": pire["correlation"],
            "avec": pire["b"] if pire["a"] == nom else pire["a"],
            "seuil": seuil, "reserve": ""}
