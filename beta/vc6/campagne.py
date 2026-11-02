"""VC6 V1, Temps 2 : la campagne (gel verifie -> donnees -> coherence -> runs -> mesures).

Ordre impose par le prompt du 02/11 : tests de coherence d'abord, arret si l'un echoue ; puis
« Variante expo fixe » et « Variante expo vol » avec leurs temoins, le test annexe, la designation
de la meilleure (application 19), « Variante poche or » et « Variante poche mixte » sur ce sizing,
la robustesse BTC seul depuis 2014, et pour chaque essai nulls D4, Sharpe deflate, PBO.
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
import math

import numpy as np
import pandas as pd

from beta import config
from beta.invest import metriques, nulls
from beta.protocole import experiences
from beta.stats import pbo as pbo_mod
from beta.vc6 import coherence
from beta.vc6 import donnees as dn
from beta.vc6 import moteur as mt
from beta.vc6 import regles as R

log = logging.getLogger("beta.vc6.campagne")

TEXTE = config.RACINE / "VC6_V1" / "temps2" / "PREENREGISTREMENT.md"
UN = pd.Timedelta(days=1)


class CampagneError(RuntimeError):
    """Gel rompu, test de coherence rate ou cas non prevu : arret, aucun chiffre ne sort."""


def verifier_gel() -> dict:
    lignes = [x for x in experiences._lignes() if x.get("id") == R.ID_EXP
              and x.get("statut") == "preenregistre"]
    if not lignes:
        raise CampagneError(f"{R.ID_EXP} n'est pas preenregistree")
    pre = lignes[-1]
    if pre.get("empreinte") != R.empreinte():
        raise CampagneError(f"regles changees depuis le gel : {pre.get('empreinte')} -> "
                            f"{R.empreinte()}")
    texte = hashlib.sha256(TEXTE.read_bytes()).hexdigest()[:16]
    if pre.get("empreinte_preenregistrement") != texte:
        raise CampagneError("PREENREGISTREMENT.md a change depuis le gel")
    return pre


# ----------------------------------------------------------------------------- donnees

def _reindexer(s: pd.Series, jours: pd.DatetimeIndex, quoi: str, depuis: int = 0) -> np.ndarray:
    x = s.reindex(jours)
    if x.iloc[depuis:].isna().any():
        raise CampagneError(f"{quoi} manquant le {x.iloc[depuis:].index[x.iloc[depuis:].isna()][0]:%Y-%m-%d}")
    return x.to_numpy(dtype=float)


def charger_principal() -> dict:
    barres = {a: dn.barres_5m(a) for a in R.POCHES}
    closes = dn.clotures_perp(barres)
    return {"closes": closes, "sigma": dn.sigma_har(barres),
            "funding": {a: dn.funding_jour(a) for a in R.POCHES}}


def entrees_principal(d: dict, debut: str = R.DEBUT_PRINCIPAL, fin: str = R.FIN) -> mt.Entrees:
    jours = pd.date_range(pd.Timestamp(debut) - UN, pd.Timestamp(fin), freq="D")
    closes = d["closes"]
    sma = closes["BTC"].rolling(R.SMA).mean()
    baissier = _reindexer((closes["BTC"] < sma).where(sma.notna()), jours, "mode BTC")
    xau = dn.or_close(jours[0] - UN, jours[-1])
    rend = {a: _reindexer(closes[a].pct_change(), jours, f"rendement {a}") for a in R.POCHES}
    rend["XAU"] = _reindexer(xau.pct_change(), jours, "rendement or")
    return mt.Entrees(
        jours=jours, baissier=baissier.astype(bool),
        sigma={a: _reindexer(d["sigma"][a], jours, f"sigma {a}") for a in R.POCHES},
        funding_annuel={a: _reindexer(d["funding"][a]["somme"] * R.JOURS_AN, jours,
                                      f"funding {a}") for a in R.POCHES},
        funding_jour={a: _reindexer(d["funding"][a]["somme"], jours, f"funding {a}")
                      for a in R.POCHES},
        rendements=rend)


def funding_robustesse() -> pd.Series:
    reel = dn.funding_jour("BTC")["somme"]
    limite = pd.Timestamp(R.FUNDING_AVANT_PERP_JUSQU_A)
    avant = pd.Series(R.FUNDING_AVANT_PERP * R.REGLEMENTS_PAR_JOUR_AVANT_PERP,
                      index=pd.date_range("2011-01-01", limite - UN, freq="D"))
    return pd.concat([avant, reel[reel.index >= limite]])


def entrees_robustesse(debut: str = R.DEBUT_ROBUSTESSE, fin: str = R.FIN) -> tuple:
    close = dn.bitstamp_close()
    jours = pd.date_range(pd.Timestamp(debut) - UN, pd.Timestamp(fin), freq="D")
    sma = close.rolling(R.SMA).mean()
    f = funding_robustesse()
    ent = mt.Entrees(
        jours=jours,
        baissier=_reindexer((close < sma).where(sma.notna()), jours, "mode").astype(bool),
        sigma={"BTC": _reindexer(dn.sigma_ecart_type(close), jours, "sigma")},
        funding_annuel={"BTC": _reindexer(f * R.JOURS_AN, jours, "funding")},
        funding_jour={"BTC": _reindexer(f, jours, "funding")},
        rendements={"BTC": _reindexer(close.pct_change(), jours, "rendement")})
    return ent, close


# ----------------------------------------------------------------------------- mesures

def ulcer(r: np.ndarray) -> float:
    return float(math.sqrt(np.mean(metriques.drawdown(metriques.courbe(r))[1:] ** 2)))


def mesures(r: np.ndarray, n_essais: int | None, expo: np.ndarray,
            sim: dict | None = None) -> dict:
    s = metriques.standard(r, n_essais=n_essais)
    n = len(r)
    out = {k: s[k] for k in ("rendement_total", "cagr", "vol", "sharpe", "dsr", "mdd",
                             "ulcer", "duree_sous_eau_max_j")}
    out["ratio_cagr_ulcer"] = s["cagr"] / s["ulcer"] if s["ulcer"] > 0 else None
    out["expo_moyenne"] = float(np.mean(expo))
    out["n_jours"] = n
    if sim is not None:
        change = np.any(np.abs(np.diff(sim["y"], axis=0)) > 0, axis=1)
        out.update({
            "changements_par_an": float(change.sum() / (n / R.JOURS_AN)),
            "frais": float(sim["frais"].sum()), "financement": float(sim["financement"].sum()),
            "jours_contraints": int(sim["contraint"].any(axis=1).sum()),
            "jours_contraints_par_poche": dict(zip(sim["poches"],
                                                   sim["contraint"].sum(axis=0).tolist())),
            "jours_en_rampe": int(sim["en_rampe"].sum()),
            "jours_levier": int((sim["e"] > 1 + 1e-12).any(axis=1).sum())})
    else:
        out.update({"changements_par_an": 0.0, "frais": 0.0, "financement": None,
                    "jours_contraints": None, "jours_en_rampe": None, "jours_levier": None})
    return out


def parametres(cle: str, sizing_meilleur: str | None = None, poids=None) -> mt.Parametres:
    v = R.VARIANTES[cle]
    sizing = v["sizing"]
    cible = v["cible"]
    if sizing == "meilleure":
        sizing = R.VARIANTES[sizing_meilleur]["sizing"]
        cible = R.VARIANTES[sizing_meilleur]["cible"]
    return mt.Parametres(poids=dict(poids or R.POIDS), sizing=sizing, cible=cible,
                         baissiere=dict(v["baissiere"]))


def distribution_nulle(ent: mt.Entrees, p: mt.Parametres, cle: str) -> dict:
    n = ent.n
    signal = ent.baissier[:n].astype(float)
    dernier = ent.baissier[n:]
    gens = {"circulaire": functools.partial(nulls.decalage_circulaire, m=R.M_DECALAGE),
            "segments": nulls.melange_segments}
    sortie = {}
    for nom, gen in gens.items():
        rng = nulls.flux(R.GRAINE, R.ID_EXP, cle, nom)
        u = np.empty(R.B_NULLS)
        for b in range(R.B_NULLS):
            s = gen(signal, rng)
            u[b] = ulcer(mt.simuler(ent, p, np.concatenate([s > 0.5, dernier]))["r"])
        sortie[nom] = u
    return sortie


def evaluer(ent: mt.Entrees, p: mt.Parametres, cle: str, n_essais: int, poids: dict,
            avec_nulls: bool = True) -> dict:
    sim = mt.simuler(ent, p)
    m = mesures(sim["r"], n_essais, sim["expo_totale"], sim)
    t = mt.temoin(ent, poids, m["expo_moyenne"])
    mt_ = mesures(t["r"], None, t["expo_totale"])
    mt_["financement"] = float(t["financement"].sum())
    res = {"cle": cle, "sim": sim, "mesures": m, "temoin": {"r": t["r"], "mesures": mt_}}
    if avec_nulls:
        dist = distribution_nulle(ent, p, cle)
        pc = nulls.p_value(dist["circulaire"], m["ulcer"], True)
        ps = nulls.p_value(dist["segments"], m["ulcer"], True)
        pr = nulls.p_retenue(pc, ps)
        res["nulls"] = {"p_circulaire": pc, "p_segments": ps, "p_retenue": pr,
                        "verdict_d4": nulls.verdict(pr),
                        "ulcer_nul_median": {k: float(np.median(v)) for k, v in dist.items()}}
        res["utile"] = bool(m["ulcer"] < mt_["ulcer"] and pr is not None and pr < R.SEUIL_P)
    return res


def designer(fixe: dict, vol: dict) -> dict:
    """Application 19 : la meilleure entre « Variante expo fixe » et « Variante expo vol »."""
    rf, rv = fixe["mesures"]["ratio_cagr_ulcer"], vol["mesures"]["ratio_cagr_ulcer"]
    if not fixe["utile"] and not vol["utile"]:
        cle = "vol" if rv > rf else "fixe"
        return {"meilleure": cle, "regle2_vol_retenue": False,
                "note": "aucune des deux n'est utile : plus haut ratio rendement / Ulcer"}
    if vol["utile"] and rv > rf:
        return {"meilleure": "vol", "regle2_vol_retenue": True, "note": "regle 2 remplie"}
    return {"meilleure": "fixe", "regle2_vol_retenue": False,
            "note": "regle 2 non remplie par la Variante expo vol"}


def regle3(base: dict, autre: dict) -> dict:
    ub, ua = base["mesures"]["ulcer"], autre["mesures"]["ulcer"]
    cb, ca = base["mesures"]["cagr"], autre["mesures"]["cagr"]
    return {"ulcer_plus_bas": bool(ua < ub), "cagr_suffisant": bool(ca >= cb - 0.02),
            "remplace": bool(ua < ub and ca >= cb - 0.02)}


def calculer_pbo(series: dict[str, np.ndarray], jours: pd.DatetimeIndex) -> dict:
    m = pd.DataFrame({k: v for k, v in sorted(series.items())}, index=jours)
    return pbo_mod.calculer(m, R.SEUIL_PBO)


# ----------------------------------------------------------------------------- campagne

DOSSIER = config.DATA / "vc6_temps2"
CSV_HAR = config.RACINE / "VC6_V1" / "controle_har" / "RAPPORT_CONTROLE_HAR.csv"


def _sma_au_dessus(close: pd.Series, jours: pd.DatetimeIndex) -> np.ndarray:
    sma = close.rolling(R.SMA).mean()
    return _reindexer((close >= sma).where(sma.notna()), jours, "SMA").astype(bool)


def references(d: dict, ent: mt.Entrees) -> dict:
    jours = ent.jours
    sub = d["closes"].reindex(jours)
    v = sum(w * sub[a].to_numpy() / sub[a].iloc[0] for a, w in R.POIDS.items())
    r_panier = v[1:] / v[:-1] - 1.0
    urth = dn.urth_close(jours[0] - UN, jours[-1])
    r_urth = _reindexer(urth.pct_change(), jours, "URTH")[1:]
    return {"panier": r_panier, "etf_monde": r_urth}


def a_risque_egal(r_ref: np.ndarray, r_var: np.ndarray) -> np.ndarray:
    k = np.std(r_var, ddof=1) / np.std(r_ref, ddof=1)
    return k * r_ref


def prediction(res: dict) -> dict:
    har = pd.read_csv(CSV_HAR)
    proches = har.apply(lambda x: abs(x.qlike_har - x.qlike_ecart_type_30j)
                        / x.qlike_ecart_type_30j < 0.10, axis=1)
    lev = res["levier"]["annexe40"]
    mdd = {k: res["runs"][k]["mesures"]["mdd"] for k in res["runs"]}
    return {
        "har": {"ecarts_relatifs": dict(zip(har.actif, (abs(har.qlike_har - har.qlike_ecart_type_30j)
                                                        / har.qlike_ecart_type_30j).round(4))),
                "actifs_a_moins_de_10pc": int(proches.sum()),
                "statut": "confirmee" if proches.sum() >= 2 else "infirmee"},
        "volatilite": {"vol_utile": res["runs"]["vol"]["utile"],
                       "statut": "infirmee" if res["runs"]["vol"]["utile"] else "confirmee"},
        "levier": {"jours": lev["jours"], "gain_part_en_levier": lev["gain_part_en_levier"],
                   "financement": lev["financement"],
                   "statut": ("non mesurable" if lev["jours"] == 0 else
                              "confirmee" if lev["gain_part_en_levier"] < lev["financement"]
                              else "infirmee")},
        "drawdown": {"mdd": mdd, "statut": "confirmee" if min(mdd.values()) < -0.40
                     else "infirmee"},
        "sma_unique": {"statut": "non mesurable",
                       "lecture": "retard de sortie et aller-retours (sections SMA 200)"},
    }


def executer(sans_nulls: bool = False) -> dict:
    pre = verifier_gel()
    n_essais = experiences.compteur(famille="invest")
    d = charger_principal()
    ent = entrees_principal(d)
    coh = coherence.tous(ent)
    if not coh["passe"]:
        raise CampagneError(f"test de coherence rate : {json.dumps(coh, default=str)[:2000]}")
    log.info("coherence : 5 tests passes")
    avec = not sans_nulls
    runs = {}
    for cle in ("fixe", "vol", "annexe40"):
        runs[cle] = evaluer(ent, parametres(cle), cle, n_essais, R.POIDS, avec)
        log.info("%s : Ulcer %.4f", cle, runs[cle]["mesures"]["ulcer"])
    choix = designer(runs["fixe"], runs["vol"]) if avec else {"meilleure": "vol"}
    for cle in ("or", "mixte"):
        runs[cle] = evaluer(ent, parametres(cle, choix["meilleure"]), cle, n_essais, R.POIDS,
                            avec)
        log.info("%s : Ulcer %.4f", cle, runs[cle]["mesures"]["ulcer"])
    base = runs[choix["meilleure"]]
    regles = {"1": {k: {"ulcer": runs[k]["mesures"]["ulcer"],
                        "ulcer_temoin": runs[k]["temoin"]["mesures"]["ulcer"],
                        "p_retenue": runs[k].get("nulls", {}).get("p_retenue"),
                        "utile": runs[k].get("utile")} for k in runs},
              "2": choix,
              "3": {k: regle3(base, runs[k]) for k in ("or", "mixte")},
              "4": {"aucune_utile": not (runs["fixe"].get("utile") or runs["vol"].get("utile"))}}
    rempl = [k for k in ("or", "mixte") if regles["3"][k]["remplace"]]
    regles["3"]["conclusion"] = (rempl[0] if len(rempl) == 1 else
                                 "les deux : choix de Jonas" if rempl else "poche BTC gardee")
    jours_r = ent.jours[1:]
    pbos = {"quatre_variantes": calculer_pbo({k: runs[k]["sim"]["r"] for k in
                                              ("fixe", "vol", "or", "mixte")}, jours_r),
            "sizing": calculer_pbo({k: runs[k]["sim"]["r"] for k in ("fixe", "vol")}, jours_r),
            "poche_baissiere": calculer_pbo({k: runs[k]["sim"]["r"] for k in
                                             (choix["meilleure"], "or", "mixte")}, jours_r)}
    refs = references(d, ent)
    ref_mesures = {k: mesures(r, None, np.ones(len(r))) for k, r in refs.items()}
    verdict = {}
    for k, run in runs.items():
        rv = run["sim"]["r"]
        m = run["mesures"]
        eg = {n: mesures(a_risque_egal(r, rv), None, np.ones(len(r))) for n, r in refs.items()}
        verdict[k] = {"sharpe": m["sharpe"], "sharpe_sup_1": bool((m["sharpe"] or 0) > 1),
                      "mdd": m["mdd"], "mdd_sup_m25": bool(m["mdd"] > -0.25),
                      "cagr": m["cagr"],
                      "panier_risque_egal_cagr": eg["panier"]["cagr"],
                      "bat_panier": bool(m["cagr"] > eg["panier"]["cagr"]),
                      "etf_risque_egal_cagr": eg["etf_monde"]["cagr"],
                      "bat_etf": bool(m["cagr"] > eg["etf_monde"]["cagr"])}
    closes = d["closes"]
    au_dessus = {a: _sma_au_dessus(closes[a], ent.jours) for a in ("ETH", "SOL")}
    v_btc = closes["BTC"].reindex(ent.jours).to_numpy()
    courbes = {k: metriques.courbe(r["sim"]["r"]) for k, r in runs.items()}
    from beta.vc6 import analyse as an
    ana = {}
    for k, run in runs.items():
        p = parametres(k, choix["meilleure"])
        cible = p.cible if p.sizing == "vol" else 0.25
        ana[k] = {"pires_drawdowns": an.pires_drawdowns(ent.jours, run["sim"]),
                  "contributions": an.contributions(run["sim"]),
                  "conflits": an.conflits(ent, p, run["sim"], au_dessus),
                  "vol_realisee": an.vol_realisee(ent, run["sim"], cible),
                  "aller_retours": an.aller_retours(ent.jours, ent.baissier, run["sim"],
                                                    run["temoin"]["r"]),
                  "sortie_lente": an.sortie_lente(ent.jours, ent, run["sim"])}
    levier = {k: an.levier(run["sim"]) for k, run in runs.items()}
    bears = an.grands_bears(ent.jours, v_btc, ent.baissier, courbes)
    # perpetuel contre Bitstamp, periode commune ou les deux SMA 200 existent
    bit = dn.bitstamp_close()
    sp, sb = closes["BTC"].rolling(R.SMA).mean(), bit.rolling(R.SMA).mean()
    mp, mb = (closes["BTC"] < sp).where(sp.notna()), (bit < sb).where(sb.notna())
    communs = mp.dropna().index.intersection(mb.dropna().index)
    communs = communs[communs <= pd.Timestamp(R.FIN)]
    diff = mp.loc[communs].astype(bool) != mb.loc[communs].astype(bool)
    perp_bitstamp = {"debut": f"{communs[0]:%Y-%m-%d}", "fin": f"{communs[-1]:%Y-%m-%d}",
                     "jours": int(len(communs)), "jours_differents": int(diff.sum()),
                     "dates": [f"{x:%Y-%m-%d}" for x in communs[diff.to_numpy()]]}
    # robustesse BTC seul depuis 2014
    ent_r, close_r = entrees_robustesse()
    rob = {}
    for cle in ("fixe", "vol"):
        p = parametres(cle, poids={"BTC": 1.0})
        rob[cle] = evaluer(ent_r, p, f"robustesse_{cle}", n_essais, {"BTC": 1.0}, avec)
        rob[cle]["levier"] = an.levier(rob[cle]["sim"])
    rob_bears = an.grands_bears(ent_r.jours, close_r.reindex(ent_r.jours).to_numpy(),
                                ent_r.baissier,
                                {k: metriques.courbe(v["sim"]["r"]) for k, v in rob.items()})
    hold_r = close_r.reindex(ent_r.jours).to_numpy()
    rob_hold = mesures(hold_r[1:] / hold_r[:-1] - 1, None, np.ones(ent_r.n))
    res = {"experience": R.ID_EXP, "empreinte_regles": R.empreinte(),
           "preenregistre_le": pre.get("date"), "n_essais_invest": n_essais,
           "compteurs": {"invest": n_essais, "global": experiences.compteur_total(),
                         "trading": experiences.compteur()},
           "periode": {"debut": f"{jours_r[0]:%Y-%m-%d}", "fin": f"{jours_r[-1]:%Y-%m-%d}",
                       "n_jours": int(len(jours_r))},
           "coherence": coh, "runs": runs, "regles": regles, "pbo": pbos,
           "references": ref_mesures, "verdict_vc6": verdict, "analyses": ana,
           "levier": levier, "grands_bears": bears, "perp_bitstamp": perp_bitstamp,
           "robustesse": {"runs": rob, "grands_bears": rob_bears, "hold_btc": rob_hold,
                          "debut": f"{ent_r.jours[1]:%Y-%m-%d}", "n_jours": ent_r.n},
           "nulls": avec, "jours": ent.jours}
    res["prediction"] = prediction(res)
    return res
