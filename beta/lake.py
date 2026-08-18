"""Construction du lake : feather -> parquet, avec un catalogue qui declare les trous.

Le lake existe pour repondre a une seule question, une fois pour toutes : ou sont les
donnees, et que valent-elles ? D'ou deux sorties, jamais l'une sans l'autre :

1. un parquet par (paire, timeframe), colonnes normalisees, index temporel strictement
   croissant, sans doublon, en UTC ;
2. une ligne de catalogue disant la couverture REELLE et le nombre de bougies MANQUANTES.

Le point 2 est le plus important. Une serie trouee ne leve aucune exception : elle produit
un backtest faux, en silence, et personne ne s'en apercoit avant d'avoir bati dessus. Le
catalogue rend le trou visible sans qu'on ait a y penser (invariant n° 3).
"""

from __future__ import annotations

import logging
import pathlib
import shutil

import duckdb
import pandas as pd

from beta import config, univers

log = logging.getLogger("beta.lake")

COLONNES = ("date", "open", "high", "low", "close", "volume")

SCHEMA_CATALOGUE = """
CREATE TABLE IF NOT EXISTS datasets (
    paire            VARCHAR NOT NULL,
    timeframe        VARCHAR NOT NULL,
    marche           VARCHAR NOT NULL,
    fichier          VARCHAR NOT NULL,
    n_bougies        BIGINT  NOT NULL,
    debut            TIMESTAMPTZ,
    fin              TIMESTAMPTZ,
    bougies_attendues BIGINT,
    bougies_manquantes BIGINT,
    couverture_pct   DOUBLE,
    plus_grand_trou_h DOUBLE,
    doublons_retires BIGINT,
    suspect          BOOLEAN,
    source           VARCHAR,
    maj              TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (paire, timeframe)
)
"""


class LakeError(RuntimeError):
    """Conversion impossible : source absente, illisible ou inexploitable."""


def _lire_feather(chemin: pathlib.Path) -> pd.DataFrame:
    try:
        df = pd.read_feather(chemin)
    except (OSError, ValueError) as exc:
        raise LakeError(f"lecture impossible ({chemin.name}) : {exc}") from exc
    manquantes = [c for c in COLONNES if c not in df.columns]
    if manquantes:
        raise LakeError(f"{chemin.name} : colonnes absentes {manquantes}")
    return df[list(COLONNES)]


def normaliser(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """UTC, tri chronologique, doublons de timestamp retires. Retourne (df, n_doublons).

    Les doublons viennent des reprises de telechargement : freqtrade concatene et ne
    dedoublonne pas toujours. Un doublon non retire compte deux fois la meme bougie dans un
    backtest — silencieusement, la aussi. On garde la DERNIERE occurrence, la plus recente.
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], utc=True)
    avant = len(df)
    df = (df.sort_values("date")
            .drop_duplicates(subset="date", keep="last")
            .reset_index(drop=True))
    return df, avant - len(df)


def auditer(df: pd.DataFrame, timeframe: str) -> dict:
    """Couverture reelle : combien de bougies manquent entre la premiere et la derniere.

    On ne compare pas a une date de listing theorique — inconnue et sujette a debat — mais a
    l'intervalle effectivement couvert. La question a laquelle ca repond est : « cette serie
    est-elle continue ? », pas « remonte-t-elle assez loin ? ». La seconde se lit dans
    `debut`.
    """
    if df.empty:
        return {"n_bougies": 0, "debut": None, "fin": None, "bougies_attendues": 0,
                "bougies_manquantes": 0, "couverture_pct": 0.0, "plus_grand_trou_h": 0.0}
    pas = pd.Timedelta(minutes=univers.pas_minutes(timeframe))
    debut, fin = df["date"].iloc[0], df["date"].iloc[-1]
    attendues = int((fin - debut) / pas) + 1
    ecarts = df["date"].diff().dropna()
    plus_grand = float(ecarts.max() / pd.Timedelta(hours=1)) if len(ecarts) else 0.0
    manquantes = max(attendues - len(df), 0)
    return {"n_bougies": len(df), "debut": debut, "fin": fin,
            "bougies_attendues": attendues, "bougies_manquantes": manquantes,
            "couverture_pct": round(100.0 * len(df) / attendues, 4) if attendues else 0.0,
            "plus_grand_trou_h": round(plus_grand, 3)}


def _catalogue():
    """Connexion au catalogue, forcee en UTC.

    Sans le `SET TimeZone`, DuckDB RESTITUE les TIMESTAMPTZ dans le fuseau de la machine :
    le stockage reste juste, mais le catalogue affiche « BTC commence a 19:00 » pour une
    bougie de 17:00 UTC. Un decalage d'affichage sur une donnee temporelle finit toujours
    par etre lu comme la donnee elle-meme (invariant : tout en UTC, sans exception).
    """
    config.preparer_dossiers()
    conn = duckdb.connect(str(config.CATALOGUE))
    conn.execute("SET TimeZone='UTC'")
    conn.execute(SCHEMA_CATALOGUE)
    return conn


def inscrire(audit: dict, paire: univers.Paire, timeframe: str, fichier: pathlib.Path,
             doublons: int, source: str) -> None:
    suspect = bool(audit["couverture_pct"] < 100.0 - config.TROUS_PCT_ALERTE)
    with _catalogue() as conn:
        conn.execute("DELETE FROM datasets WHERE paire = ? AND timeframe = ?",
                     [paire.symbole, timeframe])
        conn.execute(
            "INSERT INTO datasets (paire, timeframe, marche, fichier, n_bougies, debut, fin,"
            " bougies_attendues, bougies_manquantes, couverture_pct, plus_grand_trou_h,"
            " doublons_retires, suspect, source, maj)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?, now())",
            [paire.symbole, timeframe, config.TRADING_MODE, str(fichier),
             audit["n_bougies"], audit["debut"], audit["fin"], audit["bougies_attendues"],
             audit["bougies_manquantes"], audit["couverture_pct"],
             audit["plus_grand_trou_h"], doublons, suspect, source])
    if suspect:
        log.warning("%s %s : couverture %.2f %% (%d bougies manquantes, plus grand trou "
                    "%.1f h) — SUSPECT", paire.base, timeframe, audit["couverture_pct"],
                    audit["bougies_manquantes"], audit["plus_grand_trou_h"])


def convertir(paire: univers.Paire, timeframe: str, source: pathlib.Path,
              origine: str) -> dict:
    """feather -> parquet + ligne de catalogue. Retourne l'audit."""
    if not source.exists():
        raise LakeError(f"source absente : {source}")
    df, doublons = normaliser(_lire_feather(source))
    audit = auditer(df, timeframe)
    cible = config.chemin_parquet(paire.slug, timeframe)
    cible.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_parquet(cible, index=False, compression="zstd")
    except (OSError, ValueError) as exc:
        raise LakeError(f"ecriture parquet impossible ({cible.name}) : {exc}") from exc
    inscrire(audit, paire, timeframe, cible, doublons, origine)
    log.info("%-5s %-3s %7d bougies · %s -> %s · couverture %.2f %%%s",
             paire.base, timeframe, audit["n_bougies"],
             str(audit["debut"])[:10], str(audit["fin"])[:10], audit["couverture_pct"],
             f" · {doublons} doublon(s) retire(s)" if doublons else "")
    return audit


def importer_depuis_arit(paire: univers.Paire, timeframe: str) -> dict:
    """Les 4 paires historiques : on prend le feather d'ARIT tel quel, en LECTURE SEULE.

    Retelecharger ce qui est deja sur disque coute ~27 min pour un resultat identique au bit
    pres. ARIT n'est jamais ecrit (invariant n° 1) : `pd.read_feather` ouvre en lecture.
    """
    return convertir(paire, timeframe, config.chemin_feather_arit(paire.slug, timeframe),
                     origine="arit2.0")


def integrer_telechargement(paire: univers.Paire, timeframe: str) -> dict:
    """Les paires nouvelles, deposees par freqtrade dans `data/raw/`."""
    return convertir(paire, timeframe, config.chemin_feather_brut(paire.slug, timeframe),
                     origine="freqtrade download-data")


def etat() -> pd.DataFrame:
    """Le catalogue, lisible. La colonne `suspect` est la seule a regarder en premier."""
    if not config.CATALOGUE.exists():
        return pd.DataFrame()
    with _catalogue() as conn:
        return conn.execute(
            "SELECT paire, timeframe, n_bougies, debut, fin, couverture_pct,"
            " bougies_manquantes, plus_grand_trou_h, suspect, source, maj"
            " FROM datasets ORDER BY paire, timeframe").df()


def purger() -> None:
    """Remet le lake a zero. `data/` est jetable (invariant n° 7)."""
    if config.LAKE.exists():
        shutil.rmtree(config.LAKE)
    config.preparer_dossiers()
