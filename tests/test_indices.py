"""Tests du spike indices/ETF (14/09) : univers, lecture 1d seule, schema parquet, jointures.

Ce que ces tests protegent en priorite : qu'un indice entre au lake par la MEME porte que les
perpetuels (schema identique, catalogue renseigne), et qu'il en ressorte sans les colonnes
qui ne le concernent pas (funding, Fear & Greed) — sans jamais planter le pipeline.
"""

from __future__ import annotations

import pathlib
import sys

import pandas as pd
import pyarrow.parquet as pq
import pytest

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from beta import config  # noqa: E402
from beta.lake import catalogue, construction, lecture, telechargement, univers  # noqa: E402
from beta.moteur import pipeline  # noqa: E402


@pytest.fixture
def lake_isole(tmp_path, monkeypatch):
    """Un lake jetable : aucun test ne doit toucher au vrai `data/`."""
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "LAKE", tmp_path / "lake")
    monkeypatch.setattr(config, "BRUT", tmp_path / "raw")
    monkeypatch.setattr(config, "USERDIR", tmp_path / "user_data")
    monkeypatch.setattr(config, "CATALOGUE", tmp_path / "lake" / "catalogue.duckdb")
    config.preparer_dossiers()
    return tmp_path


def _brut_yfinance(n: int = 10, debut: str = "2024-01-01", tz: str = "America/New_York",
                   nan_a: int | None = None) -> pd.DataFrame:
    """Ce que rend `yfinance.Ticker.history` : jours ouvres, index dans le fuseau de la bourse,
    colonnes capitalisees, volume entier."""
    index = pd.bdate_range(debut, periods=n).tz_localize(tz)
    brut = pd.DataFrame({
        "Open": [100.0 + i for i in range(n)], "High": [101.0 + i for i in range(n)],
        "Low": [99.0 + i for i in range(n)], "Close": [100.5 + i for i in range(n)],
        "Adj Close": [100.5 + i for i in range(n)], "Volume": [1000 + i for i in range(n)],
    }, index=index)
    brut.index.name = "Date"
    if nan_a is not None:
        brut.iloc[nan_a, brut.columns.get_loc("Close")] = float("nan")
    return brut


def _ohlcv_1d(dates: pd.DatetimeIndex) -> pd.DataFrame:
    n = len(dates)
    return pd.DataFrame({"date": dates, "open": [1.0] * n, "high": [2.0] * n,
                         "low": [0.5] * n, "close": [1.5] * n, "volume": [10.0] * n})


# --- univers ---------------------------------------------------------------------------

def test_univers_compte_cinq_indices_et_toujours_six_paires():
    assert {i.base for i in univers.INDICES} == {"SP500", "NASDAQ", "CAC40", "MSCIWORLD",
                                                  "XAUUSD"}
    assert {i.ticker for i in univers.INDICES} == {"^GSPC", "^IXIC", "^FCHI", "URTH", "GC=F"}
    assert len(univers.PAIRES) == 6                 # le spike n'a rien change cote crypto


def test_indice_slug_et_symbole():
    sp = univers.resoudre("SP500")
    assert univers.est_indice(sp)
    assert sp.slug == "SP500" and sp.symbole == "^GSPC"
    assert config.chemin_parquet(sp.slug, "1d").name == "SP500-1d.parquet"


def test_resoudre_indice_par_base_slug_et_ticker():
    for nom in ("SP500", "sp500", " SP500 ", "^GSPC", "^gspc"):
        assert univers.resoudre(nom).base == "SP500"
    assert univers.resoudre("gc=f").base == "XAUUSD"
    assert univers.resoudre("URTH").base == "MSCIWORLD"


def test_resoudre_paire_reste_une_paire():
    assert not univers.est_indice(univers.resoudre("BTC"))
    assert univers.resoudre("BTC_USDT_USDT").symbole == "BTC/USDT:USDT"


def test_actif_hors_univers_refuse_avec_les_deux_listes():
    with pytest.raises(KeyError, match="hors univers.*SP500"):
        univers.resoudre("DAX")


def test_timeframes_de():
    assert univers.timeframes_de(univers.resoudre("SP500")) == ("1d",)
    assert univers.timeframes_de(univers.resoudre("BTC")) == univers.TIMEFRAMES


# --- lecture : 1d seulement, pas de funding ------------------------------------------

def test_table_source_indice_refuse_tout_sauf_1d():
    sp = univers.resoudre("SP500")
    assert lecture._table_source(sp, "1d") == ("1d", False)
    for timeframe in ("4h", "1h", "5m", "15m"):
        with pytest.raises(lecture.DataError, match="seul le 1d"):
            lecture._table_source(sp, timeframe)


def test_disponible_indice_hors_1d_est_faux_sans_lever(lake_isole):
    assert lecture.disponible("SP500", "4h") is False
    assert lecture.disponible("SP500", "1d") is False


def test_funding_indice_leve_data_error_pas_key_error():
    with pytest.raises(lecture.DataError, match="indice"):
        lecture.funding("XAUUSD")


# --- yfinance -> lake ------------------------------------------------------------------

def test_normaliser_yfinance_minuit_utc_colonnes_minuscules():
    df = telechargement.normaliser_yfinance(_brut_yfinance(5), aujourd_hui="2024-02-01")
    assert list(df.columns) == list(construction.COLONNES)
    assert str(df["date"].dt.tz) == "UTC"
    assert (df["date"].dt.hour == 0).all() and (df["date"].dt.minute == 0).all()
    # la date calendaire de la seance est conservee telle quelle, pas decalee par le fuseau
    assert df["date"].iloc[0] == pd.Timestamp("2024-01-01", tz="UTC")
    assert df["volume"].dtype == float and "Adj Close" not in df.columns


def test_normaliser_yfinance_retire_nan_et_bougie_du_jour():
    brut = _brut_yfinance(5, nan_a=2)                       # 1er au 5 janvier 2024
    df = telechargement.normaliser_yfinance(brut, aujourd_hui="2024-01-05 14:00")
    dates = [d.date().isoformat() for d in df["date"]]
    assert "2024-01-03" not in dates                        # NaN retire
    assert "2024-01-05" not in dates                        # seance en cours retiree
    assert dates == ["2024-01-01", "2024-01-02", "2024-01-04"]


def test_normaliser_yfinance_vide():
    assert telechargement.normaliser_yfinance(pd.DataFrame()).empty


def test_deposer_indice_ecrit_le_schema_exact_du_lake(lake_isole):
    """Meme schema que les perpetuels : TIMESTAMPTZ ms + 5 DOUBLE. Un fichier 'presque
    pareil' (date en ns, volume entier) casserait une jointure DuckDB plus tard."""
    sp = univers.resoudre("SP500")
    df = telechargement.normaliser_yfinance(_brut_yfinance(10), aujourd_hui="2024-02-01")
    audit = construction.deposer(sp, "1d", df, "test", calendrier=construction.CALENDRIER_OUVRE)

    cible = config.chemin_parquet("SP500", "1d")
    assert cible.exists() and audit["n_bougies"] == 10
    assert pq.read_schema(cible).remove_metadata().equals(construction.SCHEMA_PARQUET)

    ligne = catalogue.etat().iloc[0]
    assert ligne["paire"] == "^GSPC" and ligne["marche"] == univers.MARCHE_INDICES
    assert ligne["couverture_pct"] == 100.0 and not bool(ligne["suspect"])

    relu = lecture.load("SP500", "1d")
    assert len(relu) == 10 and str(relu["date"].dt.tz) == "UTC"
    assert relu["date"].is_monotonic_increasing


def test_convertir_crypto_ecrit_le_meme_schema(lake_isole):
    """Le schema est impose a TOUT le lake, pas seulement aux indices."""
    dates = pd.date_range("2024-01-01", periods=5, freq="1D", tz="UTC")
    source = lake_isole / "btc.feather"
    _ohlcv_1d(dates).to_feather(source)
    construction.convertir(univers.par_base("BTC"), "1d", source, origine="test")
    schema = pq.read_schema(config.chemin_parquet("BTC_USDT_USDT", "1d")).remove_metadata()
    assert schema.equals(construction.SCHEMA_PARQUET)


def test_telecharger_indices_sans_reseau(lake_isole, monkeypatch):
    """L'appel reseau est remplace ; tout le reste (normalisation, parquet, catalogue) tourne."""
    monkeypatch.setattr(telechargement, "_historique", lambda indice: _brut_yfinance(8))
    resultats = telechargement.telecharger_indices()
    assert resultats == {i.base: "ok" for i in univers.INDICES}
    for indice in univers.INDICES:
        assert lecture.disponible(indice.base, "1d")
    assert len(catalogue.etat()) == 5


def test_telecharger_indices_un_echec_n_annule_pas_les_autres(lake_isole, monkeypatch):
    def historique(indice):
        if indice.base == "CAC40":
            raise telechargement.DownloadError("429 Too Many Requests")
        return _brut_yfinance(8)
    monkeypatch.setattr(telechargement, "_historique", historique)
    resultats = telechargement.telecharger_indices()
    assert resultats["CAC40"].startswith("echec")
    assert sum(1 for v in resultats.values() if v == "ok") == 4
    assert not lecture.disponible("CAC40", "1d")


# --- audit en jours ouvres -------------------------------------------------------------

def test_audit_ouvre_le_week_end_n_est_pas_un_trou():
    dates = pd.bdate_range("2024-01-01", "2024-01-12", tz="UTC")     # 2 semaines ouvrees
    audit = construction.auditer(_ohlcv_1d(dates), "1d", calendrier="ouvre")
    assert audit["bougies_attendues"] == 10 and audit["bougies_manquantes"] == 0
    assert audit["couverture_pct"] == 100.0
    assert audit["plus_grand_trou_h"] == pytest.approx(72.0)        # vendredi -> lundi


def test_audit_ouvre_compte_un_jour_ouvre_manquant():
    dates = pd.bdate_range("2024-01-01", "2024-01-12", tz="UTC").delete(2)   # mercredi 3
    audit = construction.auditer(_ohlcv_1d(dates), "1d", calendrier="ouvre")
    assert audit["bougies_attendues"] == 10 and audit["bougies_manquantes"] == 1
    assert audit["couverture_pct"] == 90.0


def test_audit_continu_inchange_pour_les_perpetuels():
    dates = pd.date_range("2024-01-01", periods=14, freq="1D", tz="UTC")
    audit = construction.auditer(_ohlcv_1d(dates), "1d")
    assert audit["bougies_attendues"] == 14 and audit["couverture_pct"] == 100.0


def test_audit_ouvre_refuse_un_autre_timeframe():
    dates = pd.date_range("2024-01-01", periods=3, freq="4h", tz="UTC")
    with pytest.raises(construction.LakeError, match="1d seulement"):
        construction.auditer(_ohlcv_1d(dates), "4h", calendrier="ouvre")


def test_indice_suspect_sur_trou_de_plus_de_sept_jours(lake_isole):
    """96 % de couverture passe la tolerance ouvree, mais une semaine entiere qui manque
    doit quand meme marquer la serie : c'est le second critere."""
    dates = pd.bdate_range("2024-01-01", "2024-06-28", tz="UTC")
    semaine = [d for d in dates if pd.Timestamp("2024-03-04", tz="UTC") <= d
               <= pd.Timestamp("2024-03-08", tz="UTC")]
    trouee = dates.drop(semaine)
    construction.deposer(univers.resoudre("CAC40"), "1d", _ohlcv_1d(trouee), "test",
                         calendrier=construction.CALENDRIER_OUVRE)
    ligne = catalogue.etat().iloc[0]
    assert ligne["couverture_pct"] > 94.0
    assert bool(ligne["suspect"])


def test_indice_jours_feries_pas_suspect(lake_isole):
    """~4 % de jours feries isoles : declares au catalogue (manquantes > 0), pas suspects."""
    dates = pd.bdate_range("2024-01-01", "2024-12-31", tz="UTC")
    feries = dates[5::25]                  # ~10 jours isoles, ni le premier ni le dernier
    construction.deposer(univers.resoudre("SP500"), "1d", _ohlcv_1d(dates.drop(feries)),
                         "test", calendrier=construction.CALENDRIER_OUVRE)
    ligne = catalogue.etat().iloc[0]
    assert ligne["bougies_manquantes"] == len(feries)
    assert not bool(ligne["suspect"])


# --- pipeline : funding ignore, F&G ignore, FRED joint --------------------------------

def _df_1d(n: int = 6) -> pd.DataFrame:
    return _ohlcv_1d(pd.date_range("2024-01-01", periods=n, freq="1D", tz="UTC"))


def test_joindre_funding_indice_rend_df_inchange(monkeypatch):
    def jamais(paire):
        raise AssertionError("le funding ne doit pas etre cherche pour un indice")
    monkeypatch.setattr(lecture, "funding", jamais)
    df = _df_1d()
    joint = pipeline._joindre_funding(df, "SP500")
    pd.testing.assert_frame_equal(joint, df)
    assert "funding_rate" not in joint.columns


def test_joindre_macro_indice_sans_fng_mais_avec_fred(monkeypatch):
    monkeypatch.setattr(lecture, "fear_greed", lambda: pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01", "2024-01-02"], utc=True), "fng": [10.0, 20.0]}))
    glob = pd.DataFrame({"vix": [15.0, 16.0]},
                        index=pd.to_datetime(["2024-01-01", "2024-01-02"], utc=True))
    monkeypatch.setattr(lecture, "macro_globales", lambda: glob)

    joint = pipeline._joindre_macro(_df_1d(), "SP500")
    assert "fng" not in joint.columns                    # crypto-only
    assert "vix" in joint.columns                        # FRED : pertinent, joint
    # Meme regle de decalage que pour les paires : la valeur du jour D est datee D+1 puis
    # jointe STRICTEMENT avant l'ouverture. Une bougie 1d ouvre a minuit, donc la bougie
    # D+1 ne la voit pas encore (egalite exclue) : elle apparait a la bougie D+2. C'est le
    # sens conservateur, et c'est deja ce que voit le 1d crypto.
    assert pd.isna(joint["vix"].iloc[0]) and pd.isna(joint["vix"].iloc[1])
    assert joint["vix"].iloc[2] == pytest.approx(15.0)
    assert joint["vix"].iloc[3] == pytest.approx(16.0)


def test_joindre_macro_paire_garde_le_fng(monkeypatch):
    monkeypatch.setattr(lecture, "fear_greed", lambda: pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01"], utc=True), "fng": [10.0]}))
    monkeypatch.setattr(lecture, "macro_globales", lambda: pd.DataFrame())
    joint = pipeline._joindre_macro(_df_1d(), "BTC")
    assert "fng" in joint.columns
    assert joint["fng"].iloc[2] == pytest.approx(10.0)   # bougie D+2, cf. test precedent


def test_joindre_macro_indice_sans_aucune_macro_rend_df_inchange(monkeypatch):
    monkeypatch.setattr(lecture, "fear_greed", lambda: pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01"], utc=True), "fng": [10.0]}))
    monkeypatch.setattr(lecture, "macro_globales", lambda: pd.DataFrame())
    df = _df_1d()
    pd.testing.assert_frame_equal(pipeline._joindre_macro(df, "XAUUSD"), df)
