"""T1J : le juge, une datation des cycles faite APRES COUP sur les clotures d'un actif.

Seuils par trimestre civil :

    delta_ref       = |ln(1 - baisse_ref)|                     (baisse_ref = 20 %, variantes 15/25)
    sigma_actif(q)  = ecart-type des rendements log quotidiens des 2 annees civiles
                      avant q, x rac(252)
    sigma_SP_ref    = meme calcul sur le SPX de toute la periode labo (constante)
    delta(q)        = delta_ref sigma_actif(q) / sigma_SP_ref
    theta_baisse    = 1 - exp(-delta) ; theta_hausse = exp(delta) - 1

En bull on suit le plus haut ; une baisse de theta_baisse depuis lui ouvre un bear, qui commence AU
JOUR DU PLUS HAUT. En bear on suit le plus bas ; une hausse de theta_hausse depuis lui ouvre un
bull, qui commence au jour du plus bas. L'etat de depart est fixe par le premier franchissement.
Le juge peut lire tout l'historique : il ne sert qu'a mesurer, jamais a decider.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from beta.temps1_justesse import regles as R

PIC, CREUX = "pic", "creux"


@dataclass
class Juge:
    """Les pivots d'un actif (dates et prix), et les seuils appliques jour par jour."""
    dates: pd.DatetimeIndex
    prix: np.ndarray
    pivots: list[tuple[int, str]]                 # (indice dans dates, PIC | CREUX), alternes
    confirmations: list[int]                      # indice du jour ou chaque pivot est confirme
    theta_baisse: np.ndarray
    theta_hausse: np.ndarray
    sigma_jour: np.ndarray                        # sigma_actif(q) / rac(252) du jour
    debut: int                                    # premier jour juge (premier trimestre eligible)
    infos: dict = field(default_factory=dict)

    def date(self, i: int) -> pd.Timestamp:
        return self.dates[i]

    def bears(self) -> list[tuple[int, int]]:
        """Bears complets (pic, creux)."""
        paires = zip(self.pivots, self.pivots[1:], strict=False)
        return [(a, b) for (a, ta), (b, _) in paires if ta == PIC]

    def bulls(self) -> list[tuple[int, int]]:
        """Bulls complets (creux, pic suivant)."""
        paires = zip(self.pivots, self.pivots[1:], strict=False)
        return [(a, b) for (a, ta), (b, _) in paires if ta == CREUX]

    def jours_bear(self) -> np.ndarray:
        """Masque des jours bear du juge sur tout l'historique : bears complets [pic, creux[ et,
        si le dernier pivot est un pic, le bear en cours [pic, fin]."""
        masque = np.zeros(len(self.dates), dtype=bool)
        for a, b in self.bears():
            masque[a:b] = True
        if self.pivots and self.pivots[-1][1] == PIC:
            masque[self.pivots[-1][0]:] = True
        return masque


def sigma_annualise(r: pd.Series) -> float:
    return float(r.std(ddof=1) * math.sqrt(R.ANNUALISATION))


def rendements_log(close: pd.Series) -> pd.Series:
    return np.log(close).diff().dropna()


def sigma_sp_ref(spx: pd.Series) -> float:
    """Volatilite annualisee du SPX sur toute la periode labo (rendements dates dans la periode)."""
    r = rendements_log(spx)
    return sigma_annualise(r[(r.index >= R.LABO[0]) & (r.index <= R.LABO[1])])


def premier_trimestre(close: pd.Series) -> pd.Timestamp:
    """Premier debut de trimestre civil precede de 2 annees completes de donnees."""
    borne = pd.Timestamp(close.index.min()) + pd.DateOffset(years=2)
    q = borne.to_period("Q")
    return q.start_time if borne == q.start_time else (q + 1).start_time


def sigmas_trimestriels(close: pd.Series, debut: pd.Timestamp) -> pd.Series:
    """sigma_actif(q) pour chaque trimestre q de `debut` a la fin des donnees."""
    r = rendements_log(close)
    trimestres = pd.period_range(debut, close.index.max(), freq="Q")
    valeurs = {}
    for q in trimestres:
        q0 = q.start_time
        fen = r[(r.index >= q0 - pd.DateOffset(years=2)) & (r.index < q0)]
        valeurs[q] = sigma_annualise(fen)
    return pd.Series(valeurs)


def dater(prix: np.ndarray, theta_baisse: np.ndarray, theta_hausse: np.ndarray,
          debut: int = 0) -> tuple[list[tuple[int, str]], list[int]]:
    """La machine a etats du juge sur prix[debut:], comparaisons inclusives (<=, >=)."""
    n = len(prix)
    pivots: list[tuple[int, str]] = []
    confirmations: list[int] = []
    etat = None
    imax = imin = debut

    def pivot(i: int, sorte: str, jour: int) -> None:
        pivots.append((i, sorte))
        confirmations.append(jour)

    for i in range(debut + 1, n):
        p = prix[i]
        if etat is None:
            if p > prix[imax]:
                imax = i
            if p < prix[imin]:
                imin = i
            baisse = p <= prix[imax] * (1.0 - theta_baisse[i])
            hausse = p >= prix[imin] * (1.0 + theta_hausse[i])
            if baisse and hausse:
                # Les deux franchis le meme jour : l'extremum le plus ancien est venu le premier.
                if imin < imax:
                    pivot(imin, CREUX, i)
                    pivot(imax, PIC, i)
                    etat = "bear"
                    imin = imax + int(np.argmin(prix[imax:i + 1]))
                else:
                    pivot(imax, PIC, i)
                    pivot(imin, CREUX, i)
                    etat = "bull"
                    imax = imin + int(np.argmax(prix[imin:i + 1]))
            elif baisse:
                pivot(imax, PIC, i)
                etat = "bear"
                imin = imax + int(np.argmin(prix[imax:i + 1]))
            elif hausse:
                pivot(imin, CREUX, i)
                etat = "bull"
                imax = imin + int(np.argmax(prix[imin:i + 1]))
            else:
                continue
        else:
            if etat == "bull" and p > prix[imax]:
                imax = i
            if etat == "bear" and p < prix[imin]:
                imin = i
        # Un meme jour peut, en principe, confirmer plusieurs pivots (seuils changeant d'un
        # trimestre a l'autre) : on rejoue la regle jusqu'a ce que l'etat ne bouge plus.
        while True:
            if etat == "bull" and p <= prix[imax] * (1.0 - theta_baisse[i]):
                pivot(imax, PIC, i)
                etat = "bear"
                imin = imax + int(np.argmin(prix[imax:i + 1]))
            elif etat == "bear" and p >= prix[imin] * (1.0 + theta_hausse[i]):
                pivot(imin, CREUX, i)
                etat = "bull"
                imax = imin + int(np.argmax(prix[imin:i + 1]))
            else:
                break
    return pivots, confirmations


def juger(close: pd.Series, sigma_ref: float, baisse_ref: float = R.DELTA_REF_BAISSE,
          sigma_unique: float | None = None) -> Juge:
    """Le juge d'un actif sur tout son historique, a partir du premier trimestre eligible."""
    debut = premier_trimestre(close)
    sig_q = sigmas_trimestriels(close, debut)
    trimestre = close.index.to_period("Q")
    sigma = trimestre.map(lambda q: sig_q.get(q, np.nan)).to_numpy(dtype=float)
    if sigma_unique is not None:
        sigma = np.where(np.isnan(sigma), np.nan, sigma_unique)
    delta_ref = abs(math.log(1.0 - baisse_ref))
    delta = delta_ref * sigma / sigma_ref
    tb, th = 1.0 - np.exp(-delta), np.exp(delta) - 1.0
    i0 = int(close.index.searchsorted(debut))
    pivots, conf = dater(close.to_numpy(dtype=float), tb, th, i0)
    return Juge(dates=close.index, prix=close.to_numpy(dtype=float), pivots=pivots,
                confirmations=conf, theta_baisse=tb, theta_hausse=th,
                sigma_jour=sigma / math.sqrt(R.ANNUALISATION), debut=i0,
                infos={"debut": f"{debut:%Y-%m-%d}", "baisse_ref": baisse_ref,
                       "delta_ref": delta_ref, "sigma_ref": sigma_ref,
                       "sigma_unique": sigma_unique})
