"""VC6 V2 : les 4 tests de coherence du moteur (etape C du prompt du 02/11/2026), AVANT tout run.

a. « V2 – poche baissiere sous HAR » avec E_BTC force a 1 dans la poche baissiere = la « Variante
   expo vol » de la V1 : rendements identiques au bit pres a ceux du moteur de la V1 sur les memes
   entrees, et valeur finale et Ulcer egaux a ceux que la V1 a mesures (resultats du 02/11).
b. « V2 – HAR sans regime » avec Ei force a 1, sans frais = panier 50/25/25 reequilibre chaque jour
   (test b de la V1 : VC6_V1/temps2/verif_independante.py, sans import de BETA ; ecart < 0,1 %).
c. Anticipation : sigma remplace par la volatilite realisee du jour t + 1 doit ameliorer le Sharpe
   et l'Ulcer de « V2 – HAR sans regime ». Ni l'un ni l'autre : alignement des dates suspect.
d. Null : un decalage circulaire de 0 jour redonne exactement le resultat observe (les deux
   essais) ; pour « V2 – HAR sans regime », l'ordre identite des blocs de 63 jours aussi.
Un test rate : arret, rien d'autre ne tourne. Le test d ne rend que des egalites, pas les chiffres
des essais.
"""

from __future__ import annotations

import pickle

import numpy as np

from beta import config
from beta.invest import metriques
from beta.vc6 import campagne as c1
from beta.vc6 import coherence as coh1
from beta.vc6 import moteur as mt1
from beta.vc6_v2 import donnees as dn
from beta.vc6_v2 import moteur as mt
from beta.vc6_v2 import nulls as nu

PKL_V1 = config.DATA / "vc6_temps2" / "resultats.pkl"
TOLERANCE_B = 0.001


def _valeur(r: np.ndarray) -> float:
    return float(metriques.courbe(r)[-1])


def test_a(ent: mt.Entrees) -> dict:
    p = mt.parametres_essai("poche_baissiere_har")
    p.e_baissiere_force = 1.0
    v2 = mt.simuler(ent, p)
    v1 = mt1.simuler(ent, c1.parametres("vol"))
    if not PKL_V1.exists():
        return {"passe": False, "raison": f"resultat de la V1 absent : {PKL_V1}"}
    res = pickle.loads(PKL_V1.read_bytes())
    mesure = res["runs"]["vol"]
    s2 = metriques.standard(v2["r"])
    sortie = {
        "valeur_finale_v2": _valeur(v2["r"]), "valeur_finale_v1": 1.0 + mesure["mesures"][
            "rendement_total"],
        "ulcer_v2": s2["ulcer"], "ulcer_v1": mesure["mesures"]["ulcer"],
        "rendements_identiques_moteur_v1": bool(np.array_equal(v2["r"], v1["r"])),
        "rendements_identiques_mesure_v1": bool(np.array_equal(v2["r"], mesure["sim"]["r"])),
        "ecart_max": float(np.max(np.abs(v2["r"] - mesure["sim"]["r"]))),
        "jours": int(len(v2["r"]))}
    sortie["passe"] = bool(sortie["rendements_identiques_moteur_v1"]
                           and sortie["rendements_identiques_mesure_v1"]
                           and s2["rendement_total"] == mesure["mesures"]["rendement_total"]
                           and sortie["ulcer_v2"] == sortie["ulcer_v1"])
    return sortie


def test_b(ent: mt.Entrees) -> dict:
    p = mt.parametres_essai("har_sans_regime")
    p.sizing, p.e_fixe, p.frais_pb = "fixe", 1.0, 0.0
    sim = mt.simuler(ent, p)
    ref = coh1.independant()["b"]
    v = _valeur(sim["r"])
    ecart = abs(v / ref - 1.0)
    return {"moteur": v, "independant": ref, "ecart_relatif": ecart,
            "expositions_toutes_a_1": bool(np.all(sim["e"] == 1.0)),
            "passe": bool(ecart < TOLERANCE_B and np.all(sim["e"] == 1.0))}


def test_c(ent: mt.Entrees, rv) -> dict:
    p = mt.parametres_essai("har_sans_regime")
    normal = metriques.standard(mt.simuler(ent, p)["r"])
    ent_c, garde = dn.entrees_anticipees(ent, rv)
    anticipe = metriques.standard(mt.simuler(ent_c, p)["r"])
    sharpe = anticipe["sharpe"] > normal["sharpe"]
    ulcer = anticipe["ulcer"] < normal["ulcer"]
    statut = "passe" if sharpe and ulcer else ("echec" if not (sharpe or ulcer) else "un seul")
    return {"sharpe_normal": normal["sharpe"], "sharpe_anticipe": anticipe["sharpe"],
            "ulcer_normal": normal["ulcer"], "ulcer_anticipe": anticipe["ulcer"],
            "sharpe_ameliore": bool(sharpe), "ulcer_ameliore": bool(ulcer),
            "jours_sans_rv_sigma_garde": garde, "statut": statut, "passe": statut == "passe"}


def test_d(ent: mt.Entrees) -> dict:
    sortie = {}
    p1 = mt.parametres_essai("har_sans_regime")
    s1 = mt.simuler(ent, p1)
    u1 = nu.ulcer(s1["r"])
    r0 = nu.r_positions(ent, s1, p1, nu.decaler(s1["y"], 0))
    identite = np.arange(nu.n_blocs(len(s1["y"])))
    rb = nu.r_positions(ent, s1, p1, nu.permuter_blocs(s1["y"], identite))
    sortie["har_sans_regime"] = {
        "circulaire_0_rendements_identiques": bool(np.array_equal(r0, s1["r"])),
        "circulaire_0_ulcer_identique": nu.ulcer(r0) == u1,
        "blocs_identite_rendements_identiques": bool(np.array_equal(rb, s1["r"])),
        "blocs": int(len(identite))}
    p2 = mt.parametres_essai("poche_baissiere_har")
    s2 = mt.simuler(ent, p2)
    r2 = mt.simuler(ent, p2, nu.mode_circulaire(ent, 0))["r"]
    sortie["poche_baissiere_har"] = {
        "mode_identique": bool(np.array_equal(nu.mode_circulaire(ent, 0), ent.baissier)),
        "circulaire_0_rendements_identiques": bool(np.array_equal(r2, s2["r"])),
        "circulaire_0_ulcer_identique": nu.ulcer(r2) == nu.ulcer(s2["r"])}
    sortie["passe"] = bool(all(all(v for k, v in x.items() if k != "blocs")
                               for x in sortie.values()))
    return sortie


def tous() -> dict:
    """Les 4 tests, dans l'ordre ; arret au premier qui rate."""
    d = dn.charger_principal()
    ent = dn.entrees_principal(d)
    res = {}
    for nom, f in (("a", lambda: test_a(ent)), ("b", lambda: test_b(ent)),
                   ("c", lambda: test_c(ent, d["rv"])), ("d", lambda: test_d(ent))):
        res[nom] = f()
        if not res[nom]["passe"]:
            res["arret"] = nom
            break
    res["passe"] = all(res[k]["passe"] for k in "abcd" if k in res) and "arret" not in res
    res["jours"] = {"debut": f"{ent.jours[1]:%Y-%m-%d}", "fin": f"{ent.jours[-1]:%Y-%m-%d}",
                    "n": ent.n}
    return res
