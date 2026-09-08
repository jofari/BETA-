"""Chemins et constantes de BETA. Le SEUL endroit ou un chemin de donnees est ecrit.

Invariant n° 2 : personne d'autre ne construit un chemin OHLCV. Le but du projet est qu'on
ne cherche plus jamais ou sont les donnees.
"""

from __future__ import annotations

import os
import pathlib

RACINE = pathlib.Path(__file__).resolve().parents[1]

DATA = RACINE / "data"
LAKE = DATA / "lake"                     # parquet, une table par (paire, timeframe)
BRUT = DATA / "raw"                      # zone de depot de freqtrade download-data (feather)
USERDIR = DATA / "user_data"             # freqtrade EXIGE un user_data, meme pour un simple
                                         # download : il le cherche dans le CWD si on ne le
                                         # lui donne pas, et sort en erreur s'il manque
CATALOGUE = LAKE / "catalogue.duckdb"    # metadonnees : couverture, trous, provenance
JOURNAL = DATA / "build_lake.log"

# ARIT est LU, jamais ecrit (invariant n° 1). Surchargeable pour les tests et si le depot
# demenage — mais jamais en dur ailleurs que dans ce fichier.
ARIT = pathlib.Path(os.environ.get("ARIT_HOME", r"C:\Users\jofar\ARIT2.0"))
ARIT_DATA = ARIT / "user_data" / "data" / "binance" / "futures"

EXCHANGE = "binance"
TRADING_MODE = "futures"

# Un fichier parquet par (paire, timeframe). A 6 paires c'est le bon grain : ~630 k lignes
# en 5m sur 6 ans, soit une quinzaine de Mo compresses, que DuckDB lit sans les charger.
# Repartir par annee ne se justifiera qu'au-dela de ~50 paires — le noter plutot que le
# faire trop tot.
SEUIL_PARTITION_PAR_ANNEE = 50

# Tolerance de trous. Au-dela, la serie est marquee SUSPECTE au catalogue : un backtest sur
# une serie trouee produit des resultats faux EN SILENCE (invariant n° 3).
TROUS_PCT_ALERTE = 1.0

TIMEOUT_TELECHARGEMENT_S = 3600          # repere mesure : ~27 min pour 4 paires en sequentiel


def chemin_parquet(slug: str, timeframe: str) -> pathlib.Path:
    return LAKE / f"{slug}-{timeframe}.parquet"


def chemin_feather_arit(slug: str, timeframe: str) -> pathlib.Path:
    return ARIT_DATA / f"{slug}-{timeframe}-{TRADING_MODE}.feather"


def chemin_feather_funding(slug: str) -> pathlib.Path:
    """Taux de financement 8h d'une paire, telecharge par freqtrade dans ARIT (lecture seule).

    freqtrade depose le funding sous le suffixe `-1h-funding_rate` (une ligne par periode
    de 8h), a cote des bougies `-{tf}-futures`. Le 1h est trompeur : le pas reel est 8h.
    """
    return ARIT_DATA / f"{slug}-1h-funding_rate.feather"


def chemin_feather_brut(slug: str, timeframe: str) -> pathlib.Path:
    # `--datadir` designe DEJA le dossier de l'exchange : freqtrade y depose directement
    # `futures/`, sans re-creer un niveau `binance/`. Verifie sur le telechargement du 18/08.
    return BRUT / TRADING_MODE / f"{slug}-{timeframe}-{TRADING_MODE}.feather"


# Sous-dossiers que freqtrade cree lui-meme au demarrage. On les cree AVANT de lancer quoi
# que ce soit : deux processus simultanes les creent sinon en meme temps, et le perdant sort
# sur FileExistsError (WinError 183). Constate le 18/08 sur LINK et XRP en parallele.
USERDIR_SOUS_DOSSIERS = ("logs", "data", "strategies", "notebooks", "plot",
                         "hyperopts", "hyperopt_results", "backtest_results")


def preparer_dossiers() -> None:
    for dossier in (DATA, LAKE, BRUT, USERDIR):
        dossier.mkdir(parents=True, exist_ok=True)
    for nom in USERDIR_SOUS_DOSSIERS:
        (USERDIR / nom).mkdir(parents=True, exist_ok=True)
