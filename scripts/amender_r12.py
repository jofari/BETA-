"""Amendement de R12 (13/10) : le spread de detention passe au modele « tick » du moteur.

    /root/venvs/arit/bin/python scripts/amender_r12.py

Decide par Jonas le 2026-10-13, apres l'audit du code de BETA, AVANT toute mesure de R12 (il
a demande de ne pas la mesurer pour le moment) : l'estimateur de Corwin & Schultz, que le
preenregistrement du 12/10 reprenait « comme tout Run », suivait la volatilite et non le
spread — ~0,13 R par trade en 1h sur les six paires (2021-2024), pour un spread reel de
0,01 (BTC) a 0,93 pb (SOL) mesure le 13/10 sur le carnet Binance. Le moteur paie desormais
un tick rapporte au prix, le tick etant lu dans les prix du lake (`espace_r.pas_de_cotation`).

Seule la ligne `regles.couts.detention` change. Aucune donnee de R12 n'a ete regardee : ni
distribution de l'OI, ni rendement horaire, ni trade. `experiences.amender` garde la ligne
d'origine dans le registre et refuse d'amender une experience deja mesuree.
Idempotent : relancer ne reecrit rien.
"""

from __future__ import annotations

import copy
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta.protocole import experiences  # noqa: E402

log = logging.getLogger("beta.amender_r12")

ID_EXP = "R12"
DETENTION = ("spread = 1 tick / prix (modele 'tick' du moteur depuis le 13/10 : tick lu dans "
             "les prix du lake, ~0,01 a 1 pb sur les six paires) et funding reel du lake, "
             "comme tout Run")
RAISON = ("audit du 13/10 : l'estimateur de Corwin & Schultz mesurait la volatilite, pas le "
          "spread (~0,13 R par trade en 1h sur les six paires, pour 0,01 a 0,93 pb reels au "
          "carnet Binance) ; le moteur paie desormais 1 tick / prix. Aucune donnee de R12 "
          "regardee.")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    entree = experiences.exiger(ID_EXP)
    if entree["regles"]["couts"]["detention"] == DETENTION:
        log.info("%s deja amendee : rien a faire", ID_EXP)
        return 0
    regles = copy.deepcopy(entree["regles"])
    regles["couts"]["detention"] = DETENTION
    experiences.amender(ID_EXP, RAISON, regles=regles)
    log.info("%s amendee (statut %s, compteur inchange : %d)", ID_EXP,
             experiences.etat()[ID_EXP]["statut"], experiences.compteur())
    return 0


if __name__ == "__main__":
    sys.exit(main())
