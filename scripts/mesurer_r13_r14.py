"""Mesure R13 (or 5m) et R14 (Nasdaq-100 1h) et les clot au registre — verdict par le programme.

    /root/venvs/arit/bin/python scripts/mesurer_r13_r14.py

Chaque lot (3 variantes de stop) passe par `pipeline.cribler` : BH sur la famille de 3, S7,
S9 et S10 calcules sur le lot entier. Le verdict de l'EXPERIENCE applique la regle ecrite au
preenregistrement (scripts/preenregistrer_r13_r14.py), sans jugement ajoute.

La periode est figee au preenregistrement et passee au Run (`debut`, `fin` bornee par
holdout.borner_train) : le rattrapage de l'or vers 2003 ne l'elargit pas en silence. Les
sources (Dukascopy, Yahoo) peuvent reecrire le passe : l'empreinte de la serie lue est
journalisee dans la cloture, pour qu'une remesure dise si elle a lu la meme chose.
"""
from __future__ import annotations

import hashlib
import json
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta.lake import lecture                    # noqa: E402
from beta.moteur import pipeline, registre       # noqa: E402
from beta.protocole import experiences, holdout  # noqa: E402

log = logging.getLogger("beta.mesurer_r13_r14")

LOTS = {
    "R13": {"actif": "XAU_SPOT", "timeframe": "5m", "debut": "2023-06-21",
            "horizon": 72, "candidates": ["r13_ny_or_stop_050", "r13_ny_or_stop_100",
                                          "r13_ny_or_stop_150"]},
    "R14": {"actif": "NDX", "timeframe": "1h", "debut": "2023-11-22",
            "horizon": 6, "candidates": ["r14_ny_ndx1h_stop_050", "r14_ny_ndx1h_stop_100",
                                         "r14_ny_ndx1h_stop_150"]},
}
TAKE_PROFIT_R = 3.0


def empreinte(actif: str, timeframe: str, debut: str) -> dict:
    df = lecture.load(actif, timeframe, debut=debut, fin=holdout.borner_train(None))
    brut = df[["date", "open", "high", "low", "close"]].to_csv(index=False).encode()
    return {"sha256": hashlib.sha256(brut).hexdigest()[:16], "bougies": len(df),
            "premiere": str(df["date"].min()), "derniere": str(df["date"].max())}


def verdict_experience(issues: list[str]) -> str:
    """La regle du preenregistrement, telle quelle."""
    if "confirmee" in issues:
        return "confirmee"
    if "indecidable" in issues:
        return "indecidable"
    return "infirmee"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    disponibles = registre.toutes()
    sortie = {}
    for id_exp, lot in LOTS.items():
        etat = experiences.etat().get(id_exp, {})
        if etat.get("statut") == "clos":
            log.error("%s deja close : on ne remesure pas sous le meme id", id_exp)
            return 1
        donnees = empreinte(lot["actif"], lot["timeframe"], lot["debut"])
        candidates = {n: disponibles[n] for n in lot["candidates"]}
        verdicts = pipeline.cribler(candidates, paires=(lot["actif"],),
                                    timeframe=lot["timeframe"], debut=lot["debut"],
                                    take_profit_r=TAKE_PROFIT_R,
                                    horizon_bougies=lot["horizon"], id_experience=id_exp)
        if len(verdicts) != len(candidates):
            log.error("%s : %d verdicts sur %d candidates — experience NON close", id_exp,
                      len(verdicts), len(candidates))
            return 1
        lignes = {}
        for nom, v in sorted(verdicts.items()):
            m = v.metriques
            lignes[nom] = {"run": v.run.id, "issue": v.issue, "n": m.get("n"),
                           "r_moyen": m.get("r_moyen"), "mde_r": m.get("mde_r"),
                           "win_rate": m.get("win_rate"),
                           "profit_factor": m.get("profit_factor"),
                           "portes_echouees": v.portes_echouees,
                           "portes_non_executees": v.portes_non_executees,
                           "reserves": list(v.reserves)}
        verdict = verdict_experience([x["issue"] for x in lignes.values()])
        resultat = " ; ".join(
            f"{nom} : {x['issue']}, n={x['n']}, R moyen={x['r_moyen']}, MDE={x['mde_r']}, "
            f"portes echouees={len(x['portes_echouees'])}, non executees="
            f"{len(x['portes_non_executees'])}" for nom, x in lignes.items())
        experiences.clore(id_exp, verdict, resultat, lot=lot["candidates"],
                          runs=[x["run"] for x in lignes.values()], donnees=donnees,
                          detail=lignes)
        sortie[id_exp] = {"verdict": verdict, "donnees": donnees, "candidates": lignes}
        print(f"\n{id_exp} : {verdict.upper()}")
        for nom, x in lignes.items():
            print(f"  {nom:<24} {x['issue']:<12} n={x['n']}  R moyen={x['r_moyen']}  "
                  f"MDE={x['mde_r']}  echouees={x['portes_echouees']}  "
                  f"non executees={x['portes_non_executees']}")
    print(json.dumps(sortie, ensure_ascii=False, default=str, indent=1))
    print(f"\ncompteur trading : {experiences.compteur()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
