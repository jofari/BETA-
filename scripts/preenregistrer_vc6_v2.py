"""Preenregistrement de VC6 V2 (prompt de Jonas du 02/11/2026).

    /root/venvs/beta/bin/python scripts/preenregistrer_vc6_v2.py

Fige `beta.vc6_v2.regles.REGLES`, VC6_V2/PREENREGISTREMENT.md et VC6_V2/spec_figee.md (empreintes),
puis journalise les 2 essais AVANT tout calcul sur les vraies donnees : le compteur invest passe de
59 a 61 (spec). Le test de coherence c calcule deja le Sharpe et l'Ulcer de « V2 – HAR sans
regime » : d'ou le preenregistrement avant les tests (invariant 4). Idempotent : une seconde
execution n'ecrit rien.
"""

from __future__ import annotations

import hashlib
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta.protocole import experiences  # noqa: E402
from beta.vc6_v2 import gel  # noqa: E402
from beta.vc6_v2 import regles as R  # noqa: E402

log = logging.getLogger("beta.preenregistrer_vc6_v2")
INVEST_AVANT_ATTENDU = 59


def run_id(cle: str) -> str:
    return hashlib.sha256(f"{R.ID_EXP}:{cle}:{R.empreinte()}".encode()).hexdigest()[:12]


HYPOTHESE = (
    "VC6 V2 (spec figee du 02/11/2026). Essai 1, V2 - HAR sans regime : BTC, ETH, SOL (50/25/25) "
    "investis en permanence avec Ei = clip(0,25 / sigma HAR ; 0,2 ; 2) ont un Ulcer plus bas que "
    "l'exposition constante de meme moyenne, mieux que les memes positions decalees dans le temps "
    "(nulls des positions). Essai 2, V2 - poche baissiere sous HAR : la Variante expo vol de la V1 "
    "avec une poche baissiere de 25 % x E_BTC (clip(0,25 / sigma BTC ; 0,2 ; 1)) a un Ulcer plus "
    "bas que son temoin, mieux que le hasard (nulls du mode).")
METRIQUE = "Ulcer Index sur la periode principale 01/06/2021 -> 31/10/2026"
REGLE = {
    "1": "utile = Ulcer < celui de son temoin expo constante, avec p retenue < 0,05 (D4)",
    "2": "un seul essai utile -> cet essai ; les deux -> le plus haut ratio rendement annualise / "
         "Ulcer ; aucun -> VC6 rejetee, aucune configuration retenue, le paper ne sert qu'a roder "
         "l'execution",
    "3": "rapporte sans effet : V2 - poche baissiere sous HAR contre la Variante expo vol de la V1 "
         "(Ulcer, drawdown max, rendement annualise, contribution de la poche baissiere pendant le "
         "drawdown max)",
    "pbo": "PBO du choix entre les deux essais (S10, CSCV 16 blocs, Sharpe, seuil 20 %) calculee "
           "et rapportee a titre d'information (addendum de la V1 du 02/11/2026, repris par la "
           "spec) ; les regles 1 et 2 decident seules",
    "verdict": "pour info : Sharpe > 1 ; drawdown max < 25 % ; bat le panier et l'ETF monde a "
               "risque egal",
}
DEJA_CONNU = (
    "Tout le Temps 2 de la V1 et son correctif du 02/11 (Variante expo vol : Ulcer 13,90 % contre "
    "17,58 % pour le temoin, p retenue 0,250, Ulcer nul median 15,50 % / 15,13 %, drawdown max "
    "-28,1 % dont -20,7 points pour la poche baissiere BTC). Panier 50/25/25 reequilibre : "
    "2,470541. Sigma HAR annualise sur la periode principale : BTC 36-132 %, ETH 51-206 %, SOL "
    "74-590 %, donc aucun levier possible dans les deux essais sur la periode principale. Aucun "
    "chiffre des deux essais calcule sur les vraies donnees ; moteur V2 eprouve sur donnees "
    "synthetiques seulement.")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    if R.ID_EXP in experiences.etat():
        log.info("%s deja preenregistree : rien a ecrire", R.ID_EXP)
        gel.verifier()
        return 0
    invest_avant = experiences.compteur(famille="invest")
    global_avant = experiences.compteur_total()
    if invest_avant != INVEST_AVANT_ATTENDU:
        raise SystemExit(f"compteur invest a {invest_avant}, la spec part de "
                         f"{INVEST_AVANT_ATTENDU} : arret")
    essais = list(R.ESSAIS)
    experiences.preenregistrer(
        R.ID_EXP, HYPOTHESE, METRIQUE, REGLE,
        split_autorise="periode principale 01/06/2021 -> 31/10/2026 (deja vue : diagnostic, "
                       "peut eliminer, pas valider) ; robustesse BTC seul 2014 -> 31/10/2026 "
                       "(information)",
        issue_attendue="non renseignee : verdict mecanique, rien ne vient de Claude",
        famille_taille=len(essais), deja_connu=DEJA_CONNU, famille_compteur="invest",
        n_configurations=len(essais),
        decide_par="Jonas, 02/11/2026 : spec VC6 V2 (prompt « On prepare la V2 »)",
        compteur={"invest_avant": invest_avant, "global_avant": global_avant,
                  "regle": "+1 par essai : les 2 essais de la V2, journalises avant le premier "
                           "calcul sur les vraies donnees (test de coherence c compris)",
                  "invest_attendu_apres": invest_avant + len(essais),
                  "global_attendu_apres": global_avant + len(essais)},
        regles=R.REGLES, empreinte=R.empreinte(),
        empreinte_preenregistrement=gel.empreinte_fichier(gel.TEXTE),
        empreinte_spec=gel.empreinte_fichier(gel.SPEC))
    for cle in essais:
        experiences.enregistrer_run(run_id(cle), R.ID_EXP, f"vc6_v2:{cle}", R.empreinte(),
                                    issue="essai journalise avant calcul")
    gel.verifier()
    log.info("%s preenregistree — regles %s ; invest %d -> %d, global %d -> %d", R.ID_EXP,
             R.empreinte(), invest_avant, experiences.compteur(famille="invest"), global_avant,
             experiences.compteur_total())
    return 0


if __name__ == "__main__":
    sys.exit(main())
