"""Preenregistrement de TI1 — les 5 votes du socle VC dans leur usage INVEST (onglet Test invest).

    ARIT_HOME=/root/ARIT2.0 /root/venvs/beta/bin/python scripts/preenregistrer_ti1.py

Cahier des charges de Jonas du 2026-10-20 (« Test invest ») : les votes du regime n'ont ete
mesures qu'en trading actif (VC2-VC5) ; ici, ils pilotent l'exposition E d'un panier tenu en
buy and hold, et la question est la SURVIE aux grandes baisses, a cout acceptable en hausse
ratee — pas la prediction. Phase 0 rendue le meme jour
(/root/rapports/2026-10-20_test-invest-phase0.md), decisions D1-D6 de Jonas (« oui pour
tout ») ecrites dans la config ci-dessous, AVANT toute mesure.

Compteur 93 -> 94, puis +1 par (config x periode) mesuree (D5) : la campagne en compte 24.
Idempotent : relancer ne reecrit rien.
"""

from __future__ import annotations

import json
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta.protocole import experiences  # noqa: E402
from beta.strategies import voie_c2 as c2  # noqa: E402

log = logging.getLogger("beta.preenregistrer_ti1")

ID_EXP = "TI1"
SOCLE = "VC3"
VOTES = ("momentum_btc", "taux_reel_10a", "inflation_anticipee_10a", "nasdaq", "fear_greed")


def config_ti1() -> dict:
    """Tout ce qui fixe la mesure. Les votes sont relus dans le registre (`c2.config`)."""
    socle = c2.config(SOCLE)
    return {
        "version": ID_EXP,
        "socle": {"relu_dans": SOCLE, "empreinte": c2.empreinte(socle),
                  "blocs": {k: socle[k] for k in ("vote_momentum", "votes_macro", "decalages",
                                                   "seuils_etat")},
                  "note": "blocs des votes identiques dans VC2, VC4 et VC5 (verifie le 20/10)"},
        "votes": list(VOTES),
        "pit": {"mode": "publication",
                "regle": "DFII10 et NASDAQ100 : observation D utilisable a la decision t si "
                         "t >= jour ouvre US suivant D (feries federaux) + 1 jour ; staleness "
                         "du socle conservee (4 j DFII10, 7 j NASDAQ, mesures a la decision). "
                         "momentum, T10YIE et F&G : `voie_c2.votes` tel quel (deja PIT)",
                "decide": "D1, Jonas 20/10"},
        "donnees": {"source": "lake BETA : clotures 1d 00:00 UTC des perpetuels USDT-M "
                              "Binance (proxy du spot) ; FRED et F&G du lake ; DS1 non utilise "
                              "(aucune bougie 1D)",
                    "panier": {"paires": ["BTC", "ETH", "SOL", "BNB", "XRP", "LINK"],
                               "poids": "egaux, non rebalance (les poids derivent)"},
                    "benchmark_secondaire": "BTC en buy and hold",
                    "trou_accepte": {"fear_greed 2024-10-26": "D6 : regle de peremption du "
                                     "socle (valeur du 25/10, <= 48 h)"}},
        "periodes": {"principale": ["2024-01-11", "2026-10-19"],
                     "stress": ["2020-09-15", "2026-10-19"],
                     "convention": "dates = premier et dernier jour de RENDEMENT ; V0 = 1 a la "
                                   "cloture de la veille du premier jour (P0) ; fin figee"},
        "exposition": {"decalage": "E decidee a la cloture t, appliquee au rendement de t+1",
                       "socle": {"theta_h": 0.4, "theta_b": 0.4, "e_haut": 1.0, "e_def": 0.25,
                                 "veille": "E inchangee (memoire)", "e_init": 1.0},
                       "paliers": {"theta_h": 0.4, "theta_b": 0.4, "e_haut": 1.0,
                                   "e_neutre": 0.7, "e_def": 0.25},
                       "score": "somme des votes actifs / nombre de votes actifs",
                       "levier": "aucun (E <= 1) ; rf = 0 ; pas de cout d'entree (ni pour "
                                 "le hold)"},
        "couts": {"kappa_pb": 10.0, "par": "unite de |E(t-1) - E(t-2)|"},
        "survie": {"theta_episode": 0.20, "theta_faux": 0.10, "horizon_faux_j": 60,
                   "captures": "semaines civiles completes (lundi -> dimanche UTC)"},
        "nulls": {"B": 1000, "graine": 0, "m_j": 90,
                  "graines_derivees": "SeedSequence([graine, crc32(null), crc32(signal), "
                                      "crc32(periode)])",
                  "circulaire": "s'(t) = s((t + tau) mod N), tau uniforme dans [m, N - m]",
                  "segments": "ordre des periodes de valeur constante melange, sans jamais "
                              "recoller deux periodes de meme valeur (durees conservees)",
                  "sur": "socle (score total, mapping socle) et chaque vote seul (paliers)"},
        "annualisation": "365 jours (Sharpe en racine de 365 : non comparable aux mesures VC, "
                         "racine de 252)",
        "temoin": "exposition constante = moyenne de E sur la periode, memes couts (reference, "
                  "hors compteur)",
    }


CAMPAGNE = {
    "par_periode": [
        "socle complet, mapping socle (nulls)",
        "socle complet, mapping paliers",
        "chaque vote seul, mapping paliers (nulls) x 5",
        "chaque ablation (4 votes), mapping socle x 5",
    ],
    "configs": 24,
    "kappa_spearman": "les 10 paires de votes, par periode (hors compteur)",
}

METRIQUE = ("Ulcer Index de la strategie (racine de la moyenne des DD(t)^2, courbe quotidienne, "
            "V0 = 1), par periode, jamais agregee. Secondaires : protection agregee (Prot, "
            "ponderee par la gravite des episodes >= 20 % du panier), Calmar, |MDD|. Sharpe "
            "(racine de 365) et DSR (N = compteur) informatifs.")

REGLE = {
    "p_retenue": "par signal et par periode : p = max(p_circulaire, p_segments) de l'Ulcer "
                 "(il faut battre LES DEUX nulls, D4), p = (1 + #{M_b <= M_obs}) / (1 + B)",
    "reel": "p < 0,05 : effet considere comme reel",
    "non_concluant": "0,05 <= p < 0,20 : non concluant, documente tel quel, aucune conclusion "
                     "favorable",
    "hasard": "p >= 0,20 : indistinguable du hasard",
    "multiplicite": "q de Benjamini-Hochberg sur les 6 signaux de chaque periode, INFORMATIF : "
                    "ne change aucun verdict (D4)",
    "secondaires": "p de Prot et Calmar (plus grand = meilleur) et de |MDD| (plus petit = "
                   "meilleur), rapportees sans verdict",
    "application": "mecanique, sans reinterpretation (Jonas, 20/10)",
    "puissance": "periode a moins de 3 episodes >= 20 % : signalee en rouge",
    "indecidable": "serie manquante ou trouee hors trou accepte (C5) : arret, aucun chiffre",
}

HYPOTHESE = (
    "Dans leur usage invest (exposition long-only E d'un panier des 6 paires tenu en buy and "
    "hold, decidee a la cloture et appliquee le lendemain), le socle des 5 votes VC et chacun "
    "de ses votes pris seul reduisent la gravite des grandes baisses (Ulcer Index) davantage "
    "que le meme signal dont le lien temporel avec les prix est rompu (decalage circulaire et "
    "melange de segments, meme distribution d'exposition).")

DEJA_CONNU = (
    "Rapport et red team du 19/10 (/root/rapports/2026-10-19_reflexion-vc6-audit.md, 12/06/2021 "
    "-> 18/10/2026) : le momentum donne la direction (l'etat suit son signe 1 204 jours sur 1 206 "
    "hors veille), la veille dure 38 % du temps, le vote NASDAQ vaut -1 sur 6,6 % des jours et "
    "change l'etat 28 jours en 5 ans, F&G et momentum sont correles a +0,67, DFII10 et T10YIE a "
    "-0,24, le F&G vaut +1 sur 1 049 jours et -1 sur 420. VC2 contre VC2T (07/10) : apport des 4 "
    "votes -2,7 %/an, IC 95 % [-8,0 ; +2,9], maxDD -34,8 % contre -38,2 %, turnover 2,7 contre "
    "5,9 fois/an. VC3 et VC5 mesurees et suivies en forward sur ces memes fenetres. Phase 0 du "
    "20/10, SANS P&L ni indicateur : episodes >= 20 % du panier = 3 en principale (-32,1 %, "
    "-43,3 %, -61,9 % non rattrape), 7 en stress (domines par 2021-11 -> 2022-12, -86 %) ; "
    "ecart PIT des votes (calendrier de publication contre decalage fixe) : DFII10 5,2 % des "
    "jours (45 sur 1 013 en principale), NASDAQ 1,6 % (9), etat du regime 2,4 %. Ce test peut "
    "eliminer un vote, il ne peut pas en valider un : tout a deja ete regarde sur ces fenetres.")

ISSUE_ATTENDUE = {
    "note": "a priori de Claude, ecrit avant tout calcul",
    "socle": "reel en stress, non concluant en principale",
    "momentum_btc": "reel en stress, non concluant en principale",
    "fear_greed": "non concluant",
    "taux_reel_10a": "hasard",
    "inflation_anticipee_10a": "hasard",
    "nasdaq": "hasard",
}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    deja = experiences.etat()
    if ID_EXP in deja:
        log.info("%s deja preenregistree (empreinte %s) : rien a ecrire",
                 ID_EXP, deja[ID_EXP].get("empreinte"))
        return 0
    cfg = config_ti1()
    entree = experiences.preenregistrer(
        ID_EXP, HYPOTHESE, METRIQUE, REGLE,
        split_autorise="fenetres deja vues : principale (rendements du 2024-01-11 au "
                       "2026-10-19, hold-out 2025+ inclus, consomme pour l'allocation "
                       "quotidienne depuis le 13/10) et stress (2020-09-15 -> 2026-10-19), "
                       "rapportees separement, jamais agregees",
        issue_attendue=json.dumps(ISSUE_ATTENDUE, ensure_ascii=False), famille_taille=12,
        deja_connu=DEJA_CONNU,
        decide_par="Jonas, 2026-10-20 : cahier des charges « Test invest », puis « oui pour "
                   "tout » aux decisions D1-D6 et aux choix par defaut de la Phase 0",
        campagne=CAMPAGNE, compteur="+1 par (config x periode) mesuree (D5, enregistrer_run)",
        config=cfg, empreinte=c2.empreinte(cfg))
    log.info("%s preenregistree — empreinte %s, essai cumule n° %s",
             ID_EXP, entree["empreinte"], entree["n_essais_cumules"])
    log.info("compteur courant : %d", experiences.compteur())
    return 0


if __name__ == "__main__":
    sys.exit(main())
