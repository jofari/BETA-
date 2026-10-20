"""Les perpetuels TradFi au lake (Jonas, 20/10) : or, QQQ (NASDAQ-100), SPY (S&P 500).

Ce que ces tests protegent : ils entrent au lake comme les 6 paires (memes timeframes, meme
porte freqtrade -> parquet -> catalogue, funding compris), SANS entrer dans `univers.PAIRES` —
les mesures qui parcourent l'univers crypto ne changent pas — et une panne de leur mise a jour
ne retire rien aux autres.
"""

from __future__ import annotations

import pandas as pd
import pytest

from beta import config
from beta.lake import construction, maj, telechargement, univers


@pytest.fixture
def isole(tmp_path, monkeypatch):
    for nom, chemin in (("DATA", tmp_path), ("LAKE", tmp_path / "lake"),
                        ("BRUT", tmp_path / "raw"), ("USERDIR", tmp_path / "user_data"),
                        ("CATALOGUE", tmp_path / "lake" / "catalogue.duckdb"),
                        ("MACRO", tmp_path / "macro"),
                        ("MACRO_GLOBAL", tmp_path / "macro" / "global"),
                        ("ARIT_DATA", tmp_path / "arit"), ("ARIT_MACRO", tmp_path / "arit_m"),
                        ("ARIT_MACRO_GLOBAL", tmp_path / "arit_m" / "global")):
        monkeypatch.setattr(config, nom, chemin)
    config.preparer_dossiers()
    return tmp_path


def test_trois_perpetuels_tradfi_hors_des_6_paires():
    assert [p.base for p in univers.TRADFI] == ["XAU", "QQQ", "SPY"]
    assert [p.symbole for p in univers.TRADFI] == ["XAU/USDT:USDT", "QQQ/USDT:USDT",
                                                   "SPY/USDT:USDT"]
    assert len(univers.PAIRES) == 6 and len(univers.symboles()) == 6
    assert not {p.base for p in univers.TRADFI} & {p.base for p in univers.PAIRES}


def test_tradfi_demandes_depuis_leur_cotation():
    assert {p.base: p.depuis for p in univers.TRADFI} == {
        "XAU": "20251211", "QQQ": "20260406", "SPY": "20260406"}


def test_resoudre_tradfi_sans_collision_avec_les_indices():
    assert univers.resoudre("XAU") is univers.TRADFI[0]
    assert univers.resoudre("QQQ/USDT:USDT").base == "QQQ"
    assert univers.resoudre("spy_usdt_usdt").base == "SPY"
    assert univers.est_indice(univers.resoudre("XAUUSD"))      # l'or yfinance reste l'indice
    assert univers.timeframes_de(univers.resoudre("XAU")) == univers.TIMEFRAMES


def test_maj_tradfi_telecharge_puis_integre_les_4_timeframes(isole, monkeypatch):
    telecharges, integres = [], []

    def faux_telecharger(paires, **_):
        for p in paires:
            telecharges.append(p.base)
            for tf in univers.TIMEFRAMES:
                config.chemin_feather_brut(p.slug, tf).parent.mkdir(parents=True, exist_ok=True)
                config.chemin_feather_brut(p.slug, tf).write_bytes(b"x")
        return {p.base: "ok" for p in paires}

    monkeypatch.setattr(telechargement, "telecharger", faux_telecharger)
    monkeypatch.setattr(construction, "integrer_telechargement",
                        lambda p, tf: integres.append((p.base, tf)) or {})
    assert maj.mettre_a_jour_tradfi() == []
    assert telecharges == ["XAU", "QQQ", "SPY"]                 # une a la fois, dans l'ordre
    assert integres == [(b, tf) for b in ("XAU", "QQQ", "SPY") for tf in univers.TIMEFRAMES]


def test_maj_tradfi_un_echec_n_arrete_pas_les_autres(isole, monkeypatch):
    integres = []

    def faux_telecharger(paires, **_):
        p = paires[0]
        if p.base == "QQQ":
            return {"QQQ": "echec (code 2) : reseau"}
        for tf in univers.TIMEFRAMES:
            config.chemin_feather_brut(p.slug, tf).parent.mkdir(parents=True, exist_ok=True)
            config.chemin_feather_brut(p.slug, tf).write_bytes(b"x")
        return {p.base: "ok"}

    monkeypatch.setattr(telechargement, "telecharger", faux_telecharger)
    monkeypatch.setattr(construction, "integrer_telechargement",
                        lambda p, tf: integres.append(p.base) or {})
    problemes = maj.mettre_a_jour_tradfi()
    assert problemes[0] == "QQQ (telechargement) : echec (code 2) : reseau"
    assert sorted(set(integres)) == ["SPY", "XAU"]
    assert all("QQQ" in p for p in problemes)


def test_maj_tradfi_sans_reseau_n_appelle_pas_freqtrade(isole, monkeypatch):
    def interdit(*_, **__):
        raise AssertionError("aucun appel reseau attendu")

    monkeypatch.setattr(telechargement, "telecharger", interdit)
    problemes = maj.mettre_a_jour_tradfi(reseau=False)
    assert len(problemes) == 3 * len(univers.TIMEFRAMES)       # feathers absents, signales
    assert problemes[0] == "XAU 5m : feather absent de data/raw"


def test_fraicheur_surveille_aussi_les_tradfi(isole):
    lignes = {f["serie"]: f for f in maj.fraicheur(pd.Timestamp("2026-10-20", tz="UTC"))}
    for base in ("XAU", "QQQ", "SPY"):
        assert lignes[f"{base} 1d"]["en_retard"] and lignes[f"{base} funding"]["en_retard"]
    assert "BTC 1d" in lignes                                   # les 6 paires restent la
