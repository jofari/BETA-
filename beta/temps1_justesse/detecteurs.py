"""T1J : les detecteurs, un signal par jour de l'actif juge : -1 bear, 0 neutre, +1 bull, NaN avant
la prechauffe.

SMA et MOM se calculent sur les clotures de l'actif juge. La couche 1 (C1_V1, C1_V2 et les
variantes de fenetre de C1_V1) est un regime GLOBAL : calculee sur les seances US, chaque
indicateur sur ses propres observations puis pris a sa derniere valeur connue (DEXJPUS : a sa
date d'utilisation), puis reportee sur le calendrier de l'actif juge (signal d'une seance US
valable jusqu'a la seance US suivante). Le signal du jour t n'utilise que des donnees publiees au
plus tard en t : c'est ce que verifie l'epreuve de causalite (tests et campagne).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from beta.temps1_justesse import regles as R
from beta.temps1_justesse.donnees import Donnees

BEAR, NEUTRE, BULL = -1.0, 0.0, 1.0


def _sigma(x: pd.Series, w: int) -> pd.Series:
    return x.rolling(w, min_periods=w).std(ddof=1)


def _moyenne(x: pd.Series, w: int) -> pd.Series:
    return x.rolling(w, min_periods=w).mean()


def sma(close: pd.Series, n: int) -> pd.Series:
    """bear si cloture < moyenne des n dernieres clotures (jour compris), bull sinon."""
    m = _moyenne(close, n)
    return pd.Series(np.where(m.isna(), np.nan, np.where(close < m, BEAR, BULL)),
                     index=close.index)


def mom(close: pd.Series, n: int = R.MOM_FENETRE) -> pd.Series:
    """bear si cloture(t) / cloture(t - n) - 1 < 0, bull sinon."""
    r = close / close.shift(n) - 1.0
    return pd.Series(np.where(r.isna(), np.nan, np.where(r < 0, BEAR, BULL)), index=close.index)


# ----------------------------------------------------------------------------- couche 1

def _booleen(vrai: pd.Series, valide: pd.Series) -> pd.Series:
    """Indicateur en flottant : 1.0 vrai, 0.0 faux, NaN tant que ses entrees manquent."""
    return pd.Series(np.where(valide.to_numpy(), vrai.to_numpy().astype(float), np.nan),
                     index=vrai.index)


def indicateurs_v1(d: Donnees, w: int) -> dict[str, pd.Series]:
    """V, Y, T, G de C1_V1 (fenetre w), chacun sur ses propres observations."""
    s = R.C1_V1_SEUILS
    vix = d.vix
    m, sg = _moyenne(vix, w), _sigma(vix, w)
    saut = vix / vix.shift(5) - 1.0
    v = _booleen((vix > m + s["k_vix"] * sg) | (saut > s["saut_vix_5"]),
                 m.notna() & sg.notna() & saut.notna())
    jpy = d.usdjpy
    r5 = jpy / jpy.shift(5) - 1.0
    sr = _sigma(r5, w)
    y = _booleen(r5 < -s["k_jpy"] * sr, r5.notna() & sr.notna())
    spx = d.prix["SPX"]
    dt = spx / _moyenne(spx, s["sma"]) - 1.0
    ddt = dt - dt.shift(s["delta"])
    st = _sigma(ddt, w)
    t = _booleen((dt < 0) | ((dt >= 0) & (dt <= s["bande_t"]) & (ddt < -s["k_t"] * st)),
                 dt.notna() & ddt.notna() & st.notna())
    gold = d.prix["OR"]
    g = gold / _moyenne(gold, s["sma"]) - 1.0
    dg = g - g.shift(s["delta"])
    sgg = _sigma(dg, w)
    gg = _booleen((g > 0) | ((g >= -s["bande_g"]) & (g < 0) & (dg > s["k_g"] * sgg)),
                  g.notna() & dg.notna() & sgg.notna())
    return {"V": v, "Y": y, "T": t, "G": gg}


def indicateurs_v2(d: Donnees) -> dict[str, pd.Series]:
    """V, Y, T, G de C1_V2 (seuils fixes)."""
    s = R.C1_V2_SEUILS
    vix = d.vix
    v = _booleen(vix > s["vix"], vix.notna())
    jpy = d.usdjpy
    r = jpy / jpy.shift(s["jpy_fenetre"]) - 1.0
    y = _booleen(r < -s["jpy_baisse"], r.notna())
    spx = d.prix["SPX"]
    m = _moyenne(spx, s["sma"])
    t = _booleen(spx < m, m.notna())
    gold = d.prix["OR"]
    mg = _moyenne(gold, s["sma"])
    g = _booleen(gold > mg, mg.notna())
    return {"V": v, "Y": y, "T": t, "G": g}


def _sur_seances_us(ind: dict[str, pd.Series], d: Donnees) -> pd.DataFrame:
    """Chaque indicateur a sa derniere valeur connue a chaque seance US.

    Y (USD/JPY) est indexe par la date d'UTILISATION de ses observations (clarification E) :
    toutes les observations d'une semaine deviennent lisibles le meme jour, la plus recente
    l'emporte.
    """
    seances = d.seances_us
    y = ind["Y"].copy()
    y.index = pd.DatetimeIndex(d.usdjpy_utilisable.reindex(y.index).to_numpy())
    y = y[~y.index.duplicated(keep="last")].sort_index()
    sortie = {}
    for nom, serie in (("V", ind["V"]), ("Y", y), ("T", ind["T"]), ("G", ind["G"])):
        sortie[nom] = serie.reindex(serie.index.union(seances)).ffill().reindex(seances)
    return pd.DataFrame(sortie)


def etats(ind_us: pd.DataFrame) -> pd.Series:
    """1. liquidite (V ou Y) -> bear ; 2. sinon monetaire (T et G) -> neutre ; 3. sinon bull."""
    valide = ind_us.notna().all(axis=1)
    v, y, t, g = (ind_us[k].fillna(0).astype(bool) for k in ("V", "Y", "T", "G"))
    etat = np.where(v | y, BEAR, np.where(t & g, NEUTRE, BULL))
    return pd.Series(np.where(valide, etat, np.nan), index=ind_us.index)


def couche1_us(d: Donnees, nom: str) -> pd.Series:
    """Le regime C1 sur les seances US."""
    ind = indicateurs_v2(d) if nom == "C1_V2" else indicateurs_v1(d, R.FENETRE_C1[nom])
    return etats(_sur_seances_us(ind, d))


def sur_calendrier(signal_us: pd.Series, dates: pd.DatetimeIndex) -> pd.Series:
    """Le signal de la derniere seance US <= t, pour chaque date t de l'actif juge."""
    pos = signal_us.index.searchsorted(dates, side="right") - 1
    valeurs = np.where(pos >= 0, signal_us.to_numpy()[np.clip(pos, 0, None)], np.nan)
    return pd.Series(valeurs, index=dates)


def signal(d: Donnees, detecteur: str, actif: str) -> pd.Series:
    """Le signal d'un detecteur sur le calendrier d'un actif juge."""
    close = d.prix[actif]
    if detecteur in R.SMA_FENETRES:
        return sma(close, R.SMA_FENETRES[detecteur])
    if detecteur == "MOM126":
        return mom(close)
    if detecteur in ("C1_V1", "C1_V2", *R.VARIANTES_C1):
        return sur_calendrier(couche1_us(d, detecteur), close.index)
    raise KeyError(f"detecteur inconnu : {detecteur}")
