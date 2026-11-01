"""T1C : les clotures d'ETH et de SOL (copies figees de l'etape A) et le sigma de reference de T1J.

Lecture seule. Chaque copie est verifiee par son SHA-256 AVANT d'etre lue : une copie qui a change
depuis le gel n'est pas la donnee preenregistree. Convention de T1J : index naif = jour civil UTC,
la cloture du jour D est celle de la bougie 1d ouverte le jour D a 00:00 UTC.
"""

from __future__ import annotations

import hashlib
import logging
import math
import pathlib

import pandas as pd

from beta import config
from beta.temps1_complement import regles as R
from beta.temps1_justesse import donnees as dn
from beta.temps1_justesse import juge as jg

log = logging.getLogger("beta.temps1_complement.donnees")


class DonneesError(RuntimeError):
    """Copie absente, modifiee depuis le gel, vide ou incoherente : aucun chiffre ne sort."""


def sha256(chemin: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def close(actif: str) -> pd.Series:
    """Les clotures journalieres de l'actif, coupees a la date de fin figee."""
    spec = R.ACTIFS[actif]
    chemin = config.RACINE / spec["copie"]
    if not chemin.exists():
        raise DonneesError(f"{actif} : copie figee absente ({spec['copie']})")
    if sha256(chemin) != spec["sha256"]:
        raise DonneesError(f"{actif} : {spec['copie']} a change depuis le gel (SHA-256)")
    df = pd.read_parquet(chemin)
    s = df["close"].astype(float)
    s.index = pd.DatetimeIndex(pd.to_datetime(df["date"], utc=True)).tz_convert(None).normalize()
    s = s[~s.index.duplicated(keep="last")].sort_index().dropna()
    s = s[s.index <= pd.Timestamp(R.FIN)]
    if s.empty:
        raise DonneesError(f"{actif} : serie vide")
    if (s <= 0).any():
        raise DonneesError(f"{actif} : {int((s <= 0).sum())} valeur(s) non positive(s)")
    s.name = "close"
    return s


def couverture(s: pd.Series) -> dict:
    """Debut, fin, nombre de clotures et jours civils manquants (calendrier 7 j / 7)."""
    attendus = pd.date_range(s.index.min(), s.index.max(), freq="D")
    return {"debut": f"{s.index.min():%Y-%m-%d}", "fin": f"{s.index.max():%Y-%m-%d}",
            "n": int(len(s)), "jours_manquants": int(len(attendus.difference(s.index)))}


def series_t1j() -> dict[str, pd.Series]:
    """Les series de la copie figee de T1J, empreinte verifiee (celle de la mesure de T1J)."""
    chemin = config.RACINE / R.COPIE_T1J
    if not chemin.exists():
        raise DonneesError(f"copie figee de T1J absente ({R.COPIE_T1J})")
    long = pd.read_parquet(chemin)
    series = {nom: pd.Series(g["close"].to_numpy(dtype=float), index=pd.DatetimeIndex(g["date"]),
                             name="close")
              for nom, g in long.groupby("serie", sort=True)}
    if dn._empreinte(series) != R.EMPREINTE_DONNEES_T1J:
        raise DonneesError(f"copie de T1J : empreinte {dn._empreinte(series)} au lieu de "
                           f"{R.EMPREINTE_DONNEES_T1J}")
    return series


def sigma_sp_ref() -> float:
    """sigma_S&P_ref de T1J, recalcule sur sa copie figee et compare a la valeur de sa mesure."""
    sigma = jg.sigma_sp_ref(series_t1j()["SPX"])
    if not math.isclose(sigma, R.SIGMA_SP_REF_T1J, rel_tol=0.0, abs_tol=1e-15):
        raise DonneesError(f"sigma_SP_ref recalcule {sigma!r} different de celui de T1J "
                           f"{R.SIGMA_SP_REF_T1J!r}")
    return sigma


def empreinte(closes: dict[str, pd.Series]) -> str:
    """Empreinte des clotures lues, calculee comme celle des donnees de T1J."""
    return dn._empreinte(closes)
