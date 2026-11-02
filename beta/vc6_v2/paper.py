"""« Paper de plomberie – VC6 V2 poche baissiere sous HAR » (Jonas, 02/11/2026).

Run NON juge : il sert uniquement a verifier l'execution. Regles : VC6_V2/spec_figee.md sans aucune
modification (regles de la V2 gelees, empreinte epinglee ici). Decisions de Jonas du 02/11/2026 :
    A. comptant : le backtest compte les couts comme au comptant (funding seulement sur la part en
       levier, jamais utilisee). Le funding reel des perpetuels BTC, ETH et SOL est journalise
       chaque jour, pour information, jamais paye ;
    B. n'echanger que quand le modele change une exposition (position nette par actif) ;
    C. ligne de diagnostic au registre (`VC6_V2_PAPER`), sans essai, compteur inchange ;
    D. execution a l'ouverture de la bougie 1 min de 00:00 UTC (comptant Binance), + 10 pb.

Chaque jour E (timer beta-vc6-paper, apres beta-maj) : decision a la cloture de E-1 (barre 5 min de
23:55) avec le code du backtest (`beta.vc6_v2.vivant.decider`), execution simulee au prix de 00:00
de E, une ligne dans PAPER_VC6.jsonl (ajout seul). Le premier jour construit toute la position.
Donnee manquante a la cloture : aucun nouvel ordre, une ligne « donnee manquante », alerte. Aucune
cle, aucun ordre reel : seules les routes publiques de Binance sont lues (`beta.paper`).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

from beta import config
from beta import paper as bp
from beta.vc6_v2 import regles as R
from beta.vc6_v2 import vivant

ID = "VC6_V2_PAPER"
NOM = "Paper de plomberie – VC6 V2 poche baissière sous HAR"
EMPREINTE_REGLES_V2 = "e39ad1cdaa14326e"
JOURNAL = "PAPER_VC6.jsonl"
CAPITAL_USDT = 10_000.0
ACTIFS = R.POCHES

PAPER = {
    "id": ID, "nom": NOM, "regles_v2": EMPREINTE_REGLES_V2, "essai": vivant.ESSAI,
    "instrument": "comptant Binance (BTCUSDT, ETHUSDT, SOLUSDT)", "capital_usdt": CAPITAL_USDT,
    "decision": "cloture du jour D (barre 5 min de 23:55 du perpetuel), code du backtest",
    "prix_execution": "ouverture de la bougie 1 min de 00:00 UTC du jour D+1, comptant",
    "frais_pb": R.FRAIS_PB,
    "echanges": "seulement quand le modele change une exposition (position nette par actif) ; "
                "le premier jour construit toute la position",
    "funding": "reglements des perpetuels journalises pour information, jamais payes",
    "donnee_manquante": "aucun nouvel ordre, ligne au journal, alerte",
    "fantome": "sigma HAR nourri par Garman-Klass sur les bougies 1 j du lake, sans effet",
}


class PaperError(RuntimeError):
    """Marche illisible, ou execution impossible au comptant : rien n'est ecrit ce jour-la."""


def verifier_gel() -> dict:
    """Le verrou : ligne de diagnostic au registre, regles V2 et parametres du paper inchanges."""
    from beta.protocole import experiences
    entree = experiences.exiger(ID)
    ecarts = {"diagnostic": (entree.get("diagnostic"), True),
              "regles_v2": (R.empreinte(), EMPREINTE_REGLES_V2),
              "empreinte_paper": (entree.get("empreinte_paper"), empreinte())}
    rompus = {k: v for k, v in ecarts.items() if v[0] != v[1]}
    if rompus:
        raise PaperError(f"gel du paper rompu : {rompus}")
    return entree


def empreinte() -> str:
    texte = json.dumps(PAPER, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()[:16]


def chemin_journal(repertoire: Path | None = None) -> Path:
    return (repertoire or config.RACINE) / JOURNAL


def lire_journal(chemin: Path) -> list[dict]:
    return bp.lire_journal(chemin)


def executer(etat: dict | None, poids: dict[str, float], a_traiter: list[str],
             prix: dict[str, float], regles: dict[str, bp.Regles], frais_pb: float) -> dict:
    """Une execution au comptant, pure. `etat` = cash et quantites apres la derniere execution
    (None le premier jour, qui construit toute la position) ; `poids` = positions nettes du modele
    en fraction du capital ; seules les paires `a_traiter` bougent ensuite. Ventes d'abord ;
    jamais de decouvert."""
    premiere = etat is None
    cash = CAPITAL_USDT if premiere else float(etat["cash"])
    q = {a: (0.0 if premiere else float(etat["quantites"][a])) for a in ACTIFS}
    valeur_avant = cash + sum(q[a] * prix[a] for a in ACTIFS)
    traiter = sorted(a for a in ACTIFS if poids[a] != 0.0) if premiere else sorted(a_traiter)
    voulus, ignores = {}, []
    for a in traiter:
        cible = max(bp.au_pas(poids[a] * valeur_avant / prix[a], regles[a]), 0.0)
        ordre = round(cible - q[a], regles[a].decimales)
        if ordre == 0.0:
            continue
        notional = abs(ordre) * prix[a]
        if notional < regles[a].notional_min or abs(ordre) < regles[a].qte_min:
            ignores.append({"actif": a, "qte": ordre, "notional": round(notional, 4),
                            "raison": f"sous le minimum ({regles[a].notional_min:g} USDT, "
                                      f"{regles[a].qte_min:g})"})
            continue
        voulus[a] = ordre
    taux = frais_pb / 1e4
    achats = {a: o for a, o in voulus.items() if o > 0}
    dispo = cash + sum(-o * prix[a] * (1 - taux) for a, o in voulus.items() if o < 0)
    cout = sum(o * prix[a] * (1 + taux) for a, o in achats.items())
    if cout > dispo:
        echelle = max(dispo, 0.0) / cout
        for a, o in achats.items():
            voulus[a] = bp.au_pas(o * echelle, regles[a], vers_zero=True)
            if voulus[a] * prix[a] < regles[a].notional_min:
                ignores.append({"actif": a, "qte": o, "raison": "cash insuffisant"})
                del voulus[a]
    ordres, frais = [], 0.0
    for a, o in sorted(voulus.items(), key=lambda x: x[1]):
        notional = abs(o) * prix[a]
        f = notional * taux
        cash -= o * prix[a] + f
        q[a] = round(q[a] + o, regles[a].decimales)
        frais += f
        ordres.append({"actif": a, "sens": "achat" if o > 0 else "vente", "qte": o,
                       "prix": prix[a], "notional": round(notional, 6), "frais": round(f, 8)})
    if cash < -1e-6 or any(v < 0 for v in q.values()):
        raise PaperError(f"comptant a decouvert apres execution ({cash:.2f} USDT)")
    valeur = cash + sum(q[a] * prix[a] for a in ACTIFS)
    return {"premiere": premiere, "a_traiter": traiter, "valeur_avant": valeur_avant,
            "ordres": ordres, "ignores": ignores, "frais": round(frais, 8), "cash": cash,
            "quantites": q, "valeur": valeur,
            "poids": {a: q[a] * prix[a] / valeur for a in ACTIFS}}


def _arrondi(x, n: int = 6):
    return None if x is None else round(float(x), n)


def _funding_du_jour(d: dict) -> dict:
    """Pour information : chaque reglement de ]D 00:00 ; D+1 00:00] (lake), par actif."""
    debut = d["jour"].tz_localize("UTC")
    out = {}
    for a in ACTIFS:
        s = d["reglements"][a]
        s = s[(s.index > debut) & (s.index <= debut + vivant.UN)]
        out[a] = [{"instant": f"{t:%Y-%m-%d %H:%M}", "taux": float(v)} for t, v in s.items()]
    return out


def _gk(fant: dict | None, a: str):
    x = (fant or {}).get(a)
    return x.get("sigma_har_gk") if isinstance(x, dict) else None


def e_paper(poids_paper: dict[str, float], baissiere_modele: float) -> dict[str, float]:
    """Ei reelle du paper : poids tenu / poids de la poche ; pour le BTC, hors poche baissiere."""
    return {a: (poids_paper[a] - (baissiere_modele if a == "BTC" else 0.0)) / R.POIDS[a]
            for a in ACTIFS}


def ligne_executee(jour_exec: dt.date, dec: dict, fant: dict | None, exe: dict, prix: dict,
                   funding: dict, maintenant: dt.datetime) -> dict:
    pb = dec["poche_baissiere"]
    ep = e_paper(exe["poids"], pb["modele"])
    return {
        "date": jour_exec.isoformat(), "statut": "execute", "run": NOM, "id": ID,
        "ecrit_le": maintenant.isoformat(timespec="seconds"),
        "regles_v2": EMPREINTE_REGLES_V2, "paper": empreinte(),
        "decision": {"cloture": dec["jour_decision"], "mode_btc": dec["mode_btc"],
                     "en_rampe": dec["en_rampe"], "levier_modele": dec["levier_modele"]},
        "actifs": {a: {"sigma_har": _arrondi(dec["poches"][a]["sigma_har"]),
                       "sigma_har_gk_fantome": _arrondi(_gk(fant, a)),
                       "ecart_type_30j": _arrondi(dec["poches"][a]["ecart_type_30j"]),
                       "funding_annualise": _arrondi(dec["poches"][a]["funding_annualise"]),
                       "e_cible": _arrondi(dec["poches"][a]["e_cible"]),
                       "e_modele": _arrondi(dec["poches"][a]["e_modele"]),
                       "e_paper": _arrondi(ep[a]),
                       "contraint": dec["poches"][a]["contraint"],
                       "poids_modele": _arrondi(dec["poids_modele"][a]),
                       "poids_paper": _arrondi(exe["poids"][a])}
                   for a in ACTIFS},
        "poche_baissiere": {k: _arrondi(v) for k, v in pb.items()},
        "fantome": fant,
        "a_traiter": exe["a_traiter"], "prix": prix,
        "prix_source": PAPER["prix_execution"],
        "ordres": exe["ordres"], "ignores": exe["ignores"], "frais": exe["frais"],
        "funding_info": funding,
        "cash": exe["cash"], "quantites": exe["quantites"],
        "valeur_avant": exe["valeur_avant"], "valeur": exe["valeur"],
        "capital_initial": CAPITAL_USDT, "premiere": exe["premiere"],
    }


def ligne_manquante(jour_exec: dt.date, raison: str, etat: dict | None, prix: dict | None,
                    maintenant: dt.datetime) -> dict:
    cash = CAPITAL_USDT if etat is None else float(etat["cash"])
    q = {a: (0.0 if etat is None else float(etat["quantites"][a])) for a in ACTIFS}
    valeur = None if prix is None else cash + sum(q[a] * prix[a] for a in ACTIFS)
    return {"date": jour_exec.isoformat(), "statut": "donnee_manquante", "run": NOM, "id": ID,
            "ecrit_le": maintenant.isoformat(timespec="seconds"),
            "regles_v2": EMPREINTE_REGLES_V2, "paper": empreinte(),
            "decision": {"cloture": (jour_exec - dt.timedelta(days=1)).isoformat()},
            "manquant": raison, "ordres": [], "ignores": [], "frais": 0.0, "prix": prix,
            "cash": cash, "quantites": q, "valeur_avant": valeur, "valeur": valeur,
            "capital_initial": CAPITAL_USDT, "premiere": etat is None, "alerte": True}


def journee(maintenant: dt.datetime, marche, chemin: Path) -> dict | None:
    """Le jour d'execution `maintenant.date()` : une ligne ecrite, ou None si deja fait.
    Leve PaperError si le marche est illisible (rien n'est ecrit)."""
    jour_exec = maintenant.date()
    lignes = lire_journal(chemin)
    if lignes and lignes[-1]["date"] == jour_exec.isoformat():
        return None
    etat = None if not lignes else {"cash": lignes[-1]["cash"],
                                    "quantites": lignes[-1]["quantites"]}
    instant = dt.datetime.combine(jour_exec, dt.time(0, 0), dt.UTC)
    try:
        prix = {a: marche.prix_a(bp.SPOT, f"{a}USDT", instant) for a in ACTIFS}
        regles = {a: marche.regles(bp.SPOT, f"{a}USDT") for a in ACTIFS}
    except bp.PaperError as exc:
        raise PaperError(str(exc)) from exc
    try:
        d = vivant.charger(jour_exec - dt.timedelta(days=1))
        dec = vivant.decider(d)
    except vivant.DonneeManquante as exc:
        ligne = ligne_manquante(jour_exec, str(exc), etat, prix, maintenant)
    else:
        try:
            fant = vivant.fantome(d)
        except Exception as exc:  # noqa: BLE001 - le fantome ne bloque jamais une journee
            fant = {"erreur": str(exc)}
        exe = executer(etat, dec["poids_modele"], dec["a_traiter"], prix, regles, R.FRAIS_PB)
        ligne = ligne_executee(jour_exec, dec, fant, exe, prix, _funding_du_jour(d), maintenant)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ligne, ensure_ascii=True) + "\n")
    return ligne
