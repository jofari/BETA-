"""Preenregistrement de VC4 — VC3 decidee a chaque ouverture de session, au dernier prix.

    ARIT_HOME=/root/ARIT2.0 /root/venvs/arit/bin/python scripts/preenregistrer_vc4.py

Decide par Jonas le 2026-10-10 (~23:15 UTC), en lisant le dashboard Forward : « le recalcul
journalier pose probleme, il devrait s'activer a chaque ouverture de session en semaine et une
fois par jour le week-end », puis, au questionnaire, « tout recalculer au dernier prix » et une
variante SEPAREE de VC5 (cible 35 %). Un seul changement par rapport a VC3 : la CADENCE. La
config (votes, seuils, moteur, poche maximum, spot, plafond 1, frais, bande) est celle de VC3,
relue dans le registre ; l'empreinte couvre en plus le calendrier des decisions.

LES INSTANTS DE DECISION (fixes ici, avant toute mesure)
    lundi -> vendredi (date UTC) : ouverture de Tokyo 09:00 Asia/Tokyo (= 00:00 UTC),
        de Londres 08:00 Europe/London (07:00 UTC en heure d'ete, 08:00 en hiver),
        de New York 09:30 America/New_York (13:30 UTC en heure d'ete, 14:30 en hiver) ;
    samedi, dimanche : une decision, 00:00 UTC.
    Jours feries ignores (le marche crypto ne ferme pas ; seule l'heure compte). Heures d'ete
    par la base IANA (zoneinfo).

CE QUI EST RECALCULE A CHAQUE INSTANT t (« tout, au dernier prix »)
    - prix de t = cloture de la derniere bougie 5 min close a t (ouverte a t - 5 min) ;
    - le vote momentum BTC (126 j), le momentum des alts en baissier (126 j) et tout le moteur
      haussier (vol 180 j, momentum 126 j, sigma 30 j, levier, poids) sont calcules sur une
      serie QUOTIDIENNE ANCREE a l'heure de t : le prix a cette heure-la chaque jour. Memes
      fenetres en jours que VC3 ; a 00:00 UTC, c'est exactement VC3 (verifie : les clotures
      5 min reproduisent les clotures 1d du lake a l'identique sur 2 217 jours, 10/10) ;
    - les votes macro (DFII10, T10YIE, Nasdaq-100) et le F&G : ceux de VC3 pour le jour civil
      UTC de t, memes delais de publication (FRED <= J-2, F&G <= J-1). Rien de plus frais en
      cours de journee : pas de donnee publiee qu'on n'aurait pas eue ;
    - l'etat, la bande de 20 points, la poche baissiere et le plus haut de l'equite : regles de
      VC3, appliquees a chaque instant au lieu de chaque jour.
    Les positions decidees a t sont tenues jusqu'a l'instant suivant ; frais de VC3 sur chaque
    echange. Rendement quotidien = produit des periodes du jour (chaque jour commence par une
    decision a 00:00 UTC) : meme grille de jours que VC3, comparaison directe.

Compteur 81 -> 82, puis +10 avec les voisins de R1 a la mesure (arbitrage A1), comme VC3.
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

log = logging.getLogger("beta.preenregistrer_vc4")

ID_EXP = "VC4"

CALENDRIER = {
    "semaine": [
        {"session": "Tokyo", "heure": "09:00", "fuseau": "Asia/Tokyo"},
        {"session": "Londres", "heure": "08:00", "fuseau": "Europe/London"},
        {"session": "New York", "heure": "09:30", "fuseau": "America/New_York"},
    ],
    "week_end": [{"session": "quotidienne", "heure": "00:00", "fuseau": "UTC"}],
    "jours_semaine": "lundi a vendredi, date UTC",
    "feries": "ignores",
    "prix": "cloture de la derniere bougie 5 min close a l'instant (ouverte a t - 5 min)",
    "moteur": "serie quotidienne ancree a l'heure UTC de l'instant ; fenetres de VC3 en jours",
    "macro": "votes de VC3 du jour civil UTC de l'instant (memes delais de publication)",
}


def config_vc4() -> dict:
    """La config VC3 RELUE dans le registre (empreinte verifiee), plus le calendrier."""
    cfg = copy.deepcopy(c2.config("VC3"))
    cfg["version"] = ID_EXP
    cfg["cadence"] = CALENDRIER
    return cfg


FENETRE_BACKTEST = ["2021-06-12", "2026-09-05"]

METRIQUE = ("Sharpe net (racine de 252) et maxDD net de la serie QUOTIDIENNE (00:00 -> 00:00 "
            "UTC, produit des periodes entre instants) du 2021-06-12 au 2026-09-05, memes "
            "frais et memes prix que VC3 (spot : taker 10 pb + slippage 5/10 pb par cote a "
            "CHAQUE echange, aucun funding ; bougies 5 min des perpetuels du lake, proxy du spot)")

REGLE = {
    "confirmee": "admise au forward : maxDD net >= -25 % ET Sharpe net > Sharpe du hold BTC "
                 "SPOT (meme fenetre) ET epreuves de causalite passees (troncature a un "
                 "instant, perturbation des prix posterieurs) ET reglages non fragiles (R1 : la "
                 "mediane des 10 voisins passe aussi la porte)",
    "infirmee": "maxDD net < -25 % OU Sharpe net <= Sharpe du hold BTC spot OU causalite en "
                "echec OU fragilite (R1)",
    "indecidable": "donnees manquantes sur la fenetre (bougies 5 min, lake ou series macro)",
    "forward": "dry-run de 6 mois a partir du 2026-10-12 (premier lundi : les trois sessions) "
               "avec les criteres de VC3 : maxDD >= -25 %, vol realisee (racine de 252) entre "
               "10 % et 30 %, et des que l'execution existe : slippage reel <= 2x le modele, "
               "zero incident critique. Comparaisons a VC3 et aux holds : informatives. Chaque "
               "passage d'etape est une decision manuelle de Jonas.",
}

DEJA_CONNU = (
    "VC3 (meme config, une decision par jour a 00:00 UTC) mesuree le 07/10 sur cette fenetre, "
    "CONFIRMEE de justesse : Sharpe 0,80, maxDD -23,2 %, turnover 2,2x/an ; 4 voisins sur 10 "
    "crevent le budget, tous sur les fenetres de momentum ; alertes R3 et R4. VC5 (cible 35 %) "
    "mesuree le 10/10 juste avant ce preenregistrement : CONFIRMEE (Sharpe 0,75, maxDD -31,1 %). "
    "Rien n'a ete mesure en intraday avant ce preenregistrement ; seule verification faite : "
    "les bougies 5 min du lake reproduisent les clotures 1d a l'identique (2 217 jours, 6 paires, "
    "aucune bougie 5 min manquante depuis 2021). Precedent : sur la voie C, le reglage fin des "
    "frequences s'est revele du bruit (03/10) ; decider plus souvent augmente le turnover et "
    "donc les frais. La fenetre est vue et revue : ce backtest peut eliminer VC4, il ne la "
    "valide pas. Le benefice attendu par Jonas est la REACTIVITE (couper ou entrer en cours de "
    "journee) : un VC4 qui ne fait pas mieux que VC3 serait a dire tel quel.")

VOISINS = {
    "vote_momentum.fenetre": [90, 180],
    "haussier.fenetre_mom": [90, 180],
    "baissier.fenetre_mom_alts": [90, 180],
    "haussier.fenetre": [20, 45],
    "haussier.bande": [0.10, 0.30],
}

SURAPPRENTISSAGE = {
    "R1_plateau": {
        "role": "PORTE : peut infirmer VC4",
        "voisins": VOISINS,
        "regle": "VC4 infirmee pour fragilite si la MEDIANE des 10 voisins echoue a la porte : "
                 "mediane des maxDD nets < -25 % OU mediane des Sharpe nets <= Sharpe du hold "
                 "BTC spot. Un voisin meilleur que VC4 ne devient JAMAIS candidat.",
    },
    "R2_sharpe_degonfle": {"role": "informatif", "methode": "comme VC3"},
    "R3_cone_et_ecart_au_hold": {
        "role": "informatif, avec alerte",
        "methode": "comme VC3 (bootstrap par blocs, l = 5, 20, 50 j, 2 000 rejeux, graine 0)",
        "alerte": "P(maxDD < -25 %) > 50 % pour l = 20 j",
    },
    "R4_stabilite": {
        "role": "informatif, avec alerte",
        "methode": "comme VC3",
        "alerte": "Sharpe OOS < 0, ou plus de la moitie du gain total venue d'une seule annee",
    },
    "comparaison_vc3": {
        "role": "informatif",
        "methode": "Sharpe, CAGR, maxDD, turnover et frais de VC4 contre VC3, IC 95 % de "
                   "Sharpe(VC4) - Sharpe(VC3) en bootstrap apparie (l = 20 j) ; nombre de "
                   "changements d'etat en cours de journee ; ce que la cadence apporte ou coute",
    },
}

HYPOTHESE = (
    "VC3 decidee a chaque ouverture de session en semaine (Tokyo, Londres, New York) et une "
    "fois a 00:00 UTC le week-end, tout recalcule au dernier prix (momentum et moteur sur des "
    "series quotidiennes ancrees a l'heure de la decision ; macro du jour civil, memes delais), "
    "tient le budget de VC3 (maxDD >= -25 %) et bat le hold BTC spot en Sharpe net.")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    deja = experiences.etat()
    if ID_EXP in deja:
        log.info("%s deja preenregistree (empreinte %s) : rien a ecrire",
                 ID_EXP, deja[ID_EXP].get("empreinte"))
        return 0
    cfg = config_vc4()
    entree = experiences.preenregistrer(
        ID_EXP, HYPOTHESE, METRIQUE, REGLE,
        split_autorise="fenetre deja vue par la voie C, VC2, VC2T, VC3 et VC5 "
                       "(2021-06-12 -> 2026-09-05)",
        issue_attendue="confirmee", famille_taille=1, deja_connu=DEJA_CONNU,
        fenetre_backtest=FENETRE_BACKTEST, debut_rattrapage="2026-09-06",
        debut_live="2026-10-12",
        decide_par="Jonas, 2026-10-10 ~23:15 UTC : ouvertures de session en semaine + une fois "
                   "par jour le week-end, tout recalcule au dernier prix, variante separee de "
                   "VC5 (questionnaire, avant toute mesure)",
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
