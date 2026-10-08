"""Le moteur : contrats, triple barriere, enchainement. Ce qui doit casser doit casser."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from beta.moteur import espace_r, registre
from beta.moteur.contrats import (CONFIRMEE, Candidate, ContratError, Run, Verdict)
from beta.protocole import experiences


def serie(closes, hauts=None, bas=None, debut="2024-01-01") -> pd.DataFrame:
    n = len(closes)
    dates = pd.date_range(debut, periods=n, freq="1h", tz="UTC")
    return pd.DataFrame({
        "date": dates, "open": closes, "close": closes,
        "high": hauts if hauts is not None else closes,
        "low": bas if bas is not None else closes,
        "volume": np.ones(n)})


def signaux_fixes(sens_par_index: dict, n: int, stop: float | None = None) -> pd.DataFrame:
    sens = np.zeros(n, dtype=int)
    for i, s in sens_par_index.items():
        sens[i] = s
    colonnes = {"sens": sens}
    if stop is not None:
        colonnes["stop_distance"] = np.full(n, stop, dtype=float)
    return pd.DataFrame(colonnes)


# --- triple barriere -----------------------------------------------------------------

def test_take_profit_touche_rend_exactement_le_r_cible():
    closes = np.array([100.0, 101, 102, 103, 104, 105])
    df = serie(closes)
    trades = espace_r.evaluer(df, signaux_fixes({0: 1}, len(df), stop=2.0),
                              take_profit_r=2.0, horizon_bougies=5)
    assert len(trades) == 1
    assert trades.loc[0, "raison_sortie"] == espace_r.TP
    assert trades.loc[0, "r"] == pytest.approx(2.0)


def test_stop_touche_rend_moins_un_r():
    closes = np.array([100.0, 99, 98, 97, 96, 95])
    df = serie(closes)
    trades = espace_r.evaluer(df, signaux_fixes({0: 1}, len(df), stop=2.0),
                              take_profit_r=2.0, horizon_bougies=5)
    assert trades.loc[0, "raison_sortie"] == espace_r.SL
    assert trades.loc[0, "r"] == pytest.approx(-1.0)


def test_bougie_ambigue_compte_comme_un_stop():
    """SL et TP dans la meme bougie => SL. Le choix pessimiste, comme cote ARIT."""
    closes = np.array([100.0, 100, 100])
    hauts = np.array([100.0, 105, 105])          # touche le TP a 104
    bas = np.array([100.0, 97, 97])              # et le SL a 98, dans la MEME bougie
    df = serie(closes, hauts, bas)
    trades = espace_r.evaluer(df, signaux_fixes({0: 1}, len(df), stop=2.0),
                              take_profit_r=2.0, horizon_bougies=2)
    assert trades.loc[0, "raison_sortie"] == espace_r.SL


def test_sortie_a_l_horizon_utilise_la_cloture():
    closes = np.array([100.0, 100.5, 101.0, 100.8])
    df = serie(closes)
    trades = espace_r.evaluer(df, signaux_fixes({0: 1}, len(df), stop=10.0),
                              take_profit_r=5.0, horizon_bougies=2)
    assert trades.loc[0, "raison_sortie"] == espace_r.HORIZON
    assert trades.loc[0, "r"] == pytest.approx((101.0 - 100.0) / 10.0)


def test_short_symetrique_du_long():
    closes = np.array([100.0, 99, 98, 97, 96, 95])
    df = serie(closes)
    trades = espace_r.evaluer(df, signaux_fixes({0: -1}, len(df), stop=2.0),
                              take_profit_r=2.0, horizon_bougies=5)
    assert trades.loc[0, "sens"] == "short"
    assert trades.loc[0, "raison_sortie"] == espace_r.TP
    assert trades.loc[0, "r"] == pytest.approx(2.0)


def test_le_cout_est_soustrait_et_croit_quand_le_stop_se_resserre():
    closes = np.array([100.0, 101, 102, 103, 104, 105])
    df = serie(closes)
    large = espace_r.evaluer(df, signaux_fixes({0: 1}, len(df), stop=4.0),
                             take_profit_r=1.0, horizon_bougies=5,
                             cout_aller_retour_pct=0.1)
    serre = espace_r.evaluer(df, signaux_fixes({0: 1}, len(df), stop=1.0),
                             take_profit_r=1.0, horizon_bougies=5,
                             cout_aller_retour_pct=0.1)
    assert serre.loc[0, "cout_r"] > large.loc[0, "cout_r"]
    assert serre.loc[0, "r"] < serre.loc[0, "r_brut"]


# --- couts de detention : spread et funding ------------------------------------------

def serie_avec_meches(n: int = 60, graine: int = 0, meche: float = 0.8) -> pd.DataFrame:
    """Une serie qui a une vraie amplitude intra-bougie — sans quoi le spread estime est 0.

    Corwin & Schultz lit le spread dans l'ecart entre l'amplitude d'UNE bougie et celle de
    DEUX : une serie plate (high = low = close, comme `serie()`) rend donc exactement 0,0,
    ce qui est correct mais ne teste rien.
    """
    rng = np.random.default_rng(graine)
    closes = 100.0 + np.cumsum(rng.normal(0.0, 0.3, n))
    return serie(closes, hauts=closes + meche, bas=closes - meche)


def test_le_spread_estime_est_nul_sur_une_serie_sans_amplitude():
    df = serie(np.linspace(100, 110, 40))
    estimes = espace_r.spread_corwin_schultz(df)
    assert estimes.iloc[1:].eq(0.0).all()


def test_le_spread_estime_n_est_jamais_negatif_et_ne_traine_pas_de_nan():
    df = serie_avec_meches(graine=7)
    brut = espace_r.spread_corwin_schultz(df)
    assert brut.iloc[1:].ge(0.0).all()
    assert brut.iloc[1:].gt(0.0).any()
    rempli = espace_r._serie_spread(df)
    assert np.isfinite(rempli).all()          # warm-up compris : aucun signal perdu


def test_le_spread_reduit_le_r_du_trade():
    df = serie_avec_meches(graine=1)
    sig = signaux_fixes({30: 1}, len(df), stop=2.0)
    options = {"take_profit_r": 2.0, "horizon_bougies": 10}
    sans = espace_r.evaluer(df, sig, **options)
    avec = espace_r.evaluer(df, sig, spread=True, **options)
    assert avec.loc[0, "spread_r"] > 0.0
    assert avec.loc[0, "r"] < sans.loc[0, "r"]
    # Le cout ne touche QUE le resultat : meme geometrie, meme trade, meme sortie.
    assert avec.loc[0, "r_brut"] == pytest.approx(sans.loc[0, "r_brut"])
    assert avec.loc[0, "raison_sortie"] == sans.loc[0, "raison_sortie"]
    assert avec.loc[0, "r"] == pytest.approx(avec.loc[0, "r_brut"] - avec.loc[0, "cout_r"])


def test_le_spread_paye_vaut_un_spread_complet_par_aller_retour():
    """Un demi a l'entree, un demi a la sortie — pas deux spreads, pas un demi."""
    df = serie_avec_meches(graine=2)
    sig = signaux_fixes({30: 1}, len(df), stop=2.0)
    trades = espace_r.evaluer(df, sig, take_profit_r=2.0, horizon_bougies=10, spread=True)
    estimes = espace_r._serie_spread(df)
    sortie = 30 + int(trades.loc[0, "duree_bougies"])
    demi_somme = 0.5 * (estimes[30] + estimes[sortie])
    attendu = demi_somme * trades.loc[0, "prix_entree"] / 2.0    # x entree / risque
    assert trades.loc[0, "spread_r"] == pytest.approx(attendu)


def serie_funding(taux: float, n: int = 8) -> pd.DataFrame:
    df = serie(np.full(n, 100.0))              # plate : la sortie se fait a l'horizon
    df["funding_rate"] = taux
    return df


def test_un_funding_positif_coute_au_long_et_paie_le_short():
    df = serie_funding(0.0001)
    options = {"take_profit_r": 2.0, "horizon_bougies": 5, "funding": True}
    long = espace_r.evaluer(df, signaux_fixes({0: 1}, len(df), stop=2.0), **options)
    short = espace_r.evaluer(df, signaux_fixes({0: -1}, len(df), stop=2.0), **options)
    assert long.loc[0, "r_brut"] == pytest.approx(0.0)
    assert long.loc[0, "funding_r"] > 0.0        # un cout pour le long
    assert short.loc[0, "funding_r"] < 0.0       # un revenu pour le short
    assert long.loc[0, "r"] < 0.0 < short.loc[0, "r"]
    assert long.loc[0, "r"] == pytest.approx(-short.loc[0, "r"])


def test_le_funding_est_compte_au_prorata_de_la_duree_de_la_bougie():
    """Le pipeline joint le taux en PALIER : le sommer bougie a bougie paierait le meme
    reglement huit fois en 1h. Le total doit valoir taux x duree_tenue / 8 h."""
    df = serie_funding(0.0001)                   # bougies 1h, reglement 8h
    trades = espace_r.evaluer(df, signaux_fixes({0: 1}, len(df), stop=2.0),
                              take_profit_r=2.0, horizon_bougies=5, funding=True)
    heures_tenues = float(trades.loc[0, "duree_h"])
    attendu = 0.0001 * (heures_tenues / 8.0) * (100.0 / 2.0)   # x entree / risque
    assert trades.loc[0, "funding_r"] == pytest.approx(attendu)


def test_un_funding_manquant_vaut_zero_et_ne_fait_pas_sauter_le_trade():
    df = serie_funding(0.0001)
    df.loc[2:4, "funding_rate"] = np.nan
    trades = espace_r.evaluer(df, signaux_fixes({0: 1}, len(df), stop=2.0),
                              take_profit_r=2.0, horizon_bougies=5, funding=True)
    assert len(trades) == 1
    plein = espace_r.evaluer(serie_funding(0.0001),
                             signaux_fixes({0: 1}, 8, stop=2.0),
                             take_profit_r=2.0, horizon_bougies=5, funding=True)
    assert 0.0 < trades.loc[0, "funding_r"] < plein.loc[0, "funding_r"]


def test_une_paire_sans_colonne_funding_ne_casse_pas_l_evaluation():
    """Le cas d'un indice : pas de perpetuel, donc pas de funding — un etat normal."""
    df = serie_avec_meches(graine=3)
    assert "funding_rate" not in df.columns
    trades = espace_r.evaluer(df, signaux_fixes({30: 1}, len(df), stop=2.0),
                              take_profit_r=2.0, horizon_bougies=10,
                              spread=True, funding=True)
    assert len(trades) == 1
    assert trades.loc[0, "funding_r"] == pytest.approx(0.0)
    assert trades.loc[0, "spread_r"] > 0.0


def test_le_cout_total_est_la_somme_des_trois_postes():
    df = serie_avec_meches(graine=4)
    df["funding_rate"] = 0.0001
    trades = espace_r.evaluer(df, signaux_fixes({30: 1}, len(df), stop=2.0),
                              take_profit_r=2.0, horizon_bougies=10,
                              cout_aller_retour_pct=0.07, spread=True, funding=True)
    ligne = trades.loc[0]
    assert ligne["cout_r"] == pytest.approx(ligne["frais_r"] + ligne["spread_r"]
                                            + ligne["funding_r"])
    assert ligne["r"] == pytest.approx(ligne["r_brut"] - ligne["cout_r"])


def test_les_couts_de_detention_sont_eteints_par_defaut_dans_le_moteur():
    """`evaluer` rend la geometrie nue ; c'est le Run qui porte la politique de couts."""
    df = serie_avec_meches(graine=5)
    df["funding_rate"] = 0.0001
    trades = espace_r.evaluer(df, signaux_fixes({30: 1}, len(df), stop=2.0),
                              take_profit_r=2.0, horizon_bougies=10)
    assert trades.loc[0, "spread_r"] == pytest.approx(0.0)
    assert trades.loc[0, "funding_r"] == pytest.approx(0.0)
    assert trades.loc[0, "r"] == pytest.approx(trades.loc[0, "r_brut"])


def test_signal_sur_la_derniere_bougie_est_ecarte():
    df = serie(np.array([100.0, 101, 102]))
    trades = espace_r.evaluer(df, signaux_fixes({2: 1}, len(df), stop=1.0))
    assert trades.empty


def test_signal_sans_atr_disponible_est_ecarte():
    """Sans stop_distance, le warm-up de l'ATR ne donne pas de risque : pas de trade."""
    df = serie(np.linspace(100, 110, 5))
    trades = espace_r.evaluer(df, signaux_fixes({0: 1}, len(df)), periode_atr=14)
    assert trades.empty


def test_mfe_ne_regarde_pas_apres_la_sortie():
    closes = np.array([100.0, 98, 120, 120])     # stoppe en 1, envolee ensuite
    df = serie(closes, hauts=np.array([100.0, 98, 120, 120]),
               bas=np.array([100.0, 97, 119, 119]))
    trades = espace_r.evaluer(df, signaux_fixes({0: 1}, len(df), stop=2.0),
                              take_profit_r=2.0, horizon_bougies=3)
    assert trades.loc[0, "raison_sortie"] == espace_r.SL
    assert trades.loc[0, "mfe_r"] < 1.0


# --- enchainement et equity ----------------------------------------------------------

def test_enchainer_supprime_les_trades_qui_se_chevauchent():
    df = serie(np.linspace(100, 130, 30))
    trades = espace_r.evaluer(df, signaux_fixes({i: 1 for i in range(10)}, len(df),
                                                stop=5.0),
                              take_profit_r=3.0, horizon_bougies=10, paire="BTC")
    sequence = espace_r.enchainer(trades)
    assert len(sequence) < len(trades)
    sorties = pd.to_datetime(sequence["ts_sortie"], utc=True).to_numpy()
    entrees = pd.to_datetime(sequence["ts_entree"], utc=True).to_numpy()
    assert all(entrees[i + 1] >= sorties[i] for i in range(len(sequence) - 1))


def test_equity_est_croissante_si_tous_les_trades_gagnent():
    trades = pd.DataFrame({"r": [1.0, 1.0, 1.0],
                           "ts_sortie": pd.date_range("2024-01-01", periods=3, tz="UTC")})
    courbe = espace_r.equity(trades, capital=1000.0, risque_par_trade_pct=1.0)
    assert courbe["equity"].is_monotonic_increasing
    assert courbe["drawdown_pct"].max() == pytest.approx(0.0)


# --- contrats ------------------------------------------------------------------------

def test_candidate_refuse_un_sens_hors_domaine():
    candidate = Candidate(nom="fausse", hypothese="R2",
                          signaux=lambda df: pd.DataFrame({"sens": [7] * len(df)}))
    with pytest.raises(ContratError, match="sens hors"):
        candidate.appliquer(serie(np.array([1.0, 2.0])))


def test_candidate_refuse_une_sortie_desalignee():
    candidate = Candidate(nom="courte", hypothese="R2",
                          signaux=lambda df: pd.DataFrame({"sens": [0]}))
    with pytest.raises(ContratError, match="alignement"):
        candidate.appliquer(serie(np.array([1.0, 2.0, 3.0])))


def test_empreinte_change_avec_les_parametres():
    a = Candidate(nom="x", hypothese="R2", signaux=lambda df: df, parametres={"k": 1})
    b = Candidate(nom="x", hypothese="R2", signaux=lambda df: df, parametres={"k": 2})
    assert a.empreinte != b.empreinte


def test_run_refuse_une_experience_non_preenregistree(tmp_path, monkeypatch):
    monkeypatch.setattr(experiences, "REGISTRE", tmp_path / "vide.jsonl")
    candidate = Candidate(nom="x", hypothese="INEXISTANTE", signaux=lambda df: df)
    with pytest.raises(experiences.ProtocoleError, match="non preenregistree"):
        Run(candidate=candidate, paires=("BTC",), timeframe="4h")


def test_run_refuse_le_holdout_si_le_preenregistrement_ne_l_autorise_pas(tmp_path,
                                                                        monkeypatch):
    registre_test = tmp_path / "exp.jsonl"
    monkeypatch.setattr(experiences, "REGISTRE", registre_test)
    experiences.preenregistrer("T1", "h", "m", {"confirmee": "x"}, split_autorise="train")
    candidate = Candidate(nom="x", hypothese="T1", signaux=lambda df: df)
    with pytest.raises(ContratError, match="hold-out"):
        Run(candidate=candidate, paires=("BTC",), timeframe="4h", split="holdout")


def test_verdict_ne_peut_pas_etre_confirme_avec_une_porte_echouee(tmp_path, monkeypatch):
    monkeypatch.setattr(experiences, "REGISTRE", tmp_path / "exp.jsonl")
    experiences.preenregistrer("T2", "h", "m", {"confirmee": "x"})
    candidate = Candidate(nom="x", hypothese="T2", signaux=lambda df: df)
    run = Run(candidate=candidate, paires=("BTC",), timeframe="4h")
    with pytest.raises(ContratError, match="echoue"):
        Verdict(run=run, issue=CONFIRMEE, portes={"S8_buy_and_hold": False})


def test_verdict_ne_peut_pas_etre_confirme_avec_une_porte_non_executee(tmp_path,
                                                                      monkeypatch):
    monkeypatch.setattr(experiences, "REGISTRE", tmp_path / "exp.jsonl")
    experiences.preenregistrer("T3", "h", "m", {"confirmee": "x"})
    candidate = Candidate(nom="x", hypothese="T3", signaux=lambda df: df)
    run = Run(candidate=candidate, paires=("BTC",), timeframe="4h")
    with pytest.raises(ContratError, match="n'ont pas tourne"):
        Verdict(run=run, issue=CONFIRMEE,
                portes={"S8_buy_and_hold": True, "S3_bootstrap": None})


def test_une_porte_non_executee_n_est_pas_un_echec(tmp_path, monkeypatch):
    monkeypatch.setattr(experiences, "REGISTRE", tmp_path / "exp.jsonl")
    experiences.preenregistrer("T4", "h", "m", {"confirmee": "x"})
    candidate = Candidate(nom="x", hypothese="T4", signaux=lambda df: df)
    run = Run(candidate=candidate, paires=("BTC",), timeframe="4h")
    verdict = Verdict(run=run, portes={"S1_benjamini_hochberg": None,
                                       "S8_buy_and_hold": True})
    assert verdict.portes_echouees == []
    assert verdict.portes_non_executees == ["S1_benjamini_hochberg"]


def _run_de_test(tmp_path, monkeypatch, id_exp: str) -> dict:
    monkeypatch.setattr(experiences, "REGISTRE", tmp_path / "exp.jsonl")
    experiences.preenregistrer(id_exp, "h", "m", {"confirmee": "x"})
    candidate = Candidate(nom="x", hypothese=id_exp, signaux=lambda df: df)
    return {"candidate": candidate, "paires": ("BTC",), "timeframe": "4h"}


def test_deux_runs_a_couts_differents_ont_des_id_differents(tmp_path, monkeypatch):
    """Le bug qui rendait deux mesures differentes indistinguables dans `data/runs/`."""
    base = _run_de_test(tmp_path, monkeypatch, "T5")
    ids = {
        "reference": Run(**base).id,
        "frais": Run(**base, frais_pct=0.20).id,
        "slippage": Run(**base, slippage_pct=0.10).id,
        "sans_spread": Run(**base, spread=False).id,
        "sans_funding": Run(**base, funding=False).id,
    }
    assert len(set(ids.values())) == len(ids), ids


def test_un_run_paie_les_couts_de_detention_par_defaut(tmp_path, monkeypatch):
    base = _run_de_test(tmp_path, monkeypatch, "T6")
    run = Run(**base)
    assert run.spread is True
    assert run.funding is True
    resume = run.resume()
    assert resume["spread"] is True and resume["funding"] is True
    assert resume["frais_pct"] == run.frais_pct
    assert resume["slippage_pct"] == run.slippage_pct
    # Les couts de detention ne sont PAS dans le forfait aller-retour : ils se calculent
    # trade par trade, et confondre les deux ferait payer deux fois.
    assert resume["cout_aller_retour_pct"] == pytest.approx(0.07)


# --- registre ------------------------------------------------------------------------

def test_le_registre_decouvre_les_candidates_du_paquet():
    toutes = registre.toutes()
    assert "r2_mean_reversion" in toutes
    assert toutes["r2_mean_reversion"].hypothese == "R2"
