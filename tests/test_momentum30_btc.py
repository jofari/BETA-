"""Tests de coherence du moteur MOMENTUM30_BTC, sur donnees synthetiques seulement."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from beta.invest import nulls
from beta.momentum30_btc import moteur


def _jours(n: int, debut: str = "2020-01-01") -> pd.DatetimeIndex:
    return pd.date_range(debut, periods=n, freq="D", tz="UTC")


def test_exposition_causale_et_alignee():
    rng = np.random.default_rng(1)
    close = 100 * np.cumprod(1 + rng.normal(0, 0.02, 400))
    e = moteur.exposition(close, 30)
    assert np.isnan(e[:31]).all() and not np.isnan(e[31:]).any()
    # prefixe : l'exposition d'un jour ne depend que des clotures qui le precedent
    for t in (50, 120, 399):
        assert np.array_equal(moteur.exposition(close[:t], 30)[31:], e[31:t], equal_nan=True)
    # valeur : e[i] lit close[i-1] contre close[i-31]
    i = 200
    assert e[i] == (1.0 if close[i - 1] > close[i - 31] else 0.0)


def test_hold_sans_couts_reproduit_le_ratio_des_clotures():
    close = np.array([100.0, 110.0, 99.0, 120.0, 130.0])
    r_b = moteur.rendements_bruts(close)[1:]
    z = np.zeros(len(r_b))
    h = moteur.hold(r_b, z, z)
    assert h["rendement_total"] == pytest.approx(130.0 / 100.0 - 1.0)
    assert h["expo_moyenne"] == 1.0 and h["changements_expo"] == 0


def test_couts_funding_et_cash():
    r_b = np.array([0.01, 0.02, -0.01, 0.03])
    e = np.array([0.0, 1.0, 1.0, 0.0])
    phi = np.array([0.001, 0.001, 0.001, 0.001])
    rf = np.array([0.0001] * 4)
    net = moteur.rendement_net(e, r_b, phi, rf, kappa_pb=6.0)
    # jour 1 : cash ; jour 2 : entree (6 pb) + funding ; jour 3 : funding ; jour 4 : sortie + cash
    attendu = np.array([0.0001, 0.02 - 6e-4 - 0.001, -0.01 - 0.001, -6e-4 + 0.0001])
    assert np.allclose(net["r"], attendu)
    assert net["turnover"] == 2.0


def test_rendement_net_refuse_les_nan():
    with pytest.raises(ValueError):
        moteur.rendement_net(np.array([np.nan, 1.0]), np.zeros(2), np.zeros(2), np.zeros(2))


def test_funding_journalier_somme_les_trois_reglements_du_jour():
    jours = _jours(2)
    dates = pd.to_datetime(["2020-01-01 00:00", "2020-01-01 08:00", "2020-01-01 16:00",
                            "2020-01-02 00:00", "2020-01-02 08:00", "2020-01-02 16:00",
                            "2020-01-03 00:00"], utc=True)
    f = pd.DataFrame({"date": dates, "funding_rate": [9.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]})
    phi = moteur.funding_journalier(f, jours)
    # ]01 00:00 ; 02 00:00] = 1+2+3 ; ]02 00:00 ; 03 00:00] = 4+5+6 ; le 9.0 de 01 00:00 est exclu
    assert np.allclose(phi, [6.0, 15.0])
    with pytest.raises(ValueError):
        moteur.funding_journalier(f, _jours(3))


def test_verdict_mecanique():
    ok = {"sharpe_superieur": True, "cagr_superieur_ou_egal": True, "drawdown_moins_profond": True}
    assert moteur.verdict(ok, 0.01) == "confirmee"
    assert moteur.verdict(ok, 0.10) == "indecidable"
    assert moteur.verdict(ok, 0.30) == "infirmee"
    assert moteur.verdict(ok, None) == "indecidable"
    assert moteur.verdict({**ok, "cagr_superieur_ou_egal": False}, 0.01) == "infirmee"


def test_nulls_decalage_zero_redonne_l_observe_et_p_dans_les_bornes():
    rng = np.random.default_rng(3)
    n = 400
    r_b = rng.normal(0.001, 0.03, n)
    e = (rng.random(n) > 0.5).astype(float)
    phi = np.full(n, 1e-4)
    rf = np.zeros(n)
    obs = moteur._sharpe(e, r_b, phi, rf, 6.0)
    assert moteur._sharpe(np.roll(e, 0), r_b, phi, rf, 6.0) == obs
    res = moteur.nulls_sharpe(e, r_b, phi, rf, b=50, graine=0)
    assert res["observe"] == obs
    for nom in ("circulaire", "segments"):
        assert 1 / 51 <= res[nom]["p"] <= 1.0
    assert res["p_retenue"] == max(res["circulaire"]["p"], res["segments"]["p"])
    # memes graines => memes tirages (flux derive par cle)
    assert moteur.nulls_sharpe(e, r_b, phi, rf, b=50, graine=0) == res


def test_segments_conserves_par_le_melange():
    rng = nulls.flux(0, "test")
    e = np.array([1.0] * 5 + [0.0] * 3 + [1.0] * 2 + [0.0] * 7)
    m = nulls.melange_segments(e, rng)
    assert sorted(nulls.segments(m)) == sorted(nulls.segments(e))


def test_par_annee():
    jours = _jours(400)
    r_b = np.full(400, 0.001)
    e = np.ones(400)
    t = moteur.par_annee(jours, r_b, r_b, e)
    assert list(t.index) == [2020, 2021] and t.loc[2020, "jours"] == 366
