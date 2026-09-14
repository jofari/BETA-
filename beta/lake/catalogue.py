"""Le catalogue du lake : ce qu'on possede, et ce que ca vaut.

Separe de la construction a dessein. Convertir un fichier et DECLARER ce qu'il contient sont
deux responsabilites differentes : la premiere echoue bruyamment, la seconde est la seule
protection contre une panne silencieuse. Une serie trouee ne leve aucune exception — elle
produit un backtest faux, et personne ne s'en apercoit avant d'avoir bati dessus.
"""

from __future__ import annotations

import logging
import pathlib
import shutil

import duckdb
import pandas as pd

from beta import config
from beta.lake import univers

log = logging.getLogger("beta.lake.catalogue")

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


def inscrire(audit: dict, paire: univers.Paire | univers.Indice, timeframe: str,
             fichier: pathlib.Path, doublons: int, source: str, marche: str | None = None,
             tolerance_pct: float | None = None, trou_max_h: float | None = None) -> None:
    """Declare la serie au catalogue, et decide si elle est SUSPECTE.

    Par defaut (les perpetuels) : suspecte sous `config.TROUS_PCT_ALERTE` de trous. Les
    indices quotidiens passent une tolerance plus large (les jours feries ne sont pas des
    trous) et un second critere, le plus grand trou en heures — une semaine qui manque au
    milieu d'une serie a 97 % de couverture est exactement ce qu'une tolerance en pourcentage
    ne voit pas.
    """
    tolerance = config.TROUS_PCT_ALERTE if tolerance_pct is None else float(tolerance_pct)
    suspect = bool(audit["couverture_pct"] < 100.0 - tolerance)
    if trou_max_h is not None and audit["plus_grand_trou_h"] > trou_max_h:
        suspect = True
    with _catalogue() as conn:
        conn.execute("DELETE FROM datasets WHERE paire = ? AND timeframe = ?",
                     [paire.symbole, timeframe])
        conn.execute(
            "INSERT INTO datasets (paire, timeframe, marche, fichier, n_bougies, debut, fin,"
            " bougies_attendues, bougies_manquantes, couverture_pct, plus_grand_trou_h,"
            " doublons_retires, suspect, source, maj)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?, now())",
            [paire.symbole, timeframe, marche or config.TRADING_MODE, str(fichier),
             audit["n_bougies"], audit["debut"], audit["fin"], audit["bougies_attendues"],
             audit["bougies_manquantes"], audit["couverture_pct"],
             audit["plus_grand_trou_h"], doublons, suspect, source])
    if suspect:
        log.warning("%s %s : couverture %.2f %% (%d bougies manquantes, plus grand trou "
                    "%.1f h) — SUSPECT", paire.base, timeframe, audit["couverture_pct"],
                    audit["bougies_manquantes"], audit["plus_grand_trou_h"])



def etat() -> pd.DataFrame:
    """Le catalogue, lisible. La colonne `suspect` est la seule a regarder en premier."""
    if not config.CATALOGUE.exists():
        return pd.DataFrame()
    with _catalogue() as conn:
        return conn.execute(
            "SELECT paire, timeframe, marche, n_bougies, debut, fin, couverture_pct,"
            " bougies_manquantes, plus_grand_trou_h, suspect, source, maj"
            " FROM datasets ORDER BY marche, paire, timeframe").df()


def purger() -> None:
    """Remet le lake a zero. `data/` est jetable (invariant n° 7)."""
    if config.LAKE.exists():
        shutil.rmtree(config.LAKE)
    config.preparer_dossiers()
