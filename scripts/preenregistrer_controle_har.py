"""Preenregistrement du Controle HAR (VC6 V1, phase 2) : test de mesure, AUCUN essai.

    /root/venvs/beta/bin/python scripts/preenregistrer_controle_har.py

Prompt de Jonas du 2026-11-01 (« GO phase 2 : Controle HAR »), fige mot pour mot avec ses
applications dans VC6_V1/controle_har/PREENREGISTREMENT.md. Journalise l'experience dans
EXPERIMENTS.jsonl avec `diagnostic=True`, famille invest : le compteur ne bouge pas. Idempotent.
"""

from __future__ import annotations

import hashlib
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta import config  # noqa: E402
from beta.controle_har import regles  # noqa: E402
from beta.protocole import experiences  # noqa: E402

log = logging.getLogger("beta.preenregistrer_controle_har")

TEXTE = config.RACINE / "VC6_V1" / "controle_har" / "PREENREGISTREMENT.md"


def empreinte_texte() -> str:
    return hashlib.sha256(TEXTE.read_bytes()).hexdigest()[:16]


HYPOTHESE = ("Pour chaque actif (BTC, ETH, SOL), la prevision HAR de la variance journaliere "
             "moyenne des 5 jours suivants (RV 5 min, MCO sur une fenetre glissante de 730 "
             "jours) a une QLIKE moyenne plus basse ou egale a celle de l'ecart-type 30 jours "
             "des rendements log journaliers, sur les jours ou le HAR a ses 730 jours de RV.")

METRIQUE = ("QLIKE moyenne de chaque prevision contre la moyenne des RV 5 min des 5 jours "
            "suivants, par actif ; rapportes : p de Diebold-Mariano (information), jours "
            "evalues, jours exclus, previsions <= 0 remplacees.")

DEJA_CONNU = (
    "Inventaire de l'etape A (01/11) : bougies 5 min et clotures lues en entier (debut, fin, "
    "barres manquantes, hash) ; aucune RV 5 min, aucun HAR, aucune QLIKE calcules sur ces "
    "copies. Recherche du 16/10, non preenregistree (beta/strategies/voie_c6_vol.py) : un HAR "
    "different (RV Garman-Klass de l'OHLC 1d, horizon 1 jour, fenetre 250 jours) contre R30 sur "
    "837 jours (mi-2024 a 10/2026), QLIKE contre la RV Garman-Klass : BTC HAR 0,608 / R30 "
    "0,614 ; ETH 0,684 / 0,637 ; SOL 0,604 / 0,546 ; contre r2, HAR moins bon que R30 sur les "
    "trois. Fiches des 14 et 19/10 : pronostic de litterature, non verifie, HAR-RV > ecart-type "
    "30 jours.")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    if regles.ID_EXP in experiences.etat():
        log.info("%s deja journalisee : rien a ecrire", regles.ID_EXP)
        return 0
    avant = {"global": experiences.compteur_total(),
             "invest": experiences.compteur(famille="invest")}
    entree = experiences.preenregistrer(
        regles.ID_EXP, HYPOTHESE, METRIQUE, regles.REGLES["decision"],
        split_autorise="historique complet des bougies 5 min et des clotures des perpetuels "
                       "BTC, ETH et SOL (copies figees de l'etape A) jusqu'au 31/10/2026 ; "
                       "evaluation sur les jours ou le HAR a ses 730 jours de RV",
        issue_attendue="non renseignee : la regle 5 est mecanique",
        deja_connu=DEJA_CONNU, famille_compteur="invest", diagnostic=True,
        decide_par="Jonas, 2026-11-01 : prompt « GO phase 2 : Controle HAR »",
        diagnostic_de="VC6 V1 (spec figee du 01/11/2026) : sigma de la poche investie",
        regles=regles.REGLES, empreinte=regles.empreinte(),
        empreinte_preenregistrement=empreinte_texte(), compteur_avant=avant)
    apres = {"global": experiences.compteur_total(),
             "invest": experiences.compteur(famille="invest")}
    log.info("%s journalisee (test de mesure, diagnostic) — regles %s, texte %s ; compteur "
             "global %d -> %d, invest %d -> %d", regles.ID_EXP, entree["empreinte"],
             entree["empreinte_preenregistrement"], avant["global"], apres["global"],
             avant["invest"], apres["invest"])
    if apres != avant:
        log.error("le compteur a bouge : ce n'est pas un test de mesure sans essai")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
