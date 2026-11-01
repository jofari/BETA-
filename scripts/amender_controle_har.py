"""Amendement du Controle HAR (01/11/2026) : clotures journalieres tirees des bougies 5 min.

    /root/venvs/beta/bin/python scripts/amender_controle_har.py

Decide par Jonas le 2026-11-01, AVANT tout calcul : la premiere campagne (code e7c6906) s'est
arretee a la lecture des donnees, parce que deux bougies 1d des perpetuels ont ete saisies avant la
fin du jour (BTC le 24/09/2019, ETH le 11/12/2019) alors que leurs 288 barres 5 min sont completes.
La cloture du jour D devient celle de la barre 5 min de 23:55 ; les copies 1d ne servent plus qu'au
controle. Aucune RV, aucun HAR, aucune QLIKE n'a ete calcule. `experiences.amender` garde la
ligne d'origine dans le registre et refuse d'amender une experience deja mesuree.
Idempotent : relancer ne reecrit rien.
"""

from __future__ import annotations

import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta.controle_har import regles  # noqa: E402
from beta.controle_har.campagne import empreinte_texte  # noqa: E402
from beta.protocole import experiences  # noqa: E402

log = logging.getLogger("beta.amender_controle_har")

RAISON = ("01/11/2026, avant tout calcul, decision de Jonas : la premiere campagne (e7c6906) "
          "s'est arretee a la lecture, deux bougies 1d saisies avant la fin du jour (BTC "
          "24/09/2019, ETH 11/12/2019) alors que les 288 barres 5 min sont completes ; cloture "
          "du jour = barre 5 min de 23:55, copies 1d en controle seulement. Aucune RV, aucun HAR, "
          "aucune QLIKE calcules.")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    entree = experiences.exiger(regles.ID_EXP)
    if entree.get("empreinte") == regles.empreinte():
        log.info("%s deja amendee : rien a faire", regles.ID_EXP)
        return 0
    avant = {"global": experiences.compteur_total(),
             "invest": experiences.compteur(famille="invest")}
    experiences.amender(regles.ID_EXP, RAISON, regles=regles.REGLES,
                        empreinte=regles.empreinte(),
                        empreinte_preenregistrement=empreinte_texte(),
                        decide_par="Jonas, 2026-11-01 : « Clotures des 5 min »")
    apres = {"global": experiences.compteur_total(),
             "invest": experiences.compteur(famille="invest")}
    log.info("%s amendee — regles %s, texte %s ; compteur global %d -> %d, invest %d -> %d",
             regles.ID_EXP, regles.empreinte(), empreinte_texte(), avant["global"],
             apres["global"], avant["invest"], apres["invest"])
    if apres != avant:
        log.error("le compteur a bouge : ce n'est pas un test de mesure sans essai")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
