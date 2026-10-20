"""Test invest — analyse (C) : redondance entre votes, contribution de chacun par ablation.

C3 : deux votes tres d'accord (kappa eleve) comptent presque double dans le score. Le kappa
retire l'accord attendu par hasard, que l'accord brut ne retire pas (deux votes souvent a 0
s'accordent beaucoup sans rien dire).
C2 : Delta_k(M) = M(complet) - M(sans k). Lecture mecanique du cahier des charges : si retirer k
ameliore ou ne change pas les metriques de survie (Ulcer, MDD, protection), k est « inutile ou
nuisible ».
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

SURVIE = {"ulcer": "plus_petit", "mdd": "plus_grand", "protection": "plus_grand"}


def kappa_cohen(a: np.ndarray, b: np.ndarray) -> float | None:
    """kappa = (p_o - p_e) / (1 - p_e), categories = valeurs prises par l'un ou l'autre."""
    a, b = np.asarray(a), np.asarray(b)
    p_o = float(np.mean(a == b))
    categories = np.union1d(a, b)
    p_e = float(sum(np.mean(a == c) * np.mean(b == c) for c in categories))
    return None if p_e >= 1.0 else (p_o - p_e) / (1.0 - p_e)


def _spearman(a: np.ndarray, b: np.ndarray) -> float | None:
    if np.all(a == a[0]) or np.all(b == b[0]):
        return None
    return float(stats.spearmanr(a, b).statistic)


def matrices_accord(votes: pd.DataFrame) -> dict[str, dict[str, dict[str, float | None]]]:
    """Kappa, Spearman et accord brut pour chaque paire de votes (matrices symetriques)."""
    noms = list(votes.columns)
    sortie: dict[str, dict] = {"kappa": {}, "spearman": {}, "accord": {}}
    for x in noms:
        for cle in sortie:
            sortie[cle][x] = {}
        for y in noms:
            a, b = votes[x].to_numpy(), votes[y].to_numpy()
            sortie["kappa"][x][y] = 1.0 if x == y else kappa_cohen(a, b)
            sortie["spearman"][x][y] = 1.0 if x == y else _spearman(a, b)
            sortie["accord"][x][y] = float(np.mean(a == b))
    return sortie


def _delta(complet: float | None, sans: float | None) -> float | None:
    return None if complet is None or sans is None else complet - sans


def contributions(complet: dict, sans: dict[str, dict]) -> dict[str, dict]:
    """Pour chaque vote retire : Delta(M) = M(complet) - M(sans lui), et la lecture C2."""
    sortie = {}
    for k, m in sans.items():
        delta = {cle: _delta(complet.get(cle), m.get(cle)) for cle in complet}
        retirer_ne_nuit_pas = True
        for cle, sens in SURVIE.items():
            d = delta.get(cle)
            if d is None:
                continue
            # Delta = complet - sans : retirer ne nuit pas si « sans » est au moins aussi bon.
            if (sens == "plus_petit" and d < 0) or (sens == "plus_grand" and d > 0):
                retirer_ne_nuit_pas = False
        sortie[k] = {"delta": delta,
                     "lecture": "inutile ou nuisible" if retirer_ne_nuit_pas
                     else "contribue a la survie"}
    return sortie
