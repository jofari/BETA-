"""Tests du CSCV : une reference naive recalcule tout combinaison par combinaison.

Aucune donnee de la voie C ici, et jamais la graine 0 (reservee au controle preenregistre de PBOC).
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.stats import rankdata

from beta.stats import cscv


def reference(m: np.ndarray, s: int, ppa: float = 252.0) -> tuple[float, np.ndarray]:
    """Lecture directe de l'article : concatener les blocs, Sharpe numpy, rang scipy."""
    t, n = m.shape
    b = t // s
    j_is, j_oos = cscv.combinaisons(s)
    lambdas = []
    for ci, co in zip(j_is, j_oos, strict=True):
        lignes_is = np.concatenate([np.arange(k * b, (k + 1) * b) for k in ci])
        lignes_oos = np.concatenate([np.arange(k * b, (k + 1) * b) for k in co])
        a, o = m[lignes_is], m[lignes_oos]
        sh_is = a.mean(axis=0) / a.std(axis=0, ddof=1) * math.sqrt(ppa)
        sh_oos = o.mean(axis=0) / o.std(axis=0, ddof=1) * math.sqrt(ppa)
        etoile = int(np.argmax(sh_is))
        w = rankdata(sh_oos, method="average")[etoile] / (n + 1)
        lambdas.append(math.log(w / (1 - w)))
    lambdas = np.array(lambdas)
    return float((lambdas <= 0).mean()), lambdas


def test_combinaisons_de_16_blocs():
    j_is, j_oos = cscv.combinaisons(16)
    assert j_is.shape == j_oos.shape == (12870, 8)
    for ci, co in zip(j_is[::97], j_oos[::97], strict=True):
        assert sorted([*ci, *co]) == list(range(16))
    assert len({tuple(c) for c in j_is}) == 12870


def test_exemple_calcule_a_la_main():
    # Bloc 0 = jours 0-1, bloc 1 = jours 2-3 ; colonnes A, B, C.
    m = np.array([[1.0, 0.0, -1.0],
                  [3.0, 2.0, 1.0],
                  [-1.0, 1.0, 0.0],
                  [1.0, 3.0, 4.0]])
    r = cscv.pbo(m, s=2)
    # J = {0} : n* = A, pire OOS (rang 1) ; J = {1} : n* = B, rang 2 sur 3 -> w = 0,5, lambda = 0.
    assert r.etoiles.tolist() == [0, 1]
    assert r.rangs.tolist() == [1.0, 2.0]
    assert r.w.tolist() == [0.25, 0.5]
    assert r.lambdas[0] == pytest.approx(math.log(1 / 3))
    assert r.lambdas[1] == 0.0
    assert r.pbo == 1.0                     # lambda = 0 compte dans la PBO (<= 0)


@pytest.mark.parametrize("graine", [11, 12, 13])
def test_identique_a_la_reference(graine):
    rng = np.random.default_rng(graine)
    m = rng.standard_normal((48, 7)) * 0.02 + 0.001
    m[:, 5] = m[:, 2]                       # doublon exact : egalites IS et OOS
    attendu_pbo, attendu_lambdas = reference(m, s=6)
    r = cscv.pbo(m, s=6, lot=7)             # lots plus petits que C(6, 3) = 20
    assert r.n_combinaisons == 20
    np.testing.assert_allclose(r.lambdas, attendu_lambdas, rtol=0, atol=1e-12)
    assert r.pbo == attendu_pbo


def test_egalite_is_premiere_colonne_et_rang_moyen_oos():
    rng = np.random.default_rng(21)
    m = rng.standard_normal((40, 5)) * 0.01
    m[:, 1] += 0.05                         # largement la meilleure partout
    m[:, 3] = m[:, 1]                       # sa copie exacte
    r = cscv.pbo(m, s=4)
    assert (r.etoiles == 1).all()           # la premiere des deux
    assert (r.rangs == 4.5).all()           # rangs 4 et 5 partages
    assert r.pbo == 0.0


def test_persistance_parfaite_donne_zero():
    rng = np.random.default_rng(31)
    m = np.linspace(-0.01, 0.01, 9)[None, :] + rng.standard_normal((64, 9)) * 1e-6
    r = cscv.pbo(m, s=8)
    assert (r.etoiles == 8).all() and (r.rangs == 9).all()
    assert r.pbo == 0.0


def test_anti_persistance_parfaite_donne_un():
    # Colonnes de +1 et -1 en nombre egal : moyenne totale nulle, donc la moyenne OOS est
    # l'oppose de la moyenne IS. La meilleure IS est toujours la pire OOS.
    rng = np.random.default_rng(41)
    base = np.array([1.0] * 32 + [-1.0] * 32)
    m = np.column_stack([rng.permutation(base) for _ in range(6)])
    r = cscv.pbo(m, s=8)
    assert (r.lambdas < 0).all()
    assert r.pbo == 1.0


def test_le_sharpe_ne_depend_pas_de_l_echelle():
    rng = np.random.default_rng(51)
    m = rng.standard_normal((96, 11)) * 0.02
    echelles = rng.uniform(0.1, 10.0, size=11)
    a, b = cscv.pbo(m, s=8), cscv.pbo(m * echelles, s=8)
    assert (a.etoiles == b.etoiles).all() and (a.rangs == b.rangs).all()
    assert a.pbo == b.pbo


def test_calibration_sous_le_hasard():
    # Rendements iid sans avantage : le rang OOS de n* est uniforme, E[PBO] = 1/2.
    valeurs = [cscv.pbo(np.random.default_rng(g).standard_normal((160, 20)), s=8).pbo
               for g in range(1, 201)]
    assert np.mean(valeurs) == pytest.approx(0.5, abs=0.03)


@pytest.mark.parametrize("m, s, message", [
    (np.zeros((10, 3)) + np.arange(30).reshape(10, 3), 4, "multiple"),
    (np.random.default_rng(61).standard_normal((12, 3)), 3, "pair"),
    (np.random.default_rng(62).standard_normal((12, 1)), 4, "au moins 2"),
    (np.full((12, 3), np.nan), 4, "manquant"),
])
def test_entrees_refusees(m, s, message):
    with pytest.raises(cscv.CSCVError, match=message):
        cscv.pbo(m, s=s)


def test_ecart_type_nul_refuse():
    m = np.random.default_rng(71).standard_normal((16, 3))
    m[:, 1] = 0.001                         # constante : ecart-type nul
    with pytest.raises(cscv.CSCVError, match="ecart-type"):
        cscv.pbo(m, s=4)


def test_serie_constante_refusee_malgre_l_arrondi():
    # Sur des blocs de 119 jours, une colonne constante a 0,1 a une variance calculee de
    # +7,5e-18, pas 0 : un test « variance <= 0 » la laisserait passer, Sharpe ~3,6e7.
    m = np.random.default_rng(81).standard_normal((476, 3))
    m[:, 2] = 0.1
    with pytest.raises(cscv.CSCVError, match="ecart-type"):
        cscv.pbo(m, s=4)
