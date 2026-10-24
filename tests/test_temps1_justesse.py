"""T1J (test de justesse, Jonas 24/10) : ce que ces tests protegent.

Le gel (regles et clarifications inchangees depuis le preenregistrement) ; le calendrier de
parution de DEXJPUS (E) ; la machine a etats du juge (bear au jour du plus haut, bull au jour du
plus bas, etat de depart par le premier franchissement) ; les mesures sur un cas calcule a la main
(rates = 1, fausses alertes, bascules, justesse, periode mesuree B) ; les episodes neutres (C) ; le
hasard reproductible ; la causalite des detecteurs ; la regle de choix (domination, regle 3,
etape B pour tous les retenus, gagnant D, « solide »). Aucune vraie donnee n'est mesuree ici.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from beta.protocole import experiences
from beta.temps1_justesse import campagne as ca
from beta.temps1_justesse import detecteurs as det
from beta.temps1_justesse import donnees as dn
from beta.temps1_justesse import juge as jg
from beta.temps1_justesse import mesures as ms
from beta.temps1_justesse import regles as R
from beta.temps1_justesse import verdict as vd

# ----------------------------------------------------------------------------- gel


def test_les_regles_et_les_clarifications_n_ont_pas_bouge_depuis_le_gel():
    pre = ca.preenregistrement()
    assert pre["famille_compteur"] == "invest"
    assert pre["empreinte"] == R.empreinte()
    assert pre["empreinte_clarifications"] == ca.empreinte_clarifications()


def test_seize_essais_au_verdict_et_dix_huit_informatifs():
    assert len(ca.couples_verdict()) == 16
    c = ca.detail_compteur("empreinte-de-test")
    assert c["essais_verdict"] == 16 and c["informatifs"]["total"] == 18
    pre = ca.preenregistrement()["compteur"]
    assert pre["gel_global_22_10"] == 117
    assert pre["invest_attendu_apres"] == pre["invest_avant"] + 16


def test_le_compteur_attendu_ne_depend_pas_du_nombre_de_lancements():
    deja = experiences.runs_journalises()
    if any(x.get("experience") == R.ID_EXP for x in deja):
        pytest.skip("campagne deja journalisee : l'attendu se lit dans RUNS.jsonl")
    c = ca.detail_compteur("empreinte-de-test")
    assert c["attendu_apres"]["invest"] == c["avant_journalisation"]["invest"] - 1 + 16


# ----------------------------------------------------------------------------- DEXJPUS (E)

def test_dexjpus_utilisable_le_mardi_suivant_mercredi_si_lundi_ferie():
    obs = pd.DatetimeIndex(["2026-10-14", "2026-10-16", "2026-10-07", "2026-01-15",
                            "2026-10-17"])
    u = dn.dates_utilisables(obs)
    assert u[pd.Timestamp("2026-10-14")] == pd.Timestamp("2026-10-20")    # mer. -> mardi suivant
    assert u[pd.Timestamp("2026-10-16")] == pd.Timestamp("2026-10-20")    # vendredi -> mardi
    assert u[pd.Timestamp("2026-10-07")] == pd.Timestamp("2026-10-14")    # Columbus Day lundi 12
    assert u[pd.Timestamp("2026-01-15")] == pd.Timestamp("2026-01-21")    # MLK lundi 19
    assert u[pd.Timestamp("2026-10-17")] == pd.Timestamp("2026-10-20")    # samedi -> sa semaine


# ----------------------------------------------------------------------------- juge

def _cst(n, x):
    return np.full(n, x)


def test_juge_bear_au_jour_du_plus_haut_bull_au_jour_du_plus_bas():
    prix = np.array([100, 105, 110, 99, 85, 90, 80, 100, 120, 115], dtype=float)
    pivots, conf = jg.dater(prix, _cst(10, 0.2), _cst(10, 0.2))
    assert pivots == [(2, jg.PIC), (6, jg.CREUX)]       # 110 -> 85 (-22,7 %) : pic au jour 2
    assert conf == [4, 7]                               # 80 -> 100 (+25 %) : creux au jour 6


def test_juge_etat_de_depart_par_le_premier_franchissement():
    prix = np.array([100, 95, 90, 100, 112, 130, 120, 100, 101], dtype=float)
    pivots, _ = jg.dater(prix, _cst(9, 0.2), _cst(9, 0.2))
    assert pivots[0] == (2, jg.CREUX)                   # hausse de 90 a 112 d'abord
    assert pivots[1] == (5, jg.PIC)                     # puis 130 -> 100 (-23 %)


def test_juge_comparaisons_inclusives():
    prix = np.array([100, 80, 96], dtype=float)         # exactement -20 % puis +20 %
    pivots, _ = jg.dater(prix, _cst(3, 0.2), _cst(3, 0.2))
    assert pivots == [(0, jg.PIC), (1, jg.CREUX)]


def test_sigma_trimestriel_lit_les_deux_annees_d_avant_seulement():
    jours = pd.bdate_range("2010-01-01", "2014-12-31")
    rng = np.random.default_rng(1)
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(jours)))), index=jours)
    debut = jg.premier_trimestre(close)
    assert debut == pd.Timestamp("2012-01-01")         # 01/01/2010 + 2 ans : un debut de trimestre
    s = jg.sigmas_trimestriels(close, debut)
    q = pd.Period("2013Q1")
    r = jg.rendements_log(close)
    attendu = r[(r.index >= "2011-01-01") & (r.index < "2013-01-01")].std(ddof=1) * math.sqrt(252)
    assert s[q] == pytest.approx(attendu)


def test_premier_trimestre_btc_au_01_10_2013():
    close = pd.Series(1.0, index=pd.date_range("2011-08-18", "2014-01-01"))
    assert jg.premier_trimestre(close) == pd.Timestamp("2013-10-01")


# ----------------------------------------------------------------------------- mesures

PRIX = np.array([100, 98, 95, 105, 110, 120, 115, 108, 100, 92, 90, 95, 100, 108, 112, 118, 105,
                 98, 96, 100], dtype=float)
B, U, N = det.BEAR, det.BULL, det.NEUTRE


def _juge(prix=PRIX, pivots=None, sigma=0.01):
    dates = pd.date_range("2020-01-01", periods=len(prix))
    pivots = pivots or [(2, jg.CREUX), (5, jg.PIC), (10, jg.CREUX), (15, jg.PIC), (18, jg.CREUX)]
    n = len(prix)
    return jg.Juge(dates=dates, prix=prix, pivots=pivots, confirmations=[0] * len(pivots),
                   theta_baisse=_cst(n, 0.1), theta_hausse=_cst(n, 0.1),
                   sigma_jour=_cst(n, sigma), debut=0, infos={"debut": "2020-01-01"})


@pytest.fixture
def sans_prechauffe(monkeypatch):
    monkeypatch.setattr(ms.R, "PRECHAUFFE_SEANCES", 0)


def test_mesures_calculees_a_la_main(sans_prechauffe):
    j = _juge()
    sig = pd.Series([U, U, U, B, U, U, U, B, B, B, B, B, U, U, U, U, U, U, U, U], index=j.dates)
    m = ms.mesurer(sig, j, "2020-01-01", "2020-01-20")
    assert m["mesuree"] == ["2020-01-03", "2020-01-19"]                 # [pivot 2, pivot 18[
    assert m["n_bears"] == 2 and m["rates_entree"] == 1
    assert m["entrees"][0]["f_entree"] == pytest.approx((120 - 108) / (120 - 90))
    assert m["entrees"][0]["retard_seances"] == 2 and m["entrees"][0]["retard_jours"] == 2
    assert m["entrees"][1]["rate"] and m["entrees"][1]["f_entree"] == 1.0   # A : rate = 1
    assert m["f_entree_mediane"] == pytest.approx((0.4 + 1.0) / 2)
    assert m["f_entree_pire"] == 1.0
    assert [s["f_sortie"] for s in m["sorties"]] == pytest.approx([0.0, (100 - 90) / (118 - 90)])
    assert m["n_alertes"] == 2 and m["fausses_alertes"] == 1           # le jour 3, seul
    assert m["fausses_alertes_an"] == pytest.approx(1 / (16 / 365.25))
    assert m["bascules"] == 4
    assert m["r_bear"] == pytest.approx(3 / 8) and m["r_bull"] == pytest.approx(5 / 8)
    assert m["justesse"] == pytest.approx(0.5)


def test_un_episode_a_cheval_n_est_pas_mesure(sans_prechauffe):
    j = _juge()
    sig = pd.Series(U, index=j.dates)
    m = ms.mesurer(sig, j, "2020-01-04", "2020-01-20")      # le pivot du 3 est hors periode
    assert m["mesuree"] == ["2020-01-06", "2020-01-19"]
    assert m["n_bears"] == 2 and m["n_bulls"] == 1
    assert {"type": "bull", "debut": "2020-01-03", "fin": "2020-01-06"} in m["a_cheval"]


def test_sortie_ratee_compte_un(sans_prechauffe):
    j = _juge()
    sig = pd.Series([U] * 10 + [B] * 10, index=j.dates)     # jamais de bull apres le creux du 10
    m = ms.mesurer(sig, j, "2020-01-01", "2020-01-20")
    assert m["sorties"][1]["rate"] and m["rates_sortie"] == 1 and m["f_sortie_pire"] == 1.0


def test_prechauffe_insuffisante_arrete(monkeypatch):
    j = _juge()
    with pytest.raises(ms.MesureError, match="prechauffe"):
        ms.mesurer(pd.Series(U, index=j.dates), j, "2020-01-01", "2020-01-20")


def test_episode_neutre_juge_depuis_la_veille():
    prix = np.array([100.0, 110.0, 110.0, 100.0])
    sig = np.array([U, N, U, N])
    e = ms.episodes_neutres(sig, prix, _cst(4, 0.01))
    assert e[0]["n"] == 1 and e[0]["juste"] is False        # C : 100 -> 110, pas toujours juste
    assert e[1]["juste"] is False
    e = ms.episodes_neutres(sig, prix, _cst(4, 0.2))
    assert e[0]["juste"] is True


def test_hasard_reproductible_et_dans_la_periode_mesuree():
    prix = 100 * np.exp(np.cumsum(np.random.default_rng(3).normal(0, 0.01, 500)))
    a = ms.hasard_neutres(prix, _cst(500, 0.01), [3, 5, 8], 50, 400)
    b = ms.hasard_neutres(prix, _cst(500, 0.01), [3, 5, 8], 50, 400)
    assert a == b and 0.0 <= a <= 1.0
    assert ms.hasard_neutres(prix, _cst(500, 0.01), [], 50, 400) is None


# ----------------------------------------------------------------------------- detecteurs

def _donnees_synthetiques(graine: int = 7) -> dn.Donnees:
    rng = np.random.default_rng(graine)
    us = pd.bdate_range("1988-01-01", "1995-12-31")

    def marche(dates, vol, base=100.0):
        return pd.Series(base * np.exp(np.cumsum(rng.normal(0, vol, len(dates)))), index=dates)
    londres = us[us.dayofweek != 0].union(pd.bdate_range("1988-01-01", "1995-12-31")[::7])
    jpy_obs = us[::1]
    prix = {"SPX": marche(us, 0.01), "NDX": marche(us, 0.015), "OR": marche(londres, 0.009),
            "BTC": marche(pd.date_range("1988-01-01", "1995-12-31"), 0.04)}
    vix = pd.Series(np.abs(15 + np.cumsum(rng.normal(0, 1, len(us)))) + 9, index=us)
    jpy = marche(jpy_obs, 0.006, 140.0)
    return dn.Donnees(prix=prix, vix=vix, usdjpy=jpy, usdjpy_utilisable=dn.dates_utilisables(
        jpy.index), seances_us=us, empreinte="test", couverture={})


def test_detecteurs_causaux_publication_dexjpus_comprise():
    d = _donnees_synthetiques()
    for coupure in map(pd.Timestamp, ("1991-03-15", "1993-07-02", "1995-01-10")):
        dt = ca.tronquer(d, coupure)
        for nom in (*R.VERDICT, *R.BANDE, *R.VARIANTES_C1):
            for actif in R.ACTIFS:
                plein = det.signal(d, nom, actif)
                court = det.signal(dt, nom, actif)
                ref = plein[plein.index <= coupure]
                assert court.index.equals(ref.index)
                assert np.array_equal(court.to_numpy(), ref.to_numpy(), equal_nan=True), (
                    nom, actif, coupure)


def test_couche1_lit_dexjpus_a_sa_date_de_publication():
    d = _donnees_synthetiques()
    ind = det.indicateurs_v2(d)
    us = det._sur_seances_us(ind, d)
    # Une observation du mercredi 1992-06-10 n'est lisible qu'a partir du mardi 1992-06-16.
    obs = pd.Timestamp("1992-06-10")
    assert d.usdjpy_utilisable[obs] == pd.Timestamp("1992-06-16")
    y = ind["Y"]
    lu_lundi = us.loc[pd.Timestamp("1992-06-15"), "Y"]
    lu_mardi = us.loc[pd.Timestamp("1992-06-16"), "Y"]
    assert lu_mardi == y[pd.Timestamp("1992-06-12")]       # le vendredi de la meme semaine
    assert lu_lundi == y[pd.Timestamp("1992-06-05")]       # la semaine d'avant


def test_etats_de_la_couche_1_dans_l_ordre():
    ind = pd.DataFrame({"V": [1, 0, 0, 0, np.nan], "Y": [0, 1, 0, 0, 0], "T": [1, 1, 1, 0, 1],
                        "G": [1, 1, 1, 1, 1]}, dtype=float)
    assert list(det.etats(ind).to_numpy()[:4]) == [B, B, N, U]
    assert np.isnan(det.etats(ind).to_numpy()[4])


def test_sma_et_mom_tels_qu_ecrits():
    close = pd.Series([1, 2, 3, 2, 1, 5], dtype=float)
    assert list(det.sma(close, 3).to_numpy()[2:]) == [U, B, B, U]   # 3 vs 2 ; 2 vs 2,33 ; 1 vs 2
    assert list(det.mom(close, 2).to_numpy()[2:]) == [U, U, B, U]


# ----------------------------------------------------------------------------- verdict

def _m(med, fa, pire=None, entrees=None):
    return {"f_entree_mediane": med, "fausses_alertes_an": fa,
            "f_entree_pire": med if pire is None else pire,
            "entrees": entrees or []}


def _ep(*fs, actif=None):
    return [{"pic": f"p{i}", "creux": f"c{i}", "f_entree": f, **({"actif": actif} if actif else {})}
            for i, f in enumerate(fs)]


def test_domination_large_et_stricte():
    assert vd.domine(_m(0.3, 1.0), _m(0.4, 1.0))
    assert vd.domine(_m(0.4, 0.5), _m(0.4, 1.0))
    assert not vd.domine(_m(0.4, 1.0), _m(0.4, 1.0))
    assert not vd.domine(_m(0.3, 2.0), _m(0.4, 1.0))


def test_temoin_moyenne_et_episodes_mis_ensemble():
    spx = {**dict.fromkeys(vd.SCALAIRES), "f_entree_mediane": 0.2, "fausses_alertes_an": 1.0,
           "entrees": _ep(0.1, 0.3)}
    ndx = {**dict.fromkeys(vd.SCALAIRES), "f_entree_mediane": 0.4, "fausses_alertes_an": 3.0,
           "entrees": _ep(0.5)}
    t = vd.temoin(spx, ndx)
    assert t["f_entree_mediane"] == pytest.approx(0.3) and t["fausses_alertes_an"] == 2.0
    assert len(t["entrees"]) == 3 and {e["actif"] for e in t["entrees"]} == {"SPX", "NDX"}


def _tables(c1v1_btc_fa=0.5):
    ref_t = _m(0.5, 1.0, entrees=_ep(0.5, 0.5, 0.5, actif="SPX"))
    ref_o = _m(0.5, 1.0, entrees=_ep(0.5, 0.5, 0.5))
    return {
        "SMA200": {"TEMOIN": ref_t, "OR": ref_o, "BTC": _m(0.5, 1.0)},
        # Meilleur partout : retenu ; au BTC, domine par SMA200 si ses alertes depassent.
        "C1_V1": {"TEMOIN": _m(0.3, 0.8, 0.6, _ep(0.2, 0.4, 0.6, actif="SPX")),
                  "OR": _m(0.3, 0.8, 0.6, _ep(0.2, 0.4, 0.6)),
                  "BTC": _m(0.6, c1v1_btc_fa)},
        # Meilleure mediane mais plus d'alertes : pas domine ; majorite ok ; retenu.
        "MOM126": {"TEMOIN": _m(0.4, 2.0, 0.7, _ep(0.3, 0.4, 0.7, actif="SPX")),
                   "OR": _m(0.4, 2.0, 0.7, _ep(0.3, 0.4, 0.7)), "BTC": _m(0.4, 0.5)},
        # Domine par SMA200 sur l'or : non retenu.
        "C1_V2": {"TEMOIN": _m(0.4, 0.5, 0.5, _ep(0.4, 0.4, 0.6, actif="SPX")),
                  "OR": _m(0.6, 1.5, 0.9, _ep(0.6, 0.6, 0.6)), "BTC": _m(0.1, 0.1)},
    }


def test_regle_3_etape_b_pour_tous_les_retenus_et_gagnant_d():
    v = vd.verdict(_tables())
    assert v["retenus_a"] == ["MOM126", "C1_V1"]
    assert not v["etape_a"]["C1_V2"]["retenu"] and v["etape_a"]["C1_V2"]["OR"]["domine_par_sma200"]
    assert set(v["etape_b"]) == {"MOM126", "C1_V1"}         # D : tous les retenus passent a B
    assert v["retenus"] == ["MOM126", "C1_V1"]
    assert v["gagnant"]["gagnant"] == "C1_V1" and v["statut"] == "candidat retenu : C1_V1"


def test_un_retenu_elimine_au_btc_laisse_l_autre_gagner():
    v = vd.verdict(_tables(c1v1_btc_fa=2.0))                # C1_V1 domine par SMA200 au BTC
    assert v["etape_b"]["C1_V1"]["elimine"] and v["retenus"] == ["MOM126"]
    assert v["gagnant"]["gagnant"] == "MOM126"


def test_aucun_retenu_sma200_retenue():
    t = _tables()
    for x in R.CANDIDATS:
        t[x]["OR"] = _m(0.9, 3.0, entrees=_ep(0.9, 0.9, 0.9))
    v = vd.verdict(t)
    assert v["retenus"] == [] and v["statut"] == vd.SMA200_RETENUE


def test_majorite_stricte_egalite_ne_compte_pas():
    ref = _m(0.5, 1.0, entrees=_ep(0.5, 0.5, 0.5, 0.5))
    x = _m(0.4, 1.0, entrees=_ep(0.4, 0.5, 0.5, 0.3))
    assert vd.majorite(x, ref) == {"plus_faible": 2, "episodes": 4, "majorite": False}


def test_solide_demande_meme_gagnant_et_memes_retenus():
    a = vd.verdict(_tables())
    b = vd.verdict(_tables(c1v1_btc_fa=2.0))
    assert vd.cle_solidite(a) == vd.cle_solidite(vd.verdict(_tables()))
    assert vd.cle_solidite(a) != vd.cle_solidite(b)


# ----------------------------------------------------------------------------- chaine complete

def _donnees_longues(graine: int = 11) -> dn.Donnees:
    rng = np.random.default_rng(graine)
    us = pd.bdate_range("1985-01-01", "2026-10-23")

    def marche(dates, vol, base=100.0):
        return pd.Series(base * np.exp(np.cumsum(rng.normal(0.0002, vol, len(dates)))),
                         index=dates)
    prix = {"SPX": marche(us, 0.011), "NDX": marche(us, 0.016),
            "OR": marche(us[us.dayofweek != 4].union(us[::10]), 0.01),
            "BTC": marche(pd.date_range("2011-08-18", "2026-10-23"), 0.04, 10.0)}
    vix = pd.Series(np.clip(18 + np.cumsum(rng.normal(0, 0.8, len(us))) % 30, 9, 80), index=us)
    jpy = marche(us, 0.006, 140.0)
    return dn.Donnees(prix=prix, vix=vix, usdjpy=jpy, usdjpy_utilisable=dn.dates_utilisables(
        jpy.index), seances_us=us, empreinte="synthetique", couverture={
            k: {"serie": k, "debut": "x", "fin": "y", "n": 1, "trous_plus_de_5_seances": 0,
                "trous_exemples": []} for k in ("SPX", "NDX", "OR", "BTC", "VIX", "USDJPY")})


def test_chaine_complete_jusqu_au_rapport(tmp_path, monkeypatch):
    import json

    from beta.temps1_justesse import rapport

    d = _donnees_longues()
    res = ca.calculer(d)
    c = ca.detail_compteur(d.empreinte)
    s = ca._propre({"experience": R.ID_EXP, "code": "test", "regles": R.empreinte(),
                    "clarifications": "test", "calcule_le": "2026-10-24T00:00:00+00:00",
                    "donnees": {"empreinte": d.empreinte, "couverture": d.couverture,
                                "dexjpus_publication": "test"},
                    "compteur": {**c, "apres_journalisation": c["attendu_apres"],
                                 "preenregistrement": ca.preenregistrement()["compteur"]},
                    "causalite": {"coupures": [], "echecs": []}, "resultats": res})
    s = json.loads(json.dumps(s))                       # ce que lit --rapport
    md = rapport.markdown(s)
    for titre in ("## 1. Compteur", "## 4. Tableau principal", "## 8. Étape B", "## 11. Verdict",
                  "## 12. Écarts"):
        assert titre in md
    assert "Verdict" in rapport.resume(s)
    monkeypatch.setattr(ca, "SORTIE", tmp_path)
    rapport.csvs(s)
    assert (tmp_path / "RAPPORT_JUSTESSE.csv").read_text(encoding="utf-8").count("\n") > 10
