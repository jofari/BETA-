"""Preenregistrement de T1C — complement ETH et SOL du Temps 1, DIAGNOSTIC (aucun essai).

    /root/venvs/beta/bin/python scripts/preenregistrer_t1c.py

Etape C du prompt de Jonas du 2026-11-01 (« On lance le backtest V1 de VC6 »), figee mot pour mot
avec ses applications dans VC6_V1/temps1_complement_eth_sol/PREENREGISTREMENT.md. Journalise T1C
dans EXPERIMENTS.jsonl avec `diagnostic=True`, famille invest : le compteur ne bouge pas.
Idempotent.
"""

from __future__ import annotations

import hashlib
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta import config  # noqa: E402
from beta.protocole import experiences  # noqa: E402
from beta.temps1_complement import regles  # noqa: E402

log = logging.getLogger("beta.preenregistrer_t1c")

TEXTE = config.RACINE / "VC6_V1" / "temps1_complement_eth_sol" / "PREENREGISTREMENT.md"


def empreinte_texte() -> str:
    return hashlib.sha256(TEXTE.read_bytes()).hexdigest()[:16]


HYPOTHESE = ("La SMA 200 d'ETH (puis de SOL), calculee sur ses propres clotures journalieres "
             "depuis le debut disponible, classe les jours bear et bull du juge de T1J mieux "
             "qu'un signal aleatoire de meme agitation (memes durees, permutees entre episodes "
             "du meme etat), sur la periode mesuree de l'actif.")

METRIQUE = ("p_justesse du test 1 de T1F (part des 1 000 tirages de justesse >= observee), par "
            "actif ; rapportes : p_latence, test 1 bis (decalage circulaire), test 2, mesures "
            "observees de T1J.")

DEJA_CONNU = (
    "Rapports de T1J et de T1F (24/10) : SMA 200 du BTC p_justesse 0,007 (test 1), 0,048 (test "
    "1 bis) ; sur les quatre actifs de T1J et le temoin, SMA 200 au test 1 : p_justesse de 0,000 "
    "a 0,007, p_latence de 0,708 a 0,986. Inventaire de l'etape A (01/11) : ETH et SOL lus en "
    "entier (debut, fin, trous, hash), jusqu'a la cloture du 31/10/2026. Aucun juge, aucune SMA "
    "et aucun tirage calcule sur ETH ou SOL.")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    if regles.ID_EXP in experiences.etat():
        log.info("%s deja journalisee : rien a ecrire", regles.ID_EXP)
        return 0
    avant = {"global": experiences.compteur_total(),
             "invest": experiences.compteur(famille="invest")}
    entree = experiences.preenregistrer(
        regles.ID_EXP, HYPOTHESE, METRIQUE, regles.REGLES["decision"],
        split_autorise="historique complet d'ETH et de SOL (perpetuels Binance, copies figees de "
                       "l'etape A) jusqu'au 31/10/2026 ; periode mesuree du juge",
        issue_attendue="non renseignee : le verdict est mecanique (Jonas 24/10)",
        deja_connu=DEJA_CONNU, famille_compteur="invest", diagnostic=True,
        decide_par="Jonas, 2026-11-01 : prompt « On lance le backtest V1 de VC6 », etape C",
        diagnostic_de=f"{regles.ID_JUSTESSE}, {regles.ID_FIABILITE}", regles=regles.REGLES,
        empreinte=regles.empreinte(), empreinte_preenregistrement=empreinte_texte(),
        compteur_avant=avant)
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
