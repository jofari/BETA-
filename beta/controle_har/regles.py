"""Controle HAR : les regles GELEES. Ce module ne calcule rien.

Texte fige : VC6_V1/controle_har/PREENREGISTREMENT.md (prompt de Jonas du 01/11/2026, mot pour mot,
et ses applications), dont l'empreinte est ecrite au registre. `REGLES` porte les valeurs que le
code lit ; son empreinte aussi. La campagne refuse de tourner si l'une ou l'autre a change.
"""

from __future__ import annotations

import hashlib
import json

ID_EXP = "VC6_V1_CONTROLE_HAR"
FIN = "2026-10-31"                         # date de fin figee a l'etape A
DOSSIER_COPIES = "data/vc6_v1/sources_figees"
SHA256 = {                                 # copies figees de l'etape A (VC6_V1/spec_figee.md)
    "BTC_perp_5m": "42e62509f051ece9fd86f2a19848e36d53b88b0661243b9aae91320e4caf3618",
    "ETH_perp_5m": "5e1a62bff2d7a21e2971e321d03e789d074a814c3f329c327e9af7c2ce7a592f",
    "SOL_perp_5m": "0771ad9ed20d60bc1b5e17d16e384fda03f2b2ec447656e938c182923f4fe75d",
    "BTC_perp_1d": "1bd26426c4cf103bb4b19766aa0a67cefbfe18d9532fe0997592935cab25cb93",
    "ETH_perp_1d": "19eec6a3c1882cfb484a54891c1dbf586ce519d50665b135d0c1153005cc172f",
    "SOL_perp_1d": "58e10ba349297c52ccf30ffc5364811c4ddf95d819c6bdefab078217d9d57c42",
}
ACTIFS = {a: {"bougies_5m": f"{DOSSIER_COPIES}/{a}_perp_5m.parquet",
              "bougies_1d": f"{DOSSIER_COPIES}/{a}_perp_1d.parquet",
              "serie": f"perpetuel Binance USDT-M {a} (lake BETA)"}
          for a in ("BTC", "ETH", "SOL")}

BARRES_PAR_JOUR = 288                      # barres 5 min ouvertes de 00:00 a 23:55 UTC
PART_MANQUANTE_MAX = 0.10                  # jour exclu si manquantes > 10 % des 288 barres
HORIZON = 5                                # cible : RV moyenne des 5 jours suivants
FENETRES_HAR = (1, 5, 22)                  # RV du jour, moyennes 5 et 22 jours (jour compris)
FENETRE_MCO = 730                          # jours de RV dans la fenetre glissante
FENETRE_ECART_TYPE = 30                    # rendements log journaliers
DDOF = 1
COUPURES_CAUSALITE = ("2021-12-31", "2022-12-31", "2023-12-31", "2024-12-31", "2025-12-31")
HAR, ECART_TYPE = "HAR", "ecart-type 30 jours"

REGLES: dict = {
    "version": ID_EXP,
    "preenregistrement": "VC6_V1/controle_har/PREENREGISTREMENT.md",
    "prompt": "Jonas 2026-11-01, « GO phase 2 : Controle HAR »",
    "statut": "test de mesure : aucun essai ajoute au compteur (diagnostic=True, famille invest)",
    "donnees": {"actifs": ACTIFS, "sha256": SHA256, "fin": FIN,
                "jour": "barres ouvertes de D 00:00 a D 23:55 UTC ; cloture du jour D = cloture "
                        "de la bougie 1d ouverte en D, verifiee egale a celle de la barre 5 min "
                        "de 23:55"},
    "rv": {"definition": "somme des carres des rendements log 5 min des barres du jour UTC ; "
                         "rendement = ln(cloture / cloture de la barre ouverte 5 min avant), "
                         "jamais a travers un trou",
           "barres_par_jour": BARRES_PAR_JOUR, "part_manquante_max": PART_MANQUANTE_MAX,
           "jour_exclu": "manquantes > 10 % de 288 (>= 29) : pas de RV, ni regresseur, ni "
                         "cible, ni evaluation, ni decompte des 730 jours ; compte",
           "barres_plates": "barres a volume nul = presentes, comptees et rapportees"},
    "har": {"cible": f"moyenne des RV de t+1 a t+{HORIZON}",
            "regresseurs": "constante, RV_t, moyenne RV t-4..t, moyenne RV t-21..t",
            "fenetres": list(FENETRES_HAR), "estimation": "MCO",
            "fenetre_mco": f"RV des {FENETRE_MCO} derniers jours ayant une RV, t compris ; "
                           "lignes entierement dans la fenetre (704 au plus)",
            "avant_730_jours": "ecart-type 30 jours",
            "prevision_negative_ou_nulle": "ecart-type 30 jours ce jour-la, compte"},
    "reference": {"definition": "ecart-type d'echantillon des 30 derniers rendements log "
                                "journaliers (t compris), au carre : variance journaliere",
                  "fenetre": FENETRE_ECART_TYPE, "ddof": DDOF},
    "critere": {"perte": "QLIKE = RV/h - ln(RV/h) - 1, RV = moyenne des RV de t+1 a t+5",
                "jours_evalues": "HAR avec ses 730 jours de RV, cible complete (t+5 <= fin, "
                                 "aucun jour exclu) ; memes jours pour les deux modeles",
                "diebold_mariano": "information seulement : d = QLIKE HAR - QLIKE ecart-type, "
                                   "Newey-West Bartlett, retard int(4 (n/100)^(2/9)), p "
                                   "bilaterale normale"},
    "decision": {"regle": "si QLIKE moyenne HAR > QLIKE moyenne ecart-type 30 jours "
                          "(strictement) pour un actif, sigma de cet actif = ecart-type 30 "
                          "jours ; sinon HAR avec ses replis",
                 "diebold_mariano": "ne decide rien"},
    "causalite": {"coupures": list(COUPURES_CAUSALITE),
                  "exigence": "previsions recalculees avec les seules donnees <= coupure = "
                              "previsions completes ; sinon arret"},
    "non_fait": "ni comblement, ni plancher, ni troncature, ni autre modele, ni autre fenetre ; "
                "pas de PBO (signale a Jonas)",
}


def empreinte(regles: dict | None = None) -> str:
    texte = json.dumps(REGLES if regles is None else regles, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()[:16]
