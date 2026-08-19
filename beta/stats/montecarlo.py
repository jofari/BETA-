"""S4 — Monte-Carlo sur la sequence des trades : cone d'equity, P(perte), P(drawdown).

Une courbe d'equity est UN tirage. L'ordre dans lequel les trades sont arrives n'a rien de
necessaire : la meme strategie, sur le meme marche decale de trois semaines, aurait produit
un autre dessin. Ce module montre l'ensemble des dessins compatibles avec les memes trades.

Deux rejeux, qui ne repondent pas a la meme question :

- **permutation** — memes trades, ordre melange. Le rendement final est identique a chaque
  tirage ; seul le CHEMIN change. C'est le test du drawdown : « la sequence observee
  etait-elle chanceuse ? » ;
- **reechantillonnage avec remise** — on tire des trades au hasard, avec repetition. Le
  rendement final varie. C'est le test de l'esperance : « combien de fois ce systeme
  finit-il en perte ? »

Le drawdown maximal est la mesure la plus fragile d'un backtest, celle qui varie le plus
d'un tirage a l'autre. Annoncer « MDD 9,5 % » sans le cone, c'est annoncer le tirage le plus
flatteur d'une famille dont on n'a pas regarde l'etendue.
"""

from __future__ import annotations

import numpy as np

N_TIRAGES = 10_000
PERCENTILES_CONE = (5, 25, 50, 75, 95)
SEUIL_DD_PCT = 20.0


def _courbes(matrice_r: np.ndarray, capital: float, risque_pct: float) -> np.ndarray:
    """(n_tirages, n_trades) d'equity, a risque fixe sur le capital initial."""
    gains = matrice_r * capital * risque_pct / 100.0
    return capital + np.cumsum(gains, axis=1)


def _drawdown_max_pct(courbes: np.ndarray) -> np.ndarray:
    sommets = np.maximum.accumulate(courbes, axis=1)
    return np.min((courbes / sommets - 1.0) * 100.0, axis=1)


def simuler(r: np.ndarray, mode: str = "permutation", n_tirages: int = N_TIRAGES,
            capital: float = 100_000.0, risque_pct: float = 1.0,
            graine: int = 0) -> dict:
    """Rejoue la sequence de R `n_tirages` fois. `mode` : permutation | remise.

    Retourne le cone (percentiles d'equity trade par trade), la distribution du resultat
    final, celle du drawdown maximal, et les deux probabilites qui decident : finir en
    perte, et depasser le seuil de drawdown.
    """
    x = np.asarray(r, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 2:
        return {"n": n, "mode": mode, "erreur": "trop peu de trades pour un Monte-Carlo"}

    rng = np.random.default_rng(graine)
    if mode == "permutation":
        matrice = np.array([rng.permutation(x) for _ in range(n_tirages)])
    elif mode == "remise":
        matrice = x[rng.integers(0, n, size=(n_tirages, n))]
    else:
        raise ValueError(f"mode inconnu : {mode} (permutation | remise)")

    courbes = _courbes(matrice, capital, risque_pct)
    finaux = courbes[:, -1]
    dd = _drawdown_max_pct(courbes)
    reel = _courbes(x[None, :], capital, risque_pct)[0]
    dd_reel = float(_drawdown_max_pct(reel[None, :])[0])

    return {
        "n": n, "mode": mode, "n_tirages": n_tirages,
        "capital": capital, "risque_pct": risque_pct,
        "equity_finale_reelle": float(reel[-1]),
        "equity_finale": {f"p{p}": float(np.percentile(finaux, p))
                          for p in PERCENTILES_CONE},
        "drawdown_max_reel_pct": dd_reel,
        "drawdown_max": {f"p{p}": float(np.percentile(dd, 100 - p))
                         for p in PERCENTILES_CONE},
        "p_perte": float((finaux < capital).mean()),
        "p_drawdown_pire_que_seuil": float((dd <= -SEUIL_DD_PCT).mean()),
        "seuil_dd_pct": SEUIL_DD_PCT,
        # Rang du drawdown observe dans la distribution simulee : proche de 0, la sequence
        # reelle a ete CHANCEUSE, et le MDD publie sous-estime le risque reel.
        "centile_drawdown_reel": float((dd <= dd_reel).mean() * 100.0),
        "cone": {f"p{p}": np.percentile(courbes, p, axis=0).tolist()
                 for p in PERCENTILES_CONE},
    }


def resume(r: np.ndarray, n_tirages: int = N_TIRAGES, capital: float = 100_000.0,
           risque_pct: float = 1.0, graine: int = 0) -> dict:
    """Les deux modes d'un coup — c'est la paire qu'il faut lire, jamais l'un des deux."""
    return {"permutation": simuler(r, "permutation", n_tirages, capital, risque_pct, graine),
            "remise": simuler(r, "remise", n_tirages, capital, risque_pct, graine)}
