"""VC6 V1, Temps 2 : les 5 tests de coherence du moteur, AVANT tout run de variante.

a. BTC seul, exposition 1, sans levier ni frais : le moteur = SMA 200 calculee a part
   (VC6_V1/temps2/verif_independante.py, sans import de BETA). a1 : bascule immediate, sans poche
   baissiere ; a2 : rampe de 5 jours et poche baissiere de 25 % BTC (spec).
b. Exposition 1 en permanence, sans regime ni frais : le moteur = panier 50/25/25 reequilibre
   chaque jour, calcule a part.
c. Anticipation : la decision de t appliquee au rendement de t doit AMELIORER le resultat.
d. Frais : un aller-retour de 100 % du capital coute 2 x 10 pb.
e. Funding : sur une semaine en levier tiree au hasard (graine 0), le financement deduit = le calcul
   a la main sur les reglements bruts.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

from beta import config
from beta.invest import metriques
from beta.vc6 import donnees as dn
from beta.vc6 import moteur as mt
from beta.vc6 import regles as R

SCRIPT = config.RACINE / "VC6_V1" / "temps2" / "verif_independante.py"
TOLERANCE_A = 0.001


def _valeur(r: np.ndarray) -> float:
    return float(np.prod(1.0 + r))


def independant() -> dict:
    with tempfile.NamedTemporaryFile(suffix=".json") as f:
        subprocess.run([sys.executable, "-I", str(SCRIPT), str(config.RACINE), f.name],
                       check=True, capture_output=True)
        return json.loads(open(f.name).read())


def test_a_b(ent: mt.Entrees, ref: dict) -> dict:
    sans = dict(frais_pb=0.0, bande=0.0, sizing="fixe", e_fixe=1.0)
    a1 = mt.simuler(ent, mt.Parametres(poids={"BTC": 1.0}, baissiere={}, rampe=1, **sans))
    a2 = mt.simuler(ent, mt.Parametres(poids={"BTC": 1.0}, baissiere={"BTC": 0.25}, **sans))
    b = mt.simuler(ent, mt.Parametres(regime=False, baissiere={}, **sans))
    sortie = {}
    for cle, sim in (("a1", a1), ("a2", a2), ("b", b)):
        v = _valeur(sim["r"])
        ecart = abs(v / ref[cle] - 1.0)
        sortie[cle] = {"moteur": v, "independant": ref[cle], "ecart_relatif": ecart,
                       "passe": bool(ecart < TOLERANCE_A)}
    return sortie


def test_c(ent: mt.Entrees) -> dict:
    sortie = {}
    configs = {
        "BTC seul, SMA 200, bascule immediate, sans frais":
            dict(poids={"BTC": 1.0}, baissiere={}, rampe=1, frais_pb=0.0, sizing="fixe"),
        "BTC, ETH, SOL 50/25/25, regime, rampe 1 jour, sans poche baissiere ni frais":
            dict(baissiere={}, rampe=1, frais_pb=0.0, sizing="fixe"),
    }
    for nom, k in configs.items():
        normal = mt.simuler(ent, mt.Parametres(**k))
        anticipe = mt.simuler(ent, mt.Parametres(anticipation=True, **k))
        vn, va = _valeur(normal["r"]), _valeur(anticipe["r"])
        un = float(np.sqrt(np.mean(metriques.drawdown(metriques.courbe(normal["r"]))[1:] ** 2)))
        ua = float(np.sqrt(np.mean(metriques.drawdown(metriques.courbe(anticipe["r"]))[1:] ** 2)))
        sortie[nom] = {"valeur_normale": vn, "valeur_anticipee": va, "ulcer_normal": un,
                       "ulcer_anticipe": ua, "passe": bool(va > vn and ua < un)}
    return sortie


def test_d() -> dict:
    jours = pd.date_range("2030-01-01", periods=4, freq="D")
    zero = np.zeros(4)
    ent = mt.Entrees(jours=jours, baissier=np.array([True, False, True, True]),
                     sigma={"BTC": np.full(4, 0.5)}, funding_annuel={"BTC": zero},
                     funding_jour={"BTC": zero}, rendements={"BTC": zero})
    sim = mt.simuler(ent, mt.Parametres(poids={"BTC": 1.0}, baissiere={}, rampe=1,
                                        sizing="fixe"))
    total = float(sim["frais"].sum())
    return {"positions": sim["y"][:, 0].tolist(), "frais_par_jour": sim["frais"].tolist(),
            "frais_total": total, "attendu": 2 * R.FRAIS_PB / 1e4,
            "valeur_finale": _valeur(sim["r"]), "valeur_attendue": (1 - R.FRAIS_PB / 1e4) ** 2,
            "passe": bool(abs(total - 0.002) < 1e-15
                          and abs(_valeur(sim["r"]) - 0.999 ** 2) < 1e-15)}


def test_e(ent: mt.Entrees) -> dict:
    p = mt.Parametres(regime=False, baissiere={}, sizing="fixe", e_fixe=2.0)
    sim = mt.simuler(ent, p)
    jours = ent.jours[1:]
    plein = np.all(np.isclose(sim["e"], 2.0), axis=1)
    debuts = [i for i in range(len(jours) - 6) if plein[i:i + 7].all()]
    rng = np.random.default_rng(R.GRAINE)
    i0 = debuts[int(rng.integers(len(debuts)))]
    semaine = jours[i0:i0 + 7]
    main = 0.0
    detail = []
    for a, w in R.POIDS.items():
        f = dn.funding_brut(a)
        for d in semaine:
            debut = pd.Timestamp(d).tz_localize("UTC")
            reglements = f[(f.index > debut) & (f.index <= debut + pd.Timedelta(days=1))]
            main += (2.0 - 1.0) * w * float(reglements.sum())
            detail.append({"actif": a, "jour": f"{d:%Y-%m-%d}", "reglements": len(reglements),
                           "somme": float(reglements.sum())})
    moteur = float(sim["financement"][i0:i0 + 7].sum())
    return {"semaine": [f"{semaine[0]:%Y-%m-%d}", f"{semaine[-1]:%Y-%m-%d}"],
            "semaines_candidates": len(debuts), "moteur": moteur, "a_la_main": main,
            "ecart": abs(moteur - main), "detail": detail,
            "passe": bool(abs(moteur - main) < 1e-12)}


def tous(ent: mt.Entrees) -> dict:
    ref = independant()
    res = {"a_b": test_a_b(ent, ref), "c": test_c(ent), "d": test_d(), "e": test_e(ent)}
    res["passe"] = bool(all(x["passe"] for x in res["a_b"].values())
                        and all(x["passe"] for x in res["c"].values())
                        and res["d"]["passe"] and res["e"]["passe"])
    return res
