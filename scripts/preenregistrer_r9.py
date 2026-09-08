"""Préenregistrement de R9 — funding extrême → retournement contrarien.

L'hypothèse directionnelle du funding, issue de I1 (notée le 19/08) et des mesures
descriptives du 07/09. Le champ `deja_connu` déclare le snooping : les données 2019-2026
ont déjà servi à formuler l'hypothèse.
"""
from __future__ import annotations

import sys
import pathlib

RACINE = pathlib.Path("/root/BETA-")
sys.path.insert(0, str(RACINE))

from beta.protocole import experiences  # noqa: E402

HYPOTHESE = (
    "Le funding extrême précède un retournement de la tendance courte : un funding dans le "
    "décile bas de sa distribution glissante sur 90 jours (positionnement long dégonflé) est "
    "suivi d'un rebond haussier, un funding dans le décile haut (longs sur-leveragés) d'un "
    "retournement baissier. Mesuré en R moyen par trade, coûts déduits, sens contrarien, sur "
    "les 6 paires de l'univers en 4h."
)

METRIQUE = "R moyen par trade (triple barrière du moteur, take_profit_r=2.0, coûts déduits)"

REGLE = {
    "confirmee": "R moyen > 0, p survivant à Benjamini-Hochberg sur la famille, et les neuf "
                 "portes S1-S9 franchies",
    "infirmee": "R moyen <= 0, ou une porte de la batterie échoue",
    "indecidable": "moins de 30 signaux retenus après élimination des chevauchements",
}

DEJA_CONNU = (
    "I1 (notée le 19/08) posait déjà la question. Mesures DESCRIPTIVES du 07/09 sur les MÊMES "
    "données (donc ce préenregistrement est entaché de snooping partiel) : funding bottom 10 % "
    "→ +1,10 %/7j et funding top 10 % → −1,85 %/7j sur la dernière année, MAIS l'effet s'INVERSE "
    "sur 2019+ (régime-dépendant). R3 vient d'être mesurée : le carry funding est positif "
    "(11-15 %/an) mais ne bat pas le hold — le funding est un crowding, pas un edge autonome. "
    "Ce préenregistrement teste si, malgré la dépendance au régime déjà observée, la batterie "
    "S1-S9 confirme ou tue la version contrarienne. Issue attendue : infirmee."
)

entree = experiences.preenregistrer(
    "R9",
    HYPOTHESE,
    METRIQUE,
    REGLE,
    split_autorise="train",
    issue_attendue="infirmee",
    famille_taille=1,
    deja_connu=DEJA_CONNU,
)

print(f"R9 préenregistrée — essai cumulé n° {entree['n_essais_cumules']}")
print(f"compteur courant : {experiences.compteur()}")
