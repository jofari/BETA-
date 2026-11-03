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
    # Paper de plomberie (Jonas 02/11) : journal a part (beta.vc6_v2.paper), pas de suivi au
    # cours de cloture ; non juge, VC6 rejetee le 02/11.
    ("VC6", "VC6 V2 — poche baissière sous HAR", "comptant"),
)
PAPER_SEUL = {"VC6": "paper de plomberie — non jugé (VC6 rejetée le 02/11, rodage de l'exécution)"}
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
    if nom in PAPER_SEUL:
        return PAPER_SEUL[nom]
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


TOLERANCE_PAS = 5e-4                # le journal arrondit a 6 decimales


def pas_a_pas(consigne: dict | None) -> dict | None:
    """L'allocation de la consigne du jour, etape par etape, CONTRE-VERIFIEE.

    Rien n'est decide ici : la chaine (`c2_suivi`) a deja calcule et journalise chaque brique
    (`indicateurs.moteur`, `indicateurs.execution`). On refait chaque etape a partir des briques
    de l'etape precedente, par la formule ecrite en clair, et on compare au resultat journalise.
    Un controle faux = l'explication affichee ne decrit pas ce que la chaine a fait : a creuser,
    jamais a corriger ici. Voies a cadence quotidienne seulement (VC4 ne journalise pas le moteur).
    """
    ind = (consigne or {}).get("indicateurs") or {}
    m, ex = ind.get("moteur"), ind.get("execution")
    if not m or not ex:
        return None
    h = m["params"]
    controles: list[dict] = []

    def controle(etape: int, libelle: str, attendu: float, journal: float | None) -> bool:
        ok = journal is not None and abs(attendu - journal) <= TOLERANCE_PAS
        controles.append({"etape": etape, "libelle": libelle, "attendu": attendu,
                          "journal": journal, "ok": ok})
        return ok

    # 1. Poids : 50 % base (inverse de la vol) + 50 % tendance (idem si momentum > 0).
    inverses = {p: 1.0 / x["vol_180j"] for p, x in m["paires"].items() if x["vol_180j"]}
    somme_inv = sum(inverses.values())
    poids = []
    for paire, x in m["paires"].items():
        base = inverses.get(paire, 0.0) / somme_inv if somme_inv else 0.0
        tendance = base if x["tendance_active"] else 0.0
        composite = h["poids_jambes"] * (base + tendance)
        controle(1, f"{paire} : poids de base", base, x["poids_base"])
        controle(1, f"{paire} : composite", composite, x["composite"])
        poids.append({"paire": paire, "vol": x["vol_180j"], "inverse": inverses.get(paire),
                      "base": base, "momentum": x["momentum"],
                      "tendance_active": x["tendance_active"], "tendance": tendance,
                      "composite": composite})
    somme_composite = sum(x["composite"] for x in poids)
    controle(1, "somme des composites", somme_composite, m["somme_composite"])

    # 2. Taille : cible de vol / vol du portefeuille, bornee, avec hysteresis.
    brut_calcule = m["cible_vol"] / m["sigma"] if m["sigma"] else None
    calcule = min(max(brut_calcule, h["lmin"]), h["lmax"]) if brut_calcule else None
    controle(2, "levier calcule", calcule, m["levier_calcule"])
    ecart_levier = abs(m["levier_calcule"] - m["levier"])
    change = ecart_levier <= TOLERANCE_PAS
    # En vigueur = calcule (il vient de bouger) ou ecart <= seuil (on garde l'ancien).
    controles.append({"etape": 2, "libelle": "hysteresis du levier", "attendu": h["seuil_levier"],
                      "journal": ecart_levier, "ok": change or ecart_levier <= h["seuil_levier"]})

    # 3. Position voulue : composite x levier en vigueur, plafonnee (spot : pas d'emprunt).
    brut_moteur = somme_composite * m["levier"]
    plafond = m.get("plafond_brut")
    echelle = plafond / brut_moteur if plafond is not None and brut_moteur > plafond else 1.0
    for x in poids:
        x["voulu"] = x["composite"] * m["levier"] * echelle
        controle(3, f"{x['paire']} : voulu", x["voulu"], m["paires"][x["paire"]]["voulu"])
    brut_voulu = brut_moteur * echelle
    controle(3, "investi voulu", brut_voulu, m["brut_voulu"])
    controle(3, "investi voulu (execution)", brut_voulu, ex["brut_voulu"])

    # 4. Ordre ou non : regle de l'etat du jour sur l'ecart tenu / voulu.
    etat = ind.get("etat")
    if etat == "haussier":
        regle = "somme des écarts |voulu − tenu| par paire > bande"
        attendu = ex["ecart"] > ex["bande"]
    elif etat == "veille":
        regle = "investi tenu − investi voulu > bande (réduction seulement)"
        attendu = ex["brut_tenu"] - ex["brut_voulu"] > ex["bande"]
    else:
        regle, attendu = "baissier : règles de poche et de coupe des alts", None
    if attendu is not None:
        controles.append({"etape": 4, "libelle": "décision d'ordre", "attendu": attendu,
                          "journal": bool(consigne.get("trade")),
                          "ok": attendu == bool(consigne.get("trade"))})
    return {
        "etat": etat, "lu": m["lu"], "params": h,
        "etape1": {"paires": poids, "somme_composite": somme_composite},
        "etape2": {"cible_vol": m["cible_vol"], "sigma": m["sigma"], "brut": brut_calcule,
                   "calcule": m["levier_calcule"], "en_vigueur": m["levier"],
                   "ecart": ecart_levier, "change": change},
        "etape3": {"brut_moteur": brut_moteur, "plafond": plafond, "echelle": echelle,
                   "brut_voulu": brut_voulu},
        "etape4": {"regle": regle, "brut_tenu": ex["brut_tenu"], "ecart": ex["ecart"],
                   "bande": ex["bande"], "trade": bool(consigne.get("trade")),
                   "brut_final": consigne.get("brut")},
        "controles": controles,
        "verifie": all(c["ok"] for c in controles),
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
        # VC6 n'a pas de cout au carnet (execution au prix d'ouverture, frais fixes) : None.
        mesures = [o for o in ordres if o.get(cle) is not None]
        n = sum(o["notional"] for o in mesures)
        return sum(o[cle] * o["notional"] for o in mesures) / n if n else None

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


def passages_vc6(lignes: list[dict]) -> list[dict]:
    """Le journal VC6 (`beta.vc6_v2.paper`) traduit dans la forme des autres PAPER_<voie>.

    Rien n'est recalcule : memes chiffres, autres noms (valeur -> equite, ecrit_le ->
    execute_le, actif -> paire). Comptant : aucun funding regle (il est journalise pour
    information seulement, decision A de Jonas du 02/11). Une journee « donnee_manquante »
    garde le compte tel quel et ne passe aucun ordre.
    """
    sortie = []
    for ligne in lignes:
        if ligne.get("valeur") is None:
            continue
        prix, valeur = ligne.get("prix") or {}, ligne["valeur"]
        sortie.append({
            "date": ligne["date"], "execute_le": ligne.get("ecrit_le"),
            "statut": ligne.get("statut"), "capital_initial": ligne["capital_initial"],
            "equite_avant": ligne["valeur_avant"], "equite": valeur, "cash": ligne["cash"],
            "quantites": ligne["quantites"], "milieux": prix,
            "frais": ligne.get("frais") or 0.0, "funding": {},
            "ignores": ligne.get("ignores") or [],
            "poids": {a: q * prix[a] / valeur for a, q in ligne["quantites"].items()
                      if a in prix and valeur},
            "ordres": [{"paire": o["actif"], "sens": o["sens"], "notional": o["notional"],
                        "prix": o["prix"], "cout_carnet_pb": None, "ecart_ouverture_pb": None,
                        "slippage_modele_pb": None} for o in ligne.get("ordres") or []],
            "decision": ligne.get("decision"), "actifs": ligne.get("actifs"),
            "poche_baissiere": ligne.get("poche_baissiere"),
        })
    return sortie


def paper_vc6(lignes: list[dict]) -> dict | None:
    """Le paper VC6 dans la forme de `paper()`, plus la decision du jour (mode BTC, E par actif)."""
    passages = passages_vc6(lignes)
    if not passages:
        return None
    p = paper(passages, [])
    derniere = passages[-1]
    # Pas de modele quotidien a cote : la comparaison au backtest est le rejeu du lundi.
    p["modele"] = None
    for point in p["points"]:
        point["modele"] = None
    # Le rendement compte la journee executee (frais du jour compris), comme le releve minute.
    p["rendement"] = derniere["equite"] / p["capital"] - 1.0
    p["decision"] = {"date": derniere["date"], "statut": derniere["statut"],
                     **(derniere.get("decision") or {}),
                     "e_paper": {a: x.get("e_paper")
                                 for a, x in (derniere.get("actifs") or {}).items()},
                     "poche_baissiere": (derniere.get("poche_baissiere") or {}).get("modele")}
    return p


def vue(racine: Path | None = None) -> dict:
    racine = racine or config.RACINE
    registre = experiences.etat()
    voies = []
    for nom, titre, instrument in VOIES:
        if nom in PAPER_SEUL:
            voies.append({"nom": nom, "titre": titre, "instrument": instrument,
                          "statut": statut(nom, registre), "suivi": None, "paper_seul": True,
                          "paper": paper_vc6(_lire(racine / f"PAPER_{nom}.jsonl")),
                          "pas_a_pas": None})
            continue
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
            "pas_a_pas": pas_a_pas(s["consigne"]) if s else None,
        })
    return {"voies": voies, "paires": list(vc.PAIRES),
            "genere_le": datetime.now(UTC).isoformat(timespec="seconds")}


# --- Paper en direct ------------------------------------------------------------------------
# Un seul chiffre paper par voie, releve chaque minute par le timer beta-paper-direct
# (`beta.paper_direct`, DIRECT_PAPER.jsonl) : le compte du dernier passage aux prix de la
# minute, net du funding regle. La courbe part des passages quotidiens (PAPER_<voie>.jsonl)
# tant que le releve minute n'existait pas, puis suit les minutes. Le serveur ne lit pas
# Binance : il relit le fichier.
POINTS_MAX = 1500                   # par voie : au-dela, un point sur k (le dernier toujours)


def direct(racine: Path | None = None) -> dict:
    from beta import paper_direct
    racine = racine or config.RACINE
    minutes = paper_direct.lire(racine)
    voies = {}
    for nom, _, _ in VOIES:
        passages = _lire(racine / f"PAPER_{nom}.jsonl")
        if nom in PAPER_SEUL:
            passages = passages_vc6(passages)
        if not passages:
            continue
        capital = passages[0]["capital_initial"]
        releves = [(m["t"], m["e"][nom]) for m in minutes if nom in m["e"]]
        debut_minutes = releves[0][0] if releves else "9999"
        points = [(l["execute_le"], l["equite"]) for l in passages
                  if l.get("execute_le") and l["execute_le"] < debut_minutes] + releves
        pas = max(1, math.ceil(len(points) / POINTS_MAX))
        garde = points[::pas] + ([points[-1]] if (len(points) - 1) % pas else [])
        t, e = points[-1]
        voies[nom] = {"capital": capital, "t": t, "equite": e, "rendement": e / capital - 1.0,
                      "points": [{"t": x, "r": y / capital - 1.0} for x, y in garde]}
    return {"voies": voies, "genere_le": datetime.now(UTC).isoformat(timespec="seconds")}
