"""L'epreuve de causalite sur la serie que la candidate tradera (04/11/2026, R13 et R14).

Avant : l'epreuve de l'atelier tournait sur BTC (4h, ou le timeframe demande), jamais sur l'or
ni le Nasdaq ; et une candidate posee a la main dans `beta/candidates/` n'en passait aucune.
Ces tests disent les trois choses qui ont change :

1. avec `actif`, l'epreuve lit CETTE serie, toute la periode, et compte ses signaux ;
2. si la serie manque, elle s'arrete — aucun repli silencieux sur BTC ;
3. le moteur refait l'epreuve sur les series du run : une candidate qui lit le futur n'est
   pas mesuree, rien n'est journalise, et le rapport de l'epreuve part avec le run.

Series fabriquees par le test, dans un dossier temporaire : jamais la source vivante.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from beta import config
from beta.atelier import epreuve
from beta.lake import lecture
from beta.moteur import causalite, pipeline
from beta.moteur.contrats import Candidate, Run
from beta.protocole import experiences

# --- materiel -------------------------------------------------------------------------------------


def _ndx_1h(jours: int = 30) -> pd.DataFrame:
    """Seances de janvier 2024 (heure d'hiver : 09:30 New York = 14:30 UTC), 7 bougies 1h.

    La premiere bougie monte un jour sur deux : le fade de R14 vend apres une hausse et
    achete apres une baisse, donc la moitie des signaux sont longs.
    """
    jours_ouvres = pd.bdate_range("2024-01-02", periods=jours)
    lignes = []
    for k, jour in enumerate(jours_ouvres):
        for h in range(7):
            debut = jour + pd.Timedelta(hours=14, minutes=30) + pd.Timedelta(hours=h)
            hausse = (k % 2 == 0) if h == 0 else True
            ouverture, cloture = (100.0, 101.0) if hausse else (101.0, 100.0)
            lignes.append({"date": debut.tz_localize("UTC"), "open": ouverture,
                           "high": 101.5, "low": 99.5, "close": cloture, "volume": 0.0})
    return pd.DataFrame(lignes)


@pytest.fixture
def marches(tmp_path, monkeypatch):
    """Un `data/marches` temporaire avec le seul NDX 1h ; macro neutralisee (source vivante)."""
    monkeypatch.setattr(config, "MARCHES", tmp_path)
    monkeypatch.setattr(pipeline, "_joindre_macro", lambda df, paire=None: df)
    _ndx_1h().to_parquet(tmp_path / "NDX-1h.parquet", index=False)
    return tmp_path


def _serie_horaire(jours: int = 200, graine: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(graine)
    dates = pd.date_range("2024-01-01", periods=jours * 24, freq="1h", tz="UTC")
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.003, len(dates))))
    ouverture = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"date": dates, "open": ouverture,
                         "high": np.maximum(ouverture, close) * 1.001,
                         "low": np.minimum(ouverture, close) * 0.999,
                         "close": close, "volume": 1.0})


def signaux_causaux(df: pd.DataFrame) -> pd.DataFrame:
    """Long chaque jour a 15:00 UTC, stop a 1 % du prix : ne lit que la ligne decidee."""
    a_15h = pd.to_datetime(df["date"], utc=True).dt.hour == 15
    sens = pd.Series(0, index=df.index, dtype=int)
    sens[a_15h] = 1
    stop = pd.Series(np.nan, index=df.index, dtype=float)
    stop[a_15h] = 0.01 * df.loc[a_15h, "close"]
    return pd.DataFrame({"sens": sens, "stop_distance": stop})


def signaux_qui_lisent_le_futur(df: pd.DataFrame) -> pd.DataFrame:
    """La moyenne de la serie ENTIERE : aucun motif interdit, et pourtant du futur."""
    sens = pd.Series(0, index=df.index, dtype=int)
    sens[df["close"] > df["close"].mean()] = 1
    return pd.DataFrame({"sens": sens})


@pytest.fixture
def registre_temporaire(tmp_path, monkeypatch):
    monkeypatch.setattr(experiences, "REGISTRE", tmp_path / "EXPERIMENTS.jsonl")
    monkeypatch.setattr(experiences, "JOURNAL_RUNS", tmp_path / "RUNS.jsonl")
    monkeypatch.setattr(pipeline, "RESULTATS", tmp_path / "runs")
    monkeypatch.setattr(pipeline, "_joindre_macro", lambda df, paire=None: df)
    serie = _serie_horaire()
    monkeypatch.setattr(lecture, "load", lambda paire, timeframe, debut=None, fin=None,
                        colonnes=None: serie.copy())
    experiences.preenregistrer("TZ1", "h", "m", {"confirmee": "x"})
    return tmp_path


# --- l'atelier : la serie reelle ------------------------------------------------------------------

def test_l_epreuve_tourne_sur_la_serie_demandee_et_compte_ses_signaux(marches):
    rapport = epreuve.eprouver("r14_ny_ndx1h_stop_100", "1h", actif="NDX")
    assert rapport["ok"], rapport["refus"]
    m = rapport["mesures"]
    assert m["serie_reelle"] is True
    assert m["temoin"].startswith("NDX 1h")
    assert m["n_bougies"] == 30 * 7
    # Une seance = un signal ; une hausse sur deux est fadee en vente.
    assert (m["n_signaux"], m["n_long"], m["n_short"]) == (30, 15, 15)
    assert m["causalite"] == "ok" and m["determinisme"] == "ok"
    assert not any("TEMOIN" in r for r in rapport["reserves"])


def test_l_epreuve_respecte_la_periode_demandee(marches):
    rapport = epreuve.eprouver("r14_ny_ndx1h_stop_100", "1h", actif="NDX",
                               debut="2024-01-16")
    assert rapport["mesures"]["premiere"].startswith("2024-01-16")
    assert rapport["mesures"]["n_signaux"] == 20          # 30 seances, 10 avant le 16/01


def test_sans_la_serie_demandee_l_epreuve_s_arrete_au_lieu_de_prendre_btc(marches):
    with pytest.raises(epreuve.EpreuveError, match="indisponible"):
        epreuve.eprouver("r14_ny_ndx1h_stop_100", "5m", actif="NDX")


def test_sans_actif_le_rapport_dit_que_la_serie_est_un_temoin(monkeypatch):
    temoin = _serie_horaire(jours=60)
    monkeypatch.setattr(epreuve, "_serie_temoin", lambda timeframe="": (temoin, "BTC 4h"))
    rapport = epreuve.eprouver("r2_mean_reversion")
    assert rapport["mesures"]["serie_reelle"] is False
    assert any("TEMOIN" in r and "--actif" in r for r in rapport["reserves"])


def test_le_coeur_attrape_une_lecture_du_futur_sans_motif_interdit():
    candidate = Candidate(nom="futur", hypothese="TZ1", signaux=signaux_qui_lisent_le_futur)
    resultat = causalite.eprouver_serie(candidate, _serie_horaire(jours=30))
    assert any(r.startswith("CAUSALITE") for r in resultat["refus"])
    assert resultat["mesures"]["causalite"] == "refusee"


# --- le moteur : l'epreuve avant toute mesure -----------------------------------------------------

def test_le_moteur_ne_mesure_pas_une_candidate_qui_lit_le_futur(registre_temporaire):
    candidate = Candidate(nom="futur", hypothese="TZ1", signaux=signaux_qui_lisent_le_futur)
    run = Run(candidate=candidate, paires=("XAU_SPOT",), timeframe="1h")
    with pytest.raises(causalite.EpreuveRefusee, match="CAUSALITE") as refus:
        pipeline.executer(run, n_chemins=0)
    assert refus.value.rapport["ok"] is False
    # Rien n'est mesure, donc rien n'est journalise : le compteur ne bouge pas.
    assert not (registre_temporaire / "RUNS.jsonl").exists()
    assert not (registre_temporaire / "runs").exists()


def test_le_rapport_de_l_epreuve_part_avec_le_run(registre_temporaire):
    candidate = Candidate(nom="causale", hypothese="TZ1", signaux=signaux_causaux)
    run = Run(candidate=candidate, paires=("XAU_SPOT",), timeframe="1h")
    _, artefacts = pipeline.executer(run, n_chemins=0)
    rapport = artefacts["epreuve"]
    assert rapport["ok"] and rapport["empreinte"] == candidate.empreinte
    assert rapport["series"]["XAU_SPOT"]["n_signaux"] == 200      # un par jour
    ecrit = json.loads((registre_temporaire / "runs" / run.id / "epreuve.json")
                       .read_text(encoding="utf-8"))
    assert ecrit["series"] == json.loads(json.dumps(rapport["series"], default=str))


def test_le_second_passage_du_criblage_reprend_l_epreuve_du_premier(registre_temporaire,
                                                                   monkeypatch):
    """L'epreuve tourne une fois par candidate et par lot, pas deux."""
    from types import SimpleNamespace

    vus = []

    def faux_executer(run, **options):
        vus.append(options.get("epreuve"))
        art = {"equity": pd.DataFrame({"ts": [], "equity": []}),
               "sequence": pd.DataFrame({"ts_sortie": [], "r": []}), "detail": {},
               "epreuve": {"ok": True, "marque": run.candidate.nom}}
        return SimpleNamespace(run=run), art

    monkeypatch.setattr(pipeline, "executer", faux_executer)
    lot = {"a": Candidate(nom="a", hypothese="TZ1", signaux=signaux_causaux)}
    pipeline.cribler(lot, ("BTC",), "4h")
    assert vus == [None, {"ok": True, "marque": "a"}]
