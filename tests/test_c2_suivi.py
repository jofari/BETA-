"""Suivi forward de la voie C2 (VC2, VC3) : journal en ajout seul, empreintes gardees,
consigne = position du lendemain."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from beta.strategies import voie_c2 as c2

_spec = importlib.util.spec_from_file_location(
    "c2_suivi", Path(__file__).resolve().parents[1] / "scripts" / "c2_suivi.py")
suivi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(suivi)

H, B, V = c2.HAUSSIER, c2.BAISSIER, c2.VEILLE


def _lancer(journal, monkeypatch, id_exp="VC3"):
    monkeypatch.setattr("sys.argv", ["c2_suivi", "--id", id_exp, "--journal", str(journal)])
    return suivi.main()


def _jour(s):
    return pd.Timestamp(s, tz="UTC")


@pytest.fixture(scope="module")
def cfg():
    return c2.config("VC3")


# ------------------------------------------------------------------------- registre, journal

@pytest.mark.parametrize("id_exp,empreinte,live,admise", [
    ("VC3", "7adef08a837a8c50", "2026-10-08", True),       # confirmee : dry-run a juger
    ("VC2", "744700fa7d8980fc", "2026-10-07", False),      # infirmee : suivi informatif
])
def test_empreintes_dates_et_statut_du_registre(id_exp, empreinte, live, admise):
    # Si ce test casse, l'experience a ete repreenregistree : ce n'est plus le meme suivi.
    assert c2.empreinte(c2.config(id_exp)) == suivi.EMPREINTES[id_exp] == empreinte
    assert suivi.dates_du_registre(id_exp) == (_jour("2026-09-06"), _jour(live))
    assert suivi.admise_au_dry_run(id_exp) is admise


def test_nature_live_ou_rattrapage():
    live = _jour("2026-10-08")
    assert suivi.nature(_jour("2026-10-07"), live, _jour("2026-10-08")) == "rattrapage"
    assert suivi.nature(_jour("2026-10-08"), live, _jour("2026-10-09")) == "live"
    # le timer a manque deux jours : la journee est hors echantillon, mais ecrite apres coup
    assert suivi.nature(_jour("2026-10-08"), live, _jour("2026-10-11")) == "rattrapage"


@pytest.mark.parametrize("id_exp", ["VC3", "VC2"])
def test_journal_en_ajout_seul(tmp_path, monkeypatch, id_exp):
    journal = tmp_path / "suivi.jsonl"
    _lancer(journal, monkeypatch, id_exp)
    premier = journal.read_text()
    lignes = [json.loads(l) for l in premier.splitlines()]
    debut_live = f"{suivi.dates_du_registre(id_exp)[1]:%Y-%m-%d}"
    assert lignes[0]["date"] == "2026-09-06"
    assert all(l["config"] == suivi.EMPREINTES[id_exp] for l in lignes)
    assert all(l["type"] == "rattrapage" for l in lignes if l["date"] < debut_live)
    assert [("consigne_lendemain" in l) for l in lignes] == [False] * (len(lignes) - 1) + [True]
    _lancer(journal, monkeypatch, id_exp)
    assert journal.read_text() == premier          # rien de reecrit, rien de duplique


def test_refuse_un_journal_d_une_autre_config(tmp_path, monkeypatch):
    journal = tmp_path / "suivi.jsonl"
    journal.write_text(json.dumps({"date": "2026-09-06", "config": "autre", "r_net": 0}) + "\n")
    assert _lancer(journal, monkeypatch) == 2
    assert len(journal.read_text().splitlines()) == 1


def test_trous_du_calendrier():
    jours = pd.DatetimeIndex(["2026-09-06", "2026-09-07", "2026-09-09"], tz="UTC")
    assert suivi.trous(jours) == ["2026-09-08"]
    assert suivi.trous(jours[:2]) == [] and suivi.trous(jours[:0]) == []


# ------------------------------------------------------------------------------- consigne

@pytest.fixture(scope="module")
def reelles():
    return c2.donnees(fin=c2.FIN_BACKTEST)


@pytest.fixture(scope="module", params=["VC3", "VC2"])
def experience(request, reelles):
    """VC3 (poche maximum, spot) et VC2 (poche achetee, perpetuels) : deux chemins differents."""
    cfg = c2.config(request.param)
    return cfg, c2.calculer(reelles, cfg)


def _temoins(chemin) -> dict[str, int]:
    """Une journee de chaque regle : la consigne de la veille doit y mener exactement."""
    etat, to = chemin["etat"].to_numpy(), chemin["turnover"]
    debuts, episode = set(), False                 # meme notion d'episode que `derouler`
    for i, e in enumerate(etat):
        if e == B and not episode:
            debuts.add(i)
        episode = (episode or e == B) and e != H
    cas = {
        "debut d'episode baissier": lambda i: i in debuts and to[i] > 0,
        "sortie d'une alt en baissier": lambda i: etat[i] == B and i not in debuts and to[i] > 0,
        "reduction en veille": lambda i: etat[i] == V and to[i] > 0,
        "reequilibrage haussier": lambda i: etat[i] == H and etat[i - 1] == H and to[i] > 0,
        "haussier dans la bande": lambda i: etat[i] == H and etat[i - 1] == H and to[i] == 0.0,
    }
    return {nom: next(i for i in range(1, len(etat)) if f(i)) for nom, f in cas.items()}


def test_la_consigne_de_la_veille_est_la_position_du_jour(reelles, experience):
    cfg, chemin = experience
    for nom, i in _temoins(chemin).items():
        veille = chemin["jours"][i - 1]
        c = suivi.suivre(c2.tronquer(reelles, veille), cfg)["consigne"]
        assert c["date"] == chemin["jours"][i], nom
        assert c["etat"] == chemin["etat"].iat[i], nom
        assert c["votes"] == {k: int(v) for k, v in chemin["votes"].iloc[i].items()}, nom
        assert np.array_equal(c["position"], chemin["positions"][i]), nom
        assert c["turnover"] == chemin["turnover"][i] and c["trade"] == (c["turnover"] > 0), nom
        assert np.isclose(np.abs(c["ordres"]).sum(), c["turnover"], atol=1e-12), nom


def _synthetiques(n=420, debut="2023-01-01"):
    cal = pd.date_range(debut, periods=n, freq="D", tz="UTC")
    rng = np.random.default_rng(1)
    closes = pd.DataFrame({p: 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, n)))
                           for p in c2.vc.PAIRES}, index=cal)
    sess = pd.bdate_range(cal[0], cal[-1], tz="UTC")
    return {"closes": closes, "funding": pd.DataFrame(0.0001, index=cal, columns=c2.vc.PAIRES),
            "DFII10": pd.Series(np.linspace(1.0, 2.0, len(sess)), index=sess),
            "T10YIE": pd.Series(2.3, index=sess),
            "NASDAQ100": pd.Series(np.linspace(1e4, 1.2e4, len(sess)), index=sess),
            "fng": pd.Series(50.0, index=cal)}


def test_la_garde_attrape_une_fuite_du_futur(cfg, monkeypatch):
    d = _synthetiques()
    suivi.suivre(d, cfg)                                       # chaine causale : passe
    vrais_votes = c2.votes
    monkeypatch.setattr(c2, "votes", lambda d, cfg: vrais_votes(d, cfg).shift(-1).fillna(0.0))
    with pytest.raises(suivi.CausaliteError):
        suivi.suivre(d, cfg)
