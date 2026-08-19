"""S1, S2, S7 — ce qui reste d'un resultat quand on compte tous les essais.

Trois outils qui repondent a la meme question sous trois angles : *combien de fois ai-je
regarde avant de trouver ca ?*

- **S1 Benjamini-Hochberg** — sur une famille de tests declaree, controle la proportion
  attendue de faux positifs parmi les rejets (FDR), plutot que la probabilite d'en faire un
  seul (FWER). Moins brutal que Bonferroni, et adapte a une exploration ;
- **S2 Sharpe degonfle (DSR)** — Bailey & Lopez de Prado (2014). Le Sharpe maximal de N
  essais sur du bruit pur n'est pas 0 : il croit comme sqrt(2 ln N). Le DSR retire cette
  esperance avant de conclure ;
- **S7 Reality Check de White / SPA de Hansen** — la p-value du MAXIMUM d'un univers de N
  candidates, obtenue par bootstrap. C'est le test correct quand on choisit la meilleure
  d'un lot : la p-value de la gagnante prise isolement n'a aucun sens.

Le N qui alimente S2 et S7 vient du compteur cumulatif de `protocole.experiences`, qui part
de 30 et ne redescend jamais. C'est la seule facon d'honorer les essais qu'on a faits et
oublies — le biais principal, celui qui ne laisse aucune trace si on ne le compte pas.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

from beta.stats import bootstrap

FDR_DEFAUT = 0.10
EULER = 0.5772156649015329        # gamma d'Euler-Mascheroni, dans l'esperance du maximum


def benjamini_hochberg(table: pd.DataFrame, fdr: float = FDR_DEFAUT,
                       colonne: str = "p_brute") -> pd.DataFrame:
    """Procedure BH sur la famille ENTIERE de `table`. Ajoute rang, seuil_BH, signif_BH.

    Portage de `ARIT2.0/analysis/mesures.py:benjamini_hochberg`, garde identique pour que
    les deux projets restent comparables.

    Un test survit si p <= (rang / m) x fdr, m = taille de la famille. Appliquer BH a un
    sous-ensemble choisi APRES avoir vu les resultats revient a ne pas l'appliquer : c'est
    la fraude methodologique la plus courante et la plus facile a commettre de bonne foi.
    """
    if table.empty:
        return table
    out = table.sort_values(colonne).reset_index(drop=True)
    m = len(out)
    out["rang"] = out.index + 1
    out["seuil_BH"] = out["rang"] / m * fdr
    survivants = out.index[out[colonne] <= out["seuil_BH"]]
    coupure = survivants.max() if len(survivants) else -1
    out["signif_BH"] = out.index <= coupure
    return out


def sharpe(rendements: np.ndarray) -> float:
    """Sharpe NON annualise, par observation. L'annualisation est un choix d'affichage."""
    x = np.asarray(rendements, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return float("nan")
    sigma = x.std(ddof=1)
    return float(x.mean() / sigma) if sigma else float("nan")


def sharpe_attendu_du_maximum(n_essais: int, variance_sharpe: float = 1.0) -> float:
    """E[max Sharpe] de n_essais independants sur du bruit pur (Bailey & LdP, eq. 5).

    C'est le chiffre qui manque a tous les backtests : sur 30 essais, un Sharpe de 2 tire du
    bruit n'est pas surprenant. Sans ce seuil, on prend l'extremum d'une distribution nulle
    pour une decouverte.
    """
    n = max(int(n_essais), 2)
    ecart = math.sqrt(max(variance_sharpe, 0.0))
    z1 = stats.norm.ppf(1.0 - 1.0 / n)
    z2 = stats.norm.ppf(1.0 - 1.0 / (n * math.e))
    return ecart * ((1.0 - EULER) * z1 + EULER * z2)


def sharpe_degonfle(rendements: np.ndarray, n_essais: int,
                    variance_sharpe: float | None = None) -> dict:
    """DSR : probabilite que le Sharpe observe depasse celui qu'on attend du hasard.

    Le denominateur corrige l'asymetrie et l'aplatissement : une strategie a queue gauche
    epaisse (ce que produit tout stop-loss) a un Sharpe moins fiable a longueur egale, et le
    Sharpe brut ne le dit pas.

    Lecture : DSR > 0,95 signifie « ce Sharpe reste improbable sous le hasard une fois
    l'echantillonnage de N essais paye ». Ce n'est PAS une probabilite que la strategie
    fonctionne.
    """
    x = np.asarray(rendements, dtype=float)
    x = x[np.isfinite(x)]
    t = len(x)
    sr = sharpe(x)
    resultat = {"n": t, "sharpe": sr, "n_essais": n_essais,
                "sharpe_seuil": float("nan"), "dsr": float("nan"),
                "skew": float("nan"), "kurtosis": float("nan")}
    if t < 3 or not np.isfinite(sr):
        return resultat
    skew = float(stats.skew(x))
    kurt = float(stats.kurtosis(x, fisher=False))     # non centree : 3 pour une normale
    # Variance du Sharpe sous H0, en l'absence d'estimation externe : 1/(T-1) est
    # l'approximation usuelle et volontairement prudente.
    var_sr = (1.0 / (t - 1)) if variance_sharpe is None else variance_sharpe
    seuil = sharpe_attendu_du_maximum(n_essais, var_sr)
    denominateur = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr ** 2
    if denominateur <= 0:
        resultat.update({"sharpe_seuil": seuil, "skew": skew, "kurtosis": kurt})
        return resultat
    z = (sr - seuil) * math.sqrt(t - 1) / math.sqrt(denominateur)
    resultat.update({"sharpe_seuil": seuil, "dsr": float(stats.norm.cdf(z)),
                     "skew": skew, "kurtosis": kurt})
    return resultat


def _matrice(series: dict[str, np.ndarray]) -> tuple[list[str], np.ndarray]:
    """Aligne des series de longueurs differentes sur la plus courte, sans les melanger."""
    noms = list(series)
    if not noms:
        return [], np.empty((0, 0))
    longueur = min(len(series[n]) for n in noms)
    return noms, np.column_stack([np.asarray(series[n], dtype=float)[:longueur]
                                  for n in noms])


def reality_check(series: dict[str, np.ndarray], n_repetitions: int = 1000,
                  ell: float | None = None, graine: int = 0,
                  studentise: bool = True) -> dict:
    """S7 — p-value du MEILLEUR d'un univers de candidates (White 2000, Hansen 2005).

    `series` : une entree par candidate, chacune une serie de performances DEJA relatives a
    la reference (par exemple R par trade, ou rendement moins buy-and-hold). H0 : aucune
    candidate ne bat la reference.

    La statistique est le maximum sur les candidates de sqrt(T) x moyenne. Sa distribution
    sous H0 s'obtient en recentrant chaque colonne sur sa propre moyenne puis en
    rebootstrappant par blocs — de sorte que la dependance temporelle ET la correlation
    entre candidates soient conservees, ce qu'une correction de Bonferroni ignore.

    `studentise=True` donne le SPA de Hansen : diviser par l'ecart-type empeche une
    candidate tres volatile et sans edge de dominer la statistique du maximum.
    """
    noms, matrice = _matrice(series)
    if not noms or matrice.shape[0] < 3:
        return {"n_candidates": len(noms), "p_value": float("nan"), "meilleure": None}
    t, k = matrice.shape
    moyennes = matrice.mean(axis=0)
    echelle = matrice.std(axis=0, ddof=1) if studentise else np.ones(k)
    echelle = np.where(echelle > 0, echelle, np.nan)

    observe = np.nanmax(math.sqrt(t) * moyennes / echelle)
    centre = matrice - moyennes                     # H0 : moyenne nulle pour chacune
    ell = bootstrap.longueur_optimale(matrice[:, 0]) if ell is None else ell
    rng = np.random.default_rng(graine)

    maxima = np.empty(n_repetitions)
    for i in range(n_repetitions):
        tirage = centre[bootstrap.indices(t, t, ell, rng)]
        maxima[i] = np.nanmax(math.sqrt(t) * tirage.mean(axis=0) / echelle)
    p = (int((maxima >= observe).sum()) + 1) / (n_repetitions + 1)
    return {"n_candidates": k, "n_observations": t, "statistique": float(observe),
            "p_value": float(p), "ell": float(ell),
            "meilleure": noms[int(np.nanargmax(moyennes / echelle))],
            "moyennes": {n: float(m) for n, m in zip(noms, moyennes, strict=True)}}
