"""VC6 V1, Temps 2 : correctif du 02/11/2026 (Jonas), mesures de rapport seulement.

    /root/venvs/beta/bin/python scripts/vc6_v1_correctif.py

Relit les resultats du run du 02/11 (data/vc6_temps2/resultats.pkl), verifie qu'ils sont bien ceux
que rendent les copies figees et le moteur V1 (re-simulation, rendements identiques au bit pres),
recalcule les deux mesures corrigees (`beta.vc6.correctif`) et ecrit
VC6_V1/rapport_temps2_corrige.md. L'original VC6_V1/rapport_temps2.md n'est pas touche. Aucun
essai, aucune regle, aucun compteur ne bouge. Arret sans rien ecrire si une verification echoue.
"""

from __future__ import annotations

import logging
import pathlib
import pickle
import subprocess
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta import config  # noqa: E402
from beta.invest import metriques  # noqa: E402
from beta.vc6 import campagne, correctif, rapport  # noqa: E402
from beta.vc6 import moteur as mt  # noqa: E402
from beta.vc6 import regles as R  # noqa: E402

log = logging.getLogger("beta.vc6_v1_correctif")
PKL = campagne.DOSSIER / "resultats.pkl"
DATE = "02/11/2026"
VARIANTES = ("fixe", "vol", "annexe40", "or", "mixte")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=config.RACINE, capture_output=True,
                          text=True).stdout.strip()


def verifier(res: dict, ent: mt.Entrees, ent_r: mt.Entrees) -> dict:
    """Re-simule les 5 essais, la robustesse et leurs temoins : identiques au bit pres."""
    meilleure = res["regles"]["2"]["meilleure"]
    ecarts = []
    n = 0
    for k in VARIANTES:
        run = res["runs"][k]
        sim = mt.simuler(ent, campagne.parametres(k, meilleure))
        tem = mt.temoin(ent, R.POIDS, run["mesures"]["expo_moyenne"])
        for quoi, a, b in ((k, sim["r"], run["sim"]["r"]),
                           (f"temoin {k}", tem["r"], run["temoin"]["r"])):
            n += 1
            if not np.array_equal(a, b):
                ecarts.append(quoi)
    for k in ("fixe", "vol"):
        run = res["robustesse"]["runs"][k]
        poids = {"BTC": 1.0}
        sim = mt.simuler(ent_r, campagne.parametres(k, poids=poids))
        tem = mt.temoin(ent_r, poids, run["mesures"]["expo_moyenne"])
        for quoi, a, b in ((f"robustesse {k}", sim["r"], run["sim"]["r"]),
                           (f"temoin robustesse {k}", tem["r"], run["temoin"]["r"])):
            n += 1
            if not np.array_equal(a, b):
                ecarts.append(quoi)
    return {"runs": n, "identiques": not ecarts, "ecarts": ecarts}


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s  %(message)s")
    res = pickle.loads(PKL.read_bytes())
    if res.get("experience") != R.ID_EXP or res.get("empreinte_regles") != R.empreinte():
        raise correctif.CorrectifError("resultats.pkl ne vient pas des regles V1 gelees")
    campagne.verifier_gel()
    d = campagne.charger_principal()
    ent = campagne.entrees_principal(d)
    ent_r, close_r = campagne.entrees_robustesse()
    verif = verifier(res, ent, ent_r)
    if not verif["identiques"]:
        raise correctif.CorrectifError(f"re-simulation differente : {verif['ecarts']}")
    log.info("verification : %d series re-simulees, identiques au bit pres", verif["runs"])
    aller_retours = {k: correctif.aller_retours(ent.jours, ent.baissier, res["runs"][k]["sim"],
                                                res["runs"][k]["temoin"]["r"])
                     for k in VARIANTES}
    v_btc = d["closes"]["BTC"].reindex(ent.jours).to_numpy()
    bears = correctif.grands_bears(ent.jours, v_btc, ent.baissier,
                                   {k: metriques.courbe(res["runs"][k]["sim"]["r"])
                                    for k in VARIANTES})
    rob = res["robustesse"]["runs"]
    bears_rob = correctif.grands_bears(ent_r.jours, close_r.reindex(ent_r.jours).to_numpy(),
                                       ent_r.baissier,
                                       {k: metriques.courbe(v["sim"]["r"]) for k, v in rob.items()})
    cor = {"date": DATE, "commit": _git("rev-parse", "--short", "HEAD"),
           "commit_mesure": _git("log", "-1", "--format=%h", "--", "VC6_V1/rapport_temps2.md"),
           "resultats": str(PKL.relative_to(config.RACINE)), "verification": verif,
           "controle_frais": all(x["controle_frais"] for x in aller_retours.values()),
           "aller_retours": aller_retours, "grands_bears": bears,
           "robustesse_grands_bears": bears_rob}
    for k, x in aller_retours.items():
        log.info("%s : %d aller-retours, %d fenetres, frais %.6f <= totaux %.6f, ecart temoin %.6f",
                 k, x["n"], x["n_fenetres"], x["frais_total"], x["frais_totaux"],
                 x["ecart_temoin_total"])
    for b in bears + bears_rob:
        log.info("bear %s -> %s : %s %s", b["pic"], b["creux"], b["statut"], b["bascule"])
    chemin = rapport.ecrire(res, correctif=cor)
    log.info("rapport corrige : %s", chemin)
    return 0


if __name__ == "__main__":
    sys.exit(main())
