"""Test invest — nulls (D) : generateurs, p-values, regle de decision, graines."""

from collections import Counter

import numpy as np
import pytest

from beta.invest import nulls as nu


def _signal(n=400, graine=1):
    """Un signal a 3 valeurs, par paliers de durees variees, sans periodicite."""
    rng = np.random.default_rng(graine)
    morceaux, total = [], 0
    while total < n:
        d = int(rng.integers(3, 40))
        morceaux.append(np.full(d, rng.choice([-1.0, 0.0, 1.0])))
        total += d
    return np.concatenate(morceaux)[:n]


# ------------------------------------------------------------------- decalage circulaire

def test_decalage_circulaire_est_une_rotation_entre_m_et_n_moins_m():
    s = _signal()
    for graine in range(20):
        sp = nu.decalage_circulaire(s, np.random.default_rng(graine), m=90)
        taus = [t for t in range(len(s)) if np.array_equal(np.roll(s, -t), sp)]
        assert len(taus) == 1 and 90 <= taus[0] <= len(s) - 90     # s'(t) = s(t + tau mod N)
        assert sorted(sp) == sorted(s)                              # meme distribution


def test_decalage_circulaire_refuse_une_serie_trop_courte():
    with pytest.raises(ValueError):
        nu.decalage_circulaire(np.zeros(150), np.random.default_rng(0), m=90)


# --------------------------------------------------------------------- melange de segments

def test_segments_de_valeur_constante():
    s = np.array([1.0, 1.0, 0.0, 0.0, 0.0, 1.0, -1.0, -1.0])
    assert nu.segments(s) == [(1.0, 2), (0.0, 3), (1.0, 1), (-1.0, 2)]


def test_melange_conserve_valeurs_et_durees_sans_jamais_fusionner():
    s = _signal()
    origine = Counter(nu.segments(s))
    for graine in range(50):
        sp = nu.melange_segments(s, np.random.default_rng(graine))
        assert len(sp) == len(s)
        assert Counter(nu.segments(sp)) == origine          # memes (valeur, duree), un pour un


def test_melange_d_un_signal_binaire_garde_l_alternance():
    s = np.concatenate([np.full(d, v) for d, v in zip([5, 3, 8, 2, 7, 4], [1, -1] * 3,
                                                       strict=True)]).astype(float)
    for graine in range(20):
        sp = nu.melange_segments(s, np.random.default_rng(graine))
        valeurs = [v for v, _ in nu.segments(sp)]
        assert all(a != b for a, b in zip(valeurs, valeurs[1:], strict=False))
        assert Counter(nu.segments(sp)) == Counter(nu.segments(s))


def test_melange_change_vraiment_l_ordre():
    s = _signal()
    assert any(not np.array_equal(nu.melange_segments(s, np.random.default_rng(g)), s)
               for g in range(10))


def test_un_signal_constant_est_son_propre_null():
    s = np.full(200, -1.0)
    assert np.array_equal(nu.melange_segments(s, np.random.default_rng(0)), s)
    assert np.array_equal(nu.decalage_circulaire(s, np.random.default_rng(0), m=90), s)


# ---------------------------------------------------------------------- p-values (D3)

def test_p_value_plus_petit_est_meilleur():
    assert nu.p_value(np.array([1.0, 2.0, 3.0, 4.0]), 2.0, plus_petit_meilleur=True) == 3 / 5


def test_p_value_plus_grand_est_meilleur():
    assert nu.p_value(np.array([1.0, 2.0, 3.0, 4.0]), 3.0, plus_petit_meilleur=False) == 3 / 5


def test_p_value_indefinie_si_la_metrique_l_est():
    assert nu.p_value(np.array([np.nan, np.nan]), None, plus_petit_meilleur=False) is None


def test_p_value_compte_un_calmar_infini_comme_meilleur():
    assert nu.p_value(np.array([np.inf, 1.0]), 2.0, plus_petit_meilleur=False) == 2 / 3


# ------------------------------------------------------------------- regle de decision D4

@pytest.mark.parametrize(("p", "attendu"), [(0.001, "reel"), (0.0499, "reel"),
                                            (0.05, "non concluant"), (0.1999, "non concluant"),
                                            (0.2, "hasard"), (1.0, "hasard")])
def test_verdict_applique_la_regle_ecrite_avant_le_test(p, attendu):
    assert nu.verdict(p) == attendu


def test_p_retenue_est_la_pire_des_deux_nulls():
    assert nu.p_retenue(0.01, 0.12) == 0.12 and nu.p_retenue(None, 0.3) is None


def test_q_de_benjamini_hochberg_informatif():
    q = nu.bh_q([0.01, 0.04, 0.03, 0.5, None])
    assert q[:4] == pytest.approx([0.04, 0.04 * 4 / 3, 0.04 * 4 / 3, 0.5])
    assert q[4] is None


# --------------------------------------------------------------------------- graines (C1)

def test_flux_deterministes_et_independants_par_cle():
    a = nu.flux(0, "circulaire", "socle", "principale").random(5)
    b = nu.flux(0, "circulaire", "socle", "principale").random(5)
    c = nu.flux(0, "segments", "socle", "principale").random(5)
    assert np.array_equal(a, b) and not np.array_equal(a, c)


def test_distribution_nulle_deterministe_et_complete():
    s = _signal()

    def evaluer(x):
        return {"ulcer": float(np.abs(np.cumsum(x)).mean()), "prot": None}

    d1 = nu.distribution_nulle(s, evaluer, 30, nu.flux(0, "a"), nu.melange_segments)
    d2 = nu.distribution_nulle(s, evaluer, 30, nu.flux(0, "a"), nu.melange_segments)
    assert d1.keys() == {"ulcer", "prot"} and len(d1["ulcer"]) == 30
    assert np.array_equal(d1["ulcer"], d2["ulcer"]) and np.isnan(d1["prot"]).all()
