"""Temps 1 — la campagne T1A : 7 detecteurs x 2 cibles, chacun mesure sur les deux periodes par
le moteur de TI1 tel quel, puis les trois portes et le verdict mecanique.

Branchement sans modification du moteur (DISCOVERY.md § 1) : `grille` pose les clotures de la
cible sur le calendrier CIVIL, comblees par la derniere valeur connue (rendement nul sans seance),
et `score_en_vigueur` donne a chaque jour de rendement le score decide a la cloture de la
derniere seance de la veille ou avant. Le moteur annualise sur 365 jours et ses captures veulent
des semaines de 7 jours : c'est sa convention, on la lui donne.

Compteur : un essai par couple (detecteur x cible) = 14, journalises AVANT le premier calcul
(prompt, regle 3) ; un run couvre les deux periodes. Rejouer ne compte rien de plus.
"""

from __future__ import annotations

import dataclasses
import functools
import hashlib
import json
import logging
import math
import subprocess
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from beta import config
from beta.invest import metriques, moteur, nulls
from beta.invest.moteur import Mapping
from beta.protocole import experiences
from beta.temps1 import detecteurs as det
from beta.temps1 import donnees as dn

log = logging.getLogger("beta.temps1.campagne")

ID_EXP = "T1A"
CIBLES = ("SPX", "NDX")
REFERENCE = "SMA200"
CANDIDATS = ("MOM126", "COUCHE1")
BANDE = ("SMA126", "SMA168", "SMA200", "SMA210", "SMA252")
LABO = ("1991-01-01", "2023-12-31")
DEBUT_INFORMATIVE = "2024-01-01"
SEUIL_PORTE_HASARD = 0.05
DOSSIER = config.DATA / "temps1"
METRIQUES_NULLS = {"ulcer": True, "mdd_abs": True, "prot": False, "calmar": False}
UN_JOUR = pd.Timedelta(days=1)


@dataclasses.dataclass(frozen=True)
class Config:
    detecteur: str
    cible: str
    labo: tuple[str, str] = LABO
    informative: tuple[str, str] = (DEBUT_INFORMATIVE, "")
    mapping: Mapping = Mapping("paliers")
    kappa_pb: float = 10.0
    theta_episode: float = 0.20
    theta_f: float = 0.10
    horizon_j: int = 60
    b: int = 1000
    graine: int = 0
    m_j: int = 90
    prechauffe_seances: int = dn.PRECHAUFFE_SEANCES

    def dict(self) -> dict:
        return json.loads(json.dumps(dataclasses.asdict(self)))

    def periodes(self) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
        return {"labo": tuple(pd.Timestamp(x) for x in self.labo),
                "informative": tuple(pd.Timestamp(x) for x in self.informative)}


def configs(fin_informative: pd.Timestamp, b: int = 1000) -> list[Config]:
    return [Config(detecteur=x, cible=c, labo=LABO,
                   informative=(DEBUT_INFORMATIVE, f"{fin_informative:%Y-%m-%d}"), b=b)
            for x in det.DETECTEURS for c in CIBLES]


def empreinte_config(cfg: Config) -> str:
    return hashlib.sha256(json.dumps(cfg.dict(), sort_keys=True).encode()).hexdigest()[:16]


def run_id(cfg: Config, empreinte_donnees: str) -> str:
    cle = json.dumps({"exp": ID_EXP, "config": cfg.dict(), "donnees": empreinte_donnees},
                     sort_keys=True)
    return hashlib.sha256(cle.encode()).hexdigest()[:12]


# =========================================================================================
# Adaptateur : seances -> calendrier civil du moteur TI1
# =========================================================================================

def grille(close: pd.Series, nom: str, debut: pd.Timestamp, fin: pd.Timestamp) -> pd.DataFrame:
    """Les clotures sur chaque jour civil de [debut - 1, fin], comblees par la derniere connue."""
    jours = pd.date_range(debut - UN_JOUR, fin, freq="D")
    s = close[close.index <= fin]
    c = s.reindex(s.index.union(jours)).ffill().reindex(jours)
    if c.isna().any():
        raise dn.DonneesError(f"{nom} : aucune cloture avant le {debut - UN_JOUR:%Y-%m-%d}")
    return c.to_frame(nom)


def score_en_vigueur(score_seances: pd.Series, jours: pd.DatetimeIndex) -> pd.Series:
    """Le score qui joue le jour i : celui de la derniere seance <= i - 1 (NaN compris : un NaN
    de prechauffe n'est jamais masque par un comblement)."""
    seances = score_seances.index.as_unit("ns").asi8
    veille = (jours - UN_JOUR).as_unit("ns").asi8
    rang = np.searchsorted(seances, veille, side="right") - 1
    x = score_seances.to_numpy(dtype=float)
    return pd.Series(np.where(rang >= 0, x[np.maximum(rang, 0)], np.nan), index=jours)


# =========================================================================================
# Evaluation d'une periode (pure), calquee sur `invest.campagne.evaluer`, sans BTC ni funding
# =========================================================================================

def _avec_protection(r, e, v_b, eps, cfg: Config) -> dict:
    std = metriques.standard(r, e=e)
    s = metriques.survie(v_b, metriques.courbe(r), e, eps, cfg.mapping, cfg.theta_f,
                         cfg.horizon_j)
    return {**std, "protection": s["protection"]}


def _nulls(cfg: Config, periode: str, s: np.ndarray, p: moteur.Panier, eps: list,
           r_obs: np.ndarray) -> dict:
    def evaluer_null(s_null: np.ndarray) -> dict:
        r = moteur.rendement(moteur.exposition(s_null, cfg.mapping), p.r, cfg.kappa_pb)["r"]
        return metriques.pour_nulls(r, p.v, eps)

    observe = metriques.pour_nulls(r_obs, p.v, eps)
    generateurs = {"circulaire": functools.partial(nulls.decalage_circulaire, m=cfg.m_j),
                   "segments": nulls.melange_segments}
    sortie = {"b": cfg.b, "graine": cfg.graine, "m_j": cfg.m_j, "observe": observe, "p": {}}
    for nom, gen in generateurs.items():
        rng = nulls.flux(cfg.graine, nom, f"{cfg.detecteur}:{cfg.cible}", periode)
        dist = nulls.distribution_nulle(s, evaluer_null, cfg.b, rng, gen)
        sortie[nom] = {k: v.tolist() for k, v in dist.items()}
        sortie["p"][nom] = {m: nulls.p_value(dist[m], observe[m], plus_petit)
                            for m, plus_petit in METRIQUES_NULLS.items()}
    sortie["p_retenue"] = nulls.p_retenue(sortie["p"]["circulaire"]["ulcer"],
                                          sortie["p"]["segments"]["ulcer"])
    sortie["verdict"] = nulls.verdict(sortie["p_retenue"])
    return sortie


def evaluer_periode(cfg: Config, d: dn.Donnees, periode: str, debut: pd.Timestamp,
                    fin: pd.Timestamp) -> dict:
    # Prechauffe : 252 seances de chaque serie lue avant la premiere decision (au moins ce que
    # le detecteur regarde en arriere).
    besoin = {(cfg.cible if k == "cible" else k): max(n, cfg.prechauffe_seances)
              for k, n in det.BESOIN[cfg.detecteur].items()}
    dn.controler_prechauffe(d, cfg.cible, debut, {cfg.cible: cfg.prechauffe_seances, **besoin})
    decisions = dn.seances(d, cfg.cible, debut, fin)
    score_seances = det.score(cfg.detecteur, d, cfg.cible, decisions)
    closes = grille(d.closes[cfg.cible], cfg.cible, debut, fin)
    p = moteur.panier(closes, {cfg.cible: 1.0}, debut, fin)
    s = moteur.aligner(score_en_vigueur(score_seances, p.jours), p.jours)
    e = moteur.exposition(s, cfg.mapping)
    out = moteur.rendement(e, p.r, cfg.kappa_pb)
    v_s = metriques.courbe(out["r"])
    eps = metriques.episodes(p.v, cfg.theta_episode)
    surv = metriques.survie(p.v, v_s, e, eps, cfg.mapping, cfg.theta_f, cfg.horizon_j)
    temoin = moteur.temoin_constant(e, p.r, cfg.kappa_pb)
    n = len(p.jours)
    dates = [f"{debut - UN_JOUR:%Y-%m-%d}"] + [f"{j:%Y-%m-%d}" for j in p.jours]
    for ep in surv["episodes"]:
        for cle in ("pic", "creux", "fin"):
            ep[f"date_{cle}"] = None if ep[cle] is None else dates[ep[cle]]
    for f in surv["faux_signaux"]["detail"]:
        f["date"] = dates[f["k"]]
    niveaux = {f"{x:g}": float(np.mean(np.isclose(e, x)))
               for x in (cfg.mapping.e_haut, cfg.mapping.e_neutre, cfg.mapping.e_def)}
    res = {
        "periode": {"nom": periode, "debut": f"{debut:%Y-%m-%d}", "fin": f"{fin:%Y-%m-%d}",
                    "n_jours": n, "n_seances_decision": int(len(decisions)),
                    "n_episodes": len(eps), "puissance_faible": len(eps) < 3,
                    "part_par_exposition": niveaux,
                    "trous_combles": dn.trous_combles(d, cfg.cible, debut, fin)},
        "metriques": {
            "strategie": {**metriques.standard(out["r"], e=e),
                          "protection": surv["protection"], "turnover": out["turnover"],
                          "couts": float(out["cout"].sum())},
            "buy_and_hold": _avec_protection(p.r, np.ones(n), p.v, eps, cfg),
            "temoin": _avec_protection(temoin["r"], np.full(n, temoin["e"]), p.v, eps, cfg),
        },
        "survie": {**surv, "captures": metriques.captures(out["r"], p.r, p.jours)},
        "series": {"dates": dates, "v_s": v_s, "v_b": p.v, "e": e, "score": s},
        "nulls": None, "verdict": None,
    }
    if cfg.b > 0:
        res["nulls"] = _nulls(cfg, periode, s, p, eps, out["r"])
        res["verdict"] = res["nulls"]["verdict"]
    return res


def _propre(x):
    """JSON strict et stable : numpy -> Python, NaN/inf -> None, flottants a 10 decimales."""
    if isinstance(x, dict):
        return {k: _propre(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, np.ndarray)):
        return [_propre(v) for v in x]
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return None if not math.isfinite(float(x)) else round(float(x), 10)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def evaluer(cfg: Config, d: dn.Donnees) -> dict:
    """Un couple (detecteur x cible) sur ses deux periodes."""
    return _propre({"experience": ID_EXP, "detecteur": cfg.detecteur, "cible": cfg.cible,
                    "config": cfg.dict(),
                    "donnees": {"empreinte": d.empreinte, "pit_dexjpus": d.pit_dexjpus,
                                "fin": f"{d.fin:%Y-%m-%d}"},
                    "periodes": {nom: evaluer_periode(cfg, d, nom, debut, fin)
                                 for nom, (debut, fin) in cfg.periodes().items()}})


# =========================================================================================
# Les trois portes (labo seulement) et le verdict mecanique
# =========================================================================================

def ligne(res: dict, periode: str) -> dict:
    p = res["periodes"][periode]
    m, t = p["metriques"]["strategie"], p["metriques"]["temoin"]
    nul = p["nulls"] or {"p": {}, "p_retenue": None}
    return {"detecteur": res["detecteur"], "cible": res["cible"], "periode": periode,
            "ulcer": m["ulcer"], "ulcer_temoin": t["ulcer"], "mdd": m["mdd"],
            "cagr": m["cagr"], "expo_moyenne": m["expo_moyenne"],
            "changements": m["changements_expo"], "protection": m["protection"],
            "p_circulaire": nul["p"].get("circulaire", {}).get("ulcer"),
            "p_segments": nul["p"].get("segments", {}).get("ulcer"),
            "p_retenue": nul["p_retenue"], "verdict_nulls": p["verdict"]}


def portes(lignes_labo: list[dict]) -> list[dict]:
    """Porte 1 : p retenue < 0,05 (D4). Porte 2 : Ulcer < Ulcer du temoin. Porte 3 : Ulcer <
    Ulcer de SMA200 (meme cible). Portes 1-2 : SMA200 et candidats ; porte 3 : candidats ;
    fenetres de la bande : aucune (« n/a », regle 2 : pas de choix de fenetre)."""
    ref = {x["cible"]: x["ulcer"] for x in lignes_labo if x["detecteur"] == REFERENCE}
    sortie = []
    for x in lignes_labo:
        juge = x["detecteur"] in (REFERENCE, *CANDIDATS)
        p1 = (x["p_retenue"] is not None and x["p_retenue"] < SEUIL_PORTE_HASARD) if juge \
            else None
        p2 = (x["ulcer"] < x["ulcer_temoin"]) if juge else None
        p3 = (x["ulcer"] < ref[x["cible"]]) if x["detecteur"] in CANDIDATS else None
        sortie.append({**x, "ulcer_sma200": ref[x["cible"]], "porte1": p1, "porte2": p2,
                       "porte3": p3})
    return sortie


def verdict(lignes_portes: list[dict]) -> dict:
    """Mecanique : candidat(s) retenu(s) si 3 portes sur les 2 cibles ; sinon SMA200 retenue si
    portes 1 et 2 sur les 2 cibles ; sinon aucun timing demontre."""
    def passe(nom: str, cles: tuple[str, ...]) -> bool:
        lot = [x for x in lignes_portes if x["detecteur"] == nom]
        return len(lot) == len(CIBLES) and all(x[c] is True for x in lot for c in cles)

    retenus = [c for c in CANDIDATS if passe(c, ("porte1", "porte2", "porte3"))]
    if retenus:
        return {"verdict": "candidat retenu", "retenus": retenus,
                "sma200_portes_1_2": passe(REFERENCE, ("porte1", "porte2"))}
    if passe(REFERENCE, ("porte1", "porte2")):
        return {"verdict": "SMA200 retenue", "retenus": [REFERENCE],
                "sma200_portes_1_2": True}
    return {"verdict": "aucun timing demontre", "retenus": [], "sma200_portes_1_2": False}


# =========================================================================================
# Mesure : verrou, compteur (avant le premier calcul), ecriture
# =========================================================================================

def _code() -> str | None:
    try:
        return subprocess.run(["git", "-C", str(config.RACINE), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def journaliser(cfgs: list[Config], empreinte_donnees: str) -> dict[str, Config]:
    """Les 14 essais au compteur, AVANT tout calcul. Un run deja journalise ne recompte pas."""
    deja = {x.get("run_id") for x in experiences.runs_journalises()}
    rids = {}
    for cfg in cfgs:
        rid = run_id(cfg, empreinte_donnees)
        rids[rid] = cfg
        if rid not in deja:
            experiences.enregistrer_run(rid, ID_EXP, f"temps1:{cfg.detecteur}:{cfg.cible}",
                                        empreinte_config(cfg), issue="lance (labo + informative)")
    return rids


def lancer_campagne(d: dn.Donnees, b: int = 1000, recalculer: bool = False) -> dict:
    """La campagne preenregistree. Compteur note avant / apres la journalisation des 14 essais."""
    experiences.exiger(ID_EXP)
    # La ligne de preenregistrement elle-meme (l'etat fusionne prend le N de la derniere ligne).
    pre = [x for x in experiences._lignes() if x.get("id") == ID_EXP
           and x.get("statut") == "preenregistre"][-1]
    cfgs = configs(d.fin, b)
    compteur_avant = experiences.compteur()
    rids = journaliser(cfgs, d.empreinte)
    compteur_apres = experiences.compteur()
    log.info("compteur d'essais : %d -> %d (%d couples)", compteur_avant, compteur_apres,
             len(rids))
    DOSSIER.mkdir(parents=True, exist_ok=True)
    resultats, calcules = {}, 0
    for rid, cfg in rids.items():
        chemin = DOSSIER / f"{rid}.json"
        if chemin.exists() and not recalculer:
            resultats[rid] = json.loads(chemin.read_text(encoding="utf-8"))
            continue
        log.info("mesure %s x %s", cfg.detecteur, cfg.cible)
        res = {**evaluer(cfg, d), "run_id": rid, "code": _code(),
               "calcule_le": datetime.now(UTC).isoformat(timespec="seconds")}
        chemin.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
        resultats[rid] = res
        calcules += 1
    labo = portes([ligne(r, "labo") for r in resultats.values()])
    info = [ligne(r, "informative") for r in resultats.values()]
    v = verdict(labo)
    synthese = _propre({
        "experience": ID_EXP, "runs": list(resultats), "code": _code(),
        "calcule_le": datetime.now(UTC).isoformat(timespec="seconds"),
        "compteur": {"avant_t1a": (pre.get("compteur") or {}).get("avant"),
                     "apres_preenregistrement": pre.get("n_essais_cumules"),
                     "avant_journalisation": compteur_avant, "apres": compteur_apres},
        "donnees": {"empreinte": d.empreinte, "pit_dexjpus": d.pit_dexjpus,
                    "fin": f"{d.fin:%Y-%m-%d}", "couverture": d.couverture},
        "labo": labo, "informative": info, "verdict": v})
    (DOSSIER / f"campagne_{ID_EXP}.json").write_text(json.dumps(synthese, ensure_ascii=False),
                                                     encoding="utf-8")
    if calcules:                                    # un rejeu sans calcul n'ecrit rien
        cle = hashlib.sha256("|".join(sorted(resultats)).encode()).hexdigest()[:12]
        experiences.marquer_mesuree(ID_EXP, cle, f"campagne (14 couples) — {v['verdict']}"
                                    + (f" : {', '.join(v['retenus'])}" if v["retenus"] else ""))
    return synthese
