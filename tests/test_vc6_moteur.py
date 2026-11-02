"""Moteur VC6 V1 (Temps 2) : mecanique sur donnees synthetiques, sans source vivante."""

import math

import numpy as np
import pandas as pd
import pytest

from beta.vc6 import moteur as mt
from beta.vc6 import regles as R


def _ent(baissier, n=None, sigma=0.5, funding=0.0, r=0.0, poches=("BTC",)):
    n = len(baissier) if n is None else n
    jours = pd.date_range("2030-01-01", periods=n, freq="D")
    actifs = set(poches) | {"BTC"}
    return mt.Entrees(
        jours=jours, baissier=np.asarray(baissier, dtype=bool),
        sigma={a: np.full(n, sigma) for a in poches},
        funding_annuel={a: np.full(n, funding * 365) for a in poches},
        funding_jour={a: np.full(n, funding) for a in poches},
        rendements={a: np.full(n, r) for a in actifs})


def test_rampe_lineaire_vers_le_baissier():
    ent = _ent([False, True, True, True, True, True, True, True])
    sim = mt.simuler(ent, mt.Parametres(poids={"BTC": 1.0}, sizing="fixe", frais_pb=0.0))
    poche, baisse = sim["y"][:, 0], sim["y"][:, 1]
    assert poche.tolist() == pytest.approx([1.0, 0.8, 0.6, 0.4, 0.2, 0.0, 0.0])
    assert baisse.tolist() == pytest.approx([0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.25])
    assert sim["en_rampe"].tolist() == [False, True, True, True, True, True, False]


def test_frais_sur_la_position_nette():
    ent = _ent([False, True, True])
    sim = mt.simuler(ent, mt.Parametres(poids={"BTC": 1.0}, sizing="fixe", rampe=1))
    # 1 BTC -> 0,25 BTC (poche baissiere) : on vend 0,75, pas 1 + 0,25
    assert sim["frais"][1] == pytest.approx(0.75 * 1e-3)


def test_bande_de_10_pc():
    ent = _ent([False] * 4)
    ent.sigma["BTC"] = np.array([0.5, 0.48, 0.40, 0.40])   # cible 0,5 ; 0,52 ; 0,625
    sim = mt.simuler(ent, mt.Parametres(poids={"BTC": 1.0}, baissiere={}))
    assert sim["e"][:, 0].tolist() == pytest.approx([0.5, 0.5, 0.625])


def test_plafond_funding_et_clip():
    ent = _ent([False, False], sigma=0.05, funding=0.0002)  # 0,0002 x 365 = 7,3 % < 20 %
    sim = mt.simuler(ent, mt.Parametres(poids={"BTC": 1.0}, baissiere={}))
    assert sim["e"][0, 0] == pytest.approx(2.0)
    ent = _ent([False, False], sigma=0.05, funding=0.001)    # 36,5 % > 20 %
    sim = mt.simuler(ent, mt.Parametres(poids={"BTC": 1.0}, baissiere={}))
    assert sim["e"][0, 0] == pytest.approx(1.0)


def test_securite_de_liquidation():
    sigma = 5.0
    e, contraint = mt.cible_poche(sigma, 0.0, mt.Parametres(sizing="fixe", e_fixe=2.0))
    assert contraint
    assert e == pytest.approx(1 / (R.MARGE + 3 * sigma / math.sqrt(365)))
    assert not mt.cible_poche(0.5, 0.0, mt.Parametres(sizing="fixe", e_fixe=2.0))[1]


def test_financement_seulement_sur_l_exces():
    ent = _ent([False, False, False], sigma=0.1, funding=0.0003)
    sim = mt.simuler(ent, mt.Parametres(poids={"BTC": 1.0}, baissiere={}))
    assert sim["financement"].tolist() == pytest.approx([0.0003, 0.0003])


def test_alignement_decision_veille():
    ent = _ent([False, True, False], r=0.0)
    ent.rendements["BTC"] = np.array([np.nan, 0.10, -0.10])
    p = mt.Parametres(poids={"BTC": 1.0}, baissiere={}, rampe=1, sizing="fixe", frais_pb=0.0)
    sim = mt.simuler(ent, p)
    assert sim["r"].tolist() == pytest.approx([0.10, 0.0])     # decision de D0 sur le jour 1
    anticipe = mt.simuler(ent, mt.Parametres(**{**p.__dict__, "anticipation": True}))
    assert anticipe["r"].tolist() == pytest.approx([0.0, -0.10])


def test_temoin_constant():
    ent = _ent([False, False, False], r=0.01, poches=("BTC", "ETH", "SOL"))
    t = mt.temoin(ent, R.POIDS, 0.6)
    assert t["r"].tolist() == pytest.approx([0.006, 0.006])
