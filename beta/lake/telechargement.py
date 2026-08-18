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
"""

from __future__ import annotations

import logging
import pathlib
import shutil
import subprocess
import sys
import time

from beta import config
from beta.lake import univers

log = logging.getLogger("beta.download")


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
