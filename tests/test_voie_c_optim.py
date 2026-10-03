"""Optimisation de la gestion de la voie C : le moteur a bande reproduit celui de la mesure."""

import numpy as np
import pandas as pd

from beta.strategies import voie_c_optim as vo
from beta.strategies import voie_c_voltarget as vc


def _jeu(n=120, k=4, graine=0):
    rng = np.random.default_rng(graine)
    index = pd.date_range("2022-01-01", periods=n, freq="D", tz="UTC")
    rend = pd.DataFrame(rng.normal(0, 0.03, (n, k)), index=index)
    fund = pd.DataFrame(rng.normal(0, 3e-4, (n, k)), index=index)
    cible = pd.DataFrame(rng.normal(0, 0.4, (n, k)), index=index)
    cible.iloc[:5] = np.nan
    return cible, rend, fund


def test_bande_nulle_reproduit_le_moteur_de_mesure():
    cible, rend, fund = _jeu()
    for pas in (1, 3, 7):
        attendu = vc.derouler(cible, rend, fund, pas, 5.0)["r_net"].to_numpy()
        r_net, _ = vo.derouler_bande(cible.to_numpy(), rend.to_numpy(), fund.to_numpy(),
                                     pas, 0.0, 5.0)
        np.testing.assert_allclose(r_net, attendu, atol=1e-15)


def test_bande_reduit_les_frais_sans_changer_le_brut_quand_rien_ne_trade():
    cible, rend, fund = _jeu(graine=1)
    fund[:] = 0.0
    net0, brut0 = vo.derouler_bande(cible.to_numpy(), rend.to_numpy(), fund.to_numpy(),
                                    1, 0.0, 5.0)
    net_inf, brut_inf = vo.derouler_bande(cible.to_numpy(), rend.to_numpy(),
                                          fund.to_numpy(), 1, 1e9, 5.0)
    # Bande infinie : on entre une fois, puis on ne trade plus jamais.
    assert (brut_inf - net_inf)[6:].max() == 0.0
    assert (brut0 - net0).sum() > (brut_inf - net_inf).sum()


def test_la_grille_ne_charge_rien_apres_le_scelle():
    closes, rendements, funding_j = vo.donnees()
    assert closes.index.max() <= vo.FIN_VUE
    assert funding_j.index.max() <= vo.FIN_VUE


def test_hysteresis_ne_bouge_que_au_dela_du_seuil():
    from beta.strategies import voie_c_verif as vv
    lev = pd.Series([np.nan, 1.0, 1.2, 1.3, 1.0, 1.6, 1.5])
    out = vv.hysteresis(lev, 0.25).tolist()
    assert np.isnan(out[0])
    assert out[1:] == [1.0, 1.0, 1.3, 1.0, 1.6, 1.6]   # 1,3 -> 1,0 : ecart 0,3 > 0,25


def test_hysteresis_est_causale():
    from beta.strategies import voie_c_verif as vv
    rng = np.random.default_rng(3)
    lev = pd.Series(rng.uniform(0.25, 3.0, 300))
    complet = vv.hysteresis(lev, 0.25)
    pd.testing.assert_series_equal(vv.hysteresis(lev[:200], 0.25), complet[:200])


def test_chaine_complete_causale_sur_le_lake():
    from beta.strategies import voie_c_verif as vv
    closes, _, funding_j = vo.donnees()
    assert all(e < 1e-12 for _, e in vv.epreuve_causalite(closes, funding_j))
