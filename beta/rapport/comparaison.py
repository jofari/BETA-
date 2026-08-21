"""La vue comparative : plusieurs strategies mises en regard, pas une fiche a la fois.

Elle ne se construit PAS a partir d'un criblage : elle relit `data/runs/`, quels que soient
le moment et la commande qui les ont produits. C'est le point de conception — deux
strategies ecrites a trois semaines d'ecart doivent se comparer sans qu'on ait a les
remesurer ensemble.

Une regle qui evite l'erreur la plus facile a commettre ici : **un seul run par candidate**,
le plus recent de son split. Deux runs de la meme candidate ne sont pas deux strategies ;
les laisser tous les deux gonflerait l'univers du reality check avec une copie de
lui-meme — donc rendrait S7 plus severe pour de mauvaises raisons, et la matrice de
correlation afficherait fierement 1,00 entre une candidate et elle-meme.

Ce qui est affiche vient de `beta.stats.comparaison`. Ce module ne calcule rien : il lit,
il deduplique, il allege pour l'ecran.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from beta.moteur.pipeline import RESULTATS
from beta.rapport import identite
from beta.rapport.runs import MAX_POINTS_COURBE, _lire_json, _lire_parquet
from beta.stats import comparaison as stats_comparaison

log = logging.getLogger("beta.rapport.comparaison")


class _VerdictLu:
    """Un verdict relu du disque, presente comme celui du moteur.

    `stats.comparaison.classer` attend des objets `Verdict`. Reconstruire de vrais Verdict
    demanderait de reconstruire les Run, donc les Candidate, donc d'importer le code des
    candidates — et un fichier supprime depuis rendrait la page blanche. On presente donc
    la meme surface (`metriques`, `issue`, `portes_echouees`, `run.id_experience`) a partir
    du JSON, et rien d'autre n'est necessaire.
    """

    def __init__(self, verdict: dict) -> None:
        self.metriques = verdict.get("metriques") or {}
        self.issue = verdict.get("issue", "")
        self.portes_echouees = verdict.get("portes_echouees") or []
        self.portes_non_executees = verdict.get("portes_non_executees") or []
        self.run = type("Run", (), {"id_experience": verdict.get("experience", "")})()


def _runs_a_comparer(split: str = "train") -> dict[str, dict]:
    """Le run le plus recent de chaque candidate, pour le split demande."""
    if not RESULTATS.exists():
        return {}
    retenus: dict[str, dict] = {}
    for dossier in RESULTATS.iterdir():
        verdict = _lire_json(dossier / "verdict.json")
        if not verdict or verdict.get("split") != split:
            continue
        nom = verdict.get("candidate") or dossier.name
        ancien = retenus.get(nom)
        if ancien is None or (verdict.get("lance_le") or "") > (ancien.get("lance_le") or ""):
            retenus[nom] = {**verdict, "_dossier": dossier}
    return retenus


def _alleger(equity: pd.DataFrame) -> list[dict]:
    """La courbe reduite a ce qu'un ecran peut montrer, base 100 pour etre superposable."""
    if equity.empty or "equity" not in equity.columns:
        return []
    base = float(equity["equity"].iloc[0]) or 1.0
    pas = max(1, len(equity) // MAX_POINTS_COURBE)
    reduit = equity.iloc[::pas]
    return [{"ts": str(ligne.ts), "valeur": round(100.0 * float(ligne.equity) / base, 4)}
            for ligne in reduit.itertuples()]


def charger_lot(split: str = "train") -> dict:
    """Relit du disque tout ce qu'une comparaison demande. Le SEUL chemin de lecture.

    Rend `{verdicts, equities, univers, arit, n}`. CLI et dashboard passent tous les deux
    par ici : deux chemins de lecture, ce serait deux endroits ou oublier de ne garder
    qu'un run par candidate — et l'oubli ne se verrait que sous la forme d'une matrice de
    correlation a 1,00 avec soi-meme, qu'on mettrait longtemps a comprendre.
    """
    runs = _runs_a_comparer(split)
    verdicts, equities, univers, titres = {}, {}, {}, {}
    for nom, verdict in runs.items():
        titres[nom] = identite.resoudre(verdict)
        dossier = verdict["_dossier"]
        verdicts[nom] = _VerdictLu(verdict)
        equity = _lire_parquet(dossier / "equity.parquet")
        if not equity.empty:
            equities[nom] = equity
        trades = _lire_parquet(dossier / "trades.parquet")
        if not trades.empty and "r" in trades.columns:
            serie = trades["r"].dropna().to_numpy()
            if len(serie) >= 3:
                univers[nom] = serie
    return {"verdicts": verdicts, "equities": equities, "univers": univers,
            "titres": titres,
            "arit": stats_comparaison.equity_arit(train_seulement=(split == "train")),
            "n": len(runs)}


def classement_du_lot(split: str = "train") -> tuple[dict, dict]:
    """(lot, classement) — le couple dont CLI et dashboard ont tous les deux besoin."""
    lot = charger_lot(split)
    return lot, stats_comparaison.classer(
        lot["verdicts"], lot["equities"], univers_r=lot["univers"],
        equity_arit=lot["arit"])


def vue(split: str = "train") -> dict:
    """Tout ce que l'onglet Comparaison affiche. Ne leve pas : l'absence est une donnee."""
    lot, classement = classement_du_lot(split)
    if not lot["n"]:
        return {"n": 0, "tableau": [], "courbes": {}, "matrice": {"noms": [], "valeurs": []},
                "reality_check": {}, "redondances": [], "arit_present": False,
                "titres": {}, "split": split,
                "reserves": ["aucun run enregistre : lancer `python beta.py cribler`"]}
    equities, arit = lot["equities"], lot["arit"]

    courbes = {nom: _alleger(eq) for nom, eq in equities.items()}
    if arit is not None and not arit.empty:
        courbes["AritV1 (reference)"] = _alleger(arit)

    matrice = classement["matrice_correlation"]
    return {
        "n": lot["n"],
        "split": split,
        "titres": lot["titres"],
        "tableau": _table(classement["tableau"]),
        "reality_check": _propre_dict(classement["reality_check"]),
        "matrice": {"noms": list(matrice.columns),
                    "valeurs": [[_propre(v) for v in ligne]
                                for ligne in matrice.to_numpy()]} if not matrice.empty
                   else {"noms": [], "valeurs": []},
        "redondances": classement["redondances"],
        "courbes": courbes,
        "arit_present": arit is not None and not arit.empty,
        "reserves": classement["reserves"],
    }


def _propre(valeur):
    if isinstance(valeur, (float, np.floating)):
        valeur = float(valeur)
        return None if not np.isfinite(valeur) else round(valeur, 6)
    if isinstance(valeur, (int, np.integer)):
        return int(valeur)
    return None if valeur is None else str(valeur)


def _propre_dict(charge: dict) -> dict:
    return {cle: (_propre_dict(v) if isinstance(v, dict) else _propre(v))
            for cle, v in charge.items()}


def _table(tableau: pd.DataFrame) -> list[dict]:
    if tableau.empty:
        return []
    return [{cle: _propre(valeur) for cle, valeur in ligne.items()}
            for ligne in tableau.to_dict(orient="records")]
