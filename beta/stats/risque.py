"""Le risque au-dela de l'ecart-type : queues, chemin, et ce qui reste une fois le marche retire.

OUTILS INFORMATIFS (15/11/2026). Aucun n'est une porte ni un verdict ; aucun seuil de
decision ne vit ici (une regle ne change que par decision de Jonas, `DECISIONS.md`).

Le Sharpe traite une hausse brutale et une baisse brutale comme le meme risque, et ne dit
rien du chemin. Trois familles de mesures le completent :

- **queues** — Sortino (seul l'ecart a la baisse compte), Omega (gains / pertes autour d'un
  seuil, sans hypothese de loi), VaR et CVaR historiques (la perte d'un mauvais jour, et la
  perte MOYENNE des mauvais jours — la seule des deux qui voit la queue), VaR de
  Cornish-Fisher (ce que la normale sous-estime quand il y a asymetrie et queues epaisses) ;
- **chemin** — table des drawdowns (pic, creux, retour, durees), Ulcer, part du temps sous
  l'eau, CDaR, et le drawdown maximal rejoue PAR BLOCS. S4 melange les trades un a un : cela
  detruit les grappes de pertes, donc sous-estime les drawdowns d'une strategie dont les
  pertes arrivent groupees. Le bootstrap par blocs les garde ;
- **marche retire** — regression sur la reference : alpha, beta, t de l'alpha en
  Newey-West (HAC). S8 compare deux rendements ; ceci repond a la question d'a cote :
  « ce que la candidate gagne, est-ce autre chose que son exposition a la reference ? ».
  Avec la comparaison a VOLATILITE EGALE : une candidate a 1 % de risque par trade ne peut
  pas battre en rendement brut un hold investi a 100 %, sans que cela dise rien de son edge.

Deux conventions de serie :
- `rendements` : une serie de rendements ou de P&L PAR PERIODE (jour). Les ratios (Sortino,
  Omega, Sharpe) ne dependent pas de l'echelle : un P&L journalier en R convient ;
- `courbe` : une courbe de valeur, indexee par date ou non. Les drawdowns en % exigent une
  courbe positive ; la courbe du moteur (risque fixe, non composee) reste positive tant que
  la perte cumulee n'atteint pas le capital — sinon `drawdowns` le dit.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

from beta.stats import bootstrap, multitest

JOURS_AN = 365.0
NIVEAU = 0.95
N_TIRAGES = 2000


def _propre(x) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    return x[np.isfinite(x)]


# =========================================================================================
# Queues
# =========================================================================================

def sortino(rendements, cible: float = 0.0, periodes_an: float = JOURS_AN) -> float:
    """(moyenne - cible) / ecart a la baisse, annualise. NaN sans aucune periode sous la cible.

    Ecart a la baisse = racine(moyenne(min(x - cible, 0)^2)) sur TOUTES les periodes (pas
    seulement les perdantes) : la definition de Sortino & Price, la seule comparable d'une
    strategie a l'autre quand elles n'ont pas le meme nombre de jours perdants.
    """
    x = _propre(rendements)
    if len(x) < 2:
        return float("nan")
    baisse = math.sqrt(float(np.mean(np.minimum(x - cible, 0.0) ** 2)))
    return float((x.mean() - cible) / baisse * math.sqrt(periodes_an)) if baisse > 0 \
        else float("nan")


def omega(rendements, seuil: float = 0.0) -> float:
    """Somme des gains au-dessus du seuil / somme des pertes en dessous. 1 = sans edge."""
    x = _propre(rendements)
    pertes = float(np.maximum(seuil - x, 0.0).sum())
    return float(np.maximum(x - seuil, 0.0).sum() / pertes) if pertes > 0 else float("nan")


def var_cvar(rendements, niveau: float = NIVEAU) -> dict:
    """VaR et CVaR historiques, en PERTE positive, dans l'unite de la serie.

    VaR = -quantile(1 - niveau). CVaR (expected shortfall) = perte moyenne des periodes au
    moins aussi mauvaises que la VaR. `n_queue` = le nombre de periodes dans cette queue :
    a 95 % sur 400 jours, la CVaR repose sur 20 observations, et cela doit se voir.
    """
    x = _propre(rendements)
    if len(x) < 20:
        return {"niveau": niveau, "var": float("nan"), "cvar": float("nan"), "n_queue": 0}
    quantile = float(np.quantile(x, 1.0 - niveau))
    queue = x[x <= quantile]
    return {"niveau": niveau, "var": -quantile, "cvar": float(-queue.mean()),
            "n_queue": int(len(queue))}


def var_cornish_fisher(rendements, niveau: float = NIVEAU) -> dict:
    """VaR normale et VaR corrigee de l'asymetrie et des queues (Cornish-Fisher, ordre 4).

    z_cf = z + (z^2 - 1) S / 6 + (z^3 - 3 z) K / 24 - (2 z^3 - 5 z) S^2 / 36, K = aplatissement
    en EXCES. Le rapport des deux dit de combien la loi normale sous-estime la perte. Le
    developpement n'est fiable que pour des ecarts moderes a la normale : `hors_domaine`
    signale |S| > 1,5 ou K > 8 ; au-dela, lire la CVaR historique.
    """
    x = _propre(rendements)
    if len(x) < 20:
        return {"niveau": niveau, "var_normale": float("nan"), "var_cf": float("nan")}
    mu, sigma = float(x.mean()), float(x.std(ddof=1))
    s, k = float(stats.skew(x)), float(stats.kurtosis(x, fisher=True))
    z = stats.norm.ppf(1.0 - niveau)
    z_cf = (z + (z ** 2 - 1.0) * s / 6.0 + (z ** 3 - 3.0 * z) * k / 24.0
            - (2.0 * z ** 3 - 5.0 * z) * s ** 2 / 36.0)
    return {"niveau": niveau, "var_normale": -(mu + z * sigma), "var_cf": -(mu + z_cf * sigma),
            "skew": s, "kurtosis_exces": k, "hors_domaine": bool(abs(s) > 1.5 or k > 8.0)}


def ratio_des_queues(rendements) -> float:
    """|centile 95| / |centile 5| : sous 1, les mauvaises periodes pesent plus que les bonnes."""
    x = _propre(rendements)
    if len(x) < 20:
        return float("nan")
    bas = abs(float(np.quantile(x, 0.05)))
    return float(abs(np.quantile(x, 0.95)) / bas) if bas > 0 else float("nan")


# =========================================================================================
# Chemin
# =========================================================================================

def _courbe(courbe) -> pd.Series:
    s = courbe if isinstance(courbe, pd.Series) else pd.Series(np.asarray(courbe, dtype=float))
    return s.astype(float).dropna()


def sous_l_eau(courbe) -> pd.Series:
    """Drawdown courant, en fraction du dernier sommet (0 au sommet, -0,25 a -25 %)."""
    v = _courbe(courbe)
    return v / v.cummax() - 1.0


def drawdowns(courbe, n: int = 5) -> list[dict]:
    """Les `n` pires episodes de drawdown : pic, creux, retour, profondeur, durees.

    Un episode va d'un sommet a son retour au meme niveau ; `fin` vaut None s'il n'est pas
    rattrape a la fin de la serie (et `duree_retour` aussi). Les durees sont en jours si
    l'index est fait de dates, en nombre de points sinon. Courbe non positive : liste vide —
    un drawdown en % d'un sommet negatif ne veut rien dire.
    """
    v = _courbe(courbe)
    if len(v) < 2 or float(v.min()) <= 0:
        return []
    dd = (v / v.cummax() - 1.0).to_numpy()
    dates = isinstance(v.index, pd.DatetimeIndex)

    def ecart(i: int, j: int):
        return int((v.index[j] - v.index[i]).days) if dates else int(j - i)

    def etiquette(i: int):
        return v.index[i].isoformat() if dates else int(i)

    episodes, i, m = [], 0, len(v)
    while i < m:
        if dd[i] >= 0:
            i += 1
            continue
        pic = i - 1
        j = i
        while j < m and dd[j] < 0:
            j += 1
        creux = pic + 1 + int(np.argmin(dd[pic + 1:j]))
        fin = j if j < m else None
        episodes.append({
            "pic": etiquette(pic), "creux": etiquette(creux),
            "fin": etiquette(fin) if fin is not None else None,
            "profondeur": float(dd[creux]),
            "duree_baisse": ecart(pic, creux),
            "duree_retour": ecart(creux, fin) if fin is not None else None,
            "duree_totale": ecart(pic, fin if fin is not None else m - 1),
            "rattrape": fin is not None})
        i = j
    return sorted(episodes, key=lambda e: e["profondeur"])[:n]


def chemin(courbe, niveau: float = NIVEAU) -> dict:
    """Drawdown maximal, Ulcer, part du temps sous l'eau, CDaR, plus long episode.

    Ulcer = racine(moyenne(dd^2)) : penalise la profondeur ET la duree. CDaR = moyenne des
    (1 - niveau) pires valeurs du drawdown courant : le « drawdown d'un mauvais moment », la
    ou le maximum n'est qu'un point. Courbe non positive => {} avec la raison.
    """
    v = _courbe(courbe)
    if len(v) < 2:
        return {"raison": "moins de 2 points"}
    if float(v.min()) <= 0:
        return {"raison": "courbe nulle ou negative : drawdown en % sans objet"}
    dd = (v / v.cummax() - 1.0).to_numpy()
    seuil = float(np.quantile(dd, 1.0 - niveau))
    tous = drawdowns(v, n=len(v))
    return {"drawdown_max": float(dd.min()),
            "ulcer": float(math.sqrt(np.mean(dd ** 2))),
            "part_sous_l_eau": float((dd < 0).mean()),
            "cdar": float(dd[dd <= seuil].mean()), "niveau": niveau,
            "n_episodes": len(tous),
            "plus_long_episode": max((e["duree_totale"] for e in tous), default=0),
            "non_rattrape": any(not e["rattrape"] for e in tous)}


def drawdown_par_blocs(pnl, ell: float | None = None, n_tirages: int = N_TIRAGES,
                       graine: int = 0) -> dict:
    """Le drawdown maximal rejoue par blocs, sur un P&L ADDITIF (R par trade ou par jour).

    Drawdown = distance au dernier sommet de la somme cumulee, depart a 0 compris, dans
    l'unite du P&L (R). Tirage par blocs stationnaire (`bootstrap.indices`) de longueur
    moyenne `ell` (n^(1/3) par defaut, fixee d'avance) : les grappes de pertes survivent, la
    ou la permutation de S4 les dissout. `centile_observe` = part des tirages au drawdown au
    moins aussi severe que l'observe : proche de 100, l'historique reel a ete chanceux.
    `iid` refait le calcul avec des blocs de 1 : l'ecart entre les deux medianes mesure ce
    que les grappes ajoutent.
    """
    x = _propre(pnl)
    n = len(x)
    if n < 10:
        return {"n": n, "raison": "moins de 10 observations"}
    ell = bootstrap.longueur_optimale(x) if ell is None else float(ell)

    def pire(serie: np.ndarray) -> float:
        cumul = np.concatenate([[0.0], np.cumsum(serie)])
        return float((cumul - np.maximum.accumulate(cumul)).min())

    def rejouer(longueur: float, decalage: int) -> np.ndarray:
        rng = np.random.default_rng(graine + decalage)
        return np.array([pire(x[bootstrap.indices(n, n, longueur, rng)])
                         for _ in range(n_tirages)])

    observe = pire(x)
    blocs, iid = rejouer(ell, 0), rejouer(1.0, 1)

    def quantiles(d: np.ndarray) -> dict:
        return {"median": float(np.median(d)), "p5": float(np.quantile(d, 0.05)),
                "p1": float(np.quantile(d, 0.01))}

    return {"n": n, "ell": float(ell), "n_tirages": n_tirages, "observe": observe,
            "blocs": quantiles(blocs), "iid": quantiles(iid),
            "centile_observe": float((blocs <= observe).mean() * 100.0)}


# =========================================================================================
# Marche retire
# =========================================================================================

def _alignees(a, b) -> tuple[np.ndarray, np.ndarray]:
    if isinstance(a, pd.Series) and isinstance(b, pd.Series):
        commun = pd.concat([a, b], axis=1, join="inner").dropna()
        return commun.iloc[:, 0].to_numpy(dtype=float), commun.iloc[:, 1].to_numpy(dtype=float)
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if len(a) != len(b):
        raise ValueError(f"series de longueurs differentes ({len(a)} et {len(b)}) : passer "
                         "des pd.Series indexees par date, ou les aligner d'abord")
    garde = np.isfinite(a) & np.isfinite(b)
    return a[garde], b[garde]


def retards_newey_west(n: int) -> int:
    """Troncature de Newey & West (1994) : partie entiere de 4 x (n / 100)^(2/9)."""
    return max(1, int(4.0 * (n / 100.0) ** (2.0 / 9.0))) if n > 1 else 0


def alpha_beta(candidate, reference, retards: int | None = None,
               periodes_an: float = JOURS_AN) -> dict:
    """Regression candidate = alpha + beta x reference + residu, erreurs HAC de Newey-West.

    Les deux series sont des rendements de MEME periode (pd.Series : alignees sur les dates
    communes). L'erreur-type de l'alpha tient compte de l'autocorrelation et de
    l'heteroscedasticite des residus (noyau de Bartlett, `retards_newey_west`) : l'erreur
    ordinaire des moindres carres est trop petite sur des rendements a volatilite groupee.

    Rend alpha (par periode et annualise), beta, t et p unilaterale de l'alpha (H1 : alpha > 0),
    R2, correlation, erreur de suivi et ratio d'information annualises. L'alpha depend de
    l'ECHELLE de la candidate : sur un P&L en R, seul son t se lit ; sur deux series de
    rendements en fraction, sa valeur aussi.
    """
    y, x = _alignees(candidate, reference)
    n = len(y)
    vide = {"n": n, "alpha": float("nan"), "beta": float("nan"), "t_alpha": float("nan"),
            "p_alpha": float("nan"), "r2": float("nan")}
    if n < 30 or float(np.var(x)) <= 0 or float(np.var(y)) <= 0:
        return vide
    plan = np.column_stack([np.ones(n), x])
    xtx_inv = np.linalg.inv(plan.T @ plan)
    coefficients = xtx_inv @ plan.T @ y
    residus = y - plan @ coefficients
    retards = retards_newey_west(n) if retards is None else int(retards)

    scores = plan * residus[:, None]
    milieu = scores.T @ scores
    for k in range(1, min(retards, n - 1) + 1):
        poids = 1.0 - k / (retards + 1.0)
        croise = scores[k:].T @ scores[:-k]
        milieu += poids * (croise + croise.T)
    covariance = xtx_inv @ milieu @ xtx_inv * (n / (n - 2))
    es_alpha, es_beta = (math.sqrt(max(float(covariance[i, i]), 0.0)) for i in (0, 1))
    alpha, beta = float(coefficients[0]), float(coefficients[1])
    t_alpha = alpha / es_alpha if es_alpha > 0 else float("nan")
    actif = y - x
    suivi = float(actif.std(ddof=1))
    return {
        "n": n, "retards": retards, "alpha": alpha, "alpha_annuel": alpha * periodes_an,
        "beta": beta, "es_alpha": es_alpha, "es_beta": es_beta, "t_alpha": float(t_alpha),
        "p_alpha": float(stats.t.sf(t_alpha, n - 2)) if np.isfinite(t_alpha) else float("nan"),
        "r2": float(1.0 - (residus @ residus) / float(((y - y.mean()) ** 2).sum())),
        "correlation": float(np.corrcoef(y, x)[0, 1]),
        "erreur_de_suivi_annuelle": suivi * math.sqrt(periodes_an),
        "ratio_information": (float(actif.mean() / suivi * math.sqrt(periodes_an))
                              if suivi > 0 else float("nan"))}


def a_volatilite_egale(candidate, reference, periodes_an: float = JOURS_AN) -> dict:
    """La candidate ramenee a la volatilite de la reference, puis comparee.

    Levier k = sigma(reference) / sigma(candidate). Le rendement moyen annualise de la
    candidate x k se compare alors a celui de la reference : l'ecart vaut exactement
    (Sharpe candidate - Sharpe reference) x volatilite annuelle de la reference. C'est la
    lecture en « points de rendement par an » d'un ecart de Sharpe, sans composition ni cout
    de levier : un ordre de grandeur, pas un compte.
    """
    y, x = _alignees(candidate, reference)
    if len(y) < 30:
        return {"n": len(y), "levier": float("nan")}
    sy, sx = float(y.std(ddof=1)), float(x.std(ddof=1))
    if sy <= 0 or sx <= 0:
        return {"n": len(y), "levier": float("nan")}
    k = sx / sy
    racine = math.sqrt(periodes_an)
    return {"n": len(y), "levier": k,
            "volatilite_reference_annuelle": sx * racine,
            "rendement_candidate_annuel": float(y.mean() * k * periodes_an),
            "rendement_reference_annuel": float(x.mean() * periodes_an),
            "ecart_annuel": float((y.mean() * k - x.mean()) * periodes_an),
            "sharpe_candidate": multitest.sharpe(y) * racine,
            "sharpe_reference": multitest.sharpe(x) * racine}
