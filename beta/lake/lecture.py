"""L'API de lecture du lake. Le point d'entree unique de tout ce qui lira des donnees.

    from beta import data
    df = data.load("BTC", "4h")
    df = data.load("BTC", "15m", debut="2023-01-01", fin="2024-01-01")

Deux choses qu'elle garantit et qu'un `read_parquet` a la main ne garantit pas :

- **le timeframe demande peut ne pas etre stocke.** Tout multiple de 5 min se derive du 5m
  par resampling — exact, pas approche. On ne telecharge pas ce qu'on peut calculer.
- **une serie suspecte se signale.** Si le catalogue a marque des trous au-dela du seuil, la
  lecture emet un avertissement. Silencieuse, l'erreur se propage jusqu'au backtest.
"""

from __future__ import annotations

import logging

import duckdb
import pandas as pd

from beta import config
from beta.lake import univers

log = logging.getLogger("beta.data")

# Regle de resampling OHLCV. Ecrite une fois : c'est le genre d'agregation ou une erreur
# (prendre le `first` du high, par exemple) ne se voit jamais a la lecture du code appelant.
AGREGATION = {"open": "first", "high": "max", "low": "min", "close": "last",
              "volume": "sum"}


class DataError(RuntimeError):
    """Donnee absente du lake, ou timeframe non derivable."""


def _table_source(paire: univers.Paire, timeframe: str) -> tuple[str, bool]:
    """(timeframe a lire, faut-il resampler). Le 5m est la base de toute derivation."""
    if timeframe in univers.TIMEFRAMES:
        return timeframe, False
    pas = univers.pas_minutes(timeframe)
    base = univers.pas_minutes("5m")
    if pas % base:
        raise DataError(f"{timeframe} n'est pas un multiple de 5m : non derivable")
    return "5m", True


def disponible(paire: str, timeframe: str) -> bool:
    p = univers.resoudre(paire)
    source, _ = _table_source(p, timeframe)
    return config.chemin_parquet(p.slug, source).exists()


def load(paire: str, timeframe: str, debut: str | None = None,
         fin: str | None = None, colonnes: tuple[str, ...] | None = None) -> pd.DataFrame:
    """OHLCV d'une paire, en UTC, index temporel croissant.

    `debut`/`fin` sont inclusifs et acceptent tout ce que pandas sait lire ('2023-01-01').
    Le filtrage est pousse dans DuckDB : on ne charge jamais le fichier entier pour en
    garder un mois.
    """
    p = univers.resoudre(paire)
    source, resampler = _table_source(p, timeframe)
    chemin = config.chemin_parquet(p.slug, source)
    if not chemin.exists():
        raise DataError(f"{p.base} {source} absent du lake ({chemin.name}). "
                        "Lancer scripts/build_lake.py.")

    champs = "*" if colonnes is None else ", ".join(("date", *colonnes))
    clauses, params = [], []
    if debut:
        clauses.append("date >= ?")
        params.append(pd.Timestamp(debut, tz="UTC"))
    if fin:
        clauses.append("date <= ?")
        params.append(pd.Timestamp(fin, tz="UTC"))
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    requete = f"SELECT {champs} FROM read_parquet(?){where} ORDER BY date"
    try:
        with duckdb.connect() as conn:
            conn.execute("SET TimeZone='UTC'")
            df = conn.execute(requete, [str(chemin), *params]).df()
    except duckdb.Error as exc:
        raise DataError(f"lecture impossible ({chemin.name}) : {exc}") from exc

    df["date"] = pd.to_datetime(df["date"], utc=True)
    _avertir_si_suspect(p, source)
    return resample(df, timeframe) if resampler else df.reset_index(drop=True)


def resample(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """5m -> tout multiple de 5 min. `label`/`closed` a gauche : convention freqtrade.

    Une bougie porte l'horodatage de son OUVERTURE. Se tromper ici decale toute la serie
    d'une bougie et fabrique du look-ahead sans que rien ne le signale.
    """
    if df.empty:
        return df
    pas = f"{univers.pas_minutes(timeframe)}min"
    agg = {c: AGREGATION[c] for c in AGREGATION if c in df.columns}
    out = (df.set_index("date")
             .resample(pas, label="left", closed="left")
             .agg(agg)
             .dropna(subset=["open"])
             .reset_index())
    return out


def funding(paire: str) -> pd.DataFrame:
    """Taux de financement 8h de la paire, lu dans les feathers d'ARIT (lecture seule).

    Rend un DataFrame (date, funding_rate), trie et tz-aware. `date` est l'horodatage de
    REGLEMENT de la periode — le taux est celui qui a ete paye a cette date, pour la periode
    [date-8h, date]. Pour une entree a un instant t, le taux SANS look-ahead est donc celui
    dont le reglement est STRICTEMENT anterieur a t (cf. merge_asof allow_exact_matches=False
    dans le pipeline).
    """
    p = univers.resoudre(paire)
    chemin = config.chemin_feather_funding(p.slug)
    if not chemin.exists():
        raise DataError(f"{p.base} funding absent du lake ARIT ({chemin.name})")
    df = pd.read_feather(chemin)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return df[["date", "funding_rate"]].sort_values("date").reset_index(drop=True)


def fear_greed() -> pd.DataFrame:
    """Fear & Greed Index quotidien, lu dans les donnees macro d'ARIT (lecture seule).

    Rend un DataFrame (date, fng), date = minuit UTC du jour. Le F&G du jour n'est public
    qu'a la fin de ce jour (source alternative.me) : pour l'utiliser SANS look-ahead, le
    pipeline le decale d'un jour (voir `_joindre_macro`).
    """
    chemin = config.ARIT_MACRO / "fear_greed.json"
    if not chemin.exists():
        raise DataError(f"F&G absent ({chemin.name})")
    import json
    brut = json.loads(chemin.read_text(encoding="utf-8"))
    lignes = [(pd.Timestamp(int(x["timestamp"]), unit="s", tz="UTC"), float(x["value"]))
              for x in brut.get("data", []) if x.get("timestamp")]
    df = pd.DataFrame(lignes, columns=["date", "fng"])
    return df.sort_values("date").reset_index(drop=True)


def _avertir_si_suspect(paire: univers.Paire, timeframe: str) -> None:
    if not config.CATALOGUE.exists():
        return
    try:
        with duckdb.connect(str(config.CATALOGUE), read_only=True) as conn:
            conn.execute("SET TimeZone='UTC'")
            ligne = conn.execute(
                "SELECT couverture_pct, bougies_manquantes, plus_grand_trou_h"
                " FROM datasets WHERE paire = ? AND timeframe = ? AND suspect",
                [paire.symbole, timeframe]).fetchone()
    except duckdb.Error:
        return          # le catalogue n'est pas une dependance dure de la lecture
    if ligne:
        log.warning("%s %s est marquee SUSPECTE au catalogue : couverture %.2f %%, "
                    "%d bougies manquantes, plus grand trou %.1f h",
                    paire.base, timeframe, *ligne)


def catalogue() -> pd.DataFrame:
    """Ce que contient le lake. A lire avant de lancer quoi que ce soit dessus."""
    from beta.lake import catalogue
    return catalogue.etat()
