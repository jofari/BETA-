"""Temps 1 — les detecteurs, aux seances de decision de l'actif cible.

Aucun parametre n'est regle ici : fenetres et seuils sont ceux du prompt du 21/10, ecrits une
fois. Sortie commune : un SCORE par seance, que le moteur TI1 convertit en exposition avec
`Mapping("paliers")` (seuils +-0,4) : +1 -> 1,0 ; 0 -> 0,7 ; -1 -> 0,25.

- SMA_n, MOM126 : vrai -> +1, faux -> -1 (jamais 0) ;
- COUCHE1 : expansion +1, stress monetaire 0, stress de liquidite -1.

NaN = pas encore defini (prechauffe) : la campagne refuse de demarrer sur un NaN. Inegalites
strictes partout, comme ecrites (« > SMA », « > 0 », « > 25 », « baisse de plus de 5 % »).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from beta.temps1 import donnees as dn
from beta.temps1.donnees import Donnees

SMA_FENETRES = {"SMA126": 126, "SMA168": 168, "SMA200": 200, "SMA210": 210, "SMA252": 252}
MOM_FENETRE = 126
VIX_SEUIL = 25.0
USDJPY_FENETRE = 21
USDJPY_SEUIL = -0.05
SMA_COUCHE1 = 200
DETECTEURS = ("SMA200", "SMA126", "SMA168", "SMA210", "SMA252", "MOM126", "COUCHE1")
# Ce que chaque detecteur lit, en observations, jusqu'a la premiere decision (prechauffe).
BESOIN = {**{k: {"cible": n} for k, n in SMA_FENETRES.items()},
          "MOM126": {"cible": MOM_FENETRE + 1},
          "COUCHE1": {"SPX": SMA_COUCHE1, "VIX": 1, "DEXJPUS": USDJPY_FENETRE + 1,
                      "XAU_LBMA": SMA_COUCHE1}}


def _drapeau(vrai: pd.Series, defini: pd.Series) -> pd.Series:
    """1.0 / 0.0, NaN tant que l'indicateur n'est pas defini."""
    return pd.Series(np.where(defini, vrai.astype(float), np.nan), index=vrai.index)


def sma(close: pd.Series, n: int) -> pd.Series:
    return close.rolling(n, min_periods=n).mean()


def au_dessus_sma(close: pd.Series, n: int) -> pd.Series:
    m = sma(close, n)
    return _drapeau(close > m, m.notna())


def momentum_positif(close: pd.Series, n: int = MOM_FENETRE) -> pd.Series:
    r = close / close.shift(n) - 1.0
    return _drapeau(r > 0, r.notna())


def score_binaire(drapeau: pd.Series) -> pd.Series:
    return pd.Series(np.where(drapeau.isna(), np.nan, np.where(drapeau == 1.0, 1.0, -1.0)),
                     index=drapeau.index)


def indicateurs_couche1(d: Donnees, decisions: pd.DatetimeIndex) -> pd.DataFrame:
    """T, V, Y, G en vigueur a chaque decision (1.0 / 0.0 / NaN), chacun sur SES seances."""
    spx, vix = d.closes["SPX"], d.closes["VIX"]
    t = _drapeau(spx < sma(spx, SMA_COUCHE1), sma(spx, SMA_COUCHE1).notna())
    v = _drapeau(vix > VIX_SEUIL, vix.notna())
    dex = d.closes["DEXJPUS"]
    variation = dex / dex.shift(USDJPY_FENETRE) - 1.0
    y = _drapeau(variation < USDJPY_SEUIL, variation.notna())
    xau = d.closes["XAU_LBMA"]
    g = _drapeau(xau > sma(xau, SMA_COUCHE1), sma(xau, SMA_COUCHE1).notna())
    return pd.DataFrame({"T": dn.a_la_decision(t, decisions),
                         "V": dn.a_la_decision(v, decisions),
                         "Y": dn.derniere_connue(y, d.dexjpus_dispo, decisions),
                         "G": dn.a_la_decision(g, decisions)}, index=decisions)


def couche1(ind: pd.DataFrame) -> pd.Series:
    """Priorite : liquidite (V ou Y) -> -1 ; sinon monetaire (T et G) -> 0 ; sinon +1."""
    defini = ind[["T", "V", "Y", "G"]].notna().all(axis=1)
    liquidite = (ind["V"] == 1.0) | (ind["Y"] == 1.0)
    monetaire = (ind["T"] == 1.0) & (ind["G"] == 1.0)
    score = np.where(liquidite, -1.0, np.where(monetaire, 0.0, 1.0))
    return pd.Series(np.where(defini, score, np.nan), index=ind.index)


def score(nom: str, d: Donnees, cible: str, decisions: pd.DatetimeIndex) -> pd.Series:
    """Le score du detecteur `nom` a chaque seance de decision de `cible`."""
    close = d.closes[cible]
    if nom in SMA_FENETRES:
        return score_binaire(au_dessus_sma(close, SMA_FENETRES[nom])).reindex(decisions)
    if nom == "MOM126":
        return score_binaire(momentum_positif(close)).reindex(decisions)
    if nom == "COUCHE1":
        return couche1(indicateurs_couche1(d, decisions))
    raise KeyError(f"detecteur inconnu : {nom} (connus : {DETECTEURS})")
