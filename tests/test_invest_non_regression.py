"""Non-regression du dashboard pendant l'ajout de l'onglet « Test invest » (C2, Jonas 20/10).

Ecrit AVANT toute modification du code partage, et vert sur l'etat du 20/10 (526973d) : il fige
ce qui existait — les 7 onglets et leur ordre, chaque id du HTML, l'ordre des scripts, la bascule
des onglets, le chargement initial et les routes du serveur. L'onglet ajoute ne peut que
s'ajouter : s'il retire ou deplace quoi que ce soit d'existant, ce fichier echoue.
"""

import re
from pathlib import Path

from beta.rapport import serveur

WEB = Path(serveur.__file__).resolve().parent / "web"

ONGLETS_EXISTANTS = ["strategie", "forward", "candidates", "comparaison", "atelier", "lake",
                     "protocole"]

IDS_EXISTANTS = {
    "atelier-code", "atelier-ecraser", "atelier-essais", "atelier-hypothese",
    "atelier-intention", "atelier-liste", "atelier-message", "atelier-modele", "atelier-modeles",
    "atelier-module", "atelier-rapport", "badge-lecture-seule", "carte-lake", "carte-protocole",
    "carte-verdict", "comparaison-courbes", "comparaison-entete", "comparaison-legende",
    "comparaison-matrice", "comparaison-reserves", "comparaison-s7", "comparaison-tableau",
    "distribution", "equity", "experiences", "fiche-action-message", "fiche-annees",
    "fiche-annees-graph", "fiche-bootstrap", "fiche-cone", "fiche-cpcv", "fiche-dd",
    "fiche-detail", "fiche-distribution", "fiche-entete", "fiche-equity", "fiche-explication",
    "fiche-liste", "fiche-mc-chiffres", "fiche-paires", "fiche-raisons", "fiche-sens",
    "fiche-syn-chiffres", "fiche-wf-chiffres", "fiche-wf-graph", "forward-allocation",
    "forward-execution", "forward-genere", "forward-indicateurs", "forward-ordres",
    "forward-paper", "forward-paper-legende", "forward-positions", "forward-suivi",
    "forward-suivi-legende", "forward-voies", "holdout", "idee-form", "idee-message",
    "idee-source", "idee-texte", "idees", "kpis", "lien-vps", "onglet-atelier",
    "onglet-candidates", "onglet-comparaison", "onglet-forward", "onglet-lake",
    "onglet-protocole", "onglet-strategie", "par-paire", "par-sens", "par-strategie", "portee",
    "rafraichir", "raisons-rejet", "raisons-sortie", "series",
}

SCRIPTS_EXISTANTS = ["fiche.js", "atelier.js", "comparaison.js", "forward.js", "app.js"]

ROUTES_EXISTANTES = {"/api/atelier", "/api/candidate", "/api/comparaison", "/api/forward",
                     "/api/forward/direct", "/api/idees", "/api/lake", "/api/protocole",
                     "/api/run", "/api/runs", "/api/strategie"}


def _html() -> str:
    return (WEB / "index.html").read_text(encoding="utf-8")


def _app() -> str:
    return (WEB / "app.js").read_text(encoding="utf-8")


def test_les_7_onglets_existants_restent_en_tete_et_dans_l_ordre():
    onglets = re.findall(r'data-onglet="([^"]+)"', _html())
    assert onglets[:7] == ONGLETS_EXISTANTS


def test_le_premier_onglet_reste_celui_qui_est_actif_au_chargement():
    actif = re.search(r'class="tab is-active" data-onglet="([^"]+)"', _html())
    assert actif and actif.group(1) == "strategie"


def test_aucun_id_existant_ne_disparait():
    assert IDS_EXISTANTS <= set(re.findall(r'id="([^"]+)"', _html()))


def test_scripts_existants_dans_le_meme_ordre_et_app_js_en_dernier():
    scripts = re.findall(r'<script src="([^"]+)"', _html())
    assert [s for s in scripts if s in SCRIPTS_EXISTANTS] == SCRIPTS_EXISTANTS
    assert scripts[-1] == "app.js"


def test_la_bascule_connait_toujours_les_7_onglets_dans_l_ordre():
    liste = re.search(r'\[([^\]]*)\]\s*\.forEach\(\(o\) => \(\$\("#onglet-" \+ o\)', _app())
    assert liste, "liste des onglets d'ongletActif introuvable"
    noms = re.findall(r'"([a-z]+)"', liste.group(1))
    assert noms[:7] == ONGLETS_EXISTANTS


def test_le_chargement_initial_appelle_toujours_les_memes_onglets():
    corps = re.search(r"async function charger\(\) \{(.*?)\n\}", _app(), re.S).group(1)
    for appel in ("FORWARD.charger()", "rendreStrategie()", "rendreLake()",
                  "rendreProtocole()", "FICHE.charger()", "ATELIER.charger()",
                  "COMPARAISON.charger()", "chargerIdees()"):
        assert appel in corps


def test_les_routes_existantes_sont_toutes_la():
    assert ROUTES_EXISTANTES <= set(serveur.ROUTES)


def test_le_vps_reste_en_lecture_seule_pour_les_post():
    source = Path(serveur.__file__).read_text(encoding="utf-8")
    assert 'serveur en lecture seule (VPS)"}, 403' in source
