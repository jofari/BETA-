"""Preenregistrement de R12 — racheter le creux d'une cascade de liquidations (OI + prix).

    /root/venvs/arit/bin/python scripts/preenregistrer_r12.py

Decide par Jonas le 2026-10-12 (questionnaire, avant toute mesure) : premiere strategie de
trading ACTIF de BETA, horizon horaire ; sens = contrepartie des liquides (acheter apres une
cascade de longs, vendre apres une cascade de shorts) ; execution simulee = ordre limite puis
repli au marche. R7 (meche > 3x ATR en 4h) est le precedent : la difference est le
declencheur, qui exige une chute de l'open interest (desendettement force), pas une meche.

Tous les nombres ci-dessous sont fixes AVANT la mesure et justifies dans JUSTIFICATIONS.
Aucune distribution de l'OI ni du rendement horaire n'a ete regardee pour les choisir.
Idempotent : relancer ne reecrit rien.
"""

from __future__ import annotations

import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta.protocole import experiences  # noqa: E402

log = logging.getLogger("beta.preenregistrer_r12")

ID_EXP = "R12"

REGLES = {
    "univers": ["BTC", "ETH", "SOL", "BNB", "LINK", "XRP"],
    "periode": "train seulement : du 1er jour de metrics + 90 j d'amorcage (BTC 2020-09-01, "
               "autres 2021-12-01) au 2024-12-31 ; hold-out (2025-01-01+) non touche",
    "grille": "decision a chaque cloture horaire t (UTC)",
    "oi": "sum_open_interest (en CONTRATS, pas en valeur : la valeur bouge avec le prix) des "
          "metrics Binance a 5 min ; snapshot horodate <= t",
    "declencheur": {
        "d_oi": "d_oi(t) = OI(t) / OI(t - 1 h) - 1",
        "ret": "ret(t) = close(t) / close(t - 1 h) - 1 (bougies 1h du lake)",
        "quantiles": "quantiles glissants sur les 90 jours PRECEDENT t (t exclu), au moins "
                     "90 jours d'historique sinon aucun signal",
        "cascade_longs": "d_oi(t) <= quantile 2,5 % de d_oi ET ret(t) <= quantile 2,5 % de ret "
                         "=> LONG (on achete aux liquides)",
        "cascade_shorts": "d_oi(t) <= quantile 2,5 % de d_oi ET ret(t) >= quantile 97,5 % de "
                          "ret => SHORT (on vend aux shorts liquides)",
    },
    "entree": "ordre LIMITE au prix close(t), valable 15 min : rempli si le bas (long) / le haut "
              "(short) d'une minute aggTrades de [t, t+15 min) passe STRICTEMENT au-dela du "
              "prix limite (toucher ne suffit pas : file d'attente) ; sinon ordre au MARCHE a "
              "l'ouverture de la minute t+15 min",
    "sortie": "triple barriere du moteur : stop = 2 x ATR(14) des bougies 1h connues a t, "
              "objectif 2 R, horizon 4 h ; barrieres suivies en 5 min a partir de la bougie "
              "qui suit le remplissage ; toutes les sorties au MARCHE",
    "chevauchement": "une seule position par paire : un signal pendant une position ouverte "
                     "sur la meme paire est ignore",
    "couts": {
        "maker": "2 pb, aucun slippage (entree limite remplie)",
        "taker": "5 pb + slippage 5 pb (BTC, ETH) ou 10 pb (SOL, BNB, LINK, XRP) par cote "
                 "(bareme ARIT) : repli au marche et toutes les sorties",
        "detention": "spread (Corwin-Schultz) et funding reel du lake, comme tout Run",
    },
}

METRIQUE = ("R moyen par trade, net de tous les couts (maker/taker selon le remplissage, "
            "slippage, spread, funding), longs et shorts ensemble, 6 paires, train seulement")

REGLE = {
    "confirmee": "R moyen > 0, p survivant a Benjamini-Hochberg sur la famille (1), et les "
                 "neuf portes S1-S9 franchies (S8 : buy-and-hold sur la meme periode)",
    "infirmee": "R moyen <= 0, ou une porte de la batterie echoue",
    "indecidable": "moins de 30 signaux retenus apres elimination des chevauchements",
    "suite_si_confirmee": "AUCUN passage direct au reel : preenregistrement du forward (paper "
                          "sur le vrai carnet, avec la meme regle d'execution), decision de "
                          "Jonas. Le hold-out 2025+ ne s'ouvre qu'une fois, sur decision de "
                          "Jonas, sans aucun reglage entre-temps.",
}

INFORMATIF = {
    "longs_seuls": "R moyen des seuls longs (Jonas prefere le long) : informatif, ne peut ni "
                   "confirmer ni sauver R12",
    "remplissage": "taux de remplissage limite ; R moyen des trades remplis en limite contre "
                   "ceux passes au marche (mesure de la selection adverse)",
    "oi_decale": "meme regle avec l'OI decale d'un pas de 5 min (snapshot <= t - 5 min) : si "
                 "le R moyen change de signe, ALERTE (le resultat tiendrait a l'horodatage)",
    "tout_au_marche": "meme regle avec entree au marche a close(t) : borne pessimiste",
    "par_paire_et_par_annee": "R moyen et n par paire et par annee civile ; alerte si plus de "
                              "la moitie du R total vient d'une seule paire ou d'une seule annee",
}

JUSTIFICATIONS = {
    "1 h": "horizon choisi par Jonas le 12/10 (« heure »)",
    "2,5 %": "queue unilaterale a ~2 sigmas, convention ; MEME seuil pour l'OI et le prix pour "
             "n'avoir qu'un seul nombre a justifier",
    "90 jours": "fenetre glissante des quantiles deja employee par R9 : aucun choix nouveau",
    "contrats": "l'OI en valeur baisse mecaniquement quand le prix baisse : il confondrait la "
                "cascade et le simple mouvement de prix",
    "limite a close(t)": "pas d'ecart arbitraire sous le marche : le prix de la decision, en "
                         "maker",
    "15 min": "un quart de la bougie de decision : au-dela, l'information de la cascade a "
              "l'heure t n'est plus fraiche",
    "remplissage strict": "toucher le prix ne prouve pas qu'un ordre en file aurait ete servi",
    "4 h": "borne haute de l'horizon annonce a Jonas (« 1 a 4 h ») avant sa decision",
    "2 x ATR(14), 2 R": "barrieres par defaut du moteur, inchangees depuis R1 (R7 et R9 aussi)",
    "couts": "bareme ARIT (taker 5 pb, slippage 5/10 pb) ; maker Binance de base 2 pb",
}

HYPOTHESE = (
    "Une cascade de liquidations — une heure ou l'open interest (en contrats) chute dans son "
    "2,5 % le plus bas sur 90 jours glissants ET ou le prix bouge dans sa queue a 2,5 % — est "
    "suivie d'un retour partiel : se porter contrepartie des liquides (acheter apres une "
    "cascade de longs, vendre apres une cascade de shorts), entree par ordre limite au prix de "
    "cloture puis repli au marche apres 15 min, sortie en triple barriere sur 4 h, a un R moyen "
    "strictement positif, tous couts deduits, sur les 6 paires.")

DEJA_CONNU = (
    "R7 (20/08, remesuree le 19/09) : meme intuition par le PRIX seul, meche 4h > 3x ATR(14), "
    "INFIRMEE. Relu le 12/10 : la candidate auto_r7_01 (modele local) est BOGUEE (elle ne "
    "calcule pas d'ATR glissant : min sur toute la serie), ses 2 961 trades a -0,21 R mesurent "
    "le bogue ; auto_r7_03 (impulsion 3x ATR + volume double) : +0,28 R sur 102 trades, MDE "
    "0,47 R, BH, DSR et reality check echoues — sous-puissante, ni pour ni contre. Aucune des "
    "deux n'utilisait l'OI. R2 (retour a la moyenne z-score 48 bougies 4h) INFIRMEE : le retour "
    "a la moyenne NAIF ne paie pas sur ces paires. R9 (funding extreme contrarien) INFIRMEE, "
    "effet dependant du regime. Les metrics (OI) n'ont JAMAIS ete lues par une mesure de BETA "
    "avant ce preenregistrement ; seul le schema des colonnes (12/10, 20 premieres minutes du "
    "01/03/2023) a ete affiche. Les series OHLCV 2019-2024 ont deja servi a toutes les R "
    "precedentes. Issue attendue : infirmee (prior fonde sur R2/R7/R9).")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    if ID_EXP in experiences.etat():
        log.info("%s deja preenregistree : rien a ecrire", ID_EXP)
        return 0
    entree = experiences.preenregistrer(
        ID_EXP, HYPOTHESE, METRIQUE, REGLE,
        split_autorise="train", issue_attendue="infirmee", famille_taille=1,
        deja_connu=DEJA_CONNU,
        decide_par="Jonas, 2026-10-12 : horizon horaire, rachat du creux (longs et shorts), "
                   "entree limite + repli au marche (questionnaire, avant toute mesure)",
        derive_de="I2 / R7 (meme intuition, declencheur different : OI en plus du prix)",
        regles=REGLES, informatif=INFORMATIF, justifications=JUSTIFICATIONS)
    log.info("%s preenregistree — essai cumule n° %s", ID_EXP, entree["n_essais_cumules"])
    log.info("compteur courant : %d", experiences.compteur())
    return 0


if __name__ == "__main__":
    sys.exit(main())
