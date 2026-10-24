"""T1F : les deux modeles nuls, appliques au signal observe sur la periode mesuree de T1J.

Test 1 (clarification 1) : la suite des etats est gardee telle quelle, les durees sont melangees
entre episodes du MEME etat. Parts de jours bear / bull / neutre, nombre de bascules et
durees sont donc conserves exactement ; seules les positions changent.
Test 1 bis (clarification 4) : decalage circulaire de k seances, k uniforme dans [90, N - 90].
"""

from __future__ import annotations

import numpy as np

from beta.temps1_fiabilite import regles as R


def episodes(seg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Etats et durees des episodes consecutifs de meme etat d'un segment sans NaN."""
    seg = np.asarray(seg, dtype=float)
    if len(seg) == 0 or np.isnan(seg).any():
        raise ValueError("segment vide ou avec des jours sans signal")
    bords = np.flatnonzero(seg[1:] != seg[:-1]) + 1
    debuts = np.concatenate([[0], bords])
    fins = np.concatenate([bords, [len(seg)]])
    return seg[debuts], fins - debuts


def permuter_par_etat(seg: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Meme suite d'etats ; les durees des episodes d'un meme etat sont permutees entre elles."""
    etats, durees = episodes(seg)
    nouvelles = durees.copy()
    for etat in np.unique(etats):                    # ordre fixe : -1, 0, +1
        idx = np.flatnonzero(etats == etat)
        nouvelles[idx] = durees[idx][rng.permutation(len(idx))]
    return np.repeat(etats, nouvelles)


def decaler(seg: np.ndarray, rng: np.random.Generator,
            minimum: int = R.DECALAGE_MIN) -> np.ndarray:
    """Decalage circulaire de k seances, k uniforme dans [minimum, N - minimum]."""
    n = len(seg)
    if n < 2 * minimum:
        raise ValueError(f"plage de {n} seances : pas de decalage d'au moins {minimum} possible")
    k = int(rng.integers(minimum, n - minimum + 1))
    return np.roll(np.asarray(seg, dtype=float), k)
