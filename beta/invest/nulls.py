"""Test invest — les nulls (D) : le signal est-il mieux place dans le temps que le hasard ?

Deux generateurs, parametres du mapping figes, meme moteur, memes couts :
1. decalage circulaire : s'(t) = s((t + tau) mod N), tau uniforme dans [m, N - m]. Garde toute
   la distribution et l'autocorrelation du signal, ne casse que son lien avec les prix ;
2. melange de segments : l'ordre des periodes de valeur constante est tire au hasard, sans
   JAMAIS recoller deux periodes de meme valeur (sinon leurs durees fusionnent et « conserver
   les durees de regime » serait faux). Garde les durees et la repartition des valeurs.

Regle de decision (D4, ecrite avant le test) : p retenue = la pire des deux (il faut battre les
deux nulls) ; p < 0,05 reel, 0,05 <= p < 0,20 non concluant, sinon hasard. BH : informatif.
Graines derivees par cle (`flux`) : un test donne les memes tirages quels que soient les autres
tests lances avec lui (C1).
"""

from __future__ import annotations

import zlib
from collections.abc import Callable

import numpy as np

SEUIL_REEL, SEUIL_HASARD = 0.05, 0.20


def flux(graine: int, *cles: str) -> np.random.Generator:
    """SeedSequence([graine, crc32(cle)...]) : stable d'une machine a l'autre (pas `hash`)."""
    return np.random.default_rng(
        np.random.SeedSequence([graine, *(zlib.crc32(c.encode()) for c in cles)]))


def decalage_circulaire(s: np.ndarray, rng: np.random.Generator, m: int = 90) -> np.ndarray:
    n = len(s)
    if n < 2 * m + 1:
        raise ValueError(f"serie de {n} jours : trop courte pour un decalage d'au moins {m} j")
    tau = int(rng.integers(m, n - m + 1))
    return np.roll(np.asarray(s), -tau)


def segments(s: np.ndarray) -> list[tuple[float, int]]:
    """(valeur, duree) de chaque periode de valeur constante, dans l'ordre."""
    s = np.asarray(s)
    if len(s) == 0:
        return []
    bords = np.flatnonzero(s[1:] != s[:-1]) + 1
    debuts = np.concatenate([[0], bords])
    fins = np.concatenate([bords, [len(s)]])
    return [(float(s[d]), int(f - d)) for d, f in zip(debuts, fins, strict=True)]


def _faisable(compte: dict, n: int, precedente) -> bool:
    """Peut-on ranger `n` segments sans deux valeurs egales cote a cote, apres `precedente` ?"""
    return all(c <= (n // 2 if v == precedente else (n + 1) // 2) for v, c in compte.items())


def melange_segments(s: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Les memes segments (valeur, duree), dans un ordre tire au hasard, jamais fusionnes.

    Construction pas a pas : a chaque position, une valeur differente de la precedente, tiree
    en proportion des segments qui lui restent, parmi celles qui laissent un rangement possible
    pour la suite ; puis une de ses durees, dans un ordre deja melange.
    """
    segs = segments(s)
    if len(segs) <= 1:
        return np.asarray(s).copy()
    valeurs = sorted({v for v, _ in segs})
    durees = {v: [int(d) for d in rng.permutation([d for w, d in segs if w == v])]
              for v in valeurs}
    compte = {v: len(durees[v]) for v in valeurs}
    ordre, precedente = [], None
    for position in range(len(segs)):
        restant = len(segs) - position - 1
        candidats = []
        for v in valeurs:
            if compte[v] == 0 or v == precedente:
                continue
            compte[v] -= 1
            if _faisable(compte, restant, v):
                candidats.append(v)
            compte[v] += 1
        poids = np.array([compte[v] for v in candidats], dtype=float)
        v = candidats[int(rng.choice(len(candidats), p=poids / poids.sum()))]
        ordre.append(v)
        compte[v] -= 1
        precedente = v
    return np.concatenate([np.full(durees[v].pop(), v) for v in ordre])


def p_value(nulles: np.ndarray, observe: float | None, plus_petit_meilleur: bool) -> float | None:
    """D3 : (1 + #{M_b au moins aussi bon que M_obs}) / (1 + B)."""
    if observe is None or (isinstance(observe, float) and np.isnan(observe)):
        return None
    x = np.asarray(nulles, dtype=float)
    meilleurs = (x <= observe) if plus_petit_meilleur else (x >= observe)
    return float((1 + int(meilleurs.sum())) / (1 + len(x)))


def p_retenue(p_circulaire: float | None, p_segments: float | None) -> float | None:
    """D4 : il faut battre LES DEUX nulls, donc la plus grande des deux p-values."""
    if p_circulaire is None or p_segments is None:
        return None
    return max(p_circulaire, p_segments)


def verdict(p: float | None) -> str | None:
    """Mecanique, sans reinterpretation : reel / non concluant / hasard."""
    if p is None:
        return None
    if p < SEUIL_REEL:
        return "reel"
    return "non concluant" if p < SEUIL_HASARD else "hasard"


def bh_q(ps: list[float | None]) -> list[float | None]:
    """q-values de Benjamini-Hochberg sur la famille donnee (INFORMATIF, D4)."""
    valides = [(i, p) for i, p in enumerate(ps) if p is not None]
    q: list[float | None] = [None] * len(ps)
    if not valides:
        return q
    m = len(valides)
    tries = sorted(valides, key=lambda x: x[1])
    courant = 1.0
    for rang in range(m, 0, -1):
        i, p = tries[rang - 1]
        courant = min(courant, p * m / rang)
        q[i] = courant
    return q


def distribution_nulle(signal: np.ndarray, evaluer: Callable[[np.ndarray], dict], b: int,
                       rng: np.random.Generator,
                       generateur: Callable[[np.ndarray, np.random.Generator], np.ndarray]
                       ) -> dict[str, np.ndarray]:
    """B tirages du generateur, chacun evalue par le meme moteur ; None devient NaN."""
    valeurs: dict[str, list[float]] = {}
    for _ in range(b):
        for cle, x in evaluer(generateur(signal, rng)).items():
            valeurs.setdefault(cle, []).append(np.nan if x is None else float(x))
    return {cle: np.array(v, dtype=float) for cle, v in valeurs.items()}
