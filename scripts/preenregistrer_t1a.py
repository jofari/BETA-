"""Preenregistrement de T1A — Temps 1, etape A (laboratoire actions) : SMA 200 contre MOM126 et
COUCHE1, sur le S&P 500 et le Nasdaq-100, moteur TI1 tel quel.

    /root/venvs/beta/bin/python scripts/preenregistrer_t1a.py

Prompt de Jonas du 2026-10-21 (« BETA / Temps 1, etape A (laboratoire) », valeurs par defaut du
preenregistrement du 21/10/2026), Phase 1 rendue AVANT tout code (temps1/DISCOVERY.md, 714aeae),
decisions de Jonas du meme soir : Nasdaq-100 ^NDX, or LBMA PM via le World Gold Council.

Compteur : 117 avant ; +1 ici (hypothese sans mesure), puis les 14 couples (detecteur x actif)
journalises avant le premier calcul remplacent ce +1 : 131 attendu apres. Idempotent.
"""

from __future__ import annotations

import hashlib
import json
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta.protocole import experiences  # noqa: E402
from beta.temps1 import campagne as ca  # noqa: E402
from beta.temps1 import detecteurs as det  # noqa: E402
from beta.temps1 import donnees as dn  # noqa: E402

log = logging.getLogger("beta.preenregistrer_t1a")

ID_EXP = ca.ID_EXP


def config_t1a() -> dict:
    defaut = ca.Config("SMA200", "SPX")
    return {
        "version": ID_EXP,
        "prompt": "Jonas 2026-10-21, « BETA / Temps 1, etape A (laboratoire) »",
        "moteur": {"reutilise": "beta.invest.moteur / metriques / nulls (TI1, run de reference "
                                "84d75b9fef3e), sans modification",
                   "calendrier": "clotures de la cible sur le calendrier CIVIL, comblees par la "
                                 "derniere valeur connue (rendement nul sans seance) : convention "
                                 "du moteur (365 j, captures sur semaines de 7 j) ; score en "
                                 "vigueur le jour i = decision a la cloture de la derniere seance "
                                 "<= i - 1 ; meme courbe qu'un calcul seance par seance aux dates "
                                 "de seance (test)",
                   "exposition": "decidee a la cloture J, appliquee au rendement de J+1",
                   "mapping": {"nom": "paliers", "theta": 0.4, "e_haut": 1.0, "e_neutre": 0.7,
                               "e_def": 0.25, "scores": "vrai/expansion +1, monetaire 0, "
                                                       "faux/liquidite -1"},
                   "kappa_pb": defaut.kappa_pb, "kappa_par": "unite de |dE| (1,0 -> 0,25 = 7,5 pb)",
                   "rf": 0.0, "cout_entree": "aucun", "levier": "aucun",
                   "indices": "de prix, dividendes exclus"},
        "cibles": {"SPX": "S&P 500 ^GSPC (Yahoo)", "NDX": "Nasdaq-100 ^NDX (Yahoo, Jonas 21/10)"},
        "detecteurs": {
            "SMA200": "reference : cloture cible > SMA simple 200 clotures -> 1,0 sinon 0,25",
            "bande": {k: f"meme regle, {n} clotures" for k, n in det.SMA_FENETRES.items()
                      if k != "SMA200"},
            "MOM126": "rendement de la cible sur 126 seances > 0 -> 1,0 sinon 0,25",
            "COUCHE1": {"T": "cloture S&P 500 < SMA 200 du S&P 500 (quelle que soit la cible)",
                        "V": f"VIX > {det.VIX_SEUIL:g}",
                        "Y": f"USD/JPY (DEXJPUS) en baisse de plus de 5 % sur "
                             f"{det.USDJPY_FENETRE} observations",
                        "G": "fixing or > SMA 200 de l'or (200 fixings)",
                        "etats": "liquidite si V ou Y -> 0,25 ; sinon monetaire si T et G -> "
                                 "0,7 ; sinon expansion -> 1,0"},
            "inegalites": "strictes, telles qu'ecrites ; chaque indicateur sur SES seances, "
                          "derniere valeur connue a la decision"},
        "donnees": {
            "sources": {"SPX": "Yahoo ^GSPC", "NDX": "Yahoo ^NDX", "VIX": "Yahoo ^VIX",
                        "XAU_LBMA": "fixing LBMA PM USD/oz via World Gold Council (fsapi.gold.org,"
                                    " requetes annuelles) — ecart a yfinance (Jonas 21/10)",
                        "DEXJPUS": "FRED DEXJPUS (H.10, hebdomadaire)"},
            "collecteur": "beta/marches (data/marches, etat.json), hors lake, hors Binance, "
                          "hors freqtrade",
            "pit": {"SPX, NDX": "cloture du jour",
                    "VIX": "cloture du jour (16:15 ET, 15 min apres les actions : idealisation "
                           "« decide a la cloture » du moteur, signalee)",
                    "XAU_LBMA": "fixing PM 15:00 Londres, utilisable le jour meme",
                    "DEXJPUS": "publication ALFRED V -> utilisable a la cloture de la premiere "
                               "seance strictement apres V ; date ALFRED non informative (retard "
                               f"> {dn.RETARD_ALFRED_PLAUSIBLE_J} j : observation anterieure a "
                               "l'archive) ou absente -> decalage de 2 jours ouvres US (feries "
                               "federaux), signale avec ses comptes"},
            "trous": "seance de la cible sans observation -> derniere valeur connue ; comptes "
                     "par serie et par periode (seances comblees, suites > 5 seances)",
            "prechauffe": f"{dn.PRECHAUFFE_SEANCES} observations de chaque serie lue avant la "
                          "premiere decision (au moins la fenetre du detecteur), sinon arret",
            "crypto": "aucune"},
        "periodes": {"labo": list(ca.LABO), "informative": [ca.DEBUT_INFORMATIVE,
                                                            "derniere seance commune des deux "
                                                            "cibles au lancement, figee"],
                     "convention": "dates = premier et dernier jour de rendement ; V0 = 1 a la "
                                   "cloture de la veille du premier jour"},
        "survie": {"theta_episode": defaut.theta_episode, "theta_faux": defaut.theta_f,
                   "horizon_faux_j": defaut.horizon_j,
                   "defensif": "E <= 0,25 (retard, faux signaux)",
                   "captures": "semaines civiles completes"},
        "nulls": {"B": defaut.b, "graine": defaut.graine, "m_j": defaut.m_j,
                  "graines_derivees": "flux(0, null, '<detecteur>:<cible>', periode)",
                  "circulaire": "decalage circulaire du score, tau dans [90, N - 90] jours civils",
                  "segments": "melange des periodes de score constant, jamais recollees",
                  "metriques": "Ulcer (decide), |MDD|, protection, Calmar (rapportees)"},
        "temoin": "exposition constante = moyenne de E sur la periode, memes frais",
    }


HYPOTHESE = (
    "Sur le S&P 500 et le Nasdaq-100 tenus en buy and hold avec une exposition long-only decidee "
    "a la cloture J et appliquee en J+1 (labo 1991-2023, indices de prix), un detecteur de regime "
    "(MOM126 ou COUCHE1) reduit la gravite des grandes baisses (Ulcer Index) plus que : le meme "
    "signal dont le lien temporel avec les prix est rompu (nulls TI1), une exposition constante "
    "egale a son exposition moyenne, et la SMA 200 de la cloture — sur les DEUX actifs.")

METRIQUE = ("Ulcer Index de la strategie (racine de la moyenne des DD(t)^2, courbe quotidienne "
            "du calendrier civil comble, V0 = 1), par (detecteur x actif x periode), jamais "
            "agrege. Rapportes sans verdict : MDD, protection par episode >= 20 %, retard de "
            "detection, faux signaux et leur cout, captures haussiere et baissiere, CAGR, "
            "exposition moyenne, nombre de changements, p circulaire, p segments.")

REGLE = {
    "porte_1_hasard": "p retenue = max(p circulaire, p segments) de l'Ulcer (D4 inchangee) < 0,05",
    "porte_2_temoin": "Ulcer < Ulcer de l'exposition constante egale a l'exposition moyenne",
    "porte_3_reference": "Ulcer < Ulcer de SMA200, meme actif, meme periode",
    "periode_jugee": "labo seulement (1991-01-01 -> 2023-12-31)",
    "candidats": "MOM126 et COUCHE1 : retenus s'ils franchissent les 3 portes sur les 2 actifs ; "
                 "si les deux passent, les deux sont retenus (aucun departage n'est prevu)",
    "sma200": "portes 1 et 2 appliquees a SMA200 elle-meme ; « SMA200 retenue » si elle les "
              "franchit sur les 2 actifs et qu'aucun candidat n'est retenu",
    "verdict": "candidat retenu > SMA200 retenue > aucun timing demontre, mecanique, sans "
               "reinterpretation",
    "bande": "SMA126/168/210/252 : rapportees cote a cote, SANS portes (aucun choix de fenetre)",
    "informative": "2024-01-01 -> fin : tableau separe, « deja vu, ne decide rien »",
    "puissance": "periode a moins de 3 episodes >= 20 % : signalee",
    "indecidable": "serie absente, prechauffe insuffisante ou DEXJPUS illisible : arret, aucun "
                   "chiffre ; toute regle non implementable exactement : arret et rapport "
                   "(regle 2 du prompt)",
}

DEJA_CONNU = (
    "Aucun chiffre de ce labo n'a ete calcule : ni detecteur, ni rendement de strategie, ni "
    "Ulcer. Les sondes du 21/10 n'ont lu que des niveaux isoles pour controler les sources (SPX "
    "330,22 au 31/12/1990, 1 527,46 au 24/03/2000, 676,53 au 09/03/2009 ; NDX 4 704,73 au "
    "27/03/2000 ; VIX 80,86 au 20/11/2008, 82,69 au 16/03/2020 ; or 850 $ au 21/01/1980, 1 895 $ "
    "au 05/09/2011). Connu de tous : l'histoire 1991-2023 de ces indices est publique et a servi a "
    "populariser la SMA 200 (Faber 2007) et le momentum de series temporelles (Moskowitz, Ooi, "
    "Pedersen 2012) — le labo n'est hors echantillon pour personne, il peut eliminer un "
    "detecteur, il ne peut pas en sacrer un. La periode informative a ete vecue en direct. TI1 "
    "(crypto, 20/10) : momentum 126 j de BTC « hasard » sur ses deux periodes, autre actif. "
    "COUCHE1 vient du preenregistrement de Jonas du 21/10 ; son origine n'est pas documentee ici.")

ISSUE_ATTENDUE = {
    "note": "a priori de Claude, ecrit avant tout calcul",
    "SMA200": "portes 1 et 2 franchies sur les deux actifs",
    "MOM126": "portes 1 et 2 franchies, porte 3 echouee sur au moins un actif",
    "COUCHE1": "porte 1 incertaine (VIX en retard sur les baisses, lent a redescendre), porte 3 "
               "echouee sur au moins un actif",
    "verdict": "SMA200 retenue",
}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    deja = experiences.etat()
    if ID_EXP in deja:
        log.info("%s deja preenregistree (empreinte %s) : rien a ecrire",
                 ID_EXP, deja[ID_EXP].get("empreinte"))
        return 0
    avant = experiences.compteur()
    cfg = config_t1a()
    entree = experiences.preenregistrer(
        ID_EXP, HYPOTHESE, METRIQUE, REGLE,
        split_autorise="labo 1991-01-01 -> 2023-12-31 (decide) ; informative 2024-01-01 -> "
                       "derniere seance (deja vue, ne decide rien) ; actions = laboratoire, "
                       "aucune donnee crypto, hold-out crypto de BETA non concerne",
        issue_attendue=json.dumps(ISSUE_ATTENDUE, ensure_ascii=False), famille_taille=14,
        deja_connu=DEJA_CONNU,
        decide_par="Jonas, 2026-10-21 : prompt « BETA / Temps 1, etape A (laboratoire) » "
                   "(valeurs par defaut du preenregistrement du 21/10/2026) ; Nasdaq-100 ^NDX et "
                   "or LBMA PM via le World Gold Council (questions du 21/10 ~17:30 UTC)",
        detecteurs=list(det.DETECTEURS), cibles=list(ca.CIBLES),
        compteur={"avant": avant, "regle": "+1 par couple (detecteur x actif) = 14, journalises "
                                           "avant le premier calcul", "attendu_apres": avant + 14},
        config=cfg,
        empreinte=hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:16])
    log.info("%s preenregistree — empreinte %s, compteur %d -> %d (hypothese sans mesure)",
             ID_EXP, entree["empreinte"], avant, experiences.compteur())
    return 0


if __name__ == "__main__":
    sys.exit(main())
