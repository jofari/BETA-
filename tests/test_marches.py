"""Les vrais marches (Jonas, 20-21/10) : collecte hors Binance et hors freqtrade.

Ce que ces tests protegent : une seance pas finie n'est jamais ecrite ; une source en panne ne
touche pas la copie ; une reecriture du passe par la source est comptee et journalisee ; l'or
WGC se complete annee par annee sans perdre les annees deja stockees ; une page de maintenance
n'est jamais prise pour une serie ; les noms neufs ne heurtent aucun nom du lake.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from beta.lake import univers
from beta.marches import collecte, sources
from beta.marches.series import SERIES, par_nom


@pytest.fixture
def isole(tmp_path, monkeypatch):
    monkeypatch.setattr(collecte, "DOSSIER", tmp_path / "marches")
    monkeypatch.setattr(collecte, "ETAT", tmp_path / "marches" / "etat.json")
    monkeypatch.setattr(collecte, "REVISIONS", tmp_path / "marches" / "revisions.jsonl")
    monkeypatch.setattr(collecte, "PAUSE_WGC_S", 0.0)
    return tmp_path


def _yahoo(debut="2026-10-01", fin="2026-10-21", base=100.0):
    jours = pd.bdate_range(debut, fin)
    close = base + np.arange(len(jours), dtype=float)
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                         "volume": 1.0}, index=pd.DatetimeIndex(jours, name="date"))


# ----------------------------------------------------------------------------- noms

def test_noms_neufs_sans_collision_avec_le_lake():
    for s in SERIES:
        with pytest.raises(KeyError):
            univers.resoudre(s.nom)
    assert par_nom("ndx").identifiant == "^NDX"           # Jonas 21/10 : pas le Composite
    assert par_nom("XAU_LBMA").source == "wgc"


# ----------------------------------------------------------------------------- seances

def test_la_seance_du_jour_n_est_ecrite_qu_une_fois_close():
    df = _yahoo("2026-10-19", "2026-10-21")
    pendant = pd.Timestamp("2026-10-21 18:00", tz="UTC")        # 14:00 a New York
    apres = pd.Timestamp("2026-10-21 21:30", tz="UTC")          # 17:30 a New York
    assert collecte.seances_closes(df, "America/New_York", pendant).index.max() == \
        pd.Timestamp("2026-10-20")
    assert collecte.seances_closes(df, "America/New_York", apres).index.max() == \
        pd.Timestamp("2026-10-21")


def test_trous_en_jours_ouvres_les_week_ends_et_le_11_septembre_n_en_sont_pas():
    dates = pd.DatetimeIndex(["2001-09-07", "2001-09-10", "2001-09-17",   # 4 jours fermes
                              "2001-09-18", "2001-10-01"])                   # 8 jours absents
    t = collecte.trous(dates)
    assert t == [{"apres": "2001-09-18", "avant": "2001-10-01", "jours_ouvres": 8}]


# ----------------------------------------------------------------------------- mise a jour

def test_mise_a_jour_ecrit_decrit_et_relit_en_utc(isole, monkeypatch):
    monkeypatch.setattr(sources, "yahoo_1d", lambda t: _yahoo())
    e = collecte.mettre_a_jour(par_nom("SPX"),
                               maintenant=pd.Timestamp("2026-10-21 22:00", tz="UTC"))
    assert e["statut"] == "ok" and e["debut"] == "2026-10-01" and e["fin"] == "2026-10-21"
    assert e["n"] == 15 and e["trous_plus_de_5_seances"] == 0
    df = collecte.lire("SPX")
    assert str(df.index.tz) == "UTC" and df.index[0] == pd.Timestamp("2026-10-01", tz="UTC")


def test_une_source_en_panne_ne_touche_pas_la_copie(isole, monkeypatch):
    monkeypatch.setattr(sources, "yahoo_1d", lambda t: _yahoo())
    n_avant = collecte.tout_mettre_a_jour(["SPX"])["SPX"]["n"]
    avant = collecte.chemin("SPX").read_bytes()

    def panne(t):
        raise sources.SourceError("Yahoo ^GSPC : 429")
    monkeypatch.setattr(sources, "yahoo_1d", panne)
    etat = collecte.tout_mettre_a_jour(["SPX"])
    assert etat["SPX"]["statut"] == "echec" and "429" in etat["SPX"]["erreur"]
    assert etat["SPX"]["n"] == n_avant                  # la description de la copie reste
    assert collecte.chemin("SPX").read_bytes() == avant


def test_une_reecriture_du_passe_est_comptee_et_journalisee(isole, monkeypatch):
    monkeypatch.setattr(sources, "yahoo_1d", lambda t: _yahoo())
    collecte.mettre_a_jour(par_nom("SPX"), maintenant=pd.Timestamp("2026-10-22", tz="UTC"))
    modifie = _yahoo()
    modifie.loc[pd.Timestamp("2026-10-05"), "close"] = 999.0
    monkeypatch.setattr(sources, "yahoo_1d", lambda t: modifie)
    e = collecte.mettre_a_jour(par_nom("SPX"), maintenant=pd.Timestamp("2026-10-22", tz="UTC"))
    assert e["revisions"]["valeurs_changees"] == 1
    assert e["revisions"]["exemples"][0] == {"date": "2026-10-05", "avant": 102.0, "apres": 999.0}
    lignes = collecte.REVISIONS.read_text(encoding="utf-8").splitlines()
    assert len(lignes) == 1 and json.loads(lignes[0])["serie"] == "SPX"


def test_serie_en_retard_signalee(isole, monkeypatch):
    monkeypatch.setattr(sources, "yahoo_1d", lambda t: _yahoo(fin="2026-10-09"))
    e = collecte.mettre_a_jour(par_nom("SPX"), maintenant=pd.Timestamp("2026-10-21 22:00",
                                                                       tz="UTC"))
    assert e["statut"] == "en retard" and e["retard_j"] == 12


# ----------------------------------------------------------------------------- or WGC

def test_or_wgc_complete_l_annee_en_cours_sans_perdre_les_autres(isole, monkeypatch):
    appels = []

    def wgc(annee):
        appels.append(annee)
        jours = pd.bdate_range(f"{annee}-01-01", f"{annee}-12-31" if annee < 2026
                               else "2026-10-20")
        return pd.Series(float(annee), index=pd.DatetimeIndex(jours, name="date"), name="close")
    monkeypatch.setattr(sources, "wgc_annee", wgc)
    maintenant = pd.Timestamp("2026-10-21 22:00", tz="UTC")
    collecte.mettre_a_jour(par_nom("XAU_LBMA"), maintenant=maintenant)   # rien en stock
    assert appels == list(range(1970, 2027))
    appels.clear()
    e = collecte.mettre_a_jour(par_nom("XAU_LBMA"), maintenant=maintenant)
    assert appels == [2026]
    assert e["debut"] == "1970-01-01" and e["fin"] == "2026-10-20"
    assert e["revisions"]["valeurs_changees"] == 0


def test_wgc_refuse_le_prix_spot_des_plages_courtes(monkeypatch):
    ms = int(pd.Timestamp("2026-10-10", tz="UTC").value // 10**6)          # un samedi
    monkeypatch.setattr(sources, "_json", lambda url: {"chartData": {"USD": [[ms, 4194.65]]}})
    with pytest.raises(sources.SourceError, match="week-end"):
        sources.wgc_annee(2026)


# ----------------------------------------------------------------------------- FRED

def test_fred_en_maintenance_n_est_jamais_une_serie(monkeypatch):
    page = "<!doctype html>\n<html><title>Site Maintenance | St. Louis Fed</title></html>"
    monkeypatch.setattr(sources, "_texte", lambda url: page)
    with pytest.raises(sources.SourceError, match="maintenance"):
        sources.fred_csv("DEXJPUS")


def test_fred_retire_les_jours_sans_valeur(monkeypatch):
    csv = "observation_date,DEXJPUS\n2026-10-09,150.1\n2026-10-12,\n2026-10-13,151.2\n"
    monkeypatch.setattr(sources, "_texte", lambda url: csv)
    s = sources.fred_csv("DEXJPUS")
    assert list(s.index.strftime("%Y-%m-%d")) == ["2026-10-09", "2026-10-13"]


def test_dexjpus_sans_alfred_garde_les_valeurs_et_le_dit(isole, monkeypatch):
    s = pd.Series([150.0, 151.0], index=pd.DatetimeIndex(["2026-10-09", "2026-10-13"],
                                                          name="date"), name="close")
    monkeypatch.setattr(sources, "fred_csv", lambda sid: s)

    def alfred(sid):
        raise sources.SourceError("ALFRED en maintenance")
    monkeypatch.setattr(sources, "premieres_publications", alfred)
    e = collecte.mettre_a_jour(par_nom("DEXJPUS"),
                               maintenant=pd.Timestamp("2026-10-14", tz="UTC"))
    assert e["statut"] == "ok" and "maintenance" in e["alfred"]["indisponible"]
    assert collecte.lire("DEXJPUS")["publie_le"].isna().all()
