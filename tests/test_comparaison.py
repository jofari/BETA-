"""La boite a idees et le banc COMPARATIF : ce qui ne se voit qu'a plusieurs.

Deux etages testes ensemble parce qu'ils repondent a la meme demande : « ou je suggere une
idee » et « comment je compare plusieurs strategies entre elles ». Le fil commun est le
compteur d'essais — noter une idee ne doit rien couter, la promouvoir doit couter, et
comparer vingt candidates doit devenir plus severe, pas plus flatteur.

Le test qui porte le module : `test_le_reality_check_ne_sacre_pas_le_meilleur_de_vingt_
bruits`. Sans lui, rien ne distingue un banc comparatif d'un classeur de resultats.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from beta.protocole import experiences, idees
from beta.stats import comparaison

# --- la boite a idees ---------------------------------------------------------------------

@pytest.fixture
def boite(tmp_path, monkeypatch):
    """Une boite et un registre d'experiences jetables : on ne touche pas aux vrais."""
    monkeypatch.setattr(idees, "REGISTRE", tmp_path / "IDEES.jsonl")
    monkeypatch.setattr(experiences, "REGISTRE", tmp_path / "EXPERIMENTS.jsonl")
    # Sans ce patch, `compteur()` lit le JOURNAL_RUNS REEL : des qu'une hypothese est
    # reellement mesuree sous un id que le test reutilise (R9, R10...), le compteur ne
    # monte plus dans le test et `promouvoir` ne fait plus +1. Le banc de test doit etre
    # isole du registre reel, journal compris.
    monkeypatch.setattr(experiences, "JOURNAL_RUNS", tmp_path / "RUNS.jsonl")
    return tmp_path / "IDEES.jsonl"


def test_noter_une_idee_ne_coute_rien(boite):
    """LE point de la boite : sans etage gratuit, on ne note aucune idee et on les perd."""
    avant = experiences.compteur()
    idees.ajouter("Le funding extreme precede un retournement de la tendance courte.")
    assert experiences.compteur() == avant


def test_promouvoir_avance_le_compteur_d_un_cran(boite):
    idees.ajouter("Le funding extreme precede un retournement de la tendance courte.")
    avant = experiences.compteur()
    promue = idees.promouvoir("I1", "R9", "hypothese falsifiable", "R moyen",
                              {"confirmee": "p<=0.05", "infirmee": "sinon"})
    assert promue["compteur_apres"] == avant + 1
    assert idees.etat()["I1"]["etat"] == idees.PROMUE


def test_une_idee_ne_se_promeut_pas_deux_fois(boite):
    """Deux promotions pour une hypothese compteraient deux essais pour un seul test."""
    idees.ajouter("Une idee que je vais promouvoir deux fois.")
    idees.promouvoir("I1", "R9", "h", "m", {"confirmee": "x"})
    with pytest.raises(idees.IdeeError, match="deja promue"):
        idees.promouvoir("I1", "R10", "h", "m", {"confirmee": "x"})


def test_une_promotion_refusee_laisse_l_idee_intacte(boite):
    """Si le preenregistrement echoue, l'idee ne doit PAS se dire promue.

    L'inverse laisserait une idee marquee promue sans experience derriere — un mensonge
    dans le seul fichier ou l'on va chercher ce qui reste a faire.
    """
    idees.ajouter("Une idee dont la promotion va echouer.")
    experiences.preenregistrer("R9", "deja pris", "m", {"confirmee": "x"})
    with pytest.raises(experiences.ProtocoleError):
        idees.promouvoir("I1", "R9", "h", "m", {"confirmee": "x"})
    assert idees.etat()["I1"]["etat"] == idees.NOUVELLE


def test_une_idee_ecartee_reste_au_fichier(boite):
    """Savoir ce qu'on a decide de NE PAS tester, et pourquoi, vaut autant qu'un resultat."""
    idees.ajouter("Une idee que je vais ecarter apres reflexion.")
    idees.ecarter("I1", "deja mesuree cote ARIT en juillet")
    etat = idees.etat()["I1"]
    assert etat["etat"] == idees.ECARTEE
    assert "juillet" in etat["motif"]
    assert "Une idee que je vais ecarter" in etat["texte"]     # le texte survit a la fusion


def test_ecarter_sans_motif_est_refuse(boite):
    idees.ajouter("Une idee quelconque, assez longue pour passer.")
    with pytest.raises(idees.IdeeError, match="sans motif"):
        idees.ecarter("I1", "   ")


def test_une_idee_trop_courte_est_refusee(boite):
    with pytest.raises(idees.IdeeError, match="dix caracteres"):
        idees.ajouter("court")


def test_les_idees_vivent_hors_de_data():
    """`data/` est jetable : une idee perdue par un nettoyage est une idee qu'on n'aura pas."""
    from beta import config
    assert config.DATA not in idees.REGISTRE.parents


# --- le banc comparatif -------------------------------------------------------------------

def _equity(rendements: np.ndarray, depart: str = "2021-01-01") -> pd.DataFrame:
    dates = pd.date_range(depart, periods=len(rendements), freq="1D", tz="UTC")
    return pd.DataFrame({"ts": dates, "equity": 100_000.0 * (1 + rendements).cumprod()})


def _verdict(nom: str, r_moyen: float, n: int = 100):
    return type("V", (), {"metriques": {"n": n, "r_moyen": r_moyen, "mde_r": 0.2},
                          "issue": "indecidable", "portes_echouees": [],
                          "portes_non_executees": ["S1_benjamini_hochberg"],
                          "run": type("R", (), {"id_experience": "R9"})()})()


def test_le_reality_check_ne_sacre_pas_le_meilleur_de_vingt_bruits():
    """Le test qui distingue un banc comparatif d'un classeur de resultats.

    Vingt candidates de bruit pur : la meilleure aura toujours l'air bonne. S7 doit dire
    que ce n'est pas une decouverte. Sans cette porte, le premier gagnant du banc serait un
    artefact du CHOIX du meilleur, et on l'aurait cru.
    """
    rng = np.random.default_rng(7)
    univers = {f"bruit{i}": rng.normal(0, 1, 400) for i in range(20)}
    equities = {nom: _equity(serie / 100) for nom, serie in univers.items()}
    verdicts = {nom: _verdict(nom, float(serie.mean())) for nom, serie in univers.items()}

    classement = comparaison.classer(verdicts, equities, univers_r=univers)
    assert classement["reality_check"]["p_value"] > 0.05


def test_le_reality_check_voit_une_vraie_gagnante_glissee_dans_le_bruit():
    """Le controle symetrique : une porte qui refuse TOUT ne prouve rien non plus."""
    rng = np.random.default_rng(11)
    univers = {f"bruit{i}": rng.normal(0, 1, 400) for i in range(19)}
    univers["vraie"] = rng.normal(0.45, 1, 400)
    equities = {nom: _equity(serie / 100) for nom, serie in univers.items()}
    verdicts = {nom: _verdict(nom, float(serie.mean())) for nom, serie in univers.items()}

    rc = comparaison.classer(verdicts, equities, univers_r=univers)["reality_check"]
    assert rc["p_value"] <= 0.05
    assert rc["meilleure"] == "vraie"


def test_deux_candidates_identiques_sont_signalees_redondantes():
    """Deux strategies correlees a 1 n'en font pas deux : elles en font une, testee deux fois."""
    rng = np.random.default_rng(3)
    serie = rng.normal(0.001, 0.02, 300)
    equities = {"a": _equity(serie), "jumelle": _equity(serie * 1.01)}
    verdicts = {nom: _verdict(nom, 0.1) for nom in equities}

    classement = comparaison.classer(verdicts, equities)
    redondances = classement["redondances"]
    assert redondances and {redondances[0]["a"], redondances[0]["b"]} == {"a", "jumelle"}
    assert redondances[0]["correlation"] > 0.95


def test_le_classement_est_trie_sur_le_r_moyen_pas_sur_l_issue():
    """Classer par verdict mettrait en tete celles qui ont eu la chance qu'une porte saute."""
    rng = np.random.default_rng(5)
    equities = {nom: _equity(rng.normal(0, 0.01, 200)) for nom in ("faible", "forte")}
    verdicts = {"faible": _verdict("faible", -0.3), "forte": _verdict("forte", 0.4)}
    tableau = comparaison.classer(verdicts, equities)["tableau"]
    assert list(tableau["candidate"]) == ["forte", "faible"]
    assert list(tableau["rang"]) == [1, 2]


def test_une_seule_candidate_donne_une_reserve_explicite():
    """Avec une candidate, S7 n'a pas d'objet — et le banc doit le DIRE, pas passer."""
    equities = {"seule": _equity(np.random.default_rng(1).normal(0, 0.01, 200))}
    classement = comparaison.classer({"seule": _verdict("seule", 0.1)}, equities,
                                     univers_r={"seule": np.zeros(50)})
    assert not np.isfinite(classement["reality_check"]["p_value"])
    assert any("n'a pas d'objet" in r for r in classement["reserves"])


def test_l_ecart_contre_arit_se_mesure_sur_la_periode_COMMUNE():
    """Comparer 2021-2022 a 2019-2026 ferait gagner la comparaison sur des annees non vues."""
    rng = np.random.default_rng(13)
    candidate = _equity(rng.normal(0.001, 0.01, 200), depart="2022-01-01")
    arit = _equity(rng.normal(0.000, 0.01, 900), depart="2021-01-01")
    classement = comparaison.classer({"c": _verdict("c", 0.2)}, {"c": candidate},
                                     equity_arit=arit)
    ligne = classement["tableau"].iloc[0]
    assert 150 <= ligne["vs_arit_n_jours_communs"] <= 200


def test_l_absence_d_arit_est_une_reserve_pas_un_plantage():
    equities = {"seule": _equity(np.random.default_rng(2).normal(0, 0.01, 100))}
    reserves = comparaison.classer({"seule": _verdict("seule", 0.1)}, equities)["reserves"]
    assert any("AritV1 absent" in r for r in reserves)


def test_la_comparaison_dit_toujours_que_le_R_d_arit_n_est_pas_comparable():
    """La faute la plus facile ici serait de moyenner un R d'ARIT et un R du moteur."""
    rng = np.random.default_rng(17)
    equities = {"c": _equity(rng.normal(0.001, 0.01, 300))}
    arit = _equity(rng.normal(0.0, 0.01, 300))
    reserves = comparaison.classer({"c": _verdict("c", 0.2)}, equities,
                                   equity_arit=arit)["reserves"]
    assert any("COURBES journalieres seulement" in r for r in reserves)


# --- la vue du dashboard ----------------------------------------------------------------------

def test_la_vue_ne_compte_qu_un_run_par_candidate():
    """Deux runs de la meme candidate ne sont pas deux strategies.

    Les compter deux fois gonflerait l'univers de S7 avec une copie de lui-meme — donc
    rendrait la porte plus severe pour une mauvaise raison — et la matrice afficherait
    fierement 1,00 entre une candidate et elle-meme.
    """
    from beta.rapport import comparaison as vue_comparaison
    runs = vue_comparaison._runs_a_comparer("train")
    assert len(runs) == len({v.get("candidate") for v in runs.values()})


def test_la_vue_est_serialisable_en_json():
    """Un seul NaN au fond fait page blanche sans rien dire dans le navigateur."""
    import json

    from beta.rapport import comparaison as vue_comparaison
    texte = json.dumps(vue_comparaison.vue("train"), allow_nan=False)
    assert "NaN" not in texte
