"""Onglet Forward : les suivis au cours de cloture et le paper trading, relus tels quels.

Le serveur ne recalcule rien a partir du lake : il relit les journaux SUIVI_<voie>.jsonl et
PAPER_<voie>.jsonl, qui font foi, et n'en tire que des cumuls d'affichage — base 100, maxDD,
vol, moyennes de slippage ponderees par le notional. Une voie sans journal s'affiche vide,
sans erreur : sur le PC de Jonas, ou les timers ne tournent pas, c'est l'etat normal.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path

from beta import config
from beta.protocole import experiences
from beta.strategies import voie_c_voltarget as vc

# Ordre d'affichage : la reference, l'experience en dry-run, puis l'informative.
VOIES = (
    ("VOIE_C", "Voie C figée", "perpétuels"),
    ("VC3", "VC3 — poche maximum", "spot"),
    ("VC2", "VC2 — poche achetée", "perpétuels"),
)
N_ORDRES = 40                       # derniers ordres paper affiches


def _lire(chemin: Path) -> list[dict]:
    if not chemin.exists():
        return []
    return [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines() if l.strip()]


def bilan(rendements: list[float]) -> dict:
    """Rendement cumule, maxDD, vol annualisee (racine de 252, la convention de la cible)."""
    equite, pic, mdd = 1.0, 1.0, 0.0
    for r in rendements:
        equite *= 1.0 + r
        pic = max(pic, equite)
        mdd = min(mdd, equite / pic - 1.0)
    n = len(rendements)
    vol = None
    if n > 1:
        moyenne = sum(rendements) / n
        vol = math.sqrt(sum((r - moyenne) ** 2 for r in rendements) / (n - 1) * vc.PPA)
    return {"net": equite - 1.0, "mdd": mdd, "vol": vol, "n": n}


def statut(nom: str, registre: dict) -> str:
    if nom == "VOIE_C":
        return "référence — config figée le 03/10"
    issue = registre.get(nom, {}).get("derniere_issue")
    return {"confirmee": "dry-run de 6 mois (confirmée le 07/10)",
            "infirmee": "informative (infirmée le 07/10)"}.get(issue, issue or "—")


def suivi(lignes: list[dict]) -> dict | None:
    """Le suivi au cours de cloture : courbe depuis le debut du rattrapage, et l'etat du jour."""
    if not lignes:
        return None
    live = [l for l in lignes if l.get("type") == "live"]
    derniere = lignes[-1]
    return {
        "points": [{"date": l["date"], "equite": l["equite"], "btc": l["equite_btc"],
                    "live": l.get("type") == "live"} for l in lignes],
        "debut": lignes[0]["date"], "fin": derniere["date"],
        "debut_live": live[0]["date"] if live else None,
        "tout": bilan([l["r_net"] for l in lignes]),
        "live": bilan([l["r_net"] for l in live]) if live else None,
        "btc": derniere["equite_btc"] - 1.0,
        "derniere": {k: derniere.get(k) for k in ("date", "etat", "votes", "somme",
                                                   "positions", "brut", "levier")},
        "consigne": derniere.get("consigne_lendemain"),
    }


def paper(lignes: list[dict], modele: list[dict]) -> dict | None:
    """Le paper depuis son premier jour, et le suivi sur les memes journees de detention.

    La journee d du suivi est la detention entre les executions de d et de d+1 : le modele
    vaut donc, a l'execution du jour D, le produit de ses rendements des jours [debut, D).
    """
    if not lignes:
        return None
    capital = lignes[0]["capital_initial"]
    r_modele = {l["date"]: l["r_net"] for l in modele}
    points, cumul_modele, precedente = [], 1.0, None
    for l in lignes:
        if precedente is not None:
            for jour, r in sorted(r_modele.items()):
                if precedente <= jour < l["date"]:
                    cumul_modele *= 1.0 + r
        points.append({"date": l["date"], "paper": l["equite_avant"] / capital,
                       "modele": cumul_modele})
        precedente = l["date"]
    ordres = [{"date": l["date"], **o} for l in lignes for o in l["ordres"]]
    notional = sum(o["notional"] for o in ordres)

    def moyenne(cle: str) -> float | None:
        return sum(o[cle] * o["notional"] for o in ordres) / notional if notional else None

    derniere = lignes[-1]
    return {
        "capital": capital, "debut": lignes[0]["date"], "fin": derniere["date"],
        "n_jours": len(lignes), "points": points,
        "equite": derniere["equite"], "rendement": derniere["equite_avant"] / capital - 1.0,
        "modele": points[-1]["modele"] - 1.0,
        "frais": sum(l["frais"] for l in lignes),
        "funding": sum(sum(l["funding"].values()) for l in lignes),
        "n_ordres": len(ordres), "notional": notional,
        "carnet_pb": moyenne("cout_carnet_pb"), "ouverture_pb": moyenne("ecart_ouverture_pb"),
        "modele_pb": moyenne("slippage_modele_pb"),
        "poids": derniere["poids"], "cash": derniere["cash"],
        "ignores": sum(len(l["ignores"]) for l in lignes),
        "ordres": ordres[-N_ORDRES:][::-1],
    }


def vue(racine: Path | None = None) -> dict:
    racine = racine or config.RACINE
    registre = experiences.etat()
    voies = []
    for nom, titre, instrument in VOIES:
        lignes_suivi = _lire(racine / f"SUIVI_{nom}.jsonl")
        voies.append({
            "nom": nom, "titre": titre, "instrument": instrument,
            "statut": statut(nom, registre),
            "suivi": suivi(lignes_suivi),
            "paper": paper(_lire(racine / f"PAPER_{nom}.jsonl"), lignes_suivi),
        })
    return {"voies": voies, "paires": list(vc.PAIRES),
            "genere_le": datetime.now(UTC).isoformat(timespec="seconds")}
