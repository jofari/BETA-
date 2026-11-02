"""VC6 V2 : moteur, nulls et decision sur donnees synthetiques (aucune source vivante)."""

import numpy as np
import pandas as pd
import pytest

from beta.invest import nulls as nl
from beta.vc6 import moteur as mt1
from beta.vc6 import regles as R1
from beta.vc6_v2 import decision
from beta.vc6_v2 import donnees as dn
from beta.vc6_v2 import moteur as mt
from beta.vc6_v2 import nulls as nu
from beta.vc6_v2 import regles as R


def _ent(baissier, sigma=0.5, funding=0.0, r=0.0, poches=("BTC",)):
    n = len(baissier)
    jours = pd.date_range("2030-01-01", periods=n, freq="D")
    return mt.Entrees(
        jours=jours, baissier=np.asarray(baissier, dtype=bool),
        sigma={a: np.full(n, sigma) for a in poches},
        funding_annuel={a: np.full(n, funding * 365) for a in poches},
        funding_jour={a: np.full(n, funding) for a in poches},
        rendements={a: np.full(n, r) for a in set(poches) | {"BTC"}})


def _ent_aleatoire(n=400, graine=1):
    rng = np.random.default_rng(graine)
    jours = pd.date_range("2030-01-01", periods=n, freq="D")
    baissier = np.repeat(rng.random(n // 4) < 0.4, 4)[:n]
    baissier[::37] = ~baissier[::37]                # des bascules pendant les rampes
    poches = ("BTC", "ETH", "SOL")
    rend = {a: rng.normal(0.0, 0.04, n) for a in poches}
    for a in poches:
        rend[a][0] = np.nan
    return mt.Entrees(
        jours=jours, baissier=baissier,
        sigma={a: rng.uniform(0.08, 1.5, n) for a in poches},
        funding_annuel={a: rng.uniform(-0.1, 0.4, n) for a in poches},
        funding_jour={a: rng.uniform(-0.0003, 0.001, n) for a in poches},
        rendements=rend)


def test_valeurs_reprises_de_la_v1():
    for nom in ("POIDS", "SMA", "CLIP_BAS", "CLIP_HAUT", "FUNDING_SEUIL", "MARGE",
                "K_SIGMA_LIQ", "JOURS_AN", "RAMPE", "BANDE", "FRAIS_PB", "POCHE_BAISSIERE",
                "FUNDING_AVANT_PERP", "FUNDING_AVANT_PERP_JUSQU_A",
                "REGLEMENTS_PAR_JOUR_AVANT_PERP", "FENETRE_ECART_TYPE", "B_NULLS", "GRAINE",
                "M_DECALAGE", "SEUIL_P", "SEUIL_PBO", "FIN", "DEBUT_PRINCIPAL",
                "DEBUT_ROBUSTESSE"):
        assert getattr(R, nom) == getattr(R1, nom), nom
    assert R.CIBLE == R1.VARIANTES["vol"]["cible"]
    assert all(R1.SHA256[k] == v for k, v in R.SHA256.items())


def test_har_sans_regime_toujours_investi():
    ent = _ent([False, True, True, False, True], poches=("BTC", "ETH", "SOL"))
    sim = mt.simuler(ent, mt.parametres_essai("har_sans_regime"))
    assert sim["lignes"] == [("poche", "BTC"), ("poche", "ETH"), ("poche", "SOL")]
    assert np.allclose(sim["y"], [[0.25, 0.125, 0.125]] * 4)
    assert not sim["en_rampe"].any() and not sim["baissier"].any()


@pytest.mark.parametrize("sigma, attendu", [(0.5, 0.125), (2.0, 0.05), (0.1, 0.25)])
def test_poche_baissiere_sous_har(sigma, attendu):
    # E_BTC = clip(0,25 / sigma ; 0,2 ; 1) : 0,5 ; 0,2 (plancher) ; 1 (plafond, pas de levier)
    ent = _ent([True, True, True], sigma=sigma)
    sim = mt.simuler(ent, mt.Parametres(poids={"BTC": 1.0}))
    assert sim["y"][:, 1].tolist() == pytest.approx([attendu, attendu])
    assert sim["y"][:, 0].tolist() == pytest.approx([0.0, 0.0])
    assert sim["financement"].tolist() == pytest.approx([0.0, 0.0])


def test_bande_sur_la_poche_baissiere():
    ent = _ent([True] * 4)
    ent.sigma["BTC"] = np.array([0.5, 0.48, 0.40, 0.40])   # E_BTC 0,5 ; 0,521 ; 0,625
    sim = mt.simuler(ent, mt.Parametres(poids={"BTC": 1.0}))
    # 0,125 -> 0,130 (4,2 % < 10 %) : inchange ; -> 0,15625 (25 %) : change
    assert sim["y"][:, 1].tolist() == pytest.approx([0.125, 0.125, 0.15625])


def test_rampe_vers_la_poche_baissiere_sous_har():
    ent = _ent([False] + [True] * 7, sigma=0.5)
    sim = mt.simuler(ent, mt.Parametres(poids={"BTC": 1.0}, frais_pb=0.0))
    assert sim["y"][:, 0].tolist() == pytest.approx([0.5, 0.4, 0.3, 0.2, 0.1, 0.0, 0.0])
    assert sim["y"][:, 1].tolist() == pytest.approx([0.0, 0.025, 0.05, 0.075, 0.1, 0.125, 0.125])
    assert sim["en_rampe"].tolist() == [False, True, True, True, True, True, False]


def test_e_btc_force_a_1_redonne_la_v1_au_bit_pres():
    ent = _ent_aleatoire()
    v1 = mt1.simuler(ent, mt1.Parametres(sizing="vol", cible=0.25, baissiere={"BTC": 0.25}))
    p = mt.parametres_essai("poche_baissiere_har")
    p.e_baissiere_force = 1.0
    v2 = mt.simuler(ent, p)
    assert v1["baissier"].sum() > 50 and v1["en_rampe"].sum() > 50
    for cle in ("r", "y", "frais", "financement", "levier_brut", "contraint"):
        assert np.array_equal(v1[cle], v2[cle]), cle


def test_sans_regime_redonne_la_v1_au_bit_pres():
    ent = _ent_aleatoire(graine=2)
    v1 = mt1.simuler(ent, mt1.Parametres(regime=False, baissiere={}, sizing="vol", cible=0.25))
    v2 = mt.simuler(ent, mt.parametres_essai("har_sans_regime"))
    assert (v2["e"] > 1).any() and (v2["financement"] != 0).any()   # levier et financement
    for cle in ("r", "y", "frais", "financement"):
        assert np.array_equal(v1[cle], v2[cle]), cle


def test_pnl_redonne_le_rendement_du_moteur():
    ent = _ent_aleatoire(graine=3)
    for cle in R.ESSAIS:
        p = mt.parametres_essai(cle)
        sim = mt.simuler(ent, p)
        r = mt.pnl(ent, sim["lignes"], sim["poches"], p.poids, sim["y"], p.frais_pb)["r"]
        assert np.array_equal(r, sim["r"])


def test_securite_de_la_poche_baissiere():
    assert mt.e_baissiere(0.5, mt.Parametres()) == 0.5
    with pytest.raises(mt.MoteurError):
        mt.e_baissiere(mt.SIGMA_MAX_BAISSIERE * 1.01, mt.Parametres())
    # a ce sigma, la securite de liquidation contraindrait une exposition de 1
    s = mt.SIGMA_MAX_BAISSIERE * 1.01
    assert 1.0 / (R.MARGE + R.K_SIGMA_LIQ * s / np.sqrt(365)) < 1.0


def test_decaler_et_permuter_les_blocs():
    x = np.arange(10).reshape(5, 2)
    assert nu.decaler(x, 2).tolist() == [[4, 5], [6, 7], [8, 9], [0, 1], [2, 3]]
    assert nu.decaler(x, 0).tolist() == x.tolist()
    y = np.arange(130)
    assert nu.n_blocs(130) == 3                         # 63 + 63 + 4
    z = nu.permuter_blocs(y, [2, 0, 1])
    assert z[:4].tolist() == [126, 127, 128, 129] and z[4] == 0 and len(z) == 130
    assert np.array_equal(nu.permuter_blocs(y, [0, 1, 2]), y)
    assert nu.n_blocs(1979) == 32                       # 31 x 63 + 26
    with pytest.raises(ValueError):
        nu.permuter_blocs(y, [0, 0, 1])


def test_tirage_de_k_comme_la_v1():
    rng1, rng2 = nl.flux(0, "test"), nl.flux(0, "test")
    s = np.arange(500.0)
    for _ in range(50):
        k = nu.tirer_k(500, rng1)
        assert 90 <= k <= 410
        assert np.array_equal(nu.decaler(s, k), nl.decalage_circulaire(s, rng2, m=90))


def test_nulls_a_decalage_nul_et_distributions():
    ent = _ent_aleatoire(n=300, graine=4)
    assert np.array_equal(nu.mode_circulaire(ent, 0), ent.baissier)
    p1 = mt.parametres_essai("har_sans_regime")
    s1 = mt.simuler(ent, p1)
    assert np.array_equal(nu.r_positions(ent, s1, p1, nu.decaler(s1["y"], 0)), s1["r"])
    d1 = nu.distribution_positions(ent, p1, s1, "x", b=4)
    p2 = mt.parametres_essai("poche_baissiere_har")
    d2 = nu.distribution_mode(ent, p2, "y", b=4)
    for d in (d1, d2):
        assert set(d) == {"circulaire", "segments"}
        assert all(len(v) == 4 and np.isfinite(v).all() for v in d.values())
    pv = nu.p_values(d1, nu.ulcer(s1["r"]))
    assert pv["p_retenue"] == max(pv["p_circulaire"], pv["p_segments"])


def test_entrees_anticipees():
    ent = _ent([False] * 5, poches=("BTC",))
    rv = pd.DataFrame({"BTC": [0.0001, 0.0004, np.nan, 0.0009, 0.0016]}, index=ent.jours)
    ent_c, garde = dn.entrees_anticipees(ent, rv)
    attendu = [np.sqrt(365 * 0.0004), 0.5, np.sqrt(365 * 0.0009), np.sqrt(365 * 0.0016), 0.5]
    assert ent_c.sigma["BTC"].tolist() == pytest.approx(attendu)
    assert garde == {"BTC": 1}


def test_regles_de_decision():
    assert decision.utile(0.10, 0.20, 0.049)
    assert not decision.utile(0.10, 0.20, 0.05)
    assert not decision.utile(0.20, 0.10, 0.001)
    assert not decision.utile(0.10, 0.20, None)
    c = decision.configuration_retenue
    a, b = "har_sans_regime", "poche_baissiere_har"
    assert c({a: {"utile": False, "ratio": 1.0}, b: {"utile": False, "ratio": 2.0}})[
        "retenue"] is None
    assert c({a: {"utile": True, "ratio": 1.0}, b: {"utile": False, "ratio": 2.0}})["retenue"] == a
    assert c({a: {"utile": True, "ratio": 1.0}, b: {"utile": True, "ratio": 2.0}})["retenue"] == b
    with pytest.raises(decision.DecisionError):
        c({a: {"utile": True, "ratio": 1.0}, b: {"utile": True, "ratio": 1.0}})
