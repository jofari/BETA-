"""Correctif du 02/11/2026 des mesures de rapport VC6 V1 (sections 6 et 8), donnees synthetiques."""

import numpy as np
import pandas as pd
import pytest

from beta.vc6 import correctif as cr


def _jours(n):
    return pd.date_range("2030-01-01", periods=n, freq="D")


def test_fenetres_qui_se_chevauchent_fusionnees():
    # rampe de 5 jours : [10;17[, [12;18[, [13;22[ se chevauchent ; [50;65[ est a part
    fen = cr.fenetres_sans_chevauchement([(10, 12), (12, 13), (13, 17), (50, 60)], 100)
    assert [(f["debut"], f["fin"]) for f in fen] == [(10, 22), (50, 65)]
    assert [len(f["paires"]) for f in fen] == [3, 1]


def test_fenetre_coupee_a_la_fin_de_la_periode():
    fen = cr.fenetres_sans_chevauchement([(90, 98)], 100)
    assert (fen[0]["debut"], fen[0]["fin"]) == (90, 100)


def _sim(n, frais):
    return {"r": np.zeros(n), "frais": np.asarray(frais, dtype=float)}


def test_aller_retours_chaque_jour_compte_une_seule_fois():
    n = 60
    b = np.zeros(n + 1, dtype=bool)
    b[10:12] = True          # bascules en 10 (vers baissier) et 12 (retour)
    b[13:50] = True          # bascule en 13 (vers baissier), retour en 50 : 37 jours, pas une paire
    sim = _sim(n, np.full(n, 0.001))
    res = cr.aller_retours(_jours(n + 1), b, sim, np.zeros(n))
    # paires (10, 12) et (12, 13) : fenetres [10;17[ et [12;18[ -> une seule, [10;18[
    assert res["n"] == 2
    assert res["n_fenetres"] == 1
    assert res["jours"] == 8
    assert res["frais_total"] == pytest.approx(0.008)
    assert res["frais_totaux"] == pytest.approx(0.060)
    assert res["controle_frais"]
    # l'ancienne mesure aurait compte 7 + 6 = 13 jours de frais
    assert res["fenetres"][0]["aller_retours"] == 2


def test_controle_des_frais_arrete_si_violation():
    n = 40
    b = np.zeros(n + 1, dtype=bool)
    b[10:12] = True
    frais = np.full(n, 0.001)
    frais[30] = -1.0          # impossible en vrai : sert a declencher le controle
    with pytest.raises(cr.CorrectifError):
        cr.aller_retours(_jours(n + 1), b, _sim(n, frais), np.zeros(n))


def _bear(close, bascule_a):
    n = len(close)
    b = np.zeros(n, dtype=bool)
    if bascule_a is not None:
        b[bascule_a:] = True
    return b


def test_bascule_dans_l_episode():
    close = np.array([100, 110, 120, 100, 80, 70, 90, 125], dtype=float)
    # plus haut en 2 (120), creux en 5 (70), retour en 7
    res = cr.grands_bears(_jours(8), close, _bear(close, 4), {"x": np.ones(8)})
    assert res[0]["statut"] == "bascule"
    assert res[0]["bascule"] == "2030-01-05"
    assert res[0]["delai_j"] == 2
    assert res[0]["baisse_btc_avant_bascule"] == pytest.approx(80 / 120 - 1)


def test_bascule_apres_le_creux_rate():
    close = np.array([100, 110, 120, 100, 80, 70, 90, 125, 126], dtype=float)
    # creux en 5 ; la bascule n'arrive qu'en 6 : hors de [plus haut ; creux] -> rate
    res = cr.grands_bears(_jours(9), close, _bear(close, 6), {"x": np.ones(9)})
    assert res[0]["statut"] == "rate"
    assert res[0]["bascule"] is None and res[0]["delai_j"] is None
    assert res[0]["perte_variantes"] == {}


def test_bascule_le_jour_du_creux_comptee():
    close = np.array([100, 110, 120, 100, 80, 70, 90, 125], dtype=float)
    res = cr.grands_bears(_jours(8), close, _bear(close, 5), {"x": np.ones(8)})
    assert res[0]["statut"] == "bascule" and res[0]["delai_j"] == 3


def test_deja_baissier_au_plus_haut_non_prevu():
    close = np.array([100, 110, 120, 100, 80, 70, 90, 125], dtype=float)
    with pytest.raises(cr.CorrectifError):
        cr.grands_bears(_jours(8), close, _bear(close, 1), {"x": np.ones(8)})
