"""T1J : la regle de choix, mecanique, sans reinterpretation.

1. A domine B si mediane f_entree(A) <= B et fausses alertes / an (A) <= B, dont une strictement.
3. Etape A : un candidat est retenu s'il n'est domine par SMA200 ni sur le temoin actions ni sur
   l'or, et s'il a une f_entree plus faible que SMA200 sur strictement plus de la moitie des
   episodes de chacun des deux (temoin : episodes SPX et NDX ensemble).
4. Etape B : TOUS les retenus de A passent ; domine par SMA200 sur le BTC = elimine (D).
2. Gagnant principal parmi les retenus apres B : domines elimines (sur les moyennes temoin / or),
   puis plus petite moyenne des medianes f_entree temoin et or ; egalite : meilleur pire cas
   moyen (D). Aucun retenu : « SMA200 retenue comme brique regime ».
5. Solide : meme gagnant ET meme liste de retenus sous les 3 variantes du juge.
"""

from __future__ import annotations

from beta.temps1_justesse import regles as R

SCALAIRES = ("f_entree_mediane", "f_entree_pire", "rates_entree", "n_bears", "f_sortie_mediane",
             "f_sortie_pire", "rates_sortie", "n_bulls", "fausses_alertes_an", "bascules_an",
             "r_bear", "r_bull", "justesse", "taux_neutres_justes", "taux_neutres_hasard")
SMA200_RETENUE = "SMA200 retenue comme brique regime"


def _moyenne(a, b):
    return None if a is None or b is None else (a + b) / 2


def temoin(spx: dict, ndx: dict) -> dict:
    """Le temoin actions : moyenne des deux valeurs ; episodes SPX et NDX mis ensemble (4)."""
    t = {k: _moyenne(spx.get(k), ndx.get(k)) for k in SCALAIRES}
    t["entrees"] = ([{**e, "actif": "SPX"} for e in spx["entrees"]]
                    + [{**e, "actif": "NDX"} for e in ndx["entrees"]])
    t["temoin"] = True
    return t


def domine(a: dict, b: dict) -> bool:
    ma, mb = a["f_entree_mediane"], b["f_entree_mediane"]
    fa, fb = a["fausses_alertes_an"], b["fausses_alertes_an"]
    return ma <= mb and fa <= fb and (ma < mb or fa < fb)


def relation(x: dict, ref: dict) -> str:
    if domine(x, ref):
        return "domine SMA200"
    if domine(ref, x):
        return "domine par SMA200"
    return "aucune domination"


def _cle(e: dict) -> tuple:
    return (e.get("actif"), e["pic"], e["creux"])


def majorite(candidat: dict, reference: dict) -> dict:
    """Episodes ou f_entree(candidat) < f_entree(reference), strictement (egalite : non)."""
    ref = {_cle(e): e["f_entree"] for e in reference["entrees"]}
    plus_faible = sum(1 for e in candidat["entrees"] if e["f_entree"] < ref[_cle(e)])
    n = len(candidat["entrees"])
    return {"plus_faible": plus_faible, "episodes": n, "majorite": plus_faible > n / 2}


def etape_a(tables: dict) -> dict:
    """tables[detecteur]['TEMOIN' | 'OR'] -> pour chaque candidat, la regle 3 detaillee."""
    ref = tables[R.REFERENCE]
    sortie = {}
    for x in R.CANDIDATS:
        lignes = {}
        for a in ("TEMOIN", "OR"):
            lignes[a] = {"domine_par_sma200": domine(ref[a], tables[x][a]),
                         **majorite(tables[x][a], ref[a])}
        retenu = all(not v["domine_par_sma200"] and v["majorite"] for v in lignes.values())
        sortie[x] = {**lignes, "retenu": retenu}
    return sortie


def etape_b(tables: dict, retenus_a: list[str]) -> dict:
    ref = tables[R.REFERENCE]["BTC"]
    return {x: {"domine_par_sma200": domine(ref, tables[x]["BTC"]),
                "elimine": domine(ref, tables[x]["BTC"])} for x in retenus_a}


def gagnant(tables: dict, retenus: list[str]) -> dict:
    """D : moyennes temoin / or, domines elimines, plus petite mediane, puis meilleur pire cas."""
    if not retenus:
        return {"gagnant": None, "ex_aequo": [], "moyennes": {}}
    moy = {x: {"f_entree_mediane": _moyenne(tables[x]["TEMOIN"]["f_entree_mediane"],
                                            tables[x]["OR"]["f_entree_mediane"]),
               "fausses_alertes_an": _moyenne(tables[x]["TEMOIN"]["fausses_alertes_an"],
                                              tables[x]["OR"]["fausses_alertes_an"]),
               "f_entree_pire": _moyenne(tables[x]["TEMOIN"]["f_entree_pire"],
                                         tables[x]["OR"]["f_entree_pire"])} for x in retenus}
    restants = [x for x in retenus if not any(domine(moy[y], moy[x]) for y in retenus if y != x)]
    meilleure = min(moy[x]["f_entree_mediane"] for x in restants)
    restants = [x for x in restants if moy[x]["f_entree_mediane"] == meilleure]
    pire = min(moy[x]["f_entree_pire"] for x in restants)
    restants = [x for x in restants if moy[x]["f_entree_pire"] == pire]
    return {"gagnant": restants[0] if len(restants) == 1 else None,
            "ex_aequo": restants if len(restants) > 1 else [], "moyennes": moy}


def verdict(tables: dict) -> dict:
    """Le verdict complet : etape A, etape B, gagnant principal ou SMA200 retenue."""
    a = etape_a(tables)
    retenus_a = [x for x in R.CANDIDATS if a[x]["retenu"]]
    b = etape_b(tables, retenus_a)
    retenus_b = [x for x in retenus_a if not b[x]["elimine"]]
    g = gagnant(tables, retenus_b)
    if not retenus_b:
        statut = SMA200_RETENUE
    elif g["gagnant"]:
        statut = f"candidat retenu : {g['gagnant']}"
    else:
        statut = "candidats retenus ex aequo : " + ", ".join(g["ex_aequo"])
    return {"etape_a": a, "retenus_a": retenus_a, "etape_b": b, "retenus": retenus_b,
            "gagnant": g, "statut": statut}


def cle_solidite(v: dict) -> tuple:
    """Ce qui doit rester identique sous les variantes du juge : gagnant ET retenus."""
    return (v["statut"], tuple(v["retenus"]))
