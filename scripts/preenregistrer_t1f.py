"""Preenregistrement de T1F — fiabilite du test de justesse, DIAGNOSTIC (aucun essai).

    /root/venvs/beta/bin/python scripts/preenregistrer_t1f.py

Prompt de Jonas du 2026-10-24 (« BETA / Temps 1 – fiabilite du test de justesse »), fige mot pour
mot avec ses clarifications dans temps1_fiabilite/PREENREGISTREMENT.md. Journalise T1F dans
EXPERIMENTS.jsonl avec `diagnostic=True`, famille invest : le compteur ne bouge pas. Idempotent.
"""

from __future__ import annotations

import hashlib
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta import config  # noqa: E402
from beta.protocole import experiences  # noqa: E402
from beta.temps1_fiabilite import regles  # noqa: E402

log = logging.getLogger("beta.preenregistrer_t1f")

TEXTE = config.RACINE / "temps1_fiabilite" / "PREENREGISTREMENT.md"


def empreinte_texte() -> str:
    return hashlib.sha256(TEXTE.read_bytes()).hexdigest()[:16]


HYPOTHESE = ("C1_V1 et C1_V2 detectent les bears du juge de T1J plus tot (mediane de f_entree) "
             "qu'un detecteur aleatoire de meme agitation : le meme signal dont les durees sont "
             "melangees entre episodes du meme etat, sur la periode mesuree de T1J.")

METRIQUE = ("p_latence (part des 1 000 tirages de mediane f_entree <= observee) sur le temoin "
            "actions et sur l'or ; rapportes : p_justesse, fausses alertes par an, test 1 bis "
            "(decalage circulaire), BTC, diagnostic des f = 0.")

DEJA_CONNU = (
    "Le rapport de T1J (24/10, 13:21 UTC) : verdict « candidat retenu : C1_V2 ; retenus : C1_V1, "
    "C1_V2 », non solide ; medianes de f_entree temoin 0,13 (C1_V1), 0,15 (C1_V2) contre 0,36 "
    "(SMA200) ; or 0,14 et 0,05 contre 0,66 ; bascules par an temoin 23,9 et 15,2 contre 7,8. "
    "Aucun tirage aleatoire n'a ete calcule. Le test est concu APRES avoir vu ce verdict, pour "
    "le mettre a l'epreuve : il peut le fragiliser, pas le renforcer.")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    if regles.ID_EXP in experiences.etat():
        log.info("%s deja journalisee : rien a ecrire", regles.ID_EXP)
        return 0
    avant = {"global": experiences.compteur_total(),
             "invest": experiences.compteur(famille="invest")}
    entree = experiences.preenregistrer(
        regles.ID_EXP, HYPOTHESE, METRIQUE, regles.REGLES["verdict"],
        split_autorise="periodes mesurees de T1J (labo 1991-2023 pour SPX, NDX, or ; BTC sur son "
                       "historique juge) ; aucune donnee nouvelle",
        issue_attendue="non renseignee : le verdict est mecanique (Jonas 24/10)",
        deja_connu=DEJA_CONNU, famille_compteur="invest", diagnostic=True,
        decide_par="Jonas, 2026-10-24 : prompt « BETA / Temps 1 – fiabilite du test de "
                   "justesse » et 4 clarifications (permutation par etat, periode mesuree, "
                   "temoin tirage par tirage, decalage en seances)",
        diagnostic_de=regles.ID_JUSTESSE, regles=regles.REGLES, empreinte=regles.empreinte(),
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
