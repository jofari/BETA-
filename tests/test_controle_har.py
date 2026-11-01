"""Controle HAR (VC6 V1, phase 2, Jonas 01/11/2026) : ce que ces tests protegent.

Le gel (regles, texte du preenregistrement, marque diagnostic) ; la lecture des copies figees
(SHA-256, coupe a la date de fin, cloture 1d = barre 5 min de 23:55) ; la RV journaliere (somme des
carres, jamais a travers un trou, jour exclu au-dela de 10 % de barres manquantes) ; l'ecart-type
30 jours (ddof 1) ; le HAR (constante, lignes entierement dans la fenetre des 730 jours de RV) ;
les replis ; la QLIKE ; la regle 5 stricte ; Diebold-Mariano ; l'arret sur un cas non prevu ;
l'epreuve de causalite ; le rapport et l'addendum. Aucun calcul sur les vraies donnees ici : series
synthetiques seulement.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np
import pandas as pd
import pytest

from beta.controle_har import campagne as ca
from beta.controle_har import donnees as dn
from beta.controle_har import har as hr
from beta.controle_har import regles as R
from beta.protocole import experiences


def _barres(jours: int = 800, debut: str = "2019-01-01", graine: int = 0) -> pd.DataFrame:
    """Barres 5 min synthetiques a volatilite journaliere persistante (log-AR(1))."""
    rng = np.random.default_rng(graine)
    lv = np.zeros(jours)
    for d in range(1, jours):
        lv[d] = 0.97 * lv[d - 1] + rng.normal(0, 0.15)
    sigma = np.repeat(0.03 * np.exp(lv) / math.sqrt(R.BARRES_PAR_JOUR), R.BARRES_PAR_JOUR)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 1, jours * R.BARRES_PAR_JOUR) * sigma))
    idx = pd.date_range(debut, periods=len(close), freq="5min", tz="UTC")
    return pd.DataFrame({"close": close, "volume": 1.0}, index=idx)


def _cloture_1d(barres: pd.DataFrame) -> pd.Series:
    return barres["close"].groupby(barres.index.tz_convert(None).normalize()).last()


def test_le_controle_har_est_un_test_de_mesure_gele_qui_ne_compte_pas():
    pre = ca.verifier_gel()
    assert pre["diagnostic"] is True and pre["famille_compteur"] == "invest"
    assert pre["empreinte"] == R.empreinte() == "f7be9a3d4d2c0023"
    assert pre["empreinte_preenregistrement"] == ca.empreinte_texte()
    assert "n_configurations" not in pre
    assert R.ID_EXP not in {x.get("experience") for x in experiences.runs_journalises()}


def test_la_rv_est_la_somme_des_carres_sans_traverser_un_trou():
    b = _barres(4, debut="2024-01-01", graine=1)
    garde = np.ones(len(b), dtype=bool)
    garde[288 + 100:288 + 128] = False          # 28 barres manquantes le 02/01 : jour garde
    garde[576 + 50:576 + 79] = False            # 29 barres manquantes le 03/01 : jour exclu
    bt = b[garde]
    rvj = hr.rv_journaliere(bt)
    attendu: dict = {}
    t, c = bt.index, bt["close"].to_numpy()
    for i in range(1, len(bt)):
        if t[i] - t[i - 1] == pd.Timedelta(minutes=5):
            jour = t[i].tz_convert(None).normalize()
            attendu[jour] = attendu.get(jour, 0.0) + math.log(c[i] / c[i - 1]) ** 2
    assert list(rvj["manquantes"]) == [0, 28, 29, 0]
    assert list(rvj["exclu"]) == [False, False, True, False]
    assert list(rvj["rendements"]) == [287, 259, 258, 288]      # 1re barre ; apres chaque trou
    for jour in ("2024-01-01", "2024-01-02", "2024-01-04"):
        assert rvj.at[pd.Timestamp(jour), "rv"] == pytest.approx(attendu[pd.Timestamp(jour)],
                                                                 rel=1e-12)
    assert math.isnan(rvj.at[pd.Timestamp("2024-01-03"), "rv"])


def test_un_jour_entierement_absent_est_exclu_et_le_rendement_suivant_n_existe_pas():
    b = _barres(3, debut="2024-01-01", graine=2)
    bt = b[b.index.tz_convert(None).normalize() != pd.Timestamp("2024-01-02")]
    rvj = hr.rv_journaliere(bt)
    assert list(rvj.index) == list(pd.date_range("2024-01-01", periods=3, freq="D"))
    assert list(rvj["barres"]) == [288, 0, 288] and list(rvj["exclu"]) == [False, True, False]
    assert rvj.at[pd.Timestamp("2024-01-03"), "rendements"] == 287


def test_ecart_type_30_jours_echantillon_au_carre_sans_traverser_un_trou():
    rng = np.random.default_rng(3)
    jours = pd.date_range("2024-01-01", periods=60, freq="D")
    s = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.02, 60))), index=jours)
    r = np.log(s).diff()
    v = hr.ecart_type_30(s)
    assert math.isnan(v.iloc[29])
    assert v.iloc[30] == pytest.approx(np.var(r.iloc[1:31].to_numpy(), ddof=1), rel=1e-12)
    assert v.iloc[-1] == pytest.approx(np.var(r.iloc[-30:].to_numpy(), ddof=1), rel=1e-12)
    v2 = hr.ecart_type_30(s.drop(jours[40]))
    assert v2.loc[jours[40]:].isna().all() and v2.iloc[39] == v.iloc[39]


def test_le_har_prend_les_lignes_entierement_dans_la_fenetre_de_730_jours_de_rv():
    rv = hr.rv_journaliere(_barres(900, graine=4))["rv"]
    h = hr.har(rv)
    x = hr.regresseurs(rv)
    assert h["prevision"].first_valid_index() == rv.index[729]
    assert h["lignes"].iloc[729] == 704
    t = 850
    s = np.arange(t - 708, t - 4)                                  # s de t - 708 a t - 5
    X = np.column_stack([np.ones(len(s)), x[["rv_jour", "rv_5", "rv_22"]].to_numpy()[s]])
    beta = np.linalg.lstsq(X, x["cible"].to_numpy()[s], rcond=None)[0]
    xt = np.r_[1.0, x[["rv_jour", "rv_5", "rv_22"]].to_numpy()[t]]
    assert h["prevision"].iloc[t] == pytest.approx(xt @ beta, rel=1e-12)
    assert h["lignes"].iloc[t] == 704
    assert x["rv_5"].iloc[t] == pytest.approx(rv.iloc[t - 4:t + 1].mean(), rel=1e-12)
    assert x["rv_22"].iloc[t] == pytest.approx(rv.iloc[t - 21:t + 1].mean(), rel=1e-12)
    assert x["cible"].iloc[t] == pytest.approx(rv.iloc[t + 1:t + 6].mean(), rel=1e-12)


def test_les_replis_avant_730_jours_et_prevision_negative_ou_nulle():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    prev = pd.Series([np.nan, np.nan, 0.5, -0.1, 0.0], index=idx)
    jours = pd.Series([728, 729, 730, 731, 732], index=idx)
    ecart = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], index=idx)
    p, avant, negative = hr.replis(prev, jours, ecart)
    assert list(p) == [1.0, 2.0, 0.5, 4.0, 5.0]
    assert list(avant) == [True, True, False, False, False]
    assert list(negative) == [False, False, False, True, True]


def test_qlike_nulle_si_exacte_et_plus_dure_pour_la_sous_estimation():
    assert hr.qlike(2.0, 2.0) == 0.0
    assert hr.qlike(1.0, 2.0) == pytest.approx(0.5 - math.log(0.5) - 1)
    assert hr.qlike(2.0, 1.0) > hr.qlike(1.0, 2.0)


def test_regle_5_stricte():
    assert hr.decision(0.30, 0.30) == R.HAR
    assert hr.decision(0.3001, 0.30) == R.ECART_TYPE
    assert hr.decision(0.20, 0.30) == R.HAR


def test_diebold_mariano_formule_de_newey_west():
    assert hr.diebold_mariano(np.ones(29))["p"] is None
    d = np.random.default_rng(5).normal(-0.05, 0.2, 400)
    dm = hr.diebold_mariano(d)
    n, retard = 400, int(4 * (400 / 100) ** (2 / 9))
    u = d - d.mean()
    var = u @ u / n + sum(2 * (1 - k / (retard + 1)) * (u[k:] @ u[:-k]) / n
                          for k in range(1, retard + 1))
    assert dm["retard"] == retard == 5 and dm["n"] == n
    assert dm["stat"] == pytest.approx(d.mean() / math.sqrt(var / n), rel=1e-12)
    assert dm["stat"] < 0 and dm["p"] < 0.01


def test_un_actif_synthetique_de_bout_en_bout(monkeypatch):
    monkeypatch.setattr(R, "COUPURES_CAUSALITE", ("2020-12-31", "2021-01-31"))
    b = _barres(800)
    a = ca.mesurer_actif(b, _cloture_1d(b))
    assert a["sigma_retenu"] == hr.decision(a["qlike"]["har"], a["qlike"]["ecart_type"])
    assert a["jours_evalues"] == 800 - 729 - 5                    # origines 729 a 794
    assert a["periodes"]["har_des_le"] == "2020-12-30"
    assert a["jours_exclus"]["total"] == 0 and a["causalite"] == []
    assert a["dernier_har"]["lignes"] == 704
    assert a["diebold_mariano"]["n"] == a["jours_evalues"]


def test_un_jour_evaluable_sans_prevision_arrete_la_campagne(monkeypatch):
    monkeypatch.setattr(R, "COUPURES_CAUSALITE", ())
    b = _barres(800)
    jour = pd.Timestamp("2021-01-30")                             # dans la periode evaluee
    bt = b[b.index.tz_convert(None).normalize() != jour]
    with pytest.raises(ca.ControleError, match="sans prevision HAR"):
        ca.mesurer_actif(bt, _cloture_1d(bt))


def test_l_epreuve_de_causalite_attrape_un_regard_vers_le_futur(monkeypatch):
    monkeypatch.setattr(R, "COUPURES_CAUSALITE", ("2020-12-31", "2021-01-31"))
    b = _barres(800)
    c = _cloture_1d(b)
    assert ca.causalite(b, c, ca.previsions(b, c)) == []
    vrai = hr.ecart_type_30
    monkeypatch.setattr(ca.hr, "ecart_type_30", lambda s: vrai(s).shift(-1))
    assert ca.causalite(b, c, ca.previsions(b, c)) != []


def test_les_copies_sont_verifiees_par_leur_sha256_et_coupees_a_la_fin(tmp_path, monkeypatch):
    idx = pd.date_range("2026-10-31 23:45", "2026-11-01 00:10", freq="5min", tz="UTC")
    df5 = pd.DataFrame({"date": idx, "open": 1.0, "high": 1.0, "low": 1.0,
                        "close": np.arange(1.0, len(idx) + 1), "volume": 1.0})
    jours = pd.date_range("2026-10-30", "2026-11-01", freq="D", tz="UTC")
    df1 = pd.DataFrame({"date": jours, "open": 1.0, "high": 1.0, "low": 1.0,
                        "close": [5.0, 2.0, 9.0], "volume": 1.0})
    c5, c1 = tmp_path / "X_perp_5m.parquet", tmp_path / "X_perp_1d.parquet"
    df5.to_parquet(c5, index=False)
    df1.to_parquet(c1, index=False)
    sha = {p.stem: hashlib.sha256(p.read_bytes()).hexdigest() for p in (c5, c1)}
    monkeypatch.setattr(R, "SHA256", sha)
    monkeypatch.setattr(R, "ACTIFS", {"X": {"bougies_5m": str(c5), "bougies_1d": str(c1),
                                            "serie": "x"}})
    b, c = dn.bougies_5m("X"), dn.clotures_1d("X")
    assert b.index.max() == pd.Timestamp("2026-10-31 23:55", tz="UTC") and len(b) == 3
    assert c.index.tz is None and list(c) == [5.0, 2.0]
    assert dn.controle_clotures(b, c) == ["2026-10-30", "2026-10-31"]   # sans barre ; 2 != 3
    monkeypatch.setattr(R, "SHA256", {**sha, "X_perp_5m": "0" * 64})
    with pytest.raises(dn.DonneesError, match="change depuis le gel"):
        dn.bougies_5m("X")


def test_le_rapport_et_l_addendum_s_ecrivent_sur_une_synthese_fabriquee(tmp_path, monkeypatch):
    from beta.controle_har import rapport

    monkeypatch.setattr(R, "COUPURES_CAUSALITE", ())
    actifs = {}
    for nom, graine in (("BTC", 0), ("ETH", 1)):
        b = _barres(800, graine=graine)
        c = _cloture_1d(b)
        actifs[nom] = {"couverture": dn.couverture(b, c), **ca.mesurer_actif(b, c)}
    s = ca._propre({
        "experience": R.ID_EXP, "code": "x", "regles": R.empreinte(), "preenregistrement": "p",
        "calcule_le": "2026-11-01T19:00:00+00:00",
        "donnees": {"empreinte": "e", "fin": R.FIN, "sha256": R.SHA256, "copies": R.ACTIFS},
        "compteur": {"avant": {"global": 1, "invest": 1, "trading": 0},
                     "apres": {"global": 1, "invest": 1, "trading": 0}, "diagnostic": True},
        "actifs": actifs})
    md = rapport.markdown(s)
    assert ("| actif | QLIKE HAR | QLIKE écart-type 30 jours | p de Diebold-Mariano | jours "
            "évalués | jours exclus | prévisions ≤ 0 remplacées |") in md
    for titre in ("## 1. Tableau par actif", "## 2. σ̂ retenu par actif", "## 3. Périodes",
                  "## 4. Diebold-Mariano", "## 7. Empreintes", "## 8. Épreuve de causalité"):
        assert titre in md
    assert "**BTC : σ̂ = " in md and "**ETH : σ̂ = " in md
    assert "T1J" not in md and "T1F" not in md and "T1C" not in md
    monkeypatch.setattr(ca, "SORTIE", tmp_path)
    rapport.ecrire(s)
    for f in ("RAPPORT_CONTROLE_HAR.md", "RAPPORT_CONTROLE_HAR.csv", "RESUME_DISCORD.md"):
        assert (tmp_path / f).exists()
    spec = tmp_path / "spec_figee.md"
    spec.write_text("# spec\n", encoding="utf-8")
    monkeypatch.setattr(ca, "SPEC", spec)
    assert rapport.ajouter_addendum(s) is True
    assert rapport.ajouter_addendum(s) is False                       # une seule fois
    texte = spec.read_text(encoding="utf-8")
    assert texte.startswith("# spec\n") and texte.count(rapport.TITRE_ADDENDUM) == 1
    assert "## Addendum du 01/11/2026 — σ̂ retenu au « Contrôle HAR »" in texte
