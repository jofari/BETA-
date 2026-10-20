"""Test invest — la vue de l'onglet : relit data/test_invest/, ne calcule rien (D3)."""

import json

import pytest

from beta.invest import campagne
from beta.rapport import invest, serveur


def _run(rid="0123456789ab", periode="principale", verdict="hasard"):
    return {"run_id": rid, "statut": "campagne", "calcule_le": "2026-10-20T17:00:00+00:00",
            "libelle": "socle complet · socle", "signal": "complet", "verdict": verdict,
            "config": {"periode": periode, "indicateurs": ["momentum_btc"], "kappa_pb": 10.0,
                       "theta_episode": 0.2, "b": 1000, "graine": 0, "pit": "publication",
                       "nulls": True, "mapping": {"nom": "socle"}},
            "periode": {"nom": periode, "n_jours": 10, "n_episodes": 1},
            "metriques": {"strategie": {"ulcer": 0.2, "mdd": -0.3, "protection": 0.1,
                                        "expo_moyenne": 0.7}},
            "nulls": {"p_retenue": 0.4}, "series": {"v_s": [1.0] * 11}}


@pytest.fixture
def dossier(tmp_path, monkeypatch):
    d = tmp_path / "test_invest"
    monkeypatch.setattr(campagne, "DOSSIER", d)
    return d


def test_vue_sans_rien_de_calcule(dossier):
    v = invest.vue()
    assert v["runs"] == [] and v["campagne"] is None
    assert "scripts/test_invest.py" in v["commande"]


def test_vue_liste_les_runs_sans_leurs_series_et_la_campagne(dossier):
    dossier.mkdir()
    (dossier / "0123456789ab.json").write_text(json.dumps(_run()), encoding="utf-8")
    (dossier / "campagne_TI1.json").write_text(json.dumps({"experience": "TI1"}),
                                               encoding="utf-8")
    v = invest.vue()
    assert v["campagne"] == {"experience": "TI1"}
    (r,) = v["runs"]
    assert r["run_id"] == "0123456789ab" and r["mapping"] == "socle"
    assert r["periode"] == "principale" and r["indicateurs"] == ["momentum_btc"]
    assert r["ulcer"] == 0.2 and r["p_retenue"] == 0.4 and "series" not in r


@pytest.mark.parametrize("mauvais", ["../etc", "0123456789AB", "abc", "campagne_TI1"])
def test_un_identifiant_de_run_invalide_est_refuse(dossier, mauvais):
    with pytest.raises(ValueError):
        invest.run({"id": [mauvais]})


def test_run_introuvable_puis_trouve(dossier):
    with pytest.raises(FileNotFoundError):
        invest.run({"id": ["0123456789ab"]})
    dossier.mkdir()
    (dossier / "0123456789ab.json").write_text(json.dumps(_run()), encoding="utf-8")
    assert invest.run({"id": ["0123456789ab"]})["series"]["v_s"][0] == 1.0


def test_les_routes_de_l_onglet_sont_des_get():
    assert {"/api/invest", "/api/invest/run"} <= set(serveur.ROUTES)


def test_la_liste_ne_relit_un_run_que_s_il_a_change(dossier, monkeypatch):
    dossier.mkdir()
    chemin = dossier / "0123456789ab.json"
    chemin.write_text(json.dumps(_run()), encoding="utf-8")
    lectures = []
    vrai = invest._lire
    monkeypatch.setattr(invest, "_lire", lambda c: lectures.append(c.name) or vrai(c))
    invest.vue()
    invest.vue()
    assert lectures == ["0123456789ab.json"]
    chemin.write_text(json.dumps(_run(verdict="reel")), encoding="utf-8")
    import os
    os.utime(chemin, ns=(1, 2_000_000_000_000_000_000))
    assert invest.vue()["runs"][0]["verdict"] == "reel" and len(lectures) == 2
