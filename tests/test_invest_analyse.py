"""Test invest — analyse (C) : redondance entre votes (kappa, Spearman) et ablation."""

import numpy as np
import pandas as pd
import pytest

from beta.invest import analyse as an


def test_kappa_de_cohen_a_la_main():
    a = np.array([1, 1, 0, -1, 0, 1])
    b = np.array([1, 0, 0, -1, 1, 1])
    p_o, p_e = 4 / 6, (3 * 3 + 2 * 2 + 1 * 1) / 36
    assert an.kappa_cohen(a, b) == pytest.approx((p_o - p_e) / (1 - p_e))


def test_kappa_accord_parfait_desaccord_parfait_et_indefini():
    a = np.array([1, 1, -1, -1])
    assert an.kappa_cohen(a, a) == pytest.approx(1.0)
    assert an.kappa_cohen(a, -a) == pytest.approx(-1.0)
    assert an.kappa_cohen(np.zeros(4), np.zeros(4)) is None        # p_e = 1


def test_matrices_d_accord_sur_toutes_les_paires():
    v = pd.DataFrame({"x": [1, 1, -1, -1, 0], "y": [1, 1, -1, -1, 0], "z": [0, 0, 0, 0, 0]})
    m = an.matrices_accord(v)
    assert m["kappa"]["x"]["y"] == pytest.approx(1.0)
    assert m["kappa"]["y"]["x"] == m["kappa"]["x"]["y"]
    assert m["accord"]["x"]["z"] == pytest.approx(0.2)              # un seul jour a 0 des deux
    assert m["spearman"]["x"]["y"] == pytest.approx(1.0)
    assert m["spearman"]["x"]["z"] is None                          # z constant
    assert m["kappa"]["x"]["x"] == 1.0


def test_contribution_par_ablation_et_lecture_mecanique():
    complet = {"ulcer": 0.10, "mdd": -0.30, "protection": 0.40, "cagr": 0.20}
    sans = {"utile": {"ulcer": 0.14, "mdd": -0.35, "protection": 0.30, "cagr": 0.22},
            "inutile": {"ulcer": 0.10, "mdd": -0.30, "protection": 0.40, "cagr": 0.25},
            "nuisible": {"ulcer": 0.08, "mdd": -0.25, "protection": 0.45, "cagr": 0.21}}
    c = an.contributions(complet, sans)
    assert c["utile"]["delta"]["ulcer"] == pytest.approx(-0.04)       # M(complet) - M(sans k)
    assert c["utile"]["delta"]["cagr"] == pytest.approx(-0.02)
    assert c["utile"]["lecture"] == "contribue a la survie"
    assert c["inutile"]["lecture"] == "inutile ou nuisible"          # ne change rien
    assert c["nuisible"]["lecture"] == "inutile ou nuisible"         # la retirer ameliore


def test_contribution_sans_protection_definie():
    c = an.contributions({"ulcer": 0.1, "mdd": -0.2, "protection": None},
                         {"k": {"ulcer": 0.1, "mdd": -0.2, "protection": None}})
    assert c["k"]["delta"]["protection"] is None and c["k"]["lecture"] == "inutile ou nuisible"
