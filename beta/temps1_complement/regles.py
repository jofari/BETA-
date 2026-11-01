"""T1C : les regles GELEES du complement ETH et SOL. Ce module ne calcule rien.

Texte fige : VC6_V1/temps1_complement_eth_sol/PREENREGISTREMENT.md (etape C du prompt de Jonas du
01/11/2026, mot pour mot, et ses applications), dont l'empreinte est ecrite au registre. `REGLES`
porte les valeurs que le code lit ; son empreinte aussi. La campagne refuse de tourner si l'une ou
l'autre a change.
"""

from __future__ import annotations

import hashlib
import json

from beta.temps1_fiabilite import regles as RF

ID_EXP = "T1C"
ID_JUSTESSE, COMMIT_JUSTESSE = "T1J", "8afdbe7"
ID_FIABILITE, COMMIT_FIABILITE = "T1F", "590688e"
# Les modules reutilises : identiques, octet pour octet, a ceux de ces commits.
MODULES_JUSTESSE = ("__init__.py", "regles.py", "donnees.py", "detecteurs.py", "juge.py",
                    "mesures.py", "verdict.py", "campagne.py")
MODULES_FIABILITE = ("__init__.py", "regles.py", "nulls.py", "campagne.py")
EMPREINTE_REGLES_T1J = "c0959f429d9dcf8f"
EMPREINTE_REGLES_T1F = "77b7f85b49132d77"
EMPREINTE_DONNEES_T1J = "a3d6d80952500d57"
COPIE_T1J = "tests/donnees/t1j_a3d6d80952500d57.parquet"
SIGMA_SP_REF_T1J = 0.18257135761750884     # synthese de la mesure de T1J (24/10, 13:21 UTC)

DETECTEUR = "SMA200"
FENETRE_SMA = 200
FIN = "2026-10-31"                         # date de fin figee a l'etape A
ACTIFS = {
    "ETH": {"copie": "data/vc6_v1/sources_figees/ETH_perp_1d.parquet",
            "sha256": "19eec6a3c1882cfb484a54891c1dbf586ce519d50665b135d0c1153005cc172f",
            "serie": "perpetuel Binance USDT-M ETH, bougie 1d (lake BETA)"},
    "SOL": {"copie": "data/vc6_v1/sources_figees/SOL_perp_1d.parquet",
            "sha256": "58e10ba349297c52ccf30ffc5364811c4ddf95d819c6bdefab078217d9d57c42",
            "serie": "perpetuel Binance USDT-M SOL, bougie 1d (lake BETA)"},
}
SEUIL_P_JUSTESSE = 0.05

REGLES: dict = {
    "version": ID_EXP,
    "preenregistrement": "VC6_V1/temps1_complement_eth_sol/PREENREGISTREMENT.md",
    "prompt": "Jonas 2026-11-01, « On lance le backtest V1 de VC6 », etape C",
    "diagnostic": "aucun essai (meme configuration de detecteur, regle du 24/10) ; famille invest",
    "reutilise": {"t1j": {"commit": COMMIT_JUSTESSE, "modules": list(MODULES_JUSTESSE),
                          "regles": EMPREINTE_REGLES_T1J},
                  "t1f": {"commit": COMMIT_FIABILITE, "modules": list(MODULES_FIABILITE),
                          "regles": EMPREINTE_REGLES_T1F}},
    "donnees": {"actifs": ACTIFS, "fin": FIN,
                "convention": "cloture du jour D = cloture de la bougie 1d ouverte le jour D a "
                              "00:00 UTC (jour civil UTC clos, comme le BTC de T1J) ; 7 j / 7, "
                              "sans comblement",
                "sigma_sp_ref": {"valeur": SIGMA_SP_REF_T1J, "copie": COPIE_T1J,
                                 "empreinte": EMPREINTE_DONNEES_T1J}},
    "detecteur": f"{DETECTEUR} : bear si cloture < moyenne des {FENETRE_SMA} dernieres clotures "
                 "(jour compris), bull sinon (beta.temps1_justesse.detecteurs.sma)",
    "juge": "juge principal de T1J inchange (baisse de reference 20 %, sigma 2 ans par trimestre "
            "x rac(252), sigma_SP_ref constante de T1J) ; debut au premier trimestre precede de 2 "
            "ans de donnees (comme le BTC, decision 6 du 24/10) ; dernier cycle en cours exclu",
    "periode": "du premier trimestre juge a la fin figee ; periode mesuree M = [premier pivot, "
               "dernier pivot[ (clarification B de T1J)",
    "tests": {"test_1": "permutation des durees par etat, decide (T1F)",
              "test_1_bis": "decalage circulaire dans [90, N - 90], rapporte (T1F)",
              "test_2": "etat au pic et f_entree diagnostic, rapporte (T1F)",
              "tirages": {"n": RF.N_TIRAGES, "graine": RF.GRAINE,
                          "par": "actif et test"},
              "p": "p_justesse = part des tirages de justesse >= observee ; p_latence = part des "
                   "tirages de mediane f_entree <= observee",
              "lecture_d4": "beta.invest.nulls.verdict : p < 0,05 reel ; < 0,20 non concluant ; "
                            "sinon hasard"},
    "decision": {"retenu": f"p_justesse du test 1 < {SEUIL_P_JUSTESSE} : la poche suit la "
                           "SMA 200 de l'actif lui-meme",
                 "sinon": "l'actif suivra le regime de la SMA 200 du BTC",
                 "indecidable": "mesure impossible (aucun bear complet dans M, prechauffe "
                                "insuffisante, signal indefini, causalite ratee) : aucun verdict "
                                "pour cet actif, arret, la suite revient a Jonas (regle de T1J)",
                 "rapporte": "test 1 bis, p_latence, test 2 : ne decident rien"},
    "fiabilite": "p_latence du test 1 et sa lecture D4, test 1 bis a cote",
    "non_calcule": "variantes du juge de T1J (15 %, 25 %, sigma unique)",
    "compteur": "T1C journalisee diagnostic=True, famille invest ; aucun run dans RUNS.jsonl",
}


def empreinte(regles: dict | None = None) -> str:
    texte = json.dumps(REGLES if regles is None else regles, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()[:16]
