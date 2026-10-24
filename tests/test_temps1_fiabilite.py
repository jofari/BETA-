"""T1F (fiabilite du test de justesse, Jonas 24/10) : ce que ces tests protegent.

Le gel (regles, texte du preenregistrement, marque diagnostic) ; les modules de T1J identiques
au commit 8afdbe7 ; la permutation par etat qui conserve parts, bascules et durees
(clarification 1) ; le decalage dans [90, N - 90] (clarification 4) ; les p (<= et >=, egalites
comprises) et le temoin tirage par tirage (clarification 3) ; les trois cas du test 2 et la
f_entree diagnostic ; la regle de verdict. Aucun tirage n'est fait sur les vraies donnees ici.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from beta.protocole import experiences
from beta.temps1_fiabilite import campagne as ca
from beta.temps1_fiabilite import nulls
from beta.temps1_fiabilite import regles as R
from beta.temps1_justesse import detecteurs as det
from beta.temps1_justesse import juge as jg

B, U, N = det.BEAR, det.BULL, det.NEUTRE


def test_t1f_est_un_diagnostic_gele_qui_ne_compte_pas():
    pre = ca.verifier_gel()
    assert pre["diagnostic"] is True and pre["famille_compteur"] == "invest"
    assert pre["empreinte"] == R.empreinte()
    assert pre["empreinte_preenregistrement"] == ca.empreinte_texte()
    d = experiences.detail_compteur(famille="invest")
    assert R.ID_EXP not in {x.get("experience") for x in experiences.runs_journalises()}
    assert d["total"] == d["dette"] + d["mesures"] + d["en_attente"]


def test_les_modules_de_t1j_sont_ceux_du_commit_8afdbe7():
    assert ca.verifier_modules() == []


def _bascules(s):
    return int(np.sum(s[1:] != s[:-1]))


def test_permutation_par_etat_conserve_parts_bascules_et_durees():
    seg = np.array([U] * 30 + [N] * 4 + [B] * 7 + [U] * 12 + [B] * 2 + [N] * 9 + [U] * 50
                   + [B] * 20 + [U] * 3)
    rng = np.random.default_rng(0)
    vus = set()
    for _ in range(200):
        p = nulls.permuter_par_etat(seg, rng)
        assert len(p) == len(seg)
        for etat in (B, U, N):
            assert np.sum(p == etat) == np.sum(seg == etat)
        assert _bascules(p) == _bascules(seg)
        e0, d0 = nulls.episodes(seg)
        e1, d1 = nulls.episodes(p)
        assert np.array_equal(e0, e1)                                  # meme suite d'etats
        for etat in (B, U, N):
            assert sorted(d0[e0 == etat]) == sorted(d1[e1 == etat])    # memes durees
        vus.add(p.tobytes())
    assert len(vus) > 10                                                # les positions bougent


def test_permutation_reproductible_avec_la_graine():
    seg = np.array([U] * 10 + [B] * 3 + [U] * 7 + [B] * 9 + [U] * 4)
    a = nulls.permuter_par_etat(seg, np.random.default_rng(0))
    b = nulls.permuter_par_etat(seg, np.random.default_rng(0))
    assert np.array_equal(a, b)


def test_decalage_entre_90_et_n_moins_90():
    seg = np.arange(300, dtype=float)
    rng = np.random.default_rng(0)
    for _ in range(500):
        k = int(np.argmax(nulls.decaler(seg, rng) == 0))
        assert 90 <= k <= 210
    with pytest.raises(ValueError):
        nulls.decaler(np.zeros(179), rng)


def test_p_inclut_les_egalites_et_le_temoin_se_calcule_tirage_par_tirage():
    obs = {"f_entree_mediane": 0.3, "justesse": 0.7, "fausses_alertes_an": 2.0}
    nul = {"f_entree_mediane": [0.2, 0.3, 0.5, 0.6], "justesse": [0.7, 0.8, 0.5, 0.6],
           "fausses_alertes_an": [1, 2, 3, 4]}
    r = ca.resumer(obs, nul)
    assert r["p_latence"] == 0.5 and r["p_justesse"] == 0.5
    assert r["lecture_latence"] == "hasard"
    o, n = ca.temoin({"SPX": obs, "NDX": {**obs, "f_entree_mediane": 0.5}},
                     {"SPX": nul, "NDX": {**nul, "f_entree_mediane": [0.4, 0.1, 0.5, 0.0]}})
    assert o["f_entree_mediane"] == pytest.approx(0.4)
    assert n["f_entree_mediane"] == pytest.approx([0.3, 0.2, 0.5, 0.3])   # tirage k avec k


def _juge(prix, pivots):
    dates = pd.date_range("2020-01-01", periods=len(prix))
    n = len(prix)
    return jg.Juge(dates=dates, prix=np.asarray(prix, dtype=float), pivots=pivots,
                   confirmations=[0] * len(pivots), theta_baisse=np.full(n, 0.1),
                   theta_hausse=np.full(n, 0.1), sigma_jour=np.full(n, 0.01), debut=0,
                   infos={"debut": "2020-01-01"})


def test_trois_cas_au_pic_et_f_diagnostic():
    prix = [100.0] * 40 + [120.0] + list(np.linspace(118, 90, 20)) + [95.0] * 5
    j = _juge(prix, [(40, jg.PIC), (60, jg.CREUX)])
    pic, creux = f"{j.dates[40]:%Y-%m-%d}", f"{j.dates[60]:%Y-%m-%d}"
    obs = {"entrees": [{"pic": pic, "creux": creux, "f_entree": 0.0}]}
    # bear depuis 30 seances avant le pic, jusqu'au jour 45 ; nouvelle bascule au jour 50
    s = [U] * 10 + [B] * 36 + [U] * 4 + [B] * 16
    e = ca.diagnostic_f0(pd.Series(s, index=j.dates), j, obs)[0]
    assert e["cas"] == "en bear avant le pic" and e["seances_avant"] == 30
    assert e["f_diagnostic"] == pytest.approx((120 - prix[50]) / (120 - prix[60]))
    s = [U] * 40 + [B] * 26
    e = ca.diagnostic_f0(pd.Series(s, index=j.dates), j, obs)[0]
    assert e["cas"] == "bascule le jour du pic" and e["f_diagnostic"] == 0.0
    s = [U] * 30 + [B] * 15 + [U] * 21                                    # 10 s. avant : garde
    e = ca.diagnostic_f0(pd.Series(s, index=j.dates), j, obs)[0]
    assert e["cas"] == "en bear avant le pic" and e["f_diagnostic"] == 0.0
    s = [U] * 66
    e = ca.diagnostic_f0(pd.Series(s, index=j.dates), j, obs)[0]
    assert e["cas"] == "pas en bear au pic" and e["rate_diagnostic"] and e["f_diagnostic"] == 1.0


def test_verdict_fiable_non_concluant_agitation():
    def t(pt, po):
        return {x: {"TEMOIN": {"p_latence": pt}, "OR": {"p_latence": po},
                    "BTC": {"p_latence": 0.5, "lecture_latence": "hasard"}} for x in R.CANDIDATS}
    assert ca.verdict(t(0.01, 0.049))["C1_V1"]["verdict"] == "fiable"
    assert ca.verdict(t(0.05, 0.01))["C1_V1"]["verdict"] == "non concluant"
    assert ca.verdict(t(0.199, 0.10))["C1_V2"]["verdict"] == "non concluant"
    assert ca.verdict(t(0.01, 0.20))["C1_V2"]["verdict"] == "du a l'agitation"


def test_donnees_de_t1j_reconstituees_a_l_identique():
    if not ca.JSON_T1J.exists():
        pytest.skip("mesure de T1J absente de data/ (jetable)")
    d = ca.donnees_t1j(ca.synthese_t1j())
    assert d.empreinte == R.EMPREINTE_DONNEES_T1J


def test_le_rapport_s_ecrit_sur_une_synthese_fabriquee(tmp_path, monkeypatch):
    from beta.temps1_fiabilite import rapport

    rng = np.random.default_rng(1)
    obs = {"f_entree_mediane": 0.2, "justesse": 0.7, "fausses_alertes_an": 2.0}

    def nul():
        return {k: list(rng.uniform(0, 1, 50)) for k in ("f_entree_mediane", "justesse",
                                                          "fausses_alertes_an")}
    tests = {t: {d: {a: ca.resumer(obs, nul()) for a in (*R.ACTIFS, "TEMOIN")}
                 for d in R.DETECTEURS} for t in ("test_1", "test_1_bis")}
    ep = [{"pic": "2020-01-01", "creux": "2020-02-01", "cas": "en bear avant le pic",
           "seances_avant": 4, "f_entree": 0.0, "f_diagnostic": 0.3, "rate_diagnostic": False}]
    s = {"calcule_le": "2026-10-24T00:00:00+00:00", "code": "x", "modules_t1j":
         {"commit": R.COMMIT_JUSTESSE, "identiques": True}, "donnees": "d", "regles_t1j": "r",
         "preenregistrement": "p", "regles": "g",
         "compteur": {"avant": {"global": 1, "invest": 1, "trading": 0},
                      "apres": {"global": 1, "invest": 1, "trading": 0}},
         "plages": {a: {"debut": "a", "fin": "b", "seances": 1} for a in R.ACTIFS},
         "tests": tests, "verdict": ca.verdict(tests["test_1"]),
         "test_2": {d: {a: {"episodes": ep, "resume": ca.resume_f0(ep)} for a in R.ACTIFS}
                    for d in R.DETECTEURS}}
    md = rapport.markdown(s)
    for titre in ("## 1. Empreintes", "## 2. Test 1", "## 3. Test 1 bis", "## 4. Test 2",
                  "## 5. Verdict", "## 6. Écarts"):
        assert titre in md
    monkeypatch.setattr(ca, "SORTIE", tmp_path)
    rapport.ecrire(s)
    assert (tmp_path / "RAPPORT_FIABILITE_tests.csv").exists()
    assert "Fiabilité" in (tmp_path / "RESUME_DISCORD.md").read_text(encoding="utf-8")
