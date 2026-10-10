"""VC4 : instants de session (heures d'ete comprises), identite avec VC3 a 00:00, causalite."""

import copy

import numpy as np
import pandas as pd
import pytest

from beta.strategies import voie_c2 as c2
from beta.strategies import voie_c4 as c4

UN_JOUR = pd.Timedelta(days=1)


def _t(s):
    return pd.Timestamp(s, tz="UTC")


@pytest.fixture(scope="module")
def cfg4():
    return c2.config("VC4")


@pytest.fixture(scope="module")
def reelles():
    return c2.donnees(fin=c2.FIN_BACKTEST)


@pytest.fixture(scope="module")
def cinq(reelles):
    # meme borne d'information que VC3 : la derniere bougie 1d se clot le lendemain a 00:00
    return c4.donnees_5m(debut=reelles["closes"].index[0], fin=c2.FIN_BACKTEST + UN_JOUR)


# ------------------------------------------------------------------------------- instants

@pytest.mark.parametrize("jour,attendu", [
    # ete des deux cotes (BST, EDT)
    ("2026-10-12", ["00:00", "07:00", "13:30"]),
    # Londres repasse a l'heure d'hiver le 25/10, New York le 01/11 : une semaine decalee
    ("2026-10-26", ["00:00", "08:00", "13:30"]),
    # hiver des deux cotes (GMT, EST)
    ("2026-11-02", ["00:00", "08:00", "14:30"]),
    # week-end : une seule decision
    ("2026-10-10", ["00:00"]), ("2026-10-11", ["00:00"]),
])
def test_instants_de_session_et_heures_d_ete(cfg4, jour, attendu):
    quand = c4.instants(_t(jour), _t(jour), cfg4["cadence"])
    assert [f"{t:%H:%M}" for t in quand] == attendu
    assert all(t.normalize() == _t(jour) for t in quand)


def test_le_prix_d_un_instant_est_la_bougie_close_a_cet_instant():
    serie = pd.Series([1.0, 2.0, 3.0], index=pd.DatetimeIndex(
        [_t("2026-10-12 06:55"), _t("2026-10-12 07:00"), _t("2026-10-12 07:05")]))
    prix = c4.prix_aux_instants({p: serie for p in c2.vc.PAIRES},
                                pd.DatetimeIndex([_t("2026-10-12 07:00"),
                                                  _t("2026-10-12 07:03"),
                                                  _t("2026-10-12 09:00")]))
    assert prix["BTC"].iloc[0] == 2.0                  # close a 07:00 pile
    assert prix["BTC"].iloc[1] == 2.0                  # 07:05 n'existe pas encore a 07:03
    assert np.isnan(prix["BTC"].iloc[2])               # plus de 30 min sans prix : absent


# --------------------------------------------------------------------- identite avec VC3

def test_une_cadence_de_00h_redonne_vc3_a_l_identique(reelles, cinq, cfg4):
    # Meme chaine, memes prix : si la seule difference avec VC3 est la cadence, alors a la
    # cadence de VC3 on doit retrouver VC3 au centime pres. C'est ce qui rend la mesure de
    # VC4 interpretable comme « l'effet de la cadence, et rien d'autre ».
    minuit = copy.deepcopy(cfg4)
    une = [{"session": "minuit", "heure": "00:00", "fuseau": "UTC"}]
    minuit["cadence"] = {**minuit["cadence"], "semaine": une, "week_end": une}
    v4 = c4.calculer(reelles, cinq, minuit)
    v3 = c2.calculer(reelles, c2.config("VC3"))
    assert v4["jours"].equals(v3["jours"])
    assert np.allclose(v4["r_net_jour"].to_numpy(), v3["r_net"], atol=1e-12, rtol=0)
    assert np.allclose(v4["positions"], v3["positions"], atol=1e-12, rtol=0)
    assert (v4["etat"].to_numpy() == v3["etat"].to_numpy()).all()


def test_les_sessions_ajoutent_des_decisions_en_semaine_seulement(reelles, cinq, cfg4):
    r = c4.calculer(reelles, cinq, cfg4)
    par_jour = pd.Series(1, index=r["instants"]).groupby(r["instants"].normalize()).sum()
    week_end = par_jour.index.weekday >= 5
    assert (par_jour[week_end] == 1).all() and (par_jour[~week_end] == 3).all()
    assert len(r["jours"]) == len(c2.calculer(reelles, c2.config("VC3"))["jours"])


# ------------------------------------------------------------------------------ causalite

@pytest.mark.parametrize("t", ["2022-11-09 14:30", "2025-04-07 07:00", "2025-04-07 13:30",
                               "2024-03-02 00:00"])
def test_causalite_troncature_et_perturbation(reelles, cinq, cfg4, t):
    ecarts = c4.epreuve_causalite(reelles, cinq, cfg4, _t(t))
    assert all(e == 0.0 for e in ecarts.values()), ecarts


def test_la_journee_en_cours_se_decide_sans_sa_bougie_quotidienne(reelles, cinq, cfg4):
    # En live, a 13:30 la bougie 1d du jour n'est pas close : la chaine doit decider quand meme
    jour = _t("2025-04-07")
    d = {k: (v[v.index < jour] if k == "closes" else v) for k, v in reelles.items()}
    r = c4.calculer(d, c4.tronquer_5m(cinq, jour + pd.Timedelta(hours=13, minutes=30)), cfg4,
                    fin=jour)
    assert [f"{t:%H:%M}" for t in r["instants"][r["instants"].normalize() == jour]] == [
        "00:00", "07:00", "13:30"]
    with pytest.raises(ValueError):
        c4.calculer(d, cinq, cfg4, fin=jour + UN_JOUR)      # deux jours d'avance : refuse
