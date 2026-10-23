"""VC6 — deux indicateurs de volatilite autonomes : HAR-RV et EGARCH(1,1).

    PYTHONPATH=/root/BETA- /root/venvs/arit/bin/python beta/strategies/voie_c6_indicateurs.py

Deux fonctions pures, sans cablage production, sans backtest, sans combinaison :

  har_rv(ohlc)       Corsi (2009). RV_t par Garman-Klass (defaut) ou Parkinson, puis
                     RV_t = b0 + b1 RV_{t-1} + b2 moy5(RV)_{t-1} + b3 moy22(RV)_{t-1}, MCO.
  egarch(rendements) Nelson (1991), EGARCH(1,1) gaussien, QMLE scipy :
                     ln s2_t = w + a (|z_{t-1}| - E|z|) + g z_{t-1} + b ln s2_{t-1},
                     mu fixe et ciblage de variance (cf. ajuster_egarch).

Causalite stricte : la valeur a l'index t est la prevision de la variance du jour t et
n'utilise que des donnees <= t-1, COEFFICIENTS COMPRIS. Un MCO ou un MLE ajuste une fois sur
tout l'echantillon ferait lire le futur a chaque prevision passee ; ici :
  - HAR : MCO en fenetre GLISSANTE (250 j), re-estime chaque jour sur les seuls couples
    (x_s, RV_s) avec t-250 <= s <= t-1 ;
  - EGARCH : re-estime tous les `pas` jours en fenetre GLISSANTE (250 j) ; les parametres
    du bloc [k, k+pas) sont ajustes sur r_{k-250}..r_{k-1}, puis le filtre tourne avec eux
    depuis le debut de cette meme fenetre.
Fenetre glissante et non croissante (16/10) : en croissante, 2019-2020 ne sortait jamais de
l'estimation, l'intercept restait cale sur un regime disparu et la prevision ne descendait
jamais sous ~47 % de vol annualisee (moyenne ~74 % contre ~57 % realise).
Les bornes de bloc sont fixees par la position depuis le debut de la serie, si bien que
f(x[:t]) == f(x)[:t] (verifie par la demo, l'epreuve de causalite de l'invariant 7).

Unites : variance JOURNALIERE de log-rendement (pas annualisee). La demo annualise
(racine de 365 x variance, marche 24/7) pour l'affichage seulement.

Ce fichier n'est ni une candidate ni une mesure : il n'imprime aucune perte de prevision,
aucun test, aucun verdict. Sa demo lit le train seulement (`holdout.borner_train()`).
"""

from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd
from scipy import optimize

log = logging.getLogger("beta.strategies.voie_c6_indicateurs")

E_ABS_Z = math.sqrt(2.0 / math.pi)   # E|z| pour z ~ N(0, 1)
PLANCHER = 1e-10                     # variance minimale rendue (un HAR en niveaux peut passer < 0)


# --------------------------------------------------------------------------- RV quotidienne

def variance_realisee(ohlc: pd.DataFrame, methode: str = "gk") -> pd.Series:
    """Variance du jour t estimee sur la seule bougie t (pas de decalage ici).

    gk         Garman-Klass : 0.5 ln(H/L)^2 - (2 ln 2 - 1) ln(C/O)^2
    parkinson  ln(H/L)^2 / (4 ln 2)
    Colonnes attendues : open, high, low, close (minuscules).
    """
    hl = np.log(ohlc["high"] / ohlc["low"])
    if methode == "parkinson":
        rv = hl ** 2 / (4.0 * math.log(2.0))
    elif methode == "gk":
        co = np.log(ohlc["close"] / ohlc["open"])
        rv = 0.5 * hl ** 2 - (2.0 * math.log(2.0) - 1.0) * co ** 2
    else:
        raise ValueError(f"methode inconnue : {methode!r} (gk ou parkinson)")
    # GK peut etre negatif sur une bougie sans meche ; une variance ne l'est pas.
    return rv.clip(lower=0.0).rename("rv")


# --------------------------------------------------------------------------- HAR-RV

def har_rv(ohlc: pd.DataFrame, methode: str = "gk", fenetre: int = 250,
           min_obs: int = 250) -> pd.Series:
    """Prevision HAR-RV de la variance du jour t, a partir de donnees <= t-1.

    Regresseurs connus a t-1 : RV_{t-1}, moyenne 5j et 22j de RV finissant en t-1.
    Coefficients : MCO sur les couples (x_s, RV_s) avec t-fenetre <= s <= t-1, re-estimes
    chaque jour (fenetre GLISSANTE : l'intercept suit le regime de vol courant au lieu de
    rester cale sur 2019-2020). NaN tant que moins de `min_obs` couples valides sont dans la
    fenetre. Plancher a PLANCHER.
    """
    rv = variance_realisee(ohlc, methode)
    x = pd.DataFrame({
        "rv1": rv.shift(1),
        "rv5": rv.rolling(5).mean().shift(1),
        "rv22": rv.rolling(22).mean().shift(1),
    })
    X = np.column_stack([np.ones(len(x)), x.to_numpy()])
    y = rv.to_numpy()
    ok = np.isfinite(X).all(axis=1) & np.isfinite(y)

    prev = np.full(len(y), np.nan)
    for t in range(len(y)):
        if not np.isfinite(X[t]).all():
            continue
        # Couples s dans [t-fenetre, t-1] : la ligne t elle-meme n'entre pas.
        s = slice(max(0, t - fenetre), t)
        m = ok[s]
        if m.sum() < min_obs:
            continue
        beta, *_ = np.linalg.lstsq(X[s][m], y[s][m], rcond=None)
        prev[t] = X[t] @ beta
    prev = np.where(np.isfinite(prev), np.maximum(prev, PLANCHER), np.nan)
    return pd.Series(prev, index=ohlc.index, name="har")


# --------------------------------------------------------------------------- EGARCH(1,1)

def _filtre_egarch(r: np.ndarray, params: np.ndarray, ln_s2_0: float) -> np.ndarray:
    """ln s2_t pour t = 0..n (n+1 valeurs) ; ln s2_t ne depend que de r_0..r_{t-1}."""
    mu, w, a, g, b = params
    ln_s2 = np.empty(len(r) + 1)
    ln_s2[0] = ln_s2_0
    for t in range(len(r)):
        z = (r[t] - mu) * math.exp(-0.5 * ln_s2[t])
        ln_s2[t + 1] = w + a * (abs(z) - E_ABS_Z) + g * z + b * ln_s2[t]
        ln_s2[t + 1] = min(max(ln_s2[t + 1], -50.0), 50.0)  # garde-fou numerique
    return ln_s2


def _neg_log_vrais(params: np.ndarray, r: np.ndarray, ln_s2_0: float) -> float:
    ln_s2 = _filtre_egarch(r, params, ln_s2_0)[:-1]
    e = r - params[0]
    return 0.5 * float(np.sum(math.log(2.0 * math.pi) + ln_s2 + e ** 2 * np.exp(-ln_s2)))


# (a, g, b) ; mu et w ne sont pas libres, cf. ajuster_egarch. b >= 0 et <= 0.99 : sur 250
# jours, b libre jusqu'a 0.9999 partait en butee (marche aleatoire en log-variance).
_BORNES = [(-1.0, 2.0), (-1.0, 1.0), (0.0, 0.99)]


def ajuster_egarch(r: np.ndarray) -> tuple[np.ndarray, float]:
    """QMLE gaussien d'un EGARCH(1,1) sur r (en %). Rend (mu, w, a, g, b) et ln s2_0.

    Sur une fenetre courte (250 j) le QMLE a 5 parametres libres n'est pas identifie :
    w et b partent en butee, mu absorbe la tendance et la log-variance derive jusqu'a des
    vols de 2 %. D'ou deux contraintes standard :
      - mu fixe a la moyenne de la fenetre ;
      - ciblage de variance : w = (1 - b) ln var(r), le niveau de long terme EST celui de
        la fenetre (c'est le regime courant que la fenetre glissante doit suivre).
    Depart a froid a chaque appel : pas de dependance au chemin des blocs precedents.
    """
    mu = float(np.mean(r))
    ln_s2_0 = math.log(max(float(np.var(r)), PLANCHER))

    def complets(p: np.ndarray) -> np.ndarray:
        a, g, b = p
        return np.array([mu, (1.0 - b) * ln_s2_0, a, g, b])

    res = optimize.minimize(lambda p: _neg_log_vrais(complets(p), r, ln_s2_0),
                            np.array([0.15, -0.05, 0.9]), method="L-BFGS-B", bounds=_BORNES)
    if not res.success:
        log.warning("EGARCH : optimiseur non converge (%s)", res.message)
    return complets(res.x), ln_s2_0


def egarch(rendements: pd.Series, pas: int = 21, fenetre: int = 250,
           min_obs: int = 250) -> pd.Series:
    """Prevision EGARCH(1,1) de la variance du jour t, a partir de rendements <= t-1.

    `rendements` : log-rendements journaliers (decimaux), index temporel. Le rendement a
    l'index t est celui du jour t ; la prevision a l'index t ne le lit pas.
    Re-estimation tous les `pas` jours en fenetre GLISSANTE : les parametres du bloc
    [k, k+pas) sont ajustes sur r_{k-fenetre}..r_{k-1} seulement, la premiere fois quand
    `min_obs` rendements valides precedent (cf. ajuster_egarch pour les contraintes). Le filtre
    repart lui aussi du debut de la fenetre (etat initial = ln var de la fenetre), pour que
    rien d'anterieur a k-fenetre n'entre dans la prevision.
    Les NaN de tete (premier rendement) sont ecartes ; un NaN interne est une erreur.
    """
    serie = rendements.loc[rendements.first_valid_index():]
    if serie.isna().any():
        raise ValueError("rendements : NaN hors de la tete de serie")
    r = serie.to_numpy() * 100.0   # en %, l'optimiseur est mieux conditionne
    n = len(r)
    prev = np.full(n, np.nan)
    for k in range(max(min_obs, 1), n, pas):
        debut = max(0, k - fenetre)
        params, ln_s2_0 = ajuster_egarch(r[debut:k])
        fin = min(k + pas, n)
        # Filtre depuis le debut de la fenetre : ln_s2[i] lit r_debut..r_{debut+i-1}.
        ln_s2 = _filtre_egarch(r[debut:fin - 1], params, ln_s2_0)
        prev[k:fin] = np.exp(ln_s2[k - debut:fin - debut]) / 1e4
        log.debug("EGARCH bloc %s : %s", serie.index[k].date(), np.round(params, 4))
    out = pd.Series(prev, index=serie.index, name="egarch").reindex(rendements.index)
    return out


# --------------------------------------------------------------------------- demo

def _vol_annuelle(var: pd.Series) -> pd.Series:
    return np.sqrt(var * 365.0) * 100.0


def demo(paire: str = "BTC") -> pd.DataFrame:
    from beta.lake.lecture import load
    from beta.protocole import holdout

    df = load(paire, "1d", fin=holdout.borner_train(),
              colonnes=("open", "high", "low", "close")).set_index("date")
    r = np.log(df["close"]).diff()

    har = har_rv(df)
    eg = egarch(r)
    r30 = r.rolling(30).var().shift(1)   # vol glissante 30j, connue a t-1

    # Epreuve de causalite : f(x[:t]) == f(x)[:t].
    coupe = len(df) - 200
    assert np.allclose(har_rv(df.iloc[:coupe]), har.iloc[:coupe], equal_nan=True)
    assert np.allclose(egarch(r.iloc[:coupe]), eg.iloc[:coupe], equal_nan=True)
    log.info("causalite verifiee (coupe a %s)", df.index[coupe].date())

    vols = pd.DataFrame({"HAR": _vol_annuelle(har), "EGARCH": _vol_annuelle(eg),
                         "R30": _vol_annuelle(r30),
                         "RV_GK_jour": _vol_annuelle(variance_realisee(df))}).dropna()

    print(f"\n{paire} 1d — vol annualisee en % (prevision du jour, lue a t-1), "
          f"{vols.index[0].date()} -> {vols.index[-1].date()} (train seulement)")
    print("\nFin de mois :")
    print(vols.resample("ME").last().round(1).to_string())
    print("\n30 derniers jours :")
    print(vols.tail(30).round(1).to_string())
    print("\nResume (descriptif, pas une mesure de qualite de prevision) :")
    print(vols.describe().round(1).to_string())
    print("\nCorrelation des niveaux :")
    print(vols.corr().round(2).to_string())
    return vols


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    pd.set_option("display.width", 120)
    demo()
