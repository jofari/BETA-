"""La jointure funding/macro est CAUSALE : une bougie ne voit que le passe.

C'est la propriete la plus critique du moteur (chantiers D5/D6) : un look-ahead dans la
jointure fabriquerait exactement le faux gagnant que la batterie S1-S9 est censee tuer.
"""

from __future__ import annotations

import pandas as pd
import pytest

from beta.lake import lecture
from beta.moteur import pipeline


def _df(n: int = 12) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n, freq="4h", tz="UTC")
    return pd.DataFrame({"date": dates, "open": 100.0, "high": 101.0,
                         "low": 99.0, "close": 100.0, "volume": 1.0})


@pytest.fixture
def sans_macro(monkeypatch):
    """Isole la jointure funding : pas de F&G ni de series globales."""
    monkeypatch.setattr(lecture, "fear_greed",
                        lambda: pd.DataFrame({"date": [], "fng": []}))
    monkeypatch.setattr(lecture, "macro_globales", lambda: pd.DataFrame())


def test_funding_regle_exactement_a_l_ouverture_est_exclu(sans_macro, monkeypatch):
    """Un funding regle exactement a l'ouverture de la bougie n'est PAS encore certain."""
    fr = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01 00:00", "2024-01-01 08:00"], utc=True),
        "funding_rate": [0.01, 0.02],
    })
    monkeypatch.setattr(lecture, "funding", lambda p: fr)
    joint = pipeline._joindre_funding(_df(), "BTC")
    # 00:00 : aucun reglement strictement avant -> NaN
    assert pd.isna(joint["funding_rate"].iloc[0])
    # 04:00 : le reglement de 00:00 est strictement avant -> 0.01 (pas 0.02)
    assert joint["funding_rate"].iloc[1] == pytest.approx(0.01)
    # 08:00 : le reglement de 08:00 est EXCLU (exact) -> encore 0.01
    assert joint["funding_rate"].iloc[2] == pytest.approx(0.01)


def test_macro_decale_d_un_jour(monkeypatch):
    """Le F&G du jour D ne doit JAMAIS apparaître avant D+1 (pas de look-ahead)."""
    monkeypatch.setattr(lecture, "fear_greed", lambda: pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"], utc=True),
        "fng": [10.0, 20.0, 30.0],
    }))
    monkeypatch.setattr(lecture, "macro_globales", lambda: pd.DataFrame())
    df = _df(18)          # 3 jours en 4h
    joint = pipeline._joindre_macro(df)
    j1 = joint.loc[joint["date"].dt.date == pd.Timestamp("2024-01-01").date(), "fng"]
    j2 = joint.loc[joint["date"].dt.date == pd.Timestamp("2024-01-02").date(), "fng"]
    # Le 01/01, le F&G du 01/01 (10.0) n'est pas encore connu
    assert not (j1 == 10.0).any()
    # Le 02/01, le F&G du 01/01 (10.0) est visible, mais celui du 02/01 (20.0) ne l'est pas
    assert (j2 == 10.0).any()
    assert not (j2 == 20.0).any()


def test_macro_weekend_forward_fill(monkeypatch):
    """Le NaN du week-end (series FRED jours ouvres) est comble par la valeur de vendredi,
    et ne se propage PAS au lundi via le decalage."""
    monkeypatch.setattr(lecture, "fear_greed", lambda: pd.DataFrame({
        "date": pd.to_datetime(["2024-01-05", "2024-01-06", "2024-01-07", "2024-01-08"],
                               utc=True),
        "fng": [50.0, 60.0, 70.0, 80.0],          # fng quotidien, week-end compris
    }))
    # globales FRED : jours ouvres seulement (pas de 06/01 ni 07/01)
    glob = pd.DataFrame({"baa10y": [1.5, 1.6]},
                        index=pd.to_datetime(["2024-01-05", "2024-01-08"], utc=True))
    monkeypatch.setattr(lecture, "macro_globales", lambda: glob)
    df = _df(24)          # 4 jours en 4h
    joint = pipeline._joindre_macro(df)
    # Le lundi 08/01 ne doit PAS avoir de NaN (le vendredi 05/01 est forward-fill)
    lundi = joint.loc[joint["date"].dt.date == pd.Timestamp("2024-01-08").date(), "baa10y"]
    assert lundi.notna().all()


def test_join_est_causal_par_troncature(sans_macro, monkeypatch):
    """Tronquer la serie a t ne change pas les valeurs jointes avant t."""
    fr = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01 00:00", "2024-01-01 08:00",
                                "2024-01-01 16:00"], utc=True),
        "funding_rate": [0.01, 0.02, 0.03],
    })
    monkeypatch.setattr(lecture, "funding", lambda p: fr)
    df = _df(9)
    plein = pipeline._joindre_funding(df, "BTC")["funding_rate"]
    tronque = pipeline._joindre_funding(df.iloc[:6], "BTC")["funding_rate"]
    # les 6 premieres valeurs sont identiques, avec ou sans les bougies suivantes
    pd.testing.assert_series_equal(tronque, plein.iloc[:6], check_names=False)
