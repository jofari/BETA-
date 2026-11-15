"""Choisir dans un lot : le SPA de Hansen et les p-values ajustees de Romano-Wolf.

OUTILS INFORMATIFS (15/11/2026). Aucun n'est une porte ni un verdict : S7 reste le Reality
Check studentise de `multitest.reality_check`, et rien ici n'entre dans `batterie.issue`.

S7 repond a « le MEILLEUR du lot bat-il la reference ? » par une seule p-value. Deux limites
connues, deux outils :

- **SPA de Hansen (2005)** — le Reality Check recentre CHAQUE candidate sur sa moyenne, y
  compris les tres mauvaises : ajouter au lot des candidates nettement perdantes gonfle la
  loi nulle du maximum et fait monter la p-value, donc baisse la puissance. Hansen ne
  recentre que celles qui ne sont pas clairement sous la reference. Trois p-values, toujours
  publiees ensemble : `p_bas` (liberale), `p_consistant` (la sienne), `p_haut` (prudente —
  le recentrage complet, donc le meme principe que S7, avec ici un ecart-type HAC).
  Un ecart large entre `p_consistant` et `p_haut` dit que le lot contient du lest ;
- **Romano & Wolf (2005), descente pas a pas** — S7 ne dit rien des AUTRES candidates. La
  descente donne a chacune une p-value ajustee qui controle le risque d'au moins un faux
  rejet dans tout le lot (FWER), en gardant la correlation entre candidates : moins brutale
  que Bonferroni, plus stricte que le FDR de S1.

Entree, comme S7 : {nom: serie}, toutes ALIGNEES (ligne t = meme jour), chacune une
performance deja RELATIVE a la reference (`multitest.univers_journalier` : P&L journalier en
R, reference zero).
"""

from __future__ import annotations

import math

import numpy as np

from beta.stats import bootstrap, multitest

N_REPETITIONS = 1000


def ecart_type_long_terme(x: np.ndarray, ell: float) -> float:
    """Ecart-type de racine(n) x moyenne, coherent avec le bootstrap stationnaire (Hansen 2005).

    omega^2 = gamma_0 + 2 x somme_{i=1}^{n-1} kappa(n, i) x gamma_i, avec
    kappa(n, i) = (n - i) / n x (1 - q)^i + i / n x (1 - q)^(n - i), q = 1 / ell.
    C'est la variance que le bootstrap de Politis-Romano attribue a la moyenne : diviser par
    elle met la statistique observee et ses tirages sur la meme echelle.
    """
    x = np.asarray(x, dtype=float)
    n = len(x)
    if n < 3:
        return float("nan")
    centre = x - x.mean()
    gamma = np.correlate(centre, centre, mode="full")[n - 1:] / n
    q = 1.0 / max(float(ell), 1.0)
    i = np.arange(1, n)
    kappa = (n - i) / n * (1.0 - q) ** i + i / n * (1.0 - q) ** (n - i)
    variance = float(gamma[0] + 2.0 * (kappa * gamma[1:]).sum())
    return math.sqrt(variance) if variance > 0 else float("nan")


def _tirages(matrice: np.ndarray, ell: float, n_repetitions: int, graine: int) -> np.ndarray:
    """(B, k) : la moyenne de chaque colonne sur chaque tirage conjoint par blocs."""
    t = matrice.shape[0]
    rng = np.random.default_rng(graine)
    return np.array([matrice[bootstrap.indices(t, t, ell, rng)].mean(axis=0)
                     for _ in range(n_repetitions)])


def _preparer(series: dict[str, np.ndarray], ell: float | None):
    noms, matrice = multitest._matrice(series)
    if not noms or matrice.shape[0] < 10:
        return noms, matrice, None, None, None
    t = matrice.shape[0]
    ell = bootstrap.longueur_optimale(matrice[:, 0]) if ell is None else float(ell)
    omega = np.array([ecart_type_long_terme(matrice[:, j], ell)
                      for j in range(matrice.shape[1])])
    return noms, matrice, ell, omega, t


def spa_hansen(series: dict[str, np.ndarray], n_repetitions: int = N_REPETITIONS,
               ell: float | None = None, graine: int = 0) -> dict:
    """Test SPA : H0, aucune candidate ne bat la reference. Rend p_bas, p_consistant, p_haut.

    T = max(max_k racine(n) x moyenne_k / omega_k, 0). Sous H0, chaque tirage est recentre
    par g(moyenne_k) : max(moyenne_k, 0) pour `p_bas` ; moyenne_k si
    racine(n) x moyenne_k / omega_k >= -racine(2 ln ln n), sinon 0, pour `p_consistant` ;
    moyenne_k pour `p_haut`. Les candidates d'ecart-type nul (aucun trade) sont ignorees.
    """
    noms, matrice, ell, omega, t = _preparer(series, ell)
    vide = {"n_candidates": len(noms), "p_bas": float("nan"),
            "p_consistant": float("nan"), "p_haut": float("nan"), "meilleure": None}
    if omega is None:
        return vide
    utiles = np.isfinite(omega) & (omega > 0)
    if not utiles.any():
        return vide
    m, w = matrice[:, utiles], omega[utiles]
    gardes = [n for n, u in zip(noms, utiles, strict=True) if u]
    moyennes = m.mean(axis=0)
    racine = math.sqrt(t)
    stats_k = racine * moyennes / w
    observe = max(float(stats_k.max()), 0.0)
    seuil = -math.sqrt(2.0 * math.log(math.log(t)))
    recentrages = {"p_bas": np.maximum(moyennes, 0.0),
                   "p_consistant": np.where(stats_k >= seuil, moyennes, 0.0),
                   "p_haut": moyennes}
    tirages = _tirages(m, ell, n_repetitions, graine)
    sortie = {"n_candidates": len(gardes), "n_observations": t, "statistique": observe,
              "ell": float(ell), "n_repetitions": n_repetitions,
              "meilleure": gardes[int(np.argmax(stats_k))],
              "n_recentrees": int((stats_k >= seuil).sum())}
    for nom, g in recentrages.items():
        nuls = np.maximum((racine * (tirages - g) / w).max(axis=1), 0.0)
        sortie[nom] = (int((nuls >= observe).sum()) + 1) / (n_repetitions + 1)
    return sortie


def romano_wolf(series: dict[str, np.ndarray], n_repetitions: int = N_REPETITIONS,
                ell: float | None = None, graine: int = 0) -> dict:
    """p-values ajustees par descente pas a pas (H0_k : la candidate k ne bat pas la reference).

    Statistiques t_k = racine(n) x moyenne_k / omega_k, rangees de la plus forte a la plus
    faible. La p ajustee de la j-ieme = part des tirages ou le maximum, pris sur les
    candidates de rang >= j, des t recentres atteint t_(j) ; puis rendue monotone (une
    candidate ne peut pas etre mieux notee qu'une candidate plus forte qu'elle).
    Rend {nom: {"t": ..., "p_ajustee": ...}}, dans l'ordre des t decroissants.
    """
    noms, matrice, ell, omega, t = _preparer(series, ell)
    if omega is None:
        return {"n_candidates": len(noms), "candidates": {}}
    utiles = np.isfinite(omega) & (omega > 0)
    if not utiles.any():
        return {"n_candidates": 0, "candidates": {}}
    m, w = matrice[:, utiles], omega[utiles]
    gardes = [n for n, u in zip(noms, utiles, strict=True) if u]
    moyennes = m.mean(axis=0)
    racine = math.sqrt(t)
    stats_k = racine * moyennes / w
    nuls = racine * (_tirages(m, ell, n_repetitions, graine) - moyennes) / w
    ordre = np.argsort(-stats_k)
    ajustees, precedente = {}, 0.0
    for rang, k in enumerate(ordre):
        maxima = nuls[:, ordre[rang:]].max(axis=1)
        p = (int((maxima >= stats_k[k]).sum()) + 1) / (n_repetitions + 1)
        precedente = max(precedente, p)
        ajustees[gardes[k]] = {"t": float(stats_k[k]), "moyenne": float(moyennes[k]),
                               "p_ajustee": float(precedente)}
    return {"n_candidates": len(gardes), "n_observations": t, "ell": float(ell),
            "n_repetitions": n_repetitions, "candidates": ajustees}
