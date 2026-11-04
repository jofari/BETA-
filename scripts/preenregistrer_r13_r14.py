"""Preenregistrement de R13 (or) et R14 (Nasdaq-100) — R8 « fade de l'open New York » retestee.

Jonas, 04/11/2026 : « retester sur les memes parametres mais sur l'or et le nasdaq maintenant
qu'on a les donnees ». Perimetre choisi par lui le meme jour, apres l'inventaire des donnees :
or 5m + Nasdaq 1h, les 3 variantes de stop.

    /root/venvs/arit/bin/python scripts/preenregistrer_r13_r14.py
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta.protocole import experiences  # noqa: E402

LOT_R13 = ["r13_ny_or_stop_050", "r13_ny_or_stop_100", "r13_ny_or_stop_150"]
LOT_R14 = ["r14_ny_ndx1h_stop_050", "r14_ny_ndx1h_stop_100", "r14_ny_ndx1h_stop_150"]

REGLE = {
    "confirmee": "au moins une des 3 variantes CONFIRMEE par le moteur : R moyen > 0, p survivant "
                 "a Benjamini-Hochberg sur la famille de 3, et les dix portes S1-S10 franchies "
                 "(S8 : buy-and-hold du meme actif sur la meme periode ; S10 : PBO du lot < 20 %)",
    "infirmee": "aucune variante confirmee ni indecidable : R moyen <= 0, ou une porte echoue",
    "indecidable": "aucune variante confirmee, et au moins une indecidable (moins de 30 signaux "
                   "apres elimination des chevauchements, ou porte non executable)",
    "verdict_par_le_programme": "scripts/mesurer_r13_r14.py applique cette regle aux issues "
                                "rendues par pipeline.cribler et clot l'experience lui-meme",
    "suite_si_confirmee": "AUCUN passage au reel : preenregistrement d'un paper sur le perpetuel "
                          "TradFi (XAUUSDT / QQQUSDT), decision de Jonas. Le hold-out 2025+ reste "
                          "scelle pour ces actifs.",
}

DEJA_CONNU_COMMUN = (
    "R8 (21/08, remesuree le 19/09 aux couts corriges) : la MEME regle sur les 6 cryptos en 5m est "
    "INFIRMEE, 8 portes sur 9 echouees, R moyen -0,29 / -0,16 / -0,12 (stops 0,5x / 1x / 1,5x) sur "
    "10 744 trades, negative 5 annees sur 6, MFE moyen +1,48 R contre une cible a 3 R, 66 % de "
    "sorties au stop. Ces chiffres sont connus de Jonas et de Claude au moment d'ecrire ceci ; "
    "c'est pour cela que les PARAMETRES sont ceux de R8 tels quels (aucun reglage choisi apres "
    "avoir vu les cryptos), et les 3 variantes gardees (Jonas : « les 3 »). "
    "Regarde AVANT ce preenregistrement, sur le train seulement et sans aucun rendement : "
    "la couverture des series (dates, nombre de bougies, heures des bougies 1h du NDX), et le "
    "nombre de signaux de la regle avec l'epreuve de causalite (signaux(df[:t]) == "
    "signaux(df)[:t], 25 coupures, OK). Les series intraday de l'or et du NDX n'ont servi a "
    "aucune mesure de BETA avant ceci (Temps 1 et Test invest n'ont lu que du QUOTIDIEN). "
    "Couts = ceux du moteur pour un perpetuel Binance (0,10 % aller-retour + 0,02 % de slippage "
    "+ spread d'un tick) : c'est le prix de l'instrument qu'on traderait (XAUUSDT, QQQUSDT), pas "
    "celui de l'indice, qui ne se trade pas. Pas de funding (serie comptant / indice) : sous-"
    "estime un peu le cout d'une position tenue au plus 6 h. Issue attendue : infirmee (prior R8)."
)

r13 = experiences.preenregistrer(
    "R13",
    "R8 a l'identique sur l'OR COMPTANT (XAU/USD, Dukascopy BID, 5m) : les 45 premieres minutes "
    "de la seance americaine (09:30-10:15 New York, changements d'heure compris) sont une prise "
    "de liquidite ; entrer a la cloture de 10:15 dans le sens OPPOSE au corps de la fenetre, stop "
    "a 0,5x / 1x / 1,5x son amplitude, cible 3 R, horizon 72 bougies 5m, a un R moyen "
    "strictement positif, couts deduits.",
    "R moyen par trade (triple barriere du moteur, take_profit_r=3.0, horizon 72 bougies 5m, "
    "couts aller-retour deduits), par variante, lot des 3 variantes",
    REGLE,
    split_autorise="train",
    issue_attendue="infirmee",
    famille_taille=3,
    deja_connu=DEJA_CONNU_COMMUN + " Or : 395 signaux sur la periode (193 longs).",
    derive_de="R8",
    decide_par="Jonas, 2026-11-04 : memes parametres que R8, or 5m + Nasdaq 1h, les 3 stops",
    regles={"actif": "XAU_SPOT (data/marches, beta.marches.intraday)", "timeframe": "5m",
            "periode": "2023-06-21 (1re bougie 5m) -> 2024-12-31, FIGEE : le rattrapage de l'or "
                       "vers 2003 n'elargit PAS cette mesure (un elargissement = un nouvel id)",
            "candidates": LOT_R13, "take_profit_r": 3.0, "horizon_bougies": 72},
)

r14 = experiences.preenregistrer(
    "R14",
    "R8 sur le NASDAQ-100 (^NDX, Yahoo) en 1h, seule resolution disponible avant 2025 : la "
    "premiere bougie horaire de la seance (09:30-10:30 New York, 60 min au lieu des 45 de R8) est "
    "une prise de liquidite ; entrer a sa cloture (10:30) dans le sens OPPOSE a son corps, stop a "
    "0,5x / 1x / 1,5x son amplitude, cible 3 R, horizon 6 bougies 1h (les 6 h de R8, jusqu'a la "
    "cloture de 16:00), a un R moyen strictement positif, couts deduits.",
    "R moyen par trade (triple barriere du moteur, take_profit_r=3.0, horizon 6 bougies 1h, "
    "couts aller-retour deduits), par variante, lot des 3 variantes",
    REGLE,
    split_autorise="train",
    issue_attendue="infirmee",
    famille_taille=3,
    deja_connu=DEJA_CONNU_COMMUN + (
        " NDX : 278 signaux (131 longs) — a peine au-dessus de 30 par variante apres "
        "chevauchements, test PEU puissant. Variante IMPOSEE par la donnee et non choisie : "
        "fenetre de 60 min, barrieres lues en 1h (un stop et une cible touches dans la meme "
        "bougie se tranchent par la convention du moteur, plus souvent qu'en 5m)."),
    derive_de="R8",
    decide_par="Jonas, 2026-11-04 : memes parametres que R8, or 5m + Nasdaq 1h, les 3 stops",
    regles={"actif": "NDX (data/marches, beta.marches.intraday)", "timeframe": "1h",
            "periode": "2023-11-22 (1re bougie 1h) -> 2024-12-31, FIGEE",
            "candidates": LOT_R14, "take_profit_r": 3.0, "horizon_bougies": 6},
)

for e in (r13, r14):
    print(f"{e['id']} preenregistree — N au preenregistrement : {e['n_essais_cumules']}")
print(f"compteur trading courant : {experiences.compteur()}")
