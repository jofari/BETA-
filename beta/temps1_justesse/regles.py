"""T1J : les regles GELEES du test de justesse. Ce module ne calcule rien.

Source : prompt de Jonas du 2026-10-24 (« BETA / Temps 1 : test de JUSTESSE des detecteurs de
regime », regles reprises du preenregistrement « Temps 1 : detecteur de regime » gele le
22/10/2026), decouverte `temps1_justesse/DISCOVERY.md` (7be0fe1), puis les reponses de Jonas
du 24/10 : 9 questions, ambiguites A a F, et 3 precisions (fenetre de V, « solide », f_sortie).

`REGLES` est fige par `scripts/preenregistrer_t1j.py` (empreinte = sha256 du JSON trie). La
campagne refuse de tourner si l'empreinte a change depuis : changer une regle apres le gel
demande un amendement explicite, jamais une retouche silencieuse.
"""

from __future__ import annotations

import hashlib
import json

ID_EXP = "T1J"

# Detecteurs du verdict, de la bande et des variantes informatives de C1_V1.
VERDICT = ("SMA200", "MOM126", "C1_V1", "C1_V2")
CANDIDATS = ("MOM126", "C1_V1", "C1_V2")
REFERENCE = "SMA200"
BANDE = ("SMA126", "SMA168", "SMA210", "SMA252")
VARIANTES_C1 = ("C1_V1_S21", "C1_V1_S126")
SMA_FENETRES = {"SMA126": 126, "SMA168": 168, "SMA200": 200, "SMA210": 210, "SMA252": 252}
FENETRE_C1 = {"C1_V1": 63, "C1_V1_S21": 21, "C1_V1_S126": 126}

# Actifs juges : nom interne -> serie de `beta.marches`.
ACTIFS = {"SPX": "SPX", "NDX": "NDX", "OR": "XAU_LBMA", "BTC": "BTC_DS1"}
LABO_ACTIFS = ("SPX", "NDX", "OR")
TEMOIN = ("SPX", "NDX")

LABO = ("1991-01-01", "2023-12-31")
DEBUT_INFORMATIVE = "2024-01-01"
PRECHAUFFE_SEANCES = 252

DELTA_REF_BAISSE = 0.20
VARIANTES_JUGE = {"baisse_15": {"baisse_ref": 0.15}, "baisse_25": {"baisse_ref": 0.25},
                  "sigma_unique": {"sigma_unique": True}}
ANNUALISATION = 252
N_TIRAGES = 1000
GRAINE = 0

# Couche 1 : seuils tels qu'ecrits dans le prompt.
C1_V1_SEUILS = {"k_vix": 2.0, "saut_vix_5": 0.30, "k_jpy": 2.0, "bande_t": 0.03, "k_t": 1.5,
                "bande_g": 0.03, "k_g": 1.5, "delta": 5, "sma": 200}
C1_V2_SEUILS = {"vix": 25.0, "jpy_fenetre": 21, "jpy_baisse": 0.05, "sma": 200}
MOM_FENETRE = 126
JOURS_OUVRES_PUBLICATION = 2       # DEXJPUS : 2e jour ouvre Fed apres le vendredi de la semaine

REGLES: dict = {
    "version": ID_EXP,
    "prompt": "Jonas 2026-10-24, « BETA / Temps 1 : test de JUSTESSE des detecteurs de regime » "
              "(regles du preenregistrement « Temps 1 : detecteur de regime » gele le 22/10/2026)",
    "objet": "justesse de signaux bear / bull / neutre contre une datation des cycles faite apres "
             "coup (le juge) ; aucune exposition, aucun sizing, aucun Ulcer, aucune performance",
    "donnees": {
        "series": {"SPX": "beta.marches SPX (Yahoo ^GSPC)", "NDX": "beta.marches NDX (Yahoo ^NDX)",
                   "OR": "beta.marches XAU_LBMA (fixing LBMA PM, World Gold Council)",
                   "BTC": "beta.marches BTC_DS1 (DS1 bougies_1d, Bitstamp BTC/USD, Jonas 24/10)",
                   "VIX": "beta.marches VIXCLS (FRED)",
                   "USDJPY": "beta.marches DEXJPUS (FRED, H.10)"},
        "trous": "derniere valeur connue ; nombre de seances comblees rapporte par serie et "
                 "periode",
        "dexjpus_publication": "ALFRED indisponible ; vrai calendrier (Jonas 24/10, E) : une "
                               "observation de la semaine S (lundi-vendredi) devient utilisable a "
                               "la cloture du 2e jour ouvre Fed strictement apres le vendredi de S "
                               "(mardi en temps normal, mercredi si le lundi est ferie ; jours "
                               "ouvres = lundi-vendredi hors feries federaux US)",
        "pit_autres": "SPX, NDX, VIX : cloture du jour ; or : fixing PM du jour ; BTC : cloture du "
                      "jour civil UTC",
        "prechauffe_seances": PRECHAUFFE_SEANCES,
    },
    "periodes": {
        "labo": list(LABO),
        "informative": [DEBUT_INFORMATIVE, "derniere date de chaque actif au lancement, figee "
                                           "par l'empreinte des donnees ; deja vu, ne decide rien"],
        "btc": ["premier trimestre civil precede de 2 ans d'historique BTC (decision 6)",
                "derniere date au lancement"],
    },
    "actifs": {"labo": list(LABO_ACTIFS), "etape_b": ["BTC"],
               "temoin": "SPX et NDX = un seul temoin actions : chaque mesure = moyenne des deux "
                         "valeurs ; episodes SPX et NDX mis ensemble pour la majorite (decision "
                         "4) ; chaque actif aussi rapporte seul"},
    "calendriers": "chaque actif juge sur SES dates (SPX, NDX : seances US ; or : jours de "
                   "fixing ; BTC : 7 j / 7) ; SMA et MOM sur les clotures de l'actif juge ; "
                   "couche 1 calculee sur les seances US (SPX), chaque indicateur sur ses "
                   "propres observations puis derniere valeur connue ; signal C1 d'une seance US "
                   "valable jusqu'a la seance US suivante sur le calendrier de l'actif "
                   "(decision 5)",
    "detecteurs": {
        "signal": "-1 bear, 0 neutre, +1 bull, un par jour de l'actif juge",
        "SMA_n": "bear si cloture < moyenne simple des n dernieres clotures (jour compris), "
                 "bull sinon ; n = " + ", ".join(f"{k} {v}" for k, v in SMA_FENETRES.items()),
        "MOM126": "bear si cloture(t) / cloture(t - 126 seances) - 1 < 0, bull sinon",
        "C1_V1": {
            "fenetre_w": FENETRE_C1["C1_V1"],
            "V": "VIX > moyenne_w(VIX) + 2 sigma_w(VIX) OU VIX(t) / VIX(t - 5) - 1 > 0,30",
            "Y": "rendement 5 observations de USD/JPY < -2 sigma_w(rendements 5 observations)",
            "T": "d = SPX / SMA200(SPX) - 1 ; vrai si d < 0 OU (0 <= d <= 0,03 ET "
                 "Delta5(d) < -1,5 sigma_w(Delta5(d)))",
            "G": "g = or / SMA200(or) - 1 ; vrai si g > 0 OU (-0,03 <= g < 0 ET "
                 "Delta5(g) > +1,5 sigma_w(Delta5(g)))",
            "notations": "sigma_w = ecart-type d'echantillon (ddof 1) des w dernieres valeurs, "
                         "jour compris ; moyenne_w idem ; Delta5(x) = x(t) - x(t - 5)",
        },
        "C1_V2": {"V": "VIX > 25", "Y": "USD/JPY(t) / USD/JPY(t - 21 observations) - 1 < -0,05",
                  "T": "SPX < SMA200(SPX)", "G": "or > SMA200(or)"},
        "etats_C1": "1. stress de liquidite si V ou Y -> bear ; 2. sinon stress monetaire si T "
                    "et G -> neutre ; 3. sinon expansion -> bull ; regime global juge contre "
                    "chaque actif",
        "variantes_C1_V1": "C1_V1_S21 et C1_V1_S126 : w = 21 et 126 pour moyenne_w et sigma_w de "
                           "V et sigma_w de Y, T, G (Jonas 24/10 : moyenne et sigma ensemble) ; "
                           "informatives, labo seulement",
    },
    "juge": {
        "algorithme": "en bull, suivre Hmax depuis le debut du bull ; des que P(t) <= Hmax (1 - "
                      "theta_baisse), bear, qui commence au jour du plus haut ; en bear, suivre "
                      "Lmin ; des que P(t) >= Lmin (1 + theta_hausse), bull, qui commence au jour "
                      "du plus bas ; etat de depart fixe par le premier franchissement ; dernier "
                      "cycle en cours exclu de toute mesure",
        "theta": "delta_ref = |ln(1 - 0,20)| ; sigma_actif(q) = ecart-type (ddof 1) des "
                 "rendements log quotidiens de l'actif sur les 2 annees civiles precedant le "
                 "debut du trimestre q, x racine(252) ; sigma_SP_ref = meme calcul sur le SPX "
                 "de toute la periode labo, constante (aussi pour le BTC et 2024 -> fin, "
                 "decision 8) ; delta(q) = delta_ref sigma_actif(q) / sigma_SP_ref ; "
                 "theta_baisse = 1 - exp(-delta) ; theta_hausse = exp(delta) - 1 ; theta du "
                 "trimestre civil du jour t",
        "segments": "bear = jours [pic, creux[ ; bull = jours [creux, pic suivant[",
        "historique": "le juge tourne sur tout l'historique de l'actif, a partir du premier "
                      "trimestre precede de 2 ans de donnees",
        "variantes": "baisse de reference 15 % et 25 % ; sigma unique (sigma_actif calcule une "
                     "fois sur la periode jugee : labo pour SPX, NDX, or ; periode BTC pour le "
                     "BTC) ; rapportees, NON comptees (Jonas 24/10, F)",
    },
    "mesures": {
        "domaine": "periode mesuree M = [premier pivot du juge dans la periode, dernier pivot du "
                   "juge dans la periode[ (B : un episode n'appartient a une periode que si ses "
                   "deux bornes y sont ; le dernier cycle en cours est exclu)",
        "f_entree": "pour chaque bear (pic tau, creux c) dans M : t_k = premier jour >= tau en "
                    "bear ; f = (P(tau) - P(t_k)) / (P(tau) - P(c)) ; pas de bear avant c = rate, "
                    "compte f = 1 dans la mediane et le pire cas (A), nombre de rates a part",
        "f_sortie": "pour chaque bull (creux c, pic suivant) dans M : premier jour >= c en bull ; "
                    "f = (P(ce jour) - P(c)) / (P(pic suivant) - P(c)) ; pas de bull avant le pic "
                    "suivant = rate de sortie, compte f = 1 (Jonas 24/10, comme A)",
        "retard": "jours civils et seances de l'actif entre tau et t_k",
        "fausses_alertes": "episodes bear du detecteur (jours bear consecutifs) qui commencent "
                           "dans M et ne recoupent aucun bear du juge (tout l'historique, bear "
                           "en cours compris), par an (jours civils de M / 365,25)",
        "bascules": "changements de signal entre deux jours consecutifs de M, par an",
        "justesse": "Rbear = jours bear du juge (dans M) bien classes / jours bear du juge ; "
                    "Rbull idem ; justesse = (Rbear + Rbull) / 2",
        "neutres": "episode neutre de n jours : juste si |ln(P fin / P debut)| <= sigma_jour "
                   "racine(n), P debut = cloture de la veille du premier jour neutre (C), P fin "
                   "= cloture du dernier, sigma_jour = sigma_actif(q) / racine(252) du trimestre "
                   "du premier jour ; ses jours sont alors bien classes, sinon mal classes",
        "hasard_neutres": f"{N_TIRAGES} tirages par paire detecteur x actif (Jonas 24/10), "
                          f"graine {GRAINE} : duree tiree parmi celles des episodes neutres du "
                          "detecteur entierement dans M, debut tire uniformement dans M ; taux de "
                          "reussite rapporte a cote de celui du detecteur",
    },
    "verdict": {
        "domination": "A domine B si mediane f_entree(A) <= B et fausses alertes / an (A) <= B, "
                      "dont au moins une strictement",
        "regle_3": "candidat (MOM126, C1_V1, C1_V2) retenu en etape A s'il n'est domine par "
                   "SMA200 ni sur le temoin actions ni sur l'or, ET si f_entree < f_entree de "
                   "SMA200 sur strictement plus de la moitie des episodes de chacun des deux "
                   "(temoin : episodes SPX et NDX ensemble ; egalite = pas plus faible)",
        "etape_b": "TOUS les retenus de l'etape A passent l'etape B (Jonas 24/10, D) ; domine "
                   "par SMA200 sur le BTC = elimine",
        "gagnant": "parmi les retenus apres l'etape B : domines elimines (regle 1, sur les "
                   "moyennes temoin / or), puis plus petite moyenne des medianes f_entree temoin "
                   "et or ; egalite : meilleur pire cas moyen (D)",
        "aucun": "aucun candidat retenu -> « SMA200 retenue comme brique regime »",
        "solide": "meme gagnant ET meme liste de retenus sous les 3 variantes du juge (Jonas "
                  "24/10)",
        "indecidable": "un couple du verdict sans bear complet dans M, une prechauffe "
                       "insuffisante ou une regle non implementable : aucun verdict, arret et "
                       "rapport",
    },
    "compteur": {
        "famille": "invest (tests de detecteurs, comme T1A)",
        "essais_verdict": "4 detecteurs (SMA200, MOM126, C1_V1, C1_V2) x 3 actifs labo (SPX, "
                          "NDX, or) + 4 detecteurs x BTC = 16, journalises avant le premier "
                          "calcul",
        "essais_informatifs": "bande SMA (4 fenetres x 3 actifs labo = 12) + C1_V1 sigma 21 et "
                              "126 (2 x 3 actifs labo = 6) = 18, sur une ligne a part, aucun "
                              "compteur ; variantes du juge : rapportees, pas des essais",
        "valeurs": "global (compteur_total) : 117 au gel du 22/10 (valeur du prompt, gardee), "
                   "131 avant T1J ; invest (compteur famille invest) : 38 avant T1J",
    },
    "rapport": "ecrit par le programme, sans interpretation au-dela du verdict mecanique ; "
               "clarifications du 24/10 en tete de RAPPORT_JUSTESSE.md",
    # Les valeurs que le code lit : elles entrent dans l'empreinte, comme les textes.
    "parametres": {
        "verdict": list(VERDICT), "candidats": list(CANDIDATS), "reference": REFERENCE,
        "bande": list(BANDE), "variantes_c1": list(VARIANTES_C1), "sma": SMA_FENETRES,
        "fenetre_c1": FENETRE_C1, "actifs": ACTIFS, "labo_actifs": list(LABO_ACTIFS),
        "temoin": list(TEMOIN), "labo": list(LABO), "debut_informative": DEBUT_INFORMATIVE,
        "prechauffe": PRECHAUFFE_SEANCES, "baisse_ref": DELTA_REF_BAISSE,
        "variantes_juge": VARIANTES_JUGE, "annualisation": ANNUALISATION,
        "n_tirages": N_TIRAGES, "graine": GRAINE, "c1_v1": C1_V1_SEUILS, "c1_v2": C1_V2_SEUILS,
        "mom": MOM_FENETRE, "jours_ouvres_publication": JOURS_OUVRES_PUBLICATION,
    },
}


def empreinte(regles: dict | None = None) -> str:
    """sha256 (16 caracteres) du JSON trie des regles : ce que le preenregistrement fige."""
    texte = json.dumps(REGLES if regles is None else regles, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()[:16]
