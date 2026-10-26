"""CSCV : probabilite de surajustement d'un backtest (PBO).

Bailey, Borwein, Lopez de Prado et Zhu, « The Probability of Backtest Overfitting »,
Journal of Computational Finance 20(4), 2017, procedure CSCV :

1. M (T x N) : rendements de N configurations sur T jours, coupee en S blocs CONTIGUS de
   T / S jours (T multiple de S, S pair).
2. Pour chacune des C(S, S/2) combinaisons c de S/2 blocs : J = ces blocs (in-sample), J' =
   les S/2 autres (out-of-sample).
3. R = Sharpe de chaque configuration sur J, R' = sur J'. n* = argmax R.
4. w_c = rang de R'[n*] dans R' / (N + 1), rang croissant (1 = pire OOS, N = meilleure).
5. lambda_c = ln(w_c / (1 - w_c)).
PBO = part des combinaisons ou lambda_c <= 0 : la meilleure configuration IS finit dans la
moitie basse OOS.

Conventions que l'article ne fixe pas, fixees ici :
- egalite de Sharpe IS : n* = la premiere configuration dans l'ordre des colonnes ;
- egalite de Sharpe OOS : rang moyen ;
- Sharpe = moyenne / ecart-type (ddof = 1) * sqrt(ppa), rf = 0. Un ecart-type nul ou non fini
  arrete le calcul (CSCVError) : un rang tire d'un ratio sans denominateur ne veut rien dire.

Les sommes par moitie sont faites bloc par bloc, dans le meme ordre pour chaque colonne : deux
colonnes egales sur une moitie y ont exactement le meme Sharpe, donc la meme place.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

import numpy as np


class CSCVError(ValueError):
    """Entree que la procedure ne peut pas classer honnetement."""


@dataclass(frozen=True)
class Resultat:
    pbo: float
    lambdas: np.ndarray        # (C,) logit du rang OOS relatif de n*
    w: np.ndarray              # (C,) rang OOS relatif de n*, dans ]0 ; 1[
    rangs: np.ndarray          # (C,) rang OOS de n*, 1 = pire, N = meilleure
    etoiles: np.ndarray        # (C,) indice de n* (colonne)
    sharpe_is: np.ndarray      # (C,) Sharpe IS de n*
    sharpe_oos: np.ndarray     # (C,) Sharpe OOS de n*
    n_jours: int
    n_configs: int
    n_blocs: int
    jours_par_bloc: int

    @property
    def n_combinaisons(self) -> int:
        return len(self.lambdas)


def combinaisons(s: int) -> tuple[np.ndarray, np.ndarray]:
    """(IS, OOS) : C(s, s/2) lignes de s/2 indices de blocs, dans l'ordre d'itertools."""
    tous = set(range(s))
    js = list(itertools.combinations(range(s), s // 2))
    oos = [sorted(tous - set(j)) for j in js]
    return np.array(js, dtype=np.intp), np.array(oos, dtype=np.intp)


def _somme(par_bloc: np.ndarray, choix: np.ndarray) -> np.ndarray:
    """Somme des blocs choisis, ligne par ligne, toujours dans l'ordre des blocs."""
    total = par_bloc[choix[:, 0]].copy()
    for k in range(1, choix.shape[1]):
        total += par_bloc[choix[:, k]]
    return total


def _sharpe(s1: np.ndarray, s2: np.ndarray, n: int, ppa: float) -> np.ndarray:
    moyenne = s1 / n
    variance = (s2 - s1 * moyenne) / (n - 1)
    # Une serie constante donne une variance de l'ordre de l'arrondi, pas 0 : on la compare a
    # la moyenne des carres (1e-12 = ecart-type sous un millionieme de la moyenne quadratique).
    if not np.isfinite(variance).all() or (variance <= 1e-12 * s2 / n).any():
        raise CSCVError("ecart-type nul ou non fini sur une moitie : Sharpe indefini")
    return moyenne / np.sqrt(variance) * math.sqrt(ppa)


def pbo(rendements: np.ndarray, s: int, ppa: float = 252.0, lot: int = 1024) -> Resultat:
    """PBO par CSCV d'une matrice T x N de rendements (une colonne par configuration)."""
    m = np.asarray(rendements, dtype=float)
    if m.ndim != 2:
        raise CSCVError(f"matrice T x N attendue, recu {m.ndim} dimension(s)")
    t, n = m.shape
    if s < 2 or s % 2:
        raise CSCVError(f"S doit etre pair et >= 2 (recu {s})")
    if t % s:
        raise CSCVError(f"T = {t} n'est pas un multiple de S = {s} : blocs inegaux")
    if n < 2:
        raise CSCVError("il faut au moins 2 configurations pour un rang")
    if not np.isfinite(m).all():
        raise CSCVError("rendement manquant ou infini dans la matrice")

    b = t // s
    blocs = m.reshape(s, b, n)
    s1 = blocs.sum(axis=1)
    s2 = (blocs * blocs).sum(axis=1)
    j_is, j_oos = combinaisons(s)
    demi = b * (s // 2)

    morceaux = []
    for debut in range(0, len(j_is), lot):
        ci, co = j_is[debut:debut + lot], j_oos[debut:debut + lot]
        sh_is = _sharpe(_somme(s1, ci), _somme(s2, ci), demi, ppa)
        sh_oos = _sharpe(_somme(s1, co), _somme(s2, co), demi, ppa)
        lignes = np.arange(len(ci))
        etoile = sh_is.argmax(axis=1)
        v = sh_oos[lignes, etoile]
        dessous = (sh_oos < v[:, None]).sum(axis=1)
        egales = (sh_oos == v[:, None]).sum(axis=1)       # n* compris
        rang = dessous + (egales + 1) / 2.0
        morceaux.append((etoile, rang, sh_is[lignes, etoile], v))

    etoiles = np.concatenate([x[0] for x in morceaux])
    rangs = np.concatenate([x[1] for x in morceaux])
    w = rangs / (n + 1)
    lambdas = np.log(w / (1.0 - w))
    return Resultat(
        pbo=float((lambdas <= 0.0).mean()), lambdas=lambdas, w=w, rangs=rangs,
        etoiles=etoiles, sharpe_is=np.concatenate([x[2] for x in morceaux]),
        sharpe_oos=np.concatenate([x[3] for x in morceaux]),
        n_jours=t, n_configs=n, n_blocs=s, jours_par_bloc=b)
