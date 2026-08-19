"""Les trois ponts : freqtrade (M3), MCP (P2/P3), dashboard (P1).

Ce que ces tests verifient avant tout, c'est ce que les ponts REFUSENT. Un pont qui ouvre
un chemin que le protocole ferme ailleurs annule le protocole entier.
"""

from __future__ import annotations

import json

import pytest

from beta.moteur import pont_freqtrade
from beta.moteur.contrats import Candidate, ContratError, Run, Verdict
from beta.protocole import experiences
from beta.rapport import actions


@pytest.fixture
def run_jetable(tmp_path, monkeypatch):
    monkeypatch.setattr(experiences, "REGISTRE", tmp_path / "exp.jsonl")
    experiences.preenregistrer("P0", "hypothese de test", "R moyen", {"confirmee": "x"})
    candidate = Candidate(nom="pont_test", hypothese="P0",
                          signaux=lambda df: df, parametres={"k": 1})
    return Run(candidate=candidate, paires=("BTC",), timeframe="4h")


# --- M3 pont freqtrade -----------------------------------------------------------------

def test_le_pont_refuse_une_candidate_qui_n_a_pas_survecu(run_jetable, tmp_path):
    verdict = Verdict(run=run_jetable, issue="infirmee",
                      portes={"S8_buy_and_hold": False})
    with pytest.raises(ContratError, match="n'a pas survecu"):
        pont_freqtrade.exporter(run_jetable, "r2_mean_reversion", verdict,
                                dossier=tmp_path)


def test_le_pont_accepte_de_forcer_en_le_disant(run_jetable, tmp_path):
    verdict = Verdict(run=run_jetable, issue="infirmee",
                      portes={"S8_buy_and_hold": False})
    chemin = pont_freqtrade.exporter(run_jetable, "r2_mean_reversion", verdict,
                                     dossier=tmp_path, forcer=True)
    assert chemin.exists()


def test_la_strategie_exportee_est_du_python_valide(run_jetable, tmp_path):
    import ast
    chemin = pont_freqtrade.exporter(run_jetable, "r2_mean_reversion", dossier=tmp_path)
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    classes = [n.name for n in ast.walk(arbre) if isinstance(n, ast.ClassDef)]
    assert classes == ["BetaPontTest"]


def test_la_commande_freqtrade_porte_les_drapeaux_imposes(run_jetable, tmp_path):
    chemin = pont_freqtrade.exporter(run_jetable, "r2_mean_reversion", dossier=tmp_path)
    argv = pont_freqtrade.commande(run_jetable, chemin)
    for drapeau in pont_freqtrade.DRAPEAUX_IMPOSES:
        assert drapeau in argv
    assert "--enable-protections" in argv        # sans elles, on mesure l'irrealisable


# --- P2/P3 serveur MCP -----------------------------------------------------------------

def test_le_serveur_mcp_annonce_ses_outils():
    from beta.mcp import serveur
    reponse = serveur.traiter({"method": "tools/list"})
    noms = {outil["name"] for outil in reponse["tools"]}
    assert noms == {"beta_data_catalog", "beta_load_ohlcv", "beta_results", "beta_ideas",
                    "beta_suggest_idea", "beta_register_edge", "beta_submit_strategy",
                    "beta_run_backtest", "beta_publish"}


def test_l_outil_gratuit_et_l_outil_couteux_se_distinguent_dans_leur_description():
    """Un agent choisit son outil sur sa description : elle doit dire ce que ca coute.

    `beta_suggest_idea` est gratuit, `beta_register_edge` avance le compteur d'essais donc
    durcit le seuil de toutes les hypotheses. Confondre les deux fait preenregistrer dix
    idees pour en mesurer une — et ruine la batterie pour les neuf autres.
    """
    from beta.mcp import serveur
    outils = {o["name"]: o["description"]
              for o in serveur.traiter({"method": "tools/list"})["tools"]}
    assert "GRATUIT" in outils["beta_suggest_idea"]
    assert "compteur" in outils["beta_register_edge"]
    assert "beta_suggest_idea" in outils["beta_register_edge"]


def test_chaque_outil_mcp_declare_un_schema():
    from beta.mcp import serveur
    for outil in serveur.traiter({"method": "tools/list"})["tools"]:
        assert outil["inputSchema"]["type"] == "object"
        assert outil["description"]


def test_le_mcp_refuse_un_backtest_sans_preenregistrement(tmp_path, monkeypatch):
    """P3, le garde-fou du pont. Sans lui, un agent produirait mille faux gagnants."""
    from beta.mcp import serveur
    monkeypatch.setattr(experiences, "REGISTRE", tmp_path / "vide.jsonl")
    with pytest.raises(experiences.ProtocoleError, match="non preenregistree"):
        serveur.traiter({"method": "tools/call",
                         "params": {"name": "beta_run_backtest",
                                    "arguments": {"module": "r2_mean_reversion"}}})


def test_le_mcp_refuse_un_nom_de_module_douteux():
    from beta.mcp import serveur
    with pytest.raises(ValueError, match="nom de module invalide"):
        serveur.traiter({"method": "tools/call",
                         "params": {"name": "beta_submit_strategy",
                                    "arguments": {"module": "../../evade", "code": "x"}}})


def test_le_mcp_refuse_une_methode_inconnue():
    from beta.mcp import serveur
    with pytest.raises(ValueError, match="non supportee"):
        serveur.traiter({"method": "tools/destroy"})


def test_la_boucle_stdio_rend_une_erreur_plutot_que_de_mourir(capsys):
    import io

    from beta.mcp import serveur
    entree = io.StringIO(json.dumps({"jsonrpc": "2.0", "id": 1,
                                     "method": "tools/inexistant"}) + "\n")
    serveur.servir(entree=entree)
    reponse = json.loads(capsys.readouterr().out.strip())
    assert reponse["error"]["code"] == -32000


def test_le_serveur_mcp_ecrit_en_utf8_a_travers_un_vrai_tube():
    """Regression du 19/08 : sous Windows, stdout sortait en cp1252 et le client echouait.

    Le seul test du fichier qui lance un vrai sous-processus. Il coute deux secondes, et
    c'est le prix de la seule chose que les autres ne peuvent pas voir : `traiter()` rend
    des objets Python, jamais des octets. Le defaut ne vivait pas dans la logique du
    serveur, il vivait dans son branchement — un tiret cadratin de description d'outil
    sortait en 0x97, et le client n'obtenait jamais la liste des outils.

    L'environnement est transmis TEL QUEL, sans PYTHONIOENCODING : c'est le serveur qui
    doit se corriger, pas la configuration de l'appelant.
    """
    import subprocess
    import sys
    from pathlib import Path

    racine = Path(__file__).resolve().parents[1]
    requetes = "\n".join(json.dumps(r) for r in (
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})) + "\n"
    # Tube en OCTETS des deux cotes : c'est l'encodage de la reponse qui est teste, donc
    # laisser subprocess decoder a notre place viderait le test de son objet.
    fini = subprocess.run([sys.executable, "-m", "beta.mcp.serveur"],
                          input=requetes.encode("utf-8"), capture_output=True,
                          cwd=str(racine), timeout=60)

    lignes = fini.stdout.decode("utf-8", errors="strict").splitlines()   # strict : le test
    reponses = [json.loads(ligne) for ligne in lignes if ligne.strip()]  # EST le decodage
    assert reponses[0]["result"]["serverInfo"]["name"] == "beta"
    descriptions = " ".join(o["description"] for o in reponses[1]["result"]["tools"])
    assert any(ord(c) > 127 for c in descriptions), \
        "plus aucune description non-ASCII : le test ne prouve plus rien"


# --- P1 actions du dashboard -----------------------------------------------------------

def test_nettoyer_retire_ce_qui_atteindrait_un_shell():
    sale = 'candidate" && del /f C:\\ | echo $(whoami) > out'
    propre = actions.nettoyer(sale)
    for interdit in ('"', "&", "|", ">", "$", "\\"):
        assert interdit not in propre


def test_le_prompt_porte_le_verdict_et_ses_portes_echouees():
    prompt = actions.prompt_du_run({
        "run_id": "abc123", "candidate": "mean_reversion_z", "experience": "R2",
        "issue": "infirmee", "split": "train", "n_essais_cumules": 36,
        "metriques": {"n": 790, "r_moyen": -0.23, "mde_r": 0.145},
        "portes_echouees": ["S8_buy_and_hold"], "portes_non_executees": [],
        "reserves": ["ne bat pas le hold"]})
    assert "infirmee" in prompt
    assert "S8_buy_and_hold" in prompt
    assert "ne bat pas le hold" in prompt


def test_une_action_hors_liste_blanche_est_refusee():
    with pytest.raises(actions.ActionError, match="action refusee"):
        actions.executer("rm", {"run_id": "abc"})


def test_le_prompt_reste_borne_meme_avec_des_reserves_immenses():
    prompt = actions.prompt_du_run({"run_id": "a", "reserves": ["x" * 5000]})
    assert len(prompt) <= actions.PROMPT_MAX
