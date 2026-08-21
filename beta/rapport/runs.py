"""Ce que le dashboard doit savoir d'un run : la fiche complete d'une candidate.

Le serveur ne calcule rien de statistique — tout vient de `data/runs/<id>/`, ecrit par le
pipeline. Ce module ne fait que remettre en forme, agreger pour l'affichage, et surtout
**alleger** : la courbe d'equity d'un run a 790 trades et le cone Monte-Carlo a 10 000
tirages n'ont pas a traverser le reseau en entier pour etre lus a l'ecran.

Une regle tenue partout ici : ce qui n'a pas ete mesure s'affiche comme non mesure. Aucune
valeur par defaut, aucun zero de remplissage. Un tableau de bord qui comble ses trous est
un tableau de bord qui ment, et c'est precisement la panne que BETA existe pour eviter.
"""

from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd

from beta.moteur.pipeline import RESULTATS
from beta.rapport import identite
from beta.stats import descriptif

log = logging.getLogger("beta.rapport.runs")

MAX_POINTS_COURBE = 600           # au-dela, l'ecran n'affiche plus rien de plus


def _lire_json(chemin) -> dict:
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.debug("%s illisible (%s)", chemin, exc)
        return {}


def _lire_parquet(chemin) -> pd.DataFrame:
    try:
        return pd.read_parquet(chemin)
    except (OSError, ValueError, ImportError) as exc:
        log.debug("%s illisible (%s)", chemin, exc)
        return pd.DataFrame()


def liste() -> list[dict]:
    """Les runs enregistres, du plus recent au plus ancien."""
    if not RESULTATS.exists():
        return []
    runs = []
    for dossier in RESULTATS.iterdir():
        verdict = _lire_json(dossier / "verdict.json")
        if not verdict:
            continue
        runs.append({cle: verdict.get(cle) for cle in
                     ("run_id", "experience", "candidate", "issue", "split", "timeframe",
                      "paires", "lance_le", "n_essais_cumules", "portes_echouees",
                      "portes_non_executees")}
                    | {"r_moyen": verdict.get("metriques", {}).get("r_moyen"),
                       "n": verdict.get("metriques", {}).get("n"),
                       "identite": identite.resoudre(verdict)})
    return sorted(runs, key=lambda r: r.get("lance_le") or "", reverse=True)


def _echantillonner(valeurs: list, maximum: int = MAX_POINTS_COURBE) -> list:
    if len(valeurs) <= maximum:
        return valeurs
    pas = len(valeurs) / maximum
    return [valeurs[min(int(i * pas), len(valeurs) - 1)] for i in range(maximum)]


def _courbe(equity: pd.DataFrame) -> dict:
    if equity.empty:
        return {"ts": [], "equity": [], "drawdown_pct": []}
    ts = pd.to_datetime(equity["ts"], utc=True)
    return {"ts": _echantillonner([t.isoformat() for t in ts]),
            "equity": _echantillonner([float(v) for v in equity["equity"]]),
            "drawdown_pct": _echantillonner([float(v) for v in equity["drawdown_pct"]])}


def _par_annee(trades: pd.DataFrame) -> list[dict]:
    """R total et nombre de trades par annee. La ventilation qui tue le plus de candidates.

    Un edge porte par une seule annee n'est pas un edge : c'est un regime. Il ne se voit ni
    dans le R moyen, ni dans la p-value, ni dans le Sharpe — seulement ici.
    """
    if trades.empty or "ts_sortie" not in trades.columns:
        return []
    annees = pd.to_datetime(trades["ts_sortie"], utc=True).dt.year
    lignes = []
    for annee, groupe in trades.groupby(annees):
        r = groupe["r"].dropna()
        lignes.append({"annee": int(annee), "n": len(groupe),
                       "r_total": float(r.sum()) if len(r) else None,
                       "r_moyen": float(r.mean()) if len(r) else None,
                       "win_rate": float((r > 0).mean()) if len(r) else None})
    return lignes


def _ventilation(trades: pd.DataFrame, cle: str) -> list[dict]:
    if trades.empty or cle not in trades.columns:
        return []
    table = descriptif.par(trades, cle)
    return json.loads(table.to_json(orient="records"))


def _histogramme(valeurs, n_classes: int = 40) -> dict:
    valeurs = np.asarray([v for v in valeurs if v is not None and np.isfinite(v)],
                         dtype=float)
    if len(valeurs) < 2:
        return {"bords": [], "effectifs": []}
    effectifs, bords = np.histogram(valeurs, bins=n_classes)
    return {"bords": [float(b) for b in bords],
            "effectifs": [int(e) for e in effectifs]}


def _texte_hypothese(id_experience: str) -> dict:
    """Le preenregistrement en clair : ce qu'on a ecrit AVANT de mesurer.

    C'est la moitie de l'explication d'une candidate, et c'est celle qui manque partout
    ailleurs. Le code dit ce que la regle CALCULE ; le preenregistrement dit ce qu'on
    attendait d'elle et a quelle condition on avait accepte de se declarer battu.
    """
    try:
        from beta.protocole import experiences
        preenr = experiences.etat().get(id_experience) or {}
    except Exception as exc:                          # noqa: BLE001 - decor, jamais fatal
        log.debug("preenregistrement '%s' illisible (%s)", id_experience, exc)
        return {}
    return {cle: preenr.get(cle) for cle in
            ("hypothese", "metrique_primaire", "regle_de_decision", "statut",
             "deja_connu", "mde_attendu", "famille_taille")}


def _code_source(module: str) -> str:
    """Le fichier de la candidate, s'il existe encore. Chaine vide sinon, jamais d'erreur.

    Un run garde son verdict quand le fichier disparait — c'est voulu — donc l'absence de
    code n'est pas une panne, c'est une information que l'interface affiche telle quelle.
    """
    try:
        from beta.rapport import atelier
        return atelier.code_de(module).get("code", "")
    except Exception as exc:                          # noqa: BLE001 - decor, jamais fatal
        log.debug("code de '%s' indisponible (%s)", module, exc)
        return ""


def explication(verdict: dict) -> dict:
    """Ce qu'il faut pour repondre a « cette strategie, elle fait quoi, concretement ? ».

    Trois etages, et aucun ne suffit seul : ce que la regle DECIDE (la candidate), ce
    qu'on en attendait (le preenregistrement), et comment le trade est SORTI (la triple
    barriere du moteur, qui n'appartient pas a la candidate et qui explique pourtant une
    grande part de son R). Les sorties ne se lisent nulle part dans le code d'une
    candidate : elles sont imposees par le Run, et les omettre ici laisserait croire que la
    regle d'entree explique tout le resultat.
    """
    identifiants = identite.resoudre(verdict)
    return {
        "identite": identifiants,
        "parametres": verdict.get("parametres") or {},
        "preenregistrement": _texte_hypothese(verdict.get("experience") or ""),
        "execution": {cle: verdict.get(cle) for cle in
                      ("timeframe", "paires", "split", "stop_atr", "take_profit_r",
                       "horizon_bougies", "cout_aller_retour_pct", "empreinte",
                       "debut", "fin")},
        "code": _code_source(identifiants.get("module") or ""),
    }


def fiche(run_id: str) -> dict:
    """Tout ce qu'il faut pour dessiner la fiche d'une candidate. Rien de plus.

    Les distributions Monte-Carlo et synthetiques sont rendues en HISTOGRAMMES, pas en
    listes de tirages : 10 000 nombres ne se lisent pas, et leur forme, si.
    """
    dossier = RESULTATS / run_id
    verdict = _lire_json(dossier / "verdict.json")
    if not verdict:
        raise FileNotFoundError(f"run inconnu : {run_id}")
    detail = _lire_json(dossier / "batterie.json")
    trades = _lire_parquet(dossier / "trades.parquet")
    equity = _lire_parquet(dossier / "equity.parquet")

    mc = detail.get("S4_monte_carlo", {})
    permutation = mc.get("permutation", {})
    remise = mc.get("remise", {})
    hold = detail.get("S8_buy_and_hold", {})
    wf = detail.get("S6_walk_forward", {})

    return {
        "verdict": verdict,
        "explication": explication(verdict),
        "courbe": _courbe(equity),
        "hold": {"courbe": {
            "ts": _echantillonner(hold.get("hold", {}).get("courbe", {}).get("ts", [])),
            "valeur": _echantillonner(hold.get("hold", {}).get("courbe", {})
                                      .get("valeur", []))},
            "metriques": {c: v for c, v in hold.get("hold", {}).items() if c != "courbe"},
            "candidate": {c: v for c, v in hold.get("candidate", {}).items()
                          if c != "courbe"},
            "ecarts": {c: hold.get(c) for c in ("ecart_rendement_pct", "ecart_sharpe",
                                                "ecart_drawdown_pct", "passe")}},
        "par_annee": _par_annee(trades),
        "par_sens": _ventilation(trades, "sens"),
        "par_paire": _ventilation(trades, "paire"),
        "par_raison": _ventilation(trades, "raison_sortie"),
        "distribution_r": _histogramme(trades["r"].tolist() if "r" in trades.columns
                                       else []),
        "monte_carlo": {
            "p_perte": remise.get("p_perte"),
            "p_drawdown": permutation.get("p_drawdown_pire_que_seuil"),
            "seuil_dd_pct": permutation.get("seuil_dd_pct"),
            "centile_drawdown_reel": permutation.get("centile_drawdown_reel"),
            "drawdown_max_reel_pct": permutation.get("drawdown_max_reel_pct"),
            "equity_finale_reelle": remise.get("equity_finale_reelle"),
            "equity_finale": remise.get("equity_finale", {}),
            "drawdown_max": permutation.get("drawdown_max", {}),
            "cone": {cle: _echantillonner(valeurs)
                     for cle, valeurs in (permutation.get("cone") or {}).items()},
        },
        "walk_forward": {"plis": wf.get("ancre", {}).get("plis", []),
                         "efficacite": wf.get("ancre", {}).get("efficacite"),
                         "cpcv": {c: wf.get("cpcv", {}).get(c) for c in
                                  ("n_combinaisons", "oos_median", "oos_p5", "oos_p95",
                                   "part_chemins_perdants")},
                         "cpcv_histogramme": _histogramme(
                             wf.get("cpcv", {}).get("scores", []), 25)},
        "synthetique": detail.get("S5_synthetique", {}),
        "bootstrap": detail.get("S3_bootstrap", []),
        "sharpe_degonfle": detail.get("S2_sharpe_degonfle", {}),
        "diversification": detail.get("S9_diversification", {}),
        "reality_check": detail.get("S7_reality_check", {}),
    }
