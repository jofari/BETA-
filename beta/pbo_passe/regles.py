"""PBOR : les regles GELEES de la PBO du passe. Ce module ne calcule rien.

Texte fige : pbo_passe/PREENREGISTREMENT.md (reponses de Jonas du 26/10/2026), dont l'empreinte
est ecrite au registre. `REGLES` porte les valeurs que le code lit ; son empreinte aussi. La
campagne refuse de tourner si l'une ou l'autre a change.
"""

from __future__ import annotations

import hashlib
import json

ID_EXP = "PBOR"

# Methode : celle de la porte S10 (beta.stats.pbo), donc celle de PBOC.
S = 16
PPA = 252.0
SEUIL = 0.20                         # batterie.SEUIL_PBO, verifie a l'execution

# Les 3 lots de cribler() de septembre : memes date et N figes, S7 sur exactement ces runs.
LOTS: dict[str, dict] = {
    "L1": {"titre": "lot R10 du 08/09/2026", "lance_le": "2026-09-08",
           "n_essais_cumules": 45,
           "runs": {"r10_conjonction": "c8a374a40a87", "r10_disjonction": "274eb02a15ee"}},
    "L2": {"titre": "lot R8 du 19/09/2026", "lance_le": "2026-09-19",
           "n_essais_cumules": 57,
           "runs": {"liquidity_ny_stop_050": "36ed58e66266",
                    "liquidity_ny_stop_100": "96d03113b579",
                    "liquidity_ny_stop_150": "52423a324274"}},
    "L3": {"titre": "lot de 8 candidates du 19/09/2026", "lance_le": "2026-09-19",
           "n_essais_cumules": 62,
           "runs": {"auto_r7_01": "2ce411b82067", "auto_r7_03": "f57f95588500",
                    "mean_reversion_z": "7eb7f9c2cb17", "r10_conjonction": "f76121140b7c",
                    "r10_disjonction": "21acf3928232",
                    "r11_credit_contrarian": "b3b0374c238e",
                    "r4_fear_greed_contrarian": "f2217235b2ed",
                    "r9_funding_contrarian": "58a1b966537e"}},
}

# sha256 (16 premiers caracteres) de data/runs/<run>/trades.parquet, releves le 26/10 avant
# tout calcul. Un fichier different arrete la campagne.
EMPREINTES_TRADES = {
    "c8a374a40a87": "bfe6ad1c82de9520", "274eb02a15ee": "ff8b4890f21c7a22",
    "36ed58e66266": "a2ab6626f32aaabd", "96d03113b579": "144faabf5027ab56",
    "52423a324274": "0f5287d67d2da71f", "2ce411b82067": "152663f1a9fa115e",
    "f57f95588500": "32fb0337a5a13aac", "7eb7f9c2cb17": "0666e738787899f4",
    "f76121140b7c": "c29c4ba5988b3ef7", "21acf3928232": "940cae2b3fe92d4c",
    "b3b0374c238e": "2280dcd261ff6c1b", "f2217235b2ed": "a92dc494cd36578e",
    "58a1b966537e": "27c8aac085db00bf",
}

# Les 6 variantes de la voie C du 22/09, dans l'ordre ou voie_c_voltarget les construit.
FIN_VC = "2026-09-05"
FIN_TRAIN_VC = "2024-06-30"
VARIANTES_VC = ("vt 25% / 30j / quotidien", "vt 45% / 30j / quotidien",
                "vt 70% / 30j / quotidien", "vt 25% / 60j / quotidien",
                "vt 45% / 60j / quotidien", "vt 70% / 60j / quotidien")

REGLES: dict = {
    "version": ID_EXP,
    "preenregistrement": "pbo_passe/PREENREGISTREMENT.md",
    "diagnostic": "aucun essai ajoute au compteur ; rapport seul, aucun verdict modifie",
    "methode": "porte S10 : beta.stats.pbo.calculer (CSCV de beta.stats.cscv)",
    "blocs": {"s": S, "jours": "les plus anciens retires pour T multiple de S"},
    "metrique": f"Sharpe = moyenne / ecart-type (ddof = 1) * sqrt({PPA:g}), rf = 0",
    "seuil": f"PBO < {SEUIL:g} : la porte S10 est franchie",
    "doublons": "rendements identiques bit a bit : le premier dans l'ordre des colonnes",
    "incalculable": "moins d'un jour par bloc, moins de 2 configurations distinctes, ou "
                    "ecart-type nul sur une moitie : S10 non executee, aucun chiffre",
    "lots": {
        "liste": {k: {"lance_le": v["lance_le"], "n_essais_cumules": v["n_essais_cumules"],
                      "runs": v["runs"]} for k, v in LOTS.items()},
        "donnees": "data/runs/<run>/trades.parquet tel qu'enregistre, empreintes figees",
        "rendement": "somme des R des trades clotures chaque jour UTC (0 sans cloture), "
                     "colonnes dans l'ordre des noms",
        "periode": "du premier au dernier jour de cloture du lot",
        "controle": "chaque verdict.json : meme candidate, meme date, meme N, univers de S7 "
                    "de la taille du lot",
    },
    "voie_c": {
        "code": "beta/strategies/voie_c_voltarget.py : preparer(fin) puis "
                "variantes_selection(), le chemin meme de main()",
        "variantes": list(VARIANTES_VC),
        "rendement": "r_net quotidien (5 bps taker, funding)",
        "periode": f"du premier jour ou les 6 variantes existent au {FIN_VC}",
        "retenue": f"rapportee : meilleur Sharpe net du train (jusqu'au {FIN_TRAIN_VC}), "
                   "la regle de main()",
    },
    "rapport": "pbo_passe/RAPPORT_PBO.md et RESUME_DISCORD.md, ecrits par le programme",
}


def empreinte(regles: dict | None = None) -> str:
    texte = json.dumps(REGLES if regles is None else regles, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()[:16]
