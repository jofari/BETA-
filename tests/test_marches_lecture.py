"""Lecture des marches intraday par le moteur (R13, R14 : 04/11/2026).

Serie ecrite par le test dans un dossier temporaire : jamais la source vivante.
"""
from __future__ import annotations

import pandas as pd
import pytest

from beta import config
from beta.lake import lecture, univers


@pytest.fixture
def marches(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MARCHES", tmp_path)
    dates = pd.date_range("2024-03-01 13:30", periods=8, freq="1h", tz="UTC")
    df = pd.DataFrame({"date": dates, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5,
                       "volume": 0.0})
    df.to_parquet(tmp_path / "NDX-1h.parquet", index=False)
    return tmp_path


def test_un_marche_intraday_se_resout_et_n_a_ni_funding_ni_fng():
    for nom in ("NDX", "XAU_SPOT", "marches:ndx"):
        actif = univers.resoudre(nom)
        assert univers.est_intraday(actif) and univers.est_indice(actif)
    # Les noms du lake gardent leur sens : NASDAQ = Composite yfinance, XAUUSD = future COMEX.
    assert not univers.est_intraday(univers.resoudre("NASDAQ"))
    assert not univers.est_intraday(univers.resoudre("XAUUSD"))


def test_la_lecture_va_dans_data_marches_et_borne_les_dates(marches):
    df = lecture.load("NDX", "1h", fin="2024-03-01 16:00")
    assert len(df) == 3 and str(df["date"].dt.tz) == "UTC"
    assert lecture.disponible("NDX", "1h")
    assert not lecture.disponible("NDX", "5m")          # absent du dossier temporaire


def test_un_timeframe_non_stocke_n_est_pas_derive(marches):
    with pytest.raises(lecture.DataError):
        lecture.load("NDX", "4h")
