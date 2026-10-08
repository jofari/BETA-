"""Preenregistrement de VC3 — la voie C2 corrigee : poche BTC « maximum », en spot.

    ARIT_HOME=/root/ARIT2.0 /root/venvs/arit/bin/python scripts/preenregistrer_vc3.py

Decide par Jonas le 2026-10-07, APRES la mesure de VC2/VC2T (infirmees : maxDD -34,8 % et
-38,2 % pour un budget de -25 %) et apres la decomposition de leur perte. Deux changements,
et deux seulement ; tout le reste est la config VC2 du registre, a l'identique :

    1. poche BTC « maximum » (12:59 UTC) : au signal baissier, BTC = min(tenu, 25 % du plus
       haut de l'equite). La regle ne fait plus que vendre. Celle de VC2 rachetait du BTC
       dans 9 episodes sur 9, et ce rachat a fait -15,4 points des -34,8 %.
    2. spot, cible 20 % (13:07 UTC) : le levier de VC2 n'a jamais servi (brut max 1,00), mais
       les perpetuels coutaient 2,7 %/an de funding. Spot = aucun funding, exposition brute
       plafonnee a 1 (pas d'emprunt), frais spot Binance 0,10 % par cote + le meme slippage.

Une hypothese seule, sans temoin (refaire VC2T n'apprendrait rien de plus sur la macro) :
compteur 59 -> 60. Idempotent : relancer ne reecrit rien.

Batterie anti-surapprentissage, demandee par Jonas a 13:13 UTC (« teste aussi l'overfitting
potentiel avec beta »), ecrite ici AVANT la mesure, seuils compris. Elle ne peut que
degrader le verdict : R1 peut infirmer VC3, R2 a R4 ne font qu'informer ou alerter. Les 10
voisins de R1 sont des mesures : chacun est journalise et paie son cran de compteur
(arbitrage A1), soit 60 -> 70 apres la mesure.
"""

from __future__ import annotations

import copy
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta.protocole import experiences  # noqa: E402
from beta.strategies import voie_c2 as c2  # noqa: E402

log = logging.getLogger("beta.preenregistrer_vc3")

ID_EXP = "VC3"


def config_vc3() -> dict:
    """La config VC2 RELUE dans le registre (empreinte verifiee), plus les deux changements."""
    cfg = copy.deepcopy(c2.config("VC2"))
    cfg["version"] = ID_EXP
    cfg["baissier"]["poche"] = "maximum"
    cfg["instrument"] = "spot"
    cfg["plafond_brut"] = 1.0
    # Taux spot Binance sans remise BNB (ARIT docs/03 : « le taux spot 0,1 % »). Le slippage
    # par cote reste celui du bareme ARIT (5 pb BTC/ETH, 10 pb les autres) : deja prudent a
    # la taille du canari (10 k).
    cfg["frais"]["taker_pb"] = 10.0
    return cfg


FENETRE_BACKTEST = ["2021-06-12", "2026-09-05"]

METRIQUE = ("Sharpe net (convention du projet, racine de 252) et maxDD net de la serie "
            "quotidienne du 2021-06-12 au 2026-09-05, frais spot (taker 10 pb + slippage "
            "5/10 pb par cote) deduits, aucun funding ; prix = clotures des perpetuels du lake, "
            "proxy du spot (ecart verifie le 07/10, voir deja_connu)")

REGLE = {
    "confirmee": "admise au forward : maxDD net >= -25 % ET Sharpe net > Sharpe du hold BTC "
                 "SPOT (sans funding, meme fenetre, memes clotures) ET epreuve de causalite "
                 "passee ET reglages non fragiles (R1 : la mediane des 10 voisins passe aussi "
                 "la porte)",
    "infirmee": "maxDD net < -25 % OU Sharpe net <= Sharpe du hold BTC spot OU causalite en "
                "echec OU fragilite (R1)",
    "indecidable": "donnees manquantes sur la fenetre (lake ou series macro)",
    "forward": "dry-run de 6 mois a partir du 2026-10-08 : maxDD <= 25 %, vol realisee "
               "(racine de 252, convention de la cible) entre 10 % et 30 %, et des que "
               "l'execution existe : slippage reel <= 2x le modele, zero incident critique. "
               "Comparaison au hold BTC spot et au hold equipondere : informative. Chaque "
               "passage d'etape est une decision manuelle de Jonas.",
}

DEJA_CONNU = (
    "VC2 et VC2T mesurees le 07/10 sur cette fenetre, INFIRMEES : Sharpe 0,72 / 0,78 (hold BTC "
    "perpetuel 0,33), maxDD -34,8 % / -38,2 %. Decomposition exacte du maxDD de VC2 (baisse du "
    "08/11/2021 au 21/11/2022) : -16,8 points pendant le retard du signal (alts -11,8), -15,4 "
    "points sur la poche BTC constituee par un ACHAT au signal (BTC 7 % -> 30 % du capital le "
    "19/12/2021, puis -66 %), -2,6 de reste. La poche de VC2 est un achat dans 9 episodes "
    "baissiers sur 9 (25 sur 26 pour VC2T), car le moteur ne tient qu'environ 15 % de BTC en "
    "haussier ; BTC etait plus haut 90 j apres dans 7 cas sur 9 (le rachat paie en correction, "
    "il coule en vrai marche baissier). Calcul grossier fait AVANT ce preenregistrement : "
    "poche « maximum » ~ -23 % sur la meme baisse (cible 30 % : ~ -35 %). La correction a "
    "donc ete trouvee en regardant la seule vraie baisse de la fenetre : ce backtest est "
    "flatteur par construction, il peut eliminer VC3, pas la valider — seul le forward "
    "tranche. Spot : dans VC2 le levier n'a jamais servi (brut max 1,00, moyen 0,41, median "
    "0,60 en haussier, multiplicateur > 1 sur 1,3 % des jours haussiers) mais le funding a "
    "coute 2,70 %/an contre 0,35 %/an de frais (turnover 2,7x/an). Prix : le lake n'a que les "
    "perpetuels ; leurs clotures servent de proxy du spot. Ecart verifie le 07/10 contre "
    "l'API spot Binance sur la fenetre, sans regarder la strategie : prime fin - debut <= "
    "10 pb par paire, ecart de suivi 0,4 a 1 %/an ; seul ecart notable SOL le 09/11/2022 (FTX, "
    "perp 17 % sous le spot, resorbe le lendemain). Tout ce que declarait VC2 vaut encore : "
    "voie C figee, diagnostic carry, parametres du moteur choisis sur le TRAIN parmi 5 760 "
    "configs (DSR ~ 0), macro jugee faible cote ARIT, apport mesure VC2 - VC2T -2,7 %/an, "
    "IC 95 % [-8,0 ; +2,9]."
)

# Un parametre a la fois, deux valeurs. Seuls les reglages de CALENDRIER (fenetres, bande) :
# ils n'ont pas de sens de risque, donc un VC3 nettement meilleur que ses voisins serait un
# creux trouve par chance sur la seule baisse de la fenetre. Les reglages de NIVEAU de risque
# (cible, poche, coupe des alts) font bouger le maxDD dans un sens connu : ils ne disent rien
# du surapprentissage et ne sont pas mesures (ils couteraient 6 crans pour rien).
VOISINS = {
    "vote_momentum.fenetre": [90, 180],          # le signal de regime BTC (retard de 2021)
    "haussier.fenetre_mom": [90, 180],           # la jambe tendance du moteur
    "baissier.fenetre_mom_alts": [90, 180],      # la sortie des alts en baissier
    "haussier.fenetre": [20, 45],                # la sigma du vol-targeting
    "haussier.bande": [0.10, 0.30],              # la bande de reequilibrage
}

SURAPPRENTISSAGE = {
    "R1_plateau": {
        "role": "PORTE : peut infirmer VC3",
        "voisins": VOISINS,
        "regle": "VC3 infirmee pour fragilite si la MEDIANE des 10 voisins echoue a la porte : "
                 "mediane des maxDD nets < -25 % OU mediane des Sharpe nets <= Sharpe du hold "
                 "BTC spot. Un voisin meilleur que VC3 ne devient JAMAIS candidat : il "
                 "faudrait un nouveau preenregistrement, qui porterait tout ce lot dans son N.",
    },
    "R2_sharpe_degonfle": {
        "role": "informatif",
        "methode": "S2 (multitest.sharpe_degonfle) sur r_net de VC3 : pleine fenetre, TRAIN, "
                   "OOS ; N = compteur du banc apres la mesure (~70), puis N + 5 810 configs "
                   "regardees pour la voie C (precedent voie_c_verif) dont VC3 herite le moteur",
        "lecture": "DSR ~ 0 attendu au N de la famille, comme la voie C le 03/10 : sur 5 ans, "
                   "aucun Sharpe <= 1 ne resiste a ~5 900 essais. C'est la limite de "
                   "l'historique, pas un verdict sur VC3 (A2 : la batterie elimine, elle ne "
                   "confirme pas ; le forward tranche).",
    },
    "R3_cone_et_ecart_au_hold": {
        "role": "informatif, avec alerte",
        "methode": "bootstrap par blocs stationnaire (S3), l = 5, 20, 50 j, 2 000 rejeux, "
                   "graine 0 : distribution du maxDD de VC3 (mediane, 5e centile, "
                   "P(maxDD < -25 %)) et IC 95 % de Sharpe(VC3) - Sharpe(hold BTC spot) en "
                   "tirage apparie",
        "alerte": "P(maxDD < -25 %) > 50 % pour l = 20 j : le budget ne tient que par le chemin "
                  "observe. Ecrit dans le verdict ; le dry-run reste le juge.",
    },
    "R4_stabilite": {
        "role": "informatif, avec alerte",
        "methode": "Sharpe, CAGR et maxDD sur TRAIN (<= 2024-06-30), OOS (>= 2024-07-01, deja "
                   "vu par la voie C) et par annee civile",
        "alerte": "Sharpe OOS < 0, ou plus de la moitie du gain total venue d'une seule annee",
    },
}

HYPOTHESE = (
    "La voie C2 (memes 5 votes, memes seuils, meme moteur haussier, memes regles d'alts et "
    "de veille) avec une poche BTC « maximum » au signal baissier — BTC = min(tenu, 25 % du "
    "plus haut de l'equite), jamais d'achat — et en SPOT (aucun funding, exposition brute "
    "<= 1, frais spot) tient son budget de risque (maxDD >= -25 %) et bat le hold BTC spot "
    "en Sharpe net.")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    deja = experiences.etat()
    if ID_EXP in deja:
        log.info("%s deja preenregistree (empreinte %s) : rien a ecrire",
                 ID_EXP, deja[ID_EXP].get("empreinte"))
        return 0
    cfg = config_vc3()
    entree = experiences.preenregistrer(
        ID_EXP, HYPOTHESE, METRIQUE, REGLE,
        split_autorise="fenetre deja vue par la voie C et par VC2/VC2T "
                       "(2021-06-12 -> 2026-09-05)",
        issue_attendue="confirmee", famille_taille=1, deja_connu=DEJA_CONNU,
        fenetre_backtest=FENETRE_BACKTEST, debut_rattrapage="2026-09-06",
        debut_live="2026-10-08",
        decide_par="Jonas, 2026-10-07 : poche « maximum, jamais d'achat » (12:59 UTC), spot "
                   "cible 20 % (13:07 UTC), apres la mesure de VC2/VC2T",
        derive_de="VC2 (config du registre, empreinte 744700fa7d8980fc)",
        surapprentissage=SURAPPRENTISSAGE,
        surapprentissage_demande_par="Jonas, 2026-10-07 13:13 UTC, avant la mesure",
        config=cfg, empreinte=c2.empreinte(cfg))
    log.info("%s preenregistree — empreinte %s, essai cumule n° %s",
             ID_EXP, entree["empreinte"], entree["n_essais_cumules"])
    log.info("compteur courant : %d", experiences.compteur())
    return 0


if __name__ == "__main__":
    sys.exit(main())
