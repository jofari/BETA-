"""Controle HAR : les copies figees de l'etape A (bougies 5 min et 1d des perpetuels).

Lecture seule. Chaque copie est verifiee par son SHA-256 AVANT d'etre lue : une copie qui a change
depuis le gel n'est pas la donnee preenregistree. Barres 5 min : index tz-aware UTC = heure
d'ouverture. Depuis l'amendement du 01/11/2026 (Jonas), la cloture du jour D est celle de la barre
5 min ouverte en D a 23:55 UTC ; les copies 1d ne servent plus qu'au controle.
"""

from __future__ import annotations

import hashlib
import logging
import pathlib

import numpy as np
import pandas as pd

from beta import config
from beta.controle_har import regles as R

log = logging.getLogger("beta.controle_har.donnees")


class DonneesError(RuntimeError):
    """Copie absente, modifiee depuis le gel, vide ou incoherente : aucun chiffre ne sort."""


def sha256(chemin: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def _lire(relatif: str, colonnes: list[str]) -> pd.DataFrame:
    chemin = config.RACINE / relatif
    if not chemin.exists():
        raise DonneesError(f"copie figee absente ({relatif})")
    attendu = R.SHA256[chemin.stem]
    if sha256(chemin) != attendu:
        raise DonneesError(f"{relatif} a change depuis le gel (SHA-256)")
    df = pd.read_parquet(chemin, columns=["date", *colonnes])
    df.index = pd.DatetimeIndex(pd.to_datetime(df.pop("date"), utc=True))
    df = df[~df.index.duplicated(keep="last")].sort_index()
    if df.empty:
        raise DonneesError(f"{relatif} : copie vide")
    if not (df["close"] > 0).all():
        raise DonneesError(f"{relatif} : cloture absente ou non positive")
    return df


def bougies_5m(actif: str) -> pd.DataFrame:
    """Barres 5 min (cloture, volume) ouvertes jusqu'au jour de fin inclus, 23:55 UTC."""
    df = _lire(R.ACTIFS[actif]["bougies_5m"], ["close", "volume"])
    fin = pd.Timestamp(R.FIN, tz="UTC") + pd.Timedelta(days=1)
    df = df[df.index < fin]
    if ((df.index - df.index.floor("5min")) != pd.Timedelta(0)).any():
        raise DonneesError(f"{actif} : barres 5 min hors de la grille de 5 min")
    return df


def clotures_1d(actif: str) -> pd.Series:
    """Clotures journalieres jusqu'au jour de fin inclus, index = jour civil UTC (naif)."""
    df = _lire(R.ACTIFS[actif]["bougies_1d"], ["close"])
    s = df["close"].astype(float)
    s.index = df.index.tz_convert(None).normalize()
    s = s[s.index <= pd.Timestamp(R.FIN)]
    s.name = "close"
    return s


def clotures_5m(barres: pd.DataFrame) -> pd.Series:
    """Cloture du jour D = cloture de la barre 5 min ouverte en D a 23:55 UTC ; un jour sans
    cette barre n'a pas de cloture. Index naif = jour civil UTC."""
    heure, minute = R.BARRE_DE_CLOTURE
    s = barres["close"][(barres.index.hour == heure) & (barres.index.minute == minute)]
    s = s.astype(float)
    s.index = s.index.tz_convert(None).normalize()
    return s.rename("close")


def controle_clotures(barres: pd.DataFrame, close_1d: pd.Series) -> list[str]:
    """Jours ou la cloture 1d differe de celle de la barre 5 min de 23:55, ou n'a pas de barre de
    23:55 : rapportes, sans effet sur le calcul (amendement du 01/11)."""
    derniere = clotures_5m(barres)
    communs = close_1d.index.intersection(derniere.index)
    ecart = communs[close_1d.loc[communs].to_numpy() != derniere.loc[communs].to_numpy()]
    sans_barre = close_1d.index.difference(derniere.index)
    return [f"{d:%Y-%m-%d}" for d in ecart.append(sans_barre).sort_values()]


def couverture(barres: pd.DataFrame, close_1d: pd.Series) -> dict:
    return {"premiere_barre_5m": f"{barres.index.min():%Y-%m-%d %H:%M}",
            "derniere_barre_5m": f"{barres.index.max():%Y-%m-%d %H:%M}",
            "barres_5m": int(len(barres)),
            "premiere_cloture_1d": f"{close_1d.index.min():%Y-%m-%d}",
            "derniere_cloture_1d": f"{close_1d.index.max():%Y-%m-%d}",
            "clotures_1d": int(len(close_1d))}


def empreinte(lus: dict[str, tuple[pd.DataFrame, pd.Series]]) -> str:
    """Empreinte des valeurs lues (dates et clotures), dans l'ordre des actifs."""
    h = hashlib.sha256()
    for actif in sorted(lus):
        barres, close_1d = lus[actif]
        for serie in (barres["close"], close_1d):
            h.update(actif.encode())
            h.update(serie.index.asi8.tobytes())
            h.update(np.ascontiguousarray(serie.to_numpy(dtype=float)).tobytes())
    return h.hexdigest()[:16]
