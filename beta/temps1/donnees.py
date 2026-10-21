"""Temps 1 — les donnees du labo : seances, point-in-time de DEXJPUS, trous, prechauffe.

Source unique : `beta.marches` (SPX, NDX, VIX, XAU_LBMA, DEXJPUS). Aucune donnee crypto.

Chaque serie garde SES seances : la SMA 200 de l'or porte sur 200 fixings, la variation de
USD/JPY sur 21 observations du H.10, T sur les seances du S&P 500. Ce n'est qu'au moment de
decider (cloture d'une seance de l'actif cible) qu'on prend, pour chacune, sa derniere valeur
CONNUE — « trous combles par la derniere valeur connue ».

DEXJPUS est publie avec retard (H.10 hebdomadaire, le lundi a 16:15 ET) : une observation n'est
utilisable qu'a partir de sa publication. Date ALFRED de premiere publication V -> utilisable a
la cloture de la premiere seance STRICTEMENT apres V (le H.10 sort apres la cloture). Sans date
ALFRED : decalage de 2 jours ouvres US (feries federaux), comme le prompt le prevoit, et signale.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

from beta.marches import collecte

log = logging.getLogger("beta.temps1.donnees")

CIBLES = ("SPX", "NDX")
ENTREES = ("SPX", "NDX", "VIX", "XAU_LBMA", "DEXJPUS")
PRECHAUFFE_SEANCES = 252
DECALAGE_REPLI_JOURS_OUVRES = 2
# Une date ALFRED n'est une date de PUBLICATION que si l'observation existait deja quand
# l'archive l'a vue paraitre ; une observation anterieure a la premiere vintage apparait d'un
# bloc a cette date (des annees plus tard) : ce n'est pas sa publication. Au-dela de ce retard,
# la date ALFRED est jugee non informative et le repli s'applique.
RETARD_ALFRED_PLAUSIBLE_J = 31


class DonneesError(RuntimeError):
    """Serie absente, trop courte pour la prechauffe, ou incoherente : on s'arrete (C5)."""


def feries_us(debut, fin) -> np.ndarray:
    debut = pd.Timestamp(debut) - pd.Timedelta(days=10)
    fin = pd.Timestamp(fin) + pd.Timedelta(days=10)
    return USFederalHolidayCalendar().holidays(debut, fin).to_numpy(dtype="datetime64[D]")


def disponibilite_dexjpus(dates: pd.DatetimeIndex, publie_le: pd.Series | None
                          ) -> tuple[pd.DatetimeIndex, dict]:
    """Pour chaque observation datee D : le premier JOUR (date de seance) ou elle est connue a
    la cloture. ALFRED quand la date est informative, sinon D + 2 jours ouvres US."""
    jours = dates.to_numpy(dtype="datetime64[D]")
    repli = np.busday_offset(jours, DECALAGE_REPLI_JOURS_OUVRES, roll="forward",
                             holidays=feries_us(dates.min(), dates.max()))
    dispo = repli.astype("datetime64[ns]")
    n_alfred = 0
    if publie_le is not None:
        pub = pd.to_datetime(publie_le.reindex(dates))
        if pub.dt.tz is not None:
            pub = pub.dt.tz_convert(None)
        pub = pub.dt.normalize()
        retard = (pub - pd.Series(dates, index=dates)).dt.days
        valide = (pub.notna() & (retard >= 0) & (retard <= RETARD_ALFRED_PLAUSIBLE_J)).to_numpy()
        # Strictement apres V : utilisable a partir du lendemain civil de la publication.
        alfred = (pub + pd.Timedelta(days=1)).to_numpy(dtype="datetime64[ns]")
        dispo = np.where(valide, alfred, dispo)
        n_alfred = int(valide.sum())
    n = len(dates)
    mode = ("alfred" if n_alfred == n else "decalage_2_jours_ouvres" if n_alfred == 0
            else "mixte")
    return pd.DatetimeIndex(dispo), {"mode": mode, "observations": n, "datees_alfred": n_alfred,
                                     "repli_2_jours_ouvres": n - n_alfred}


def derniere_connue(valeurs: pd.Series, dispo: pd.DatetimeIndex,
                    decisions: pd.DatetimeIndex) -> pd.Series:
    """A chaque decision J : la valeur de la derniere observation (dans l'ordre des observations)
    dont la disponibilite est <= J. NaN si aucune ne l'est."""
    ordre = np.arange(len(valeurs))
    d = dispo.as_unit("ns").asi8
    tri = np.argsort(d, kind="stable")
    d_trie, k_max = d[tri], np.maximum.accumulate(ordre[tri])
    rang = np.searchsorted(d_trie, decisions.as_unit("ns").asi8, side="right") - 1
    x = valeurs.to_numpy(dtype=float)
    out = np.where(rang >= 0, x[k_max[np.maximum(rang, 0)]], np.nan)
    return pd.Series(out, index=decisions)


def a_la_decision(serie: pd.Series, decisions: pd.DatetimeIndex) -> pd.Series:
    """Derniere valeur observee a la date de decision ou avant (connue le jour meme)."""
    s = serie.dropna().sort_index()
    return s.reindex(s.index.union(decisions)).ffill().reindex(decisions)


@dataclass
class Donnees:
    closes: dict[str, pd.Series]        # cloture par serie, index = date de seance (naive)
    dexjpus_dispo: pd.DatetimeIndex     # disponibilite de chaque observation DEXJPUS
    pit_dexjpus: dict                   # mode et comptes (alfred / repli)
    fin: pd.Timestamp                   # derniere seance commune des deux cibles
    empreinte: str
    couverture: dict                    # par serie : debut, fin, n, trous > 5 (collecteur)


def empreinte(closes: dict[str, pd.Series], dispo: pd.DatetimeIndex) -> str:
    h = hashlib.sha256()
    for nom in ENTREES:
        s = closes[nom]
        h.update(nom.encode())
        h.update(s.index.as_unit("ns").asi8.tobytes())
        h.update(np.ascontiguousarray(s.to_numpy(dtype=float)).tobytes())
    h.update(dispo.as_unit("ns").asi8.tobytes())
    return h.hexdigest()[:16]


def charger(lire=collecte.lire, etat=collecte.etat) -> Donnees:
    """Les cinq series du collecteur, en dates de seance naives ; DEXJPUS avec sa disponibilite."""
    closes, publie = {}, None
    for nom in ENTREES:
        try:
            df = lire(nom)
        except FileNotFoundError as exc:
            raise DonneesError(str(exc)) from exc
        s = df["close"].astype(float)
        s.index = pd.DatetimeIndex(df.index).tz_convert(None).normalize()
        if s.index.has_duplicates or (s <= 0).any() or s.isna().any():
            raise DonneesError(f"{nom} : dates en double, valeurs <= 0 ou manquantes")
        closes[nom] = s.sort_index()
        if nom == "DEXJPUS" and "publie_le" in df.columns:
            publie = pd.Series(pd.to_datetime(df["publie_le"]).to_numpy(), index=s.index)
    dispo, pit = disponibilite_dexjpus(closes["DEXJPUS"].index, publie)
    fin = min(closes[c].index.max() for c in CIBLES)
    e = etat()
    couverture = {n: {k: e.get(n, {}).get(k) for k in ("debut", "fin", "n",
                                                       "trous_plus_de_5_seances", "empreinte",
                                                       "source", "identifiant",
                                                       "source_effective")}
                  for n in ENTREES}
    return Donnees(closes=closes, dexjpus_dispo=dispo, pit_dexjpus=pit, fin=fin,
                   empreinte=empreinte(closes, dispo), couverture=couverture)


# =========================================================================================
# Trous et prechauffe
# =========================================================================================

def seances(d: Donnees, cible: str, debut: pd.Timestamp, fin: pd.Timestamp) -> pd.DatetimeIndex:
    """Les seances de decision de la cible dont la decision joue sur [debut, fin] : de la
    derniere seance avant `debut` (sa cloture fixe l'exposition du premier jour) a `fin`."""
    idx = d.closes[cible].index
    avant = idx[idx < debut]
    if len(avant) == 0:
        raise DonneesError(f"{cible} : aucune seance avant le {debut:%Y-%m-%d}")
    return idx[(idx >= avant[-1]) & (idx <= fin)]


def trous_combles(d: Donnees, cible: str, debut: pd.Timestamp, fin: pd.Timestamp) -> dict:
    """Par serie d'entree : seances de la cible SANS observation ce jour-la (comblees par la
    derniere valeur connue), et la plus longue suite de telles seances."""
    dec = seances(d, cible, debut, fin)
    sortie = {}
    for nom in dict.fromkeys((cible, "SPX", "VIX", "XAU_LBMA", "DEXJPUS")):
        absent = ~dec.isin(d.closes[nom].index)
        bords = np.diff(np.concatenate([[0], absent.astype(np.int8), [0]]))
        plus_longue = int((np.flatnonzero(bords == -1) - np.flatnonzero(bords == 1)).max()) \
            if absent.any() else 0
        sortie[nom] = {"seances_comblees": int(absent.sum()), "plus_longue_suite": plus_longue,
                       "suites_de_plus_de_5": int(((np.flatnonzero(bords == -1)
                                                    - np.flatnonzero(bords == 1)) > 5).sum())}
    return sortie


def controler_prechauffe(d: Donnees, cible: str, debut: pd.Timestamp,
                         besoin: dict[str, int]) -> None:
    """Il faut, pour chaque serie, `besoin[nom]` observations jusqu'a la premiere decision."""
    premiere = seances(d, cible, debut, debut)[0]
    for nom, n in besoin.items():
        disponibles = int((d.closes[nom].index <= premiere).sum())
        if disponibles < n:
            raise DonneesError(f"prechauffe : {nom} n'a que {disponibles} observation(s) au "
                               f"{premiere:%Y-%m-%d}, il en faut {n}")
