"""Test invest — moteur : panier en buy and hold, score normalise, mappings, rendement (A1-A3)."""

import numpy as np
import pandas as pd
import pytest

from beta.invest import moteur as mo

T = lambda s: pd.Timestamp(s, tz="UTC")                                   # noqa: E731
SOCLE = mo.Mapping("socle")
PALIERS = mo.Mapping("paliers")


# ------------------------------------------------------------------------- score et mapping

def test_score_normalise_moyenne_des_votes_actifs():
    v = pd.DataFrame({"a": [1.0, -1.0], "b": [1.0, 0.0], "c": [0.0, -1.0]},
                     index=[T("2026-01-01"), T("2026-01-02")])
    assert mo.score_normalise(v, ("a", "b")).tolist() == [1.0, -0.5]
    assert mo.score_normalise(v, ("a", "b", "c")).tolist() == pytest.approx([2 / 3, -2 / 3])
    with pytest.raises(ValueError):
        mo.score_normalise(v, ())


def test_paliers_aux_seuils():
    s = np.array([1.0, 0.4, 0.2, 0.0, -0.2, -0.4, -1.0])
    assert mo.exposition(s, PALIERS).tolist() == [1.0, 1.0, 0.7, 0.7, 0.7, 0.25, 0.25]


def test_socle_la_veille_garde_l_exposition_precedente():
    s = np.array([0.0, 0.2, 0.6, 0.2, 0.0, -0.4, 0.2, 0.4])
    assert mo.exposition(s, SOCLE).tolist() == [1.0, 1.0, 1.0, 1.0, 1.0, 0.25, 0.25, 1.0]


def test_socle_exposition_initiale_tant_qu_aucun_signal():
    m = mo.Mapping("socle", e_init=0.25)
    assert mo.exposition(np.array([0.0, 0.2, -0.2]), m).tolist() == [0.25, 0.25, 0.25]


def test_seuils_robustes_aux_erreurs_d_arrondi():
    s = np.array([0.7 - 0.3, -(0.1 + 0.2 + 0.1)])          # 0,39999... et -0,40000...1
    assert mo.exposition(s, PALIERS).tolist() == [1.0, 0.25]


def test_mapping_inconnu_refuse():
    with pytest.raises(ValueError):
        mo.exposition(np.array([0.0]), mo.Mapping("autre"))


# ---------------------------------------------------------------------- panier et holds

def _closes():
    i = pd.date_range(T("2026-01-01"), periods=3, freq="D")
    return pd.DataFrame({"A": [100.0, 110.0, 121.0], "B": [100.0, 90.0, 81.0]}, index=i)


def test_panier_buy_and_hold_non_rebalance():
    p = mo.panier(_closes(), {"A": 0.5, "B": 0.5}, T("2026-01-02"), T("2026-01-03"))
    assert list(p.jours) == [T("2026-01-02"), T("2026-01-03")]
    assert p.v.tolist() == pytest.approx([1.0, 1.0, 1.01])          # V0 = cloture du 01/01
    assert p.r.tolist() == pytest.approx([0.0, 0.01])
    assert p.poids_debut_jour[1].tolist() == pytest.approx([0.55, 0.45])    # les poids derivent


def test_panier_refuse_des_poids_qui_ne_font_pas_1_ou_un_actif_absent():
    with pytest.raises(ValueError):
        mo.panier(_closes(), {"A": 0.5, "B": 0.4}, T("2026-01-02"), T("2026-01-03"))
    with pytest.raises(ValueError):
        mo.panier(_closes(), {"A": 0.5, "C": 0.5}, T("2026-01-02"), T("2026-01-03"))


def test_hold_d_un_seul_actif():
    v = mo.hold(_closes(), "B", T("2026-01-02"), T("2026-01-03"))
    assert v.tolist() == pytest.approx([1.0, 0.9, 0.81])


# ------------------------------------------------------------------------- rendement (A3)

def test_l_exposition_decidee_a_la_cloture_t_s_applique_au_jour_t_plus_1():
    # e[i] est decidee a la cloture qui precede le jour i : la baisse a 0,25 decidee a la
    # cloture du jour 1 ne joue qu'au jour 2, jamais au jour 1 lui-meme.
    out = mo.rendement(np.array([1.0, 1.0, 0.25, 0.25]), np.array([0.1, 0.1, -0.2, 0.1]), 0.0)
    assert out["r"].tolist() == pytest.approx([0.1, 0.1, -0.05, 0.025])


def test_aligner_prend_le_vote_en_vigueur_le_jour_du_rendement():
    votes = pd.Series([1.0, -1.0, 1.0], index=pd.date_range(T("2026-01-01"), periods=3))
    jours = pd.DatetimeIndex([T("2026-01-02"), T("2026-01-03")])
    assert mo.aligner(votes, jours).tolist() == [-1.0, 1.0]
    with pytest.raises(ValueError, match="2026-01-04"):
        mo.aligner(votes, pd.DatetimeIndex([T("2026-01-04")]))


def test_cout_de_rotation_kappa_par_unite_de_delta_e_sans_cout_d_entree():
    out = mo.rendement(np.array([1.0, 0.25, 0.25, 1.0]), np.zeros(4), 10.0)
    assert out["cout"].tolist() == pytest.approx([0.0, 0.00075, 0.0, 0.00075])
    assert out["r"].tolist() == pytest.approx([0.0, -0.00075, 0.0, -0.00075])
    assert out["turnover"] == pytest.approx(1.5)


def test_funding_sur_la_seule_part_en_levier():
    out = mo.rendement(np.array([1.5, 1.0, 0.5]), np.zeros(3), 0.0, phi=np.full(3, 0.001))
    assert out["funding"].tolist() == pytest.approx([0.0005, 0.0, 0.0])
    assert out["r"].tolist() == pytest.approx([-0.0005, 0.0, 0.0])


def test_taux_sans_risque_sur_la_seule_part_en_cash():
    out = mo.rendement(np.array([0.25, 1.0, 1.5]), np.zeros(3), 0.0, rf=np.full(3, 0.0001))
    assert out["r"].tolist() == pytest.approx([0.000075, 0.0, 0.0])


def test_funding_du_panier_pondere_par_les_poids_du_debut_de_journee():
    p = mo.panier(_closes(), {"A": 0.5, "B": 0.5}, T("2026-01-02"), T("2026-01-03"))
    f = pd.DataFrame({"A": [0.0, 0.001, 0.002], "B": [0.0, 0.003, 0.004]}, index=_closes().index)
    assert mo.funding_panier(p, f).tolist() == pytest.approx(
        [0.5 * 0.001 + 0.5 * 0.003, 0.55 * 0.002 + 0.45 * 0.004])


def test_taux_sans_risque_quotidien_lu_la_veille_sur_365_jours():
    dff = pd.Series([3.65, 7.30], index=[T("2025-12-31"), T("2026-01-02")])
    jours = pd.DatetimeIndex([T("2026-01-02"), T("2026-01-03")])
    assert mo.rf_quotidien(dff, jours).tolist() == pytest.approx([0.0001, 0.0002])


def test_temoin_a_exposition_constante_egale_a_la_moyenne():
    e = np.array([1.0, 0.25, 0.25, 1.0])
    r_b = np.array([0.1, -0.1, 0.05, 0.0])
    out = mo.temoin_constant(e, r_b, 10.0)
    assert out["e"] == pytest.approx(0.625)
    assert out["r"].tolist() == pytest.approx((0.625 * r_b).tolist())      # aucune rotation
