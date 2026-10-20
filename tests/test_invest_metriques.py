"""Test invest — metriques standard (A4) et de survie (B1-B4), sur des cas faits a la main."""

import math

import numpy as np
import pandas as pd
import pytest

from beta.invest import metriques as me
from beta.invest.moteur import Mapping

SOCLE = Mapping("socle")


# --------------------------------------------------------------------------- A4

def test_courbe_et_drawdown_partent_de_v0_egal_1():
    v = me.courbe(np.array([0.1, -0.5, 0.2]))
    assert v.tolist() == pytest.approx([1.0, 1.1, 0.55, 0.66])
    assert me.drawdown(v).tolist() == pytest.approx([0.0, 0.0, -0.5, -0.4])


def test_une_perte_des_le_premier_jour_est_un_drawdown():
    assert me.drawdown(me.courbe(np.array([-0.1]))).tolist() == pytest.approx([0.0, -0.1])


def test_metriques_standard_a_la_main():
    r = np.array([0.1, -0.5, 0.2])
    m = me.standard(r, e=np.array([1.0, 0.25, 0.25]))
    assert m["n_jours"] == 3
    assert m["rendement_total"] == pytest.approx(-0.34)
    assert m["cagr"] == pytest.approx(0.66 ** (365 / 3) - 1)
    assert m["vol"] == pytest.approx(np.std(r, ddof=1) * math.sqrt(365))
    assert m["sharpe"] == pytest.approx(np.mean(r) / np.std(r, ddof=1) * math.sqrt(365))
    assert m["mdd"] == pytest.approx(-0.5)
    assert m["duree_sous_eau_max_j"] == 2
    assert m["ulcer"] == pytest.approx(math.sqrt((0.0 + 0.25 + 0.16) / 3))
    assert m["calmar"] == pytest.approx(m["cagr"] / 0.5)
    assert m["expo_moyenne"] == pytest.approx(0.5)
    assert m["changements_expo"] == 1
    assert m["dsr"] is None                                     # sans compteur, pas de DSR


def test_cagr_sur_365_jours_et_sharpe_net_du_taux_sans_risque():
    r = np.full(365, 0.001)
    r[::2] += 0.0005
    m = me.standard(r, rf=np.full(365, 0.0002), n_essais=100)
    assert m["cagr"] == pytest.approx(np.prod(1 + r) - 1)
    assert m["sharpe"] == pytest.approx(np.mean(r - 0.0002) / np.std(r, ddof=1) * math.sqrt(365))
    assert 0.0 <= m["dsr"] <= 1.0 and m["n_essais"] == 100


def test_calmar_indefini_sans_drawdown():
    m = me.standard(np.array([0.01, 0.02]))
    assert m["mdd"] == 0.0 and m["calmar"] is None and m["duree_sous_eau_max_j"] == 0


# --------------------------------------------------------------------------- B1

def test_episodes_pic_creux_fin_et_episode_non_rattrape():
    v = np.array([1.0, 1.2, 0.9, 0.95, 1.25, 1.3, 1.0, 0.98, 1.1, 1.4, 1.05])
    eps = me.episodes(v, 0.20)
    assert [(e["pic"], e["creux"], e["fin"]) for e in eps] == [(1, 2, 4), (5, 7, 9), (9, 10, None)]
    assert [e["perte"] for e in eps] == pytest.approx([0.9 / 1.2 - 1, 0.98 / 1.3 - 1, -0.25])


def test_une_baisse_sous_le_seuil_n_est_pas_un_episode():
    assert me.episodes(np.array([1.0, 1.1, 0.95, 1.2]), 0.20) == []


def test_le_pic_est_le_dernier_plus_haut_avant_le_passage_sous_le_seuil():
    eps = me.episodes(np.array([1.0, 1.2, 1.1, 1.2, 0.9, 1.3]), 0.20)
    assert [(e["pic"], e["creux"], e["fin"]) for e in eps] == [(3, 4, 5)]


# ------------------------------------------------------------------------ B2-B4

V_B = np.array([1.0, 1.0, 0.9, 0.8, 0.7, 0.75, 0.9, 1.05])
E = np.array([1.0, 1.0, 0.25, 0.25, 0.25, 1.0, 1.0])            # decidee a chaque V-index


def _survie(v_b=V_B, e=E, horizon_j=3):
    r_b = v_b[1:] / v_b[:-1] - 1
    v_s = me.courbe(e * r_b)
    return me.survie(v_b, v_s, e, me.episodes(v_b, 0.20), SOCLE, theta_f=0.10,
                     horizon_j=horizon_j)


def test_protection_d_un_episode_construit_a_la_main():
    s = _survie()
    ep = s["episodes"][0]
    v_s = me.courbe(E * (V_B[1:] / V_B[:-1] - 1))
    assert (ep["pic"], ep["creux"], ep["fin"]) == (1, 4, 7)
    assert ep["perte_b"] == pytest.approx(-0.3)
    assert ep["perte_s"] == pytest.approx(v_s[4] / v_s[1] - 1)
    assert ep["protection"] == pytest.approx(1 - (v_s[4] / v_s[1] - 1) / -0.3)
    assert s["protection"] == pytest.approx(ep["protection"])


def test_protection_agregee_ponderee_par_la_gravite():
    eps = [{"perte_b": -0.5, "protection": 0.8}, {"perte_b": -0.2, "protection": -0.1}]
    assert me.protection_agregee(eps) == pytest.approx((0.5 * 0.8 + 0.2 * -0.1) / 0.7)
    assert me.protection_agregee([]) is None


def test_retard_et_part_de_la_baisse_deja_subie():
    ep = _survie()["episodes"][0]
    assert ep["retard_j"] == 1                                  # defensif a la cloture 2
    assert ep["part_subie"] == pytest.approx((1.0 - 0.9) / (1.0 - 0.7))


def test_retour_tardif_rebond_rate_depuis_le_creux():
    ep = _survie()["episodes"][0]
    assert ep["retour_j"] == 1 and ep["rebond_rate"] == pytest.approx(0.75 / 0.7 - 1)


def test_sans_reaction_pas_de_retard_ni_de_rebond_rate():
    ep = _survie(e=np.ones(7))["episodes"][0]
    assert ep["retard_j"] is None and ep["part_subie"] is None
    assert ep["rebond_rate"] == 0.0 and ep["retour"] == "pas defensif au creux"
    assert ep["protection"] == pytest.approx(0.0)


def test_un_vrai_signal_n_est_pas_compte_faux():
    f = _survie()["faux_signaux"]
    assert (f["n_passages"], f["n_evalues"], f["n_faux"]) == (1, 1, 0)
    assert f["cout_cumule"] == 0.0


def test_faux_signal_et_son_cout():
    v_b = np.array([1.0, 1.0, 1.02, 1.05, 1.03, 1.08, 1.1])
    e = np.array([1.0, 0.25, 0.25, 1.0, 1.0, 1.0])
    f = _survie(v_b=v_b, e=e)["faux_signaux"]
    assert (f["n_passages"], f["n_evalues"], f["n_faux"]) == (1, 1, 1)
    assert f["cout_cumule"] == pytest.approx(0.75 * (1.05 / 1.0 - 1))


def test_faux_signal_non_evaluable_pres_de_la_fin():
    v_b = np.array([1.0, 1.0, 1.02, 1.05, 1.03, 1.08, 1.1])
    e = np.array([1.0, 0.25, 0.25, 1.0, 1.0, 1.0])
    f = _survie(v_b=v_b, e=e, horizon_j=10)["faux_signaux"]
    assert (f["n_passages"], f["n_evalues"], f["n_non_evaluables"], f["n_faux"]) == (1, 0, 1, 0)


def test_sans_episode_la_protection_est_indefinie():
    v_b = np.array([1.0, 1.05, 1.1])
    s = me.survie(v_b, v_b, np.ones(2), [], SOCLE, theta_f=0.1, horizon_j=60)
    assert s["episodes"] == [] and s["protection"] is None


# ------------------------------------------------------------------------- captures

def test_captures_sur_semaines_civiles_completes():
    jours = pd.date_range(pd.Timestamp("2026-01-07", tz="UTC"), periods=19, freq="D")  # mercredi
    r_b = np.zeros(19)
    r_b[5:12] = 0.01            # semaine du lundi 12/01 : hausse
    r_b[12:19] = -0.01          # semaine du lundi 19/01 : baisse
    r_s = np.where(r_b > 0, 0.5 * r_b, 0.25 * r_b)
    c = me.captures(r_s, r_b, jours)
    assert c["n_semaines"] == 2                       # 07-11/01 incomplete : ecartee
    assert c["haussiere"] == pytest.approx((1.005 ** 7 - 1) / (1.01 ** 7 - 1))
    assert c["baissiere"] == pytest.approx((0.9975 ** 7 - 1) / (0.99 ** 7 - 1))


# ------------------------------------------------------------- version rapide des nulls

def test_les_metriques_des_nulls_egalent_les_metriques_completes():
    rng = np.random.default_rng(3)                    # 9 episodes, dont un non rattrape
    r_b = rng.normal(0.002, 0.04, 800)
    v_b = me.courbe(r_b)
    eps = me.episodes(v_b, 0.20)
    assert len(eps) >= 2
    e = np.where(rng.random(800) < 0.3, 0.25, 1.0)
    r = e * r_b
    rapide = me.pour_nulls(r, v_b, eps)
    complet = me.standard(r)
    s = me.survie(v_b, me.courbe(r), e, eps, SOCLE, theta_f=0.1, horizon_j=60)
    assert rapide["ulcer"] == pytest.approx(complet["ulcer"])
    assert rapide["mdd_abs"] == pytest.approx(-complet["mdd"])
    assert rapide["calmar"] == pytest.approx(complet["calmar"])
    assert rapide["prot"] == pytest.approx(s["protection"])


def test_metriques_des_nulls_sans_episode_ni_drawdown():
    rapide = me.pour_nulls(np.array([0.01, 0.02]), me.courbe(np.array([0.01, 0.02])), [])
    assert rapide["prot"] is None and rapide["calmar"] == math.inf and rapide["mdd_abs"] == 0.0
