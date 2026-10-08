"""Préenregistrement de R11 — le stress crédit précède-t-il un rebond du crypto ?

Mesure descriptive du 10/09 : IC de Spearman +0,44 (HY) / +0,46 (IG) du NIVEAU du spread de
crédit sur le retour BTC à 30 jours — de loin le plus fort signal trouvé. Hypothèse :
après un épisode de stress crédit, le risque rebondit. Sens contrarien, LONG seulement
(la relation n'est pas symétrique : un spread serré a coïncidé avec des bull markets).
"""
from __future__ import annotations

import sys
import pathlib

RACINE = pathlib.Path("/root/BETA-")
sys.path.insert(0, str(RACINE))

from beta.protocole import experiences  # noqa: E402

HYPOTHESE = (
    "Un spread de crédit high yield élevé (stress, HY OAS dans sa queue haute sur un an) "
    "précède un rebond du crypto : LONG sur les 6 paires quand le spread est en régime de "
    "stress. Sens contrarien, LONG uniquement — la relation n'est pas symétrique (un spread "
    "serré a coïncidé avec des bull markets, donc pas de short)."
)

METRIQUE = "R moyen par trade (triple barrière du moteur), LONG quand le HY OAS est en stress"

REGLE = {
    "confirmee": "R moyen > 0, p survivant à Benjamini-Hochberg sur la famille, et les neuf "
                 "portes S1-S9 franchies",
    "infirmee": "R moyen <= 0, ou une porte de la batterie échoue",
    "indecidable": "moins de 30 signaux retenus après élimination des chevauchements",
}

DEJA_CONNU = (
    "Mesure DESCRIPTIVE du 10/09 (donc snooping) : IC +0,44 (HY) / +0,46 (IG) du niveau du "
    "spread crédit sur le retour BTC 30j. Le signal est LENT et autocorrélé — il est plus un "
    "détecteur de RÉGIME qu'un signal directionnel. Le risque est un n faible (le stress crédit "
    "est rare) ou un effet porté par quelques épisodes (2020, 2022, 2023). Issue attendue : "
    "indecidable, ou infirmee par le walk-forward."
)

entree = experiences.preenregistrer(
    "R11",
    HYPOTHESE,
    METRIQUE,
    REGLE,
    split_autorise="train",
    issue_attendue="indecidable",
    famille_taille=1,
    deja_connu=DEJA_CONNU,
)

print(f"R11 préenregistrée — essai cumulé n° {entree['n_essais_cumules']}")
print(f"compteur courant : {experiences.compteur()}")
