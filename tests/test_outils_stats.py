"""Outils informatifs du 15/11/2026 (sharpe, risque, robustesse, selection) et les deux
corrections de formule du meme jour (prix de sortie du moteur, comparaison a AritV1).

Chaque formule est verifiee contre une valeur calculee a la main ou contre une propriete
connue (calibration sous H0, cas limite), jamais contre sa propre sortie."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from beta.moteur import espace_r
from beta.stats import comparaison, multitest, risque, robustesse, selection, sharpe


def bruit(n=1000, mu=0.0, sigma=1.0, graine=0):
    return np.random.default_rng(graine).normal(mu, sigma, n)


# --- sharpe ----------------------------------------------------------------------------

def test_erreur_type_normale_est_la_formule_de_lo():
    assert sharpe.erreur_type(0.1, 501) == pytest.approx(math.sqrt((1 + 0.1 ** 2 / 2) / 500))


def test_une_queue_gauche_elargit_l_erreur_type():
    assert sharpe.erreur_type(0.1, 500, skew=-1.0, kurtosis=6.0) \
        > sharpe.erreur_type(0.1, 500)


def test_psr_contre_son_propre_sharpe_vaut_un_demi():
    x = bruit(800, mu=0.05)
    assert sharpe.psr(x, multitest.sharpe(x))["psr"] == pytest.approx(0.5)


def test_psr_a_la_longueur_minimale_vaut_la_confiance():
    """MinTRL et PSR sont la meme formule lue dans les deux sens."""
    sr, skew, kurt = 0.08, -0.5, 5.0
    n = sharpe.longueur_minimale(sr, 0.0, skew, kurt, confiance=0.95)
    z = sr / sharpe.erreur_type(sr, n, skew, kurt)
    assert stats.norm.cdf(z) == pytest.approx(0.95, abs=1e-9)


def test_longueur_minimale_infinie_sous_la_reference():
    assert sharpe.longueur_minimale(0.05, 0.10) == float("inf")


def test_duree_minimale_de_backtest_croit_avec_les_essais():
    court = sharpe.duree_minimale_backtest(10, 1.0)
    long = sharpe.duree_minimale_backtest(100, 1.0)
    assert long > court > 0
    assert long == pytest.approx(multitest.sharpe_attendu_du_maximum(100, 1.0) ** 2)
    assert sharpe.duree_minimale_backtest(100, 2.0) == pytest.approx(long / 4)


def test_facteur_lo_sans_autocorrelation_proche_de_racine_q():
    f = sharpe.facteur_lo(bruit(5000), 365)
    assert f["facteur"] == pytest.approx(math.sqrt(365), rel=0.10)


def test_facteur_lo_baisse_avec_une_autocorrelation_positive():
    rng = np.random.default_rng(1)
    x = np.zeros(4000)
    for i in range(1, len(x)):
        x[i] = 0.5 * x[i - 1] + rng.normal()
    f = sharpe.facteur_lo(x, 365)
    assert f["rho_1"] > 0.4
    assert f["facteur"] < 0.75 * f["facteur_naif"]


def test_memmel_formule_a_la_main():
    a, b = bruit(600, 0.1, graine=1), bruit(600, 0.0, graine=2)
    res = sharpe.difference_memmel(a, b)
    sa, sb, rho = multitest.sharpe(a), multitest.sharpe(b), np.corrcoef(a, b)[0, 1]
    v = (2 * (1 - rho) + 0.5 * (sa ** 2 + sb ** 2 - 2 * sa * sb * rho ** 2)) / 600
    assert res["z"] == pytest.approx((sa - sb) / math.sqrt(v))
    assert res["p_value"] == pytest.approx(stats.norm.sf(res["z"]))


def test_difference_de_sharpe_serie_contre_elle_meme():
    a = bruit(500, 0.05)
    assert sharpe.difference_memmel(a, a)["ecart"] == 0
    boot = sharpe.difference_bootstrap(a, a, n_repetitions=200)
    assert boot["ecart"] == 0 and boot["ic_bas"] == 0 and boot["ic_haut"] == 0


def test_difference_bootstrap_voit_un_vrai_ecart_et_pas_un_faux():
    vrai = sharpe.difference_bootstrap(bruit(1500, 0.15, graine=3), bruit(1500, 0.0, graine=4),
                                       n_repetitions=500)
    assert vrai["p_value"] < 0.05 and vrai["ic_bas"] > 0
    faux = sharpe.difference_bootstrap(bruit(1500, 0.0, graine=5), bruit(1500, 0.0, graine=6),
                                       n_repetitions=500)
    assert faux["ic_bas"] < 0 < faux["ic_haut"]


def test_difference_refuse_des_longueurs_inegales():
    with pytest.raises(ValueError):
        sharpe.difference_memmel(bruit(10), bruit(11))


# --- risque ----------------------------------------------------------------------------

def test_sortino_a_la_main():
    x = np.array([0.02, -0.01, 0.03, -0.02, 0.01])
    baisse = math.sqrt((0.01 ** 2 + 0.02 ** 2) / 5)
    assert risque.sortino(x, periodes_an=1.0) == pytest.approx(x.mean() / baisse)


def test_omega_a_la_main():
    assert risque.omega(np.array([3.0, -1.0, 2.0, -1.0])) == pytest.approx(2.5)
    assert math.isnan(risque.omega(np.array([1.0, 2.0])))


def test_var_cvar_historiques():
    x = np.arange(-50, 50, dtype=float)          # 100 valeurs, -50 .. 49
    res = risque.var_cvar(x, 0.95)
    assert res["var"] == pytest.approx(-np.quantile(x, 0.05))
    assert res["cvar"] >= res["var"]
    assert res["n_queue"] == 5


def test_cornish_fisher_egale_la_normale_sans_asymetrie_ni_queues():
    x = stats.norm.ppf(np.linspace(0.0005, 0.9995, 4000))
    res = risque.var_cornish_fisher(x, 0.95)
    assert res["var_cf"] == pytest.approx(res["var_normale"], rel=0.02)


def test_cornish_fisher_depasse_la_normale_avec_une_queue_gauche():
    rng = np.random.default_rng(0)
    x = np.concatenate([rng.normal(0.001, 0.01, 2000), rng.normal(-0.08, 0.02, 40)])
    res = risque.var_cornish_fisher(x, 0.99)
    assert res["skew"] < 0 and res["var_cf"] > res["var_normale"]


def test_table_des_drawdowns():
    dates = pd.date_range("2024-01-01", periods=9, freq="1D", tz="UTC")
    v = pd.Series([100, 110, 99, 105, 110, 120, 90, 96, 100], index=dates, dtype=float)
    episodes = risque.drawdowns(v)
    assert len(episodes) == 2
    pire, autre = episodes
    assert pire["profondeur"] == pytest.approx(90 / 120 - 1) and not pire["rattrape"]
    assert pire["fin"] is None and pire["duree_baisse"] == 1
    assert autre["profondeur"] == pytest.approx(99 / 110 - 1) and autre["rattrape"]
    assert autre["duree_baisse"] == 1 and autre["duree_retour"] == 2


def test_chemin_et_courbe_negative():
    v = pd.Series([100.0, 90, 95, 100, 80])
    c = risque.chemin(v)
    assert c["drawdown_max"] == pytest.approx(-0.20)
    assert c["part_sous_l_eau"] == pytest.approx(3 / 5)
    assert c["ulcer"] == pytest.approx(math.sqrt((0.1 ** 2 + 0.05 ** 2 + 0.2 ** 2) / 5))
    assert c["non_rattrape"]
    assert "raison" in risque.chemin(pd.Series([100.0, -5.0, 10.0]))
    assert risque.drawdowns(pd.Series([100.0, -5.0, 10.0])) == []


def test_drawdown_par_blocs_les_grappes_creusent():
    """Des pertes groupees : le rejeu par blocs doit donner des drawdowns plus profonds que
    le rejeu independant, qui les disperse."""
    rng = np.random.default_rng(0)
    x = np.concatenate([np.where(rng.random(40) < 0.5, 1.0, -0.2) if i % 2 == 0
                        else np.full(40, -0.45) for i in range(10)])
    res = risque.drawdown_par_blocs(x, ell=20, n_tirages=400)
    assert res["blocs"]["median"] < res["iid"]["median"] < 0
    assert res["observe"] < 0 and 0 <= res["centile_observe"] <= 100


def test_alpha_beta_retrouve_les_coefficients():
    x = bruit(3000, 0.0005, 0.02, graine=1)
    y = 0.001 + 0.5 * x + bruit(3000, 0.0, 0.005, graine=2)
    res = risque.alpha_beta(y, x)
    assert res["beta"] == pytest.approx(0.5, abs=0.02)
    assert res["alpha"] == pytest.approx(0.001, abs=0.0003)
    assert res["t_alpha"] > 5 and res["p_alpha"] < 0.001
    assert res["retards"] == risque.retards_newey_west(3000) == 8


def test_alpha_nul_d_une_simple_exposition():
    """Une candidate qui n'est que 0,3 x la reference n'a pas d'alpha : le t de l'alpha
    doit rester petit, la ou son rendement est positif des que la reference monte."""
    x = bruit(3000, 0.001, 0.02, graine=3)
    y = 0.3 * x + bruit(3000, 0.0, 0.002, graine=4)
    res = risque.alpha_beta(y, x)
    assert abs(res["t_alpha"]) < 2.5 and res["r2"] > 0.8


def test_alpha_beta_aligne_les_series_datees():
    d = pd.date_range("2024-01-01", periods=200, freq="1D", tz="UTC")
    x = pd.Series(bruit(200, graine=1), index=d)
    y = pd.Series(bruit(150, graine=2), index=d[50:])
    assert risque.alpha_beta(y, x)["n"] == 150


def test_a_volatilite_egale_est_l_ecart_de_sharpe_fois_la_vol():
    y, x = bruit(2000, 0.0004, 0.002, graine=1), bruit(2000, 0.0008, 0.03, graine=2)
    res = risque.a_volatilite_egale(y, x)
    attendu = (res["sharpe_candidate"] - res["sharpe_reference"]) \
        * res["volatilite_reference_annuelle"]
    assert res["ecart_annuel"] == pytest.approx(attendu)
    assert res["levier"] == pytest.approx(x.std(ddof=1) / y.std(ddof=1))


# --- robustesse ------------------------------------------------------------------------

def test_concentration_un_seul_trade_porte_tout():
    trades = pd.DataFrame({"r": [20.0] + [-0.1] * 99})
    c = robustesse.concentration(trades)
    assert c["n_pour_annuler"] == 1 and c["part_gains_tete"] == pytest.approx(1.0)
    assert c["r_moyen"] > 0 > c["r_moyen_sans_le_meilleur"]


def test_concentration_edge_reparti():
    trades = pd.DataFrame({"r": [1.0, -0.5] * 100})
    c = robustesse.concentration(trades)
    assert c["n_pour_annuler"] == 50 and c["part_gains_tete"] == pytest.approx(0.10)


def test_concentration_total_negatif():
    assert robustesse.concentration(pd.DataFrame({"r": [-1.0, 0.5, -1.0]}))["n_pour_annuler"] == 0


def test_stress_des_couts():
    trades = pd.DataFrame({"r_brut": [1.0, -1.0, 1.0, 0.0], "cout_r": [0.1] * 4,
                           "frais_r": [0.08] * 4, "spread_r": [0.01] * 4,
                           "funding_r": [0.01] * 4})
    s = robustesse.stress_couts(trades)
    assert s["multiple_mort"] == pytest.approx(2.5)
    par = {x["multiple"]: x["r_moyen"] for x in s["par_multiple"]}
    assert par[1.0] == pytest.approx(0.15) and par[3.0] == pytest.approx(-0.05)
    assert s["detail_couts_r"]["frais_r"] == pytest.approx(0.08)
    assert "raison" in robustesse.stress_couts(pd.DataFrame({"r": [1.0, 2.0]}))


def test_par_annee():
    trades = pd.DataFrame({
        "ts_entree": pd.to_datetime(["2021-03-01", "2021-06-01", "2022-02-01", "2022-08-01",
                                     "2023-01-05"], utc=True),
        "r": [5.0, 1.0, -1.0, -1.0, 0.5]})
    p = robustesse.par_annee(trades)
    assert [x["annee"] for x in p["annees"]] == [2021, 2022, 2023]
    assert p["annees_positives"] == 2 and p["meilleure_annee"] == 2021
    assert p["part_meilleure_annee"] == pytest.approx(6.0 / 4.5)
    assert p["r_total_sans_meilleure_annee"] == pytest.approx(-1.5)


def test_sans_une_paire():
    trades = pd.DataFrame({"paire": ["SOL"] * 10 + ["BTC"] * 10 + ["ETH"] * 10,
                           "r": [2.0] * 10 + [-0.2] * 10 + [-0.3] * 10})
    s = robustesse.sans_une_paire(trades)
    assert s["pire"] == "SOL" and s["r_moyen"] > 0 > s["r_moyen_sans_pire"]
    assert s["signe_tient"] is False
    assert robustesse.sans_une_paire(trades[trades["paire"] == "BTC"])["paires"] == []


# --- selection -------------------------------------------------------------------------

def test_ecart_type_long_terme_du_bruit_est_l_ecart_type():
    x = bruit(4000)
    assert selection.ecart_type_long_terme(x, 5.0) == pytest.approx(x.std(), rel=0.12)


def test_spa_les_trois_p_sont_ordonnees():
    series = {f"c{i}": bruit(600, graine=i) for i in range(6)}
    series["lest"] = bruit(600, mu=-0.5, graine=99)
    res = selection.spa_hansen(series, n_repetitions=300)
    assert res["p_bas"] <= res["p_consistant"] <= res["p_haut"]
    assert res["n_recentrees"] == 6          # le lest n'est pas recentre


def test_spa_voit_une_vraie_candidate_et_ignore_le_bruit():
    series = {f"c{i}": bruit(800, graine=i) for i in range(8)}
    assert selection.spa_hansen(series, n_repetitions=300)["p_consistant"] > 0.05
    series["vraie"] = bruit(800, mu=0.25, graine=50)
    res = selection.spa_hansen(series, n_repetitions=300)
    assert res["p_consistant"] < 0.01 and res["meilleure"] == "vraie"


def test_spa_calibree_sous_h0():
    """Sous H0 (moyennes nulles), le taux de rejet a 10 % doit rester de cet ordre."""
    rejets = 0
    for g in range(60):
        rng = np.random.default_rng(1000 + g)
        series = {f"c{i}": rng.normal(0, 1, 250) for i in range(4)}
        rejets += selection.spa_hansen(series, n_repetitions=150, graine=g)["p_haut"] <= 0.10
    assert rejets / 60 <= 0.25


def test_romano_wolf_monotone_et_selectif():
    series = {f"c{i}": bruit(800, graine=i) for i in range(6)}
    series["vraie"] = bruit(800, mu=0.25, graine=50)
    res = selection.romano_wolf(series, n_repetitions=300)["candidates"]
    noms = list(res)
    assert noms[0] == "vraie" and res["vraie"]["p_ajustee"] < 0.01
    ps = [res[n]["p_ajustee"] for n in noms]
    assert ps == sorted(ps)
    assert all(res[n]["p_ajustee"] > 0.05 for n in noms[1:])


def test_selection_refuse_des_series_non_alignees():
    with pytest.raises(ValueError):
        selection.spa_hansen({"a": bruit(100), "b": bruit(90)})


# --- corrections de formule du 15/11/2026 ----------------------------------------------

def _serie(closes, hauts, bas):
    n = len(closes)
    return pd.DataFrame({"date": pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC"),
                         "open": closes, "close": closes, "high": hauts, "low": bas,
                         "volume": np.ones(n)})


def _signal(n):
    return pd.DataFrame({"sens": [1] + [0] * (n - 1), "stop_distance": np.full(n, 2.0)})


def test_un_stop_touche_sort_au_prix_du_stop_pas_a_la_cloture():
    """Stop a 98 touche dans une bougie qui recloture a 103 : -1 R, sortie a 98, rendement
    -2 %. Jusqu'au 15/11/2026 : -1 R et un rendement de +3 %."""
    df = _serie(np.array([100.0, 103, 103]), np.array([100.0, 103, 103]),
                np.array([100.0, 97, 103]))
    t = espace_r.evaluer(df, _signal(3), take_profit_r=2.0, horizon_bougies=2).loc[0]
    assert t["raison_sortie"] == espace_r.SL and t["r"] == pytest.approx(-1.0)
    assert t["prix_sortie"] == pytest.approx(98.0)
    assert t["rendement_pct"] == pytest.approx(-2.0)


def test_une_cible_touchee_sort_au_prix_de_la_cible():
    df = _serie(np.array([100.0, 101, 101]), np.array([100.0, 106, 101]),
                np.array([100.0, 100, 101]))
    t = espace_r.evaluer(df, _signal(3), take_profit_r=2.0, horizon_bougies=2).loc[0]
    assert t["raison_sortie"] == espace_r.TP
    assert t["prix_sortie"] == pytest.approx(104.0)
    assert t["rendement_pct"] == pytest.approx(4.0)


def test_a_l_horizon_la_sortie_reste_la_cloture():
    df = _serie(np.array([100.0, 101, 101.5]), np.array([100.0, 101, 101.5]),
                np.array([100.0, 100, 101]))
    t = espace_r.evaluer(df, _signal(3), take_profit_r=2.0, horizon_bougies=2).loc[0]
    assert t["raison_sortie"] == espace_r.HORIZON
    assert t["prix_sortie"] == pytest.approx(101.5)


def test_rendement_et_r_decrivent_le_meme_trade():
    """rendement_pct / 100 x entree / risque == r, pour les trois raisons de sortie."""
    rng = np.random.default_rng(0)
    closes = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 600)))
    df = _serie(closes, closes * 1.006, closes * 0.994)
    sig = pd.DataFrame({"sens": np.where(np.arange(600) % 7 == 0, 1, 0),
                        "stop_distance": closes * 0.025})
    t = espace_r.evaluer(df, sig, take_profit_r=2.0, horizon_bougies=10)
    assert set(t["raison_sortie"]) == {espace_r.TP, espace_r.SL, espace_r.HORIZON}
    np.testing.assert_allclose(t["rendement_pct"] / 100 * t["prix_entree"] / t["risque"],
                               t["r"], atol=1e-9)


def test_la_comparaison_a_arit_ne_passe_plus_par_un_pourcentage():
    """Une courbe a risque fixe qui passe sous zero : l'ecart doit rester la difference des
    P&L rapportee au capital initial, et le Sharpe garder le signe du P&L."""
    jours = pd.date_range("2024-01-01", periods=60, freq="1D", tz="UTC")
    perdante = pd.DataFrame({"ts": jours, "equity": 100_000.0 - 3_000.0 * np.arange(60)})
    plate = pd.DataFrame({"ts": jours, "equity": 100_000.0
                          + 100.0 * np.sin(np.arange(60))})
    serie = comparaison._serie_journaliere(perdante)
    assert (serie < 0).all() and serie.iloc[0] == pytest.approx(-0.03)
    ecart = comparaison._ecart_contre(perdante, comparaison._serie_journaliere(plate))
    attendu = 100 * ((perdante["equity"].iloc[-1] - 100_000.0)
                     - (plate["equity"].iloc[-1] - plate["equity"].iloc[0])) / 100_000.0
    assert ecart["ecart_rendement_pct"] == pytest.approx(attendu)


# --- fiche -----------------------------------------------------------------------------

def test_la_fiche_se_construit_et_s_ecrit_sans_verdict():
    from beta.stats import fiche

    rng = np.random.default_rng(0)
    n = 300
    entrees = pd.date_range("2021-01-01", periods=n, freq="3D", tz="UTC")
    brut = np.where(rng.random(n) < 0.4, 2.0, -1.0)
    trades = pd.DataFrame({
        "paire": rng.choice(["BTC", "ETH", "SOL"], n), "ts_entree": entrees,
        "ts_sortie": entrees + pd.Timedelta(hours=20), "r_brut": brut,
        "cout_r": 0.05, "frais_r": 0.04, "spread_r": 0.005, "funding_r": 0.005,
        "r": brut - 0.05})
    equity = espace_r.equity(trades)
    jours = pd.date_range("2020-12-31", periods=920, freq="1D", tz="UTC")
    hold = {"ts": [d.isoformat() for d in jours],
            "valeur": list(np.exp(np.cumsum(rng.normal(0.001, 0.03, 920))))}
    f = fiche.construire(trades, equity, hold, n_essais=99)
    assert f["n_trades"] == n and f["sharpe"]["duree_minimale_backtest_ans"] > 0
    assert f["contre_le_hold"]["regression"]["n"] >= 800
    assert f["stress_couts"]["multiple_mort"] == pytest.approx(brut.mean() / 0.05)
    texte = fiche.markdown(f, "essai")
    assert "ni porte ni verdict" in texte
    assert not any(mot in texte.lower() for mot in ("confirm", "infirm", "indécidable"))
    sans_rien = fiche.construire(trades[["ts_sortie", "r"]])
    assert "raison" in sans_rien["contre_le_hold"] and "raison" in sans_rien["chemin"]
    assert fiche.markdown(sans_rien, "nu")
