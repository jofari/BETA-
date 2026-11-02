"""VC6 V1, Temps 2 : lecture des copies figees (SHA-256 verifie avant toute lecture).

Index de toutes les series journalieres : jour civil UTC, naif. Cloture d'un perpetuel le jour D
= barre 5 min ouverte en D a 23:55 (amendement du 01/11). Funding du jour D = reglements de
]D 00:00 ; D+1 00:00] (application 9). Or et ETF : jours de semaine seulement, dernier cours
connu les autres jours (application 15 et 25).
"""

from __future__ import annotations

import hashlib
import pathlib

import numpy as np
import pandas as pd

from beta import config
from beta.controle_har import campagne as har_campagne
from beta.controle_har import donnees as har_donnees
from beta.controle_har import har as har_calc
from beta.vc6 import regles as R


class DonneesError(RuntimeError):
    """Copie absente, modifiee depuis le gel ou incomplete : aucun chiffre ne sort."""


def _chemin(nom: str) -> pathlib.Path:
    return config.RACINE / R.DOSSIER_COPIES / f"{nom}.parquet"


def _verifier(nom: str) -> pathlib.Path:
    chemin = _chemin(nom)
    if not chemin.exists():
        raise DonneesError(f"copie figee absente : {chemin}")
    if har_donnees.sha256(chemin) != R.SHA256[nom]:
        raise DonneesError(f"{chemin.name} a change depuis le gel (SHA-256)")
    return chemin


def _lire(nom: str, colonnes: list[str]) -> pd.DataFrame:
    df = pd.read_parquet(_verifier(nom), columns=["date", *colonnes])
    df.index = pd.DatetimeIndex(pd.to_datetime(df.pop("date"), utc=True))
    return df[~df.index.duplicated(keep="last")].sort_index()


def _jour_naif(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return index.tz_convert(None).normalize()


def barres_5m(actif: str) -> pd.DataFrame:
    _verifier(f"{actif}_perp_5m")
    return har_donnees.bougies_5m(actif)


def clotures_perp(barres: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Clotures de la barre de 23:55 ; un jour sans cette barre est une erreur."""
    cols = {}
    for actif, b in barres.items():
        s = har_donnees.clotures_5m(b)
        complet = pd.date_range(s.index.min(), s.index.max(), freq="D")
        if len(complet.difference(s.index)):
            raise DonneesError(f"{actif} : jour sans barre de 23:55")
        cols[actif] = s
    return pd.DataFrame(cols)


def sigma_har(barres: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """sigma annualise = sqrt(365 h), h = prevision HAR apres replis (Controle HAR)."""
    return pd.DataFrame({a: np.sqrt(R.JOURS_AN * har_campagne.previsions(b)["har"])
                         for a, b in barres.items()})


def sigma_ecart_type(close: pd.Series) -> pd.Series:
    """Robustesse : ecart-type 30 jours des rendements log journaliers, annualise sqrt(365)."""
    return np.sqrt(R.JOURS_AN * har_calc.ecart_type_30(close))


def funding_brut(actif: str) -> pd.Series:
    return _lire(f"{actif}_funding", ["funding_rate"])["funding_rate"].astype(float)


def funding_jour(actif: str) -> pd.DataFrame:
    """Somme et nombre des reglements de ]D 00:00 ; D+1 00:00] pour chaque jour D."""
    f = funding_brut(actif)
    jour = _jour_naif((f.index - pd.Timedelta(microseconds=1)))
    g = f.groupby(jour)
    out = pd.DataFrame({"somme": g.sum(), "nombre": g.size()})
    complet = pd.date_range(out.index.min(), out.index.max(), freq="D")
    if len(complet.difference(out.index)):
        raise DonneesError(f"{actif} : jour sans reglement de funding")
    return out


def _semaine_ffill(nom: str, debut: pd.Timestamp, fin: pd.Timestamp) -> pd.Series:
    df = _lire(nom, ["close"])
    s = df["close"].astype(float)
    s.index = _jour_naif(df.index)
    s = s[s.index.dayofweek < 5]
    jours = pd.date_range(debut, fin, freq="D")
    out = s.reindex(s.index.union(jours)).ffill().reindex(jours)
    if out.isna().any():
        raise DonneesError(f"{nom} : aucun cours connu au {out.index[out.isna()][0]:%Y-%m-%d}")
    return out


def or_close(debut: pd.Timestamp, fin: pd.Timestamp) -> pd.Series:
    return _semaine_ffill("XAU_SPOT_1d", debut, fin).rename("XAU")


def urth_close(debut: pd.Timestamp, fin: pd.Timestamp) -> pd.Series:
    return _semaine_ffill("URTH_1d", debut, fin).rename("URTH")


def bitstamp_close() -> pd.Series:
    df = _lire("BTC_bitstamp_1d", ["close"])
    s = df["close"].astype(float)
    s.index = _jour_naif(df.index)
    complet = pd.date_range(s.index.min(), s.index.max(), freq="D")
    if len(complet.difference(s.index)) or not (s > 0).all():
        raise DonneesError("Bitstamp : jour manquant ou cloture non positive")
    return s.rename("BTC")


def empreinte(series: dict[str, pd.Series | pd.DataFrame]) -> str:
    h = hashlib.sha256()
    for nom in sorted(series):
        x = series[nom]
        h.update(nom.encode())
        h.update(np.asarray(x.index.asi8).tobytes())
        h.update(np.ascontiguousarray(np.asarray(x, dtype=float)).tobytes())
    return h.hexdigest()[:16]
