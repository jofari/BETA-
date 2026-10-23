"""Test invest — campagne TI1 : une config -> une mesure complete, comptee une fois (C6).

Une config = periode x votes actifs x mapping x parametres. `evaluer` est pure (donnees ->
resultat JSON) ; `mesurer` y ajoute le verrou (TI1 preenregistree), le compteur
(`enregistrer_run`, une fois par run_id : rejouer ne compte rien de plus), le DSR au N du
compteur et l'ecriture dans `data/test_invest/` (jetable : tout se recalcule a l'identique).
La campagne preenregistree : 12 configs par periode, 24 mesures (`campagne_ti1`).
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
from beta.invest import analyse, metriques, moteur, nulls
from beta.invest import donnees as dn
from beta.invest.moteur import Mapping
from beta.protocole import experiences
from beta.stats import multitest

log = logging.getLogger("beta.invest.campagne")

ID_EXP = "TI1"
FIN = "2026-10-19"
PERIODES = {"principale": ("2024-01-11", FIN), "stress": ("2020-09-15", FIN)}
POIDS = tuple((p, 1 / 6) for p in ("BTC", "ETH", "SOL", "BNB", "XRP", "LINK"))
DOSSIER = config.DATA / "test_invest"
METRIQUES_NULLS = {"ulcer": True, "mdd_abs": True, "prot": False, "calmar": False}


@dataclasses.dataclass(frozen=True)
class Config:
    periode: str = "principale"
    debut: str = PERIODES["principale"][0]
    fin: str = FIN
    indicateurs: tuple[str, ...] = dn.VOTES
    mapping: Mapping = Mapping("socle")
    kappa_pb: float = 10.0
    theta_episode: float = 0.20
    theta_f: float = 0.10
    horizon_j: int = 60
    b: int = 1000
    graine: int = 0
    m_j: int = 90
    pit: str = "publication"
    rf: bool = False
    poids: tuple[tuple[str, float], ...] = POIDS
    nulls: bool = True

    def dict(self) -> dict:
        return json.loads(json.dumps(dataclasses.asdict(self)))


def pour_periode(periode: str, **k) -> Config:
    debut, fin = PERIODES[periode]
    return Config(periode=periode, debut=debut, fin=fin, **k)


def campagne_ti1(b: int = 1000, periodes: dict | None = None) -> list[Config]:
    """Par periode : socle (socle, nulls), socle (paliers), 5 votes seuls (paliers, nulls),
    5 ablations (socle) — 24 mesures, celles du preenregistrement."""
    cfgs = []
    for periode, (debut, fin) in (periodes or PERIODES).items():
        def cfg(periode=periode, debut=debut, fin=fin, **k):
            return Config(periode=periode, debut=debut, fin=fin, b=b, **k)
        cfgs.append(cfg(mapping=Mapping("socle")))
        cfgs.append(cfg(mapping=Mapping("paliers"), nulls=False))
        cfgs += [cfg(indicateurs=(v,), mapping=Mapping("paliers")) for v in dn.VOTES]
        cfgs += [cfg(indicateurs=tuple(x for x in dn.VOTES if x != v), mapping=Mapping("socle"),
                     nulls=False) for v in dn.VOTES]
    return cfgs


def signal(cfg: Config) -> str:
    actifs = set(cfg.indicateurs)
    if actifs == set(dn.VOTES):
        return "complet"
    if len(actifs) == 1:
        return cfg.indicateurs[0]
    if len(actifs) == len(dn.VOTES) - 1:
        return "sans_" + next(v for v in dn.VOTES if v not in actifs)
    return "+".join(v for v in dn.VOTES if v in actifs)


def libelle(cfg: Config) -> str:
    s = signal(cfg)
    nom = ("socle complet" if s == "complet" else s.replace("sans_", "sans ") if
           s.startswith("sans_") else f"{s} seul" if s in dn.VOTES else s)
    return f"{nom} · {cfg.mapping.nom}"


def empreinte_config(cfg: Config) -> str:
    return hashlib.sha256(json.dumps(cfg.dict(), sort_keys=True).encode()).hexdigest()[:16]


def run_id(cfg: Config, empreinte_donnees: str) -> str:
    cle = json.dumps({"exp": ID_EXP, "config": cfg.dict(), "donnees": empreinte_donnees},
                     sort_keys=True)
    return hashlib.sha256(cle.encode()).hexdigest()[:12]


# =========================================================================================
# Evaluation (pure)
# =========================================================================================

def _propre(x):
    """JSON strict et stable : numpy -> Python, NaN/inf -> None, flottants a 10 decimales."""
    if isinstance(x, dict):
        return {k: _propre(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, np.ndarray)):
        return [_propre(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return None if not math.isfinite(float(x)) else round(float(x), 10)
    return x


def _avec_protection(r, e, v_b, eps, cfg, n_essais=None, rf=None) -> dict:
    std = metriques.standard(r, e=e, rf=rf, n_essais=n_essais)
    s = metriques.survie(v_b, metriques.courbe(r), e, eps, cfg.mapping, cfg.theta_f,
                         cfg.horizon_j)
    return {**std, "protection": s["protection"]}


def _etats(score: np.ndarray, m: Mapping) -> np.ndarray:
    s = np.round(score, 12)
    return np.where(s >= m.theta_h, 1, np.where(s <= -m.theta_b, -1, 0))


def evaluer(cfg: Config, d: dn.Donnees) -> dict:
    """Toutes les metriques A4 + B, le temoin, les benchmarks, et les nulls (D) si demandes."""
    debut, fin = pd.Timestamp(cfg.debut, tz="UTC"), pd.Timestamp(cfg.fin, tz="UTC")
    p = moteur.panier(d.closes, dict(cfg.poids), debut, fin)
    n = len(p.jours)
    s = moteur.aligner(moteur.score_normalise(d.votes, cfg.indicateurs), p.jours)
    e = moteur.exposition(s, cfg.mapping)
    phi = moteur.funding_panier(p, d.funding) if cfg.mapping.e_haut > 1 else None
    rf = moteur.rf_quotidien(d.dff, p.jours) if cfg.rf else None
    out = moteur.rendement(e, p.r, cfg.kappa_pb, phi, rf)
    v_s = metriques.courbe(out["r"])
    v_btc = moteur.hold(d.closes, "BTC", debut, fin)
    r_btc = v_btc[1:] / v_btc[:-1] - 1.0
    eps = metriques.episodes(p.v, cfg.theta_episode)
    surv = metriques.survie(p.v, v_s, e, eps, cfg.mapping, cfg.theta_f, cfg.horizon_j)
    temoin = moteur.temoin_constant(e, p.r, cfg.kappa_pb)
    un = np.ones(n)
    dates = [f"{debut - moteur.UN_JOUR:%Y-%m-%d}"] + [f"{j:%Y-%m-%d}" for j in p.jours]
    for ep in surv["episodes"]:
        for cle in ("pic", "creux", "fin"):
            ep[f"date_{cle}"] = None if ep[cle] is None else dates[ep[cle]]
    for f in surv["faux_signaux"]["detail"]:
        f["date"] = dates[f["k"]]
    etats = _etats(s, cfg.mapping)
    res = {
        "experience": ID_EXP, "libelle": libelle(cfg), "signal": signal(cfg),
        "config": cfg.dict(),
        "donnees": {"empreinte": d.empreinte, "pit": d.pit, "fin": f"{d.fin:%Y-%m-%d}",
                    "trous_acceptes": d.trous_acceptes},
        "periode": {"nom": cfg.periode, "debut": cfg.debut, "fin": cfg.fin, "n_jours": n,
                    "n_episodes": len(eps), "puissance_faible": len(eps) < 3,
                    "changements_regime": int((np.diff(etats) != 0).sum())},
        "metriques": {
            "strategie": {**metriques.standard(out["r"], e=e, rf=rf),
                          "protection": surv["protection"], "turnover": out["turnover"],
                          "couts": float(out["cout"].sum())},
            "panier": _avec_protection(p.r, un, p.v, eps, cfg),
            "btc": _avec_protection(r_btc, un, p.v, eps, cfg),
            "temoin": _avec_protection(temoin["r"], np.full(n, temoin["e"]), p.v, eps, cfg),
        },
        "survie": {**surv, "captures": metriques.captures(out["r"], p.r, p.jours)},
        "series": {"dates": dates, "v_s": v_s, "v_b": p.v, "v_btc": v_btc,
                   "dd_s": metriques.drawdown(v_s), "dd_b": metriques.drawdown(p.v), "e": e,
                   "score": s},
        "nulls": None, "verdict": None,
    }
    if cfg.nulls and cfg.b > 0:
        res["nulls"] = _nulls(cfg, s, p, eps, phi, rf, out["r"])
        res["verdict"] = res["nulls"]["verdict"]
    return _propre(res)


def _nulls(cfg: Config, s: np.ndarray, p: moteur.Panier, eps: list, phi, rf, r_obs) -> dict:
    def evaluer_null(s_null: np.ndarray) -> dict:
        r = moteur.rendement(moteur.exposition(s_null, cfg.mapping), p.r, cfg.kappa_pb, phi,
                             rf)["r"]
        return metriques.pour_nulls(r, p.v, eps)

    observe = metriques.pour_nulls(r_obs, p.v, eps)
    generateurs = {"circulaire": functools.partial(nulls.decalage_circulaire, m=cfg.m_j),
                   "segments": nulls.melange_segments}
    sortie = {"b": cfg.b, "graine": cfg.graine, "m_j": cfg.m_j, "observe": observe, "p": {}}
    for nom, gen in generateurs.items():
        dist = nulls.distribution_nulle(s, evaluer_null, cfg.b,
                                        nulls.flux(cfg.graine, nom, signal(cfg), cfg.periode),
                                        gen)
        sortie[nom] = dist
        sortie["p"][nom] = {m: nulls.p_value(dist[m], observe[m], plus_petit)
                            for m, plus_petit in METRIQUES_NULLS.items()}
    sortie["p_retenue"] = nulls.p_retenue(sortie["p"]["circulaire"]["ulcer"],
                                          sortie["p"]["segments"]["ulcer"])
    sortie["verdict"] = nulls.verdict(sortie["p_retenue"])
    return sortie


# =========================================================================================
# Mesure : verrou, compteur, DSR, ecriture
# =========================================================================================

def _code() -> str | None:
    try:
        return subprocess.run(["git", "-C", str(config.RACINE), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, timeout=10).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def _journaliser(rid: str, cfg: Config, statut: str, verdict: str | None) -> None:
    if rid in {x.get("run_id") for x in experiences.runs_journalises()}:
        return                                      # deja compte : rejouer ne compte rien
    experiences.enregistrer_run(rid, ID_EXP, f"test_invest:{statut}:{libelle(cfg)}",
                                empreinte_config(cfg), issue=verdict or "mesure")


def _finaliser(res: dict, rid: str, statut: str) -> dict:
    """DSR au N du compteur invest, puis ecriture (le N vit dans le resultat)."""
    n = experiences.n_essais_pour(ID_EXP)
    r = np.diff(np.asarray(res["series"]["v_s"], dtype=float)) / np.asarray(
        res["series"]["v_s"][:-1], dtype=float)
    dsr = multitest.sharpe_degonfle(r, n)["dsr"]
    res["metriques"]["strategie"].update(dsr=_propre(dsr), n_essais=n)
    res.update(run_id=rid, statut=statut, compteur=n, code=_code(),
               calcule_le=datetime.now(UTC).isoformat(timespec="seconds"))
    DOSSIER.mkdir(parents=True, exist_ok=True)
    (DOSSIER / f"{rid}.json").write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    return res


def mesurer(cfg: Config, d: dn.Donnees, statut: str = "exploratoire",
            recalculer: bool = False) -> dict:
    """Une mesure : TI1 doit etre preenregistree ; +1 au compteur la premiere fois seulement."""
    experiences.exiger(ID_EXP)
    rid = run_id(cfg, d.empreinte)
    chemin = DOSSIER / f"{rid}.json"
    if chemin.exists() and not recalculer:
        return json.loads(chemin.read_text(encoding="utf-8"))
    res = evaluer(cfg, d)
    _journaliser(rid, cfg, statut, res["verdict"])
    return _finaliser(res, rid, statut)


# =========================================================================================
# Synthese d'une periode : C1 (tableau des signaux + D3/D4), C2 (ablation), C3 (kappas)
# =========================================================================================

def _resume(res: dict) -> dict:
    m = res["metriques"]["strategie"]
    p = res["nulls"]["p"] if res["nulls"] else {}
    return {"signal": res["signal"], "libelle": res["libelle"], "run_id": res.get("run_id"),
            "ulcer": m["ulcer"], "mdd": m["mdd"], "protection": m["protection"],
            "calmar": m["calmar"], "cagr": m["cagr"], "sharpe": m["sharpe"], "dsr": m["dsr"],
            "expo_moyenne": m["expo_moyenne"], "changements_expo": m["changements_expo"],
            "p_circulaire": p.get("circulaire", {}).get("ulcer"),
            "p_segments": p.get("segments", {}).get("ulcer"),
            "p_secondaires": p,
            "p_retenue": res["nulls"]["p_retenue"] if res["nulls"] else None,
            "verdict": res["verdict"]}


def synthese_periode(resultats: list[dict], votes: pd.DataFrame, debut: pd.Timestamp,
                     fin: pd.Timestamp) -> dict:
    par = {(r["signal"], r["config"]["mapping"]["nom"]): r for r in resultats}
    c1 = [_resume(par[("complet", "socle")])] + [_resume(par[(v, "paliers")])
                                                for v in dn.VOTES]
    for ligne, q in zip(c1, nulls.bh_q([x["p_retenue"] for x in c1]), strict=True):
        ligne["q_bh"] = q
    cles = ("ulcer", "mdd", "protection", "calmar", "cagr", "sharpe", "expo_moyenne")
    complet = {k: par[("complet", "socle")]["metriques"]["strategie"][k] for k in cles}
    sans = {v: {k: par[(f"sans_{v}", "socle")]["metriques"]["strategie"][k] for k in cles}
            for v in dn.VOTES}
    fenetre = votes[(votes.index >= debut) & (votes.index <= fin)]
    return _propre({"c1": c1, "c2": analyse.contributions(complet, sans),
                    "c3": analyse.matrices_accord(fenetre[list(dn.VOTES)]),
                    "socle_paliers": _resume(par[("complet", "paliers")])})


def lancer_campagne(d: dn.Donnees, b: int = 1000, periodes: dict | None = None,
                    recalculer: bool = False) -> dict:
    """La campagne preenregistree : 24 mesures comptees, puis la synthese par periode.

    Toutes les mesures sont journalisees AVANT le calcul des DSR, pour que chacune porte le
    meme N (le compteur apres la campagne). Rejouer ne compte rien de plus.
    """
    experiences.exiger(ID_EXP)
    periodes = periodes or PERIODES
    a_faire, resultats = [], {}
    for cfg in campagne_ti1(b, periodes):
        rid = run_id(cfg, d.empreinte)
        chemin = DOSSIER / f"{rid}.json"
        if chemin.exists() and not recalculer:
            resultats[rid] = json.loads(chemin.read_text(encoding="utf-8"))
            continue
        log.info("mesure %s (%s)", libelle(cfg), cfg.periode)
        res = evaluer(cfg, d)
        _journaliser(rid, cfg, "campagne", res["verdict"])
        a_faire.append((rid, res))
    for rid, res in a_faire:
        resultats[rid] = _finaliser(res, rid, "campagne")
    synthese = {"experience": ID_EXP, "runs": list(resultats),
                "compteur": experiences.n_essais_pour(ID_EXP),
                "code": _code(), "calcule_le": datetime.now(UTC).isoformat(timespec="seconds"),
                "donnees": {"empreinte": d.empreinte, "pit": d.pit, "fin": f"{d.fin:%Y-%m-%d}",
                            "trous_acceptes": d.trous_acceptes},
                "periodes": {}}
    bornes = {}
    for periode, (debut, fin) in periodes.items():
        lot = [r for r in resultats.values() if r["periode"]["nom"] == periode]
        debut_t, fin_t = pd.Timestamp(debut, tz="UTC"), pd.Timestamp(fin, tz="UTC")
        bornes[periode] = (debut_t, fin_t)
        socle = next(r for r in lot if r["signal"] == "complet"
                     and r["config"]["mapping"]["nom"] == "socle")
        synthese["periodes"][periode] = {**socle["periode"],
                                         "synthese": synthese_periode(lot, d.votes, debut_t, fin_t)}
    synthese["diagnostic_pit"] = dn.diagnostic_pit(d.votes_socle, d.votes, d.cfg_socle, bornes)
    synthese = _propre(synthese)
    DOSSIER.mkdir(parents=True, exist_ok=True)
    (DOSSIER / f"campagne_{ID_EXP}.json").write_text(json.dumps(synthese, ensure_ascii=False),
                                                    encoding="utf-8")
    verdicts = "; ".join(f"{p} : " + ", ".join(f"{x['signal']} {x['verdict']}"
                                                for x in v["synthese"]["c1"])
                         for p, v in synthese["periodes"].items())
    if a_faire:                                     # un rejeu sans mesure n'ecrit rien
        cle = hashlib.sha256("|".join(sorted(resultats)).encode()).hexdigest()[:12]
        experiences.marquer_mesuree(ID_EXP, cle,
                                    f"campagne ({len(resultats)} mesures) — {verdicts}")
    return synthese
