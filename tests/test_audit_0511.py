"""Audit du 05/11/2026 : points 5 (verdict sans mesure), 6 (POST cross-site), 7 (CRLF)."""
from __future__ import annotations

import http.client
import json
import pathlib
import threading

import pytest

from beta import config
from beta.mcp import serveur as mcp
from beta.protocole import experiences
from beta.rapport import serveur


# --- point 5 : beta_publish ne clot que ce que le moteur a mesure -------------------------

@pytest.fixture
def registre(tmp_path, monkeypatch):
    monkeypatch.setattr(experiences, "REGISTRE", tmp_path / "EXPERIMENTS.jsonl")
    monkeypatch.setattr(experiences, "JOURNAL_RUNS", tmp_path / "RUNS.jsonl")
    experiences.preenregistrer("Z9", "h", "m", {"seuil": 1})
    return tmp_path


def _publier(**kw):
    return mcp.OUTILS["beta_publish"]["fonction"](**kw)


def test_publish_refuse_un_verdict_sans_run(registre):
    with pytest.raises(ValueError, match="aucun run"):
        _publier(id="Z9", verdict="confirmee", resultat="x")
    assert experiences.etat()["Z9"]["statut"] == "preenregistre"


def test_publish_refuse_une_chaine_quelconque(registre):
    experiences.enregistrer_run("r1", "Z9", "c", "e", "infirmee")
    with pytest.raises(ValueError, match="verdict inconnu"):
        _publier(id="Z9", verdict="super", resultat="x")


def test_publish_refuse_un_verdict_contraire_au_moteur(registre):
    experiences.enregistrer_run("r1", "Z9", "c", "e", "infirmee")
    with pytest.raises(ValueError, match="contraire"):
        _publier(id="Z9", verdict="confirmee", resultat="x")


def test_publish_refuse_un_lot_aux_issues_differentes(registre):
    experiences.enregistrer_run("r1", "Z9", "c1", "e1", "infirmee")
    experiences.enregistrer_run("r2", "Z9", "c2", "e2", "confirmee")
    with pytest.raises(ValueError, match="issues differentes"):
        _publier(id="Z9", verdict="confirmee", resultat="x")


def test_publish_accepte_le_verdict_du_moteur_une_seule_fois(registre):
    experiences.enregistrer_run("r1", "Z9", "c", "e", "infirmee")
    sortie = _publier(id="Z9", verdict="infirmee", resultat="x")
    assert sortie["statut"] == "clos" and sortie["source"] == "mcp"
    with pytest.raises(ValueError, match="deja clos"):
        _publier(id="Z9", verdict="infirmee", resultat="x")


def test_publish_refuse_une_hypothese_inconnue(registre):
    with pytest.raises(experiences.ProtocoleError, match="preenregistr"):
        _publier(id="INCONNUE", verdict="confirmee", resultat="x")


# --- point 6 : le dashboard du PC refuse les POST cross-site ------------------------------

@pytest.fixture
def dashboard():
    srv = serveur.ServeurExclusif(("127.0.0.1", 0), serveur.Handler)
    srv.lecture_seule, srv.lien_vps = False, None
    fil = threading.Thread(target=srv.serve_forever, daemon=True)
    fil.start()
    yield srv.server_address[1]
    srv.shutdown()
    srv.server_close()


def _post(port, entetes, corps=b'{"geste": "rien"}', chemin="/api/atelier"):
    cnx = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    cnx.putrequest("POST", chemin, skip_host=True)
    for cle, valeur in {"Content-Length": str(len(corps)), **entetes}.items():
        cnx.putheader(cle, valeur)
    cnx.endheaders(corps)
    reponse = cnx.getresponse()
    return reponse.status, json.loads(reponse.read() or b"{}")


def test_post_formulaire_cross_site_refuse(dashboard):
    statut, _ = _post(dashboard, {"Host": "127.0.0.1",
                                  "Content-Type": "application/x-www-form-urlencoded"})
    assert statut == 415


def test_post_text_plain_refuse(dashboard):
    statut, _ = _post(dashboard, {"Host": "localhost", "Content-Type": "text/plain"})
    assert statut == 415


def test_post_hote_rebinde_refuse_meme_hors_lecture_seule(dashboard):
    statut, corps = _post(dashboard, {"Host": "attaquant.example:7474",
                                      "Content-Type": "application/json"})
    assert statut == 403 and corps["erreur"] == "hote refuse"


def test_post_origine_etrangere_refusee(dashboard):
    statut, corps = _post(dashboard, {"Host": "127.0.0.1",
                                      "Content-Type": "application/json",
                                      "Origin": "https://attaquant.example"})
    assert statut == 403 and corps["erreur"] == "origine refusee"


def test_post_local_en_json_passe_les_gardes(dashboard):
    # Une idee vide est refusee par `idees` (400), pas par les gardes (403/415) : c'est
    # la preuve que la page locale du PC passe toujours, sans rien ecrire au registre.
    statut, _ = _post(dashboard, {"Host": "127.0.0.1:7474",
                                  "Content-Type": "application/json; charset=utf-8",
                                  "Origin": "http://127.0.0.1:7474"},
                      corps=b'{"texte": ""}', chemin="/api/idee")
    assert statut == 400


# --- point 7 : aucune conversion de fin de ligne a l'extraction ---------------------------

def test_gitattributes_interdit_toute_conversion_de_fin_de_ligne():
    attributs = (pathlib.Path(config.RACINE) / ".gitattributes").read_text(encoding="utf-8")
    regles = [ligne.split() for ligne in attributs.splitlines()
              if ligne.strip() and not ligne.lstrip().startswith("#")]
    assert ["*", "-text"] in regles
