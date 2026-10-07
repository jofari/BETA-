"""Preenregistrement de VC2 et VC2T — la voie C long uniquement, regime BTC a votes.

    ARIT_HOME=/root/ARIT2.0 /root/venvs/arit/bin/python scripts/preenregistrer_vc2.py

Regles fixees par Jonas le 2026-10-07, question par question, AVANT toute mesure de l'une ou
l'autre version. Ce fichier est la reference : `beta/strategies/voie_c2.py` doit reproduire
CONFIG_VC2 / CONFIG_VC2T a l'identique (test d'empreinte).

    VC2   la version complete : 5 votes (momentum BTC + 4 votes macro).
    VC2T  le temoin : le meme moteur sans aucun vote macro. L'ecart VC2 - VC2T mesure ce que
          la macro apporte — la question que Jonas posait le 28/09 cote ARIT (« on quantifie
          tres mal la macro »).

Une famille de 2 hypotheses, compteur +2. Idempotent : relancer ne reecrit rien.
"""

from __future__ import annotations

import hashlib
import json
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta.protocole import experiences  # noqa: E402

log = logging.getLogger("beta.preenregistrer_vc2")

PAIRES = ["BTC", "ETH", "SOL", "BNB", "LINK", "XRP"]

# Moteur du regime haussier : celui de la config figee le 03/10, sans short ni carry. Les deux
# jambes restantes a 1/2 chacune, comme le 1/3 d'avant (fixe a priori, jamais optimise).
HAUSSIER = {"fenetre_vol_jambes": 180, "fenetre_mom": 126, "poids_jambes": 0.5,
            "cible": 0.20, "fenetre": 30, "lmin": 0.25, "lmax": 2.0, "seuil_levier": 0.25,
            "pas": 1, "bande": 0.20}

# Regime baissier : poche BTC a 25 % du plus haut de l'equite (achat ou vente au signal), puis
# elle flotte ; plafond 100 % du capital du jour (pas de levier en baissier). Alts : 50 %
# vendus au signal, le reste de chaque alt sort quand SON rendement 126 j est negatif.
BAISSIER = {"poche_btc_du_plus_haut": 0.25, "plafond_poche": 1.0, "coupe_alts": 0.5,
            "fenetre_mom_alts": 126}

# Veille : aucun ajout ; l'exposition ne peut que BAISSER, au prorata, quand le brut tenu
# depasse le brut voulu par le moteur haussier de plus que la bande.
VEILLE = {"ajout": False, "reduction_au_prorata": True}

# Bareme ARIT (docs/03 §3.6) : taker 5 pb + slippage par cote, 10 pb hors BTC/ETH.
FRAIS = {"taker_pb": 5.0,
         "slippage_pb": {"BTC": 5.0, "ETH": 5.0, "SOL": 10.0, "BNB": 10.0, "LINK": 10.0,
                         "XRP": 10.0}}

VOTE_MOMENTUM = {"actif": "BTC", "fenetre": 126}

# Seuils, fenetres et peremptions repris d'ARIT (macro_regime.py, params.py) tels quels :
# composant « taux » (60 OBSERVATIONS, +-0,10 pt), F&G (25 / 45), bloc c6/c7 (cassure 20
# sessions, rho 30/90 sessions, armement 0,50 confirme a 0,30, desarmement 0,30, 120 h).
# NASDAQ = le NASDAQ-100 de FRED, comme ARIT — pas l'indice `NASDAQ` du lake (Nasdaq
# Composite, yfinance, non tenu a jour par beta-maj). Le vote ne vaut jamais +1 (A4).
VOTES_MACRO = {
    "taux_reel_10a": {"fred": "DFII10", "fenetre_obs": 60, "seuil_pt": 0.10,
                      "signe_hausse": -1, "perime_h": 48},
    "inflation_anticipee_10a": {"fred": "T10YIE", "fenetre_obs": 60, "seuil_pt": 0.10,
                                "signe_hausse": 1, "perime_h": 48},
    "nasdaq": {"fred": "NASDAQ100", "cassure_obs": 20, "rho_court": 30, "rho_long": 90,
               "arme_si": 0.50, "confirme_long_si": 0.30, "desarme_sous": 0.30,
               "perime_h": 120},
    "fear_greed": {"bas": 25, "haut": 45, "perime_h": 48},
}

# Point-in-time (R2). Ligne t = position tenue pendant le jour t, decidee a t 00:00 UTC.
# prix : cloture de la veille. F&G : valeur datee t-1 (regle ARIT). FRED : valeur datee t-2,
# car une serie H.15 datee J n'est publiee que vers J+1 20:15 UTC — apres le passage du
# timer (00:45 UTC). Avec J+1 le backtest verrait une valeur que le suivi live n'aurait pas.
DECALAGES = {"prix_j": 1, "fng_j": 1, "fred_j": 2}

CONFIG_VC2 = {"version": "VC2", "paires": PAIRES, "vote_momentum": VOTE_MOMENTUM,
              "votes_macro": VOTES_MACRO, "decalages": DECALAGES,
              "seuils_etat": {"haussier": 2, "baissier": -2},
              "haussier": HAUSSIER, "baissier": BAISSIER, "veille": VEILLE, "frais": FRAIS}

# Temoin : meme moteur, aucun vote macro. Un seul vote vaut +-1 et n'atteint jamais +-2 :
# l'etat est donc le signe du momentum BTC (seuils +-1), sans veille hors rodage.
CONFIG_VC2T = {**CONFIG_VC2, "version": "VC2T", "votes_macro": {},
               "seuils_etat": {"haussier": 1, "baissier": -1}}

FENETRE_BACKTEST = ["2021-06-12", "2026-09-05"]
DEBUT_RATTRAPAGE = "2026-09-06"
DEBUT_LIVE = "2026-10-07"


def empreinte(cfg: dict) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:16]


METRIQUE = ("Sharpe net (convention du projet, racine de 252) et maxDD net de la serie "
            "quotidienne du 2021-06-12 au 2026-09-05, frais (taker 5 pb + slippage 5/10 pb "
            "par cote) et funding deduits")

REGLE = {
    "confirmee": "admise au forward : maxDD net >= -25 % ET Sharpe net > Sharpe du hold BTC "
                 "(perpetuel, funding paye, meme fenetre) ET epreuve de causalite passee",
    "infirmee": "maxDD net < -25 % OU Sharpe net <= Sharpe du hold BTC OU causalite en echec",
    "indecidable": "donnees manquantes sur la fenetre (lake ou series macro)",
    "forward": "dry-run de 6 mois a partir du 2026-10-07 : maxDD <= 25 %, vol realisee "
               "(racine de 252, convention de la cible) entre 10 % et 30 %, et des que "
               "l'execution existe : slippage reel <= 2x le modele, zero incident critique. "
               "Comparaison au hold BTC et au hold equipondere : informative. Chaque passage "
               "d'etape est une decision manuelle de Jonas.",
}

DEJA_CONNU = (
    "Aucune mesure de VC2 ni de VC2T avant ce preenregistrement. Deja vu, et qui pese : "
    "(1) la voie C figee (3 jambes, long/short) sur la meme fenetre, et son journal forward "
    "jusqu'au 06/10 ; (2) le diagnostic du 07/10 sur donnees <= 05/09 : la jambe carry fait "
    "~90 % du turnover, et SANS carry (base + trend, avec shorts) Sharpe TRAIN 1,54 / maxDD "
    "-29 %, OOS 0,83 (racine de 365) — le moteur haussier de VC2 en est proche ; (3) ses "
    "parametres (cible 20 %, sigma 30 j, levier 0,25-2, hysteresis 0,25, bande 20 %) ont ete "
    "choisis sur le TRAIN parmi 5 760 configs (DSR ~ 0) : le backtest herite de ce biais ; "
    "(4) cote ARIT : macro jugee faible (B1, 05/09), aucun indicateur public stable (06/09), "
    "Jonas le 28/09 : « la macro detruit meme le backtest, on la quantifie mal » ; ARIT a "
    "mesure 3 fois qu'un signal utile en veto detruit de la valeur en terme additif "
    "(docs/06 §6.2.1) — Jonas a choisi le vote additif en le sachant. La fenetre de backtest "
    "a deja servi (TRAIN et OOS de la voie C) : le backtest elimine le manifestement faux, "
    "il ne confirme rien. La validation est le forward."
)

COMMUN = {
    "split_autorise": "fenetre deja vue par la voie C (2021-06-12 -> 2026-09-05)",
    "issue_attendue": "confirmee",
    "famille_taille": 2,
    "deja_connu": DEJA_CONNU,
    "fenetre_backtest": FENETRE_BACKTEST,
    "debut_rattrapage": DEBUT_RATTRAPAGE,
    "debut_live": DEBUT_LIVE,
    "decide_par": "Jonas, 2026-10-07, regle par regle",
}

HYPOTHESES = [
    {
        "id_exp": "VC2",
        "hypothese": (
            "Un portefeuille LONG uniquement sur les 6 perpetuels, pilote par un regime BTC a "
            "5 votes (momentum BTC 126 j, taux reel 10 ans, inflation anticipee 10 ans, "
            "cassure du NASDAQ quand BTC lui est couple, Fear & Greed) — haussier a somme "
            ">= +2 (moteur vol-cible sans short ni carry), baissier a <= -2 (poche BTC a 25 % "
            "du plus haut, alts -50 % puis sortie sur leur propre tendance), veille entre "
            "les deux (positions figees, reduction seule) — tient son budget de risque "
            "(maxDD >= -25 %) et bat le hold BTC en Sharpe net."),
        "metrique_primaire": METRIQUE,
        "metrique_secondaire": (
            "apport de la macro = r_net quotidien VC2 - VC2T, moyenne et IC bootstrap par "
            "blocs a 95 % : apporte si IC > 0, detruit si IC < 0, indecidable sinon "
            "(attendu : indecidable, puissance faible sur 5 ans)"),
        "config": CONFIG_VC2,
        "empreinte": empreinte(CONFIG_VC2),
    },
    {
        "id_exp": "VC2T",
        "hypothese": (
            "Temoin de VC2 sans aucun vote macro : regime = signe du momentum BTC 126 j, "
            "meme moteur haussier, memes regles baissieres. Meme regle de decision que VC2."),
        "metrique_primaire": METRIQUE,
        "config": CONFIG_VC2T,
        "empreinte": empreinte(CONFIG_VC2T),
    },
]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    deja = experiences.etat()
    for h in HYPOTHESES:
        id_exp = h["id_exp"]
        if id_exp in deja:
            log.info("%s deja preenregistree (empreinte %s) : rien a ecrire",
                     id_exp, deja[id_exp].get("empreinte"))
            continue
        champs = {k: v for k, v in h.items() if k not in ("id_exp", "hypothese",
                                                         "metrique_primaire")}
        entree = experiences.preenregistrer(id_exp, h["hypothese"], h["metrique_primaire"],
                                            REGLE, **COMMUN, **champs)
        log.info("%s preenregistree — empreinte %s, essai cumule n° %s",
                 id_exp, h["empreinte"], entree["n_essais_cumules"])
    log.info("compteur courant : %d", experiences.compteur())
    return 0


if __name__ == "__main__":
    sys.exit(main())
