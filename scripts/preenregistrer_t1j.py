"""Preenregistrement de T1J — Temps 1, test de JUSTESSE des detecteurs de regime.

    /root/venvs/beta/bin/python scripts/preenregistrer_t1j.py

Prompt de Jonas du 2026-10-24, decouverte temps1_justesse/DISCOVERY.md (7be0fe1) rendue AVANT
tout code du test, reponses de Jonas du meme jour (9 questions, ambiguites A a F, 3 precisions).
Fige `beta.temps1_justesse.regles.REGLES` (empreinte) et la section « Clarifications avant
calcul » de temps1_justesse/RAPPORT_JUSTESSE.md (empreinte) : la campagne refuse de tourner si
l'une ou l'autre a change.

Compteur invest : 38 avant ; +1 ici (hypothese sans mesure), puis les 16 essais du verdict
journalises avant le premier calcul remplacent ce +1 : 54 attendu apres (global 131 -> 147).
Idempotent : une seconde execution n'ecrit rien.
"""

from __future__ import annotations

import hashlib
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta import config  # noqa: E402
from beta.protocole import experiences  # noqa: E402
from beta.temps1_justesse import regles  # noqa: E402

log = logging.getLogger("beta.preenregistrer_t1j")

RAPPORT = config.RACINE / "temps1_justesse" / "RAPPORT_JUSTESSE.md"
MARQUEUR = "<!-- FIN DES CLARIFICATIONS"


def clarifications() -> str:
    """La section figee en tete du rapport : tout ce qui precede le marqueur."""
    texte = RAPPORT.read_text(encoding="utf-8")
    if MARQUEUR not in texte:
        raise SystemExit(f"{RAPPORT} : marqueur de fin des clarifications absent")
    return texte.split(MARQUEUR, 1)[0]


def empreinte_clarifications() -> str:
    return hashlib.sha256(clarifications().encode("utf-8")).hexdigest()[:16]


HYPOTHESE = (
    "Sur le S&P 500, le Nasdaq-100 et l'or (labo 1991-2023), puis sur le BTC (etape B), un "
    "detecteur de regime (MOM126, C1_V1 ou C1_V2) reconnait les bears dates apres coup par le juge "
    "plus tot que la SMA 200 sans plus de fausses alertes : il n'est domine par SMA200 (mediane de "
    "f_entree, fausses alertes par an) ni sur le temoin actions ni sur l'or, a une f_entree plus "
    "faible que SMA200 sur la majorite des episodes de chacun des deux, et n'est pas domine par "
    "SMA200 sur le BTC.")

METRIQUE = (
    "Mediane de f_entree (rates = 1) et fausses alertes par an, par detecteur x actif, sur la "
    "periode mesuree du juge ; rapportes sans entrer dans le verdict : pire cas et rates de "
    "f_entree, f_sortie, retards, bascules par an, justesse equilibree, episodes neutres contre "
    "hasard, bande SMA, variantes de fenetre de C1_V1, variantes du juge, periode 2024 -> fin.")

DEJA_CONNU = (
    "Aucun chiffre de ce test n'a ete calcule : ni detecteur, ni juge, ni mesure. La decouverte du "
    "24/10 n'a lu que la couverture des series (dates, nombres d'observations, trous) et compare "
    "Bitstamp a Coinbase (ecart de cloture median 0,03 %). Connu de Claude avant le gel : le "
    "verdict de T1A (21/10, test d'UTILITE par l'Ulcer, autre mesure, rapport non relu ici) tel "
    "que note dans sa memoire de session — aucun timing demontre ; SMA200 passe la porte du temoin "
    "mais pas celle du hasard sur SPX et NDX ; MOM126 franchit ses 3 portes sur SPX seulement ; "
    "COUCHE1 (proche de C1_V2) echoue partout, VIX > 25 sur 17,8 % des seances, 503 changements. "
    "Connu de tous : les grandes baisses publiques des actions (2000-2002, 2007-2009, 2020, 2022), "
    "de l'or et du BTC (2014, 2018, 2022) ; la SMA 200 (Faber 2007) et le momentum de series "
    "temporelles (Moskowitz, Ooi, Pedersen 2012) ont ete popularises sur ces memes historiques. "
    "Le labo n'est hors echantillon pour personne : il peut eliminer un detecteur, pas en sacrer "
    "un. C1_V1 et C1_V2 viennent du prompt de Jonas ; leur origine n'est pas documentee ici.")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    deja = experiences.etat()
    if regles.ID_EXP in deja:
        log.info("%s deja preenregistree (empreinte %s) : rien a ecrire",
                 regles.ID_EXP, deja[regles.ID_EXP].get("empreinte"))
        return 0
    invest_avant = experiences.compteur(famille="invest")
    global_avant = experiences.compteur_total()
    entree = experiences.preenregistrer(
        regles.ID_EXP, HYPOTHESE, METRIQUE, regles.REGLES["verdict"],
        split_autorise="labo 1991-01-01 -> 2023-12-31 (decide, SPX, NDX, or) ; BTC sur tout son "
                       "historique juge (etape B : peut eliminer, jamais valider seul) ; 2024-01-01"
                       " -> fin (deja vu, ne decide rien) ; aucun parametre optimise",
        issue_attendue="non renseignee : le verdict est mecanique et rien ne vient de Claude "
                       "(Jonas 24/10)",
        famille_taille=16, deja_connu=DEJA_CONNU, famille_compteur="invest",
        decide_par="Jonas, 2026-10-24 : prompt « BETA / Temps 1 : test de JUSTESSE des "
                   "detecteurs de regime » ; BTC dans DS1 ; famille invest ; reponses A-F ; "
                   "16 essais du verdict, 18 informatifs ; fenetre de V, « solide », f_sortie",
        detecteurs={"verdict": list(regles.VERDICT), "bande": list(regles.BANDE),
                    "variantes_c1": list(regles.VARIANTES_C1)},
        actifs=regles.ACTIFS,
        compteur={"gel_global_22_10": 117, "global_avant": global_avant,
                  "invest_avant": invest_avant,
                  "regle": "+1 par couple du verdict (4 detecteurs x 3 actifs labo + 4 x BTC = "
                           "16), journalises avant le premier calcul ; 18 informatifs a part",
                  "invest_attendu_apres": invest_avant + 16,
                  "global_attendu_apres": global_avant + 16},
        regles=regles.REGLES, empreinte=regles.empreinte(),
        empreinte_clarifications=empreinte_clarifications())
    log.info("%s preenregistree — regles %s, clarifications %s ; invest %d -> %d, global %d -> %d"
             " (hypothese sans mesure)", regles.ID_EXP, entree["empreinte"],
             entree["empreinte_clarifications"], invest_avant,
             experiences.compteur(famille="invest"), global_avant, experiences.compteur_total())
    return 0


if __name__ == "__main__":
    sys.exit(main())
