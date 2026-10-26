"""Tests de PBOC sans aucune donnee de la voie C, et jamais les graines reservees (0, 1001-1100)."""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
import pytest

from beta.pbo_voie_c import campagne as ca
from beta.pbo_voie_c import rapport
from beta.pbo_voie_c import regles as R
from beta.stats import cscv
from beta.strategies import voie_c_optim as vo


def _grille() -> list[dict]:
    return [dict(zip(ca.PARAMETRES, c, strict=True)) for c in itertools.product(
        vo.CIBLES, vo.ESTIMATEURS, vo.FENETRES, vo.LEVIERS_MAX, vo.LEVIERS_MIN, vo.PAS,
        vo.BANDES)]


def test_regles_coherentes_avec_la_grille():
    assert len(_grille()) == R.N_GRILLE
    assert R.CIBLE_GARDEE in vo.CIBLES
    assert R.N_JOURS == R.S * R.JOURS_PAR_BLOC
    assert pd.Timestamp(R.FIN, tz="UTC") == vo.FIN_VUE
    jours = pd.date_range(R.DEBUT_MOTEUR, R.FIN, freq="D")
    assert len(jours) == R.N_JOURS + 8 and jours[8] == pd.Timestamp(R.DEBUT)


def test_dedoublonnage_option_b_puis_doublons_exacts():
    params = _grille()
    rng = np.random.default_rng(7)
    m = rng.standard_normal((20, len(params)))
    reps = [i for i, p in enumerate(params) if p["cible"] == R.CIBLE_GARDEE]
    m[:, reps[5]] = m[:, reps[2]]               # doublon exact parmi les representants
    d = ca.dedoublonner(params, m)
    assert (d["n_grille"], d["n_groupes"], d["n_representants"]) == (5760, 960, 960)
    assert d["n_doublons_exacts"] == 1 and d["n_apres"] == 959
    assert reps[2] in d["gardes"] and reps[5] not in d["gardes"]
    assert all(params[i]["cible"] == R.CIBLE_GARDEE for i in d["gardes"])
    assert d["doublons"][0]["identique_a"] == params[reps[2]]


def test_dedoublonnage_refuse_une_grille_inattendue():
    params = _grille()[:-1]
    with pytest.raises(ca.PBOError):
        ca.dedoublonner(params, np.zeros((5, len(params))))


def test_fenetre_d_evaluation():
    dates = pd.date_range(R.DEBUT_MOTEUR, R.FIN, freq="D", tz="UTC")
    garde = ca.fenetre_evaluation(dates)
    assert garde.sum() == R.N_JOURS and not garde[:8].any()
    with pytest.raises(ca.PBOError):
        ca.fenetre_evaluation(dates[1:])
    with pytest.raises(ca.PBOError):
        ca.fenetre_evaluation(dates[:-1])


def test_verdict_au_seuil():
    assert ca.verdict(0.1999) == "candidate"
    assert ca.verdict(0.20) == "surajustee"


def test_avantage_quotidien():
    m = np.zeros((4, 3))
    mp = ca.avec_avantage(m, 3.0)
    assert np.allclose(mp[:, 0], 3.0 / np.sqrt(252.0)) and not mp[:, 1:].any()
    assert not m.any()


def _distribution(graine: int) -> dict:
    m = np.random.default_rng(graine).standard_normal((64, 12))
    return ca.distribution(cscv.pbo(m, s=8))


def _synthese(voie: bool) -> dict:
    d = _distribution(5)
    s = {"experience": R.ID_EXP, "code": "abc1234", "regles": R.empreinte(),
         "preenregistrement": "0" * 16, "debut_calcul": "2026-10-26T10:00:00+00:00",
         "calcule_le": "2026-10-26T10:30:00+00:00",
         "positif": {"graine": 0, "pbo": 0.0, "reussi": True, "avantage": {
             "3": {**d, "part_etoile_colonne_0": 1.0, "sharpe_realise_colonne_0": 3.1},
             "1": {**d, "part_etoile_colonne_0": 0.1, "sharpe_realise_colonne_0": 1.2}}},
         "negatif": {"graines": [1001, 1100], "pbo": d["w"], "moyenne": 0.5,
                     "erreur_type": 0.01, "graine_0": d, "reussi": voie},
         "compteur": {"avant": {"global": 147, "invest": 54, "trading": 93},
                      "apres": {"global": 147, "invest": 54, "trading": 93},
                      "diagnostic": True}}
    if voie:
        cfg = _grille()[1]
        s["voie_c"] = {"donnees": "f" * 16, "fenetre": {"debut": R.DEBUT, "fin": R.FIN,
                                                        "n_jours": R.N_JOURS},
                       "dedoublonnage": {"n_grille": 5760, "n_groupes": 960,
                                         "n_representants": 960, "n_doublons_exacts": 1,
                                         "n_apres": 959,
                                         "doublons": [{"config": cfg, "identique_a": cfg}]},
                       "pbo": d, "etoiles_frequentes": [{"config": cfg, "part": 0.4}]}
        s["verdict"] = ca.verdict(d["pbo"])
    else:
        s["voie_c"], s["verdict"] = None, None
        s["arret"] = "controle(s) rate(s) : negatif ; voie C non calculee"
    return s


@pytest.mark.parametrize("voie", [True, False])
def test_rapport_se_rend(voie):
    s = _synthese(voie)
    md, court = rapport.markdown(s), rapport.resume(s)
    assert "PBOC" in md and "abc1234" in md and "Compteur" in md
    if voie:
        assert "5760 avant" in md and "959 après" in md and "Verdict mécanique" in md
    else:
        assert "Arrêt" in md and "non lues" in md and "Arrêt" in court
