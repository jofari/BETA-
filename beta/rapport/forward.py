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
    ("VC5", "VC5 — cible de vol 35 %", "spot"),
    ("VC4", "VC4 — à chaque session", "spot"),
    ("VC2", "VC2 — poche achetée", "perpétuels"),
)
N_ORDRES = 40                       # derniers ordres paper affiches
TOLERANCE_LEVIER = 1e-6             # arrondis d'execution : 100,0000x % investi n'est pas du levier


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
    entree = registre.get(nom, {})
    issue, date = entree.get("derniere_issue"), entree.get("date") or ""
    le = f" le {date[8:10]}/{date[5:7]}" if len(date) == 10 else ""
    return {"confirmee": f"dry-run de 6 mois (confirmée{le})",
            "infirmee": f"informative (infirmée{le})"}.get(issue, issue or "—")


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


def allocation(ligne: dict) -> dict | None:
    """Le compte paper apres sa derniere execution : ce que vaut chaque ligne, le cash, et s'il
    y a un effet de levier.

    Comptabilite de `beta.paper` : equite = cash + somme(q * milieu), q < 0 = short (perpetuels).
    Effet de levier = on expose plus que l'equite : exposition brute > 100 %, ce qui oblige le
    cash a passer sous zero (emprunt). A ne pas confondre avec le « levier » du moteur, qui n'est
    qu'un multiplicateur de vol-cible applique aux poids (0,74 = 74 % des poids de base).
    """
    if not all(k in ligne for k in ("quantites", "milieux", "equite", "cash")):
        return None
    equite = ligne["equite"]
    actifs = []
    for paire, q in ligne["quantites"].items():
        prix = ligne["milieux"].get(paire)
        valeur = q * prix if prix is not None else 0.0
        actifs.append({"paire": paire, "quantite": q, "prix": prix, "valeur": valeur,
                       "poids": valeur / equite if equite else None})
    brute = sum(abs(a["valeur"]) for a in actifs) / equite if equite else None
    nette = sum(a["valeur"] for a in actifs) / equite if equite else None
    return {
        "date": ligne["date"], "execute_le": ligne.get("execute_le"), "equite": equite,
        "cash": ligne["cash"], "part_cash": ligne["cash"] / equite if equite else None,
        "actifs": actifs, "exposition_brute": brute, "exposition_nette": nette,
        "effet_levier": bool(brute is not None and brute > 1.0 + TOLERANCE_LEVIER),
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
    # Cadence « instant » (VC4) : plusieurs executions par jour ; la courbe et la comparaison
    # au modele quotidien partent de la PREMIERE de chaque jour (la decision de 00:00).
    premieres = list({l["date"]: l for l in reversed(lignes)}.values())[::-1]
    for l in premieres:
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
        # Heure reelle du dernier passage (01:00 UTC, ou les sessions pour VC4) : la date seule
        # ne dit pas si le run du jour a eu lieu.
        "dernier_passage": derniere.get("execute_le"),
        "n_jours": len(premieres), "points": points,
        "equite": derniere["equite"],
        "rendement": premieres[-1]["equite_avant"] / capital - 1.0,
        "modele": points[-1]["modele"] - 1.0,
        "frais": sum(l["frais"] for l in lignes),
        "funding": sum(sum(l["funding"].values()) for l in lignes),
        "n_ordres": len(ordres), "notional": notional,
        "carnet_pb": moyenne("cout_carnet_pb"), "ouverture_pb": moyenne("ecart_ouverture_pb"),
        "modele_pb": moyenne("slippage_modele_pb"),
        "poids": derniere["poids"], "cash": derniere["cash"],
        "allocation": allocation(derniere),
        "ignores": sum(len(l["ignores"]) for l in lignes),
        "ordres": ordres[-N_ORDRES:][::-1],
    }


def vue(racine: Path | None = None) -> dict:
    racine = racine or config.RACINE
    registre = experiences.etat()
    voies = []
    for nom, titre, instrument in VOIES:
        lignes_suivi = _lire(racine / f"SUIVI_{nom}.jsonl")
        s = suivi(lignes_suivi)
        consignes = _lire(racine / f"CONSIGNES_{nom}.jsonl")
        if s is not None and consignes:
            # Cadence « instant » : la consigne en vigueur est la derniere decision de session.
            c = consignes[-1]
            s["consigne"] = {"date": c["instant"][:16].replace("T", " ") + " UTC",
                             "etat": c["etat"], "trade": c["trade"],
                             "position": c["position"], "brut": c["brut"],
                             "ordres": c["ordres"], "votes": c["votes"], "somme": c["somme"]}
        voies.append({
            "nom": nom, "titre": titre, "instrument": instrument,
            "statut": statut(nom, registre),
            "suivi": s,
            "paper": paper(_lire(racine / f"PAPER_{nom}.jsonl"), lignes_suivi),
        })
    return {"voies": voies, "paires": list(vc.PAIRES),
            "genere_le": datetime.now(UTC).isoformat(timespec="seconds")}


# --- Valorisation au prix du moment ---------------------------------------------------------
# Le paper ne s'execute qu'aux passages (01:00 UTC, sessions VC4) : son equite est celle de ce
# moment-la (le 13/10, en plein creux de la nuit). Ici on revalorise, sans rien ecrire, les
# quantites et le cash du DERNIER passage aux milieux bid/ask actuels — meme formule que le
# paper : equite = cash + somme(q * milieu). Le funding couru depuis le passage n'y est pas
# (il est regle au passage suivant). Route separee : /api/forward reste hors ligne.
CACHE_VALORISATION_S = 60
_cache_prix: dict = {"t": 0.0, "prix": None, "le": None}


def prix_binance() -> dict[str, dict[str, float]]:
    """Milieux bid/ask actuels par instrument et paire (routes publiques bookTicker)."""
    import time

    from beta import paper as pp
    if _cache_prix["prix"] is not None and time.monotonic() - _cache_prix["t"] < CACHE_VALORISATION_S:
        return _cache_prix["prix"]
    marche = pp.MarcheBinance()
    voulus = {f"{p}USDT": p for p in pp.PAIRES}
    symboles = json.dumps(sorted(voulus), separators=(",", ":"))
    prix = {}
    for instrument, params in ((pp.SPOT, {"symbols": symboles}), (pp.PERPETUEL, {})):
        lignes = marche._get(instrument, "ticker/bookTicker", **params)
        prix[instrument] = {voulus[l["symbol"]]: (float(l["bidPrice"]) + float(l["askPrice"])) / 2
                            for l in lignes if l["symbol"] in voulus}
    _cache_prix.update(t=time.monotonic(), prix=prix,
                       le=datetime.now(UTC).isoformat(timespec="seconds"))
    return prix


def valorisation(racine: Path | None = None, prix: dict | None = None,
                 le: str | None = None) -> dict:
    racine = racine or config.RACINE
    try:
        prix = prix if prix is not None else prix_binance()
        le = le or _cache_prix["le"]
    except Exception as exc:  # noqa: BLE001 — affichage seulement : Binance injoignable
        return {"erreur": f"prix Binance illisibles : {exc}", "voies": {}}
    voies = {}
    for nom, _, _ in VOIES:
        lignes = _lire(racine / f"PAPER_{nom}.jsonl")
        if not lignes:
            continue
        derniere = lignes[-1]
        cours = prix.get(derniere["instrument"], {})
        if any(p not in cours for p, q in derniere["quantites"].items() if q):
            continue
        equite = derniere["cash"] + sum(q * cours[p] for p, q in derniere["quantites"].items() if q)
        voies[nom] = {
            "equite": equite,
            "rendement": equite / lignes[0]["capital_initial"] - 1.0,
            "depuis_passage": equite / derniere["equite"] - 1.0,
            "dernier_passage": derniere.get("execute_le"),
        }
    return {"prix_le": le, "voies": voies}
