"""Intraday des vrais marches : agregation, fusion, bougie en cours, rattrapage bride, direct.

Ce que ces tests protegent : une bougie pas finie n'est jamais ecrite ; le 4h se derive du 1h
sur la grille UTC ; une source qui bride arrete le rattrapage sans perdre ce qui a ete lu ; un
jour encore vide n'est pas marque lu ; les ticks du jour ne fabriquent ni 1d partiel ni heure
relue a chaque passage ; les bougies officielles remplacent celles tirees des ticks.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from beta.marches import collecte, intraday, sources


@pytest.fixture
def isole(tmp_path, monkeypatch):
    monkeypatch.setattr(collecte, "DOSSIER", tmp_path / "marches")
    monkeypatch.setattr(intraday.time, "sleep", lambda s: None)
    return tmp_path


def _minutes(jour: str, base: float = 100.0, heures=range(0, 21)) -> pd.DataFrame:
    idx = pd.DatetimeIndex([pd.Timestamp(jour, tz="UTC") + pd.Timedelta(hours=h, minutes=m)
                            for h in heures for m in range(60)], name="date")
    close = base + np.arange(len(idx)) / 100
    return pd.DataFrame({"open": close, "high": close + 0.5, "low": close - 0.5,
                         "close": close, "volume": 1.0}, index=idx)


def test_agregation_ohlcv_sur_la_grille_utc():
    m = _minutes("2026-10-20", heures=[13, 14])
    b5 = intraday.agreger(m, "5m")
    assert len(b5) == 24 and b5.index[0] == pd.Timestamp("2026-10-20 13:00", tz="UTC")
    premiere = m.iloc[:5]
    assert b5.iloc[0].to_dict() == {"open": premiere["open"].iloc[0],
                                    "high": premiere["high"].max(),
                                    "low": premiere["low"].min(),
                                    "close": premiere["close"].iloc[-1], "volume": 5.0}
    h4 = intraday.agreger(intraday.agreger(m, "1h"), "4h")
    assert list(h4.index) == [pd.Timestamp("2026-10-20 12:00", tz="UTC")]


def test_la_bougie_en_cours_n_est_jamais_ecrite():
    idx = pd.date_range("2026-10-21 13:30", periods=4, freq="5min", tz="UTC")
    df = pd.DataFrame({"close": [1.0, 2, 3, 4]}, index=idx)
    garde = intraday.closes_seulement(df, "5m", pd.Timestamp("2026-10-21 13:47", tz="UTC"))
    assert list(garde["close"]) == [1.0, 2.0, 3.0]          # 13:40 finie a 13:45 ; 13:45 en cours


def test_fusion_le_neuf_remplace_et_les_revisions_se_comptent():
    a = pd.DataFrame({"close": [1.0, 2.0, 3.0]},
                     index=pd.date_range("2026-10-20", periods=3, freq="h", tz="UTC"))
    n = pd.DataFrame({"close": [2.5, 3.0, 4.0]},
                     index=pd.date_range("2026-10-20 01:00", periods=3, freq="h", tz="UTC"))
    f, changees = intraday.fusionner(a, n)
    assert list(f["close"]) == [1.0, 2.5, 3.0, 4.0] and changees == 1


def test_yahoo_premier_passage_profond_puis_cinq_jours(isole, monkeypatch):
    demandes = []

    def yahoo(ticker, intervalle, periode):
        demandes.append((intervalle, periode))
        idx = pd.date_range("2026-10-20 13:30", periods=12, freq="5min" if intervalle == "5m"
                            else "1h", tz="UTC")
        return pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 0.0},
                            index=idx)
    monkeypatch.setattr(sources, "yahoo_intraday", yahoo)
    maintenant = pd.Timestamp("2026-10-21 12:00", tz="UTC")
    intraday.maj_yahoo("SPX", maintenant)
    intraday.maj_yahoo("SPX", maintenant)
    assert demandes == [("5m", "60d"), ("1h", "730d"), ("5m", "5d"), ("1h", "5d")]
    assert len(intraday.lire("SPX", "5m")) == 12 and len(intraday.lire("SPX", "4h")) >= 1


def test_rattrapage_bride_s_arrete_proprement_et_garde_ce_qui_est_lu(isole, monkeypatch):
    lus = []

    def jour(instrument, j):
        if len(lus) >= 2:
            raise sources.SourceError("HTTP 503")
        lus.append(j)
        return _minutes(f"{j:%Y-%m-%d}")
    monkeypatch.setattr(sources, "dukascopy_minutes", jour)
    monkeypatch.setitem(intraday.INTRADAY["XAU_SPOT"], "depuis", "2026-10-01")
    maintenant = pd.Timestamp("2026-10-21 12:00", tz="UTC")
    r = intraday.rattraper_dukascopy(maintenant=maintenant, pause_s=0)
    assert r["statut"] == "bride" and r["jours_lus"] == 2
    assert [f"{x:%F}" for x in lus] == ["2026-10-20", "2026-10-19"]     # le plus recent d'abord
    assert r["jours_restants"] == 18
    assert intraday.lire("XAU_SPOT", "1d").index.max() == pd.Timestamp("2026-10-20", tz="UTC")


def test_un_jour_recent_encore_vide_n_est_pas_marque_lu(isole, monkeypatch):
    vide = pd.DataFrame(columns=["open", "high", "low", "close", "volume"],
                        index=pd.DatetimeIndex([], tz="UTC", name="date"))
    monkeypatch.setattr(sources, "dukascopy_minutes", lambda i, j: vide)
    monkeypatch.setitem(intraday.INTRADAY["XAU_SPOT"], "depuis", "2026-10-10")
    maintenant = pd.Timestamp("2026-10-21 00:30", tz="UTC")
    intraday.rattraper_dukascopy(maintenant=maintenant, pause_s=0)
    restants = [f"{j:%F}" for j in intraday.jours_manquants("XAU_SPOT", maintenant)]
    assert restants == ["2026-10-20", "2026-10-19", "2026-10-18"]   # vides mais trop recents


def test_direct_ticks_une_fois_par_heure_sans_1d_partiel_puis_remplaces(isole, monkeypatch):
    appels = []

    def ticks(instrument, heure):
        appels.append(heure.hour)
        idx = pd.date_range(heure, periods=120, freq="30s")
        return pd.DataFrame({"bid": 4000.0 + np.arange(120) / 10, "ask": 4001.0,
                             "volume": 1.0}, index=idx)
    monkeypatch.setattr(sources, "dukascopy_ticks", ticks)
    monkeypatch.setattr(sources, "dukascopy_minutes", lambda i, j: _minutes(f"{j:%F}", 3000.0))
    monkeypatch.setitem(intraday.INTRADAY["XAU_SPOT"], "depuis", "2026-10-20")
    intraday.direct_dukascopy(maintenant=pd.Timestamp("2026-10-21 02:10", tz="UTC"))
    intraday.direct_dukascopy(maintenant=pd.Timestamp("2026-10-21 02:40", tz="UTC"))
    assert appels == [0, 1]                                     # chaque heure finie, une fois
    assert intraday.lire("XAU_SPOT", "1d").index.max() == pd.Timestamp("2026-10-20", tz="UTC")
    assert intraday.lire("XAU_SPOT", "1h").loc["2026-10-21 01:00", "close"] == pytest.approx(
        4011.9)
    # La journee publiee remplace les bougies tirees des ticks.
    intraday.rattraper_dukascopy(maintenant=pd.Timestamp("2026-10-22 06:00", tz="UTC"),
                                 pause_s=0)
    assert intraday.lire("XAU_SPOT", "1h").loc["2026-10-21 01:00", "close"] < 3100


def _heures(mois: str, base: float = 2000.0) -> pd.DataFrame:
    idx = pd.date_range(mois, pd.Timestamp(mois) + pd.offsets.MonthEnd(1)
                        + pd.Timedelta(hours=23), freq="h", tz="UTC", name="date")
    close = base + np.arange(len(idx)) / 10
    return pd.DataFrame({"open": close, "high": close + 1, "low": close - 1,
                         "close": close, "volume": 1.0}, index=idx)


def test_rattrapage_par_mois_remplit_1h_et_1d_sans_toucher_aux_jours_lus_a_la_minute(
        isole, monkeypatch):
    monkeypatch.setitem(intraday.INTRADAY["XAU_SPOT"], "depuis", "2026-08-15")
    monkeypatch.setattr(sources, "dukascopy_minutes", lambda i, j: _minutes(f"{j:%F}", 3000.0))
    maintenant = pd.Timestamp("2026-10-21 12:00", tz="UTC")
    intraday.rattraper_dukascopy(limite=1, maintenant=maintenant, pause_s=0)   # le 20/10
    lus = []

    def mois(instrument, m):
        lus.append(f"{m:%Y-%m}")
        return _heures(f"{m:%Y-%m}-01") if m.month == 9 else _heures("2026-08-01", 1000.0)
    monkeypatch.setattr(sources, "dukascopy_heures_mois", mois)
    r = intraday.rattraper_mois(maintenant=maintenant, pause_s=0)
    assert lus == ["2026-09", "2026-08"]                 # mois termines, le plus recent d'abord
    assert r == {"statut": "ok", "mois_lus": 2, "mois_restants": 0}
    h1, d1 = intraday.lire("XAU_SPOT", "1h"), intraday.lire("XAU_SPOT", "1d")
    assert h1.index.min() == pd.Timestamp("2026-08-01", tz="UTC")
    assert d1.loc[pd.Timestamp("2026-09-30", tz="UTC"), "close"] == _heures("2026-09-01")[
        "close"].iloc[-1]
    assert d1.loc[pd.Timestamp("2026-10-20", tz="UTC"), "close"] >= 3000.0   # la minute garde
    assert intraday.rattraper_mois(maintenant=maintenant, pause_s=0)["mois_lus"] == 0


def test_rattrapage_par_mois_bride_garde_les_mois_lus(isole, monkeypatch):
    monkeypatch.setitem(intraday.INTRADAY["XAU_SPOT"], "depuis", "2026-05-01")
    n = []

    def mois(instrument, m):
        if n:
            raise sources.SourceError("HTTP 429")
        n.append(m)
        return _heures(f"{m:%Y-%m}-01")
    monkeypatch.setattr(sources, "dukascopy_heures_mois", mois)
    r = intraday.rattraper_mois(maintenant=pd.Timestamp("2026-10-21", tz="UTC"), pause_s=0)
    assert r == {"statut": "bride", "mois_lus": 1, "mois_restants": 4}
