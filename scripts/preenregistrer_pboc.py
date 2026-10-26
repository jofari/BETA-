"""Preenregistrement de PBOC — PBO de la grille de la voie C, DIAGNOSTIC (aucun essai).

    /root/venvs/beta/bin/python scripts/preenregistrer_pboc.py

Prompt de Jonas du 2026-10-25 (phase 3), ses reponses du 25/10 21:16 et du 26/10, figes mot pour
mot dans pbo_voie_c/PREENREGISTREMENT.md. Journalise PBOC dans EXPERIMENTS.jsonl avec
`diagnostic=True`, famille invest : le compteur ne bouge pas. Idempotent.
"""

from __future__ import annotations

import hashlib
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta import config  # noqa: E402
from beta.pbo_voie_c import regles  # noqa: E402
from beta.protocole import experiences  # noqa: E402

log = logging.getLogger("beta.preenregistrer_pboc")

TEXTE = config.RACINE / "pbo_voie_c" / "PREENREGISTREMENT.md"


def empreinte_texte() -> str:
    return hashlib.sha256(TEXTE.read_bytes()).hexdigest()[:16]


HYPOTHESE = ("La meilleure configuration de la grille de la voie C (voie_c_optim, dedoublonnee "
             "par l'option b) sur une moitie des blocs ne finit pas dans la moitie basse sur "
             "l'autre moitie : PBO par CSCV inferieure a 20 %, apres deux controles reussis.")

METRIQUE = ("PBO par CSCV, Sharpe, 16 blocs de 119 jours du 2021-06-20 au 2026-09-05 ; "
            "controles : positif (Sharpe 3, graine 0, PBO <= 10 %), negatif (moyenne des "
            "graines 1001-1100 dans [45 % ; 55 %]).")

DEJA_CONNU = (
    "Grille mesuree le 03/10 sur le train, OOS 2024-07-01 -> 2026-09-05 imprime pour la config "
    "retenue et la reference : le hold-out 2025-01-01 -> 2026-09-05 est deja vu, la PBO est un "
    "diagnostic de surajustement, pas une validation hors echantillon. PBO jamais calculee. "
    "Simulation de conception du 25/10 sur les graines 1 a 600 seulement, sans donnee de la "
    "voie C : negatif 49,1 % en moyenne ; positif Sharpe 3 -> mediane 0,0 %, Sharpe 1 -> "
    "43,4 %. Graines 0 et 1001-1100 jamais tirees.")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    if regles.ID_EXP in experiences.etat():
        log.info("%s deja journalisee : rien a ecrire", regles.ID_EXP)
        return 0
    avant = {"global": experiences.compteur_total(),
             "invest": experiences.compteur(famille="invest")}
    entree = experiences.preenregistrer(
        regles.ID_EXP, HYPOTHESE, METRIQUE, regles.REGLES["verdict"],
        split_autorise="rendements de la grille du 2021-06-20 au 2026-09-05 (train, OOS et "
                       "hold-out deja vus) ; rien apres le 2026-09-05",
        issue_attendue="non renseignee : le verdict est mecanique",
        deja_connu=DEJA_CONNU, famille_compteur="invest", diagnostic=True,
        decide_par="Jonas : prompt du 2026-10-25 (phase 3), reponses du 2026-10-25 21:16 UTC "
                   "(option b, cible 20 %, fenetre, seuil 20 %, deux controles) et du "
                   "2026-10-26 (controle positif Sharpe 3 <= 10 %, negatif 1001-1100 dans "
                   "[45 % ; 55 %], lectures confirmees, phrase sur la puissance)",
        regles=regles.REGLES, empreinte=regles.empreinte(),
        empreinte_preenregistrement=empreinte_texte(), compteur_avant=avant)
    apres = {"global": experiences.compteur_total(),
             "invest": experiences.compteur(famille="invest")}
    log.info("%s journalisee (diagnostic) — regles %s, texte %s ; compteur global %d -> %d, "
             "invest %d -> %d", regles.ID_EXP, entree["empreinte"],
             entree["empreinte_preenregistrement"], avant["global"], apres["global"],
             avant["invest"], apres["invest"])
    if apres != avant:
        log.error("le compteur a bouge : ce n'est pas un diagnostic")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
