"""VC6 V1, Temps 2 : les regles GELEES. Ce module ne calcule rien.

Texte fige : VC6_V1/spec_figee.md (spec et addendums jusqu'au 02/11/2026) et
VC6_V1/temps2/PREENREGISTREMENT.md (prompt de Jonas mot pour mot et applications). `REGLES` porte
les valeurs que le code lit ; son empreinte est ecrite au registre. La campagne refuse de tourner
si l'empreinte a change.
"""

from __future__ import annotations

import hashlib
import json

ID_EXP = "VC6_V1_TEMPS2"
FIN = "2026-10-31"
DEBUT_PRINCIPAL = "2021-06-01"
DEBUT_ROBUSTESSE = "2014-01-01"
DOSSIER_COPIES = "data/vc6_v1/sources_figees"
SHA256 = {
    "BTC_perp_5m": "42e62509f051ece9fd86f2a19848e36d53b88b0661243b9aae91320e4caf3618",
    "ETH_perp_5m": "5e1a62bff2d7a21e2971e321d03e789d074a814c3f329c327e9af7c2ce7a592f",
    "SOL_perp_5m": "0771ad9ed20d60bc1b5e17d16e384fda03f2b2ec447656e938c182923f4fe75d",
    "BTC_funding": "bd970babd9c36149e0c6b9e295be90bd01d4cb4cc650be5a95ea0484fe0bc006",
    "ETH_funding": "335f28b5d669c78c354aed3a3fd0334eb86d07dff889ca3d997bc3d6b94413a6",
    "SOL_funding": "4c17b7a34a5e6a4d0730c399a2d5dc757a8b56aa461a07663618d0089bfc6757",
    "XAU_SPOT_1d": "4ec3b0f04a72f838db89177618096078c8184b2feed25497997aa718d38be542",
    "URTH_1d": "266aec60912cf63e2cf6ef669f6d1a5849f6be8a0f66a084b1a9cfe3589bbdf4",
    "BTC_bitstamp_1d": "5cd3f419ce33e215201e9d1e8f40cba458baba9645a38df26b8403c504f435dd",
}

POCHES = ("BTC", "ETH", "SOL")
POIDS = {"BTC": 0.50, "ETH": 0.25, "SOL": 0.25}
SMA = 200
CLIP_BAS, CLIP_HAUT = 0.2, 2.0
FUNDING_SEUIL = 0.20
MARGE = 0.005
K_SIGMA_LIQ = 3.0
JOURS_AN = 365
RAMPE = 5
BANDE = 0.10
FRAIS_PB = 10.0
POCHE_BAISSIERE = 0.25
FUNDING_AVANT_PERP = 0.0001            # robustesse : par reglement de 8 h, 3 par jour
FUNDING_AVANT_PERP_JUSQU_A = "2019-09-10"   # jours < cette date
REGLEMENTS_PAR_JOUR_AVANT_PERP = 3
FENETRE_ECART_TYPE = 30

B_NULLS = 1000
GRAINE = 0
M_DECALAGE = 90
SEUIL_P = 0.05
SEUIL_PBO = 0.20
SEUIL_GRAND_BEAR = 0.30
ALLER_RETOUR_J = 30

VARIANTES = {
    "fixe": {"nom": "Variante expo fixe", "sizing": "fixe", "cible": None,
             "baissiere": {"BTC": 0.25}, "essai": True},
    "vol": {"nom": "Variante expo vol", "sizing": "vol", "cible": 0.25,
            "baissiere": {"BTC": 0.25}, "essai": True},
    "annexe40": {"nom": "Test annexe – cible 40 %", "sizing": "vol", "cible": 0.40,
                 "baissiere": {"BTC": 0.25}, "essai": True, "eligible": False},
    "or": {"nom": "Variante poche or", "sizing": "meilleure", "cible": None,
           "baissiere": {"XAU": 0.25}, "essai": True},
    "mixte": {"nom": "Variante poche mixte", "sizing": "meilleure", "cible": None,
              "baissiere": {"BTC": 0.125, "XAU": 0.125}, "essai": True},
}

REGLES: dict = {
    "version": ID_EXP,
    "spec": "VC6_V1/spec_figee.md (spec + addendums jusqu'au 02/11/2026)",
    "preenregistrement": "VC6_V1/temps2/PREENREGISTREMENT.md",
    "fin": FIN, "debut_principal": DEBUT_PRINCIPAL, "debut_robustesse": DEBUT_ROBUSTESSE,
    "sha256": SHA256, "poches": list(POCHES), "poids": POIDS, "sma": SMA,
    "clip": [CLIP_BAS, CLIP_HAUT], "funding_seuil": FUNDING_SEUIL, "marge": MARGE,
    "k_sigma_liquidation": K_SIGMA_LIQ, "jours_an": JOURS_AN, "rampe": RAMPE, "bande": BANDE,
    "frais_pb": FRAIS_PB, "poche_baissiere": POCHE_BAISSIERE,
    "funding_avant_perp": {"taux": FUNDING_AVANT_PERP, "jusqu_a": FUNDING_AVANT_PERP_JUSQU_A,
                           "par_jour": REGLEMENTS_PAR_JOUR_AVANT_PERP},
    "sigma": {"principal": "HAR apres replis (beta.controle_har), sqrt(365 h)",
              "robustesse": f"ecart-type {FENETRE_ECART_TYPE} jours Bitstamp, sqrt(365)"},
    "or": "XAU_SPOT (Dukascopy), week-end et jours sans valeur : dernier cours, rendement nul",
    "etf_monde": "URTH",
    "nulls": {"signal": "mode", "b": B_NULLS, "graine": GRAINE, "m": M_DECALAGE,
              "metrique": "ulcer", "seuil": SEUIL_P},
    "pbo": {"seuil": SEUIL_PBO, "effet": "rapportee sans effet (addendum du 02/11)"},
    "variantes": VARIANTES,
    "rapport": {"grand_bear": SEUIL_GRAND_BEAR, "aller_retour_j": ALLER_RETOUR_J},
}


def empreinte(regles: dict | None = None) -> str:
    texte = json.dumps(REGLES if regles is None else regles, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()[:16]
