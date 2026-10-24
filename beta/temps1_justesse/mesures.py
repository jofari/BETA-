"""T1J : ce que l'on mesure d'un signal face au juge, sur une periode.

Periode mesuree M = [premier pivot du juge dans la periode, dernier pivot du juge dans la periode[ :
un episode n'appartient a une periode que si ses deux bornes y sont (clarification B), et le
dernier cycle, encore en cours, n'entre dans aucune mesure. Les rates comptent f = 1 dans les
medianes et les pires cas, d'entree (A) comme de sortie (precision du 24/10) ; leur nombre est
rapporte a part.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from beta.temps1_justesse import regles as R
from beta.temps1_justesse.detecteurs import BEAR, BULL, NEUTRE
from beta.temps1_justesse.juge import PIC, Juge


class MesureError(RuntimeError):
    """Regle non applicable telle qu'ecrite (prechauffe, aucun cycle complet) : pas de chiffre."""


def runs(masque: np.ndarray) -> list[tuple[int, int]]:
    """Suites de True consecutifs : (debut, fin incluse)."""
    m = np.concatenate([[False], np.asarray(masque, dtype=bool), [False]])
    bords = np.flatnonzero(m[1:] != m[:-1])
    return [(int(a), int(b) - 1) for a, b in zip(bords[::2], bords[1::2], strict=True)]


def domaine(j: Juge, debut: pd.Timestamp, fin: pd.Timestamp) -> tuple[int, int] | None:
    """Indices [m0, m1[ de la periode mesuree, ou None si moins de deux pivots dans la periode."""
    dans = [i for i, _ in j.pivots if debut <= j.dates[i] <= fin]
    return (dans[0], dans[-1]) if len(dans) >= 2 else None


def a_cheval(j: Juge, debut: pd.Timestamp, fin: pd.Timestamp) -> list[dict]:
    """Episodes dont une seule borne est dans la periode, et le cycle en cours s'il y commence."""
    sortie = []
    for (a, ta), (b, _) in zip(j.pivots, j.pivots[1:], strict=False):
        dedans = (debut <= j.dates[a] <= fin, debut <= j.dates[b] <= fin)
        if dedans[0] != dedans[1]:
            sortie.append({"type": "bear" if ta == PIC else "bull",
                           "debut": f"{j.dates[a]:%Y-%m-%d}", "fin": f"{j.dates[b]:%Y-%m-%d}"})
    if j.pivots and debut <= j.dates[j.pivots[-1][0]] <= fin:
        i, t = j.pivots[-1]
        sortie.append({"type": ("bear" if t == PIC else "bull") + " en cours",
                       "debut": f"{j.dates[i]:%Y-%m-%d}", "fin": None})
    return sortie


def _premier(sig: np.ndarray, a: int, b: int, valeur: float) -> int | None:
    idx = np.flatnonzero(sig[a:b] == valeur)
    return a + int(idx[0]) if len(idx) else None


def episodes_neutres(sig: np.ndarray, prix: np.ndarray, sigma_jour: np.ndarray) -> list[dict]:
    """Chaque suite de jours neutres : juste si |ln(P fin / P veille)| <= sigma_jour rac(n) (C)."""
    sortie = []
    for a, b in runs(sig == NEUTRE):
        n = b - a + 1
        if a == 0 or np.isnan(sigma_jour[a]):
            juste = None
        else:
            juste = bool(abs(math.log(prix[b] / prix[a - 1])) <= sigma_jour[a] * math.sqrt(n))
        sortie.append({"debut": a, "fin": b, "n": n, "juste": juste})
    return sortie


def hasard_neutres(prix: np.ndarray, sigma_jour: np.ndarray, durees: list[int], m0: int, m1: int,
                   graine: int = R.GRAINE, n_tirages: int = R.N_TIRAGES) -> float | None:
    """Taux de reussite de n_tirages episodes de durees tirees parmi `durees`, debut uniforme
    dans M (episode entierement dans M). Graine fixe : meme tirage a chaque relance."""
    if not durees:
        return None
    rng = np.random.default_rng(graine)
    ns = rng.choice(np.asarray(durees, dtype=int), size=n_tirages)
    debuts = rng.integers(m0, m1 - ns + 1)
    fins = debuts + ns - 1
    ecart = np.abs(np.log(prix[fins] / prix[debuts - 1]))
    return float(np.mean(ecart <= sigma_jour[debuts] * np.sqrt(ns)))


def _mediane(x: list[float]) -> float | None:
    return float(np.median(x)) if x else None


def _pire(x: list[float]) -> float | None:
    return float(np.max(x)) if x else None


def mesurer(signal: pd.Series, j: Juge, debut: str | pd.Timestamp, fin: str | pd.Timestamp | None,
            hasard: bool = False) -> dict:
    """Toutes les mesures d'un signal (calendrier de l'actif = celui du juge) sur une periode."""
    debut = pd.Timestamp(debut)
    fin = j.dates.max() if fin is None else min(pd.Timestamp(fin), j.dates.max())
    sig = signal.reindex(j.dates).to_numpy(dtype=float)
    prix = j.prix
    i_debut = int(j.dates.searchsorted(debut))
    i_fin = int(j.dates.searchsorted(fin, side="right")) - 1
    if i_debut < R.PRECHAUFFE_SEANCES:
        raise MesureError(f"prechauffe : {i_debut} seances avant {debut:%Y-%m-%d} "
                          f"(il en faut {R.PRECHAUFFE_SEANCES})")
    if np.isnan(sig[i_debut:i_fin + 1]).any():
        raise MesureError(f"signal indefini dans la periode {debut:%Y-%m-%d} -> {fin:%Y-%m-%d}")
    if i_debut < j.debut:
        raise MesureError(f"periode avant le premier trimestre juge ({j.infos['debut']})")
    dom = domaine(j, debut, fin)
    if dom is None:
        raise MesureError(f"moins de deux pivots du juge entre {debut:%Y-%m-%d} et {fin:%Y-%m-%d}")
    m0, m1 = dom
    annees = (j.dates[m1] - j.dates[m0]).days / 365.25

    entrees, f_e = [], []
    for a, b in j.bears():
        if not (m0 <= a and b <= m1):
            continue
        k = _premier(sig, a, b, BEAR)
        f = 1.0 if k is None else float((prix[a] - prix[k]) / (prix[a] - prix[b]))
        f_e.append(f)
        entrees.append({"pic": f"{j.dates[a]:%Y-%m-%d}", "creux": f"{j.dates[b]:%Y-%m-%d}",
                        "baisse": float(prix[b] / prix[a] - 1.0), "rate": k is None,
                        "f_entree": f,
                        "bascule": None if k is None else f"{j.dates[k]:%Y-%m-%d}",
                        "retard_jours": None if k is None else int((j.dates[k] - j.dates[a]).days),
                        "retard_seances": None if k is None else int(k - a)})
    sorties, f_s = [], []
    for c, p in j.bulls():
        if not (m0 <= c and p <= m1):
            continue
        k = _premier(sig, c, p, BULL)
        f = 1.0 if k is None else float((prix[k] - prix[c]) / (prix[p] - prix[c]))
        f_s.append(f)
        sorties.append({"creux": f"{j.dates[c]:%Y-%m-%d}", "pic": f"{j.dates[p]:%Y-%m-%d}",
                        "rate": k is None, "f_sortie": f,
                        "bascule": None if k is None else f"{j.dates[k]:%Y-%m-%d}"})
    if not entrees:
        raise MesureError(f"aucun bear complet du juge entre {debut:%Y-%m-%d} et {fin:%Y-%m-%d}")

    bear_juge = j.jours_bear()
    alertes = [(a, b) for a, b in runs(sig == BEAR) if m0 <= a < m1]
    fausses = [(a, b) for a, b in alertes if not bear_juge[a:b + 1].any()]
    s_m = sig[m0:m1]
    bascules = int(np.sum(s_m[1:] != s_m[:-1]))

    neutres = episodes_neutres(sig, prix, j.sigma_jour)
    juste_jour = np.zeros(len(sig), dtype=bool)
    for e in neutres:
        if e["juste"]:
            juste_jour[e["debut"]:e["fin"] + 1] = True
    bear_m = bear_juge[m0:m1]
    bien = (bear_m & (s_m == BEAR)) | (~bear_m & (s_m == BULL)) | ((s_m == NEUTRE)
                                                                  & juste_jour[m0:m1])
    r_bear = float(bien[bear_m].mean()) if bear_m.any() else None
    r_bull = float(bien[~bear_m].mean()) if (~bear_m).any() else None
    dans_m = [e for e in neutres if m0 <= e["debut"] and e["fin"] < m1]
    taux_neutre = (float(np.mean([e["juste"] for e in dans_m])) if dans_m else None)
    res = {
        "periode": [f"{debut:%Y-%m-%d}", f"{fin:%Y-%m-%d}"],
        "mesuree": [f"{j.dates[m0]:%Y-%m-%d}", f"{j.dates[m1]:%Y-%m-%d}"], "annees": annees,
        "n_bears": len(entrees), "f_entree_mediane": _mediane(f_e), "f_entree_pire": _pire(f_e),
        "rates_entree": int(sum(e["rate"] for e in entrees)),
        "n_bulls": len(sorties), "f_sortie_mediane": _mediane(f_s), "f_sortie_pire": _pire(f_s),
        "rates_sortie": int(sum(e["rate"] for e in sorties)),
        "n_alertes": len(alertes), "fausses_alertes": len(fausses),
        "fausses_alertes_an": len(fausses) / annees, "bascules": bascules,
        "bascules_an": bascules / annees, "r_bear": r_bear, "r_bull": r_bull,
        "justesse": None if r_bear is None or r_bull is None else (r_bear + r_bull) / 2,
        "jours_neutres": int(np.sum(s_m == NEUTRE)), "episodes_neutres": len(dans_m),
        "taux_neutres_justes": taux_neutre,
        "entrees": entrees, "sorties": sorties, "a_cheval": a_cheval(j, debut, fin),
    }
    if hasard and dans_m:
        res["taux_neutres_hasard"] = hasard_neutres(prix, j.sigma_jour, [e["n"] for e in dans_m],
                                                    m0, m1)
        res["n_tirages"] = R.N_TIRAGES
    return res
