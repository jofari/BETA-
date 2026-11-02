"""VC6 V2, paper de plomberie : le rejeu hebdomadaire (Jonas, 02/11/2026).

Chaque semaine (timer beta-vc6-rejeu), le backtest est rejoue sur le lake du moment, avec le code du
paper (`vivant.charger`, `vivant.decider`), sur les jours d'execution des 7 derniers jours. Pour
chaque jour et chaque actif, l'exposition du paper apres execution (poids tenus) est comparee a
celle du backtest (position nette decidee a la cloture de la veille). Tout ecart de plus de 5 points
est explique, par la premiere cause qui s'applique :
    1. aucun ordre ce jour-la : donnee manquante a la cloture ;
    2. la decision rejouee differe de celle du jour (donnee revisee depuis dans le lake) ;
    3. ordre ignore (sous le minimum de Binance, ou cash insuffisant) ;
    4. derive des prix depuis le dernier ordre de l'actif (choix B de Jonas : n'echanger que quand
       le modele change une exposition) ;
    sinon : non explique, et alerte.
En plus : controle « meme code que le backtest » (sur la periode figee, du 31/05/2021 au
31/10/2026, les positions rejouees sur le lake vivant doivent etre identiques a celles du backtest
sur les copies figees), et, pour information, le rendement du paper contre celui du backtest sur la
semaine. Une ligne par semaine dans PAPER_VC6_REJEU.jsonl, en ajout seul.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np

from beta import config
from beta.vc6_v2 import donnees as dn
from beta.vc6_v2 import moteur as mt
from beta.vc6_v2 import paper as pp
from beta.vc6_v2 import vivant

SEUIL = 0.05
FENETRE_J = 7
JOURNAL_REJEU = "PAPER_VC6_REJEU.jsonl"
TOLERANCE_JOURNAL = 1e-6        # les poids du journal sont arrondis a 6 decimales


def poids_paper(ligne: dict) -> dict[str, float] | None:
    """Poids tenus apres l'execution du jour (lus, ou recalcules pour un jour sans ordre)."""
    if ligne.get("actifs"):
        return {a: ligne["actifs"][a]["poids_paper"] for a in pp.ACTIFS}
    if not ligne.get("prix") or not ligne.get("valeur"):
        return None
    return {a: ligne["quantites"][a] * ligne["prix"][a] / ligne["valeur"] for a in pp.ACTIFS}


def expliquer(ligne: dict, actif: str, rejoue: float) -> str:
    if ligne["statut"] == "donnee_manquante":
        return "aucun ordre ce jour-là : donnée manquante à la clôture"
    if abs(ligne["actifs"][actif]["poids_modele"] - rejoue) > TOLERANCE_JOURNAL:
        return "la décision rejouée diffère de celle du jour (donnée révisée dans le lake ?)"
    ignores = [i for i in ligne.get("ignores", []) if i["actif"] == actif]
    if ignores:
        return f"ordre ignoré : {ignores[0]['raison']}"
    if actif not in ligne.get("a_traiter", []):
        return "dérive des prix depuis le dernier ordre (choix B : échanger seulement quand le " \
               "modèle change une exposition)"
    return "non expliqué"


def comparer(lignes: list[dict], rejoue: dict[str, dict[str, float]]) -> list[dict]:
    """Les ecarts de plus de 5 points entre le paper et le backtest rejoue, expliques."""
    ecarts = []
    for ligne in lignes:
        tenus = poids_paper(ligne)
        modele = rejoue.get(ligne["date"])
        if tenus is None or modele is None:
            continue
        for a in pp.ACTIFS:
            e = tenus[a] - modele[a]
            if abs(e) > SEUIL:
                ecarts.append({"jour": ligne["date"], "actif": a, "paper": round(tenus[a], 6),
                               "backtest": round(modele[a], 6),
                               "ecart_points": round(e * 100, 2),
                               "explication": expliquer(ligne, a, modele[a])})
    return ecarts


def controle_fige(ext: dict) -> dict:
    """Sur la periode figee, les positions rejouees sur le lake vivant = celles du backtest."""
    d = dn.charger_principal()
    ent = dn.entrees_principal(d)
    sim = mt.simuler(ent, mt.parametres_essai(vivant.ESSAI))
    n = ent.n
    y = ext["y"][:n]
    meme = y.shape == sim["y"].shape and bool(np.array_equal(y, sim["y"]))
    ecart = float(np.max(np.abs(y - sim["y"]))) if y.shape == sim["y"].shape else None
    return {"identique": meme, "jours": int(n), "ecart_max": ecart,
            "periode": [f"{ent.jours[1]:%Y-%m-%d}", f"{ent.jours[-1]:%Y-%m-%d}"]}


def rendements(lignes: list[dict], ext: dict, jours) -> dict | None:
    """Pour information : le paper (valeur avant ordres, de 00:00 a 00:00) contre le backtest sur
    les memes jours (rendements des jours du premier au dernier jour d'execution exclu)."""
    utiles = [x for x in lignes if x.get("valeur_avant") is not None]
    if len(utiles) < 2:
        return None
    debut, fin = utiles[0], utiles[-1]
    index = {f"{j:%Y-%m-%d}": k for k, j in enumerate(jours)}
    k0, k1 = index.get(debut["date"]), index.get(fin["date"])
    if k0 is None or k1 is None:
        return None
    r = ext["r"][k0 - 1:k1 - 1]
    return {"du": debut["date"], "au": fin["date"],
            "paper": fin["valeur_avant"] / debut["valeur_avant"] - 1.0,
            "backtest": float(np.prod(1.0 + r) - 1.0)}


def rejouer(aujourdhui: dt.date, chemin: Path, controle: bool = True) -> dict:
    """Le rejeu de la semaine qui finit `aujourdhui` (jours d'execution des 7 derniers jours)."""
    tout = pp.lire_journal(chemin)
    debut = aujourdhui - dt.timedelta(days=FENETRE_J - 1)
    lignes = [x for x in tout if debut.isoformat() <= x["date"] <= aujourdhui.isoformat()]
    attendus = [(debut + dt.timedelta(days=i)).isoformat() for i in range(FENETRE_J)]
    presents = {x["date"] for x in lignes}
    sortie = {"date": aujourdhui.isoformat(), "fenetre": [attendus[0], attendus[-1]],
              "jours": len(lignes), "jours_absents": [j for j in attendus if j not in presents
                                                      and j >= (tout[0]["date"] if tout else j)]}
    if not lignes:
        sortie.update(ecarts=[], non_expliques=0, controle_backtest_fige=None, rendement=None)
        return sortie
    d = None
    for recul in range(1, FENETRE_J + 1):
        try:
            d = vivant.charger(dt.date.fromisoformat(lignes[-1]["date"])
                               - dt.timedelta(days=recul))
            break
        except vivant.DonneeManquante:
            continue
    if d is None:
        raise vivant.DonneeManquante("aucune cloture chargeable sur la semaine")
    dec = vivant.decider(d)
    ext, ent = dec["_ext"], dec["_ent"]
    jours = ent.jours.append(ent.jours[-1:] + vivant.UN)
    rejoue = {}
    for k, j in enumerate(jours):
        execution = f"{j + vivant.UN:%Y-%m-%d}"
        if execution in presents and k < len(ext["y"]):
            rejoue[execution] = vivant.nets(ext["y"][k], ext["lignes"])
    ecarts = comparer(lignes, rejoue)
    sortie.update(ecarts=ecarts,
                  non_expliques=sum(e["explication"] == "non expliqué" for e in ecarts),
                  controle_backtest_fige=controle_fige(ext) if controle else None,
                  rendement=rendements(lignes, ext, jours))
    return sortie


def ecrire(sortie: dict, repertoire: Path | None = None) -> Path:
    chemin = (repertoire or config.RACINE) / JOURNAL_REJEU
    with chemin.open("a", encoding="utf-8") as f:
        f.write(json.dumps(sortie, ensure_ascii=True) + "\n")
    return chemin


def alerte(sortie: dict) -> list[str]:
    """Ce qui doit alerter : un ecart non explique, ou le backtest fige non reproduit."""
    out = []
    if sortie.get("non_expliques"):
        out.append(f"{sortie['non_expliques']} ecart(s) d'exposition de plus de 5 points non "
                   "explique(s)")
    c = sortie.get("controle_backtest_fige")
    if c is not None and not c["identique"]:
        out.append(f"le lake vivant ne redonne plus le backtest fige (ecart max {c['ecart_max']})")
    if sortie.get("jours_absents"):
        out.append(f"jours absents du journal : {', '.join(sortie['jours_absents'])}")
    return out

