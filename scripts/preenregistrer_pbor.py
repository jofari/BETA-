"""Preenregistrement de PBOR — PBO du passe, DIAGNOSTIC (aucun essai, aucun verdict modifie).

    /root/venvs/beta/bin/python scripts/preenregistrer_pbor.py

Reponses de Jonas du 2026-10-26 figees mot pour mot dans pbo_passe/PREENREGISTREMENT.md.
Journalise PBOR dans EXPERIMENTS.jsonl avec `diagnostic=True` : le compteur ne bouge pas.
Idempotent.
"""

from __future__ import annotations

import hashlib
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta import config  # noqa: E402
from beta.pbo_passe import regles  # noqa: E402
from beta.protocole import experiences  # noqa: E402

log = logging.getLogger("beta.preenregistrer_pbor")

TEXTE = config.RACINE / "pbo_passe" / "PREENREGISTREMENT.md"


def empreinte_texte() -> str:
    return hashlib.sha256(TEXTE.read_bytes()).hexdigest()[:16]


HYPOTHESE = ("Rejouee sur ce qui existait avant elle, la porte S10 (PBO par CSCV < 20 %) dit si "
             "le choix de la meilleure candidate des 3 lots de trading de septembre, et de la "
             "meilleure des 6 variantes de la voie C du 22/09, releve du surapprentissage. "
             "Diagnostic : rapport seul.")

METRIQUE = ("PBO par CSCV de beta.stats.pbo (porte S10) : 16 blocs contigus, Sharpe ; lots : "
            "somme quotidienne des R clotures, du premier au dernier jour de cloture du lot ; "
            "voie C : r_net quotidien des 6 variantes, du premier jour ou elles existent toutes "
            "au 2026-09-05.")

DEJA_CONNU = (
    "Les 13 runs des 3 lots sont deja juges : tous INFIRMES (S7 : meilleure r10_disjonction "
    "dans L1, liquidity_ny_stop_150 dans L2, auto_r7_03 dans L3). Une porte ne peut que "
    "degrader : aucun verdict ne peut changer, et aucun ne sera modifie. PBOC (26/10) : PBO "
    "de la grille de 5 760 de la voie C = 9,9 %. Variantes du 22/09 : selection imprimee par "
    "le script a l'epoque (scripts du 22-24/09 archives, repris dans voie_c_voltarget.py le "
    "25/09) ; OOS et hold-out jusqu'au 05/09/2026 deja vus. Aucune PBO de ces lots ni de ces "
    "variantes n'a jamais ete calculee ; aucun rendement n'a ete relu pour preparer ce texte.")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    if regles.ID_EXP in experiences.etat():
        log.info("%s deja journalisee : rien a ecrire", regles.ID_EXP)
        return 0
    avant = {"global": experiences.compteur_total(),
             "trading": experiences.compteur(famille="trading"),
             "invest": experiences.compteur(famille="invest")}
    entree = experiences.preenregistrer(
        regles.ID_EXP, HYPOTHESE, METRIQUE,
        {"pbo": regles.REGLES["seuil"],
         "lecture": "rapport seul : la porte S10 aurait ete franchie, aurait echoue ou "
                    "n'aurait pas ete executee ; aucun verdict modifie"},
        split_autorise="trades deja enregistres des 3 lots (train) ; voie C : rendements "
                       "jusqu'au 2026-09-05 (OOS et hold-out deja vus) ; rien apres",
        issue_attendue="non renseignee : la lecture est mecanique",
        deja_connu=DEJA_CONNU, famille_compteur="trading", diagnostic=True,
        decide_par="Jonas, 26/10/2026 au soir : porte obligatoire, PBO < 20 %, recalculer le "
                   "passe (rapport seul) ; periode des variantes de la voie C comme PBOC ; "
                   "lots : du premier au dernier jour de cloture",
        regles=regles.REGLES, empreinte=regles.empreinte(),
        empreinte_preenregistrement=empreinte_texte(), compteur_avant=avant)
    apres = {"global": experiences.compteur_total(),
             "trading": experiences.compteur(famille="trading"),
             "invest": experiences.compteur(famille="invest")}
    log.info("%s journalisee (diagnostic) — regles %s, texte %s ; compteurs %s -> %s",
             regles.ID_EXP, entree["empreinte"], entree["empreinte_preenregistrement"],
             avant, apres)
    if apres != avant:
        log.error("le compteur a bouge : ce n'est pas un diagnostic")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
