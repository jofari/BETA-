"""Tests du lake : univers, normalisation, audit des trous, catalogue, lecture, resampling.

Ce que ces tests protegent en priorite : la DETECTION DES TROUS. Une serie trouee ne leve
aucune exception et produit un backtest faux en silence — c'est la panne la plus couteuse
possible dans ce projet, et la seule qui ne se voit jamais a l'oeil nu.
"""

from __future__ import annotations

import pathlib
import sys

import pandas as pd
import pytest

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from beta import config, data, lake, univers  # noqa: E402


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


def _ohlcv(debut="2024-01-01", n=100, freq="1h", trou=None):
    dates = pd.date_range(debut, periods=n, freq=freq, tz="UTC")
    if trou is not None:
        dates = dates.delete(range(trou[0], trou[1]))
    return pd.DataFrame({
        "date": dates,
        "open": range(1, len(dates) + 1),
        "high": [x + 1.0 for x in range(1, len(dates) + 1)],
        "low": [x - 1.0 for x in range(1, len(dates) + 1)],
        "close": [x + 0.5 for x in range(1, len(dates) + 1)],
        "volume": [10.0] * len(dates),
    }).astype({"open": float, "high": float, "low": float, "close": float})


# --- univers : la source de verite unique ---------------------------------------------

def test_univers_compte_six_paires():
    assert len(univers.PAIRES) == 6
    assert {p.base for p in univers.PAIRES} == {"BTC", "ETH", "SOL", "BNB", "LINK", "XRP"}


def test_quatre_paires_importables_deux_a_telecharger():
    assert {p.base for p in univers.a_importer()} == {"BTC", "ETH", "SOL", "BNB"}
    assert {p.base for p in univers.a_telecharger()} == {"LINK", "XRP"}


def test_notations_de_paire():
    btc = univers.par_base("BTC")
    assert btc.symbole == "BTC/USDT:USDT"
    assert btc.slug == "BTC_USDT_USDT"


def test_resoudre_accepte_les_trois_notations():
    for nom in ("LINK", "link", "LINK/USDT:USDT", "LINK_USDT_USDT"):
        assert univers.resoudre(nom).base == "LINK"


def test_paire_hors_univers_refusee():
    with pytest.raises(KeyError, match="hors univers"):
        univers.resoudre("PEPE")


def test_pas_minutes_inconnu_refuse():
    with pytest.raises(KeyError, match="timeframe inconnu"):
        univers.pas_minutes("3s")


# --- normalisation ---------------------------------------------------------------------

def test_normaliser_trie_et_retire_les_doublons():
    df = _ohlcv(n=5)
    melange = pd.concat([df.iloc[[3]], df, df.iloc[[1]]], ignore_index=True)
    propre, doublons = lake.normaliser(melange)
    assert doublons == 2
    assert propre["date"].is_monotonic_increasing
    assert propre["date"].is_unique
    assert len(propre) == 5


def test_normaliser_force_utc():
    df = _ohlcv(n=3)
    df["date"] = df["date"].dt.tz_convert("Europe/Paris")
    propre, _ = lake.normaliser(df)
    assert str(propre["date"].dt.tz) == "UTC"


# --- audit : le coeur du projet --------------------------------------------------------

def test_audit_serie_continue_est_a_cent_pourcent():
    audit = lake.auditer(_ohlcv(n=100, freq="1h"), "1h")
    assert audit["n_bougies"] == 100
    assert audit["bougies_manquantes"] == 0
    assert audit["couverture_pct"] == 100.0
    assert audit["plus_grand_trou_h"] == 1.0


def test_audit_detecte_un_trou():
    """20 bougies retirees au milieu : la couverture doit tomber, le trou etre mesure."""
    audit = lake.auditer(_ohlcv(n=100, freq="1h", trou=(40, 60)), "1h")
    assert audit["n_bougies"] == 80
    assert audit["bougies_attendues"] == 100
    assert audit["bougies_manquantes"] == 20
    assert audit["couverture_pct"] == 80.0
    assert audit["plus_grand_trou_h"] == pytest.approx(21.0)


def test_audit_serie_vide():
    audit = lake.auditer(_ohlcv(n=0), "1h")
    assert audit["n_bougies"] == 0 and audit["couverture_pct"] == 0.0


# --- conversion + catalogue ------------------------------------------------------------

def _deposer_feather(chemin: pathlib.Path, df: pd.DataFrame) -> pathlib.Path:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    df.to_feather(chemin)
    return chemin


def test_convertir_ecrit_parquet_et_catalogue(lake_isole):
    paire = univers.par_base("BTC")
    source = _deposer_feather(lake_isole / "src.feather", _ohlcv(n=50, freq="4h"))
    audit = lake.convertir(paire, "4h", source, origine="test")

    assert audit["n_bougies"] == 50
    assert config.chemin_parquet(paire.slug, "4h").exists()
    etat = lake.etat()
    assert len(etat) == 1
    assert etat.iloc[0]["paire"] == "BTC/USDT:USDT"
    assert not bool(etat.iloc[0]["suspect"])


def test_serie_trouee_est_marquee_suspecte(lake_isole):
    paire = univers.par_base("ETH")
    source = _deposer_feather(lake_isole / "troue.feather",
                              _ohlcv(n=100, freq="1h", trou=(10, 30)))
    lake.convertir(paire, "1h", source, origine="test")
    ligne = lake.etat().iloc[0]
    assert bool(ligne["suspect"])
    assert ligne["bougies_manquantes"] == 20


def test_reconversion_ne_duplique_pas_la_ligne(lake_isole):
    """Le build est idempotent : deux passages laissent UNE ligne, pas deux."""
    paire = univers.par_base("SOL")
    source = _deposer_feather(lake_isole / "s.feather", _ohlcv(n=20, freq="1D"))
    lake.convertir(paire, "1d", source, origine="test")
    lake.convertir(paire, "1d", source, origine="test")
    assert len(lake.etat()) == 1


def test_source_absente_leve_lake_error(lake_isole):
    with pytest.raises(lake.LakeError, match="source absente"):
        lake.convertir(univers.par_base("BNB"), "1h", lake_isole / "nexistepas.feather", "test")


def test_colonnes_manquantes_levent_lake_error(lake_isole):
    source = lake_isole / "incomplet.feather"
    pd.DataFrame({"date": pd.date_range("2024-01-01", periods=3, tz="UTC"),
                  "close": [1.0, 2.0, 3.0]}).to_feather(source)
    with pytest.raises(lake.LakeError, match="colonnes absentes"):
        lake.convertir(univers.par_base("BTC"), "1h", source, "test")


# --- lecture ---------------------------------------------------------------------------

def test_load_relit_ce_qui_a_ete_ecrit(lake_isole):
    paire = univers.par_base("BTC")
    source = _deposer_feather(lake_isole / "b.feather", _ohlcv(n=48, freq="1h"))
    lake.convertir(paire, "1h", source, origine="test")

    df = data.load("BTC", "1h")
    assert len(df) == 48
    assert str(df["date"].dt.tz) == "UTC"
    assert df["date"].is_monotonic_increasing


def test_load_filtre_sur_les_bornes(lake_isole):
    paire = univers.par_base("BTC")
    source = _deposer_feather(lake_isole / "b.feather",
                              _ohlcv(debut="2024-01-01", n=240, freq="1h"))
    lake.convertir(paire, "1h", source, origine="test")

    df = data.load("BTC", "1h", debut="2024-01-05", fin="2024-01-06")
    assert df["date"].min() >= pd.Timestamp("2024-01-05", tz="UTC")
    assert df["date"].max() <= pd.Timestamp("2024-01-06", tz="UTC")


def test_load_absent_leve_data_error(lake_isole):
    with pytest.raises(data.DataError, match="absent du lake"):
        data.load("XRP", "4h")


def test_disponible(lake_isole):
    assert not data.disponible("BTC", "4h")
    source = _deposer_feather(lake_isole / "b.feather", _ohlcv(n=10, freq="4h"))
    lake.convertir(univers.par_base("BTC"), "4h", source, origine="test")
    assert data.disponible("BTC", "4h")


# --- resampling ------------------------------------------------------------------------

def test_resample_15m_depuis_5m(lake_isole):
    """Un timeframe non stocke se derive du 5m — exactement, pas approximativement."""
    paire = univers.par_base("BTC")
    source = _deposer_feather(lake_isole / "m5.feather", _ohlcv(n=60, freq="5min"))
    lake.convertir(paire, "5m", source, origine="test")

    df15 = data.load("BTC", "15m")
    assert len(df15) == 20                       # 60 bougies de 5m = 20 de 15m
    brut = data.load("BTC", "5m")
    assert df15["open"].iloc[0] == brut["open"].iloc[0]          # first
    assert df15["close"].iloc[0] == brut["close"].iloc[2]        # last
    assert df15["high"].iloc[0] == brut["high"].iloc[:3].max()   # max
    assert df15["low"].iloc[0] == brut["low"].iloc[:3].min()     # min
    assert df15["volume"].iloc[0] == brut["volume"].iloc[:3].sum()


def test_resample_horodate_a_l_ouverture(lake_isole):
    """Convention freqtrade : une bougie porte l'heure de son OUVERTURE.

    Se tromper ici decale la serie d'une bougie et fabrique du look-ahead en silence.
    """
    paire = univers.par_base("BTC")
    source = _deposer_feather(lake_isole / "m5.feather",
                              _ohlcv(debut="2024-01-01 00:00", n=12, freq="5min"))
    lake.convertir(paire, "5m", source, origine="test")
    df = data.load("BTC", "30m")
    assert df["date"].iloc[0] == pd.Timestamp("2024-01-01 00:00", tz="UTC")


def test_timeframe_non_derivable_refuse(lake_isole):
    paire = univers.par_base("BTC")
    source = _deposer_feather(lake_isole / "m5.feather", _ohlcv(n=10, freq="5min"))
    lake.convertir(paire, "5m", source, origine="test")
    with pytest.raises(KeyError):
        data.load("BTC", "7m")


# --- telechargement : la commande, sans reseau ----------------------------------------

def test_chemin_de_depot_sans_niveau_exchange():
    """`--datadir` designe deja le dossier de l'exchange : pas de `binance/` en plus.

    Se tromper ici est invisible — le telechargement REUSSIT, la conversion ne trouve rien,
    et le lake reste silencieusement incomplet.
    """
    chemin = config.chemin_feather_brut("LINK_USDT_USDT", "4h")
    assert chemin.parent.name == config.TRADING_MODE
    assert chemin.parent.parent == config.BRUT
    assert config.EXCHANGE not in chemin.parts


def test_preparer_dossiers_cree_les_sous_dossiers_freqtrade(lake_isole):
    """Deux telechargements simultanes creent sinon `logs/` en meme temps -> WinError 183."""
    config.preparer_dossiers()
    for nom in config.USERDIR_SOUS_DOSSIERS:
        assert (config.USERDIR / nom).is_dir()


def test_commande_de_telechargement_sans_erase():
    """`--erase` detruirait une reprise partielle : il ne doit jamais apparaitre."""
    from beta import download
    try:
        argv = download.commande(univers.par_base("LINK"))
    except download.DownloadError:
        pytest.skip("freqtrade absent du PATH")
    assert "--erase" not in argv
    assert "LINK/USDT:USDT" in argv
    assert "download-data" in argv
    assert str(config.BRUT) in argv
    assert "--userdir" in argv          # freqtrade sort en code 2 sans lui
