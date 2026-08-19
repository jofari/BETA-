"""P1 — le dashboard lance Claude Code avec le contexte d'un run.

Modele repris de `ALPHA/alpha/actions.py`, y compris ses deux garde-fous, qui ne sont pas
negociables ici non plus :

1. **Le client n'envoie jamais de commande.** Il envoie un nom d'action pris dans `ACTIONS`
   et un `run_id`. Le serveur reconstruit tout le reste. Aucun endpoint n'execute une
   chaine fournie par le navigateur.
2. **Tout texte qui atteint un shell passe par `nettoyer`.** Y compris — et surtout — le
   texte lu sur le disque : nom de candidate, reserves, motifs de verdict. Ce sont des
   donnees, pas du code, et rien ne garantit qu'elles ne contiennent pas de guillemets, de
   `&&` ou de retours a la ligne.

Le prompt genere porte le verdict ET ses reserves. C'est le point : demander a un agent de
« regarder ce run » sans lui dire quelles portes ont echoue revient a lui demander de
redecouvrir ce que la batterie vient d'etablir.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
import subprocess
from pathlib import Path

from beta import config

log = logging.getLogger("beta.rapport.actions")

ACTIONS = ("claude", "dossier")
PROMPT_MAX = 1200
CMD_DIR = config.DATA / "cmd"

# Tout ce qui n'est pas dans cette classe est remplace par un espace. Liste volontairement
# etroite : un prompt n'a besoin ni de guillemets, ni de pipes, ni de chevrons.
AUTORISES = re.compile(r"[^A-Za-z0-9 ÀÂÄÇÉÈÊËÎÏÔÖÙÛÜàâäçéèêëîïôöùûü_\-.,:;!?/%+=()\[\]']")


class ActionError(RuntimeError):
    """Action refusee, ou lancement impossible."""


def nettoyer(texte: str, maximum: int = PROMPT_MAX) -> str:
    return AUTORISES.sub(" ", str(texte or ""))[:maximum].strip()


def prompt_du_run(verdict: dict) -> str:
    """Le contexte d'un run, en clair, pret a etre lu par un agent."""
    metriques = verdict.get("metriques") or {}
    echouees = ", ".join(verdict.get("portes_echouees") or []) or "aucune"
    non_executees = ", ".join(verdict.get("portes_non_executees") or []) or "aucune"
    reserves = " | ".join(verdict.get("reserves") or [])
    morceaux = [
        f"Run BETA {verdict.get('run_id')} sur la candidate {verdict.get('candidate')}",
        f"(experience {verdict.get('experience')}, split {verdict.get('split')}).",
        f"Issue : {verdict.get('issue')}.",
        f"n = {metriques.get('n')}, R moyen {metriques.get('r_moyen')},"
        f" MDE {metriques.get('mde_r')}, essai cumule n {verdict.get('n_essais_cumules')}.",
        f"Portes echouees : {echouees}. Portes non executees : {non_executees}.",
        f"Reserves : {reserves}." if reserves else "",
        "Dis ce que ce verdict permet de conclure, et ce qu'il ne permet pas.",
    ]
    return nettoyer(" ".join(m for m in morceaux if m))


def _script(nom: str, lignes: list[str]) -> Path:
    """Ecrit un .cmd jetable. Passer par un fichier evite toute citation dans la commande."""
    CMD_DIR.mkdir(parents=True, exist_ok=True)
    chemin = CMD_DIR / f"{nom}.cmd"
    contenu = "@echo off\r\n" + "\r\n".join(lignes) + "\r\npause\r\n"
    chemin.write_text(contenu, encoding="utf-8")
    return chemin


def _ouvrir_terminal(dossier: Path, script: Path | None = None) -> str:
    argv = ["cmd", "/c", "start", "", "cmd", "/k",
            str(script) if script else "cd /d " + str(dossier)]
    try:
        subprocess.Popen(argv, cwd=str(dossier), close_fds=True)   # noqa: S603
    except OSError as exc:
        raise ActionError(f"terminal impossible a ouvrir ({exc})") from exc
    return "terminal ouvert"


def executer(action: str, verdict: dict) -> dict:
    """Execute une action de la liste blanche pour un run donne."""
    if action not in ACTIONS:
        raise ActionError(f"action refusee : {action}")
    run_id = nettoyer(verdict.get("run_id") or "", 32)

    if action == "dossier":
        cible = config.DATA / "runs" / run_id
        if not cible.is_dir():
            raise ActionError(f"dossier du run introuvable : {cible}")
        try:
            os.startfile(str(cible))                     # noqa: S606 - chemin local, pas
        except OSError as exc:                           # une chaine venue du client
            raise ActionError(f"explorateur indisponible ({exc})") from exc
        return {"ok": True, "message": "dossier du run ouvert"}

    prompt = prompt_du_run(verdict).replace("%", "%%")
    empreinte = hashlib.sha1(run_id.encode("utf-8")).hexdigest()[:10]
    script = _script(f"claude-{empreinte}", [f'claude "{prompt}"'])
    message = _ouvrir_terminal(config.RACINE, script)
    log.info("Claude Code lance sur le run %s", run_id)
    return {"ok": True, "message": f"{message} — Claude Code lance", "prompt": prompt}
