"""Preenregistrement du « Temps 2 » de VC6 V1 (GO phase 3 de Jonas, 02/11/2026).

    /root/venvs/beta/bin/python scripts/preenregistrer_vc6_temps2.py

Fige `beta.vc6.regles.REGLES` (empreinte) et VC6_V1/temps2/PREENREGISTREMENT.md (empreinte), puis
journalise les 5 essais (4 variantes + le test annexe) AVANT tout calcul : le compteur invest
passe de 54 a 59. Idempotent : une seconde execution n'ecrit rien.
"""

from __future__ import annotations

import hashlib
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta import config  # noqa: E402
from beta.protocole import experiences  # noqa: E402
from beta.vc6 import regles as R  # noqa: E402

log = logging.getLogger("beta.preenregistrer_vc6_temps2")
TEXTE = config.RACINE / "VC6_V1" / "temps2" / "PREENREGISTREMENT.md"


def empreinte_texte() -> str:
    return hashlib.sha256(TEXTE.read_bytes()).hexdigest()[:16]


def run_id(cle: str) -> str:
    return hashlib.sha256(f"{R.ID_EXP}:{cle}:{R.empreinte()}".encode()).hexdigest()[:12]


HYPOTHESE = (
    "VC6 V1 (spec figee du 01/11/2026 et addendums) : sur BTC, ETH, SOL (50/25/25), le regime "
    "SMA 200 du BTC avec poche baissiere et sizing par la volatilite (HAR) reduit l'Ulcer par "
    "rapport a une exposition constante de meme moyenne, mieux que le hasard (nulls D4).")
METRIQUE = "Ulcer Index sur la periode principale 01/06/2021 -> 31/10/2026"
REGLE = {
    "1": "utile = Ulcer < temoin expo constante, p retenue (nulls circulaire et segments) < 0,05",
    "2": "Variante expo vol retenue si utile et ratio rendement annualise / Ulcer > celui de "
         "Variante expo fixe",
    "3": "poche or ou mixte remplace la poche BTC si Ulcer plus bas et rendement annualise >= "
         "celui de la meilleure variante a poche BTC - 2 points",
    "4": "si aucune variante de sizing n'est utile : exposition constante x HAR",
    "pbo": "calculee et rapportee (S10, 16 blocs, seuil 20 %) a titre d'information ; les "
           "regles 1 a 4 decident seules (addendum du 02/11/2026)",
}
DEJA_CONNU = (
    "Prix crypto 2019-2026 et grandes baisses publiques du BTC ; resultats des phases 1 et 2 "
    "(ETH et SOL non retenus ; sigma = HAR pour les trois). Vu le 02/11 avant tout run, en "
    "verifiant la couverture : sigma HAR annualise >= 36 % (BTC), 51 % (ETH), 74 % (SOL) sur la "
    "periode principale, donc aucun levier possible a la cible de 25 % ; seul le test annexe "
    "(40 %) peut en creer. Aucun chiffre de variante, de temoin ni de reference calcule.")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    if R.ID_EXP in experiences.etat():
        log.info("%s deja preenregistree : rien a ecrire", R.ID_EXP)
        return 0
    invest_avant = experiences.compteur(famille="invest")
    global_avant = experiences.compteur_total()
    essais = [k for k, v in R.VARIANTES.items() if v["essai"]]
    experiences.preenregistrer(
        R.ID_EXP, HYPOTHESE, METRIQUE, REGLE,
        split_autorise="periode principale 01/06/2021 -> 31/10/2026 (deja vue : diagnostic, "
                       "peut eliminer, pas valider) ; robustesse BTC seul 2014 -> 31/10/2026",
        issue_attendue="non renseignee : verdict mecanique, rien ne vient de Claude",
        famille_taille=len(essais), deja_connu=DEJA_CONNU, famille_compteur="invest",
        n_configurations=4,
        decide_par="Jonas, 01-02/11/2026 : spec VC6 V1, addendums, GO phase 3 « Temps 2 »",
        compteur={"invest_avant": invest_avant, "global_avant": global_avant,
                  "regle": "+1 par essai : 4 variantes + le test annexe, journalises avant le "
                           "premier calcul",
                  "invest_attendu_apres": invest_avant + len(essais),
                  "global_attendu_apres": global_avant + len(essais)},
        regles=R.REGLES, empreinte=R.empreinte(), empreinte_preenregistrement=empreinte_texte())
    for cle in essais:
        experiences.enregistrer_run(run_id(cle), R.ID_EXP, f"vc6_temps2:{cle}", R.empreinte(),
                                    issue="essai journalise avant calcul")
    log.info("%s preenregistree — regles %s, texte %s ; invest %d -> %d, global %d -> %d",
             R.ID_EXP, R.empreinte(), empreinte_texte(), invest_avant,
             experiences.compteur(famille="invest"), global_avant,
             experiences.compteur_total())
    return 0


if __name__ == "__main__":
    sys.exit(main())
