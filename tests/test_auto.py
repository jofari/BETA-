"""Tests de l'auto-recherche et des trois dettes qu'elle obligeait a fermer.

Ce fichier ne teste presque pas la generation de code — un modele local n'est pas
reproductible, et ce n'est pas la que se trouve le danger. Il teste ce qui doit tenir
QUAND une machine ecrit vingt candidates par nuit :

    A1 / T8   le compteur d'essais compte les mesures, pas les hypotheses
    T9        S1 tourne, donc CONFIRMEE cesse d'etre inatteignable
    T10       le registre dit ce qui a ete mesure
    auto      la boucle refuse de demarrer plutot que de mesurer sans protocole

Le refus est la fonctionnalite. Un test qui verifie qu'une boucle d'auto-recherche
DEMARRE ne dit rien d'interessant ; ceux qui verifient qu'elle s'arrete, si.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from beta.moteur import pipeline  # noqa: E402
from beta.protocole import experiences  # noqa: E402
from beta.recherche import auto  # noqa: E402


@pytest.fixture
def registre(tmp_path):
    """Un registre ISOLE, avec son journal de runs a cote — comme a la racine du depot."""
    return tmp_path / "EXPERIMENTS.jsonl"


def _preenregistrer(registre, id_exp="R7", famille=6):
    return experiences.preenregistrer(
        id_exp, "une hypothese falsifiable", "R moyen",
        {"confirmee": "R moyen > 0", "infirmee": "R moyen <= 0"},
        famille_taille=famille, chemin=registre)


# --- A1 / T8 : ce que compte N --------------------------------------------------------

def test_le_compteur_part_de_la_dette_sur_un_registre_vide(registre):
    assert experiences.compteur(registre) == experiences.ESSAIS_INITIAUX


def test_une_hypothese_jamais_mesuree_compte_pour_un_essai(registre):
    _preenregistrer(registre)
    assert experiences.compteur(registre) == experiences.ESSAIS_INITIAUX + 1


def test_dix_candidates_sous_une_hypothese_comptent_pour_dix(registre):
    """Le coeur de A1. Avant l'arbitrage, ce nombre valait 1 quel que soit le lot."""
    _preenregistrer(registre)
    journal = registre.parent / "RUNS.jsonl"
    for i in range(10):
        experiences.enregistrer_run(f"run{i:02d}", "R7", f"c{i}", "aaa", "infirmee",
                                    chemin=journal)
    assert experiences.compteur(registre) == experiences.ESSAIS_INITIAUX + 10


def test_l_hypothese_mesuree_n_est_pas_comptee_deux_fois(registre):
    """Un essai est soit une mesure, soit une hypothese en attente. Jamais les deux."""
    _preenregistrer(registre)
    journal = registre.parent / "RUNS.jsonl"
    experiences.enregistrer_run("run0", "R7", "c", "aaa", "infirmee", chemin=journal)
    # 1 mesure, et l'hypothese R7 n'est plus « en attente » : le total reste a +1.
    assert experiences.compteur(registre) == experiences.ESSAIS_INITIAUX + 1


def test_remesurer_a_l_identique_ne_fabrique_pas_un_essai(registre):
    """Le run_id est deterministe : relancer le meme criblage ne coute pas un cran."""
    _preenregistrer(registre)
    journal = registre.parent / "RUNS.jsonl"
    for _ in range(3):
        experiences.enregistrer_run("meme-run", "R7", "c", "aaa", "infirmee",
                                    chemin=journal)
    assert experiences.compteur(registre) == experiences.ESSAIS_INITIAUX + 1


def test_le_compteur_ne_lit_pas_le_journal_reel_depuis_un_registre_isole(registre):
    """Sans cette isolation, un test compterait les mesures du depot — et le prod, deux fois."""
    _preenregistrer(registre)
    assert not (registre.parent / "RUNS.jsonl").exists()
    assert experiences.compteur(registre) == experiences.ESSAIS_INITIAUX + 1


def test_le_compteur_ne_redescend_jamais(registre):
    """Propriete la plus importante du compteur : monotone, quoi qu'il arrive."""
    valeurs = []
    journal = registre.parent / "RUNS.jsonl"
    for i in range(4):
        _preenregistrer(registre, f"R{i + 10}")
        valeurs.append(experiences.compteur(registre))
        experiences.enregistrer_run(f"r{i}", f"R{i + 10}", "c", "a", "infirmee",
                                    chemin=journal)
        valeurs.append(experiences.compteur(registre))
    assert valeurs == sorted(valeurs)


# --- T10 : le registre dit ce qui a ete mesure -----------------------------------------

def test_marquer_mesuree_pose_le_statut_sans_clore(registre):
    _preenregistrer(registre)
    experiences.marquer_mesuree("R7", "run0", "infirmee", chemin=registre)
    etat = experiences.etat(registre)["R7"]
    assert etat["statut"] == "mesure"
    assert etat["dernier_run"] == "run0"
    # L'hypothese et la regle de decision survivent a la fusion : on peut encore mesurer.
    assert experiences.exiger("R7", registre)["metrique_primaire"] == "R moyen"


def test_marquer_mesuree_ne_touche_pas_une_experience_close(registre):
    _preenregistrer(registre)
    experiences.clore("R7", "infirmee", "motif", chemin=registre)
    assert experiences.marquer_mesuree("R7", "run0", "infirmee", chemin=registre) is None
    assert experiences.etat(registre)["R7"]["statut"] == "clos"


def test_marquer_mesuree_ne_fait_pas_echouer_un_run_sans_preenregistrement(registre):
    """Une mesure qui a tourne ne doit pas etre perdue parce que son registre est muet."""
    assert experiences.marquer_mesuree("inconnue", "run0", "infirmee",
                                       chemin=registre) is None


def test_on_n_amende_plus_un_preenregistrement_apres_la_mesure(registre):
    _preenregistrer(registre)
    experiences.marquer_mesuree("R7", "run0", "infirmee", chemin=registre)
    with pytest.raises(experiences.ProtocoleError, match="on n'amende pas"):
        experiences.amender("R7", "apres coup", chemin=registre, mde_attendu=0.1)


# --- T9 : la famille d'un lot ---------------------------------------------------------

def test_la_p_representative_est_la_pire_des_longueurs_de_bloc():
    """Prendre la meilleure des trois contredirait `bootstrap.stable`, qui les exige toutes."""
    detail = {"S3_bootstrap": [{"p_value": 0.01}, {"p_value": 0.34}, {"p_value": 0.04}]}
    assert pipeline._p_representative(detail) == 0.34


def test_la_p_representative_absente_ne_vaut_pas_zero():
    assert np.isnan(pipeline._p_representative({}))
    assert np.isnan(pipeline._p_representative({"S3_bootstrap": [{"p_value": None}]}))


class _FauxRun:
    def __init__(self, nom, famille):
        self.candidate = type("C", (), {"nom": nom})()
        self.preenregistrement = {"famille_taille": famille}


class _FauxVerdict:
    def __init__(self, nom, famille):
        self.run = _FauxRun(nom, famille)


def _premiers(ps, famille):
    return {f"c{i}": (_FauxVerdict(f"c{i}", famille),
                      {"detail": {"S3_bootstrap": [{"p_value": p}]}})
            for i, p in enumerate(ps)}


def test_la_famille_est_completee_a_la_taille_declaree():
    """Mesurer 2 candidates sur une famille de 6 ne doit pas relacher le seuil des 2."""
    table = pipeline._famille_du_lot(_premiers([0.01, 0.02], famille=6))
    assert len(table) == 6
    assert int(table["m_declare"].iloc[0]) == 6
    assert (table[table["nom"].str.startswith("(non mesuree")]["p_brute"] == 1.0).all()


def test_la_famille_ne_descend_pas_sous_la_taille_du_lot():
    """Un lot plus grand que la famille declaree garde SA taille : jamais de seuil flatteur."""
    table = pipeline._famille_du_lot(_premiers([0.01] * 4, famille=2))
    assert len(table) == 4


def test_une_candidate_sans_p_value_ne_sort_pas_de_la_famille():
    """Elle ne peut pas etre corrigee, mais sa place reste prise dans le m."""
    table = pipeline._famille_du_lot(_premiers([0.01, float("nan")], famille=4))
    assert len(table) == 4
    assert list(table["nom"]).count("c1") == 0


def test_une_famille_sans_aucune_p_value_est_vide():
    assert pipeline._famille_du_lot(_premiers([float("nan")], famille=3)).empty


def test_la_batterie_execute_S1_des_qu_une_famille_est_donnee():
    """T9 en une ligne : sans famille, la porte reste None et CONFIRMEE est inatteignable."""
    from beta.stats import batterie

    trades = pd.DataFrame({"r": np.linspace(-1.0, 2.0, 40)})
    famille = pd.DataFrame({"nom": ["candidate", "autre"], "p_brute": [0.001, 0.9]})

    sans = batterie.evaluer(trades, nom="candidate")
    avec = batterie.evaluer(trades, nom="candidate", famille=famille)
    assert sans["portes"]["S1_benjamini_hochberg"] is None
    assert avec["portes"]["S1_benjamini_hochberg"] is not None


# --- la boucle : ce qu'elle refuse ----------------------------------------------------

def test_la_boucle_refuse_une_hypothese_non_preenregistree(monkeypatch, registre):
    monkeypatch.setattr(experiences, "REGISTRE", registre)
    with pytest.raises(experiences.ProtocoleError, match="non preenregistree"):
        auto._verifier_le_protocole("R99", ["une intention"], "train")


def test_la_boucle_refuse_le_hold_out(monkeypatch, registre):
    monkeypatch.setattr(experiences, "REGISTRE", registre)
    _preenregistrer(registre)
    with pytest.raises(auto.AutoError, match="ne tourne que sur le train"):
        auto._verifier_le_protocole("R7", ["une intention"], "holdout")


def test_la_boucle_refuse_une_famille_non_declaree(monkeypatch, registre):
    """Declarer la famille apres avoir vu les p-values revient a ne pas corriger."""
    monkeypatch.setattr(experiences, "REGISTRE", registre)
    _preenregistrer(registre, famille=None)
    with pytest.raises(auto.AutoError, match="famille_taille"):
        auto._verifier_le_protocole("R7", ["une intention"], "train")


def test_la_boucle_refuse_un_budget_plus_grand_que_la_famille(monkeypatch, registre):
    monkeypatch.setattr(experiences, "REGISTRE", registre)
    _preenregistrer(registre, famille=3)
    with pytest.raises(auto.AutoError, match="famille declaree de 3"):
        auto._verifier_le_protocole("R7", ["x"] * 4, "train")


def test_la_boucle_refuse_au_dela_du_plafond_machine(monkeypatch, registre):
    monkeypatch.setattr(experiences, "REGISTRE", registre)
    _preenregistrer(registre, famille=999)
    with pytest.raises(auto.AutoError, match="plafond"):
        auto._verifier_le_protocole("R7", ["x"] * (auto.BUDGET_MAX + 1), "train")


def test_la_boucle_accepte_un_lot_conforme(monkeypatch, registre):
    monkeypatch.setattr(experiences, "REGISTRE", registre)
    _preenregistrer(registre, famille=6)
    preenr, budget = auto._verifier_le_protocole("R7", ["a", "b", "c"], "train")
    assert budget == 3
    assert preenr["famille_taille"] == 6


def test_lancer_refuse_une_liste_d_intentions_vide():
    with pytest.raises(auto.AutoError, match="n'invente pas"):
        auto.lancer("R7", ["", "   "], paires=("BTC",), timeframe="4h")


def test_la_boucle_ne_preenregistre_jamais(registre):
    """Le verrou central : aucun chemin de `auto` n'ecrit dans le registre d'experiences."""
    source = (RACINE / "beta" / "recherche" / "auto.py").read_text(encoding="utf-8")
    assert "preenregistrer(" not in source
    assert "experiences.amender" not in source


def test_les_modules_ecrits_par_la_boucle_sont_reconnaissables():
    assert auto._nom_module("R7", 1).startswith(auto.PREFIXE)
    assert auto._nom_module("R-7 bis", 12) == "auto_r_7_bis_12"


# --- la boucle : le lot qu'elle crible ------------------------------------------------

def _candidate(nom, hypothese="R7"):
    from beta.moteur.contrats import Candidate
    return Candidate(nom=nom, hypothese=hypothese,
                     signaux=lambda df: df.assign(sens=0)[["sens"]])


def _fausse_ecriture(monkeypatch, refusees=()):
    """Un backend factice : le modele « ecrit » toujours, le sas refuse ce qu'on lui dit."""
    def ecrire_candidate(intention, module, id_exp, **_):
        if module in refusees:
            return {"module": module, "ok": False, "refus": ["sas : look-ahead"]}
        return {"module": module, "ok": True, "refus": [], "code": f"# {intention}"}

    def deposer(code, module, ecraser=False, **_):
        return {"module": module, "ok": True, "depose": True, "chemin": f"/x/{module}.py"}

    monkeypatch.setattr(auto.local, "ecrire_candidate", ecrire_candidate)
    monkeypatch.setattr(auto.depot, "deposer", deposer)


def test_ecrire_le_lot_numerote_les_modules_dans_l_ordre(monkeypatch):
    _fausse_ecriture(monkeypatch)
    rapports = auto.ecrire_le_lot("R7", ["a", "b", "c"])
    assert [r["module"] for r in rapports] == ["auto_r7_01", "auto_r7_02", "auto_r7_03"]


def test_une_intention_refusee_n_interrompt_pas_les_autres(monkeypatch):
    """Sa place dans la famille reste prise : abandonner en route relacherait le seuil."""
    _fausse_ecriture(monkeypatch, refusees={"auto_r7_02"})
    rapports = auto.ecrire_le_lot("R7", ["a", "b", "c"])
    assert [r["depose"] for r in rapports] == [True, False, True]
    assert len(rapports) == 3


def test_une_generation_impossible_est_journalisee_pas_fatale(monkeypatch):
    _fausse_ecriture(monkeypatch)

    def casse(intention, module, id_exp, **_):
        raise auto.local.LocalError("le serveur local ne repond plus")

    monkeypatch.setattr(auto.local, "ecrire_candidate", casse)
    rapports = auto.ecrire_le_lot("R7", ["a", "b"])
    assert len(rapports) == 2
    assert not any(r["depose"] for r in rapports)


def test_le_lot_crible_est_le_lot_ECRIT_pas_toute_l_hypothese(monkeypatch):
    """Le verrou n° 2. Un filtre par hypothese ramenerait aussi les lots precedents.

    Le budget verifie porte sur les intentions de CE lot ; si le lot crible ramasse les
    candidates deja presentes, les deux nombres divergent des le deuxieme lot.
    """
    monkeypatch.setattr(auto.registre, "charger", lambda m: _candidate(m))
    rapports = [{"module": "auto_r7_01", "depose": True},
                {"module": "auto_r7_02", "depose": True}]
    lot = auto._lot_ecrit(rapports, "R7")
    assert sorted(lot) == ["auto_r7_01", "auto_r7_02"]


def test_une_candidate_non_deposee_n_entre_pas_dans_le_lot(monkeypatch):
    monkeypatch.setattr(auto.registre, "charger", lambda m: _candidate(m))
    lot = auto._lot_ecrit([{"module": "auto_r7_01", "depose": False},
                           {"module": "auto_r7_02", "depose": True}], "R7")
    assert sorted(lot) == ["auto_r7_02"]


def test_une_candidate_qui_declare_une_AUTRE_hypothese_est_ecartee(monkeypatch):
    """Le modele a le droit de se tromper de `hypothese=` ; le banc n'a pas le droit de
    la mesurer sous une famille qui n'est pas la sienne."""
    monkeypatch.setattr(auto.registre, "charger",
                        lambda m: _candidate(m, "R2" if m.endswith("02") else "R7"))
    lot = auto._lot_ecrit([{"module": "auto_r7_01", "depose": True},
                           {"module": "auto_r7_02", "depose": True}], "R7")
    assert sorted(lot) == ["auto_r7_01"]


def test_une_candidate_deposee_mais_illisible_n_annule_pas_le_lot(monkeypatch):
    def charger(module):
        if module.endswith("01"):
            raise RuntimeError("SyntaxError dans le fichier depose")
        return _candidate(module)

    monkeypatch.setattr(auto.registre, "charger", charger)
    lot = auto._lot_ecrit([{"module": "auto_r7_01", "depose": True},
                           {"module": "auto_r7_02", "depose": True}], "R7")
    assert sorted(lot) == ["auto_r7_02"]


def test_lancer_passe_a_cribler_exactement_le_lot_ecrit(monkeypatch, registre):
    """Le chemin nominal, de bout en bout, sans modele local ni donnees."""
    monkeypatch.setattr(experiences, "REGISTRE", registre)
    _preenregistrer(registre, famille=6)
    _fausse_ecriture(monkeypatch)
    monkeypatch.setattr(auto.registre, "charger", lambda m: _candidate(m))

    vu = {}

    def faux_cribler(lot, **options):
        vu["lot"] = sorted(lot)
        vu["options"] = options
        return dict.fromkeys(lot, "verdict")

    monkeypatch.setattr(auto.pipeline, "cribler", faux_cribler)
    rapport = auto.lancer("R7", ["a", "b"], paires=("BTC",), timeframe="4h")

    assert vu["lot"] == ["auto_r7_01", "auto_r7_02"]
    assert vu["options"]["split"] == "train"
    assert rapport["lot"] == ["auto_r7_01", "auto_r7_02"]
    assert rapport["famille_declaree"] == 6


def test_lancer_ne_crible_rien_si_aucune_candidate_n_a_ete_deposee(monkeypatch, registre):
    monkeypatch.setattr(experiences, "REGISTRE", registre)
    _preenregistrer(registre, famille=6)
    _fausse_ecriture(monkeypatch, refusees={"auto_r7_01", "auto_r7_02"})
    monkeypatch.setattr(auto.pipeline, "cribler",
                        lambda *a, **k: pytest.fail("rien ne doit etre crible"))
    rapport = auto.lancer("R7", ["a", "b"], paires=("BTC",), timeframe="4h")
    assert rapport["verdicts"] == {}
    assert "rien n'a ete mesure" in rapport["motif"]


# --- le registre relit le disque -------------------------------------------------------

def test_charger_relit_le_fichier_apres_un_depot_ecrase():
    """Un module deja importe garderait son ANCIEN code : verdict faux, et signe.

    `ecraser=True` est le defaut de la boucle, donc ce cas arrive a chaque relance.
    """
    from beta.moteur import registre as reg

    dossier = RACINE / "beta" / "candidates"
    module = "_essai_rechargement"
    fichier = dossier / f"{module}.py"
    gabarit = """from beta.moteur.contrats import Candidate
def creer():
    return Candidate(nom="{nom}", hypothese="R7",
                     signaux=lambda df: df.assign(sens=0)[["sens"]])
"""
    try:
        fichier.write_text(gabarit.format(nom="version_1"), encoding="utf-8")
        assert reg.charger(module).nom == "version_1"
        fichier.write_text(gabarit.format(nom="version_2"), encoding="utf-8")
        assert reg.charger(module).nom == "version_2"
    finally:
        fichier.unlink(missing_ok=True)
        sys.modules.pop(f"{reg.PAQUET}.{module}", None)


# --- l'etage gratuit -------------------------------------------------------------------

def test_proposer_n_avance_pas_le_compteur(monkeypatch, tmp_path):
    """Noter des idees est gratuit. C'est ce qui permet a une machine d'en proposer vingt."""
    from beta.protocole import idees

    boite = tmp_path / "IDEES.jsonl"
    registre = tmp_path / "EXPERIMENTS.jsonl"
    monkeypatch.setattr(idees, "REGISTRE", boite)
    monkeypatch.setattr(auto.local, "detecter", lambda backend: ("ollama", "faux:7b"))
    monkeypatch.setattr(auto.local, "repondre", lambda *a, **k: (
        "1. apres trois bougies de meme sens, le retour a la moyenne a un R moyen positif\n"
        "- le funding extreme precede un renversement mesurable en R sur 24 heures\n"
        "trop court\n"))

    avant = experiences.compteur(registre)
    notees = auto.proposer("un sujet", 5)
    assert len(notees) == 2                       # la ligne trop courte est ecartee
    assert experiences.compteur(registre) == avant
    assert all(i["etat"] == idees.NOUVELLE for i in idees.lister(chemin=boite))


def test_proposer_nettoie_les_puces_du_modele(monkeypatch, tmp_path):
    from beta.protocole import idees

    monkeypatch.setattr(idees, "REGISTRE", tmp_path / "IDEES.jsonl")
    monkeypatch.setattr(auto.local, "detecter", lambda backend: ("ollama", "faux:7b"))
    monkeypatch.setattr(auto.local, "repondre", lambda *a, **k:
                        "* une hypothese falsifiable et suffisamment longue pour compter\n")
    assert auto.proposer("sujet", 1)[0]["texte"].startswith("une hypothese")


def test_le_journal_des_idees_n_est_pas_le_registre_d_experiences(tmp_path):
    """Deux fichiers, deux couts. Les confondre rendrait la proposition automatique payante."""
    from beta.protocole import idees

    assert idees.REGISTRE != experiences.REGISTRE


# --- la mesure hors pipeline paie, mais une seule fois --------------------------------

def _module_mesurer():
    import importlib.util
    spec = importlib.util.spec_from_file_location("scripts_mesurer",
                                                  RACINE / "scripts" / "mesurer.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_le_run_id_d_une_mesure_ne_depend_pas_du_jour():
    """Un compteur qui monte parce que le temps passe ne mesure plus rien.

    La premiere version datait l'identifiant, donc relancer mesurer.py le lendemain sans
    avoir rien touche durcissait S1/S2 pour toutes les hypotheses suivantes.
    """
    mesurer = _module_mesurer()
    empreinte = "aaaaaaaaaaaa"
    assert mesurer._run_id("R1", empreinte) == mesurer._run_id("R1", empreinte)
    assert mesurer._run_id("R1", empreinte) != mesurer._run_id("R1", "bbbbbbbbbbbb")
    assert mesurer._run_id("R1", empreinte) != mesurer._run_id("R6", empreinte)


def test_l_empreinte_d_une_mesure_porte_sur_son_code():
    """Meme convention que Candidate.empreinte : c'est le CODE qui identifie un test."""
    mesurer = _module_mesurer()
    nom, empreinte = mesurer._identite(mesurer.MESURES["R1"])
    assert nom == "r1_trailing"
    assert len(empreinte) == 12
    assert empreinte != mesurer._identite(mesurer.MESURES["R6"])[1]
