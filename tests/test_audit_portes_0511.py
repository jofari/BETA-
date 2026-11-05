"""Audit des portes du 05/11/2026 : les defauts de fonctionnement corriges SANS changer de regle.

Chaque test reprend un cas de l'audit. Aucun seuil, aucun critere de decision n'est touche :
les portes calculent enfin ce qu'elles annoncent. Les changements de REGLE (S8 a volatilite
egale, S4 jugee sur le drawdown, V empirique dans S2, q de S1, S10 incalculable) attendent
Jonas et ne sont pas ici.
"""
from __future__ import annotations

import types

import numpy as np
import pandas as pd
import pytest

from beta.moteur import espace_r, pipeline
from beta.stats import (batterie, bootstrap, descriptif, diversification, montecarlo,
                        multitest, walkforward)


def _equity(ts, pnl, capital=100_000.0):
    return pd.DataFrame({"ts": ts, "equity": capital + np.cumsum(pnl)})


# --- S9 : la correlation se lit avec son signe, sur le P&L du jour -------------------------

def test_s9_une_candidate_anticorrelee_n_est_pas_une_copie():
    rng = np.random.default_rng(0)
    t = pd.date_range("2022-01-01", periods=300, freq="D", tz="UTC")
    commun = rng.normal(0, 100, 300)
    toutes = {"A": _equity(t, commun + rng.normal(0, 20, 300)),
              "B": _equity(t, -commun + rng.normal(0, 20, 300))}
    porte = diversification.porte("B", toutes)
    assert porte["correlation_max"] < -0.9
    assert porte["passe"] is True


def test_s9_une_copie_reste_une_copie():
    rng = np.random.default_rng(1)
    t = pd.date_range("2022-01-01", periods=300, freq="D", tz="UTC")
    commun = rng.normal(0, 100, 300)
    toutes = {"A": _equity(t, commun + rng.normal(0, 20, 300)),
              "B": _equity(t, commun + rng.normal(0, 20, 300))}
    porte = diversification.porte("B", toutes)
    assert porte["correlation_max"] > 0.9 and porte["passe"] is False
    assert diversification.redondances(toutes)[0]["correlation"] > 0.9


def test_s9_mesure_le_pnl_du_jour_et_non_un_pourcentage_d_une_equity_additive():
    # La courbe du moteur est a risque fixe : elle peut descendre pres de zero. Le P&L de
    # B est exactement le double de celui de A, donc leur correlation vaut 1 ; un
    # pct_change la deformait, parce que le denominateur (l'equity de la veille) differe.
    rng = np.random.default_rng(2)
    t = pd.date_range("2022-01-01", periods=200, freq="D", tz="UTC")
    pnl = rng.normal(-450, 800, 200)
    toutes = {"A": _equity(t, pnl), "B": _equity(t, 2 * pnl)}
    assert diversification.matrice(toutes).loc["A", "B"] == pytest.approx(1.0)


# --- S6 : le dernier trade compte -----------------------------------------------------------

def _trades_reguliers(n=400, graine=3):
    rng = np.random.default_rng(graine)
    entrees = pd.Series(pd.date_range("2020-01-01", periods=n, freq="5D", tz="UTC"))
    return pd.DataFrame({"ts_entree": entrees, "ts_sortie": entrees + pd.Timedelta(days=3),
                         "r": rng.normal(0.0, 1.0, n)})


def test_s6_chaque_trade_tombe_dans_un_pli_de_test():
    trades = _trades_reguliers()
    plis = walkforward._bornes(trades["ts_entree"], walkforward.N_PLIS)
    assert walkforward._masque_test(trades, plis).all()


def test_s6_le_dernier_trade_entre_dans_le_dernier_pli_du_walk_forward():
    trades = _trades_reguliers()
    wf = walkforward.marche_en_avant(trades)
    debut_pli_2 = walkforward._bornes(trades["ts_entree"], walkforward.N_PLIS)[1][0]
    attendus = int((trades["ts_entree"] >= debut_pli_2).sum())
    assert sum(pli["n_test"] for pli in wf["plis"]) == attendus


# --- S4 : drawdown depuis le capital initial, centile lu dans le bon sens -------------------

def test_s4_le_drawdown_part_du_capital_initial():
    mc = montecarlo.simuler(np.array([-1.0, 1.0, 1.0]), "permutation", n_tirages=50)
    assert mc["drawdown_max_reel_pct"] == pytest.approx(-1.0)
    assert min(mc["drawdown_max"].values()) <= -1.0 + 1e-9


def _pertes_reparties(n_cycles=15):
    return np.array([2.0, 2.0, -1.0] * n_cycles)


def test_s4_une_chronologie_ou_les_pertes_sont_reparties_est_chanceuse():
    mc = montecarlo.simuler(_pertes_reparties(), "permutation", n_tirages=2000)
    assert mc["centile_drawdown_reel"] >= 90


def test_s4_une_chronologie_ou_les_pertes_arrivent_d_abord_ne_l_est_pas():
    r = np.sort(_pertes_reparties())               # toutes les pertes en tete
    mc = montecarlo.simuler(r, "permutation", n_tirages=2000)
    assert mc["centile_drawdown_reel"] <= 10


def test_s4_la_reserve_chanceuse_vise_la_bonne_chronologie():
    chanceuse = batterie.evaluer(pd.DataFrame({"r": _pertes_reparties()}))["reserves"]
    malchanceuse = batterie.evaluer(pd.DataFrame({"r": np.sort(_pertes_reparties())}))["reserves"]
    assert any("chanceuse" in x for x in chanceuse)
    assert not any("chanceuse" in x for x in malchanceuse)


# --- S7 : un calendrier commun, aucune troncature -------------------------------------------

def test_s7_refuse_des_series_de_longueurs_differentes():
    with pytest.raises(ValueError, match="longueur"):
        multitest.reality_check({"A": np.zeros(50), "B": np.ones(30)})


def _trades_jour(jours, r):
    sorties = pd.DatetimeIndex(jours)
    return pd.DataFrame({"ts_entree": sorties - pd.Timedelta(hours=8), "ts_sortie": sorties,
                         "r": np.asarray(r, dtype=float)})


def test_s7_l_univers_journalier_garde_la_correlation_par_date():
    rng = np.random.default_rng(4)
    jours = pd.date_range("2022-01-01", periods=1000, freq="D", tz="UTC")
    commun = rng.normal(0, 1, 1000)
    a = commun + 0.3 * rng.normal(0, 1, 1000)
    b = commun + 0.3 * rng.normal(0, 1, 1000)
    lot = {"A": _trades_jour(jours[::2], a[::2]), "B": _trades_jour(jours[::5], b[::5]),
           "vide": _trades_jour([], [])}
    univers = multitest.univers_journalier(lot)
    assert set(univers) == {"A", "B"}                    # sans trade : hors du maximum
    assert len(univers["A"]) == len(univers["B"]) == 1000 - 1   # du 1er au dernier jour du lot
    jours_communs = slice(None, None, 10)
    assert np.corrcoef(univers["A"][jours_communs], univers["B"][jours_communs])[0, 1] > 0.85
    assert univers["A"].sum() == pytest.approx(a[::2].sum())   # aucun trade jete


# --- S5 : la meme statistique des deux cotes -------------------------------------------------

def test_s5_le_reel_se_lit_sur_la_paire_du_temoin():
    sequence = pd.DataFrame({"paire": ["BTC", "ETH", "BTC", "ETH"], "r": [1.0, 5.0, 2.0, 5.0]})
    sortie = batterie.evaluer(sequence, resultats_synthetiques=[0.0] * 99 + [10.0],
                              paire_synthetique="BTC")
    assert sortie["detail"]["S5_synthetique"]["observe"] == pytest.approx(3.0)


def test_s5_le_temoin_enchaine_ses_trades_comme_le_reel(monkeypatch):
    # Trois signaux sur un chemin synthetique, dont un pendant un trade deja ouvert : le
    # reel ne le prend pas (`enchainer`), le temoin ne doit pas le prendre non plus.
    debut = pd.Timestamp("2024-01-01", tz="UTC")
    signaux_simules = pd.DataFrame({
        "paire": ["BTC~0"] * 3, "r": [1.0, 10.0, 2.0],
        "ts_entree": [debut, debut + pd.Timedelta(hours=4), debut + pd.Timedelta(days=2)],
        "ts_sortie": [debut + pd.Timedelta(days=1), debut + pd.Timedelta(days=1, hours=4),
                      debut + pd.Timedelta(days=3)]})
    monkeypatch.setattr(pipeline.espace_r, "evaluer", lambda *a, **k: signaux_simules.copy())
    monkeypatch.setitem(pipeline.synthetique.GENERATEURS, "phase",
                        lambda df, n, graine=0: iter([df] * n))
    run = types.SimpleNamespace(
        candidate=types.SimpleNamespace(appliquer=lambda df: pd.DataFrame()),
        take_profit_r=2.0, horizon_bougies=10, stop_atr=2.0, cout_aller_retour_pct=0.0,
        spread=False, funding=False, spread_modele=espace_r.MODELE_SPREAD, graine=0)
    totaux = pipeline._resultats_synthetiques(run, {"BTC": pd.DataFrame({"close": [1.0]})},
                                              "phase", 3)
    assert totaux == [3.0, 3.0, 3.0]


# --- S0 : le n effectif se mesure ------------------------------------------------------------

def test_mde_tient_compte_des_trades_groupes():
    rng = np.random.default_rng(5)
    grappes = np.repeat(rng.normal(0, 1, 200), 8) + 0.35 * rng.normal(0, 1, 1600)
    sigma = float(grappes.std(ddof=1))
    resume = descriptif.resumer(pd.DataFrame({"r": grappes}))
    assert resume["n_effectif"] < 400
    assert resume["mde_r"] > 1.8 * descriptif.mde(1600, sigma)
    assert resume["mde_r"] == pytest.approx(descriptif.mde(1600, sigma, n_eff=resume["n_effectif"]))


def test_mde_jamais_plus_genereux_que_l_hypothese_de_chevauchement():
    rng = np.random.default_rng(6)
    independants = rng.normal(0, 1, 1600)
    resume = descriptif.resumer(pd.DataFrame({"r": independants}))
    assert resume["n_effectif"] == pytest.approx(1600 / descriptif.CHEVAUCHEMENT)
    assert resume["mde_r"] == pytest.approx(descriptif.mde(1600, resume["r_sigma"]))


def test_mde_des_appelants_historiques_inchange():
    # r1_trailing et r6_news_window appellent mde(n, sigma) : leurs chiffres ne bougent pas.
    assert descriptif.mde(100, 1.0) == pytest.approx(descriptif.Z_MDE / np.sqrt(100 / 1.6))


# --- S3 : le p percentile est GARDE ----------------------------------------------------------

def test_s3_garde_le_p_percentile():
    """L'audit proposait un p « centre ». Mesure du 05/11/2026 (`scripts/calibration_s3.py`) :
    sous H0, le p actuel rejette a 4,9-6,3 % au seuil de 5 % ; le centre ne fait pas mieux
    (4,5-7,0 %, pire en asymetrie a gauche). Aucun motif de changer la porte : ce test fige
    la formule, pour qu'un changement futur passe par une decision.
    """
    x = np.array([2.0, -1.0, -1.0, 2.0, -1.0, 2.0, 2.0, -1.0, -1.0, 2.0] * 6)
    ligne = batterie.evaluer(pd.DataFrame({"r": x}))["detail"]["S3_bootstrap"][0]
    tirages = bootstrap.distribution(x, ell=float(ligne["ell_demande"]),
                                     n_repetitions=bootstrap.N_REPETITIONS, graine=0)
    assert ligne["p_value"] == pytest.approx(((tirages <= 0).sum() + 1)
                                             / (bootstrap.N_REPETITIONS + 1))
