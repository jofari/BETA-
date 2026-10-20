"""Test invest — campagne : configs, identifiants, evaluation complete, compteur (C6), C1."""

import json

import numpy as np
import pandas as pd
import pytest

from beta.invest import campagne as ca
from beta.invest import donnees as dn
from beta.invest.moteur import Mapping
from beta.protocole import experiences

T = lambda s: pd.Timestamp(s, tz="UTC")                                   # noqa: E731
PAIRES = ("BTC", "ETH", "SOL", "BNB", "XRP", "LINK")


def _donnees(graine: int = 0) -> dn.Donnees:
    """Un marche synthetique : une hausse, un krach de -60 % en 3 mois, une reprise."""
    rng = np.random.default_rng(graine)
    cal = pd.date_range(T("2024-06-01"), T("2026-03-01"), freq="D")
    n = len(cal)
    tendance = np.where((np.arange(n) > 300) & (np.arange(n) < 390), -0.01, 0.0015)
    closes = pd.DataFrame(
        100 * np.exp(np.cumsum(tendance[:, None] + rng.normal(0, 0.02, (n, 6)), axis=0)),
        index=cal, columns=list(PAIRES))
    mom = np.sign(closes["BTC"] / closes["BTC"].shift(30) - 1).shift(1).fillna(0.0)
    votes = pd.DataFrame({"momentum_btc": mom}, index=cal)
    for nom in dn.VOTES[1:]:
        brut = np.repeat(rng.choice([-1.0, 0.0, 1.0], n // 10 + 1), 10)[:n]
        votes[nom] = brut
    votes = votes[list(dn.VOTES)]
    return dn.Donnees(closes=closes, votes=votes, votes_socle=votes, funding=closes * 0.0,
                      dff=pd.Series(dtype=float),
                      cfg_socle={"seuils_etat": {"haussier": 2, "baissier": -2}},
                      fin=T("2026-03-01"),
                      pit="publication", trous_acceptes=[], empreinte=dn.empreinte(closes, votes))


def _cfg(**k):
    base = {"periode": "test", "debut": "2024-09-01", "fin": "2026-03-01", "b": 25}
    return ca.Config(**{**base, **k})


# ---------------------------------------------------------------------------- configs

def test_campagne_ti1_24_mesures_et_nulls_sur_6_signaux_par_periode():
    cfgs = ca.campagne_ti1()
    assert len(cfgs) == 24 and len({ca.run_id(c, "x") for c in cfgs}) == 24
    for periode in ("principale", "stress"):
        lot = [c for c in cfgs if c.periode == periode]
        assert len(lot) == 12
        avec_nulls = [c for c in lot if c.nulls]
        assert sorted(ca.signal(c) for c in avec_nulls) == sorted(["complet", *dn.VOTES])
        assert all(c.mapping.nom == ("socle" if ca.signal(c) == "complet" else "paliers")
                   for c in avec_nulls)
    assert ca.PERIODES == {"principale": ("2024-01-11", "2026-10-19"),
                           "stress": ("2020-09-15", "2026-10-19")}


def test_libelles_et_signaux():
    assert ca.libelle(_cfg()) == "socle complet · socle"
    assert ca.libelle(_cfg(indicateurs=("nasdaq",), mapping=Mapping("paliers"))) == \
        "nasdaq seul · paliers"
    sans = tuple(v for v in dn.VOTES if v != "fear_greed")
    assert ca.signal(_cfg(indicateurs=sans)) == "sans_fear_greed"


def test_run_id_stable_et_sensible_a_la_config_et_aux_donnees():
    a = ca.run_id(_cfg(), "e1")
    assert a == ca.run_id(_cfg(), "e1") and len(a) == 12
    assert a != ca.run_id(_cfg(kappa_pb=20.0), "e1")
    assert a != ca.run_id(_cfg(), "e2")


# ---------------------------------------------------------------------------- evaluation

def test_evaluation_complete_et_coherente():
    res = ca.evaluer(_cfg(), _donnees())
    s = res["series"]
    n = res["periode"]["n_jours"]
    assert len(s["dates"]) == n + 1 and len(s["e"]) == n
    assert s["v_s"][0] == s["v_b"][0] == s["v_btc"][0] == 1.0
    assert s["dates"][0] == "2024-08-31"                       # P0 : la veille du 1er jour
    assert res["periode"]["n_episodes"] >= 1
    m = res["metriques"]
    assert {"strategie", "panier", "btc", "temoin"} <= set(m)
    assert m["temoin"]["expo_moyenne"] == pytest.approx(m["strategie"]["expo_moyenne"])
    assert m["panier"]["protection"] == pytest.approx(0.0)    # le benchmark ne se protege pas
    p = res["nulls"]
    assert len(p["circulaire"]["ulcer"]) == 25 and len(p["segments"]["ulcer"]) == 25
    assert p["p_retenue"] == max(p["p"]["circulaire"]["ulcer"], p["p"]["segments"]["ulcer"])
    assert res["verdict"] in ("reel", "non concluant", "hasard")
    json.dumps(res)                                            # JSON strict


def test_evaluation_deterministe_c1():
    a = ca.evaluer(_cfg(), _donnees())
    b = ca.evaluer(_cfg(), _donnees())
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_sans_nulls_pas_de_verdict():
    res = ca.evaluer(_cfg(nulls=False), _donnees())
    assert res["nulls"] is None and res["verdict"] is None


def test_puissance_faible_signalee_sous_3_episodes():
    res = ca.evaluer(_cfg(nulls=False), _donnees())
    assert res["periode"]["puissance_faible"] == (res["periode"]["n_episodes"] < 3)


# ------------------------------------------------------------------- compteur (C6, D5)

@pytest.fixture
def registre(tmp_path, monkeypatch):
    reg, runs = tmp_path / "EXPERIMENTS.jsonl", tmp_path / "RUNS.jsonl"
    monkeypatch.setattr(experiences, "REGISTRE", reg)
    monkeypatch.setattr(experiences, "JOURNAL_RUNS", runs)
    monkeypatch.setattr(ca, "DOSSIER", tmp_path / "test_invest")
    experiences.preenregistrer("TI1", "h", "ulcer", {"reel": "p < 0,05"}, chemin=reg)
    return reg


def test_une_mesure_compte_une_fois_et_se_rejoue_sans_recompter(registre):
    d = _donnees()
    avant = experiences.compteur()
    res = ca.mesurer(_cfg(), d)
    assert experiences.compteur() == avant              # TI1 passe de « preenregistree » a 1 run
    assert res["compteur"] == experiences.compteur()
    assert res["metriques"]["strategie"]["dsr"] is not None
    ca.mesurer(_cfg(), d)                               # rejoue : meme run_id, rien de plus
    assert experiences.compteur() == avant
    ca.mesurer(_cfg(kappa_pb=20.0), d)                  # une autre config : +1
    assert experiences.compteur() == avant + 1
    assert (ca.DOSSIER / f"{res['run_id']}.json").exists()
    lignes = experiences.runs_journalises()
    assert [x["experience"] for x in lignes] == ["TI1", "TI1"]
    assert lignes[0]["candidate"].startswith("test_invest:exploratoire:")


def test_aucune_mesure_sans_preenregistrement(tmp_path, monkeypatch):
    monkeypatch.setattr(experiences, "REGISTRE", tmp_path / "vide.jsonl")
    monkeypatch.setattr(ca, "DOSSIER", tmp_path / "test_invest")
    with pytest.raises(experiences.ProtocoleError):
        ca.mesurer(_cfg(), _donnees())


# ------------------------------------------------------------------------ synthese (C1-C3)

def test_synthese_d_une_periode_c1_c2_c3(registre):
    d = _donnees()
    lot = [c for c in ca.campagne_ti1(b=25) if c.periode == "principale"]
    lot = [ca.Config(**{**c.__dict__, "periode": "test", "debut": "2024-09-01",
                        "fin": "2026-03-01"}) for c in lot]
    resultats = [ca.evaluer(c, d) for c in lot]
    syn = ca.synthese_periode(resultats, d.votes, T("2024-09-01"), T("2026-03-01"))
    assert [x["signal"] for x in syn["c1"]] == ["complet", *dn.VOTES]
    assert all(x["q_bh"] is not None for x in syn["c1"])
    assert set(syn["c2"]) == set(dn.VOTES)
    assert syn["c3"]["kappa"]["momentum_btc"]["momentum_btc"] == 1.0


def test_recalculer_ne_duplique_pas_la_ligne_du_journal(registre):
    d = _donnees()
    ca.mesurer(_cfg(), d)
    ca.mesurer(_cfg(), d, recalculer=True)
    assert len(experiences.runs_journalises()) == 1


def test_lancer_la_campagne_ecrit_la_synthese_et_marque_ti1(registre):
    d = _donnees()
    periodes = {"test": ("2024-09-01", "2026-03-01")}
    syn = ca.lancer_campagne(d, b=25, periodes=periodes)
    assert len(syn["runs"]) == 12 and (ca.DOSSIER / "campagne_TI1.json").exists()
    assert {"c1", "c2", "c3"} <= set(syn["periodes"]["test"]["synthese"])
    assert syn["periodes"]["test"]["n_episodes"] >= 1
    assert "test" in syn["diagnostic_pit"]
    assert experiences.etat()["TI1"]["statut"] == "mesure"
    avant, lignes_registre = experiences.compteur(), len(experiences._lignes())
    ca.lancer_campagne(d, b=25, periodes=periodes)          # rejoue : rien de plus
    assert experiences.compteur() == avant and len(experiences._lignes()) == lignes_registre
    lignes = experiences.runs_journalises()
    assert len(lignes) == 12 and all(":campagne:" in x["candidate"] for x in lignes)
