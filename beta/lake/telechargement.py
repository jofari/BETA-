"""Telechargement des paires que BETA n'a pas encore, via `freqtrade download-data`.

Pourquoi freqtrade plutot qu'un appel ccxt direct : il connait deja la pagination de
Binance, ses limites de debit, le format de fichier, et il sait REPRENDRE un telechargement
partiel. Reecrire ca serait reecrire un bug par bug.

Deux regles, toutes deux demandees par Jonas le 18/08 :
1. **on ne retelecharge jamais ce qui est deja sur disque** — les 4 paires historiques
   viennent d'ARIT par simple lecture (cf. `lake.importer_depuis_arit`) ;
2. **les paires se telechargent SIMULTANEMENT** — le repere connu est ~27 min pour 4 paires
   en sequentiel ; l'attente est du reseau, pas du calcul, donc elle se parallelise.

Le parallelisme reste volontairement modeste (un processus par paire, pas par timeframe) :
au-dela, Binance repond par des limites de debit et le gain s'inverse.

Les INDICES (spike du 14/09) suivent un autre chemin, `telecharger_indices` : yfinance, en
quotidien, en sequentiel — 5 requetes de quelques milliers de lignes, l'attente est
negligeable et Yahoo repond 429 des qu'on le presse. Ils entrent au lake par la meme porte
que tout le reste (`construction.deposer`) : meme schema parquet, meme catalogue.
"""

from __future__ import annotations

import logging
import pathlib
import shutil
import subprocess
import sys
import time

import pandas as pd

from beta import config
from beta.lake import construction, univers

log = logging.getLogger("beta.download")

ORIGINE_INDICES = "yfinance"
INTERVALLE_INDICES = "1d"

# Ce que yfinance appelle les colonnes, et ce que le lake attend. `Adj Close` est ignore
# volontairement : on garde les prix IMPRIMES (auto_adjust=False), comme pour les
# perpetuels. Sur 5 series, 4 sont des indices de prix sans dividende ; ajuster URTH seul
# en ferait une serie de rendement total au milieu de series de prix.
COLONNES_YFINANCE = {"Open": "open", "High": "high", "Low": "low", "Close": "close",
                     "Volume": "volume"}


class DownloadError(RuntimeError):
    """Telechargement impossible ou echoue."""


def _binaire() -> str:
    """Le freqtrade du venv COURANT d'abord, le PATH ensuite.

    Le venv n'est pas forcement active dans le shell qui lance BETA : chercher a cote de
    `sys.executable` est ce qui rend le script utilisable tel quel, sans activation.
    """
    voisin = pathlib.Path(sys.executable).parent / (
        "freqtrade.exe" if sys.platform == "win32" else "freqtrade")
    if voisin.exists():
        return str(voisin)
    chemin = shutil.which("freqtrade")
    if chemin:
        return chemin
    raise DownloadError(
        "freqtrade introuvable, ni a cote de l'interpreteur ni dans le PATH. Lancer avec "
        r"C:\Users\jofar\venvs\arit\Scripts\python.exe")


def commande(paire: univers.Paire, timeframes: tuple[str, ...] = univers.TIMEFRAMES) -> list[str]:
    """La commande exacte, construite ici et nulle part ailleurs.

    `--erase` n'y figure pas et ne doit pas y figurer : une reprise doit completer, pas
    detruire ce qui est deja telecharge.

    `--userdir` est obligatoire : freqtrade exige un `user_data`, meme pour un telechargement
    qui n'en lit rien. Sans lui, il le cherche dans le repertoire courant et sort en code 2.
    """
    return [_binaire(), "download-data",
            "--exchange", config.EXCHANGE,
            "--trading-mode", config.TRADING_MODE,
            "--pairs", paire.symbole,
            "--timeframes", *timeframes,
            "--timerange", f"{paire.depuis}-",
            "--datadir", str(config.BRUT),
            "--userdir", str(config.USERDIR)]


def telecharger(paires: tuple[univers.Paire, ...] | None = None,
                timeframes: tuple[str, ...] = univers.TIMEFRAMES,
                timeout_s: int = config.TIMEOUT_TELECHARGEMENT_S) -> dict[str, str]:
    """Lance un processus par paire, en parallele, et attend. Retourne {base: etat}.

    Un echec sur une paire n'annule pas les autres : on rapporte, on ne fait pas tout
    tomber. Ce qui a ete telecharge reste utilisable.
    """
    paires = paires if paires is not None else univers.a_telecharger()
    if not paires:
        log.info("rien a telecharger : toutes les paires de l'univers sont deja sur disque")
        return {}
    config.preparer_dossiers()

    processus = {}
    for paire in paires:
        log.info("telechargement %s (%s, depuis %s) — demarre",
                 paire.base, " ".join(timeframes), paire.depuis)
        try:
            processus[paire.base] = subprocess.Popen(
                commande(paire, timeframes),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", errors="replace")
        except OSError as exc:
            raise DownloadError(f"lancement impossible pour {paire.base} : {exc}") from exc

    debut = time.monotonic()
    resultats: dict[str, str] = {}
    for base, proc in processus.items():
        restant = max(timeout_s - (time.monotonic() - debut), 1)
        try:
            sortie, _ = proc.communicate(timeout=restant)
        except subprocess.TimeoutExpired:
            proc.kill()
            sortie = ""
            resultats[base] = f"TIMEOUT apres {timeout_s} s"
            log.error("%s : timeout", base)
            continue
        if proc.returncode == 0:
            resultats[base] = "ok"
            log.info("%s : telechargement termine (%.1f min)",
                     base, (time.monotonic() - debut) / 60)
        else:
            derniere = (sortie or "").strip().splitlines()[-1:] or ["(aucune sortie)"]
            resultats[base] = f"echec (code {proc.returncode}) : {derniere[0][:200]}"
            log.error("%s : %s", base, resultats[base])
    return resultats


# --- indices : yfinance, quotidien --------------------------------------------------------

def normaliser_yfinance(brut: pd.DataFrame,
                        aujourd_hui: pd.Timestamp | None = None) -> pd.DataFrame:
    """Le DataFrame de `yfinance.Ticker.history` -> OHLCV au format du lake.

    yfinance indexe par un Datetime dans le fuseau de la BOURSE (New York pour ^GSPC,
    Paris pour ^FCHI). Une bougie quotidienne porte ici la date calendaire de sa seance,
    a minuit UTC : c'est la meme convention que le 1d des perpetuels, et c'est ce qui permet
    a une jointure macro (FRED, minuit UTC) de tomber juste.

    La bougie du jour COURANT est retiree : tant que la seance n'est pas close, son `close`
    n'en est pas un, et un lake qui la garde change de valeur a chaque telechargement — le
    genre de bougie qui fabrique un faux signal de fin de journee sans que rien ne le dise.
    """
    if brut is None or brut.empty:
        return pd.DataFrame(columns=list(construction.COLONNES))
    absentes = [c for c in COLONNES_YFINANCE if c not in brut.columns]
    if absentes:
        raise DownloadError(f"yfinance : colonnes absentes {absentes}")
    df = brut[list(COLONNES_YFINANCE)].rename(columns=COLONNES_YFINANCE)
    index = pd.DatetimeIndex(df.index)
    if index.tz is not None:
        index = index.tz_localize(None)         # l'heure MURALE de la bourse, sans fuseau
    df = df.set_axis(index.normalize().tz_localize("UTC"), axis=0)
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df.rename_axis("date").reset_index()
    if aujourd_hui is None:
        aujourd_hui = pd.Timestamp.now(tz="UTC")
    else:
        aujourd_hui = pd.Timestamp(aujourd_hui)
        aujourd_hui = (aujourd_hui.tz_localize("UTC") if aujourd_hui.tz is None
                       else aujourd_hui.tz_convert("UTC"))
    df = df[df["date"] < aujourd_hui.normalize()].copy()
    for colonne in ("open", "high", "low", "close", "volume"):
        df[colonne] = pd.to_numeric(df[colonne], errors="coerce").astype(float)
    return df[list(construction.COLONNES)].reset_index(drop=True)


def _historique(indice: univers.Indice) -> pd.DataFrame:
    """L'appel reseau, isole : c'est lui que les tests remplacent."""
    try:
        import yfinance as yf
    except ImportError as exc:
        raise DownloadError(
            "yfinance absent du venv : "
            "`uv pip install --python <python du venv> yfinance`") from exc
    debut = pd.Timestamp(indice.depuis).date().isoformat()       # AAAAMMJJ -> ISO
    try:
        return yf.Ticker(indice.ticker).history(
            start=debut, interval=INTERVALLE_INDICES, auto_adjust=False, actions=False)
    except Exception as exc:                          # noqa: BLE001 - yfinance leve de tout
        raise DownloadError(f"{indice.ticker} : {exc}") from exc


def telecharger_indices(indices: tuple[univers.Indice, ...] | None = None
                        ) -> dict[str, str]:
    """yfinance -> `data/lake/{slug}-1d.parquet` + ligne de catalogue. Retourne {base: etat}.

    Sequentiel et complet a chaque appel : l'historique quotidien d'un indice depuis 2010
    pese quelques milliers de lignes, et Yahoo tolere mieux cinq requetes espacees que cinq
    simultanees. Un echec sur un indice n'annule pas les autres, comme pour les paires.
    """
    indices = indices if indices is not None else univers.INDICES
    config.preparer_dossiers()
    resultats: dict[str, str] = {}
    for indice in indices:
        log.info("telechargement %s (%s, 1d, depuis %s) — demarre",
                 indice.base, indice.ticker, indice.depuis)
        try:
            df = normaliser_yfinance(_historique(indice))
            if df.empty:
                raise DownloadError(f"{indice.ticker} : aucune bougie rendue par yfinance")
            construction.deposer(indice, INTERVALLE_INDICES, df, ORIGINE_INDICES,
                                 calendrier=construction.CALENDRIER_OUVRE)
        except (DownloadError, construction.LakeError) as exc:
            resultats[indice.base] = f"echec : {exc}"
            log.error("%s : %s", indice.base, exc)
            continue
        resultats[indice.base] = "ok"
    return resultats
