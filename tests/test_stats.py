"""La batterie S1-S9. Ces tests verifient surtout qu'elle sait TUER — c'est son seul role."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from beta.stats import (batterie, bootstrap, diversification, montecarlo, multitest,
                        reference, synthetique, walkforward)


def bruit(n=500, graine=0) -> np.ndarray:
    return np.random.default_rng(graine).normal(0.0, 1.0, n)


def edge(n=500, mu=0.3, graine=0) -> np.ndarray:
    return np.random.default_rng(graine).normal(mu, 1.0, n)


# --- S3 bootstrap --------------------------------------------------------------------

def test_les_indices_bootstrap_restent_dans_la_serie():
    rng = np.random.default_rng(0)
    idx = bootstrap.indices(50, 200, ell=5.0, rng=rng)
    assert len(idx) == 200
    assert idx.min() >= 0 and idx.max() < 50


def test_le_bootstrap_ne_declare_pas_significatif_du_bruit_pur():
    resultat = bootstrap.intervalle(bruit(), n_repetitions=300)
    assert resultat["p_value"] > 0.05
    assert resultat["ic_bas"] < 0 < resultat["ic_haut"]


def test_le_bootstrap_voit_un_edge_franc():
    resultat = bootstrap.intervalle(edge(), n_repetitions=300)
    assert resultat["p_value"] <= 0.05
    assert resultat["ic_bas"] > 0


def test_la_sensibilite_publie_les_trois_longueurs():
    resultats = bootstrap.sensibilite(edge(), n_repetitions=100)
    assert [r["ell_demande"] for r in resultats] == list(bootstrap.LONGUEURS_SENSIBILITE)
    assert bootstrap.stable(resultats)


def test_un_seul_echec_de_longueur_suffit_a_declarer_instable():
    assert not bootstrap.stable([{"p_value": 0.01}, {"p_value": 0.30}])


# --- S1 Benjamini-Hochberg -----------------------------------------------------------

def test_bh_coupe_la_famille_au_bon_rang():
    table = pd.DataFrame({"nom": list("abcde"),
                          "p_brute": [0.001, 0.008, 0.039, 0.041, 0.9]})
    out = multitest.benjamini_hochberg(table, fdr=0.10)
    assert out.loc[out["nom"] == "a", "signif_BH"].iloc[0]
    assert not out.loc[out["nom"] == "e", "signif_BH"].iloc[0]


def test_bh_ne_garde_rien_quand_tout_est_du_bruit():
    table = pd.DataFrame({"nom": list("abcd"), "p_brute": [0.4, 0.5, 0.6, 0.7]})
    assert not multitest.benjamini_hochberg(table, fdr=0.10)["signif_BH"].any()


# --- S2 Sharpe degonfle --------------------------------------------------------------

def test_le_seuil_du_maximum_croit_avec_le_nombre_d_essais():
    assert (multitest.sharpe_attendu_du_maximum(100)
            > multitest.sharpe_attendu_du_maximum(10) > 0)


def test_le_dsr_tue_un_sharpe_moyen_paye_par_beaucoup_d_essais():
    x = edge(n=200, mu=0.15)
    peu = multitest.sharpe_degonfle(x, n_essais=2)
    beaucoup = multitest.sharpe_degonfle(x, n_essais=5000)
    assert beaucoup["dsr"] < peu["dsr"]
    assert beaucoup["sharpe_seuil"] > peu["sharpe_seuil"]


# --- S7 reality check ----------------------------------------------------------------

def test_le_reality_check_ne_sacre_pas_le_meilleur_d_un_lot_de_bruit():
    univers = {f"c{i}": bruit(300, graine=i) for i in range(20)}
    resultat = multitest.reality_check(univers, n_repetitions=200)
    assert resultat["p_value"] > 0.05


def test_le_reality_check_voit_une_vraie_gagnante_parmi_du_bruit():
    univers = {f"c{i}": bruit(300, graine=i) for i in range(9)}
    univers["vraie"] = edge(300, mu=0.4, graine=99)
    resultat = multitest.reality_check(univers, n_repetitions=200)
    assert resultat["meilleure"] == "vraie"
    assert resultat["p_value"] <= 0.05


# --- S4 Monte-Carlo ------------------------------------------------------------------

def test_la_permutation_conserve_le_resultat_final():
    r = edge(100)
    mc = montecarlo.simuler(r, mode="permutation", n_tirages=200)
    finaux = set(round(v, 6) for v in mc["equity_finale"].values())
    assert len(finaux) == 1                       # meme total, seul le chemin change


def test_le_reechantillonnage_fait_varier_le_resultat_final():
    mc = montecarlo.simuler(edge(100), mode="remise", n_tirages=500)
    assert mc["equity_finale"]["p95"] > mc["equity_finale"]["p5"]


def test_une_strategie_perdante_a_une_probabilite_de_perte_elevee():
    mc = montecarlo.simuler(edge(200, mu=-0.2), mode="remise", n_tirages=500)
    assert mc["p_perte"] > 0.9


# --- S5 chemins synthetiques ---------------------------------------------------------

def _serie_marche(n=400, graine=0) -> pd.DataFrame:
    rng = np.random.default_rng(graine)
    closes = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.01, n)))
    return pd.DataFrame({"date": pd.date_range("2020-01-01", periods=n, freq="4h",
                                               tz="UTC"),
                         "open": closes, "high": closes * 1.005, "low": closes * 0.995,
                         "close": closes, "volume": np.ones(n)})


@pytest.mark.parametrize("generateur", ["gbm", "phase"])
def test_les_generateurs_rendent_des_series_exploitables(generateur):
    chemins = list(synthetique.GENERATEURS[generateur](_serie_marche(), n_chemins=3))
    assert len(chemins) == 3
    for chemin in chemins:
        assert len(chemin) == 400
        assert (chemin["high"] >= chemin["close"]).all()
        assert (chemin["low"] <= chemin["close"]).all()
        assert np.isfinite(chemin["close"]).all()


def test_un_resultat_median_parmi_les_synthetiques_ne_passe_pas():
    comparaison = synthetique.comparer(0.0, list(np.linspace(-1, 1, 100)))
    assert not comparaison["passe"]
    assert comparaison["centile"] == pytest.approx(50, abs=2)


def test_un_resultat_tres_superieur_aux_synthetiques_passe():
    assert synthetique.comparer(10.0, list(np.linspace(-1, 1, 100)))["passe"]


# --- S6 walk-forward -----------------------------------------------------------------

def _trades(n=200, mu=0.2, graine=0) -> pd.DataFrame:
    rng = np.random.default_rng(graine)
    entrees = pd.date_range("2021-01-01", periods=n, freq="3D", tz="UTC")
    return pd.DataFrame({"ts_entree": entrees, "ts_sortie": entrees + pd.Timedelta("2D"),
                         "r": rng.normal(mu, 1.0, n), "paire": "BTC"})


def test_la_purge_retire_les_trades_qui_chevauchent_le_test():
    trades = _trades()
    debut = pd.Timestamp("2021-06-01", tz="UTC")
    fin = pd.Timestamp("2021-08-01", tz="UTC")
    train, test, comptes = walkforward.purger(trades, [(debut, fin)], embargo_pct=1.0)
    assert comptes["n_purges"] > 0
    sorties = pd.to_datetime(train["ts_sortie"], utc=True)
    entrees = pd.to_datetime(train["ts_entree"], utc=True)
    assert not ((sorties >= debut) & (entrees <= fin)).any()


def test_l_embargo_retire_aussi_ce_qui_suit_immediatement_le_test():
    trades = _trades()
    fin = pd.Timestamp("2021-06-01", tz="UTC")
    _, _, sans = walkforward.purger(trades, [(fin - pd.Timedelta("30D"), fin)],
                                    embargo_pct=0.0)
    _, _, avec = walkforward.purger(trades, [(fin - pd.Timedelta("30D"), fin)],
                                    embargo_pct=10.0)
    assert avec["n_purges"] > sans["n_purges"]


def test_le_walk_forward_rend_une_efficacite_lisible():
    resultat = walkforward.marche_en_avant(_trades(n=300), n_plis=5)
    assert resultat["n_plis"] >= 3
    assert np.isfinite(resultat["efficacite"])


def test_le_cpcv_voit_qu_une_strategie_perdante_perd_sur_tous_les_chemins():
    resultat = walkforward.cpcv(_trades(n=300, mu=-0.4), n_plis=6, k_test=2)
    assert resultat["part_chemins_perdants"] > 0.9


# --- S8 buy-and-hold -----------------------------------------------------------------

def test_le_hold_mesure_bien_la_hausse_du_marche():
    resultat = reference.hold({"BTC": _serie_marche(n=800, graine=1)})
    assert np.isfinite(resultat["rendement_total_pct"])
    assert resultat["n_paires"] == 1


def test_ne_pas_battre_le_hold_fait_echouer_la_porte():
    comparaison = reference.comparer({"rendement_total_pct": 10.0, "sharpe_annuel": 0.5,
                                      "drawdown_max_pct": -20.0},
                                     {"rendement_total_pct": 200.0, "sharpe_annuel": 1.2,
                                      "drawdown_max_pct": -60.0})
    assert not comparaison["passe"]
    assert comparaison["ecart_rendement_pct"] < 0


# --- S9 diversification --------------------------------------------------------------

def _equity(graine=0, n=300) -> pd.DataFrame:
    rng = np.random.default_rng(graine)
    ts = pd.date_range("2022-01-01", periods=n, freq="1D", tz="UTC")
    return pd.DataFrame({"ts": ts, "equity": 100000 + np.cumsum(rng.normal(50, 500, n))})


def test_deux_courbes_identiques_sont_declarees_redondantes():
    courbe = _equity()
    liens = diversification.redondances({"a": courbe, "b": courbe.copy()})
    assert liens and liens[0]["correlation"] == pytest.approx(1.0)


def test_une_candidate_decorrelee_franchit_la_porte():
    resultat = diversification.porte("a", {"a": _equity(0), "b": _equity(7)})
    assert resultat["passe"]


def test_une_candidate_qui_copie_une_autre_echoue_a_la_porte():
    courbe = _equity()
    resultat = diversification.porte("a", {"a": courbe, "b": courbe.copy()})
    assert not resultat["passe"]


# --- orchestration -------------------------------------------------------------------

def test_la_batterie_declare_indecidable_un_echantillon_trop_petit():
    trades = pd.DataFrame({"r": [0.5, -1.0, 2.0], "rendement_pct": [1.0, -2.0, 4.0],
                           "ts_entree": pd.date_range("2024-01-01", periods=3, tz="UTC"),
                           "ts_sortie": pd.date_range("2024-01-02", periods=3, tz="UTC")})
    resultat = batterie.evaluer(trades, n_essais=36)
    assert batterie.issue(resultat["portes"], len(trades)) == "indecidable"
    assert any("indecidable par construction" in r for r in resultat["reserves"])


def test_la_batterie_infirme_une_strategie_perdante():
    r = edge(n=200, mu=-0.3)
    trades = pd.DataFrame({
        "r": r, "rendement_pct": r,
        "ts_entree": pd.date_range("2022-01-01", periods=200, freq="2D", tz="UTC"),
        "ts_sortie": pd.date_range("2022-01-02", periods=200, freq="2D", tz="UTC"),
        "paire": "BTC"})
    resultat = batterie.evaluer(trades, n_essais=36)
    assert batterie.issue(resultat["portes"], len(trades)) == "infirmee"


def test_une_porte_absente_reste_none_et_ne_vaut_pas_franchie():
    trades = pd.DataFrame({"r": edge(50), "rendement_pct": edge(50)})
    resultat = batterie.evaluer(trades, n_essais=36)
    assert resultat["portes"]["S8_buy_and_hold"] is None
    assert resultat["portes"]["S5_synthetique"] is None
