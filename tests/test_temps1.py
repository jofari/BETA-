"""Temps 1, etape A (labo actions) : detecteurs, point-in-time, branchement sur le moteur TI1.

Ce que ces tests protegent : les regles du prompt telles qu'ecrites (inegalites strictes, priorite
de COUCHE1, paliers 1,0 / 0,7 / 0,25) ; la causalite (un detecteur calcule sur l'historique
tronque rend la meme chose) ; DEXJPUS jamais lu avant sa publication ; le calendrier civil donne
au moteur la MEME courbe aux dates de seance qu'un calcul seance par seance ; les portes et le
verdict mecaniques ; le compteur +1 par couple, journalise avant le calcul ; aucune donnee crypto.
"""

from __future__ import annotations

import pathlib

import numpy as np
import pandas as pd
import pytest

from beta.invest import moteur
from beta.invest.moteur import Mapping
from beta.protocole import experiences
from beta.temps1 import campagne as ca
from beta.temps1 import detecteurs as det
from beta.temps1 import donnees as dn


def _seances(debut, fin):
    return pd.bdate_range(debut, fin)


def _donnees(debut="1988-01-01", fin="1993-12-31", graine=0, publie=None) -> dn.Donnees:
    """Cinq series synthetiques en jours ouvres, avec une baisse de 40 % en 1991."""
    rng = np.random.default_rng(graine)
    jours = _seances(debut, fin)
    n = len(jours)
    tendance = np.where((jours >= "1991-03-01") & (jours <= "1991-09-30"), -0.004, 0.0004)
    spx = 100 * np.exp(np.cumsum(tendance + rng.normal(0, 0.008, n)))
    ndx = 100 * np.exp(np.cumsum(1.3 * tendance + rng.normal(0, 0.011, n)))
    vix = np.clip(18 + 20 * (tendance < 0) + rng.normal(0, 2, n), 9, None)
    xau = 400 * np.exp(np.cumsum(rng.normal(0.0001, 0.007, n)))
    jpy = 140 * np.exp(np.cumsum(rng.normal(0, 0.004, n)))
    closes = {"SPX": pd.Series(spx, index=jours), "NDX": pd.Series(ndx, index=jours),
              "VIX": pd.Series(vix, index=jours), "XAU_LBMA": pd.Series(xau, index=jours),
              "DEXJPUS": pd.Series(jpy, index=jours)}
    dispo, pit = dn.disponibilite_dexjpus(jours, publie)
    return dn.Donnees(closes=closes, dexjpus_dispo=dispo, pit_dexjpus=pit, fin=jours[-1],
                      empreinte=dn.empreinte(closes, dispo), couverture={})


# ----------------------------------------------------------------------------- detecteurs

def test_sma_stricte_et_indefinie_pendant_la_prechauffe():
    close = pd.Series([1.0, 2.0, 3.0, 2.0, 2.0], index=_seances("2020-01-06", "2020-01-10"))
    d = det.au_dessus_sma(close, 3)
    assert d.iloc[:2].isna().all()
    assert list(d.iloc[2:]) == [1.0, 0.0, 0.0]        # 2 > 7/3 ? non ; 2 > 2 ? non (stricte)
    assert list(det.score_binaire(d).iloc[2:]) == [1.0, -1.0, -1.0]


def test_momentum_126_strictement_positif():
    close = pd.Series(np.r_[np.full(126, 10.0), 10.0, 10.5], index=_seances("2020-01-01",
                                                                          "2020-07-31")[:128])
    m = det.momentum_positif(close)
    assert m.iloc[:126].isna().all() and list(m.iloc[126:]) == [0.0, 1.0]


@pytest.mark.parametrize(("v", "y", "t", "g", "attendu"), [
    (1, 0, 1, 1, -1.0), (0, 1, 0, 0, -1.0), (1, 1, 0, 0, -1.0),   # liquidite d'abord
    (0, 0, 1, 1, 0.0),                                             # monetaire : T et G
    (0, 0, 1, 0, 1.0), (0, 0, 0, 1, 1.0), (0, 0, 0, 0, 1.0),      # expansion sinon
])
def test_couche1_priorite_des_etats(v, y, t, g, attendu):
    ind = pd.DataFrame({"T": [float(t)], "V": [float(v)], "Y": [float(y)], "G": [float(g)]})
    assert det.couche1(ind).iloc[0] == attendu


def test_couche1_indefinie_si_un_indicateur_manque():
    ind = pd.DataFrame({"T": [1.0], "V": [np.nan], "Y": [0.0], "G": [1.0]})
    assert np.isnan(det.couche1(ind).iloc[0])


def test_paliers_du_moteur_rendent_les_expositions_du_prompt():
    e = moteur.exposition(np.array([1.0, 0.0, -1.0]), Mapping("paliers"))
    assert list(e) == [1.0, 0.7, 0.25]


@pytest.mark.parametrize("nom", det.DETECTEURS)
def test_causalite_tronquer_l_historique_ne_change_rien(nom):
    d = _donnees()
    decisions = d.closes["SPX"].index[(d.closes["SPX"].index >= "1990-06-01")]
    complet = det.score(nom, d, "NDX", decisions)
    coupe = pd.Timestamp("1991-06-14")
    tronque = dn.Donnees(closes={k: s[s.index <= coupe] for k, s in d.closes.items()},
                         dexjpus_dispo=d.dexjpus_dispo[d.closes["DEXJPUS"].index <= coupe],
                         pit_dexjpus=d.pit_dexjpus, fin=coupe, empreinte="", couverture={})
    partiel = det.score(nom, tronque, "NDX", decisions[decisions <= coupe])
    pd.testing.assert_series_equal(partiel, complet[complet.index <= coupe])


# ----------------------------------------------------------------------------- DEXJPUS PIT

def test_repli_deux_jours_ouvres_us_saute_les_feries():
    dates = pd.DatetimeIndex(["2026-10-09", "2026-10-13"])        # 12/10 : Columbus Day
    dispo, pit = dn.disponibilite_dexjpus(dates, None)
    assert list(dispo.strftime("%Y-%m-%d")) == ["2026-10-14", "2026-10-15"]
    assert pit["mode"] == "decalage_2_jours_ouvres"


def test_alfred_strictement_apres_la_publication_sinon_repli():
    dates = pd.DatetimeIndex(["2026-10-13", "2026-10-14", "1999-01-04"])
    publie = pd.Series(pd.to_datetime(["2026-10-19", "2026-10-19", "2009-06-01"]), index=dates)
    dispo, pit = dn.disponibilite_dexjpus(dates, publie)
    assert list(dispo.strftime("%Y-%m-%d")) == ["2026-10-20", "2026-10-20", "1999-01-06"]
    assert pit == {"mode": "mixte", "observations": 3, "datees_alfred": 2,
                   "repli_2_jours_ouvres": 1}


def test_derniere_connue_n_utilise_que_le_publie():
    valeurs = pd.Series([1.0, 2.0, 3.0], index=pd.DatetimeIndex(["2026-10-12", "2026-10-13",
                                                                 "2026-10-14"]))
    dispo = pd.DatetimeIndex(["2026-10-20", "2026-10-20", "2026-10-27"])
    decisions = pd.DatetimeIndex(["2026-10-16", "2026-10-20", "2026-10-26", "2026-10-27"])
    x = dn.derniere_connue(valeurs, dispo, decisions)
    assert np.isnan(x.iloc[0]) and list(x.iloc[1:]) == [2.0, 2.0, 3.0]


# ----------------------------------------------------------------------------- adaptateur

def test_score_en_vigueur_le_week_end_et_le_lundi_viennent_du_vendredi():
    score = pd.Series([1.0, -1.0, 1.0], index=pd.DatetimeIndex(["2026-10-15", "2026-10-16",
                                                                "2026-10-19"]))
    jours = pd.date_range("2026-10-16", "2026-10-20")
    s = ca.score_en_vigueur(score, jours)
    assert list(s) == [1.0, -1.0, -1.0, -1.0, 1.0]    # ven <- jeu ; sam, dim, lun <- ven


def test_le_calendrier_civil_donne_la_courbe_des_seances():
    d = _donnees()
    debut, fin = pd.Timestamp("1991-01-01"), pd.Timestamp("1991-12-31")
    decisions = dn.seances(d, "SPX", debut, fin)
    score = det.score("SMA200", d, "SPX", decisions)
    closes = ca.grille(d.closes["SPX"], "SPX", debut, fin)
    p = moteur.panier(closes, {"SPX": 1.0}, debut, fin)
    e = moteur.exposition(moteur.aligner(ca.score_en_vigueur(score, p.jours), p.jours),
                          Mapping("paliers"))
    v_cal = pd.Series(np.cumprod(1 + moteur.rendement(e, p.r, 10.0)["r"]), index=p.jours)
    # Le meme calcul, seance par seance : E decidee a la seance precedente.
    px = d.closes["SPX"][decisions]
    e_s = np.where(score.to_numpy() > 0, 1.0, 0.25)
    r_s = px.to_numpy()[1:] / px.to_numpy()[:-1] - 1
    cout = 10.0 / 1e4 * np.abs(np.diff(np.r_[e_s[0], e_s[:-1]]))
    v_seances = pd.Series(np.cumprod(1 + e_s[:-1] * r_s - cout), index=decisions[1:])
    np.testing.assert_allclose(v_cal.reindex(decisions[1:]).to_numpy(), v_seances.to_numpy(),
                               rtol=1e-12)


def test_une_periode_complete_passe_par_le_moteur_et_les_nulls():
    d = _donnees()
    cfg = ca.Config("COUCHE1", "NDX", labo=("1991-01-01", "1991-12-31"),
                    informative=("1992-01-01", "1993-12-31"), b=30)
    res = ca.evaluer(cfg, d)
    labo = res["periodes"]["labo"]
    assert labo["periode"]["n_jours"] == 365 and labo["nulls"]["b"] == 30
    assert 0 < labo["nulls"]["p_retenue"] <= 1
    assert labo["metriques"]["temoin"]["expo_moyenne"] == pytest.approx(
        labo["metriques"]["strategie"]["expo_moyenne"])
    assert set(labo["periode"]["part_par_exposition"]) == {"1", "0.7", "0.25"}


def test_prechauffe_insuffisante_arrete_tout():
    d = _donnees(debut="1990-06-01")
    cfg = ca.Config("SMA252", "SPX", labo=("1991-01-01", "1991-12-31"),
                    informative=("1992-01-01", "1993-12-31"), b=0)
    with pytest.raises(dn.DonneesError, match="prechauffe"):
        ca.evaluer(cfg, d)


# ----------------------------------------------------------------------------- portes

def _ligne(detecteur, cible, ulcer, temoin, p):
    return {"detecteur": detecteur, "cible": cible, "ulcer": ulcer, "ulcer_temoin": temoin,
            "p_retenue": p}


def _lot_avec(surcharges: dict | None = None) -> list[dict]:
    """SMA200 passe les portes 1-2 ; tout le reste echoue, sauf ce que `surcharges` change."""
    base = {("SMA200", c): (0.10, 0.12, 0.01) for c in ca.CIBLES}
    base.update({(x, c): (0.20, 0.25, 0.30) for x in ("SMA126", "SMA168", "SMA210", "SMA252",
                                                      "MOM126", "COUCHE1") for c in ca.CIBLES})
    base.update(surcharges or {})
    return ca.portes([_ligne(x, c, *v) for (x, c), v in base.items()])


def test_portes_bande_non_jugee_et_porte_3_aux_candidats_seulement():
    lot = {(x["detecteur"], x["cible"]): x for x in _lot_avec()}
    assert lot[("SMA168", "SPX")]["porte1"] is None and lot[("SMA168", "SPX")]["porte3"] is None
    assert lot[("SMA200", "SPX")]["porte1"] is True and lot[("SMA200", "SPX")]["porte3"] is None
    assert lot[("MOM126", "NDX")]["porte3"] is False


def test_verdict_sma200_retenue_puis_candidat_puis_rien():
    assert ca.verdict(_lot_avec())["verdict"] == "SMA200 retenue"
    gagnant = {("COUCHE1", c): (0.05, 0.08, 0.001) for c in ca.CIBLES}
    assert ca.verdict(_lot_avec(gagnant)) == {"verdict": "candidat retenu",
                                              "retenus": ["COUCHE1"], "sma200_portes_1_2": True}
    sur_un_seul = {("COUCHE1", "SPX"): (0.05, 0.08, 0.001)}
    assert ca.verdict(_lot_avec(sur_un_seul))["verdict"] == "SMA200 retenue"
    sans_timing = {("SMA200", "NDX"): (0.10, 0.12, 0.06)}
    assert ca.verdict(_lot_avec(sans_timing)) == {"verdict": "aucun timing demontre",
                                                  "retenus": [], "sma200_portes_1_2": False}


def test_deux_candidats_qui_passent_sont_retenus_tous_les_deux():
    gagnants = {(x, c): (0.05, 0.08, 0.001) for x in ca.CANDIDATS for c in ca.CIBLES}
    assert ca.verdict(_lot_avec(gagnants))["retenus"] == ["MOM126", "COUCHE1"]


# ----------------------------------------------------------------------------- compteur

def test_quatorze_essais_journalises_avant_le_calcul_et_jamais_recomptes(tmp_path, monkeypatch):
    registre, runs = tmp_path / "EXPERIMENTS.jsonl", tmp_path / "RUNS.jsonl"
    monkeypatch.setattr(experiences, "REGISTRE", registre)
    monkeypatch.setattr(experiences, "JOURNAL_RUNS", runs)
    avant = experiences.compteur()
    experiences.preenregistrer(ca.ID_EXP, "h", "Ulcer", {"r": "x"}, split_autorise="labo")
    assert experiences.compteur() == avant + 1
    cfgs = ca.configs(pd.Timestamp("2026-10-20"), b=1000)
    assert len(cfgs) == 14
    ca.journaliser(cfgs, "abc")
    assert experiences.compteur() == avant + 14
    ca.journaliser(cfgs, "abc")                                  # rejouer ne compte rien
    assert experiences.compteur() == avant + 14


def test_aucune_donnee_crypto_n_entre_dans_le_labo():
    dossier = pathlib.Path(ca.__file__).parent
    for f in dossier.glob("*.py"):
        texte = f.read_text(encoding="utf-8")
        for interdit in ("beta.lake", "beta.strategies", "beta.data", "voie_c2"):
            assert interdit not in texte, f"{f.name} importe {interdit}"


# ----------------------------------------------------------------------------- bout en bout

def test_campagne_et_rapport_de_bout_en_bout_sur_donnees_synthetiques(tmp_path, monkeypatch):
    from beta.temps1 import rapport
    monkeypatch.setattr(experiences, "REGISTRE", tmp_path / "EXPERIMENTS.jsonl")
    monkeypatch.setattr(experiences, "JOURNAL_RUNS", tmp_path / "RUNS.jsonl")
    monkeypatch.setattr(ca, "DOSSIER", tmp_path / "data_temps1")
    monkeypatch.setattr(ca, "LABO", ("1991-01-01", "1991-12-31"))
    monkeypatch.setattr(ca, "DEBUT_INFORMATIVE", "1992-01-01")
    monkeypatch.setattr(rapport, "DOSSIER_RAPPORT", tmp_path / "temps1")
    experiences.preenregistrer(ca.ID_EXP, "h", "Ulcer", {"r": "x"}, split_autorise="labo",
                               compteur={"avant": experiences.compteur()})
    d = _donnees()
    syn = ca.lancer_campagne(d, b=20)
    assert syn["compteur"]["avant_t1a"] == 30 and syn["compteur"]["apres_preenregistrement"] == 31
    assert syn["compteur"]["apres"] == 44 and experiences.compteur() == 44
    assert len(syn["labo"]) == 14 and len(syn["informative"]) == 14
    assert syn["verdict"]["verdict"] in ("candidat retenu", "SMA200 retenue",
                                         "aucun timing demontre")
    mesures = [x for x in experiences._lignes() if x.get("statut") == "mesure"]
    assert len(mesures) == 1
    ca.lancer_campagne(d, b=20)                                   # rejeu : rien de plus
    assert experiences.compteur() == 44
    assert len([x for x in experiences._lignes() if x.get("statut") == "mesure"]) == 1
    chemin = rapport.ecrire(syn, ["ecart de test"])
    texte = chemin.read_text(encoding="utf-8")
    for titre in ("## 1. Compteur", "## 2. Couverture", "## 3. Tableau principal",
                  "## 4. Bande SMA", "## 5. Période informative", "## 6. Verdict mécanique",
                  "## 7. Écarts au prompt", "déjà vu, ne décide rien", "ecart de test"):
        assert titre in texte
    lignes = (tmp_path / "temps1" / "RAPPORT_ETAPE_A.csv").read_text(encoding="utf-8")
    assert len(lignes.strip().splitlines()) == 1 + 28
