"""Mesure les hypotheses mesurables sur les donnees deja presentes, et les clot au registre.

    & C:\\Users\\jofar\\venvs\\arit\\Scripts\\python.exe scripts/mesurer.py

R1 et R6 sont les deux seules du lot qui ne demandent aucune donnee nouvelle ni aucune
strategie a ecrire. Elles sont donc les deux premieres, comme prevu au chantier.

La correction de Benjamini-Hochberg est appliquee sur la famille DECLAREE au
preenregistrement (8 tests depuis l'amendement de R6), pas sur les deux qui ont tourne.
Corriger sur ce qui a effectivement tourne serait plus flatteur, et faux : les six autres
hypotheses ont ete formulees, elles comptent, qu'on les ait mesurees ou non.
"""

from __future__ import annotations

import json
import logging
import pathlib
import sys
from datetime import UTC, datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import numpy as np                                       # noqa: E402
import pandas as pd                                      # noqa: E402

from beta import config                                  # noqa: E402
from beta.protocole import experiences                   # noqa: E402
from beta.recherche import r1_trailing, r6_news_window   # noqa: E402
from beta.stats import multitest                         # noqa: E402

log = logging.getLogger("beta.mesurer")

MESURES = {"R1": r1_trailing, "R6": r6_news_window}
SORTIE = config.DATA / "mesures.json"
FDR = 0.10


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    resultats = {}
    for id_exp, module in MESURES.items():
        try:
            resultats[id_exp] = module.mesurer(clore=False)
        except experiences.ProtocoleError as exc:
            log.error("%s non mesurable : %s", id_exp, exc)
        except Exception as exc:                          # noqa: BLE001
            log.exception("%s a echoue : %s", id_exp, exc)

    famille = _famille(resultats)
    corrigee = multitest.benjamini_hochberg(famille, FDR) if not famille.empty \
        else famille
    if not corrigee.empty:
        log.info("Benjamini-Hochberg sur %d tests declares (FDR %.2f) :",
                 int(corrigee["m_declare"].iloc[0]), FDR)
        for ligne in corrigee.itertuples():
            log.info("  %s  p = %.4f  seuil BH = %.4f  -> %s", ligne.nom, ligne.p_brute,
                     ligne.seuil_BH, "survit" if ligne.signif_BH else "ne survit pas")

    for id_exp, resultat in resultats.items():
        verdict, motif = _apres_correction(resultat, corrigee)
        # Depuis A1 (20/08), N porte les MESURES. Une mesure qui ne passe pas par le
        # pipeline doit donc se journaliser elle-meme, sinon elle est gratuite au
        # compteur alors qu'elle a bel et bien consomme un essai. L'id est
        # deterministe : remesurer la meme hypothese le meme jour ne fabrique pas un
        # essai de plus.
        experiences.enregistrer_run(
            f"{id_exp}-mesure-{datetime.now(UTC).date().isoformat()}", id_exp,
            MESURES[id_exp].__name__.rsplit(".", 1)[-1], "", verdict)
        experiences.clore(id_exp, verdict, motif)
        print(f"\n{id_exp} : {verdict.upper()}\n  {motif}")

    _ecrire({"resultats": resultats,
             "benjamini_hochberg": corrigee.to_dict("records") if not corrigee.empty
             else []})
    print(f"\nCompteur d'essais cumules : {experiences.compteur()}")
    return 0


def _famille(resultats: dict) -> pd.DataFrame:
    """Les tests qui ont produit une p-value, avec la taille de famille DECLAREE.

    La table est completee par des lignes fictives a p = 1 pour atteindre la taille
    declaree : BH a besoin du m de la famille, pas du nombre de tests aboutis. Sans ce
    remplissage, ne mesurer que les deux hypotheses les plus prometteuses relacherait
    mecaniquement le seuil de toutes les autres.
    """
    lignes = []
    for id_exp, resultat in resultats.items():
        p = resultat.get("p_brute")
        if p is not None and np.isfinite(p):
            lignes.append({"nom": id_exp, "p_brute": float(p)})
    if not lignes:
        return pd.DataFrame()
    declare = max((experiences.etat().get(i, {}).get("famille_taille") or 0)
                  for i in resultats) or len(lignes)
    for i in range(len(lignes), int(declare)):
        lignes.append({"nom": f"(non mesure {i + 1})", "p_brute": 1.0})
    table = pd.DataFrame(lignes)
    table["m_declare"] = int(declare)
    return table


def _apres_correction(resultat: dict, corrigee: pd.DataFrame) -> tuple[str, str]:
    """Une hypothese confirmee avant BH ne l'est plus si elle ne survit pas a la famille."""
    verdict, motif = resultat["verdict"], resultat["motif"]
    if verdict != "confirmee" or corrigee.empty:
        return verdict, motif
    ligne = corrigee[corrigee["nom"] == resultat["id"]]
    if len(ligne) and not bool(ligne["signif_BH"].iloc[0]):
        return "indecidable", (motif + " — mais ne survit pas a Benjamini-Hochberg sur la "
                               f"famille de {int(ligne['m_declare'].iloc[0])} tests "
                               f"(seuil {float(ligne['seuil_BH'].iloc[0]):.4f})")
    return verdict, motif


def _ecrire(charge: dict) -> None:
    try:
        SORTIE.parent.mkdir(parents=True, exist_ok=True)
        SORTIE.write_text(json.dumps(charge, indent=2, ensure_ascii=False, default=str),
                          encoding="utf-8")
        log.info("detail ecrit dans %s", SORTIE)
    except OSError as exc:
        log.warning("detail non ecrit (%s)", exc)


if __name__ == "__main__":
    raise SystemExit(main())
