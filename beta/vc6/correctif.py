"""VC6 V1, Temps 2 : correctif du 02/11/2026 (Jonas) des deux mesures de rapport fausses.

Mesures seulement : aucun resultat d'essai, aucune regle, aucun seuil ne change. Le rapport corrige
(VC6_V1/rapport_temps2_corrige.md) est ecrit a cote de l'original, qui n'est pas touche.

1. Section 6, aller-retours (application 28). Les fenetres de deux aller-retours qui se suivent se
   chevauchaient : leurs jours, leurs frais et leurs ecarts au temoin etaient comptes plusieurs
   fois. Les fenetres qui se chevauchent sont fusionnees, chaque jour compte une seule fois.
   Controle automatique pour chaque essai : frais des aller-retours <= frais totaux, sinon arret.
2. Section 8, grands bears (application 27). La bascule en baissier n'est cherchee qu'entre le plus
   haut et le creux de l'episode, bornes comprises ; sinon, « rate ».

Meme alignement que `beta.vc6.analyse` : `sim[...][k]` est la position decidee a la cloture de D_k ;
une courbe a N + 1 points, v[k] = valeur a la cloture de D_k.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from beta.invest import metriques
from beta.vc6 import analyse as an
from beta.vc6 import regles as R

TOLERANCE_FRAIS = 1e-12      # arrondi flottant de deux sommes faites dans un ordre different


class CorrectifError(RuntimeError):
    """Controle du correctif rate, ou cas que le correctif ne prevoit pas : arret."""


def _j(jours: pd.DatetimeIndex, k: int | None) -> str | None:
    return None if k is None else f"{jours[k]:%Y-%m-%d}"


def paires_aller_retour(baissier: np.ndarray, n: int) -> list[tuple[int, int]]:
    """Bascule k1 puis bascule inverse k2 moins de 30 jours plus tard (definition de la V1)."""
    bs = an.bascules(np.asarray(baissier)[:n])
    return [(k1, k2) for k1, k2 in zip(bs[:-1], bs[1:], strict=True) if k2 - k1 < R.ALLER_RETOUR_J]


def fenetres_sans_chevauchement(paires: list[tuple[int, int]], n: int) -> list[dict]:
    """Fenetre d'un aller-retour : [k1 ; fin de la rampe qui suit k2[ = [k1 ; min(k2 + 5, n)[.
    Deux fenetres qui se chevauchent sont fusionnees ; le resultat est trie et disjoint."""
    fen: list[dict] = []
    for k1, k2 in sorted(paires):
        debut, fin = k1, min(k2 + R.RAMPE, n)
        if fen and debut < fen[-1]["fin"]:
            fen[-1]["fin"] = max(fen[-1]["fin"], fin)
            fen[-1]["paires"].append((k1, k2))
        else:
            fen.append({"debut": debut, "fin": fin, "paires": [(k1, k2)]})
    for a, b in zip(fen[:-1], fen[1:], strict=True):
        if b["debut"] < a["fin"]:
            raise CorrectifError("fenetres d'aller-retours encore chevauchantes")
    return fen


def aller_retours(jours: pd.DatetimeIndex, baissier: np.ndarray, sim: dict,
                  r_temoin: np.ndarray) -> dict:
    """Application 28 corrigee : chaque jour d'une fenetre compte une seule fois."""
    n = len(sim["r"])
    paires = paires_aller_retour(baissier, n)
    fen = fenetres_sans_chevauchement(paires, n)
    masque = np.zeros(n, dtype=bool)
    detail = []
    for f in fen:
        a, b = f["debut"], f["fin"]
        masque[a:b] = True
        rv = float(np.prod(1 + sim["r"][a:b]) - 1)
        rt = float(np.prod(1 + r_temoin[a:b]) - 1)
        detail.append({"debut": _j(jours, a), "fin": _j(jours, b - 1), "jours": b - a,
                       "aller_retours": len(f["paires"]),
                       "frais": float(sim["frais"][a:b].sum()), "rendement": rv,
                       "rendement_temoin": rt, "ecart_temoin": rv - rt})
    jours_comptes = int(sum(d["jours"] for d in detail))
    if jours_comptes != int(masque.sum()):
        raise CorrectifError("un jour est compte deux fois dans les fenetres d'aller-retours")
    frais_ar = float(sim["frais"][masque].sum())
    frais_totaux = float(sim["frais"].sum())
    controle = bool(frais_ar <= frais_totaux + TOLERANCE_FRAIS)
    if not controle:
        raise CorrectifError(f"controle rate : frais des aller-retours {frais_ar} > frais "
                             f"totaux {frais_totaux}")
    return {"n": len(paires), "n_fenetres": len(fen), "jours": jours_comptes,
            "frais_total": frais_ar, "frais_totaux": frais_totaux, "controle_frais": controle,
            "ecart_temoin_total": float(sum(d["ecart_temoin"] for d in detail)),
            "paires": [{"bascule": _j(jours, k1), "retour": _j(jours, k2), "duree_j": k2 - k1,
                        "vers": "baissier" if baissier[k1] else "haussier"}
                       for k1, k2 in paires],
            "fenetres": detail}


def grands_bears(jours: pd.DatetimeIndex, close_btc: np.ndarray, baissier: np.ndarray,
                 courbes: dict[str, np.ndarray]) -> list[dict]:
    """Application 27 corrigee : bascule cherchee dans [plus haut ; creux], sinon « rate »."""
    v = np.asarray(close_btc, dtype=float) / close_btc[0]
    b = np.asarray(baissier, dtype=bool)
    sortie = []
    for ep in metriques.episodes(v, R.SEUIL_GRAND_BEAR):
        pic, creux = ep["pic"], ep["creux"]
        if b[pic]:
            raise CorrectifError(f"mode deja baissier au plus haut du {_j(jours, pic)} : cas "
                                 "non prevu par le correctif")
        suite = [k for k in range(max(pic, 1), creux + 1) if b[k] and not b[k - 1]]
        bascule = suite[0] if suite else None
        d = {"pic": _j(jours, pic), "creux": _j(jours, creux), "fin": _j(jours, ep["fin"]),
             "baisse_btc": ep["perte"], "statut": "bascule" if suite else "rate",
             "bascule": _j(jours, bascule),
             "delai_j": None if bascule is None else bascule - pic,
             "baisse_btc_avant_bascule": None if bascule is None
             else float(v[bascule] / v[pic] - 1.0), "perte_variantes": {}}
        if bascule is not None:
            for cle, c in courbes.items():
                d["perte_variantes"][cle] = float(c[bascule] / c[pic] - 1.0)
        sortie.append(d)
    return sortie
