"""Ligne de diagnostic du « Paper de plomberie – VC6 V2 poche baissiere sous HAR » (02/11/2026).

    /root/venvs/beta/bin/python scripts/preenregistrer_vc6_paper.py

Decision C de Jonas : une ligne de DIAGNOSTIC au registre, sans essai, compteur inchange (invest
61). Le run n'est pas juge : il sert uniquement a verifier l'execution. La ligne porte l'empreinte
des regles de la V2 et celle des parametres du paper ; `scripts/vc6_paper.py` refuse de tourner si
l'une a change. Idempotent : une seconde execution n'ecrit rien.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from beta.protocole import experiences  # noqa: E402
from beta.vc6_v2 import paper as pp  # noqa: E402
from beta.vc6_v2 import regles as R  # noqa: E402

log = logging.getLogger("beta.preenregistrer_vc6_paper")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    if pp.ID in experiences.etat():
        log.info("%s deja au registre : rien a ecrire", pp.ID)
        pp.verifier_gel()
        return 0
    avant = {"invest": experiences.compteur(famille="invest"),
             "global": experiences.compteur_total()}
    experiences.preenregistrer(
        pp.ID,
        hypothese="Paper de plomberie de la V2 - poche baissiere sous HAR (regles de "
                  "VC6_V2/spec_figee.md sans modification) : verifier l'execution quotidienne "
                  "(decision a la cloture, ordres au comptant, journal, rejeu hebdomadaire). Run "
                  "NON juge.",
        metrique_primaire="aucune : run non juge (diagnostic d'execution)",
        regle_de_decision={"1": "aucune decision : le run sert uniquement a verifier "
                                "l'execution ; tout ecart d'exposition de plus de 5 points au "
                                "rejeu hebdomadaire est explique"},
        split_autorise="forward depuis le 02/11/2026 (paper, aucune donnee figee)",
        issue_attendue="aucune : diagnostic",
        deja_connu="VC6 V2 mesuree et rejetee le 02/11/2026 (aucune configuration retenue) ; "
                   "la poche baissiere sous HAR est la meilleure candidate, non prouvee",
        famille_compteur="invest", diagnostic=True,
        decide_par="Jonas, 02/11/2026 : decisions A (comptant), B (echanger seulement quand le "
                   "modele change une exposition), C (diagnostic), D (ouverture 1 min de 00:00 "
                   "+ 10 pb), signal fantome Garman-Klass",
        regles_v2=R.empreinte(), parametres_paper=pp.PAPER, empreinte_paper=pp.empreinte())
    apres = {"invest": experiences.compteur(famille="invest"),
             "global": experiences.compteur_total()}
    if apres != avant:
        log.error("le compteur a bouge (%s -> %s) : un diagnostic ne doit pas compter", avant,
                  apres)
        return 1
    pp.verifier_gel()
    log.info("%s au registre (diagnostic) ; compteurs inchanges : invest %d, global %d", pp.ID,
             apres["invest"], apres["global"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
