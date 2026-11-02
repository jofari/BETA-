"""VC6 V2 : le gel. Rien ne tourne sur les vraies donnees si le preenregistrement manque, ou si les
regles, le texte du preenregistrement ou la spec ont change depuis."""

from __future__ import annotations

import hashlib
import pathlib

from beta import config
from beta.protocole import experiences
from beta.vc6_v2 import regles as R

TEXTE = config.RACINE / "VC6_V2" / "PREENREGISTREMENT.md"
SPEC = config.RACINE / "VC6_V2" / "spec_figee.md"


class GelError(RuntimeError):
    """Preenregistrement absent ou gel rompu : arret, aucun chiffre ne sort."""


def empreinte_fichier(chemin: pathlib.Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()[:16]


def verifier() -> dict:
    experiences.exiger(R.ID_EXP)
    lignes = [x for x in experiences._lignes() if x.get("id") == R.ID_EXP
              and x.get("statut") == "preenregistre"]
    if not lignes:
        raise GelError(f"{R.ID_EXP} n'est pas preenregistree (scripts/preenregistrer_vc6_v2.py)")
    pre = lignes[-1]
    attendu = {"empreinte": R.empreinte(), "empreinte_preenregistrement": empreinte_fichier(TEXTE),
               "empreinte_spec": empreinte_fichier(SPEC), "famille_compteur": "invest",
               "diagnostic": False}
    ecarts = {k: (pre.get(k), v) for k, v in attendu.items() if pre.get(k) != v}
    if ecarts:
        raise GelError(f"gel rompu depuis le preenregistrement : {ecarts}")
    return pre
