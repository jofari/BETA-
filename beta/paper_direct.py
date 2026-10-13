"""Paper en direct : l'equite de chaque compte paper, relevee chaque minute.

Demande de Jonas (2026-10-13) : « un paper en direct, actualise toutes les minutes, un graphe
qui le represente, un seul indicateur paper, pas de maintenant et avant ». Le paper n'execute
qu'a ses passages (01:00 UTC, sessions VC4) ; entre deux passages ses comptes ne bougent pas,
seuls les prix bougent. Ici on valorise chaque minute le compte du DERNIER passage avec la
formule du paper :

    equite = cash - funding regle depuis le passage + somme(q * milieu bid/ask actuel)

Le funding est celui que Binance a REELLEMENT regle depuis le passage (echeances 00/08/16 UTC),
calcule comme `paper.journee` le reglera au passage suivant : la courbe ne saute donc pas au
passage, sauf des frais et du cout au carnet des ordres du jour. Rien n'est ecrit dans les
journaux du paper ; une ligne par minute dans DIRECT_PAPER.jsonl (hors git : regenere par le
timer, les PAPER_*.jsonl restent les journaux qui font foi).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from beta import config
from beta import paper as pp

FICHIER = "DIRECT_PAPER.jsonl"


def _instant(iso: str) -> dt.datetime:
    return dt.datetime.fromisoformat(iso)


def equite(derniere: dict, milieux: dict[str, float],
           echeances: dict[str, list[dict]]) -> float | None:
    """Le compte du dernier passage aux milieux donnes, net du funding regle depuis.

    `echeances` : par paire, les echeances de funding (instant ms, taux, marque) — toutes
    celles depuis un instant anterieur au passage ; seules celles APRES le passage comptent.
    None si un prix manque : on ne devine rien.
    """
    q = {p: x for p, x in derniere["quantites"].items() if x}
    if any(p not in milieux for p in q):
        return None
    cash = float(derniere["cash"])
    if derniere["instrument"] == pp.PERPETUEL:
        passage_ms = int(_instant(derniere["execute_le"]).timestamp() * 1000)
        for p, x in q.items():
            cash -= sum(x * (e["marque"] or milieux[p]) * e["taux"]
                        for e in echeances.get(p, []) if e["instant"] > passage_ms)
    return cash + sum(x * milieux[p] for p, x in q.items())


def milieux(marche) -> dict[str, dict[str, float]]:
    """Milieux bid/ask actuels par instrument et paire (bookTicker, routes publiques)."""
    voulus = {f"{p}USDT": p for p in pp.PAIRES}
    symboles = json.dumps(sorted(voulus), separators=(",", ":"))
    prix = {}
    for instrument, params in ((pp.SPOT, {"symbols": symboles}), (pp.PERPETUEL, {})):
        lignes = marche._get(instrument, "ticker/bookTicker", **params)
        prix[instrument] = {voulus[l["symbol"]]: (float(l["bidPrice"]) + float(l["askPrice"])) / 2
                            for l in lignes if l["symbol"] in voulus}
    return prix


def releve(racine: Path, marche, maintenant: dt.datetime) -> dict:
    """La ligne de la minute : {"t": instant, "e": {voie: equite}}."""
    derniers = {}
    for nom, voie in pp.voies().items():
        lignes = pp.lire_journal(pp.journal_paper(voie, racine))
        if lignes:
            derniers[nom] = lignes[-1]
    prix = milieux(marche)
    # Funding : une lecture par paire depuis le plus ancien passage en perpetuels.
    perps = [d for d in derniers.values() if d["instrument"] == pp.PERPETUEL]
    echeances: dict[str, list[dict]] = {}
    if perps:
        depuis = min(_instant(d["execute_le"]) for d in perps)
        for p in pp.PAIRES:
            if any(d["quantites"].get(p) for d in perps):
                echeances[p] = marche.funding(f"{p}USDT", depuis, maintenant)
    e = {}
    for nom, d in derniers.items():
        x = equite(d, prix.get(d["instrument"], {}), echeances)
        if x is not None:
            e[nom] = round(x, 2)
    return {"t": maintenant.isoformat(timespec="seconds"), "e": e}


def chemin(racine: Path | None = None) -> Path:
    return (racine or config.RACINE) / FICHIER


def ajouter(ligne: dict, racine: Path | None = None) -> None:
    with chemin(racine).open("a", encoding="utf-8") as f:
        f.write(json.dumps(ligne, separators=(",", ":")) + "\n")


def lire(racine: Path | None = None) -> list[dict]:
    """Les releves. Une ligne illisible (lue pendant son ecriture) est sautee, pas fatale."""
    p = chemin(racine)
    if not p.exists():
        return []
    releves = []
    for l in p.read_text(encoding="utf-8").splitlines():
        try:
            releves.append(json.loads(l))
        except ValueError:
            continue
    return releves
