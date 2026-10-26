"""Tests de PBOR sur des donnees fabriquees : ni `data/runs/`, ni le lake."""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from beta.pbo_passe import campagne as ca
from beta.pbo_passe import rapport
from beta.pbo_passe import regles as R
from beta.stats import batterie, pbo
from beta.strategies import voie_c_voltarget as vc


def test_les_regles_sont_celles_de_la_porte_s10():
    assert (R.SEUIL, R.S, R.PPA) == (batterie.SEUIL_PBO, pbo.S, pbo.PPA)
    assert [len(x["runs"]) for x in R.LOTS.values()] == [2, 3, 8]
    ids = [r for x in R.LOTS.values() for r in x["runs"].values()]
    assert len(set(ids)) == len(ids) == len(R.EMPREINTES_TRADES)
    assert set(ids) == set(R.EMPREINTES_TRADES)
    assert R.VARIANTES_VC == tuple(f"vt {c:.0%} / {f}j / quotidien"
                                   for f in vc.FENETRES_CIBLE for c in vc.CIBLES)
    assert R.FIN_TRAIN_VC == vc.FIN_TRAIN


def _faux_run(dossier, run_id, nom, lance_le, n, n_lot, r, graine=0) -> str:
    d = dossier / run_id
    d.mkdir(parents=True)
    (d / "verdict.json").write_text(json.dumps({
        "candidate": nom, "lance_le": f"{lance_le}T14:54:00+00:00", "n_essais_cumules": n,
        "issue": "infirmee"}), encoding="utf-8")
    (d / "batterie.json").write_text(json.dumps({
        "S7_reality_check": {"n_candidates": n_lot, "meilleure": "a"}}), encoding="utf-8")
    jours = pd.date_range("2024-01-01 13:00", periods=len(r), freq="D", tz="UTC")
    pd.DataFrame({"ts_sortie": jours, "r": r}).to_parquet(d / "trades.parquet", index=False)
    return hashlib.sha256((d / "trades.parquet").read_bytes()).hexdigest()[:16]


@pytest.fixture
def lot_fabrique(tmp_path):
    rng = np.random.default_rng(11)
    lot = {"titre": "lot fabrique", "lance_le": "2026-09-19", "n_essais_cumules": 62,
           "runs": {"a": "aaaa00000001", "b": "bbbb00000002", "c": "cccc00000003"}}
    empreintes = {rid: _faux_run(tmp_path, rid, nom, lot["lance_le"], 62, 3,
                                 rng.standard_normal(320))
                  for nom, rid in lot["runs"].items()}
    return tmp_path, lot, empreintes


def test_un_lot_se_charge_et_rend_la_pbo_de_s10(lot_fabrique, monkeypatch):
    runs, lot, empreintes = lot_fabrique
    trades, fiches = ca.charger_lot(lot, runs, empreintes)
    assert sorted(trades) == ["a", "b", "c"] and len(trades["a"]) == 320
    assert [f["issue"] for f in fiches] == ["infirmee"] * 3
    monkeypatch.setitem(R.LOTS, "LX", lot)
    x = ca.lot("LX", runs, empreintes)
    attendu = pbo.calculer(pbo.rendements_lot(trades), batterie.SEUIL_PBO)
    assert x["pbo"]["pbo"] == attendu["pbo"] and x["pbo"]["n_jours"] == 320
    assert x["lecture_s10"] == ca.lecture(attendu)


def test_un_fichier_de_trades_modifie_arrete_la_campagne(lot_fabrique):
    runs, lot, empreintes = lot_fabrique
    empreintes = {**empreintes, "bbbb00000002": "0" * 16}
    with pytest.raises(ca.PBOError, match="changes depuis le gel"):
        ca.charger_lot(lot, runs, empreintes)


@pytest.mark.parametrize("champ, valeur", [("candidate", "z"), ("n_essais_cumules", 57),
                                           ("lance_le", "2026-09-08T08:31:00+00:00")])
def test_un_run_qui_n_est_pas_celui_du_lot_arrete_la_campagne(lot_fabrique, champ, valeur):
    runs, lot, empreintes = lot_fabrique
    chemin = runs / "aaaa00000001" / "verdict.json"
    verdict = json.loads(chemin.read_text(encoding="utf-8"))
    chemin.write_text(json.dumps({**verdict, champ: valeur}), encoding="utf-8")
    with pytest.raises(ca.PBOError, match="n'est pas celui"):
        ca.charger_lot(lot, runs, empreintes)


def test_un_univers_s7_d_une_autre_taille_arrete_la_campagne(lot_fabrique):
    runs, lot, empreintes = lot_fabrique
    (runs / "cccc00000003" / "batterie.json").write_text(
        json.dumps({"S7_reality_check": {"n_candidates": 8}}), encoding="utf-8")
    with pytest.raises(ca.PBOError):
        ca.charger_lot(lot, runs, empreintes)


def test_les_variantes_de_la_selection_suivent_l_ordre_de_main():
    rng = np.random.default_rng(5)
    index = pd.date_range("2023-01-01", periods=120, freq="D", tz="UTC")
    paires = list(vc.PAIRES)
    ctx = {"fenetre": index[20:],
           "comp": pd.DataFrame(rng.uniform(-0.2, 0.3, (120, 6)), index=index, columns=paires),
           "rendements": pd.DataFrame(rng.normal(0, 0.03, (120, 6)), index=index,
                                      columns=paires),
           "funding_j": pd.DataFrame(1e-4, index=index, columns=paires),
           "leviers": {(c, f): pd.Series(c * f / 30.0, index=index)
                       for f in vc.FENETRES_CIBLE for c in vc.CIBLES}}
    sorties = vc.variantes_selection(ctx)
    assert tuple(sorties) == R.VARIANTES_VC
    for (c, f), nom in zip(((c, f) for f in vc.FENETRES_CIBLE for c in vc.CIBLES), sorties,
                           strict=True):
        attendu, _ = vc.lancer_variante(ctx, ctx["comp"], 1, ctx["leviers"][(c, f)])
        pd.testing.assert_frame_equal(sorties[nom], attendu)
        assert len(sorties[nom]) == 100


def _res(pbo_=0.1, passe=True, raison=None) -> dict:
    return {"seuil": 0.2, "s": 16, "n_configs_avant": 3, "n_jours_avant": 330,
            "n_jours": 320, "doublons": [], "n_configs": 3, "debut": "2024-01-11",
            "fin": "2024-11-25", "pbo": pbo_, "passe": passe, "raison": raison,
            "jours_par_bloc": 20, "n_combinaisons": 12870,
            "w": {"0.05": 0.2, "0.25": 0.4, "0.5": 0.6, "0.75": 0.7, "0.95": 0.9},
            "etoiles": {"a": 0.7, "b": 0.3}}


def test_le_rapport_se_rend_avec_une_pbo_incalculable():
    fiche = {"candidate": "a", "run": "aaaa00000001", "issue": "infirmee", "n_trades": 9,
             "meilleure_s7": "a"}
    incalc = {**_res(None, None, "PBO incalculable : ecart-type nul"), "w": None,
              "etoiles": None, "jours_par_bloc": None, "n_combinaisons": None}
    s = {"code": "abc1234", "regles": "r" * 16, "preenregistrement": "p" * 16,
         "debut_calcul": "2026-10-26T23:00:00+00:00", "calcule_le": "2026-10-26T23:05:00+00:00",
         "lots": {"L1": {"titre": "lot", "candidates": [fiche], "donnees": "d" * 16,
                         "pbo": _res(), "lecture_s10": "franchie"},
                  "L2": {"titre": "lot", "candidates": [fiche], "donnees": "d" * 16,
                         "pbo": incalc, "lecture_s10": "non executee"}},
         "voie_c": {"depart": "2021-05-01", "donnees": "v" * 16, "pbo": _res(0.4, False),
                    "lecture_s10": "echouee", "retenue_train": "vt 25% / 30j / quotidien"},
         "compteur": {"avant": {"global": 147, "trading": 93, "invest": 54},
                      "apres": {"global": 147, "trading": 93, "invest": 54}}}
    t = rapport.texte(s)
    assert "S10 aurait été franchie" in t and "n'aurait pas été exécutée" in t
    assert "**incalculable** — PBO incalculable : ecart-type nul" in t
    assert "**10,0 %**" in t and "**40,0 %**" in t and "S10 aurait échoué" in t
    r = rapport.resume(s)
    assert "PBO incalculable" in r and "PBO 40,0 %" in r
