"""Voie C2 : config preenregistree, votes, decalages, regles d'etat, causalite."""

import numpy as np
import pandas as pd
import pytest

from beta.strategies import voie_c2 as c2

H, B, V = c2.HAUSSIER, c2.BAISSIER, c2.VEILLE


@pytest.fixture(scope="module")
def cfg():
    return c2.config("VC2")


# ------------------------------------------------------------------------- config / registre

def test_configs_relues_dans_le_registre_avec_leur_empreinte():
    # Si ce test casse, la config a bouge depuis le preenregistrement du 07/10 : ce n'est plus
    # VC2. Nouvelle experience, nouveau journal, une ligne dans DECISIONS.md.
    assert c2.empreinte(c2.config("VC2")) == "744700fa7d8980fc"
    assert c2.empreinte(c2.config("VC2T")) == "7880a72b6e116005"


def test_temoin_sans_aucun_vote_macro():
    t = c2.config("VC2T")
    assert t["votes_macro"] == {} and t["seuils_etat"] == {"haussier": 1, "baissier": -1}
    assert {k: v for k, v in t.items() if k not in ("version", "votes_macro", "seuils_etat")} \
        == {k: v for k, v in c2.config("VC2").items()
            if k not in ("version", "votes_macro", "seuils_etat")}


# ------------------------------------------------------------------------------------ votes

def _jours(n, debut="2024-01-01"):
    return pd.date_range(debut, periods=n, freq="D", tz="UTC")


def test_variation_de_taux_compte_le_seuil_exact_et_le_sens():
    obs = pd.Series([1.75] * 3 + [1.85, 1.65, 1.70], index=_jours(6))
    reel = c2._score_variation(obs, 3, 0.10, signe_hausse=-1)
    # diff sur 3 obs : NaN NaN NaN +0,10 -0,10 -0,05
    assert np.isnan(reel.iloc[:3]).all()
    assert list(reel.iloc[3:]) == [-1.0, 1.0, 0.0]        # hausse du taux reel = baissier
    infl = c2._score_variation(obs, 3, 0.10, signe_hausse=1)
    assert list(infl.iloc[3:]) == [1.0, -1.0, 0.0]        # hausse de l'inflation = haussier


def test_fear_greed_seuils_arit():
    s = c2._score_fng(pd.Series([10, 24.9, 25, 44, 45, 90.0], index=_jours(6)), 25, 45)
    assert list(s) == [-1, -1, 0, 0, 1, 1]


def test_aligner_garde_le_week_end_et_perime_un_ferie():
    # Vendredi 2024-01-05 observe ; samedi/dimanche gardent la note (48 h) ; lundi ferie : 72 h
    cal = pd.date_range("2024-01-05", "2024-01-09", freq="D", tz="UTC")
    score = pd.Series([1.0], index=pd.DatetimeIndex(["2024-01-05"], tz="UTC"))
    out = c2._aligner(score, cal, perime_h=48)
    assert list(out) == [1.0, 1.0, 1.0, 0.0, 0.0]


def _sessions(n, debut="2023-01-02"):
    return pd.bdate_range(debut, periods=n, tz="UTC")


def test_vote_nasdaq_ne_vaut_jamais_plus_un_et_casse_quand_couple(cfg):
    p = cfg["votes_macro"]["nasdaq"]
    rng = np.random.default_rng(0)
    sess = _sessions(260)
    r = rng.normal(0, 0.01, len(sess))
    r[200:205] = -0.04                                   # cassure franche
    r[230:235] = +0.04                                   # cassure haussiere : jamais +1
    nas = pd.Series(10000 * np.exp(np.cumsum(r)), index=sess)
    cal = pd.date_range(sess[0], sess[-1], freq="D", tz="UTC")
    btc = pd.Series(30000 * np.exp(np.cumsum(r)), index=sess).reindex(cal).ffill()  # couple
    v = c2._vote_nasdaq(nas, btc, p, cal)
    assert set(np.unique(v)) <= {-1.0, 0.0}
    assert (v.loc[sess[200]:sess[204]] == -1.0).any()
    # decouple : BTC independant => jamais de veto
    btc_ind = pd.Series(30000 * np.exp(np.cumsum(rng.normal(0, 0.01, len(cal)))), index=cal)
    assert (c2._vote_nasdaq(nas, btc_ind, p, cal) == 0.0).all()


def _donnees_synthetiques(n=420, debut="2023-01-01"):
    cal = _jours(n, debut)
    rng = np.random.default_rng(1)
    closes = pd.DataFrame({p: 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, n)))
                           for p in c2.vc.PAIRES}, index=cal)
    funding = pd.DataFrame(0.0001, index=cal, columns=c2.vc.PAIRES)
    sess = pd.bdate_range(cal[0], cal[-1], tz="UTC")
    return {"closes": closes, "funding": funding,
            "DFII10": pd.Series(np.linspace(1.0, 2.0, len(sess)), index=sess),
            "T10YIE": pd.Series(2.3, index=sess),
            "NASDAQ100": pd.Series(np.linspace(1e4, 1.2e4, len(sess)), index=sess),
            "fng": pd.Series(50.0, index=cal)}


@pytest.mark.parametrize("cle,decalage", [("DFII10", 2), ("T10YIE", 2), ("fng", 1)])
def test_decalages_point_in_time(cfg, cle, decalage):
    d = _donnees_synthetiques()
    base = c2.votes(d, cfg)
    jour = pd.Timestamp("2024-01-10", tz="UTC")             # un mercredi
    fausse = {k: v.copy() for k, v in d.items()}
    fausse[cle].loc[jour] = 10.0 if cle == "fng" else fausse[cle].loc[jour] - 5.0
    apres = c2.votes(fausse, cfg)
    differe = (apres != base).any(axis=1)
    premier = differe[differe].index.min()
    assert premier == jour + pd.Timedelta(days=decalage)


def test_momentum_btc_decale_d_un_jour(cfg):
    d = _donnees_synthetiques()
    base = c2.votes(d, cfg)["momentum_btc"]
    jour = pd.Timestamp("2024-01-10", tz="UTC")
    d["closes"].loc[jour, "BTC"] *= 0.01                  # effondrement au jour J
    apres = c2.votes(d, cfg)["momentum_btc"]
    assert (apres.loc[:jour] == base.loc[:jour]).all()
    assert apres.loc[jour + pd.Timedelta(days=1)] == -1.0


def test_etats_aux_seuils(cfg):
    v = pd.DataFrame({"a": [1, 1, 1, -1, -1, 0], "b": [1, 0, 0, -1, 0, 0],
                      "c": [0, 0, -1, 0, -1, 0]}, index=_jours(6))
    assert list(c2.etats(v, cfg)) == [H, V, V, B, B, V]
    t = c2.config("VC2T")
    assert list(c2.etats(pd.DataFrame({"m": [1, -1, 0]}, index=_jours(3)), t)) == [H, B, V]


# ------------------------------------------------------------------------------ deroulement

def _derouler(cfg, etats, cible, rend=None, alt_baisse=None, fund=None):
    n, k = len(etats), 6
    cible = np.asarray(cible, float).reshape(n, k)
    rend = np.zeros((n, k)) if rend is None else np.asarray(rend, float)
    fund = np.zeros((n, k)) if fund is None else np.asarray(fund, float)
    alt_baisse = np.zeros((n, k - 1), bool) if alt_baisse is None else alt_baisse
    return c2.derouler(np.array(etats, object), cible, rend, fund, alt_baisse, cfg)


def test_haussier_entre_puis_respecte_la_bande(cfg):
    c = np.array([[0.3] * 6, [0.3] * 5 + [0.4], [0.3] * 5 + [0.6]])
    out = _derouler(cfg, [H, H, H], c)
    assert np.allclose(out["positions"][0], 0.3)                  # entree depuis plat
    assert np.allclose(out["positions"][1], 0.3)                  # ecart 0,1 < bande 0,2
    assert np.isclose(out["positions"][2][5], 0.6)                # ecart 0,3 > bande


def test_baissier_poche_btc_alts_moitie_puis_tendance_propre(cfg):
    c = np.full((4, 6), 0.3)
    rend = np.zeros((4, 6))
    rend[0, :] = -0.2                                              # l'equite baisse de 36 %
    baisse = np.zeros((4, 5), bool)
    baisse[3, 1] = True                                            # SOL passe sous 0 au jour 3
    out = _derouler(cfg, [H, B, B, B], c, rend=rend, alt_baisse=baisse)
    e1 = out["equite_debut"][1]
    assert np.isclose(e1, 1 + out["r_net"][0]) and e1 < 0.65       # -36 % et les frais
    pos = out["positions"]
    assert np.isclose(pos[1][0], min(0.25 / e1, 1.0))              # 25 % du plus haut
    derive = 0.3 * 0.8 / (1 + out["r_brut"][0])
    assert np.allclose(pos[1][1:], derive * 0.5)                   # derive puis -50 %
    assert np.allclose(pos[2], pos[1])                             # elle flotte, rien d'autre
    assert pos[3][2] == 0.0 and np.isclose(pos[3][1], pos[2][1])   # seul SOL sort
    assert out["episodes"] == 1


def test_baissier_poche_plafonnee_a_100_pourcent(cfg):
    rend = np.zeros((2, 6))
    rend[0, :] = -0.8                                              # brut 1 : equite ~0,2
    out = _derouler(cfg, [H, B], np.full((2, 6), 1 / 6), rend=rend)
    assert 0.25 / out["equite_debut"][1] > 1.0
    assert out["positions"][1][0] == 1.0


def test_ruine_arrete_le_deroulement(cfg):
    rend = np.zeros((2, 6))
    rend[0, :] = -0.9
    with pytest.raises(RuntimeError, match="ruine"):
        _derouler(cfg, [H, H], np.full((2, 6), 1 / 3), rend=rend)


def test_veille_sans_ajout_avec_reduction_au_prorata(cfg):
    c = np.array([[0.2] * 6, [0.5] * 6, [0.05] * 6])
    out = _derouler(cfg, [H, V, V], c)
    assert np.allclose(out["positions"][1], 0.2)                   # voulu plus haut : rien
    assert np.allclose(out["positions"][2], 0.05)                  # 1,2 -> 0,3 : au prorata


def test_veille_dans_un_episode_ne_le_relance_pas(cfg):
    c = np.full((5, 6), 0.3)
    out = _derouler(cfg, [H, B, V, B, H], c)
    assert out["episodes"] == 1
    assert np.allclose(out["positions"][3], out["positions"][1])   # pas de 2e coupe des alts
    assert np.allclose(out["positions"][4], 0.3)                   # le haussier reprend tout


def test_frais_par_paire_et_funding_paye_par_le_long(cfg):
    c = np.zeros((1, 6))
    c[0, 0], c[0, 2] = 1.0, 1.0                                    # 1x BTC, 1x SOL
    fund = np.zeros((1, 6))
    fund[0, 0] = 0.001
    out = _derouler(cfg, [H], c, fund=fund)
    assert np.isclose(out["frais"][0], (5 + 5) / 1e4 + (5 + 10) / 1e4)
    assert np.isclose(out["funding"][0], 0.001)
    assert np.isclose(out["r_net"][0], -out["frais"][0] - 0.001)


# ------------------------------------------------------------------------------------- VC3

@pytest.fixture(scope="module")
def cfg3():
    return c2.config("VC3")


def test_vc3_relue_dans_le_registre_avec_son_empreinte(cfg3):
    # Preenregistree le 07/10 apres la mesure de VC2 : poche « maximum » et spot. Si ce test
    # casse, ce n'est plus VC3.
    assert c2.empreinte(cfg3) == "7adef08a837a8c50"


def test_vc3_ne_differe_de_vc2_que_par_la_poche_le_spot_et_les_frais(cfg3):
    v2 = c2.config("VC2")
    assert cfg3["baissier"] == {**v2["baissier"], "poche": "maximum"}
    assert cfg3["instrument"] == "spot" and cfg3["plafond_brut"] == 1.0
    assert cfg3["frais"] == {**v2["frais"], "taker_pb": 10.0}
    autres = ("version", "baissier", "instrument", "plafond_brut", "frais")
    assert {k: v for k, v in cfg3.items() if k not in autres} \
        == {k: v for k, v in v2.items() if k not in autres}


def test_poche_maximum_ne_rachete_jamais_de_btc(cfg3):
    c = np.full((2, 6), 0.05)                                      # 5 % de BTC au signal
    out = _derouler(cfg3, [H, B], c)
    assert np.isclose(out["positions"][1][0], 0.05)                # VC2 serait montee a 25 %
    assert np.allclose(out["positions"][1][1:], 0.025)             # alts -50 %, comme VC2


def test_poche_maximum_vend_au_dessus_de_25_pourcent_du_plus_haut(cfg3):
    c = np.zeros((2, 6))
    c[:, 0] = 0.6
    out = _derouler(cfg3, [H, B], c)
    assert np.isclose(out["positions"][1][0], 0.25 / out["equite_debut"][1])


def test_spot_sans_funding_avec_frais_spot(cfg3):
    c = np.zeros((1, 6))
    c[0, 0], c[0, 2] = 0.5, 0.5                                    # 0,5 BTC, 0,5 SOL
    out = _derouler(cfg3, [H], c, fund=np.full((1, 6), 0.001))
    assert out["funding"][0] == 0.0
    assert np.isclose(out["frais"][0], 0.5 * (10 + 5) / 1e4 + 0.5 * (10 + 10) / 1e4)


def test_spot_plafonne_le_brut_a_1_au_prorata(cfg3):
    out = _derouler(cfg3, [H, V], np.full((2, 6), 0.3))            # le moteur veut 1,8x
    assert np.allclose(out["positions"][0], 1 / 6)
    assert np.allclose(out["positions"][1], 1 / 6)                 # veille : ni ajout ni coupe


# ------------------------------------------------------------------- causalite, donnees reelles

@pytest.fixture(scope="module")
def reelles():
    return c2.donnees(fin=c2.FIN_BACKTEST)


@pytest.mark.parametrize("id_exp", ["VC2", "VC2T", "VC3"])
@pytest.mark.parametrize("t", ["2022-11-09", "2025-04-07"])
def test_causalite_troncature_et_perturbation(reelles, id_exp, t):
    ecarts = c2.epreuve_causalite(reelles, c2.config(id_exp), pd.Timestamp(t, tz="UTC"))
    assert all(e == 0.0 for e in ecarts.values()), ecarts
