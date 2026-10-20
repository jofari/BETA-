"""Test invest — metriques standard (A4) et de survie (B1-B4).

Index : les courbes V ont N + 1 points (V[0] = 1 a la cloture P0, V[i] apres le jour i) ;
l'exposition `e` a N points, `e[i]` decidee a la cloture du V-index i (elle joue sur le jour
i + 1). Un episode, ses dates de reaction et de retour sont des V-index. Les annees comptent
365 jours (cahier des charges) ; le drawdown inclut V[0] = 1 (une perte du premier jour en est
un) ; l'Ulcer et la duree sous l'eau portent sur les N jours.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from beta.invest.moteur import Mapping
from beta.stats import multitest

JOURS_AN = 365
EPS = 1e-12


def courbe(r: np.ndarray) -> np.ndarray:
    return np.concatenate([[1.0], np.cumprod(1.0 + np.asarray(r, dtype=float))])


def drawdown(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    return v / np.maximum.accumulate(v) - 1.0


def _plus_longue_suite(masque: np.ndarray) -> int:
    m = np.asarray(masque, dtype=np.int8)
    if not m.any():
        return 0
    bords = np.diff(np.concatenate([[0], m, [0]]))
    return int((np.flatnonzero(bords == -1) - np.flatnonzero(bords == 1)).max())


def _cagr(v_fin: float, n: int) -> float:
    return v_fin ** (JOURS_AN / n) - 1.0 if v_fin > 0 else -1.0


def standard(r: np.ndarray, e: np.ndarray | None = None, rf: np.ndarray | None = None,
             n_essais: int | None = None) -> dict:
    """A4 : rendement, CAGR, vol, Sharpe (racine de 365, net de rf), DSR, MDD, duree sous
    l'eau, Calmar, Ulcer ; exposition moyenne et nombre de changements si `e` est donnee."""
    r = np.asarray(r, dtype=float)
    n = len(r)
    v = courbe(r)
    dd = drawdown(v)[1:]
    excedent = r - (0.0 if rf is None else np.asarray(rf, dtype=float))
    ecart = float(np.std(r, ddof=1)) if n > 1 else float("nan")
    cagr = _cagr(float(v[-1]), n)
    mdd = float(dd.min()) if n else 0.0
    sortie = {
        "n_jours": n, "rendement_total": float(v[-1] - 1.0), "cagr": cagr,
        "vol": ecart * math.sqrt(JOURS_AN),
        "sharpe": (float(np.mean(excedent)) / ecart * math.sqrt(JOURS_AN)
                   if ecart and ecart > 0 else None),
        "dsr": None, "n_essais": n_essais,
        "mdd": mdd, "duree_sous_eau_max_j": _plus_longue_suite(dd < -EPS),
        "calmar": cagr / abs(mdd) if mdd < -EPS else None,
        "ulcer": float(math.sqrt(np.mean(dd ** 2))) if n else 0.0,
        "expo_moyenne": None, "changements_expo": None,
    }
    if n_essais:
        sortie["dsr"] = multitest.sharpe_degonfle(excedent, n_essais)["dsr"]
    if e is not None:
        e = np.asarray(e, dtype=float)
        sortie["expo_moyenne"] = float(e.mean())
        sortie["changements_expo"] = int((np.diff(e) != 0).sum())
    return sortie


# =========================================================================================
# B1 — les episodes de grande baisse du benchmark
# =========================================================================================

def episodes(v: np.ndarray, theta: float) -> list[dict]:
    """Chaque passage sous -theta depuis le plus haut : pic, creux, fin (None si non rattrape).

    pic = dernier plus haut historique avant le passage ; creux = point le plus bas avant le
    retour au niveau du pic ; fin = ce retour. Les episodes ne se chevauchent pas : la baisse
    suivante ne compte qu'apres le retour au pic.
    """
    v = np.asarray(v, dtype=float)
    hwm = np.maximum.accumulate(v)
    dd = np.round(v / hwm - 1.0, 12)
    sortie, i, n = [], 0, len(v)
    while i < n:
        if dd[i] > -theta:
            i += 1
            continue
        pic = int(np.flatnonzero(v[: i + 1] == hwm[i])[-1])
        apres = np.flatnonzero(v[i + 1:] >= hwm[i])
        fin = int(i + 1 + apres[0]) if len(apres) else None
        creux = int(i + np.argmin(v[i:(fin if fin is not None else n)]))
        sortie.append({"pic": pic, "creux": creux, "fin": fin,
                       "perte": float(v[creux] / v[pic] - 1.0)})
        if fin is None:
            break
        i = fin
    return sortie


# =========================================================================================
# B2-B4 — protection, retard, retour tardif, faux signaux
# =========================================================================================

def protection_agregee(eps: list[dict]) -> float | None:
    """Prot = somme |L_B| Prot_j / somme |L_B| : les grandes baisses pesent plus."""
    poids = [(abs(e["perte_b"]), e["protection"]) for e in eps if e["protection"] is not None]
    total = sum(p for p, _ in poids)
    return sum(p * x for p, x in poids) / total if total > 0 else None


def survie(v_b: np.ndarray, v_s: np.ndarray, e: np.ndarray, eps: list[dict], m: Mapping,
           theta_f: float, horizon_j: int) -> dict:
    v_b, v_s, e = (np.asarray(x, dtype=float) for x in (v_b, v_s, e))
    n = len(e)
    defensif = np.round(e, 12) <= m.e_def + EPS
    au_moins_neutre = np.round(e, 12) >= m.e_neutre - EPS
    sortie = []
    for ep in eps:
        pic, creux, fin = ep["pic"], ep["creux"], ep["fin"]
        perte_b = float(v_b[creux] / v_b[pic] - 1.0)
        perte_s = float(v_s[creux] / v_s[pic] - 1.0)
        detail = {"pic": pic, "creux": creux, "fin": fin, "perte_b": perte_b,
                  "perte_s": perte_s, "protection": 1.0 - perte_s / perte_b,
                  "retard_j": None, "part_subie": None}
        borne = min(fin if fin is not None else len(v_b), n)
        reaction = np.flatnonzero(defensif[pic:borne])
        if len(reaction):
            t_def = pic + int(reaction[0])
            detail["retard_j"] = t_def - pic
            detail["part_subie"] = float((v_b[pic] - v_b[t_def]) / (v_b[pic] - v_b[creux]))
        if creux >= n:
            detail.update(retour="creux en fin de donnees", retour_j=None, rebond_rate=0.0)
        elif au_moins_neutre[creux]:
            detail.update(retour="pas defensif au creux", retour_j=None, rebond_rate=0.0)
        else:
            retour = np.flatnonzero(au_moins_neutre[creux + 1:])
            if len(retour):
                t_ret = creux + 1 + int(retour[0])
                detail.update(retour="retour a e_neutre ou plus", retour_j=t_ret - creux,
                              rebond_rate=float(v_b[t_ret] / v_b[creux] - 1.0))
            else:
                detail.update(retour="pas de retour avant la fin", retour_j=None,
                              rebond_rate=float(v_b[-1] / v_b[creux] - 1.0))
        sortie.append(detail)
    return {"episodes": sortie, "protection": protection_agregee(sortie),
            "faux_signaux": faux_signaux(v_b, e, defensif, theta_f, horizon_j)}


def faux_signaux(v_b: np.ndarray, e: np.ndarray, defensif: np.ndarray, theta_f: float,
                 horizon_j: int) -> dict:
    """Un passage en defensif est FAUX si le benchmark ne perd pas theta_f dans les H jours.

    Non evaluable si la baisse n'a pas eu lieu et que les H jours depassent les donnees. Cout
    d'un faux signal : (E avant - E defensive) x rendement du benchmark pendant la periode
    defensive (positif = hausse ratee, negatif = baisse evitee quand meme).
    """
    n, dernier = len(e), len(v_b) - 1
    detail = []
    for k in np.flatnonzero(defensif[1:] & ~defensif[:-1]) + 1:
        k = int(k)
        haut = min(k + horizon_j, dernier)
        baisse = float((v_b[k + 1:haut + 1] / v_b[k] - 1.0).min()) if haut > k else 0.0
        if baisse <= -theta_f + EPS:
            statut = "vrai"
        elif k + horizon_j > dernier:
            statut = "non evaluable"
        else:
            statut = "faux"
        cout = None
        if statut == "faux":
            sortie = next((u for u in range(k + 1, n) if not defensif[u]), dernier)
            cout = float((e[k - 1] - e[k]) * (v_b[sortie] / v_b[k] - 1.0))
        detail.append({"k": k, "statut": statut, "baisse_max": baisse, "cout": cout})
    faux = [d for d in detail if d["statut"] == "faux"]
    return {"n_passages": len(detail),
            "n_evalues": sum(d["statut"] != "non evaluable" for d in detail),
            "n_non_evaluables": sum(d["statut"] == "non evaluable" for d in detail),
            "n_faux": len(faux), "cout_cumule": float(sum(d["cout"] for d in faux)),
            "detail": detail}


# =========================================================================================
# Captures, sur rendements hebdomadaires
# =========================================================================================

def captures(r_s: np.ndarray, r_b: np.ndarray, jours: pd.DatetimeIndex) -> dict:
    """Capture haussiere / baissiere sur semaines civiles COMPLETES (lundi -> dimanche UTC)."""
    iso = jours.isocalendar()
    cle = iso["year"].to_numpy(dtype=np.int64) * 100 + iso["week"].to_numpy(dtype=np.int64)
    g = pd.DataFrame({"cle": cle, "s": np.log1p(r_s), "b": np.log1p(r_b)}).groupby("cle")
    completes = (g.size() == 7).to_numpy()
    sommes = g[["s", "b"]].sum()[completes]
    rs, rb = np.expm1(sommes["s"].to_numpy()), np.expm1(sommes["b"].to_numpy())
    hausse, baisse = rb > 0, rb < 0
    return {"n_semaines": int(completes.sum()), "n_hausse": int(hausse.sum()),
            "n_baisse": int(baisse.sum()),
            "haussiere": float(rs[hausse].mean() / rb[hausse].mean()) if hausse.any() else None,
            "baissiere": float(rs[baisse].mean() / rb[baisse].mean()) if baisse.any() else None}


# =========================================================================================
# Les quatre metriques des nulls, en une passe (24 000 tirages par campagne)
# =========================================================================================

def pour_nulls(r: np.ndarray, v_b: np.ndarray, eps: list[dict]) -> dict:
    """Ulcer, |MDD|, Calmar et Prot : memes definitions que `standard` et `survie`."""
    v = courbe(r)
    dd = drawdown(v)[1:]
    mdd = float(dd.min())
    cagr = _cagr(float(v[-1]), len(r))
    prot = None
    if eps:
        pic = np.array([x["pic"] for x in eps])
        creux = np.array([x["creux"] for x in eps])
        perte_b = v_b[creux] / v_b[pic] - 1.0
        perte_s = v[creux] / v[pic] - 1.0
        prot = float(np.sum(np.abs(perte_b) * (1.0 - perte_s / perte_b)) / np.sum(np.abs(perte_b)))
    return {"ulcer": float(math.sqrt(np.mean(dd ** 2))), "mdd_abs": abs(mdd),
            "calmar": cagr / abs(mdd) if mdd < -EPS else math.inf, "prot": prot}
