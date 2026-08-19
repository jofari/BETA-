"""L'atelier : ce qu'il REFUSE, et pourquoi la moitie des refus ne peut pas etre statique.

Ces tests sont ecrits a l'envers de l'habitude : on ne verifie pas surtout qu'une bonne
candidate passe (c'est le cas facile), on verifie qu'une mauvaise est arretee, et par le
bon etage. Un atelier qui laisserait entrer une candidate lisant le futur produirait des
verdicts que rien ne distinguerait d'un vrai — c'est la seule panne du projet qui ne se
voit jamais.

La paire de tests qui porte tout le module : `test_le_sas_ne_voit_pas_une_normalisation_
globale` et `test_l_epreuve_attrape_la_normalisation_globale_que_le_sas_a_laissee_passer`.
Elles disent la meme chose depuis les deux cotes — une liste de motifs interdits attrape ce
qu'elle connait, la causalite attrape ce qu'on n'avait pas prevu.
"""

from __future__ import annotations

import json

import pytest

from beta.atelier import depot, gabarit, local, sas

# --- materiel -------------------------------------------------------------------------------------

CORRECTE = '''"""Candidate de test, causale."""

from __future__ import annotations

import pandas as pd

from beta.moteur.contrats import Candidate

FENETRE = 20


def signaux(df: pd.DataFrame, fenetre: int = FENETRE) -> pd.DataFrame:
    moyenne = df["close"].rolling(fenetre, min_periods=fenetre).mean()
    sens = pd.Series(0, index=df.index, dtype=int)
    sens[df["close"] > moyenne] = 1
    sens[df["close"] < moyenne] = -1
    return pd.DataFrame({"sens": sens})


def creer() -> Candidate:
    return Candidate(nom="test_causale", hypothese="R2", signaux=signaux)
'''

# Le futur lu SANS aucun motif interdit : la normalisation depend du maximum de la serie
# entiere, donc de bougies posterieures a chaque ligne qu'elle decide.
NORMALISATION_GLOBALE = CORRECTE.replace(
    'moyenne = df["close"].rolling(fenetre, min_periods=fenetre).mean()',
    'moyenne = df["close"].mean()')


def _remplacer_corps(code: str, corps: str) -> str:
    """Reecrit le corps de `signaux` sans toucher au reste du fichier."""
    avant, _, apres = code.partition("def signaux")
    _, _, fin = apres.partition("def creer")
    return f"{avant}def signaux(df, fenetre=FENETRE):\n{corps}\n\ndef creer{fin}"


# --- sas : le controle statique -------------------------------------------------------------------

def test_une_candidate_conforme_passe_le_sas():
    assert sas.controler(CORRECTE, "test").ok


def test_le_sas_refuse_un_decalage_negatif():
    code = CORRECTE.replace('.rolling(fenetre, min_periods=fenetre).mean()', '.shift(-1)')
    rapport = sas.controler(code, "triche")
    assert not rapport.ok
    assert any("NEGATIF" in r for r in rapport.refus)


def test_le_sas_refuse_une_fenetre_centree():
    code = CORRECTE.replace("min_periods=fenetre", "center=True")
    assert any("center=True" in r for r in sas.controler(code, "triche").refus)


def test_le_sas_refuse_de_charger_ses_propres_donnees():
    """L'import le plus dangereux du lot : une candidate qui va chercher sa serie."""
    code = CORRECTE.replace("import pandas as pd",
                            "import pandas as pd\nfrom beta.lake import lecture")
    refus = sas.controler(code, "triche").refus
    assert any("look-ahead par construction" in r for r in refus)


@pytest.mark.parametrize("module", ["os", "subprocess", "urllib", "random", "datetime"])
def test_le_sas_refuse_les_imports_hors_liste_blanche(module):
    code = CORRECTE.replace("import pandas as pd", f"import {module}\nimport pandas as pd")
    assert not sas.controler(code, "triche").ok


def test_le_sas_laisse_passer_numpy_et_le_contrat():
    code = CORRECTE.replace("import pandas as pd", "import numpy as np\nimport pandas as pd")
    assert sas.controler(code, "test").ok


def test_le_sas_refuse_un_fichier_sans_creer():
    code = CORRECTE.replace("def creer()", "def fabriquer()")
    assert any("creer()" in r for r in sas.controler(code, "triche").refus)


def test_le_sas_refuse_ce_qui_s_execute_a_l_import():
    code = CORRECTE + '\nprint("effet de bord")\n'
    assert any("a l'import" in r for r in sas.controler(code, "triche").refus)


def test_le_sas_refuse_un_etat_partage():
    code = CORRECTE.replace("    moyenne =", "    global FENETRE\n    moyenne =")
    assert any("fonction pure" in r for r in sas.controler(code, "triche").refus)


def test_le_sas_refuse_du_python_invalide():
    assert any("Python invalide" in r
               for r in sas.controler("def signaux(df:\n  pass\n" * 10, "casse").refus)


def test_le_sas_signale_un_indice_negatif_sans_le_refuser():
    """Reserve et non refus : legitime dans une fonction auxiliaire, pas dans `signaux`."""
    code = CORRECTE.replace('df["close"] > moyenne', 'df["close"] > moyenne.iloc[-1]')
    rapport = sas.controler(code, "suspect")
    assert rapport.ok
    assert any("indice negatif" in r for r in rapport.reserves)


def test_le_sas_ne_voit_pas_une_normalisation_globale():
    """La moitie du couple. Le sas PASSE — et c'est normal, aucun motif n'est interdit ici.

    Ce test existe pour que la limite du controle statique soit ecrite quelque part plutot
    que supposee : si un jour le sas se met a refuser ce code, c'est ce test qui le dira.
    """
    assert sas.controler(NORMALISATION_GLOBALE, "sournoise").ok


def test_l_hypothese_se_lit_sans_importer():
    assert sas.hypothese_du_code(CORRECTE) == "R2"
    assert sas.hypothese_du_code("def creer(): pass") == ""


# --- depot : la validation complete ---------------------------------------------------------------

def test_l_epreuve_attrape_la_normalisation_globale_que_le_sas_a_laissee_passer():
    """L'autre moitie du couple, et la raison d'etre de l'atelier.

    Lent (il lance un sous-processus sur de vraies bougies) et non negociable : c'est le
    seul test du projet qui prouve qu'un look-ahead imprevu est arrete.
    """
    rapport = depot.valider(NORMALISATION_GLOBALE, "zz_test_sournoise")
    assert not rapport["ok"]
    assert any("CAUSALITE" in r for r in rapport["refus"])


def test_une_candidate_causale_passe_les_deux_etages():
    rapport = depot.valider(CORRECTE, "zz_test_causale")
    assert rapport["ok"], rapport["refus"]
    assert rapport["mesures"]["n_signaux"] > 0


def test_la_validation_n_ecrit_jamais_la_cible():
    """Une nouvelle version refusee ne doit pas detruire la candidate deja en place."""
    avant = depot.chemin("r2_mean_reversion").read_text(encoding="utf-8")
    depot.valider(NORMALISATION_GLOBALE, "r2_mean_reversion")
    assert depot.chemin("r2_mean_reversion").read_text(encoding="utf-8") == avant


def test_le_depot_refuse_d_ecraser_sans_qu_on_le_demande():
    with pytest.raises(depot.DepotError, match="existe deja"):
        depot.deposer(CORRECTE, "r2_mean_reversion")


@pytest.mark.parametrize("module", ["../../evade", "Majuscule", "x", "avec-tiret", ""])
def test_le_depot_refuse_un_nom_de_module_douteux(module):
    with pytest.raises(depot.DepotError, match="invalide"):
        depot.verifier_nom(module)


def test_une_candidate_refusee_ne_laisse_aucun_fichier(tmp_path, monkeypatch):
    monkeypatch.setattr(depot, "DOSSIER", tmp_path)
    rapport = depot.deposer("import os\n" + CORRECTE, "zz_test_sale")
    assert not rapport["ok"]
    assert list(tmp_path.glob("*.py")) == []


def test_l_essai_temporaire_est_invisible_du_registre():
    """Un essai oublie par un plantage ne doit jamais entrer dans un criblage."""
    from beta.moteur import registre
    assert depot.PREFIXE_ESSAI.startswith("_")
    assert all(not nom.startswith("_") for nom in registre.toutes())


def test_une_hypothese_non_preenregistree_est_une_reserve_pas_un_refus():
    """Le verrou est dans `contrats.Run`, qui refuse de MESURER.

    Le doubler ici empecherait d'ecrire une candidate avant son preenregistrement, et ce
    n'est pas l'interdit : l'interdit porte sur la mesure."""
    code = CORRECTE.replace('hypothese="R2"', 'hypothese="ZZ_jamais_ecrite"')
    reserves = depot.reserves_de_protocole(code)
    assert any("PAS preenregistree" in r for r in reserves)


# --- epreuve : le sous-processus ------------------------------------------------------------------

def test_une_boucle_sans_fin_est_tuee_par_le_chronometre():
    """Sans le sous-processus, ce code figerait le dashboard jusqu'au redemarrage.

    L'essai s'ecrit dans le VRAI `beta/candidates/` — c'est la seule facon pour le
    sous-processus de l'importer, et c'est aussi le chemin reel. Le prefixe `_essai_` le
    rend invisible du registre, et `depot.valider` le retire dans son `finally`.
    """
    sans_fin = _remplacer_corps(CORRECTE, "    while True:\n        pass\n")
    rapport = depot.valider(sans_fin, "zz_test_boucle", timeout=8)
    assert not rapport["ok"]
    assert any("rendu la main" in r for r in rapport["refus"]), rapport["refus"]
    assert not list(depot.DOSSIER.glob(f"{depot.PREFIXE_ESSAI}*.py"))


def test_l_epreuve_rend_toujours_un_rapport_meme_pour_un_module_inexistant():
    from beta.atelier import epreuve
    rapport = epreuve.lancer("zz_module_qui_n_existe_pas", timeout=60)
    assert rapport["ok"] is False
    assert rapport["refus"]


# --- gabarit --------------------------------------------------------------------------------------

def test_le_gabarit_est_du_python_valide_et_passe_le_sas():
    code = gabarit.ecrire("r9_test", "R9")
    assert sas.controler(code, "r9_test").ok


def test_le_gabarit_ne_signale_rien_donc_l_epreuve_le_refuse():
    """Voulu : un squelette qui passe est un squelette qu'on mesure par distraction."""
    rapport = depot.valider(gabarit.ecrire("zz_test_gabarit", "R2"), "zz_test_gabarit")
    assert not rapport["ok"]
    assert any("aucun signal" in r for r in rapport["refus"])


def test_l_exemple_joint_au_prompt_est_lui_meme_conforme():
    """Un exemple non conforme apprendrait au modele exactement ce qu'on refuse ensuite."""
    assert sas.controler(gabarit.EXEMPLE, "exemple").ok


# --- modele local ---------------------------------------------------------------------------------

def test_le_code_s_extrait_d_un_bloc_etiquete():
    reponse = "Voici la candidate :\n```python\nimport pandas as pd\n```\nBonne chance !"
    assert local.extraire_code(reponse).strip() == "import pandas as pd"


def test_le_code_s_extrait_d_un_bloc_nu():
    assert "def creer" in local.extraire_code("```\ndef creer():\n    pass\n```")


def test_une_reponse_sans_code_leve_un_message_clair():
    with pytest.raises(local.LocalError, match="aucun bloc de code"):
        local.extraire_code("Je ne peux pas ecrire de strategie de trading.")


def test_un_modele_injoignable_dit_quoi_faire(monkeypatch):
    """Le cas le plus frequent : Ollama eteint. Il doit rendre une consigne, pas une trace."""
    def refuser(*_args, **_kwargs):
        raise local.LocalError("connexion refusee")
    monkeypatch.setattr(local, "modeles", refuser)
    with pytest.raises(local.LocalError, match="ollama serve"):
        local.detecter("auto")


def test_les_serveurs_indisponibles_sont_une_information_pas_une_exception(monkeypatch):
    monkeypatch.setattr(local, "modeles",
                        lambda _b: (_ for _ in ()).throw(local.LocalError("eteint")))
    for serveur in local.disponibles():
        assert serveur["disponible"] is False
        assert serveur["detail"]


def test_la_consigne_interdit_explicitement_les_trois_formes_de_look_ahead():
    """Le prompt doit nommer ce que le sas refuse : un modele corrige ce qu'on lui dit."""
    consigne = local.CONSIGNE.format(exemple="")
    for interdit in ("shift(-1)", "center=True", "bfill", "beta.lake"):
        assert interdit in consigne


# --- pont dashboard -------------------------------------------------------------------------------

def test_le_dashboard_refuse_un_geste_hors_liste_blanche():
    from beta.rapport import atelier
    with pytest.raises(atelier.AtelierError, match="geste refuse"):
        atelier.executer("supprimer_tout", {"module": "r2_mean_reversion"})


def test_le_dashboard_refuse_un_code_demesure():
    from beta.rapport import atelier
    with pytest.raises(atelier.AtelierError, match="trop long"):
        atelier.executer("valider", {"module": "zz_test_gros",
                                     "code": "x" * (atelier.MAX_CODE + 1)})


def test_le_dashboard_refuse_une_generation_sans_intention():
    from beta.rapport import atelier
    with pytest.raises(atelier.AtelierError, match="une ou deux phrases"):
        atelier.executer("generer", {"module": "zz_test_vide", "intention": "  "})


# --- compteur de runs -----------------------------------------------------------------------------

def test_le_journal_des_runs_compte_les_mesures_pas_les_hypotheses(tmp_path):
    """L'ecart que l'atelier rend possible : dix candidates, une seule hypothese."""
    from beta.protocole import experiences

    journal = tmp_path / "RUNS.jsonl"
    for n in range(3):
        experiences.enregistrer_run(f"run{n}", "R7", f"candidate{n}", f"emp{n}",
                                    chemin=journal)
    experiences.enregistrer_run("run0", "R7", "candidate0", "emp0", chemin=journal)
    assert experiences.compteur_runs(journal) == 3          # run0 deux fois = un seul run
    assert len(experiences.runs_journalises(journal)) == 4  # mais les 4 lignes sont la


def test_un_journal_illisible_ne_tue_pas_le_run(tmp_path, caplog):
    from beta.protocole import experiences

    dossier = tmp_path / "occupe"
    dossier.mkdir()
    experiences.enregistrer_run("r", "R7", "c", "e", chemin=dossier)  # ecrit sur un dossier
    assert "non journalise" in caplog.text.lower()


def test_le_journal_des_runs_vit_hors_de_data():
    """`data/` est jetable : un compteur qu'un nettoyage remet a zero ment."""
    from beta import config
    from beta.protocole import experiences
    assert config.DATA not in experiences.JOURNAL_RUNS.parents


def test_le_rapport_de_validation_est_serialisable_en_json():
    """Le dashboard le renvoie tel quel : un objet non serialisable ferait page blanche."""
    json.dumps(depot.valider(CORRECTE, "zz_test_json"), default=str)
