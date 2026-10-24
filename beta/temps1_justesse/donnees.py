"""T1J : les series lues dans `beta.marches`, leurs calendriers et leurs dates de publication.

Lecture seule. Chaque serie garde SES dates (index naif = date de seance ou d'observation) :
l'alignement sur un autre calendrier se fait plus loin, par la derniere valeur connue. Seule
exception de publication : DEXJPUS, utilisable a la cloture du 2e jour ouvre Fed apres le vendredi
de la semaine de l'observation (clarification E du 24/10 : H.10 hebdomadaire, ALFRED absent).
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

from beta.marches import collecte
from beta.temps1_justesse import regles as R

log = logging.getLogger("beta.temps1_justesse.donnees")

SERIES_C1 = {"VIX": "VIXCLS", "USDJPY": "DEXJPUS"}


class DonneesError(RuntimeError):
    """Serie absente, vide ou incoherente : aucun chiffre ne doit sortir."""


@dataclass
class Donnees:
    prix: dict[str, pd.Series]        # SPX, NDX, OR, BTC : clotures sur le calendrier de l'actif
    vix: pd.Series                    # VIXCLS par date d'observation
    usdjpy: pd.Series                 # DEXJPUS par date d'observation
    usdjpy_utilisable: pd.Series      # date d'utilisation de chaque observation DEXJPUS
    seances_us: pd.DatetimeIndex      # calendrier de la couche 1 : les seances du SPX
    empreinte: str
    couverture: dict


def _close(nom: str) -> pd.Series:
    df = collecte.lire(nom)
    s = df["close"].astype(float)
    s.index = pd.DatetimeIndex(df.index).tz_convert(None).normalize()
    s = s[~s.index.duplicated(keep="last")].sort_index().dropna()
    if s.empty:
        raise DonneesError(f"{nom} : serie vide")
    if (s <= 0).any():
        raise DonneesError(f"{nom} : {int((s <= 0).sum())} valeur(s) non positive(s)")
    return s


def jours_ouvres_fed(debut: str | pd.Timestamp, fin: str | pd.Timestamp) -> pd.DatetimeIndex:
    """Lundi-vendredi hors feries federaux US (la Fed publie le H.10 ces jours-la)."""
    feries = USFederalHolidayCalendar().holidays(debut, fin)
    jours = pd.bdate_range(debut, fin)
    return jours[~jours.isin(feries)]


def dates_utilisables(observations: pd.DatetimeIndex) -> pd.Series:
    """Pour chaque observation : la date a la cloture de laquelle elle devient utilisable.

    Vendredi F de la semaine de l'observation, puis le JOURS_OUVRES_PUBLICATION-ieme jour ouvre
    Fed strictement apres F (mardi en temps normal ; mercredi si le lundi est ferie).
    """
    obs = pd.DatetimeIndex(observations).normalize()
    vendredis = obs + pd.to_timedelta((4 - obs.weekday) % 7 - 7 * (obs.weekday > 4), unit="D")
    ouvres = jours_ouvres_fed(vendredis.min() - pd.Timedelta(days=7),
                              vendredis.max() + pd.Timedelta(days=21))
    rang = ouvres.searchsorted(vendredis, side="right") + (R.JOURS_OUVRES_PUBLICATION - 1)
    if (rang >= len(ouvres)).any():
        raise DonneesError("calendrier Fed trop court pour dater les publications DEXJPUS")
    return pd.Series(ouvres[rang], index=obs, name="utilisable")


def _empreinte(series: dict[str, pd.Series]) -> str:
    h = hashlib.sha256()
    for nom in sorted(series):
        s = series[nom]
        h.update(nom.encode())
        h.update(s.index.as_unit("ns").asi8.tobytes())
        h.update(np.ascontiguousarray(s.to_numpy(dtype=float)).tobytes())
    return h.hexdigest()[:16]


def _trous_sur(calendrier: pd.DatetimeIndex, s: pd.Series, debut, fin) -> int:
    """Seances du calendrier, dans [debut, fin], sans observation de `s` ce jour-la."""
    jours = calendrier[(calendrier >= debut) & (calendrier <= fin)]
    return int((~jours.isin(s.index)).sum())


def charger() -> Donnees:
    prix = {actif: _close(serie) for actif, serie in R.ACTIFS.items()}
    vix = _close(SERIES_C1["VIX"])
    usdjpy = _close(SERIES_C1["USDJPY"])
    seances = prix["SPX"].index
    utilisable = dates_utilisables(usdjpy.index)
    tout = {**prix, "VIX": vix, "USDJPY": usdjpy}
    couverture = {}
    for nom, s in tout.items():
        serie = R.ACTIFS.get(nom) or SERIES_C1[nom]
        df = s.to_frame("close")
        df.index = df.index.tz_localize("UTC")
        c = collecte.couverture(df)
        couverture[nom] = {"serie": serie, "debut": c["debut"], "fin": c["fin"], "n": c["n"],
                           "trous_plus_de_5_seances": c["trous_plus_de_5_seances"],
                           "trous_exemples": c["trous_exemples"]}
    # Seances US de la couche 1 sans observation du jour : comblees par la derniere valeur.
    debut_labo = seances[seances.searchsorted(pd.Timestamp(R.LABO[0])) - R.PRECHAUFFE_SEANCES]
    for nom in ("VIX", "USDJPY", "OR"):
        couverture[nom]["comblees_seances_us"] = {
            "labo_avec_prechauffe": _trous_sur(seances, tout[nom], debut_labo,
                                               pd.Timestamp(R.LABO[1])),
            "informative": _trous_sur(seances, tout[nom], pd.Timestamp(R.DEBUT_INFORMATIVE),
                                      seances.max())}
    return Donnees(prix=prix, vix=vix, usdjpy=usdjpy, usdjpy_utilisable=utilisable,
                   seances_us=seances, empreinte=_empreinte(tout), couverture=couverture)
