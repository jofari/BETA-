"""VC6 V1, Temps 2 : mesures du rapport seulement (applications 27 a 35). Rien ne decide ici.

Alignement : `sim[...][k]` est la position decidee a la cloture de D_k et appliquee au rendement du
jour D_{k+1} ; la courbe v = courbe(r) a N + 1 points, v[k] = valeur a la cloture de D_k.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from beta.invest import metriques
from beta.vc6 import moteur as mt
from beta.vc6 import regles as R


def _j(jours: pd.DatetimeIndex, k: int | None) -> str | None:
    return None if k is None else f"{jours[k]:%Y-%m-%d}"


def _chaine(r: np.ndarray) -> tuple[float, float]:
    if len(r) == 0:
        return 0.0, 0.0
    v = metriques.courbe(r)
    return float(v[-1] - 1.0), float(metriques.drawdown(v).min())


def levier(sim: dict) -> dict:
    """Application 34 : jours ou au moins une poche a Ei > 1."""
    masque = (sim["e"] > 1 + 1e-12).any(axis=1)
    rend, dd = _chaine(sim["r"][masque])
    return {"expo_moyenne": float(sim["expo_totale"].mean()), "jours": int(masque.sum()),
            "rendement": rend, "drawdown": dd,
            "financement": float(sim["financement"][masque].sum()),
            "gain_part_en_levier": float(sim["levier_brut"][masque].sum())}


def bascules(baissier: np.ndarray) -> list[int]:
    """Decisions k >= 1 ou le mode change."""
    b = np.asarray(baissier, dtype=bool)
    return [int(k) for k in np.flatnonzero(b[1:] != b[:-1]) + 1]


def grands_bears(jours: pd.DatetimeIndex, close_btc: np.ndarray, baissier: np.ndarray,
                 courbes: dict[str, np.ndarray]) -> list[dict]:
    """Application 27 : episodes du BTC >= 30 %, delai jusqu'a la bascule en baissier."""
    v = np.asarray(close_btc, dtype=float) / close_btc[0]
    sortie = []
    n = len(baissier)
    for ep in metriques.episodes(v, R.SEUIL_GRAND_BEAR):
        pic = ep["pic"]
        bascule = None
        if baissier[pic] and pic > 0 and baissier[pic - 1]:
            debut = pic
            while debut > 0 and baissier[debut - 1]:
                debut -= 1
            bascule = debut
        else:
            suite = [k for k in range(max(pic, 1), n) if baissier[k] and not baissier[k - 1]]
            bascule = suite[0] if suite else None
        d = {"pic": _j(jours, pic), "creux": _j(jours, ep["creux"]), "fin": _j(jours, ep["fin"]),
             "baisse_btc": ep["perte"], "bascule": _j(jours, bascule),
             "delai_j": None if bascule is None else bascule - pic,
             "baisse_btc_avant_bascule": None if bascule is None
             else float(v[bascule] / v[pic] - 1.0), "perte_variantes": {}}
        if bascule is not None and bascule >= pic:
            for cle, c in courbes.items():
                d["perte_variantes"][cle] = float(c[bascule] / c[pic] - 1.0)
        sortie.append(d)
    return sortie


def aller_retours(jours: pd.DatetimeIndex, baissier: np.ndarray, sim: dict,
                  r_temoin: np.ndarray) -> dict:
    """Application 28 : bascule puis bascule inverse moins de 30 jours plus tard."""
    bs = bascules(baissier[:len(sim["r"])])
    detail = []
    for k1, k2 in zip(bs[:-1], bs[1:]):
        if k2 - k1 >= R.ALLER_RETOUR_J:
            continue
        fin = min(k2 + R.RAMPE, len(sim["r"]))
        frais = float(sim["frais"][k1:fin].sum())
        rv = float(np.prod(1 + sim["r"][k1:fin]) - 1)
        rt = float(np.prod(1 + r_temoin[k1:fin]) - 1)
        detail.append({"bascule": _j(jours, k1), "retour": _j(jours, k2), "duree_j": k2 - k1,
                       "vers": "baissier" if baissier[k1] else "haussier", "frais": frais,
                       "rendement": rv, "rendement_temoin": rt, "ecart_temoin": rv - rt})
    return {"n": len(detail), "frais_total": float(sum(d["frais"] for d in detail)),
            "ecart_temoin_total": float(sum(d["ecart_temoin"] for d in detail)),
            "detail": detail}


def pires_drawdowns(jours: pd.DatetimeIndex, sim: dict, k: int = 5) -> list[dict]:
    """Application 29 : episodes de la courbe, sans chevauchement, les k plus profonds."""
    v = metriques.courbe(sim["r"])
    eps = sorted(metriques.episodes(v, 1e-9), key=lambda e: e["perte"])[:k]
    n = len(sim["r"])
    sortie = []
    for e in eps:
        pic = e["pic"]
        sortie.append({"debut": _j(jours, pic), "creux": _j(jours, e["creux"]),
                       "recuperation": _j(jours, e["fin"]), "profondeur": e["perte"],
                       "mode_au_debut": ("baissier" if sim["baissier"][min(pic, n - 1)]
                                         else "haussier"),
                       "expo_au_debut": float(sim["expo_totale"][min(pic, n - 1)])})
    return sortie


def contributions(sim: dict) -> dict:
    """Application 30 : sur toute la periode et pendant le drawdown max."""
    v = metriques.courbe(sim["r"])
    dd = metriques.drawdown(v)
    creux = int(np.argmin(dd))
    pic = int(np.flatnonzero(v[:creux + 1] == np.maximum.accumulate(v)[creux])[-1])
    total = {k: float(x.sum()) for k, x in sim["contributions"].items()}
    pendant = {k: float(x[pic:creux].sum()) for k, x in sim["contributions"].items()}
    total.update(frais=-float(sim["frais"].sum()), financement=-float(sim["financement"].sum()))
    pendant.update(frais=-float(sim["frais"][pic:creux].sum()),
                   financement=-float(sim["financement"][pic:creux].sum()))
    return {"total": total, "drawdown_max": pendant, "pic": pic, "creux": creux}


def conflits(ent: mt.Entrees, p: mt.Parametres, sim: dict, au_dessus: dict[str, np.ndarray]
             ) -> dict:
    """Application 31. `au_dessus[a][k]` : cloture de a >= sa SMA 200 a D_k (ETH, SOL)."""
    n = ent.n
    b = ent.baissier[:n]
    conflit = {a: b & au_dessus[a][:n] for a in au_dessus}
    effet = {}
    for a, m in conflit.items():
        i = list(p.poids).index(a)
        x = 0.0
        for k in np.flatnonzero(m):
            e, _ = mt.cible_poche(ent.sigma[a][k], ent.funding_annuel[a][k], p)
            x += p.poids[a] * e * ent.rendements[a][k + 1]
        effet[a] = {"jours": int(m.sum()), "effet": float(x)}
    tous = np.zeros(n, dtype=bool)
    for m in conflit.values():
        tous |= m
    inverse = {}
    tous_inv = np.zeros(n, dtype=bool)
    for a in au_dessus:
        m = ~b & ~au_dessus[a][:n]
        tous_inv |= m
        i = list(p.poids).index(a)
        inverse[a] = {"jours": int(m.sum()),
                      "rendement_poche": float((sim["y"][:, i] * ent.rendements[a][1:])[m].sum())}
    return {"jours": int(tous.sum()), "par_poche": effet,
            "effet_total": float(sum(x["effet"] for x in effet.values())),
            "inverse": {"jours": int(tous_inv.sum()), "par_poche": inverse,
                        "total": float(sum(x["rendement_poche"] for x in inverse.values()))}}


def vol_realisee(ent: mt.Entrees, sim: dict, cible: float) -> dict:
    """Application 32 : ecart-type sqrt(365) de Ei x r_i les jours ou la poche est investie."""
    sortie = {}
    for i, a in enumerate(sim["poches"]):
        m = sim["y"][:, i] > 1e-12
        x = sim["e"][m, i] * ent.rendements[a][1:][m]
        sortie[a] = {"jours": int(m.sum()), "cible": cible,
                     "vol": float(np.std(x, ddof=1) * math.sqrt(R.JOURS_AN)) if m.sum() > 1
                     else None}
    return sortie


def sortie_lente(jours: pd.DatetimeIndex, ent: mt.Entrees, sim: dict) -> dict:
    """Application 35 : chaque rampe vers le baissier contre une sortie immediate.

    cout = -somme (x en rampe - x cible) x r : positif = la rampe a coute par rapport a une
    sortie immediate."""
    detail = []
    n = len(sim["r"])
    actifs = [a for _, a in sim["lignes"]]
    rend = np.column_stack([ent.rendements[a][1:] for a in actifs])
    for k in bascules(sim["baissier"]):
        if not sim["baissier"][k]:
            continue
        fin = min(k + R.RAMPE, n)
        ecart = (sim["y"][k:fin] - sim["cible"][k:fin]) * rend[k:fin]
        detail.append({"bascule": _j(jours, k), "cout": float(-ecart.sum()),
                       "btc_rampe": float(np.prod(1 + ent.rendements["BTC"][k + 1:fin + 1]) - 1)})
    return {"n": len(detail), "cout_total": float(sum(d["cout"] for d in detail)),
            "pire": max(detail, key=lambda d: d["cout"]) if detail else None,
            "detail": detail}
