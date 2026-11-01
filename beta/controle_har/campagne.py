"""Controle HAR : la campagne, de bout en bout.

Ordre : gel verifie (regles, texte du preenregistrement, marque diagnostic) -> copies figees
verifiees (SHA-256) -> par actif : RV journaliere, ecart-type 30 jours sur les clotures de la barre
5 min de 23:55 (amendement du 01/11), HAR glissant, replis, epreuve de causalite, QLIKE sur les
jours evalues, Diebold-Mariano (information), controle des copies 1d (rapporte) -> regle 5 ->
rapport ecrit par le programme.
Aucun run n'est journalise : test de mesure sans essai, le compteur ne bouge pas.
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
from beta.controle_har import donnees as dn
from beta.controle_har import har as hr
from beta.controle_har import regles as R
from beta.protocole import experiences

log = logging.getLogger("beta.controle_har.campagne")

DOSSIER = config.DATA / "controle_har"
SORTIE = config.RACINE / "VC6_V1" / "controle_har"
TEXTE = SORTIE / "PREENREGISTREMENT.md"
SPEC = config.RACINE / "VC6_V1" / "spec_figee.md"


class ControleError(RuntimeError):
    """Une condition du prompt n'est pas remplie, ou un cas qu'il ne prevoit pas : arret."""


# ----------------------------------------------------------------------------- verifications

def empreinte_texte() -> str:
    return hashlib.sha256(TEXTE.read_bytes()).hexdigest()[:16]


def verifier_gel() -> dict:
    experiences.exiger(R.ID_EXP)
    lignes = [x for x in experiences._lignes() if x.get("id") == R.ID_EXP
              and x.get("statut") == "preenregistre"]
    if not lignes:
        raise ControleError(f"{R.ID_EXP} n'est pas journalisee "
                            "(scripts/preenregistrer_controle_har.py)")
    pre = lignes[-1]
    if pre.get("diagnostic") is not True:
        raise ControleError(f"{R.ID_EXP} n'est pas marquee diagnostic")
    if pre.get("empreinte") != R.empreinte():
        raise ControleError(f"regles changees depuis le gel : {pre.get('empreinte')} -> "
                            f"{R.empreinte()}")
    if pre.get("empreinte_preenregistrement") != empreinte_texte():
        raise ControleError(f"{TEXTE.name} change depuis le gel")
    return pre


def compteurs() -> dict:
    return {"global": experiences.compteur_total(),
            "invest": experiences.compteur(famille="invest"),
            "trading": experiences.compteur(famille="trading")}


# ----------------------------------------------------------------------------- un actif

def previsions(barres: pd.DataFrame) -> pd.DataFrame:
    """Jour par jour : RV, cible, prevision HAR brute et apres replis, ecart-type 30 jours."""
    rvj = hr.rv_journaliere(barres)
    rv = rvj["rv"]
    ecart = hr.ecart_type_30(dn.clotures_5m(barres)).reindex(rv.index)
    h = hr.har(rv)
    retenue, avant, negative = hr.replis(h["prevision"], h["jours_rv"], ecart)
    return pd.DataFrame({
        "rv": rv, "exclu": rvj["exclu"], "barres": rvj["barres"],
        "manquantes": rvj["manquantes"], "volume_nul": rvj["volume_nul"],
        "cible": hr.regresseurs(rv)["cible"], "har_brut": h["prevision"], "har": retenue,
        "ecart_type": ecart, "avant_730": avant, "negative": negative,
        "jours_rv": h["jours_rv"], "lignes": h["lignes"],
        **{f"b{k}": h[f"b{k}"] for k in range(4)}})


def causalite(barres: pd.DataFrame, plein: pd.DataFrame) -> list[str]:
    """Previsions recalculees avec les seules donnees <= chaque coupure = previsions completes."""
    echecs = []
    for coupure in map(pd.Timestamp, R.COUPURES_CAUSALITE):
        if not plein.index.min() <= coupure < plein.index.max():
            continue
        lendemain = (coupure + pd.Timedelta(days=1)).tz_localize("UTC")
        court = previsions(barres[barres.index < lendemain])
        ref = plein[plein.index <= coupure]
        for col in ("har_brut", "har", "ecart_type"):
            if not (court.index.equals(ref.index)
                    and np.array_equal(court[col].to_numpy(dtype=float),
                                       ref[col].to_numpy(dtype=float), equal_nan=True)):
                echecs.append(f"{coupure:%Y-%m-%d} : {col}")
    return echecs


def _jour(d) -> str | None:
    return None if d is None or pd.isna(d) else f"{pd.Timestamp(d):%Y-%m-%d}"


def mesurer_actif(barres: pd.DataFrame, close_1d: pd.Series) -> dict:
    p = previsions(barres)
    echecs = causalite(barres, p)
    if echecs:
        raise ControleError(f"epreuve de causalite ratee : {echecs}")
    eligibles = (p["jours_rv"] >= R.FENETRE_MCO) & p["cible"].notna()
    for col, quoi in (("har_brut", "prevision HAR"), ("ecart_type", "ecart-type 30 jours")):
        trous = p.index[eligibles & p[col].isna()]
        if len(trous):
            raise ControleError(f"jour evaluable sans {quoi} (cas non prevu par le prompt) : "
                                f"{[_jour(d) for d in trous[:5]]}")
    ev = p[eligibles]
    if ev.empty:
        raise ControleError("aucun jour evaluable (moins de 730 jours de RV)")
    q_har = hr.qlike(ev["cible"], ev["har"])
    q_ec = hr.qlike(ev["cible"], ev["ecart_type"])
    moy_har, moy_ec = float(q_har.mean()), float(q_ec.mean())
    debut_ev, fin_ev = ev.index.min(), ev.index.max()
    fin_cible = fin_ev + pd.Timedelta(days=R.HORIZON)
    periode = (p.index >= debut_ev) & (p.index <= fin_cible)
    estime = p["har_brut"].notna()
    dernier = p.index[estime][-1]
    return {
        "qlike": {"har": moy_har, "ecart_type": moy_ec},
        "diebold_mariano": hr.diebold_mariano((q_har - q_ec).to_numpy()),
        "sigma_retenu": hr.decision(moy_har, moy_ec),
        "jours_evalues": int(len(ev)),
        "jours_exclus": {"total": int(p["exclu"].sum()),
                         "dans_la_periode_evaluee": int(p["exclu"][periode].sum()),
                         "dates": [_jour(d) for d in p.index[p["exclu"]]],
                         "barres_presentes": [int(n) for n in p["barres"][p["exclu"]]]},
        "previsions_negatives_remplacees": {"jours_evalues": int(ev["negative"].sum()),
                                            "tous_jours_har": int(p["negative"].sum())},
        "periodes": {"premier_jour": _jour(p.index.min()), "dernier_jour": _jour(p.index.max()),
                     "jours_avec_rv": int(p["rv"].notna().sum()),
                     "har_des_le": _jour(p.index[estime][0]),
                     "jours_har_estime": int(estime.sum()),
                     "evaluation": [_jour(debut_ev), _jour(fin_ev)],
                     "derniere_cible": _jour(fin_cible)},
        "barres_volume_nul": {"total": int(p["volume_nul"].sum()),
                              "dans_la_periode_evaluee": int(p["volume_nul"][periode].sum())},
        "moyennes_periode_evaluee": {"cible": float(ev["cible"].mean()),
                                     "har": float(ev["har"].mean()),
                                     "ecart_type": float(ev["ecart_type"].mean())},
        "dernier_har": {"jour": _jour(dernier), "lignes": int(p.at[dernier, "lignes"]),
                        "coefficients": [float(p.at[dernier, f"b{k}"]) for k in range(4)]},
        "causalite": echecs,
        "controle_1d": dn.controle_clotures(barres, close_1d),
    }


# ----------------------------------------------------------------------------- campagne

def _code() -> str | None:
    r = subprocess.run(["git", "-C", str(config.RACINE), "rev-parse", "--short", "HEAD"],
                       capture_output=True, timeout=30)
    return (r.stdout.decode().strip() or None) if r.returncode == 0 else None


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


def lire() -> dict[str, tuple[pd.DataFrame, pd.Series]]:
    """Les copies figees (bougies 5 min, et 1d pour le controle), SHA-256 verifie."""
    return {a: (dn.bougies_5m(a), dn.clotures_1d(a)) for a in R.ACTIFS}


def lancer(recalculer: bool = False) -> dict:
    from beta.controle_har import rapport

    pre = verifier_gel()
    lus = lire()
    empreinte = dn.empreinte(lus)
    sortie_json = DOSSIER / f"campagne_{R.ID_EXP}_{empreinte}.json"
    if sortie_json.exists() and not recalculer:
        s = json.loads(sortie_json.read_text(encoding="utf-8"))
        rapport.ecrire(s)
        return s
    avant = compteurs()
    actifs = {}
    for actif, (barres, close_1d) in lus.items():
        log.info("%s : %d barres 5 min, %d clotures 1d", actif, len(barres), len(close_1d))
        actifs[actif] = {"couverture": dn.couverture(barres, close_1d),
                         **mesurer_actif(barres, close_1d)}
        log.info("%s : sigma retenu = %s", actif, actifs[actif]["sigma_retenu"])
    apres = compteurs()
    if apres != avant:
        raise ControleError(f"le compteur a bouge pendant un test de mesure : {avant} -> {apres}")
    s = _propre({
        "experience": R.ID_EXP, "code": _code(), "regles": R.empreinte(),
        "preenregistrement": empreinte_texte(),
        "calcule_le": datetime.now(UTC).isoformat(timespec="seconds"),
        "donnees": {"empreinte": empreinte, "fin": R.FIN, "sha256": R.SHA256,
                    "copies": R.ACTIFS},
        "compteur": {"avant": avant, "apres": apres, "diagnostic": pre.get("diagnostic")},
        "actifs": actifs})
    DOSSIER.mkdir(parents=True, exist_ok=True)
    sortie_json.write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    rapport.ecrire(s)
    issue = "; ".join(f"{a} : sigma = {v['sigma_retenu']}" for a, v in s["actifs"].items())
    cle = hashlib.sha256(sortie_json.read_bytes()).hexdigest()[:12]
    experiences.marquer_mesuree(R.ID_EXP, cle, f"Controle HAR — {issue}")
    return s
