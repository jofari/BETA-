"""VC6 V2 : les regles GELEES. Ce module ne calcule rien.

Texte fige : VC6_V2/spec_figee.md (spec de Jonas du 02/11/2026 mot pour mot, empreintes des copies)
et VC6_V2/PREENREGISTREMENT.md (comment le code lit la spec). `REGLES` porte les valeurs que le code
lit ; son empreinte est ecrite au registre, avec celles des deux textes. Les valeurs reprises de la
V1 sont recopiees ici (un test verifie qu'elles sont egales a celles de `beta.vc6.regles`).
"""

from __future__ import annotations

import hashlib
import json

ID_EXP = "VC6_V2"
FIN = "2026-10-31"
DEBUT_PRINCIPAL = "2021-06-01"
DEBUT_ROBUSTESSE = "2014-01-01"
SHA256 = {
    "BTC_perp_5m": "42e62509f051ece9fd86f2a19848e36d53b88b0661243b9aae91320e4caf3618",
    "ETH_perp_5m": "5e1a62bff2d7a21e2971e321d03e789d074a814c3f329c327e9af7c2ce7a592f",
    "SOL_perp_5m": "0771ad9ed20d60bc1b5e17d16e384fda03f2b2ec447656e938c182923f4fe75d",
    "BTC_funding": "bd970babd9c36149e0c6b9e295be90bd01d4cb4cc650be5a95ea0484fe0bc006",
    "ETH_funding": "335f28b5d669c78c354aed3a3fd0334eb86d07dff889ca3d997bc3d6b94413a6",
    "SOL_funding": "4c17b7a34a5e6a4d0730c399a2d5dc757a8b56aa461a07663618d0089bfc6757",
    "BTC_bitstamp_1d": "5cd3f419ce33e215201e9d1e8f40cba458baba9645a38df26b8403c504f435dd",
    "URTH_1d": "266aec60912cf63e2cf6ef669f6d1a5849f6be8a0f66a084b1a9cfe3589bbdf4",
}

POCHES = ("BTC", "ETH", "SOL")
POIDS = {"BTC": 0.50, "ETH": 0.25, "SOL": 0.25}
SMA = 200
CIBLE = 0.25
CLIP_BAS, CLIP_HAUT = 0.2, 2.0
CLIP_BAISSIERE = (0.2, 1.0)            # E_BTC de la poche baissiere : pas de levier
FUNDING_SEUIL = 0.20
MARGE = 0.005
K_SIGMA_LIQ = 3.0
JOURS_AN = 365
RAMPE = 5
BANDE = 0.10
FRAIS_PB = 10.0
POCHE_BAISSIERE = 0.25
FUNDING_AVANT_PERP = 0.0001
FUNDING_AVANT_PERP_JUSQU_A = "2019-09-10"
REGLEMENTS_PAR_JOUR_AVANT_PERP = 3
FENETRE_ECART_TYPE = 30

B_NULLS = 1000
GRAINE = 0
M_DECALAGE = 90
BLOC_SEGMENTS = 63
SEUIL_P = 0.05
SEUIL_PBO = 0.20

ESSAIS = {
    "har_sans_regime": {
        "nom": "V2 – HAR sans régime", "regime": False, "baissiere": {},
        "baissiere_vol": False, "null": "positions"},
    "poche_baissiere_har": {
        "nom": "V2 – poche baissière sous HAR", "regime": True,
        "baissiere": {"BTC": POCHE_BAISSIERE}, "baissiere_vol": True, "null": "mode"},
}
REFERENCE_V1 = {"cle": "vol", "nom": "Variante expo vol"}

REGLES: dict = {
    "version": ID_EXP,
    "spec": "VC6_V2/spec_figee.md (spec de Jonas du 02/11/2026, mot pour mot)",
    "preenregistrement": "VC6_V2/PREENREGISTREMENT.md",
    "fin": FIN, "debut_principal": DEBUT_PRINCIPAL, "debut_robustesse": DEBUT_ROBUSTESSE,
    "sha256": SHA256, "poches": list(POCHES), "poids": POIDS, "sma": SMA, "cible": CIBLE,
    "clip": [CLIP_BAS, CLIP_HAUT], "clip_baissiere": list(CLIP_BAISSIERE),
    "funding_seuil": FUNDING_SEUIL, "marge": MARGE, "k_sigma_liquidation": K_SIGMA_LIQ,
    "jours_an": JOURS_AN, "rampe": RAMPE, "bande": BANDE, "frais_pb": FRAIS_PB,
    "poche_baissiere": POCHE_BAISSIERE,
    "funding_avant_perp": {"taux": FUNDING_AVANT_PERP, "jusqu_a": FUNDING_AVANT_PERP_JUSQU_A,
                           "par_jour": REGLEMENTS_PAR_JOUR_AVANT_PERP},
    "sigma": {"principal": "HAR apres replis (beta.controle_har), sqrt(365 h)",
              "robustesse": f"ecart-type {FENETRE_ECART_TYPE} jours Bitstamp, sqrt(365)"},
    "etf_monde": "URTH",
    "nulls": {"b": B_NULLS, "graine": GRAINE, "m": M_DECALAGE, "bloc": BLOC_SEGMENTS,
              "metrique": "ulcer", "seuil": SEUIL_P,
              "har_sans_regime": "positions x_i(t) tenues, decalees (circulaire) ou blocs de 63 "
                                 "jours permutes ; rendement net recalcule (frais, financement)",
              "poche_baissiere_har": "null de la V1 : serie du mode, decalage circulaire et "
                                     "melange de segments, moteur complet a chaque tirage",
              "p": "beta.invest.nulls.p_value : (1 + #{Ulcer nul <= observe}) / (1 + B) ; "
                   "p retenue = max (D4)"},
    "pbo": {"seuil": SEUIL_PBO, "effet": "rapportee sans effet (addendum V1 du 02/11, repris)"},
    "essais": ESSAIS, "reference_v1": REFERENCE_V1,
    "decision": {"1": "utile = Ulcer < temoin et p retenue < 0,05",
                 "2": "un seul utile -> lui ; les deux -> plus haut ratio rendement annualise / "
                      "Ulcer ; aucun -> VC6 rejetee, aucune configuration retenue",
                 "3": "rapporte sans effet : poche baissiere sous HAR contre Variante expo vol V1"},
}


def empreinte(regles: dict | None = None) -> str:
    texte = json.dumps(REGLES if regles is None else regles, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()[:16]
