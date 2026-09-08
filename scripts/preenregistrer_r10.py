"""Préenregistrement de R10 — la combinaison funding x F&G bat-elle chaque condition seule ?

R9 (funding seul) et R4 (F&G seul) sont deja INFIRMEES. Question naturelle : deux conditions
mortes separement deviennent-elles vivantes combinees ? Deux combinaisons, une famille.
"""
from __future__ import annotations

import sys
import pathlib

RACINE = pathlib.Path("/root/BETA-")
sys.path.insert(0, str(RACINE))

from beta.protocole import experiences  # noqa: E402

HYPOTHESE = (
    "La combinaison de deux conditions contrariennes — funding extrême ET/OU Fear & Greed "
    "extrême — produit un R moyen strictement positif, supérieur à chacune prise isolément "
    "(R9 et R4, déjà infirmées). Deux variantes : la CONJONCTION (les deux extrêmes alignés, "
    "signal rare et fort) et la DISJONCTION (l'un ou l'autre, signal fréquent et faible)."
)

METRIQUE = "R moyen par trade (triple barrière du moteur), sens contrarien à la combinaison"

REGLE = {
    "confirmee": "R moyen > 0, p survivant à Benjamini-Hochberg sur la famille, et les neuf "
                 "portes S1-S9 franchies",
    "infirmee": "R moyen <= 0, ou une porte de la batterie échoue",
    "indecidable": "moins de 30 signaux retenus après élimination des chevauchements",
}

DEJA_CONNU = (
    "R9 (funding contrarien seul) et R4 (F&G contrarien seul) sont INFIRMEES : R moyen "
    "-0.073 et -0.086, 7 portes echouees chacune. Mesures descriptives du 07/09 : les deux "
    "signaux sont des crowding/sentiment contrariens faibles et regime-dependants. Ce "
    "preenregistrement teste si leur combinaison reveille un edge que chacun seul n'a pas. "
    "Issue attendue : infirmee."
)

entree = experiences.preenregistrer(
    "R10",
    HYPOTHESE,
    METRIQUE,
    REGLE,
    split_autorise="train",
    issue_attendue="infirmee",
    famille_taille=2,
    deja_connu=DEJA_CONNU,
)

print(f"R10 préenregistrée — essai cumulé n° {entree['n_essais_cumules']}")
print(f"compteur courant : {experiences.compteur()}")
