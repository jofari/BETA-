"""VC6 V2 : les nulls des deux essais (applications 14 a 16 du preenregistrement).

« V2 – HAR sans regime » (le null teste le signal de volatilite, pas le regime) : la serie tiree est
celle des positions tenues x_i(t) = w_i Ei(t), decisions D_0 .. D_{N-1}, les trois poches ensemble.
- circulaire : x'(t) = x((t + k) mod N), k entier uniforme dans [90 ; N - 90] (meme tirage que
  `beta.invest.nulls.decalage_circulaire`) ;
- segments : x coupee depuis D_0 en blocs consecutifs de 63 jours (le dernier plus court), blocs
  remis dans un ordre tire au hasard.
Chaque tirage recalcule le rendement net par `moteur.pnl` sur les vrais rendements (frais sur les
variations de la serie tiree, financement aux vraies dates). Bande, filtre et securite ne sont pas
reappliques : ils sont deja dans la serie tiree.

« V2 – poche baissiere sous HAR » : le null de la V1 (serie du mode, decalage circulaire et melange
de segments), moteur complet a chaque tirage.

p : `beta.invest.nulls.p_value` (1 + #{Ulcer nul <= observe}) / (1 + B), p retenue = max (D4).
"""

from __future__ import annotations

import math

import numpy as np

from beta.invest import metriques
from beta.invest import nulls as nl
from beta.vc6_v2 import moteur as mt
from beta.vc6_v2 import regles as R


def ulcer(r: np.ndarray) -> float:
    """Meme formule que la V1 (`beta.vc6.campagne.ulcer`)."""
    return float(math.sqrt(np.mean(metriques.drawdown(metriques.courbe(r))[1:] ** 2)))


def tirer_k(n: int, rng: np.random.Generator, m: int = R.M_DECALAGE) -> int:
    """k uniforme dans [m ; n - m] : le tirage de `beta.invest.nulls.decalage_circulaire`."""
    if n < 2 * m + 1:
        raise ValueError(f"serie de {n} jours : trop courte pour un decalage d'au moins {m} j")
    return int(rng.integers(m, n - m + 1))


def decaler(x: np.ndarray, k: int) -> np.ndarray:
    """x'(t) = x((t + k) mod N), sur l'axe du temps (les poches restent ensemble)."""
    return np.roll(np.asarray(x), -k, axis=0)


def n_blocs(n: int, taille: int = R.BLOC_SEGMENTS) -> int:
    return -(-n // taille)


def permuter_blocs(x: np.ndarray, ordre, taille: int = R.BLOC_SEGMENTS) -> np.ndarray:
    """Blocs consecutifs de `taille` jours depuis le debut (le dernier plus court), dans `ordre`."""
    x = np.asarray(x)
    blocs = [x[i * taille:(i + 1) * taille] for i in range(n_blocs(len(x), taille))]
    ordre = [int(i) for i in ordre]
    if sorted(ordre) != list(range(len(blocs))):
        raise ValueError("ordre des blocs : ce n'est pas une permutation")
    return np.concatenate([blocs[i] for i in ordre], axis=0)


def r_positions(ent: mt.Entrees, sim: dict, p: mt.Parametres, y: np.ndarray) -> np.ndarray:
    """Rendement net d'une serie de positions tiree, sur les vrais rendements."""
    return mt.pnl(ent, sim["lignes"], sim["poches"], p.poids, y, p.frais_pb)["r"]


def distribution_positions(ent: mt.Entrees, p: mt.Parametres, sim: dict, cle: str,
                           b: int = R.B_NULLS) -> dict[str, np.ndarray]:
    """B Ulcer nuls de chaque null des positions (« V2 – HAR sans regime »)."""
    y = sim["y"]
    n = len(y)
    sortie = {}
    rng = nl.flux(R.GRAINE, R.ID_EXP, cle, "circulaire")
    u = np.empty(b)
    for i in range(b):
        u[i] = ulcer(r_positions(ent, sim, p, decaler(y, tirer_k(n, rng))))
    sortie["circulaire"] = u
    rng = nl.flux(R.GRAINE, R.ID_EXP, cle, "segments")
    u = np.empty(b)
    for i in range(b):
        u[i] = ulcer(r_positions(ent, sim, p, permuter_blocs(y, rng.permutation(n_blocs(n)))))
    sortie["segments"] = u
    return sortie


def signal_mode(ent: mt.Entrees) -> tuple[np.ndarray, np.ndarray]:
    """Le mode aux decisions D_0 .. D_{N-1} (le signal tire) et celui de D_N (jamais joue)."""
    return ent.baissier[:ent.n].astype(float), ent.baissier[ent.n:]


def mode_tire(ent: mt.Entrees, s: np.ndarray) -> np.ndarray:
    _, dernier = signal_mode(ent)
    return np.concatenate([np.asarray(s) > 0.5, dernier])


def mode_circulaire(ent: mt.Entrees, k: int) -> np.ndarray:
    signal, _ = signal_mode(ent)
    return mode_tire(ent, decaler(signal, k))


def distribution_mode(ent: mt.Entrees, p: mt.Parametres, cle: str,
                      b: int = R.B_NULLS) -> dict[str, np.ndarray]:
    """B Ulcer nuls de chaque null du mode (« V2 – poche baissiere sous HAR », null de la V1)."""
    signal, _ = signal_mode(ent)
    n = len(signal)
    sortie = {}
    rng = nl.flux(R.GRAINE, R.ID_EXP, cle, "circulaire")
    u = np.empty(b)
    for i in range(b):
        u[i] = ulcer(mt.simuler(ent, p, mode_circulaire(ent, tirer_k(n, rng)))["r"])
    sortie["circulaire"] = u
    rng = nl.flux(R.GRAINE, R.ID_EXP, cle, "segments")
    u = np.empty(b)
    for i in range(b):
        u[i] = ulcer(mt.simuler(ent, p, mode_tire(ent, nl.melange_segments(signal, rng)))["r"])
    sortie["segments"] = u
    return sortie


def p_values(dist: dict[str, np.ndarray], ulcer_observe: float) -> dict:
    pc = nl.p_value(dist["circulaire"], ulcer_observe, True)
    ps = nl.p_value(dist["segments"], ulcer_observe, True)
    pr = nl.p_retenue(pc, ps)
    return {"p_circulaire": pc, "p_segments": ps, "p_retenue": pr, "verdict_d4": nl.verdict(pr),
            "ulcer_nul_median": {k: float(np.median(v)) for k, v in dist.items()}}
