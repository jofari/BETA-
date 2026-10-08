"""Suivi forward de la voie C : journal en ajout seul, config figee gardee."""

import importlib.util
import json
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "voie_c_suivi", Path(__file__).resolve().parents[1] / "scripts" / "voie_c_suivi.py")
suivi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(suivi)


def _lancer(journal, monkeypatch):
    monkeypatch.setattr("sys.argv", ["voie_c_suivi", "--journal", str(journal)])
    return suivi.main()


def test_config_figee_inchangee():
    # Si ce test casse, quelqu'un a modifie la config du suivi : ouvrir un nouveau journal.
    assert suivi.empreinte(suivi.CONFIG_FIGEE) == "d0a971b8c4261d60"


def test_journal_en_ajout_seul(tmp_path, monkeypatch):
    journal = tmp_path / "suivi.jsonl"
    _lancer(journal, monkeypatch)
    premier = journal.read_text()
    assert premier
    lignes = [json.loads(l) for l in premier.splitlines()]
    assert lignes[0]["date"] == "2026-09-06"
    assert all(l["config"] == suivi.empreinte(suivi.CONFIG_FIGEE) for l in lignes)
    _lancer(journal, monkeypatch)
    assert journal.read_text() == premier          # rien de reecrit, rien de duplique


def test_refuse_un_journal_d_une_autre_config(tmp_path, monkeypatch):
    journal = tmp_path / "suivi.jsonl"
    journal.write_text(json.dumps({"date": "2026-09-06", "config": "autre", "r_net": 0}) + "\n")
    assert _lancer(journal, monkeypatch) == 2
