"""T1J : la campagne preenregistree, de bout en bout.

Ordre impose (prompt du 24/10, regle 3) : gel verifie -> donnees -> compteur affiche -> les 16
essais du verdict journalises -> epreuve de causalite -> calculs -> rapport ecrit par le programme.
Rien n'est calcule sur les vraies donnees avant la journalisation.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import subprocess
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from beta import config
from beta.protocole import experiences
from beta.temps1_justesse import detecteurs as det
from beta.temps1_justesse import donnees as dn
from beta.temps1_justesse import juge as jg
from beta.temps1_justesse import mesures as ms
from beta.temps1_justesse import regles as R
from beta.temps1_justesse import verdict as vd

log = logging.getLogger("beta.temps1_justesse.campagne")

ID_EXP = R.ID_EXP
DOSSIER = config.DATA / "temps1_justesse"
SORTIE = config.RACINE / "temps1_justesse"
RAPPORT = SORTIE / "RAPPORT_JUSTESSE.md"
MARQUEUR = "<!-- FIN DES CLARIFICATIONS"
COUPURES_CAUSALITE = ("1995-06-30", "2001-09-28", "2008-10-15", "2013-12-31", "2018-12-24",
                      "2020-03-23", "2022-06-16", "2025-04-08")


class GelError(RuntimeError):
    """Regles ou clarifications changees depuis le preenregistrement : la campagne refuse."""


# ----------------------------------------------------------------------------- gel, compteur

def clarifications() -> str:
    texte = RAPPORT.read_text(encoding="utf-8")
    if MARQUEUR not in texte:
        raise GelError(f"{RAPPORT} : marqueur de fin des clarifications absent")
    return texte.split(MARQUEUR, 1)[0]


def empreinte_clarifications() -> str:
    return hashlib.sha256(clarifications().encode("utf-8")).hexdigest()[:16]


def preenregistrement() -> dict:
    lignes = [x for x in experiences._lignes() if x.get("id") == ID_EXP
              and x.get("statut") == "preenregistre"]
    if not lignes:
        raise GelError(f"{ID_EXP} n'est pas preenregistree (scripts/preenregistrer_t1j.py)")
    return lignes[-1]


def verifier_gel() -> dict:
    experiences.exiger(ID_EXP)
    pre = preenregistrement()
    if pre.get("empreinte") != R.empreinte():
        raise GelError(f"regles changees depuis le gel : {pre.get('empreinte')} -> {R.empreinte()}")
    if pre.get("empreinte_clarifications") != empreinte_clarifications():
        raise GelError("section « Clarifications avant calcul » changee depuis le gel")
    return pre


def couples_verdict() -> list[tuple[str, str]]:
    """4 detecteurs x 3 actifs labo + 4 detecteurs x BTC = 16 (Jonas 24/10)."""
    return ([(d, a) for d in R.VERDICT for a in R.LABO_ACTIFS]
            + [(d, "BTC") for d in R.VERDICT])


def run_id(detecteur: str, actif: str, empreinte_donnees: str) -> str:
    cle = f"{ID_EXP}|{detecteur}|{actif}|{R.empreinte()}|{empreinte_donnees}"
    return hashlib.sha256(cle.encode()).hexdigest()[:12]


def compteurs() -> dict:
    return {"global": experiences.compteur_total(),
            "invest": experiences.compteur(famille="invest"),
            "trading": experiences.compteur(famille="trading")}


def detail_compteur(empreinte_donnees: str) -> dict:
    """Ce qui va etre journalise, et les compteurs attendus : affiche AVANT de lancer."""
    deja = {x.get("run_id") for x in experiences.runs_journalises()}
    rids = {run_id(d, a, empreinte_donnees): (d, a) for d, a in couples_verdict()}
    nouveaux = [r for r in rids if r not in deja]
    avant = compteurs()
    pre = preenregistrement()
    en_attente = 1 if not any(x.get("experience") == ID_EXP
                              for x in experiences.runs_journalises()) else 0
    attendu = {"global": avant["global"] - en_attente + len(nouveaux),
               "invest": avant["invest"] - en_attente + len(nouveaux), "trading": avant["trading"]}
    return {"gel_global_22_10": (pre.get("compteur") or {}).get("gel_global_22_10"),
            "avant_preenregistrement": {"global": (pre.get("compteur") or {}).get("global_avant"),
                                        "invest": (pre.get("compteur") or {}).get("invest_avant")},
            "avant_journalisation": avant, "attendu_apres": attendu,
            "essais_verdict": len(rids), "nouveaux": len(nouveaux),
            "calcul": f"{len(R.VERDICT)} detecteurs x {len(R.LABO_ACTIFS)} actifs labo + "
                      f"{len(R.VERDICT)} detecteurs x BTC = {len(rids)}",
            "couples": [{"run_id": r, "detecteur": d, "actif": a} for r, (d, a) in rids.items()],
            "informatifs": {"bande": len(R.BANDE) * len(R.LABO_ACTIFS),
                            "variantes_c1_v1": len(R.VARIANTES_C1) * len(R.LABO_ACTIFS),
                            "total": (len(R.BANDE) + len(R.VARIANTES_C1)) * len(R.LABO_ACTIFS)}}


def lignes_detail(c: dict) -> list[str]:
    a, b = c["avant_journalisation"], c["attendu_apres"]
    return [
        f"Compteur au gel du preenregistrement (22/10, global) : {c['gel_global_22_10']}",
        f"Compteur global (compteur_total) : {a['global']} -> {b['global']}",
        f"Compteur invest (compteur famille invest, tests de detecteurs) : "
        f"{a['invest']} -> {b['invest']}",
        f"Compteur trading actif : {a['trading']} (inchange)",
        f"Essais du verdict : {c['calcul']} ({c['nouveaux']} a journaliser)",
        f"Essais informatifs (ligne a part, aucun compteur) : bande {c['informatifs']['bande']} + "
        f"variantes C1_V1 {c['informatifs']['variantes_c1_v1']} = {c['informatifs']['total']}",
    ]


def journaliser(c: dict) -> None:
    """Les 16 essais au compteur, AVANT tout calcul. Un run deja journalise ne recompte pas."""
    deja = {x.get("run_id") for x in experiences.runs_journalises()}
    for x in c["couples"]:
        if x["run_id"] not in deja:
            experiences.enregistrer_run(x["run_id"], ID_EXP,
                                        f"temps1_justesse:{x['detecteur']}:{x['actif']}",
                                        R.empreinte(), issue="lance")


# ----------------------------------------------------------------------------- causalite

def tronquer(d: dn.Donnees, coupure: pd.Timestamp) -> dn.Donnees:
    """Les donnees telles qu'on les connaissait a la cloture de `coupure`."""
    garde = d.usdjpy_utilisable <= coupure
    return dn.Donnees(prix={a: s[s.index <= coupure] for a, s in d.prix.items()},
                      vix=d.vix[d.vix.index <= coupure], usdjpy=d.usdjpy[garde.to_numpy()],
                      usdjpy_utilisable=d.usdjpy_utilisable[garde], seances_us=d.seances_us[
                          d.seances_us <= coupure], empreinte="tronque", couverture={})


def epreuve_causalite(d: dn.Donnees) -> list[dict]:
    """signal(donnees connues en t)[: t] doit egaler signal(tout)[: t], NaN compris."""
    echecs = []
    complets = {}
    for coupure in map(pd.Timestamp, COUPURES_CAUSALITE):
        dt = tronquer(d, coupure)
        for actif in R.ACTIFS:
            if dt.prix[actif].empty:
                continue
            for nom in (*R.VERDICT, *R.BANDE, *R.VARIANTES_C1):
                if (nom, actif) not in complets:
                    complets[nom, actif] = det.signal(d, nom, actif)
                plein = complets[nom, actif]
                court = det.signal(dt, nom, actif)
                ref = plein[plein.index <= coupure]
                egal = (court.index.equals(ref.index)
                        and np.array_equal(court.to_numpy(), ref.to_numpy(), equal_nan=True))
                if not egal:
                    echecs.append({"coupure": f"{coupure:%Y-%m-%d}", "detecteur": nom,
                                   "actif": actif})
    return echecs


# ----------------------------------------------------------------------------- calculs

def periodes(d: dn.Donnees) -> dict[str, tuple[pd.Timestamp, pd.Timestamp | None]]:
    return {"labo": (pd.Timestamp(R.LABO[0]), pd.Timestamp(R.LABO[1])),
            "informative": (pd.Timestamp(R.DEBUT_INFORMATIVE), None),
            "btc": (jg.premier_trimestre(d.prix["BTC"]), None)}


def _mesurer(sig, j, debut, fin, hasard=False) -> dict:
    try:
        return ms.mesurer(sig, j, debut, fin, hasard=hasard)
    except ms.MesureError as exc:
        return {"erreur": str(exc)}


def tables_verdict(d: dn.Donnees, signaux: dict, juges: dict, per: dict) -> dict:
    """Les mesures qui decident : 4 detecteurs sur SPX, NDX, or (labo) et BTC, plus le temoin."""
    t = {}
    for nom in R.VERDICT:
        hasard = nom in ("C1_V1", "C1_V2")
        t[nom] = {a: _mesurer(signaux[nom][a], juges[a], *per["labo"], hasard=hasard)
                  for a in R.LABO_ACTIFS}
        t[nom]["BTC"] = _mesurer(signaux[nom]["BTC"], juges["BTC"], *per["btc"], hasard=hasard)
        if "erreur" not in t[nom]["SPX"] and "erreur" not in t[nom]["NDX"]:
            t[nom]["TEMOIN"] = vd.temoin(t[nom]["SPX"], t[nom]["NDX"])
    return t


def indecidable(t: dict) -> list[str]:
    return [f"{nom} x {a} : {t[nom][a]['erreur']}" for nom in t for a in t[nom]
            if "erreur" in t[nom][a]]


def calculer(d: dn.Donnees) -> dict:
    per = periodes(d)
    sigma_ref = jg.sigma_sp_ref(d.prix["SPX"])
    juges = {a: jg.juger(d.prix[a], sigma_ref) for a in R.ACTIFS}
    noms_labo = (*R.VERDICT, *R.BANDE, *R.VARIANTES_C1)
    signaux = {nom: {a: det.signal(d, nom, a) for a in R.LABO_ACTIFS} for nom in noms_labo}
    for nom in R.VERDICT:
        signaux[nom]["BTC"] = det.signal(d, nom, "BTC")

    principal = tables_verdict(d, signaux, juges, per)
    bloque = indecidable(principal)
    v = None if bloque else vd.verdict(principal)

    informatifs = {}
    for nom in (*R.BANDE, *R.VARIANTES_C1):
        informatifs[nom] = {a: _mesurer(signaux[nom][a], juges[a], *per["labo"])
                            for a in R.LABO_ACTIFS}
        if all("erreur" not in informatifs[nom][a] for a in R.TEMOIN):
            informatifs[nom]["TEMOIN"] = vd.temoin(informatifs[nom]["SPX"],
                                                   informatifs[nom]["NDX"])

    deja_vu = {}
    for nom in R.VERDICT:
        deja_vu[nom] = {a: _mesurer(signaux[nom][a], juges[a], *per["informative"])
                        for a in R.LABO_ACTIFS}
        if all("erreur" not in deja_vu[nom][a] for a in R.TEMOIN):
            deja_vu[nom]["TEMOIN"] = vd.temoin(deja_vu[nom]["SPX"], deja_vu[nom]["NDX"])

    robustesse = {}
    for cle, p in R.VARIANTES_JUGE.items():
        jv = {}
        for a in R.ACTIFS:
            sig_u = None
            if p.get("sigma_unique"):
                debut, fin = per["btc"] if a == "BTC" else per["labo"]
                r = jg.rendements_log(d.prix[a])
                r = r[(r.index >= debut) & ((r.index <= fin) if fin is not None else True)]
                sig_u = jg.sigma_annualise(r)
            jv[a] = jg.juger(d.prix[a], sigma_ref, baisse_ref=p.get("baisse_ref",
                                                                    R.DELTA_REF_BAISSE),
                             sigma_unique=sig_u)
        tv = tables_verdict(d, signaux, jv, per)
        bloque_v = indecidable(tv)
        robustesse[cle] = {"tables": tv, "indecidable": bloque_v,
                           "verdict": None if bloque_v else vd.verdict(tv),
                           "juges": {a: _resume_juge(jv[a], d.prix[a], per, a) for a in R.ACTIFS}}
    solide = None
    if v is not None and all(r["verdict"] is not None for r in robustesse.values()):
        solide = all(vd.cle_solidite(r["verdict"]) == vd.cle_solidite(v)
                     for r in robustesse.values())
    return {"sigma_sp_ref": sigma_ref, "periodes": {k: [f"{a:%Y-%m-%d}", None if b is None else
                                                        f"{b:%Y-%m-%d}"] for k, (a, b) in
                                                    per.items()},
            "juges": {a: _resume_juge(juges[a], d.prix[a], per, a) for a in R.ACTIFS},
            "principal": principal, "indecidable": bloque, "verdict": v,
            "informatifs": informatifs, "deja_vu": deja_vu, "robustesse": robustesse,
            "solide": solide}


def _resume_juge(j: jg.Juge, close: pd.Series, per: dict, actif: str) -> dict:
    """Bears du juge qui touchent les periodes de l'actif, et la plage des theta."""
    noms = ("btc",) if actif == "BTC" else ("labo", "informative")
    dernier = j.pivots[-1] if j.pivots else None
    sortie = {"debut_juge": j.infos["debut"], "periodes": {},
              "dernier_pivot": None if dernier is None else
              {"date": f"{j.dates[dernier[0]]:%Y-%m-%d}", "type": dernier[1]}}
    for nom in noms:
        debut, fin = per[nom]
        fin = close.index.max() if fin is None else fin
        dans = (j.dates >= debut) & (j.dates <= fin)
        bears = []
        for a, b in j.bears():
            if j.dates[b] < debut or j.dates[a] > fin:
                continue
            bears.append({"pic": f"{j.dates[a]:%Y-%m-%d}", "creux": f"{j.dates[b]:%Y-%m-%d}",
                          "baisse": float(j.prix[b] / j.prix[a] - 1.0),
                          "dans_la_periode": bool(debut <= j.dates[a] and j.dates[b] <= fin)})
        en_cours = None
        if j.pivots and j.pivots[-1][1] == jg.PIC and j.dates[j.pivots[-1][0]] <= fin:
            i = j.pivots[-1][0]
            en_cours = {"pic": f"{j.dates[i]:%Y-%m-%d}",
                        "baisse_a_ce_jour": float(j.prix[-1] / j.prix[i] - 1.0)}
        sortie["periodes"][nom] = {
            "theta_baisse": [float(np.nanmin(j.theta_baisse[dans])),
                             float(np.nanmax(j.theta_baisse[dans]))],
            "theta_hausse": [float(np.nanmin(j.theta_hausse[dans])),
                             float(np.nanmax(j.theta_hausse[dans]))],
            "bears": bears, "bear_en_cours": en_cours}
    return sortie


# ----------------------------------------------------------------------------- campagne

def _code() -> str | None:
    try:
        return subprocess.run(["git", "-C", str(config.RACINE), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _propre(x):
    """JSON strict : NaN et infinis -> None, types numpy -> Python."""
    if isinstance(x, dict):
        return {str(k): _propre(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_propre(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return None if not math.isfinite(float(x)) else float(x)
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def lancer(recalculer: bool = False) -> dict:
    """La campagne T1J. Rend la synthese ecrite dans data/temps1_justesse/."""
    from beta.temps1_justesse import rapport

    pre = verifier_gel()
    d = dn.charger()
    sortie_json = DOSSIER / f"campagne_{ID_EXP}_{d.empreinte}.json"
    if sortie_json.exists() and not recalculer:
        log.info("deja calculee sur ces donnees (%s) : rapport regenere seulement", d.empreinte)
        synthese = json.loads(sortie_json.read_text(encoding="utf-8"))
        rapport.ecrire(synthese)
        return synthese
    c = detail_compteur(d.empreinte)
    for ligne in lignes_detail(c):
        log.info("%s", ligne)
    journaliser(c)
    apres = compteurs()
    log.info("compteurs apres journalisation : global %d, invest %d, trading %d",
             apres["global"], apres["invest"], apres["trading"])
    echecs = epreuve_causalite(d)
    if echecs:
        log.error("epreuve de causalite ECHOUEE : %s", echecs[:5])
    res = None if echecs else calculer(d)
    synthese = _propre({
        "experience": ID_EXP, "code": _code(), "regles": R.empreinte(),
        "clarifications": empreinte_clarifications(),
        "calcule_le": datetime.now(UTC).isoformat(timespec="seconds"),
        "donnees": {"empreinte": d.empreinte, "couverture": d.couverture,
                    "dexjpus_publication": R.REGLES["donnees"]["dexjpus_publication"]},
        "compteur": {**c, "apres_journalisation": apres,
                     "preenregistrement": pre.get("compteur")},
        "causalite": {"coupures": list(COUPURES_CAUSALITE), "echecs": echecs},
        "resultats": res})
    DOSSIER.mkdir(parents=True, exist_ok=True)
    sortie_json.write_text(json.dumps(synthese, ensure_ascii=False), encoding="utf-8")
    rapport.ecrire(synthese)
    if res is not None:
        v = res["verdict"]
        issue = ("indecidable : " + "; ".join(res["indecidable"])) if v is None else v["statut"]
        cle = hashlib.sha256("|".join(x["run_id"] for x in c["couples"]).encode()).hexdigest()[:12]
        experiences.marquer_mesuree(ID_EXP, cle, f"campagne (16 essais du verdict) — {issue}")
    return synthese
