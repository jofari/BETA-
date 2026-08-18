"""Ce qu'un ensemble de trades a donne : R moyen, rendement, profit factor — et le MDE.

Le MDE n'est pas une metrique parmi d'autres, c'est **la premiere a lire**. Il repond a la
question qui precede toutes les autres : *suis-je seulement capable de voir un edge avec cet
echantillon ?* Un R moyen de +0,15 sur 40 trades et un R moyen de +0,15 sur 4 000 trades ne
sont pas le meme resultat — le premier est du bruit, le second une decouverte. Sans le MDE
affiche a cote, les deux se lisent pareil.

D'ou la regle : **toute sortie de ce module porte son MDE**. On ne publie pas un profit
factor tout seul.

Ce module ne sait pas ce qu'est une strategie. Il ne voit que des colonnes `r` et
`rendement_pct` — ce qui lui permet de traiter indifferemment un backtest freqtrade, un
rejeu hors-ligne, ou le futur moteur BETA.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

# alpha = 0,05 unilateral, puissance 80 % : z(1-alpha) + z(1-beta)
Z_MDE = 2.487
# n effectif = n / 1,6. Les trades se chevauchent (positions simultanees sur des paires
# correlees) : compter n trades independants surestime la puissance disponible.
CHEVAUCHEMENT = 1.6
N_MIN_PF = 2


def mde(n: int, sigma_r: float, effectif: bool = True) -> float:
    """Plus petit effet detectable, en R par trade. NaN si l'echantillon ne permet rien."""
    if n <= 1 or not sigma_r or math.isnan(sigma_r):
        return float("nan")
    return Z_MDE * sigma_r / math.sqrt(n / CHEVAUCHEMENT if effectif else n)


def profit_factor(rendements: pd.Series) -> float:
    """Somme des gains / valeur absolue de la somme des pertes.

    Infini si aucune perte : on rend NaN plutot qu'un `inf` qui se propagerait dans une
    moyenne et contaminerait un tableau entier.
    """
    gains = rendements[rendements > 0].sum()
    pertes = rendements[rendements < 0].sum()
    if not pertes:
        return float("nan")
    return float(gains / abs(pertes))


def resumer(trades: pd.DataFrame) -> dict:
    """Le profil d'un ensemble de trades. `r` absent => les metriques en R restent NaN."""
    n = len(trades)
    if not n:
        return {"n": 0}
    r = trades["r"].dropna() if "r" in trades.columns else pd.Series(dtype=float)
    rendement = (trades["rendement_pct"].dropna() if "rendement_pct" in trades.columns
                 else pd.Series(dtype=float))
    sigma = float(r.std(ddof=1)) if len(r) > 1 else float("nan")
    resume = {
        "n": n,
        "n_avec_r": len(r),
        "r_moyen": float(r.mean()) if len(r) else float("nan"),
        "r_median": float(r.median()) if len(r) else float("nan"),
        "r_sigma": sigma,
        "r_total": float(r.sum()) if len(r) else float("nan"),
        "mde_r": mde(len(r), sigma),
        "rendement_moyen_pct": float(rendement.mean()) if len(rendement) else float("nan"),
        "rendement_total_pct": float(rendement.sum()) if len(rendement) else float("nan"),
        "win_rate": float((r > 0).mean()) if len(r) else float("nan"),
        "profit_factor": (profit_factor(rendement) if len(rendement) >= N_MIN_PF
                          else float("nan")),
    }
    for colonne, cle in (("rendement_abs", "rendement_abs_total"),):
        if colonne in trades.columns:
            resume[cle] = float(trades[colonne].dropna().sum())
    for colonne, cle in (("mfe_r", "mfe_r_moyen"), ("mae_r", "mae_r_moyen"),
                         ("duree_h", "duree_h_mediane")):
        if colonne in trades.columns:
            valeurs = trades[colonne].replace([np.inf, -np.inf], np.nan).dropna()
            if len(valeurs):
                resume[cle] = float(valeurs.median() if cle.endswith("mediane")
                                    else valeurs.mean())
    return resume


def par(trades: pd.DataFrame, *cles: str) -> pd.DataFrame:
    """Le meme resume, ventile. `par(trades, "strategie")`, `par(trades, "paire", "sens")`.

    Les groupes sont conserves meme minuscules : c'est justement la taille du groupe qui
    doit sauter aux yeux, a cote de son MDE. Les masquer donnerait un tableau propre et
    trompeur.
    """
    cles = tuple(c for c in cles if c in trades.columns)
    if not cles:
        return pd.DataFrame([resumer(trades)])
    lignes = []
    for valeurs, groupe in trades.groupby(list(cles), dropna=False):
        valeurs = valeurs if isinstance(valeurs, tuple) else (valeurs,)
        lignes.append({**dict(zip(cles, valeurs, strict=True)), **resumer(groupe)})
    return pd.DataFrame(lignes).sort_values("n", ascending=False).reset_index(drop=True)


def raisons_de_sortie(trades: pd.DataFrame) -> pd.DataFrame:
    """Combien de trades par raison de sortie, et ce que chaque raison rapporte.

    C'est souvent la table la plus instructive d'un backtest : elle dit quelle regle ferme
    reellement les positions, et si elle les ferme bien.
    """
    if "raison_sortie" not in trades.columns:
        return pd.DataFrame()
    return par(trades, "raison_sortie")


def raisons_de_rejet(evaluations: pd.DataFrame) -> pd.DataFrame:
    """Quelle porte bloque, et combien de fois — la moitie invisible d'une strategie.

    Les trades pris ne disent rien du filtrage. Cette table dit ce qui a ete ecarte, et par
    quoi : c'est la seule facon de savoir si une porte fait son travail ou si elle est
    inerte (ou pire, si elle bloque tout).
    """
    colonne = next((c for c in ("failed_gate", "raison", "decision")
                    if c in evaluations.columns), None)
    if colonne is None:
        return pd.DataFrame()
    compte = (evaluations[colonne].fillna("(aucune)").value_counts()
              .rename_axis(colonne).reset_index(name="n"))
    compte["part_pct"] = (100 * compte["n"] / compte["n"].sum()).round(2)
    return compte
