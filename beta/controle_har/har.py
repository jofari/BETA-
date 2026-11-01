"""Controle HAR : les calculs, en fonctions pures (aucune lecture, aucune ecriture).

RV journaliere sur barres 5 min, ecart-type 30 jours, HAR en MCO glissants, replis, QLIKE et
Diebold-Mariano. Regles : beta.controle_har.regles (gelees). Toutes les fenetres glissantes sont
calculees fenetre par fenetre (sliding_window_view) : une valeur ne depend que des jours de sa
fenetre, et une fenetre qui contient un jour sans valeur n'est pas formee.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
from scipy import stats

from beta.controle_har import regles as R

PAS = pd.Timedelta(minutes=5)


def _glissant(v: np.ndarray, n: int, f, **kw) -> np.ndarray:
    """f sur la fenetre des n valeurs finissant en i ; NaN si incomplete ou si une valeur manque."""
    out = np.full(len(v), np.nan)
    if len(v) >= n:
        out[n - 1:] = f(sliding_window_view(v, n), axis=1, **kw)
    return out


def rv_journaliere(barres: pd.DataFrame) -> pd.DataFrame:
    """Par jour civil UTC, du premier au dernier jour des barres : barres presentes, manquantes,
    barres a volume nul, rendements, RV et marque d'exclusion (RV = NaN si le jour est exclu).

    Rendement d'une barre = ln(cloture / cloture de la barre ouverte 5 min avant), jamais a travers
    un trou ; la premiere barre du jour D se rapporte a la derniere barre de D - 1.
    """
    t = barres.index
    c = barres["close"].to_numpy(dtype=float)
    r = np.full(len(c), np.nan)
    if len(c) > 1:
        suit = np.asarray((t[1:] - t[:-1]) == PAS)
        r[1:] = np.where(suit, np.log(c[1:] / c[:-1]), np.nan)
    df = pd.DataFrame({"jour": t.tz_convert(None).normalize(), "r2": r ** 2,
                       "a_rendement": np.isfinite(r),
                       "volume_nul": barres["volume"].to_numpy(dtype=float) == 0.0})
    g = df.groupby("jour")
    out = pd.DataFrame({"barres": g.size(), "rendements": g["a_rendement"].sum(),
                        "volume_nul": g["volume_nul"].sum(),
                        "somme_r2": g["r2"].sum(min_count=1)})
    out = out.reindex(pd.date_range(out.index.min(), out.index.max(), freq="D"))
    for col in ("barres", "rendements", "volume_nul"):
        out[col] = out[col].fillna(0).astype(int)
    out["manquantes"] = R.BARRES_PAR_JOUR - out["barres"]
    out["exclu"] = out["manquantes"] > R.PART_MANQUANTE_MAX * R.BARRES_PAR_JOUR
    out["rv"] = out["somme_r2"].where(~out["exclu"])
    return out


def ecart_type_30(close_1d: pd.Series) -> pd.Series:
    """Variance journaliere : ecart-type d'echantillon (ddof 1) des 30 derniers rendements log
    journaliers, jour t compris, au carre. Un rendement n'existe qu'entre deux jours consecutifs."""
    jours = close_1d.index
    r = np.log(close_1d.astype(float)).diff()
    r = r.where(pd.Series(jours, index=jours).diff() == pd.Timedelta(days=1))
    r = r.reindex(pd.date_range(jours.min(), jours.max(), freq="D"))
    v = _glissant(r.to_numpy(dtype=float), R.FENETRE_ECART_TYPE, np.var, ddof=R.DDOF)
    return pd.Series(v, index=r.index, name="ecart_type")


def regresseurs(rv: pd.Series) -> pd.DataFrame:
    """RV du jour, moyennes 5 et 22 jours (jour t compris) et cible = moyenne des RV de t+1 a
    t+5. L'index de `rv` est le calendrier complet (un jour par ligne)."""
    v = rv.to_numpy(dtype=float)
    d, w, m = R.FENETRES_HAR
    x = pd.DataFrame({"rv_jour": _glissant(v, d, np.mean), "rv_5": _glissant(v, w, np.mean),
                      "rv_22": _glissant(v, m, np.mean)}, index=rv.index)
    x["cible"] = pd.Series(_glissant(v, R.HORIZON, np.mean), index=rv.index).shift(-R.HORIZON)
    return x


def har(rv: pd.Series) -> pd.DataFrame:
    """Prevision HAR brute de la cible a chaque jour t (NaN tant que la fenetre n'est pas pleine).

    MCO avec constante sur les lignes s entierement dans la fenetre des 730 derniers jours ayant
    une RV (t compris) : regresseurs de s - 21 a s, cible de s + 1 a s + 5 <= t. La prevision de t
    applique les coefficients aux regresseurs de t. Colonnes : prevision, jours_rv, lignes, b0-b3.
    """
    x = regresseurs(rv)
    v = rv.to_numpy(dtype=float)
    a_rv = np.isfinite(v)
    jours_rv = np.cumsum(a_rv)
    pos_rv = np.flatnonzero(a_rv)
    X = np.column_stack([np.ones(len(v)), x[["rv_jour", "rv_5", "rv_22"]].to_numpy()])
    y = x["cible"].to_numpy()
    ligne_ok = np.isfinite(X).all(axis=1) & np.isfinite(y)
    avant, apres = R.FENETRES_HAR[-1] - 1, R.HORIZON
    prev = np.full(len(v), np.nan)
    lignes = np.zeros(len(v), dtype=int)
    coefs = np.full((len(v), X.shape[1]), np.nan)
    for t in range(len(v)):
        if jours_rv[t] < R.FENETRE_MCO or not np.isfinite(X[t]).all():
            continue
        debut = pos_rv[jours_rv[t] - R.FENETRE_MCO]
        s = np.arange(debut + avant, t - apres + 1)
        s = s[ligne_ok[s]]
        if len(s) < X.shape[1]:
            continue
        beta, *_ = np.linalg.lstsq(X[s], y[s], rcond=None)
        prev[t], lignes[t], coefs[t] = X[t] @ beta, len(s), beta
    out = pd.DataFrame({"prevision": prev, "jours_rv": jours_rv, "lignes": lignes},
                       index=rv.index)
    for k in range(X.shape[1]):
        out[f"b{k}"] = coefs[:, k]
    return out


def replis(prevision_har: pd.Series, jours_rv: pd.Series,
           ecart: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Prevision du HAR apres replis : ecart-type 30 jours avant 730 jours de RV et les jours ou
    la prevision HAR est <= 0. Rend (prevision, avant_730, negative_ou_nulle)."""
    avant = jours_rv < R.FENETRE_MCO
    negative = prevision_har.notna() & (prevision_har <= 0)
    return prevision_har.where(~(avant | negative), ecart), avant, negative


def qlike(rv, h):
    """Perte de Patton : RV/h - ln(RV/h) - 1 (0 si la prevision est exacte)."""
    ratio = rv / h
    return ratio - np.log(ratio) - 1.0


def diebold_mariano(d: np.ndarray) -> dict:
    """Stat DM et p bilaterale (loi normale) ; variance de long terme de Newey-West, noyau de
    Bartlett, retard int(4 (n/100)^(2/9)). Meme formule que voie_c6_vol.diebold_mariano."""
    d = np.asarray(d, dtype=float)
    d = d[np.isfinite(d)]
    n = len(d)
    if n < 30:
        return {"stat": None, "p": None, "retard": None, "n": n}
    retard = int(4 * (n / 100) ** (2 / 9))
    u = d - d.mean()
    var = u @ u / n
    for k in range(1, retard + 1):
        var += 2 * (1 - k / (retard + 1)) * (u[k:] @ u[:-k]) / n
    if not var > 0:
        return {"stat": None, "p": None, "retard": retard, "n": n}
    stat = d.mean() / math.sqrt(var / n)
    return {"stat": stat, "p": 2 * stats.norm.sf(abs(stat)), "retard": retard, "n": n}


def decision(qlike_har: float, qlike_ecart: float) -> str:
    """Regle 5 : l'ecart-type 30 jours si la QLIKE moyenne du HAR est strictement plus haute."""
    return R.ECART_TYPE if qlike_har > qlike_ecart else R.HAR
