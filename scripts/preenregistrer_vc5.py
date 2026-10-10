"""Preenregistrement de VC5 — VC3 avec une cible de volatilite de 35 % au lieu de 20 %.

    ARIT_HOME=/root/ARIT2.0 /root/venvs/arit/bin/python scripts/preenregistrer_vc5.py

Decide par Jonas le 2026-10-10 (~23:15 UTC), en lisant le dashboard Forward : en regime
haussier, VC3 n'investit que ~69 % du capital, parce que sa cible de vol (20 %) est bien sous
la vol du portefeuille crypto (35,5 % sur 30 j ce jour-la). Il veut etre davantage investi en
haussier et accepte une perte maximale plus profonde : cible 35 % (~100 % investi a la vol du
jour), budget de perte -40 % (au lieu de -25 %). Un seul changement ; tout le reste est la
config VC3 du registre, a l'identique (votes, seuils, moteur, poche maximum, spot, plafond
d'exposition 1, frais). VC4 (decisions a chaque ouverture de session) est une experience
SEPAREE, decidee le meme jour : chacune ne change qu'une chose par rapport a VC3.

Compteur 70 -> 71, puis +10 avec les voisins de R1 a la mesure (arbitrage A1), comme VC3.
Idempotent : relancer ne reecrit rien.
"""

from __future__ import annotations

import copy
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta.protocole import experiences  # noqa: E402
from beta.strategies import voie_c2 as c2  # noqa: E402

log = logging.getLogger("beta.preenregistrer_vc5")

ID_EXP = "VC5"
CIBLE = 0.35
MAXDD_BUDGET = -0.40


def config_vc5() -> dict:
    """La config VC3 RELUE dans le registre (empreinte verifiee), cible de vol 35 %."""
    cfg = copy.deepcopy(c2.config("VC3"))
    cfg["version"] = ID_EXP
    cfg["haussier"]["cible"] = CIBLE
    return cfg


FENETRE_BACKTEST = ["2021-06-12", "2026-09-05"]

METRIQUE = ("Sharpe net (racine de 252) et maxDD net de la serie quotidienne du 2021-06-12 au "
            "2026-09-05, memes frais et memes prix que VC3 (spot : taker 10 pb + slippage "
            "5/10 pb par cote, aucun funding ; clotures des perpetuels du lake, proxy du spot)")

REGLE = {
    "confirmee": "admise au forward : maxDD net >= -40 % ET Sharpe net > Sharpe du hold BTC "
                 "SPOT (meme fenetre, memes clotures) ET epreuve de causalite passee ET "
                 "reglages non fragiles (R1 : la mediane des 10 voisins passe aussi la porte)",
    "infirmee": "maxDD net < -40 % OU Sharpe net <= Sharpe du hold BTC spot OU causalite en "
                "echec OU fragilite (R1)",
    "indecidable": "donnees manquantes sur la fenetre (lake ou series macro)",
    "forward": "dry-run de 6 mois a partir du 2026-10-11 : maxDD >= -40 %, vol realisee "
               "(racine de 252) entre 17,5 % et 52,5 % (0,5x a 1,5x la cible, la regle de VC3 "
               "rapportee a 35 %), et des que l'execution existe : slippage reel <= 2x le "
               "modele, zero incident critique. Comparaisons a VC3, au hold BTC spot et au "
               "hold equipondere : informatives. Chaque passage d'etape est une decision "
               "manuelle de Jonas.",
}

DEJA_CONNU = (
    "VC3 (meme config, cible 20 %) mesuree le 07/10 sur cette fenetre, CONFIRMEE de justesse : "
    "Sharpe 0,80 (hold BTC spot 0,45), CAGR 22,1 %, vol 19,7 %, maxDD -23,2 % (08/11/2021 -> "
    "14/06/2023), brut median ~0,6 en haussier ; alertes R3 (P(maxDD < -25 %) = 66-68 %) et R4 "
    "(2024 = 50 % du gain). Estimation grossiere faite le 07/10 AVANT VC3, sur la seule baisse "
    "2022 : cible 30 % ~ -35 %. Extrapolation lineaire donnee a Jonas le 10/10 avant son choix : "
    "cible 35 % ~ -40 %, tres incertaine (le plafond d'exposition a 1 en spot l'ecrete). Le "
    "choix de 35 % et du budget -40 % a ete fait APRES avoir vu VC3 et son forward : la fenetre "
    "est vue et revue (voie C, VC2, VC2T, VC3) ; ce backtest peut eliminer VC5, il ne la valide "
    "pas. Le 10/10, VC3 tenait 68,6 % investi (voulu 74,1 %, levier calcule 0,56, tenu 0,74 par "
    "hysteresis) en regime haussier de justesse (somme des votes +2).")

# Les memes 10 voisins de calendrier que VC3 (preenregistrement du 07/10), appliques a VC5.
VOISINS = {
    "vote_momentum.fenetre": [90, 180],
    "haussier.fenetre_mom": [90, 180],
    "baissier.fenetre_mom_alts": [90, 180],
    "haussier.fenetre": [20, 45],
    "haussier.bande": [0.10, 0.30],
}

SURAPPRENTISSAGE = {
    "R1_plateau": {
        "role": "PORTE : peut infirmer VC5",
        "voisins": VOISINS,
        "regle": "VC5 infirmee pour fragilite si la MEDIANE des 10 voisins echoue a la porte : "
                 "mediane des maxDD nets < -40 % OU mediane des Sharpe nets <= Sharpe du hold "
                 "BTC spot. Un voisin meilleur que VC5 ne devient JAMAIS candidat.",
    },
    "R2_sharpe_degonfle": {
        "role": "informatif",
        "methode": "S2 sur r_net de VC5 : pleine fenetre, TRAIN, OOS ; N = compteur du banc "
                   "apres la mesure, puis N + configs regardees pour la voie C",
    },
    "R3_cone_et_ecart_au_hold": {
        "role": "informatif, avec alerte",
        "methode": "bootstrap par blocs stationnaire, l = 5, 20, 50 j, 2 000 rejeux, graine 0 : "
                   "distribution du maxDD (mediane, 5e centile, P(maxDD < -40 %)) et IC 95 % de "
                   "Sharpe(VC5) - Sharpe(hold BTC spot) en tirage apparie",
        "alerte": "P(maxDD < -40 %) > 50 % pour l = 20 j",
    },
    "R4_stabilite": {
        "role": "informatif, avec alerte",
        "methode": "Sharpe, CAGR et maxDD sur TRAIN (<= 2024-06-30), OOS et par annee civile",
        "alerte": "Sharpe OOS < 0, ou plus de la moitie du gain total venue d'une seule annee",
    },
    "comparaison_vc3": {
        "role": "informatif",
        "methode": "Sharpe, CAGR, maxDD et exposition moyenne en haussier de VC5 contre VC3 sur "
                   "la meme fenetre : ce que la cible plus haute rapporte et ce qu'elle coute",
    },
}

HYPOTHESE = (
    "VC3 avec une cible de volatilite de 35 % au lieu de 20 % (donc davantage investie en "
    "regime haussier, toujours plafonnee a 100 % en spot) tient un budget de perte de -40 % "
    "et bat le hold BTC spot en Sharpe net.")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    deja = experiences.etat()
    if ID_EXP in deja:
        log.info("%s deja preenregistree (empreinte %s) : rien a ecrire",
                 ID_EXP, deja[ID_EXP].get("empreinte"))
        return 0
    cfg = config_vc5()
    entree = experiences.preenregistrer(
        ID_EXP, HYPOTHESE, METRIQUE, REGLE,
        split_autorise="fenetre deja vue par la voie C, VC2, VC2T et VC3 "
                       "(2021-06-12 -> 2026-09-05)",
        issue_attendue="confirmee", famille_taille=1, deja_connu=DEJA_CONNU,
        fenetre_backtest=FENETRE_BACKTEST, debut_rattrapage="2026-09-06",
        debut_live="2026-10-11",
        decide_par="Jonas, 2026-10-10 ~23:15 UTC : cible 35 %, budget -40 %, variante separee "
                   "de VC4 (questionnaire, avant toute mesure)",
        derive_de="VC3 (config du registre, empreinte 7adef08a837a8c50)",
        surapprentissage=SURAPPRENTISSAGE,
        surapprentissage_demande_par="meme batterie que VC3 (Jonas, 2026-10-07 13:13 UTC)",
        config=cfg, empreinte=c2.empreinte(cfg))
    log.info("%s preenregistree — empreinte %s, essai cumule n° %s",
             ID_EXP, entree["empreinte"], entree["n_essais_cumules"])
    log.info("compteur courant : %d", experiences.compteur())
    return 0


if __name__ == "__main__":
    sys.exit(main())
