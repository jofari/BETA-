"""T1C : la campagne du complement ETH et SOL, de bout en bout.

Ordre : modules de T1J (8afdbe7) et de T1F (590688e) verifies identiques -> gel verifie (regles,
texte du preenregistrement, marque diagnostic) -> sigma_SP_ref de T1J verifie -> copies figees
verifiees (SHA-256) -> par actif : epreuve de causalite, juge, mesures observees, tests 1 et 1 bis
(1 000 tirages, graine 0), test 2 -> decision mecanique -> rapport ecrit par le programme.
Aucun run n'est journalise : T1C est un diagnostic, le compteur ne bouge pas.
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
from beta.temps1_complement import donnees as dc
from beta.temps1_complement import regles as R
from beta.temps1_fiabilite import campagne as cf
from beta.temps1_fiabilite import regles as RF
from beta.temps1_justesse import campagne as cj
from beta.temps1_justesse import detecteurs as det
from beta.temps1_justesse import juge as jg
from beta.temps1_justesse import mesures as ms
from beta.temps1_justesse import regles as RJ

log = logging.getLogger("beta.temps1_complement.campagne")

DOSSIER = config.DATA / "temps1_complement"
SORTIE = config.RACINE / "VC6_V1" / "temps1_complement_eth_sol"
TEXTE = SORTIE / "PREENREGISTREMENT.md"
RETENU, SINON, INDECIDABLE = "retenu", "suit la SMA 200 du BTC", "indecidable"


class ComplementError(RuntimeError):
    """Une condition du prompt n'est pas remplie : arret, aucun chiffre."""


# ----------------------------------------------------------------------------- verifications

def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(config.RACINE), *args], capture_output=True,
                          timeout=30)


def verifier_modules() -> list[str]:
    """Les modules de T1J et de T1F reutilises : ceux de leurs commits, octet pour octet."""
    ecarts = []
    for paquet, commit, modules in (("temps1_justesse", R.COMMIT_JUSTESSE, R.MODULES_JUSTESSE),
                                    ("temps1_fiabilite", R.COMMIT_FIABILITE,
                                     R.MODULES_FIABILITE)):
        for nom in modules:
            chemin = f"beta/{paquet}/{nom}"
            ref = _git("show", f"{commit}:{chemin}")
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
        raise ComplementError(f"{R.ID_EXP} n'est pas journalisee (scripts/preenregistrer_t1c.py)")
    pre = lignes[-1]
    if pre.get("diagnostic") is not True:
        raise ComplementError(f"{R.ID_EXP} n'est pas marquee diagnostic")
    if pre.get("empreinte") != R.empreinte():
        raise ComplementError(f"regles changees depuis le gel : {pre.get('empreinte')} -> "
                              f"{R.empreinte()}")
    if pre.get("empreinte_preenregistrement") != empreinte_texte():
        raise ComplementError(f"{TEXTE.name} change depuis le gel")
    if RJ.empreinte() != R.EMPREINTE_REGLES_T1J:
        raise ComplementError("regles de T1J changees depuis sa mesure")
    if RF.empreinte() != R.EMPREINTE_REGLES_T1F:
        raise ComplementError("regles de T1F changees depuis sa mesure")
    return pre


def compteurs() -> dict:
    return {"global": experiences.compteur_total(),
            "invest": experiences.compteur(famille="invest"),
            "trading": experiences.compteur(famille="trading")}


# ----------------------------------------------------------------------------- un actif

def causalite(close: pd.Series) -> list[str]:
    """SMA 200 avec les seules clotures connues a chaque coupure de T1J = signal complet[: t]."""
    plein = det.sma(close, R.FENETRE_SMA)
    echecs = []
    for coupure in map(pd.Timestamp, cj.COUPURES_CAUSALITE):
        connu = close[close.index <= coupure]
        if connu.empty:
            continue
        court = det.sma(connu, R.FENETRE_SMA)
        ref = plein[plein.index <= coupure]
        if not (court.index.equals(ref.index)
                and np.array_equal(court.to_numpy(), ref.to_numpy(), equal_nan=True)):
            echecs.append(f"{coupure:%Y-%m-%d}")
    return echecs


def resume_juge(j: jg.Juge, m0: int | None, m1: int | None) -> dict:
    """Bears complets du juge (dans M ou non), bear en cours, plage des theta jugee."""
    bears = []
    for a, b in j.bears():
        bears.append({"pic": f"{j.dates[a]:%Y-%m-%d}", "creux": f"{j.dates[b]:%Y-%m-%d}",
                      "baisse": float(j.prix[b] / j.prix[a] - 1.0),
                      "dans_m": m0 is not None and m0 <= a and b <= m1})
    en_cours = None
    if j.pivots and j.pivots[-1][1] == jg.PIC:
        i = j.pivots[-1][0]
        en_cours = {"pic": f"{j.dates[i]:%Y-%m-%d}",
                    "baisse_a_ce_jour": float(j.prix[-1] / j.prix[i] - 1.0)}
    dernier = j.pivots[-1] if j.pivots else None
    juge = slice(j.debut, None)
    return {"debut_juge": j.infos["debut"], "bears": bears, "bear_en_cours": en_cours,
            "dernier_pivot": None if dernier is None else
            {"date": f"{j.dates[dernier[0]]:%Y-%m-%d}", "type": dernier[1]},
            "theta_baisse": [float(np.nanmin(j.theta_baisse[juge])),
                             float(np.nanmax(j.theta_baisse[juge]))],
            "theta_hausse": [float(np.nanmin(j.theta_hausse[juge])),
                             float(np.nanmax(j.theta_hausse[juge]))]}


def decision(p_justesse: float | None) -> str:
    """Regle 7 : retenu si p_justesse (test 1) < 0,05 ; sinon la SMA 200 du BTC."""
    if p_justesse is None:
        return INDECIDABLE
    return RETENU if p_justesse < R.SEUIL_P_JUSTESSE else SINON


def mesurer_actif(close: pd.Series, sigma_ref: float) -> dict:
    """Juge, mesures observees, tests 1 et 1 bis, test 2 et decision d'un actif."""
    echecs = causalite(close)
    if echecs:
        return {"statut": INDECIDABLE, "raison": f"epreuve de causalite ratee : {echecs}",
                "causalite": echecs}
    j = jg.juger(close, sigma_ref)
    debut = jg.premier_trimestre(close)
    sig = det.sma(close, R.FENETRE_SMA)
    dom = ms.domaine(j, debut, j.dates.max())
    base = {"causalite": [], "juge": resume_juge(j, *(dom or (None, None)))}
    try:
        obs = ms.mesurer(sig, j, debut, None)
        m0, m1 = cf.plage(j, debut, None)
    except (ms.MesureError, cf.FiabiliteError) as exc:
        return {**base, "statut": INDECIDABLE, "raison": str(exc)}
    manquantes = [k for k in ("f_entree_mediane", "justesse", "fausses_alertes_an")
                  if obs.get(k) is None]
    if manquantes:
        return {**base, "statut": INDECIDABLE, "observe": obs,
                "raison": f"mesure impossible : {', '.join(manquantes)} indefini(e)"}
    nul1 = cf.tirages(sig, j, debut, None, m0, m1, "permutation")
    nul2 = cf.tirages(sig, j, debut, None, m0, m1, "decalage")
    t1, t1b = cf.resumer(obs, nul1), cf.resumer(obs, nul2)
    episodes = cf.diagnostic_f0(sig, j, obs)
    return {**base, "statut": decision(t1["p_justesse"]), "observe": obs,
            "plage": {"debut": f"{j.dates[m0]:%Y-%m-%d}", "fin": f"{j.dates[m1]:%Y-%m-%d}",
                      "seances": int(m1 - m0)},
            "test_1": t1, "test_1_bis": t1b,
            "test_2": {"episodes": episodes, "resume": cf.resume_f0(episodes)},
            "tirages": {"test_1": nul1, "test_1_bis": nul2}}


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
    from beta.temps1_complement import rapport

    ecarts = verifier_modules()
    if ecarts:
        raise ComplementError(f"modules du Temps 1 differents de leurs commits : {ecarts}")
    pre = verifier_gel()
    sigma_ref = dc.sigma_sp_ref()
    closes = {a: dc.close(a) for a in R.ACTIFS}
    empreinte = dc.empreinte(closes)
    sortie_json = DOSSIER / f"campagne_{R.ID_EXP}_{empreinte}.json"
    if sortie_json.exists() and not recalculer:
        s = json.loads(sortie_json.read_text(encoding="utf-8"))
        rapport.ecrire(s)
        return s
    avant = compteurs()
    actifs = {}
    for actif, close in closes.items():
        log.info("%s : %d clotures du %s au %s", actif, len(close), f"{close.index.min():%Y-%m-%d}",
                 f"{close.index.max():%Y-%m-%d}")
        actifs[actif] = {"couverture": dc.couverture(close), **mesurer_actif(close, sigma_ref)}
        log.info("%s : %s", actif, actifs[actif]["statut"])
    apres = compteurs()
    if apres != avant:
        raise ComplementError(f"le compteur a bouge pendant un diagnostic : {avant} -> {apres}")
    s = _propre({
        "experience": R.ID_EXP, "code": _code(), "regles": R.empreinte(),
        "preenregistrement": empreinte_texte(),
        "modules": {"t1j": R.COMMIT_JUSTESSE, "t1f": R.COMMIT_FIABILITE, "identiques": True},
        "calcule_le": datetime.now(UTC).isoformat(timespec="seconds"),
        "donnees": {"empreinte": empreinte, "fin": R.FIN,
                    "copies": {a: {"copie": R.ACTIFS[a]["copie"], "sha256": R.ACTIFS[a]["sha256"],
                                   "serie": R.ACTIFS[a]["serie"]} for a in R.ACTIFS}},
        "sigma_sp_ref": sigma_ref, "regles_t1j": RJ.empreinte(), "regles_t1f": RF.empreinte(),
        "tirages_par_test": RF.N_TIRAGES, "graine": RF.GRAINE,
        "compteur": {"avant": avant, "apres": apres, "diagnostic": pre.get("diagnostic")},
        "actifs": actifs})
    DOSSIER.mkdir(parents=True, exist_ok=True)
    sortie_json.write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    rapport.ecrire(s)
    issue = "; ".join(f"{a} : {v['statut']}" for a, v in s["actifs"].items())
    cle = hashlib.sha256(sortie_json.read_bytes()).hexdigest()[:12]
    experiences.marquer_mesuree(R.ID_EXP, cle, f"complement ETH et SOL — {issue}")
    return s
