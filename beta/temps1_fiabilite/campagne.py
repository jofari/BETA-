"""T1F : la campagne de fiabilite, de bout en bout.

Ordre : modules de T1J verifies identiques au commit 8afdbe7 -> gel verifie (regles, texte du
preenregistrement, marque diagnostic) -> donnees de T1J reconstituees et verifiees (empreinte)
-> mesures observees verifiees egales a celles du rapport de T1J -> tests 1 et 1 bis (1 000
tirages par couple, graine 0) -> test 2 -> verdict mecanique -> rapport ecrit par le programme.
Aucun run n'est journalise : T1F est un diagnostic, le compteur ne bouge pas.
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
from beta.invest import nulls as d4
from beta.protocole import experiences
from beta.temps1_fiabilite import nulls
from beta.temps1_fiabilite import regles as R
from beta.temps1_justesse import campagne as cj
from beta.temps1_justesse import detecteurs as det
from beta.temps1_justesse import donnees as dn
from beta.temps1_justesse import juge as jg
from beta.temps1_justesse import mesures as ms
from beta.temps1_justesse import regles as RJ

log = logging.getLogger("beta.temps1_fiabilite.campagne")

DOSSIER = config.DATA / "temps1_fiabilite"
SORTIE = config.RACINE / "temps1_fiabilite"
TEXTE = SORTIE / "PREENREGISTREMENT.md"
JSON_T1J = config.DATA / "temps1_justesse" / f"campagne_T1J_{R.EMPREINTE_DONNEES_T1J}.json"
MESURES_VERIFIEES = ("f_entree_mediane", "fausses_alertes_an", "justesse", "n_bears",
                     "mesuree")


class FiabiliteError(RuntimeError):
    """Une condition du prompt n'est pas remplie : arret, aucun chiffre (regle 4)."""


# ----------------------------------------------------------------------------- verifications

def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(config.RACINE), *args], capture_output=True,
                          timeout=30)


def verifier_modules() -> list[str]:
    """Les modules de T1J reutilises doivent etre ceux du commit 8afdbe7, octet pour octet."""
    ecarts = []
    for nom in R.MODULES_JUSTESSE:
        chemin = f"beta/temps1_justesse/{nom}"
        ref = _git("show", f"{R.COMMIT_JUSTESSE}:{chemin}")
        if ref.returncode != 0 or ref.stdout != (config.RACINE / chemin).read_bytes():
            ecarts.append(chemin)
    return ecarts


def empreinte_texte() -> str:
    return hashlib.sha256(TEXTE.read_bytes()).hexdigest()[:16]


def verifier_gel() -> dict:
    experiences.exiger(R.ID_EXP)
    lignes = [x for x in experiences._lignes() if x.get("id") == R.ID_EXP
              and x.get("statut") == "preenregistre"]
    if not lignes:
        raise FiabiliteError(f"{R.ID_EXP} n'est pas journalisee (scripts/preenregistrer_t1f.py)")
    pre = lignes[-1]
    if pre.get("diagnostic") is not True:
        raise FiabiliteError(f"{R.ID_EXP} n'est pas marquee diagnostic")
    if pre.get("empreinte") != R.empreinte():
        raise FiabiliteError(f"regles changees depuis le gel : {pre.get('empreinte')} -> "
                             f"{R.empreinte()}")
    if pre.get("empreinte_preenregistrement") != empreinte_texte():
        raise FiabiliteError("temps1_fiabilite/PREENREGISTREMENT.md change depuis le gel")
    if RJ.empreinte() != R.EMPREINTE_REGLES_T1J:
        raise FiabiliteError("regles de T1J changees depuis sa mesure")
    return pre


def synthese_t1j() -> dict:
    if not JSON_T1J.exists():
        raise FiabiliteError(f"{JSON_T1J} absent : la mesure de T1J n'est pas lisible")
    return json.loads(JSON_T1J.read_text(encoding="utf-8"))


def donnees_t1j(t1j: dict) -> dn.Donnees:
    """Les donnees de T1J : chaque serie coupee a sa date de fin dans T1J, empreinte verifiee."""
    d = dn.charger()
    cov = t1j["donnees"]["couverture"]

    def coupe(s: pd.Series, nom: str) -> pd.Series:
        return s[s.index <= pd.Timestamp(cov[nom]["fin"])]

    prix = {a: coupe(s, a) for a, s in d.prix.items()}
    vix = coupe(d.vix, "VIX")
    jpy = coupe(d.usdjpy, "USDJPY")
    empreinte = dn._empreinte({**prix, "VIX": vix, "USDJPY": jpy})
    if empreinte != R.EMPREINTE_DONNEES_T1J:
        raise FiabiliteError(f"donnees differentes de celles de T1J : {empreinte} au lieu de "
                             f"{R.EMPREINTE_DONNEES_T1J}")
    return dn.Donnees(prix=prix, vix=vix, usdjpy=jpy,
                      usdjpy_utilisable=d.usdjpy_utilisable.reindex(jpy.index),
                      seances_us=prix["SPX"].index, empreinte=empreinte, couverture=cov)


def _egal(a, b) -> bool:
    if isinstance(a, float) or isinstance(b, float):
        return a is not None and b is not None and math.isclose(a, b, rel_tol=0, abs_tol=1e-12)
    return a == b


def verifier_observe(obs: dict, ref: dict) -> list[str]:
    """Mesures observees et bears : ceux du rapport de T1J, a l'identique."""
    ecarts = [k for k in MESURES_VERIFIEES if not _egal(obs.get(k), ref.get(k))]
    bears = [(e["pic"], e["creux"]) for e in obs["entrees"]]
    if bears != [(e["pic"], e["creux"]) for e in ref["entrees"]]:
        ecarts.append("bears du juge")
    if [e["f_entree"] for e in obs["entrees"]] != [e["f_entree"] for e in ref["entrees"]]:
        ecarts.append("f_entree par episode")
    return ecarts


# ----------------------------------------------------------------------------- tirages

def plage(j: jg.Juge, debut: pd.Timestamp, fin: pd.Timestamp | None) -> tuple[int, int]:
    """La periode mesuree de T1J en indices [m0, m1[ (clarification 2)."""
    fin = j.dates.max() if fin is None else min(pd.Timestamp(fin), j.dates.max())
    dom = ms.domaine(j, debut, fin)
    if dom is None:
        raise FiabiliteError("periode mesuree vide")
    return dom


def tirages(sig: pd.Series, j: jg.Juge, debut, fin, m0: int, m1: int, test: str) -> dict:
    """1 000 signaux aleatoires (graine 0) et leurs trois mesures, par les fonctions de T1J."""
    rng = np.random.default_rng(R.GRAINE)
    plein = sig.to_numpy(dtype=float)
    seg = plein[m0:m1]
    f, fa, juste = [], [], []
    for _ in range(R.N_TIRAGES):
        s = plein.copy()
        s[m0:m1] = (nulls.permuter_par_etat(seg, rng) if test == "permutation"
                    else nulls.decaler(seg, rng))
        m = ms.mesurer(pd.Series(s, index=sig.index), j, debut, fin)
        f.append(m["f_entree_mediane"])
        fa.append(m["fausses_alertes_an"])
        juste.append(m["justesse"])
    return {"f_entree_mediane": f, "fausses_alertes_an": fa, "justesse": juste}


def _q(x: list[float]) -> dict:
    a = np.asarray(x, dtype=float)
    return {"mediane": float(np.median(a)), "q05": float(np.quantile(a, 0.05)),
            "q95": float(np.quantile(a, 0.95))}


def resumer(obs: dict, nul: dict) -> dict:
    """p_latence (<=), p_justesse (>=), distributions et lectures D4."""
    f = np.asarray(nul["f_entree_mediane"], dtype=float)
    jt = np.asarray(nul["justesse"], dtype=float)
    p_lat = float(np.mean(f <= obs["f_entree_mediane"]))
    p_jus = float(np.mean(jt >= obs["justesse"]))
    return {"f_entree_observee": obs["f_entree_mediane"], "f_entree_aleatoire": _q(f),
            "p_latence": p_lat, "lecture_latence": d4.verdict(p_lat),
            "justesse_observee": obs["justesse"], "justesse_aleatoire": _q(jt),
            "p_justesse": p_jus, "lecture_justesse": d4.verdict(p_jus),
            "fausses_alertes_observees": obs["fausses_alertes_an"],
            "fausses_alertes_aleatoires": _q(nul["fausses_alertes_an"])}


def temoin(obs: dict[str, dict], nul: dict[str, dict]) -> tuple[dict, dict]:
    """Clarification 3 : moyenne S&P 500 / Nasdaq-100, tirage par tirage."""
    o = {k: (obs["SPX"][k] + obs["NDX"][k]) / 2
         for k in ("f_entree_mediane", "justesse", "fausses_alertes_an")}
    n = {k: list((np.asarray(nul["SPX"][k]) + np.asarray(nul["NDX"][k])) / 2)
         for k in ("f_entree_mediane", "justesse", "fausses_alertes_an")}
    return o, n


# ----------------------------------------------------------------------------- test 2

def diagnostic_f0(sig: pd.Series, j: jg.Juge, obs: dict) -> list[dict]:
    """Etat au pic de chaque bear (trois cas) et f_entree diagnostic (fenetre de 21 seances)."""
    s = sig.to_numpy(dtype=float)
    debut_run = np.full(len(s), -1)
    for a, b in ms.runs(s == det.BEAR):
        debut_run[a:b + 1] = a
    sortie = []
    for e in obs["entrees"]:
        a, c = j.dates.get_loc(pd.Timestamp(e["pic"])), j.dates.get_loc(pd.Timestamp(e["creux"]))
        if s[a] == det.BEAR:
            avant = int(a - debut_run[a])
            cas = "en bear avant le pic" if avant >= 1 else "bascule le jour du pic"
        else:
            avant, cas = None, "pas en bear au pic"
        k = next((i for i in range(a, c) if s[i] == det.BEAR
                  and debut_run[i] >= a - R.FENETRE_DIAGNOSTIC), None)
        f_diag = 1.0 if k is None else float((j.prix[a] - j.prix[k]) / (j.prix[a] - j.prix[c]))
        sortie.append({"pic": e["pic"], "creux": e["creux"], "cas": cas, "seances_avant": avant,
                       "f_entree": e["f_entree"], "f_diagnostic": f_diag,
                       "rate_diagnostic": k is None})
    return sortie


def resume_f0(episodes: list[dict]) -> dict:
    zeros = [e for e in episodes if e["f_entree"] == 0.0]
    cas = ("en bear avant le pic", "bascule le jour du pic", "pas en bear au pic")
    return {"n_bears": len(episodes), "n_f0": len(zeros),
            "parts_f0": {c: (sum(e["cas"] == c for e in zeros) / len(zeros)) if zeros else None
                         for c in cas},
            "f_entree_mediane": float(np.median([e["f_entree"] for e in episodes])),
            "f_diagnostic_mediane": float(np.median([e["f_diagnostic"] for e in episodes])),
            "rates_diagnostic": int(sum(e["rate_diagnostic"] for e in episodes))}


# ----------------------------------------------------------------------------- verdict

def verdict(test1: dict) -> dict:
    """Fiable : p_latence < 0,05 temoin ET or ; agitation : l'un >= 0,20 ; sinon non concluant."""
    sortie = {}
    for x in R.CANDIDATS:
        pt, po = test1[x]["TEMOIN"]["p_latence"], test1[x]["OR"]["p_latence"]
        if pt < R.SEUIL_FIABLE and po < R.SEUIL_FIABLE:
            v = "fiable"
        elif max(pt, po) >= R.SEUIL_AGITATION:
            v = "du a l'agitation"
        else:
            v = "non concluant"
        sortie[x] = {"p_temoin": pt, "p_or": po, "verdict": v,
                     "btc": {"p_latence": test1[x]["BTC"]["p_latence"],
                             "lecture": test1[x]["BTC"]["lecture_latence"]}}
    return sortie


# ----------------------------------------------------------------------------- campagne

def _code() -> str | None:
    r = _git("rev-parse", "--short", "HEAD")
    if r.returncode != 0:
        return None
    return r.stdout.decode().strip() or None


def _propre(x):
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
    from beta.temps1_fiabilite import rapport

    ecarts = verifier_modules()
    if ecarts:
        raise FiabiliteError(f"modules de T1J differents du commit {R.COMMIT_JUSTESSE} : "
                             f"{ecarts}")
    pre = verifier_gel()
    t1j = synthese_t1j()
    d = donnees_t1j(t1j)
    sortie_json = DOSSIER / f"campagne_{R.ID_EXP}_{d.empreinte}.json"
    if sortie_json.exists() and not recalculer:
        s = json.loads(sortie_json.read_text(encoding="utf-8"))
        rapport.ecrire(s)
        return s
    avant = {"global": experiences.compteur_total(),
             "invest": experiences.compteur(famille="invest"),
             "trading": experiences.compteur(famille="trading")}
    sigma_ref = jg.sigma_sp_ref(d.prix["SPX"])
    per = cj.periodes(d)
    obs, nul1, nul2, f0, plages = {}, {}, {}, {}, {}
    for actif in R.ACTIFS:
        j = jg.juger(d.prix[actif], sigma_ref)
        debut, fin = per["btc"] if actif == "BTC" else per["labo"]
        m0, m1 = plage(j, debut, fin)
        plages[actif] = {"debut": f"{j.dates[m0]:%Y-%m-%d}", "fin": f"{j.dates[m1]:%Y-%m-%d}",
                         "seances": int(m1 - m0)}
        for nom in R.DETECTEURS:
            sig = det.signal(d, nom, actif)
            o = ms.mesurer(sig, j, debut, fin)
            ecarts = verifier_observe(o, t1j["resultats"]["principal"][nom][actif])
            if ecarts:
                raise FiabiliteError(f"{nom} x {actif} : differe du rapport de T1J ({ecarts})")
            log.info("%s x %s : tirages (periode mesuree %s -> %s)", nom, actif,
                     plages[actif]["debut"], plages[actif]["fin"])
            obs.setdefault(nom, {})[actif] = o
            nul1.setdefault(nom, {})[actif] = tirages(sig, j, debut, fin, m0, m1, "permutation")
            nul2.setdefault(nom, {})[actif] = tirages(sig, j, debut, fin, m0, m1, "decalage")
            f0.setdefault(nom, {})[actif] = diagnostic_f0(sig, j, o)
    tests = {}
    for cle, nul in (("test_1", nul1), ("test_1_bis", nul2)):
        t = {}
        for nom in R.DETECTEURS:
            t[nom] = {a: resumer(obs[nom][a], nul[nom][a]) for a in R.ACTIFS}
            ot, nt = temoin(obs[nom], nul[nom])
            t[nom]["TEMOIN"] = resumer(ot, nt)
        tests[cle] = t
    apres = {"global": experiences.compteur_total(),
             "invest": experiences.compteur(famille="invest"),
             "trading": experiences.compteur(famille="trading")}
    s = _propre({
        "experience": R.ID_EXP, "code": _code(), "regles": R.empreinte(),
        "preenregistrement": empreinte_texte(), "modules_t1j": {"commit": R.COMMIT_JUSTESSE,
                                                                 "identiques": True},
        "calcule_le": datetime.now(UTC).isoformat(timespec="seconds"),
        "donnees": d.empreinte, "regles_t1j": RJ.empreinte(), "sigma_sp_ref": sigma_ref,
        "compteur": {"avant": avant, "apres": apres, "diagnostic": pre.get("diagnostic")},
        "plages": plages, "tests": tests, "verdict": verdict(tests["test_1"]),
        "test_2": {nom: {a: {"episodes": f0[nom][a], "resume": resume_f0(f0[nom][a])}
                         for a in R.ACTIFS} for nom in R.DETECTEURS},
        "tirages": {"test_1": nul1, "test_1_bis": nul2}})
    DOSSIER.mkdir(parents=True, exist_ok=True)
    sortie_json.write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    rapport.ecrire(s)
    issue = "; ".join(f"{x} : {v['verdict']}" for x, v in s["verdict"].items())
    cle = hashlib.sha256(sortie_json.read_bytes()).hexdigest()[:12]
    experiences.marquer_mesuree(R.ID_EXP, cle, f"diagnostic de T1J — {issue}")
    return s
