"""Suivi forward de VC4 : consignes par instant et journees closes, en ajout seul ; garde de
causalite."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from beta.strategies import voie_c2 as c2
from beta.strategies import voie_c4 as c4

_spec = importlib.util.spec_from_file_location(
    "c4_suivi", Path(__file__).resolve().parents[1] / "scripts" / "c4_suivi.py")
suivi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(suivi)


def _lancer(repertoire, monkeypatch):
    monkeypatch.setattr("sys.argv", ["c4_suivi", "--repertoire", str(repertoire)])
    return suivi.main()


def _lire(chemin):
    return [json.loads(l) for l in chemin.read_text().splitlines()]


def test_empreinte_epinglee_et_registre():
    assert c2.empreinte(c2.config("VC4")) == suivi.EMPREINTE
    assert suivi.CRITERES == {"maxdd_min": -0.25, "vol_min": 0.10, "vol_max": 0.30}


def test_journaux_en_ajout_seul(tmp_path, monkeypatch):
    assert _lancer(tmp_path, monkeypatch) == 0
    consignes, journees = tmp_path / "CONSIGNES_VC4.jsonl", tmp_path / "SUIVI_VC4.jsonl"
    avant = consignes.read_text(), journees.read_text()
    c, j = _lire(consignes), _lire(journees)
    assert c[0]["instant"] == "2026-09-06T00:00:00+00:00" and j[0]["date"] == "2026-09-06"
    assert all(x["config"] == suivi.EMPREINTE for x in c + j)
    # une journee de semaine porte ses trois decisions, une de week-end une seule
    par_jour = {x["date"]: len(x["decisions"]) for x in j}
    assert par_jour["2026-09-07"] == 3 and par_jour["2026-09-06"] == 1
    # les ordres d'une consigne sont exactement son turnover
    for x in c:
        assert abs(sum(abs(v) for v in x["ordres"].values()) - x["turnover"]) < 1e-5
    assert _lancer(tmp_path, monkeypatch) == 0
    assert (consignes.read_text(), journees.read_text()) == avant     # rien de reecrit


def test_la_garde_attrape_une_fuite_du_futur(monkeypatch):
    d = c2.donnees(fin=c2.FIN_BACKTEST)
    cinq = c4.donnees_5m(debut=d["closes"].index[0], fin=c2.FIN_BACKTEST + pd.Timedelta(days=1))
    cfg = c2.config("VC4")
    jour = pd.Timestamp("2025-04-07", tz="UTC")
    d_jour = {k: (v[v.index < jour] if k == "closes" else v) for k, v in d.items()}
    cinq_jour = c4.tronquer_5m(cinq, jour + pd.Timedelta(hours=13, minutes=30))
    r = c4.calculer(d_jour, cinq_jour, cfg, fin=jour)
    suivi.garde(d_jour, cinq_jour, cfg, r, jour)                      # chaine causale : passe
    vrai = c4.prix_aux_instants
    monkeypatch.setattr(c4, "prix_aux_instants", lambda cinq, quand: vrai(
        cinq, quand + pd.Timedelta(minutes=5)).set_axis(quand))
    r_fuite = c4.calculer(d_jour, cinq_jour, cfg, fin=jour)
    with pytest.raises(suivi.CausaliteError):
        suivi.garde(d_jour, cinq_jour, cfg, r_fuite, jour)
