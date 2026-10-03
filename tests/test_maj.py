"""Mise a jour du lake (03/10) : BETA tient sa copie a jour sans jamais ecrire dans ARIT.

Ce que ces tests protegent : (1) une copie de BETA n'est jamais ecrasee par celle, plus
vieille, d'ARIT ; (2) freqtrade COMPLETE au lieu de tout retelecharger ; (3) un
telechargement macro rate ne detruit pas le fichier en place ; (4) une serie figee se voit.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pandas as pd
import pytest

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from beta import config  # noqa: E402
from beta.lake import maj, telechargement, univers  # noqa: E402

FRED_OK = "observation_date,VIXCLS\n2026-10-01,16.39\n2026-10-02,15.80\n"


@pytest.fixture
def isole(tmp_path, monkeypatch):
    """Un data/ ET un ARIT jetables : aucun test ne touche aux vrais fichiers."""
    data, arit = tmp_path / "data", tmp_path / "arit"
    monkeypatch.setattr(config, "DATA", data)
    monkeypatch.setattr(config, "LAKE", data / "lake")
    monkeypatch.setattr(config, "BRUT", data / "raw")
    monkeypatch.setattr(config, "USERDIR", data / "user_data")
    monkeypatch.setattr(config, "CATALOGUE", data / "lake" / "catalogue.duckdb")
    monkeypatch.setattr(config, "MACRO", data / "macro")
    monkeypatch.setattr(config, "MACRO_GLOBAL", data / "macro" / "global")
    monkeypatch.setattr(config, "ARIT_DATA", arit / "futures")
    monkeypatch.setattr(config, "ARIT_MACRO", arit / "macro")
    monkeypatch.setattr(config, "ARIT_MACRO_GLOBAL", arit / "macro" / "global")
    (arit / "futures").mkdir(parents=True)
    (arit / "macro" / "global").mkdir(parents=True)
    config.preparer_dossiers()
    return tmp_path


def _ecrire(chemin: pathlib.Path, texte: str) -> pathlib.Path:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte, encoding="utf-8")
    return chemin


# --- amorcage --------------------------------------------------------------------------------

def test_amorcer_copie_ce_qui_manque(isole):
    btc = univers.par_base("BTC")
    _ecrire(config.chemin_feather_arit(btc.slug, "1d"), "arit-1d")
    _ecrire(config.ARIT_DATA / f"{btc.slug}-{config.FUNDING_SUFFIXE}.feather", "arit-fr")
    copies = maj.amorcer((btc,))
    assert config.chemin_feather_brut(btc.slug, "1d").read_text() == "arit-1d"
    assert len(copies) == 2


def test_amorcer_n_ecrase_jamais_la_copie_de_beta(isole):
    """La copie de BETA est plus recente des qu'elle a ete completee : la remplacer = reculer."""
    btc = univers.par_base("BTC")
    _ecrire(config.chemin_feather_arit(btc.slug, "1d"), "arit-vieux")
    _ecrire(config.chemin_feather_brut(btc.slug, "1d"), "beta-a-jour")
    assert maj.amorcer((btc,)) == []
    assert config.chemin_feather_brut(btc.slug, "1d").read_text() == "beta-a-jour"


def test_amorcer_ne_modifie_pas_arit(isole):
    btc = univers.par_base("BTC")
    source = _ecrire(config.chemin_feather_arit(btc.slug, "4h"), "arit")
    avant = source.stat().st_mtime_ns
    maj.amorcer((btc,))
    assert source.read_text() == "arit" and source.stat().st_mtime_ns == avant


# --- freqtrade : completer, pas retelecharger ------------------------------------------------

def _argv(paire):
    try:
        return telechargement.commande(paire)
    except telechargement.DownloadError:
        pytest.skip("freqtrade absent")


def test_paire_complete_sur_disque_sans_timerange(isole):
    """Un timerange anterieur a la 1re bougie ferait tout retelecharger (verifie le 03/10)."""
    btc = univers.par_base("BTC")
    for tf in univers.TIMEFRAMES:
        _ecrire(config.chemin_feather_brut(btc.slug, tf), "x")
    assert "--timerange" not in _argv(btc)


def test_paire_incomplete_avec_timerange(isole):
    """Sans timerange, un fichier absent ne recevrait que 30 jours."""
    btc = univers.par_base("BTC")
    _ecrire(config.chemin_feather_brut(btc.slug, "1d"), "x")
    argv = _argv(btc)
    assert argv[argv.index("--timerange") + 1] == f"{btc.depuis}-"


# --- lecture : la copie de BETA d'abord -------------------------------------------------------

def test_funding_lu_dans_la_copie_de_beta_si_elle_existe(isole):
    arit = _ecrire(config.ARIT_DATA / f"BTC_USDT_USDT-{config.FUNDING_SUFFIXE}.feather", "a")
    assert config.chemin_feather_funding("BTC_USDT_USDT") == arit
    propre = _ecrire(config.BRUT / "futures" / arit.name, "b")
    assert config.chemin_feather_funding("BTC_USDT_USDT") == propre


def test_macro_lue_dans_la_copie_de_beta_si_elle_existe(isole):
    arit = _ecrire(config.ARIT_MACRO_GLOBAL / "vix.csv", FRED_OK)
    assert config.chemin_macro("vix.csv", globale=True) == arit
    propre = _ecrire(config.MACRO_GLOBAL / "vix.csv", FRED_OK)
    assert config.chemin_macro("vix.csv", globale=True) == propre


# --- macro -------------------------------------------------------------------------------------

def test_maj_macro_ecrit_les_series(isole, monkeypatch):
    fng = json.dumps({"data": [{"value": "50", "timestamp": "1790985600"}]})

    def faux(url):
        if "alternative.me" in url:
            return fng
        sid = url.rsplit("=", 1)[1]
        return FRED_OK.replace("VIXCLS", sid)

    monkeypatch.setattr(maj, "_telecharger_texte", faux)
    etats = maj.maj_macro()
    assert set(etats.values()) == {"ok"}
    assert (config.MACRO_GLOBAL / "hy_oas.csv").read_text().startswith(
        "observation_date,BAMLH0A0HYM2")
    assert (config.MACRO / "fear_greed.json").exists()


def test_maj_macro_rate_garde_l_ancien_fichier(isole, monkeypatch):
    ancien = _ecrire(config.MACRO_GLOBAL / "vix.csv", FRED_OK)

    def faux(url):
        if "VIXCLS" in url:
            return "<html>maintenance</html>"
        raise OSError("reseau coupe")

    monkeypatch.setattr(maj, "_telecharger_texte", faux)
    etats = maj.maj_macro()
    assert etats["vix.csv"].startswith("echec")
    assert ancien.read_text() == FRED_OK
    assert not list(config.MACRO_GLOBAL.glob("*.partiel"))


# --- fraicheur -------------------------------------------------------------------------------

def test_fraicheur_signale_une_serie_figee(isole):
    _ecrire(config.MACRO_GLOBAL / "vix.csv", FRED_OK)
    maintenant = pd.Timestamp("2026-10-03 10:00", tz="UTC")
    lignes = {f["serie"]: f for f in maj.fraicheur(maintenant)}
    assert not lignes["FRED vix"]["en_retard"]
    assert lignes["FRED hy_oas"]["en_retard"]            # absente
    assert lignes["BTC 1d"]["en_retard"]                 # lake vide
    plus_tard = {f["serie"]: f for f in maj.fraicheur(maintenant + pd.Timedelta(days=10))}
    assert plus_tard["FRED vix"]["en_retard"]


def test_dxy_hebdomadaire_tolere_dix_jours(isole):
    """DTWEXBGS est hebdomadaire : 8 jours de retard ne sont pas une panne."""
    _ecrire(config.MACRO_GLOBAL / "dxy.csv", "observation_date,DTWEXBGS\n2026-09-25,118.1\n")
    lignes = {f["serie"]: f for f in maj.fraicheur(pd.Timestamp("2026-10-03", tz="UTC"))}
    assert not lignes["FRED dxy"]["en_retard"]
    tard = {f["serie"]: f for f in maj.fraicheur(pd.Timestamp("2026-10-20", tz="UTC"))}
    assert tard["FRED dxy"]["en_retard"]
