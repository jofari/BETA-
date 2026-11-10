"""Momentum trente jours sur le BTC - le moteur du test invest MOMENTUM30_BTC.

Fonctions pures, sans lecture disque : le script `scripts/mesurer_momentum30_btc.py` charge
les donnees et appelle ce module. Les regles viennent de MOMENTUM30_BTC/PREENREGISTREMENT.md,
dont l'empreinte est ecrite au registre : le script refuse de tourner si ce fichier ou
celui-ci a change depuis le preenregistrement.

Conventions (applications 1 a 8 du preenregistrement) :
- bougie quotidienne datee par son OUVERTURE ; cloture du jour D = close de la bougie D ;
- rendement du jour D : close(D) / close(D - 1) - 1 ;
- decision a la cloture du jour t, appliquee au rendement du jour t + 1 (aucune donnee de t + 1) ;
- signal : close(t) / close(t - L) - 1 > 0 => exposition 1, sinon 0 ; L = 30 ;
- R_S(t) = E R_B - kappa |dE| - E phi + (1 - E) rf   (A3 du test invest, funding paye par TOUT
  le long d'un perpetuel, pas seulement la part levieree : l'instrument est le perpetuel) ;
- aucun cout d'entree le premier jour (ni pour la strategie, ni pour le hold) ;
- metriques : beta.invest.metriques.standard ; nulls : beta.invest.nulls (D du test invest).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from beta.invest import metriques, nulls

LOOKBACK = 30
KAPPA_PB = 6.0            # 0,05 % taker + 0,01 % slippage, par cote et par unite d'exposition
B_NULLS = 1000
MARGE_NULL = 90
SEUIL_REEL, SEUIL_HASARD = nulls.SEUIL_REEL, nulls.SEUIL_HASARD
ID_EXPERIENCE = "MOMENTUM30_BTC"

CONFIRMEE, INFIRMEE, INDECIDABLE = "confirmee", "infirmee", "indecidable"


def exposition(close: np.ndarray, lookback: int = LOOKBACK) -> np.ndarray:
    """E(t + 1) = 1 si close(t) / close(t - lookback) - 1 > 0, sinon 0 ; NaN avant warm-up.

    Rendue ALIGNEE sur les jours : e[i] est l'exposition tenue pendant le jour i, decidee a la
    cloture du jour i - 1. Causale par construction : e[i] ne lit que close[:i].
    """
    close = np.asarray(close, dtype=float)
    n = len(close)
    e = np.full(n, np.nan)
    for i in range(lookback + 1, n):
        e[i] = 1.0 if close[i - 1] / close[i - 1 - lookback] - 1.0 > 0.0 else 0.0
    return e


def rendements_bruts(close: np.ndarray) -> np.ndarray:
    """r_b[i] = close[i] / close[i - 1] - 1 ; NaN en i = 0."""
    close = np.asarray(close, dtype=float)
    r = np.full(len(close), np.nan)
    r[1:] = close[1:] / close[:-1] - 1.0
    return r


def funding_journalier(reglements: pd.DataFrame, jours: pd.DatetimeIndex) -> np.ndarray:
    """phi(D) = somme des reglements de ]D 00:00 ; D + 1 00:00] UTC (application 5).

    `reglements` : colonnes date (horodatage du reglement, tz-aware) et funding_rate.
    Un jour sans aucun reglement est une donnee manquante : erreur, jamais un zero silencieux.
    """
    f = reglements.copy()
    f["date"] = pd.to_datetime(f["date"], utc=True)
    f = f.sort_values("date")
    # Le reglement de D + 1 00:00 appartient au jour D : on recule d'une microseconde.
    jour = (f["date"] - pd.Timedelta(microseconds=1)).dt.floor("D")
    somme = f.groupby(jour)["funding_rate"].sum()
    compte = f.groupby(jour)["funding_rate"].size()
    serie = somme.reindex(jours)
    manquants = serie.isna() | (compte.reindex(jours).fillna(0) < 1)
    if manquants.any():
        premiers = [str(d.date()) for d in jours[manquants.to_numpy()][:5]]
        raise ValueError(f"funding absent sur {int(manquants.sum())} jour(s), p. ex. {premiers}")
    return serie.to_numpy(dtype=float)


def rendement_net(e: np.ndarray, r_b: np.ndarray, phi: np.ndarray, rf: np.ndarray,
                  kappa_pb: float = KAPPA_PB) -> dict:
    """R_S = E R_B - kappa |dE| - E phi + (1 - E) rf. Aucun cout le premier jour."""
    e = np.asarray(e, dtype=float)
    r_b = np.asarray(r_b, dtype=float)
    phi = np.asarray(phi, dtype=float)
    rf = np.asarray(rf, dtype=float)
    if not (len(e) == len(r_b) == len(phi) == len(rf)):
        raise ValueError("series de longueurs differentes")
    if np.isnan(e).any() or np.isnan(r_b).any() or np.isnan(phi).any() or np.isnan(rf).any():
        raise ValueError("NaN dans les series : la periode doit commencer apres le warm-up")
    precedente = np.concatenate([e[:1], e[:-1]])
    rotation = np.abs(e - precedente)
    cout = kappa_pb / 1e4 * rotation
    funding = e * phi
    cash = (1.0 - e) * rf
    r = e * r_b - cout - funding + cash
    return {"r": r, "cout": cout, "funding": funding, "cash": cash,
            "turnover": float(rotation.sum())}


def evaluer(e: np.ndarray, r_b: np.ndarray, phi: np.ndarray, rf: np.ndarray,
            kappa_pb: float = KAPPA_PB, n_essais: int | None = None) -> dict:
    """Rendement net puis metriques standard (Sharpe net de rf, CAGR, MDD, Ulcer...)."""
    net = rendement_net(e, r_b, phi, rf, kappa_pb)
    m = metriques.standard(net["r"], e, rf, n_essais)
    m["turnover"] = net["turnover"]
    m["cout_total"] = float(net["cout"].sum())
    m["funding_total"] = float(net["funding"].sum())
    return m


def hold(r_b: np.ndarray, phi: np.ndarray, rf: np.ndarray, n_essais: int | None = None) -> dict:
    """Le buy-and-hold du perpetuel : E = 1 en permanence, meme funding, aucun frais."""
    return evaluer(np.ones(len(r_b)), r_b, phi, rf, kappa_pb=0.0, n_essais=n_essais)


def temoin_constant(e: np.ndarray, r_b: np.ndarray, phi: np.ndarray, rf: np.ndarray) -> dict:
    """Meme exposition MOYENNE, sans timing, sans frais (application 14 de VC6, reprise)."""
    moyenne = float(np.mean(e))
    m = evaluer(np.full(len(r_b), moyenne), r_b, phi, rf, kappa_pb=0.0)
    m["e"] = moyenne
    return m


def _sharpe(e: np.ndarray, r_b, phi, rf, kappa_pb) -> float:
    r = rendement_net(e, r_b, phi, rf, kappa_pb)["r"]
    ecart = float(np.std(r, ddof=1))
    return float(np.mean(r - rf) / ecart * math.sqrt(metriques.JOURS_AN)) if ecart > 0 else float("nan")


def nulls_sharpe(e: np.ndarray, r_b: np.ndarray, phi: np.ndarray, rf: np.ndarray,
                 kappa_pb: float = KAPPA_PB, b: int = B_NULLS, graine: int = 0,
                 id_exp: str = ID_EXPERIENCE) -> dict:
    """Les deux nulls du test invest sur la serie d'exposition, metrique Sharpe (plus grand
    meilleur) : p = (1 + #{Sharpe_nul >= Sharpe_obs}) / (1 + B), p retenue = la plus grande."""
    observe = _sharpe(e, r_b, phi, rf, kappa_pb)
    sortie = {"observe": observe, "b": b}
    for nom, generateur in (("circulaire", lambda s, rng: nulls.decalage_circulaire(s, rng, MARGE_NULL)),
                            ("segments", nulls.melange_segments)):
        rng = nulls.flux(graine, id_exp, nom)
        tirages = np.array([_sharpe(generateur(e, rng), r_b, phi, rf, kappa_pb) for _ in range(b)])
        sortie[nom] = {"p": nulls.p_value(tirages, observe, plus_petit_meilleur=False),
                       "mediane": float(np.nanmedian(tirages)),
                       "q05": float(np.nanpercentile(tirages, 5)),
                       "q95": float(np.nanpercentile(tirages, 95)),
                       "part_sup": float(np.mean(tirages >= observe))}
    sortie["p_retenue"] = nulls.p_retenue(sortie["circulaire"]["p"], sortie["segments"]["p"])
    sortie["verdict_nulls"] = nulls.verdict(sortie["p_retenue"])
    return sortie


def conditions(strategie: dict, reference: dict) -> dict:
    """Les trois conditions de rendement et de risque de la regle de decision."""
    return {"sharpe_superieur": bool(strategie["sharpe"] is not None and reference["sharpe"] is not None
                                     and strategie["sharpe"] > reference["sharpe"]),
            "cagr_superieur_ou_egal": bool(strategie["cagr"] >= reference["cagr"]),
            "drawdown_moins_profond": bool(strategie["mdd"] > reference["mdd"])}


def verdict(cond: dict, p_retenue: float | None) -> str:
    """La regle de decision du preenregistrement, mecaniquement.

    confirmee  : les trois conditions ET p retenue < 0,05 ;
    indecidable: les trois conditions ET 0,05 <= p retenue < 0,20, ou p incalculable ;
    infirmee   : une condition fausse, ou p retenue >= 0,20 (hasard).
    """
    if not all(cond.values()):
        return INFIRMEE
    if p_retenue is None or (isinstance(p_retenue, float) and math.isnan(p_retenue)):
        return INDECIDABLE
    if p_retenue < SEUIL_REEL:
        return CONFIRMEE
    if p_retenue < SEUIL_HASARD:
        return INDECIDABLE
    return INFIRMEE


def par_annee(jours: pd.DatetimeIndex, r_s: np.ndarray, r_b: np.ndarray, e: np.ndarray) -> pd.DataFrame:
    """Rendement de la strategie et du hold par annee civile, exposition moyenne, bascules."""
    df = pd.DataFrame({"r_s": r_s, "r_b": r_b, "e": e}, index=jours)
    de = np.concatenate([[0.0], np.abs(np.diff(e))])
    df["bascule"] = de
    g = df.groupby(df.index.year)
    return pd.DataFrame({"strategie": g["r_s"].apply(lambda x: float(np.prod(1 + x) - 1)),
                         "hold": g["r_b"].apply(lambda x: float(np.prod(1 + x) - 1)),
                         "exposition": g["e"].mean(), "bascules": g["bascule"].sum().astype(int),
                         "jours": g.size()})
