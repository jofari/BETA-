"""VC6 V2 : la campagne du GO de Jonas (02/11/2026). Gel -> tests de coherence -> runs -> mesures.

Ordre du prompt : « V2 – HAR sans regime » et son temoin (periode principale, puis BTC seul depuis
2014), puis « V2 – poche baissiere sous HAR » et son temoin (idem). Pour chaque essai : nulls (B =
1 000 chacun), Sharpe deflate au compteur a jour, PBO (S10) rapportee sans effet. Regles 1 et 2
appliquees, regle 3 rapportee, grille du verdict pour info. Les mesures et les analyses sont celles
de la V1 (`beta.vc6.campagne`, `beta.vc6.analyse`, applications 24 a 34), appelees sur les
simulations de la V2. Aucun chiffre a la main : `beta.vc6_v2.rapport.ecrire` lit ce que rend
`executer`.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from beta.protocole import experiences
from beta.vc6 import analyse as an
from beta.vc6 import campagne as c1
from beta.vc6 import donnees as dn1
from beta.vc6 import moteur as mt1
from beta.vc6_v2 import coherence, decision, gel
from beta.vc6_v2 import donnees as dn
from beta.vc6_v2 import moteur as mt
from beta.vc6_v2 import nulls as nu
from beta.vc6_v2 import regles as R

log = logging.getLogger("beta.vc6_v2.campagne")

ORDRE = ("har_sans_regime", "poche_baissiere_har")
POIDS_ROBUSTESSE = {"BTC": 1.0}
N_ESSAIS_ATTENDU = 61          # spec : invest 59 -> 61, journalises au preenregistrement
UN = pd.Timedelta(days=1)


class CampagneError(RuntimeError):
    """Gel rompu, test de coherence rate, compteur inattendu ou cas non prevu : arret."""


def analyses(ent: mt.Entrees, sim: dict) -> dict:
    """Le detail par essai demande par le prompt (V1, applications 29, 30, 32, 34)."""
    return {"pires_drawdowns": an.pires_drawdowns(ent.jours, sim),
            "contributions": an.contributions(sim),
            "vol_realisee": an.vol_realisee(ent, sim, R.CIBLE),
            "levier": an.levier(sim)}


def evaluer(ent: mt.Entrees, p: mt.Parametres, cle_flux: str, n_essais: int,
            poids: dict[str, float], null: str, b: int = R.B_NULLS) -> dict:
    """Un essai : simulation, mesures, temoin, nulls (B = 1 000 chacun), regle 1, analyses.
    `b` ne sert qu'aux tests sur donnees synthetiques."""
    sim = mt.simuler(ent, p)
    m = c1.mesures(sim["r"], n_essais, sim["expo_totale"], sim)
    t = mt.temoin(ent, poids, m["expo_moyenne"])
    m_t = c1.mesures(t["r"], None, t["expo_totale"])
    m_t["financement"] = float(t["financement"].sum())
    if null == "positions":
        dist = nu.distribution_positions(ent, p, sim, cle_flux, b)
    elif null == "mode":
        dist = nu.distribution_mode(ent, p, cle_flux, b)
    else:
        raise CampagneError(f"null inconnu : {null}")
    pv = nu.p_values(dist, m["ulcer"])
    pv["b"] = {k: int(len(v)) for k, v in dist.items()}
    return {"sim": sim, "mesures": m, "temoin": {"r": t["r"], "mesures": m_t}, "nulls": pv,
            "null": null, "utile": decision.utile(m["ulcer"], m_t["ulcer"], pv["p_retenue"]),
            "analyses": analyses(ent, sim)}


def reference_v1(ent: mt.Entrees, poids: dict[str, float] | None = None) -> dict:
    """La « Variante expo vol » de la V1, recalculee par le moteur de la V1 (application 15)."""
    sim = mt1.simuler(ent, c1.parametres(R.REFERENCE_V1["cle"], poids=poids))
    return {"sim": sim, "mesures": c1.mesures(sim["r"], None, sim["expo_totale"], sim),
            "analyses": {"contributions": an.contributions(sim)}}


def _ref(r: np.ndarray) -> dict:
    return c1.mesures(r, None, np.ones(len(r)))


def references_robustesse(ent_r: mt.Entrees, close_r: pd.Series) -> dict:
    """BTC achete et conserve (Bitstamp) et ETF monde (URTH) sur la periode de la robustesse."""
    hold = close_r.reindex(ent_r.jours).to_numpy(dtype=float)
    urth = dn1.urth_close(ent_r.jours[0] - UN, ent_r.jours[-1])
    r_urth = c1._reindexer(urth.pct_change(), ent_r.jours, "URTH")[1:]
    return {"btc": hold[1:] / hold[:-1] - 1.0, "etf_monde": r_urth}


def verdict(run: dict, refs: dict[str, np.ndarray]) -> dict:
    """Grille du verdict VC6, pour info (V1, application 25 pour le risque egal)."""
    m = run["mesures"]
    rv = run["sim"]["r"]
    eg = {n: c1.mesures(c1.a_risque_egal(r, rv), None, np.ones(len(r))) for n, r in refs.items()}
    return {"sharpe": m["sharpe"], "sharpe_sup_1": bool((m["sharpe"] or 0) > 1),
            "mdd": m["mdd"], "mdd_sup_m25": bool(m["mdd"] > -0.25), "cagr": m["cagr"],
            "panier_risque_egal_cagr": eg["panier"]["cagr"],
            "bat_panier": bool(m["cagr"] > eg["panier"]["cagr"]),
            "etf_risque_egal_cagr": eg["etf_monde"]["cagr"],
            "bat_etf": bool(m["cagr"] > eg["etf_monde"]["cagr"])}


def regle3(essai: dict, v1: dict) -> dict:
    """Rapportee sans effet : Ulcer, drawdown max, rendement annualise, contribution de la poche
    baissiere entre le plus haut et le creux du drawdown max de chacun (application 21)."""
    def ligne(run: dict) -> dict:
        m = run["mesures"]
        c = run["analyses"]["contributions"]
        return {"ulcer": m["ulcer"], "mdd": m["mdd"], "cagr": m["cagr"],
                "baissiere_pendant_mdd": c["drawdown_max"].get("baissiere:BTC"),
                "baissiere_total": c["total"].get("baissiere:BTC")}
    return {"essai": ligne(essai), "v1": ligne(v1)}


def assembler(ent: mt.Entrees, ent_r: mt.Entrees, refs: dict[str, np.ndarray],
              refs_rob: dict[str, np.ndarray], coh: dict, n_essais: int, compteurs: dict,
              b: int = R.B_NULLS) -> dict:
    """Runs, references, regles, PBO et grille du verdict, sur des entrees deja chargees. Separe
    du chargement pour etre eprouve de bout en bout sur donnees synthetiques."""
    runs, rob = {}, {}
    for cle in ORDRE:
        null = R.ESSAIS[cle]["null"]
        runs[cle] = evaluer(ent, mt.parametres_essai(cle), cle, n_essais, R.POIDS, null, b)
        log.info("%s, periode principale : Ulcer %.4f, p retenue %.3f", cle,
                 runs[cle]["mesures"]["ulcer"], runs[cle]["nulls"]["p_retenue"])
        rob[cle] = evaluer(ent_r, mt.parametres_essai(cle, poids=POIDS_ROBUSTESSE),
                           f"robustesse_{cle}", n_essais, POIDS_ROBUSTESSE, null, b)
        log.info("%s, robustesse : Ulcer %.4f, p retenue %.3f", cle,
                 rob[cle]["mesures"]["ulcer"], rob[cle]["nulls"]["p_retenue"])
    v1 = reference_v1(ent)
    v1_rob = reference_v1(ent_r, POIDS_ROBUSTESSE)
    regles = {"1": {k: {"ulcer": runs[k]["mesures"]["ulcer"],
                        "ulcer_temoin": runs[k]["temoin"]["mesures"]["ulcer"],
                        "p_retenue": runs[k]["nulls"]["p_retenue"], "utile": runs[k]["utile"]}
                    for k in ORDRE},
              "2": decision.configuration_retenue(
                  {k: {"utile": runs[k]["utile"],
                       "ratio": runs[k]["mesures"]["ratio_cagr_ulcer"]} for k in ORDRE}),
              "3": regle3(runs["poche_baissiere_har"], v1)}
    jours_r = ent.jours[1:]
    pbo = c1.calculer_pbo({k: runs[k]["sim"]["r"] for k in ORDRE}, jours_r)
    return {
        "experience": R.ID_EXP, "empreinte_regles": R.empreinte(), "n_essais_invest": n_essais,
        "compteurs": compteurs, "coherence": coh,
        "periode": {"debut": f"{jours_r[0]:%Y-%m-%d}", "fin": f"{jours_r[-1]:%Y-%m-%d}",
                    "n_jours": int(len(jours_r))},
        "runs": runs, "v1": v1,
        "references": {k: _ref(r) for k, r in refs.items()},
        "regles": regles, "pbo": pbo,
        "verdict_vc6": {k: verdict(runs[k], refs) for k in ORDRE},
        "robustesse": {"runs": rob, "v1": v1_rob,
                       "references": {k: _ref(r) for k, r in refs_rob.items()},
                       "debut": f"{ent_r.jours[1]:%Y-%m-%d}",
                       "fin": f"{ent_r.jours[-1]:%Y-%m-%d}", "n_jours": ent_r.n},
        "jours": ent.jours, "jours_robustesse": ent_r.jours}


def executer() -> dict:
    """Le GO : gel, compteur, tests de coherence (arret si l'un rate), donnees, puis `assembler`."""
    pre = gel.verifier()
    n_essais = experiences.n_essais_pour(R.ID_EXP)
    if n_essais != N_ESSAIS_ATTENDU:
        raise CampagneError(f"compteur invest a {n_essais}, la spec dit {N_ESSAIS_ATTENDU}")
    coh = coherence.tous()
    if not coh["passe"]:
        raise CampagneError(f"test de coherence rate : {coh.get('arret')}")
    log.info("coherence : les 4 tests passent")
    d = dn.charger_principal()
    ent = dn.entrees_principal(d)
    ent_r, close_r = dn.entrees_robustesse()
    compteurs = {"invest": experiences.compteur(famille="invest"),
                 "trading": experiences.compteur(), "global": experiences.compteur_total()}
    res = assembler(ent, ent_r, c1.references(d, ent), references_robustesse(ent_r, close_r),
                    coh, n_essais, compteurs)
    res["preenregistre_le"] = pre.get("date")
    return res
