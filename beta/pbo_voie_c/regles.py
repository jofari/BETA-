"""PBOC : les regles GELEES de la PBO de la voie C. Ce module ne calcule rien.

Texte fige : pbo_voie_c/PREENREGISTREMENT.md (prompt de Jonas du 25/10, ses reponses du 25/10
21:16 et du 26/10), dont l'empreinte est ecrite au registre. `REGLES` porte les valeurs que le
code lit ; son empreinte aussi. La campagne refuse de tourner si l'une ou l'autre a change.
"""

from __future__ import annotations

import hashlib
import json

ID_EXP = "PBOC"

# Fenetre d'evaluation : moteur parti du 12/06/2021 comme la grille, 8 premiers jours retires.
DEBUT_MOTEUR = "2021-06-12"
DEBUT = "2021-06-20"
FIN = "2026-09-05"
N_JOURS = 1904
S = 16
JOURS_PAR_BLOC = 119
PPA = 252.0

# Dedoublonnage, option b : un representant par groupe ou seule la cible change.
CIBLE_GARDEE = 0.20
N_GRILLE = 5760
N_GROUPES = 960

# Controles : grilles N(0, 1) iid de N_JOURS x N_GROUPES, numpy default_rng(graine).
N_CONTROLE = 960
GRAINE_POSITIF = 0
SR_POSITIF = 3.0
SEUIL_POSITIF = 0.10                 # PBO <= 10 % sur la graine 0
SR_INFORMATIF = 1.0                  # rapporte, ne decide rien
GRAINES_NEGATIF = (1001, 1100)       # bornes incluses : 100 graines neuves
BORNES_NEGATIF = (0.45, 0.55)        # moyenne dans [45 % ; 55 %], bornes incluses
GRAINE_NEGATIF_RAPPORTEE = 0         # rapportee, ne decide rien

SEUIL_VOIE_C = 0.20                  # PBO < 20 % -> reste candidate

REGLES: dict = {
    "version": ID_EXP,
    "preenregistrement": "pbo_voie_c/PREENREGISTREMENT.md",
    "diagnostic": "aucun essai ajoute au compteur ; famille invest",
    "methode": "CSCV, Bailey, Borwein, Lopez de Prado et Zhu (2017), beta.stats.cscv",
    "donnees": "rendements quotidiens nets de la grille voie_c_optim (evaluer, moteur "
               f"derouler_bande), moteur parti du {DEBUT_MOTEUR}",
    "fenetre": {"debut": DEBUT, "fin": FIN, "n_jours": N_JOURS},
    "blocs": {"s": S, "jours_par_bloc": JOURS_PAR_BLOC, "combinaisons": 12870},
    "metrique": f"Sharpe = moyenne / ecart-type (ddof = 1) * sqrt({PPA:g}), rf = 0",
    "egalites": "Sharpe IS egal : premiere colonne dans l'ordre de la grille ; Sharpe OOS "
                "egal : rang moyen",
    "dedoublonnage": {
        "groupes": f"option b : configurations qui ne different que par la cible, une par "
                   f"groupe ({N_GROUPES} groupes sur {N_GRILLE})",
        "cible_gardee": CIBLE_GARDEE,
        "doublons_exacts": "puis, parmi les representants, rendements identiques bit a bit sur "
                           "la fenetre d'evaluation : la premiere dans l'ordre de la grille",
    },
    "controles": {
        "loi": "N(0, 1) independants, numpy.random.default_rng(graine).standard_normal",
        "taille": [N_JOURS, N_CONTROLE],
        "positif": {"graine": GRAINE_POSITIF, "avantage": f"Sharpe annualise {SR_POSITIF:g} "
                    f"(sqrt(252)) ajoute chaque jour a la colonne 0",
                    "reussi": f"PBO <= {SEUIL_POSITIF:g}",
                    "informatif": f"meme grille, avantage Sharpe {SR_INFORMATIF:g}, ne decide "
                                  "rien"},
        "negatif": {"graines": list(GRAINES_NEGATIF),
                    "reussi": f"moyenne des PBO dans [{BORNES_NEGATIF[0]:g} ; "
                              f"{BORNES_NEGATIF[1]:g}]",
                    "rapporte": f"graine {GRAINE_NEGATIF_RAPPORTEE} seule, ne decide rien"},
        "echec": "un controle rate : arret avant la voie C, aucune donnee de la voie C lue",
    },
    "verdict": {"candidate": f"PBO < {SEUIL_VOIE_C:g} : la voie C reste candidate",
                "surajustee": f"PBO >= {SEUIL_VOIE_C:g} : la voie C est marquee surajustee "
                              "dans DECISIONS.md"},
}


def empreinte(regles: dict | None = None) -> str:
    texte = json.dumps(REGLES if regles is None else regles, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()[:16]
