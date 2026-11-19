"""Tests du moteur MOMENTUM30_BTC_GARDE, sur donnees synthetiques seulement."""
from __future__ import annotations

import numpy as np

from beta.momentum30_btc import moteur as base
from beta.momentum30_btc_garde import moteur


def test_sans_declenchement_identique_a_momentum30():
    # seuil inatteignable : la garde ne coupe jamais, on retrouve MOMENTUM30_BTC
    rng = np.random.default_rng(3)
    close = 100 * np.cumprod(1 + rng.normal(0.001, 0.02, 500))
    e, g = moteur.exposition(close, 30, seuil=10.0)
    assert np.array_equal(e, base.exposition(close, 30), equal_nan=True)
    assert np.nansum(g) == 0


def test_causalite_prefixe():
    rng = np.random.default_rng(4)
    close = 100 * np.cumprod(1 + rng.normal(0, 0.04, 600))
    e, g = moteur.exposition(close)
    for t in (80, 300, 599):
        a, b = moteur.exposition(close[:t])
        assert np.array_equal(a, e[:t], equal_nan=True)
        assert np.array_equal(b, g[:t], equal_nan=True)


def test_garde_coupe_puis_attend_un_signal_neuf():
    # 31 jours de hausse (signal 1), chute de 25 % sans que le momentum 30 j passe negatif,
    # puis reprise : la garde coupe et ne rentre pas tant que le signal ne repasse pas a 0.
    hausse = list(np.linspace(100, 200, 40))
    chute = [190, 170, 150]                    # 150 / 200 - 1 = -25 % ; 150 > close(t-30)
    reprise = [160, 170, 180, 190, 200]
    close = np.array(hausse + chute + reprise, dtype=float)
    e, g = moteur.exposition(close, 30, 0.20)
    i_150 = len(hausse) + 2                     # cloture a 150 : garde declenchee
    assert e[i_150] == 1.0                      # le jour de la chute, on etait encore dedans
    assert (e[i_150 + 1:] == 0.0).all()         # ensuite dehors, malgre la reprise
    assert (g[i_150 + 1:] == 1.0).all()         # et c'est bien la garde qui coupe
    # avant la chute, exposition pleine
    assert (e[31:len(hausse) + 1] == 1.0).all()


def test_verdict_cinq_conditions():
    tout = {k: True for k in ("a", "b", "c", "d", "e")}
    assert moteur.verdict(tout, 0.01) == moteur.CONFIRMEE
    assert moteur.verdict(tout, 0.10) == moteur.INDECIDABLE
    assert moteur.verdict(tout, 0.30) == moteur.INFIRMEE
    assert moteur.verdict({**tout, "e": False}, 0.01) == moteur.INFIRMEE
