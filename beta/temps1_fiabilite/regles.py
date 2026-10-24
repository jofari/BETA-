"""T1F : les regles GELEES du diagnostic de fiabilite. Ce module ne calcule rien.

Texte fige : temps1_fiabilite/PREENREGISTREMENT.md (prompt de Jonas du 24/10 et ses
clarifications), dont l'empreinte est ecrite au registre. `REGLES` porte les valeurs que le code
lit ; son empreinte aussi. La campagne refuse de tourner si l'une ou l'autre a change.
"""

from __future__ import annotations

import hashlib
import json

ID_EXP = "T1F"
ID_JUSTESSE = "T1J"
COMMIT_JUSTESSE = "8afdbe7"
# Les modules de T1J reutilises : ils doivent etre identiques a ceux du commit 8afdbe7.
MODULES_JUSTESSE = ("__init__.py", "regles.py", "donnees.py", "detecteurs.py", "juge.py",
                    "mesures.py", "verdict.py", "campagne.py")
EMPREINTE_DONNEES_T1J = "a3d6d80952500d57"
EMPREINTE_REGLES_T1J = "c0959f429d9dcf8f"

DETECTEURS = ("SMA200", "MOM126", "C1_V1", "C1_V2")
CANDIDATS = ("C1_V1", "C1_V2")
ACTIFS = ("SPX", "NDX", "OR", "BTC")
TEMOIN = ("SPX", "NDX")
N_TIRAGES = 1000
GRAINE = 0
DECALAGE_MIN = 90                  # seances, dans [90, N - 90]
FENETRE_DIAGNOSTIC = 21            # test 2 : episodes bear commences plus de 21 seances avant
SEUIL_FIABLE, SEUIL_AGITATION = 0.05, 0.20

REGLES: dict = {
    "version": ID_EXP,
    "preenregistrement": "temps1_fiabilite/PREENREGISTREMENT.md",
    "diagnostic": "aucun essai, aucune configuration nouvelle ; famille invest",
    "reutilise": {"commit": COMMIT_JUSTESSE, "modules": list(MODULES_JUSTESSE),
                  "donnees": EMPREINTE_DONNEES_T1J, "regles": EMPREINTE_REGLES_T1J},
    "detecteurs": list(DETECTEURS), "candidats": list(CANDIDATS), "actifs": list(ACTIFS),
    "temoin": "moyenne S&P 500 et Nasdaq-100, tirage par tirage (clarification 3)",
    "plage": "periode mesuree de T1J, [premier pivot, dernier pivot[ (clarification 2)",
    "test_1": "suite des etats gardee, durees melangees entre episodes du meme etat "
              "(clarification 1)",
    "test_1_bis": f"decalage circulaire de k seances, k uniforme dans [{DECALAGE_MIN}, "
                  f"N - {DECALAGE_MIN}] (clarification 4)",
    "tirages": {"n": N_TIRAGES, "graine": GRAINE, "par": "couple detecteur x actif et test"},
    "mesures": "mediane f_entree (rates = 1), fausses alertes par an, justesse equilibree : "
               "beta.temps1_justesse.mesures.mesurer",
    "p": "p_latence = part des tirages de mediane f_entree <= observee ; p_justesse = part des "
         "tirages de justesse >= observee",
    "lecture_d4": "beta.invest.nulls.verdict : p < 0,05 reel ; < 0,20 non concluant ; sinon "
                  "hasard",
    "test_2": f"etat au pic en trois cas ; f_entree diagnostic en ignorant les episodes bear "
              f"commences plus de {FENETRE_DIAGNOSTIC} seances avant le pic (rate = 1)",
    "verdict": {"fiable": f"p_latence < {SEUIL_FIABLE} sur le temoin ET sur l'or (test 1)",
                "non_concluant": f"l'un des deux dans [{SEUIL_FIABLE}, {SEUIL_AGITATION}[ et "
                                 "aucun au-dessus",
                "agitation": f"l'un des deux >= {SEUIL_AGITATION}",
                "btc": "rapporte, ne valide rien seul", "t1j": "verdict de T1J inchange"},
}


def empreinte(regles: dict | None = None) -> str:
    texte = json.dumps(REGLES if regles is None else regles, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()[:16]
