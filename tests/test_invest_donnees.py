"""Test invest — donnees : publication FRED (D1), votes point-in-time, controles (C5)."""

import numpy as np
import pandas as pd
import pytest

from beta.invest import donnees as dn
from beta.strategies import voie_c2 as c2

T = lambda s: pd.Timestamp(s, tz="UTC")                                   # noqa: E731


# --------------------------------------------------------------- calendrier de publication

def test_disponibilite_jour_ouvre_suivant_plus_un_jour():
    obs = pd.DatetimeIndex([T("2026-10-08"), T("2026-10-09"), T("2026-10-12"),
                            T("2026-10-16"), T("2026-11-25")])
    attendu = [T("2026-10-10"),     # jeudi -> publie vendredi -> utilisable samedi
               T("2026-10-14"),     # vendredi -> lundi 12/10 ferie (Columbus) -> mardi -> mercredi
               T("2026-10-14"),     # lundi ferie (seance NASDAQ) -> publie mardi -> mercredi
               T("2026-10-20"),     # vendredi -> lundi -> mardi
               T("2026-11-28")]     # veille de Thanksgiving -> vendredi -> samedi
    assert list(dn.disponibilite(obs)) == attendu


def test_vote_publie_derniere_observation_publiee_et_peremption():
    score = pd.Series([1.0, -1.0, 1.0, 0.0],
                      index=pd.DatetimeIndex([T("2026-10-08"), T("2026-10-09"),
                                              T("2026-10-13"), T("2026-10-14")]))
    cal = pd.date_range(T("2026-10-10"), T("2026-10-16"), freq="D")
    v = dn.vote_publie(score, cal, age_max_j=4)
    assert v.to_dict() == {
        T("2026-10-10"): 1.0,     # jeudi, age 2 j
        T("2026-10-11"): 1.0,     # le vendredi n'est pas encore publie
        T("2026-10-12"): 1.0,     # jeudi, age 4 j : encore frais
        T("2026-10-13"): 0.0,     # jeudi, age 5 j : perime (le live du 13/10 disait 0)
        T("2026-10-14"): 0.0,     # vendredi enfin publie, mais age 5 j : perime
        T("2026-10-15"): 1.0,     # mardi 13/10, publie le 14
        T("2026-10-16"): 0.0,     # mercredi 14/10
    }


def test_vote_publie_zero_avant_la_premiere_publication_et_en_rodage():
    score = pd.Series([np.nan, 1.0], index=pd.DatetimeIndex([T("2026-10-05"), T("2026-10-06")]))
    cal = pd.date_range(T("2026-10-05"), T("2026-10-08"), freq="D")
    v = dn.vote_publie(score, cal, age_max_j=4)
    assert v.tolist() == [0.0, 0.0, 0.0, 1.0]      # 05 et 06 : rien de publie ; 07 : NaN -> 0


# ------------------------------------------- equivalence avec le code du socle (voie_c2)

def _jours_ouvres(debut, fin):
    jours = pd.bdate_range(debut, fin, tz="UTC")
    feries = pd.DatetimeIndex(dn.feries_us(jours[0], jours[-1]))
    return jours[~jours.tz_localize(None).isin(feries)]


def _vote_socle_sur_publie(obs: pd.Series, p: dict, cal: pd.DatetimeIndex, t) -> float:
    """Ce que `voie_c2.votes` aurait calcule a t avec les seules observations publiees a t."""
    publie = obs[dn.disponibilite(obs.index) <= t]
    score = c2._score_variation(publie, p["fenetre_obs"], p["seuil_pt"], p["signe_hausse"])
    return float(c2._aligner(score, cal, p["perime_h"]).shift(2).fillna(0.0).loc[t])


def test_vote_variation_publie_egal_au_socle_rejoue_sur_les_seules_donnees_publiees():
    rng = np.random.default_rng(7)
    jours = _jours_ouvres("2026-05-01", "2026-12-31")
    obs = pd.Series(np.round(2.0 + np.cumsum(rng.normal(0, 0.03, len(jours))), 2), index=jours)
    p = {"fenetre_obs": 60, "seuil_pt": 0.1, "signe_hausse": -1, "perime_h": 48}
    cal = pd.date_range(T("2026-05-01"), T("2026-12-31"), freq="D")
    score = c2._score_variation(obs, p["fenetre_obs"], p["seuil_pt"], p["signe_hausse"])
    rapide = dn.vote_publie(score, cal, dn.age_max_j(p, decalage_j=2))
    for t in cal[cal >= T("2026-08-15")]:
        assert rapide.loc[t] == _vote_socle_sur_publie(obs, p, cal, t), t


def test_vote_nasdaq_publie_egal_au_socle_rejoue_sur_les_seules_donnees_publiees():
    rng = np.random.default_rng(11)
    cal = pd.date_range(T("2025-11-01"), T("2026-12-31"), freq="D")
    btc = pd.Series(np.exp(np.cumsum(rng.normal(0, 0.03, len(cal)))) * 1e4, index=cal)
    seances = _jours_ouvres("2025-11-01", "2026-12-31")
    commun = np.log(btc.reindex(seances).to_numpy())
    nas = pd.Series(np.exp(0.8 * commun + np.cumsum(rng.normal(0, 0.01, len(seances)))) * 1e3,
                    index=seances)
    p = {"cassure_obs": 20, "rho_court": 30, "rho_long": 90, "arme_si": 0.5,
         "confirme_long_si": 0.3, "desarme_sous": 0.3, "perime_h": 120}
    rapide = dn.vote_publie(dn.vote_nasdaq_seances(nas, btc, p), cal,
                            dn.age_max_j(p, decalage_j=2))
    assert (rapide != 0).sum() > 10                    # le cas teste n'est pas trivial
    for t in cal[cal >= T("2026-06-01")]:
        publie = nas[dn.disponibilite(nas.index) <= t]
        socle = c2._vote_nasdaq(publie, btc, p, cal).shift(2).fillna(0.0).loc[t]
        assert rapide.loc[t] == socle, t


# --------------------------------------------------------------------------- votes PIT

def _donnees_synthetiques():
    rng = np.random.default_rng(3)
    cal = pd.date_range(T("2025-01-01"), T("2026-10-19"), freq="D")
    closes = pd.DataFrame(np.exp(np.cumsum(rng.normal(0, 0.03, (len(cal), 6)), axis=0)) * 100,
                          index=cal, columns=["BTC", "ETH", "SOL", "BNB", "LINK", "XRP"])
    jours = _jours_ouvres("2025-01-01", "2026-10-19")
    fred = lambda: pd.Series(np.round(2 + np.cumsum(rng.normal(0, 0.03, len(jours))), 2),  # noqa: E731
                             index=jours)
    # NASDAQ couple a BTC : sans couplage, le vote NASDAQ vaudrait toujours 0
    lien = 0.8 * np.log(closes["BTC"].reindex(jours).to_numpy())
    nas = pd.Series(np.exp(lien + np.cumsum(rng.normal(0, 0.01, len(jours)))) * 2e4, index=jours)
    fng = pd.Series(rng.integers(5, 95, len(cal)).astype(float), index=cal)
    return {"closes": closes, "funding": closes * 0.0, "DFII10": fred(), "T10YIE": fred(),
            "NASDAQ100": nas, "fng": fng}


def _cfg():
    return {"vote_momentum": {"actif": "BTC", "fenetre": 126},
            "votes_macro": {
                "taux_reel_10a": {"fred": "DFII10", "fenetre_obs": 60, "seuil_pt": 0.1,
                                  "signe_hausse": -1, "perime_h": 48},
                "inflation_anticipee_10a": {"fred": "T10YIE", "fenetre_obs": 60,
                                            "seuil_pt": 0.1, "signe_hausse": 1, "perime_h": 48},
                "nasdaq": {"fred": "NASDAQ100", "cassure_obs": 20, "rho_court": 30,
                           "rho_long": 90, "arme_si": 0.5, "confirme_long_si": 0.3,
                           "desarme_sous": 0.3, "perime_h": 120},
                "fear_greed": {"bas": 25, "haut": 45, "perime_h": 48}},
            "decalages": {"prix_j": 1, "fng_j": 1, "fred_j": 2},
            "seuils_etat": {"haussier": 2, "baissier": -2}}


def test_votes_pit_ne_remplacent_que_dfii10_et_nasdaq():
    d, cfg = _donnees_synthetiques(), _cfg()
    socle, pit = c2.votes(d, cfg), dn.votes_pit(d, cfg)
    assert list(pit.columns) == list(socle.columns) == list(dn.VOTES)
    for nom in ("momentum_btc", "inflation_anticipee_10a", "fear_greed"):
        pd.testing.assert_series_equal(pit[nom], socle[nom])
    for nom in ("taux_reel_10a", "nasdaq"):
        assert (pit[nom] != socle[nom]).any()                      # le week-end, entre autres
        meme = pit.index.dayofweek.isin([2, 3, 4, 5])              # mercredi -> samedi
        assert (pit[nom][meme] == socle[nom][meme]).mean() > 0.95  # hors lendemains de feries


# ------------------------------------------------------------------------ controles (C5)

def test_controle_accepte_des_donnees_completes():
    d = _donnees_synthetiques()
    assert dn.controler(d, T("2025-06-01"), T("2026-10-19")) == []


def test_controle_arrete_sur_un_jour_de_prix_manquant():
    d = _donnees_synthetiques()
    d["closes"] = d["closes"].drop(T("2026-03-03"))
    with pytest.raises(dn.DonneesError, match="2026-03-03"):
        dn.controler(d, T("2025-06-01"), T("2026-10-19"))


def test_controle_arrete_sur_une_cloture_absente():
    d = _donnees_synthetiques()
    d["closes"].loc[T("2026-04-01"), "SOL"] = np.nan
    with pytest.raises(dn.DonneesError, match="SOL"):
        dn.controler(d, T("2025-06-01"), T("2026-10-19"))


def test_controle_arrete_si_les_prix_s_arretent_avant_la_fin():
    d = _donnees_synthetiques()
    d["closes"] = d["closes"][d["closes"].index <= T("2026-10-17")]
    with pytest.raises(dn.DonneesError, match="prix"):
        dn.controler(d, T("2025-06-01"), T("2026-10-19"))


def test_controle_arrete_sur_un_trou_fred_de_plus_de_4_jours():
    d = _donnees_synthetiques()
    trou = (d["DFII10"].index >= T("2026-02-02")) & (d["DFII10"].index <= T("2026-02-06"))
    d["DFII10"] = d["DFII10"][~trou]
    with pytest.raises(dn.DonneesError, match="DFII10"):
        dn.controler(d, T("2025-06-01"), T("2026-10-19"))


def test_controle_arrete_si_une_serie_fred_est_en_retard():
    d = _donnees_synthetiques()
    d["NASDAQ100"] = d["NASDAQ100"][d["NASDAQ100"].index <= T("2026-10-09")]
    with pytest.raises(dn.DonneesError, match="NASDAQ100"):
        dn.controler(d, T("2025-06-01"), T("2026-10-19"))


def test_controle_fng_n_accepte_que_le_trou_decide_par_jonas():
    jours = pd.date_range(T("2024-10-19"), T("2026-10-19"), freq="D")   # F&G de t-1 a t
    fng = pd.Series(50.0, index=jours.drop(T("2024-10-26")))
    assert dn.controler_fng(fng, T("2024-10-20"), T("2026-10-19")) == ["fear_greed 2024-10-26"]
    with pytest.raises(dn.DonneesError, match="2026-01-15"):
        dn.controler_fng(fng.drop(T("2026-01-15")), T("2024-10-20"), T("2026-10-19"))
    with pytest.raises(dn.DonneesError, match="fear_greed"):
        dn.controler_fng(fng[fng.index <= T("2026-10-10")], T("2024-10-20"), T("2026-10-19"))


def test_controle_du_rodage_des_votes_avant_le_debut():
    d = _donnees_synthetiques()                        # BTC depuis le 2025-01-01
    dn.controler_rodage(d, _cfg(), T("2025-09-01"))    # 126 j de momentum, 90 seances : OK
    with pytest.raises(dn.DonneesError, match="momentum"):
        dn.controler_rodage(d, _cfg(), T("2025-03-01"))


def test_diagnostic_pit_compte_les_jours_ou_les_votes_et_l_etat_different():
    cal = pd.date_range(T("2026-10-05"), T("2026-10-18"), freq="D")      # lundi -> dimanche
    socle = pd.DataFrame(0.0, index=cal, columns=list(dn.VOTES))
    socle["momentum_btc"] = 1.0
    socle["fear_greed"] = 1.0
    pit = socle.copy()
    pit.loc[T("2026-10-11"), "taux_reel_10a"] = 1.0       # dimanche : somme 3 contre 2, meme etat
    pit.loc[T("2026-10-12"), "nasdaq"] = -1.0             # lundi : somme 1, veille contre haussier
    diag = dn.diagnostic_pit(socle, pit, _cfg(), {"p": (T("2026-10-05"), T("2026-10-18"))})
    p = diag["p"]
    assert p["jours"] == 14
    assert p["votes"]["taux_reel_10a"] == {"jours": 1, "par_jour": {"dim": 1}}
    assert p["votes"]["nasdaq"] == {"jours": 1, "par_jour": {"lun": 1}}
    assert p["votes"]["momentum_btc"]["jours"] == 0
    assert p["etat"] == {"jours": 1, "dates": ["2026-10-12"]}


def test_empreinte_stable_et_sensible_a_une_valeur():
    d = _donnees_synthetiques()
    votes = dn.votes_pit(d, _cfg())
    a = dn.empreinte(d["closes"], votes)
    assert a == dn.empreinte(d["closes"].copy(), votes.copy()) and len(a) == 16
    d["closes"].iloc[100, 2] *= 1.0001
    assert dn.empreinte(d["closes"], votes) != a


# ------------------------------------------------- le cas reel du 13/10 (journal du live)

@pytest.mark.skipif(not dn.lake_disponible(), reason="lake BETA absent")
def test_le_13_10_le_vote_publie_retrouve_le_live():
    d = c2.donnees(T("2026-10-19"))
    cfg = c2.config("VC3")
    assert c2.votes(d, cfg).loc[T("2026-10-13"), "taux_reel_10a"] == -1.0   # decalage fixe
    assert dn.votes_pit(d, cfg).loc[T("2026-10-13"), "taux_reel_10a"] == 0.0  # = le live
