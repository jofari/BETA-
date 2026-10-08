"""Onglet Forward du dashboard : relecture des journaux SUIVI_/PAPER_, et le mode lecture seule
du serveur (VPS, derriere un tunnel SSH)."""

import http.client
import json
import math
import threading

import pytest

from beta.rapport import forward, serveur


def _jsonl(chemin, lignes):
    chemin.write_text("".join(json.dumps(l) + "\n" for l in lignes))


# ------------------------------------------------------------------------------- calculs

def test_bilan_rendement_maxdd_vol():
    b = forward.bilan([0.1, -0.5, 0.2])
    assert b["net"] == pytest.approx(1.1 * 0.5 * 1.2 - 1)
    assert b["mdd"] == pytest.approx(0.55 / 1.1 - 1)
    moyenne = (0.1 - 0.5 + 0.2) / 3
    ecart = math.sqrt(sum((r - moyenne) ** 2 for r in (0.1, -0.5, 0.2)) / 2)
    assert b["vol"] == pytest.approx(ecart * math.sqrt(252)) and b["n"] == 3
    assert forward.bilan([0.01])["vol"] is None


def _paper(date, equite_avant, ordres=()):
    return {"date": date, "capital_initial": 10_000.0, "equite_avant": equite_avant,
            "equite": equite_avant, "frais": 1.0, "funding": {"BTC": 0.5},
            "ordres": list(ordres), "ignores": [], "poids": {"BTC": 0.2}, "cash": 8_000.0}


def test_le_modele_couvre_les_memes_journees_de_detention():
    # le suivi du jour d = la detention entre les executions de d et de d+1
    suivi = [{"date": d, "r_net": r} for d, r in
             (("2026-10-08", 0.5), ("2026-10-09", 0.10), ("2026-10-10", -0.20),
              ("2026-10-11", 0.9))]
    lignes = [_paper("2026-10-09", 10_000.0), _paper("2026-10-10", 11_000.0),
              _paper("2026-10-11", 8_800.0)]
    p = forward.paper(lignes, suivi)
    assert [pt["modele"] for pt in p["points"]] == pytest.approx([1.0, 1.10, 1.10 * 0.80])
    assert [pt["paper"] for pt in p["points"]] == pytest.approx([1.0, 1.10, 0.88])
    assert p["rendement"] == pytest.approx(-0.12) and p["modele"] == pytest.approx(-0.12)
    assert p["frais"] == 3.0 and p["funding"] == 1.5


def test_slippage_moyen_pondere_par_le_notional():
    ordres = [{"notional": 100.0, "cout_carnet_pb": 1.0, "ecart_ouverture_pb": -10.0,
               "slippage_modele_pb": 5.0},
              {"notional": 300.0, "cout_carnet_pb": 3.0, "ecart_ouverture_pb": 30.0,
               "slippage_modele_pb": 10.0}]
    p = forward.paper([_paper("2026-10-09", 10_000.0, ordres)], [])
    assert p["carnet_pb"] == pytest.approx(2.5)
    assert p["ouverture_pb"] == pytest.approx(20.0)
    assert p["modele_pb"] == pytest.approx(8.75)
    assert p["n_ordres"] == 2 and p["ordres"][0]["date"] == "2026-10-09"
    assert forward.paper([_paper("2026-10-09", 10_000.0)], [])["carnet_pb"] is None


def test_vue_sans_journaux_et_statuts_du_registre(tmp_path):
    v = forward.vue(tmp_path)
    assert [x["nom"] for x in v["voies"]] == ["VOIE_C", "VC3", "VC2"]
    assert all(x["suivi"] is None and x["paper"] is None for x in v["voies"])
    statuts = {x["nom"]: x["statut"] for x in v["voies"]}
    assert statuts["VC3"].startswith("dry-run") and statuts["VC2"].startswith("informative")


def test_vue_relit_le_suivi(tmp_path):
    _jsonl(tmp_path / "SUIVI_VC3.jsonl", [
        {"date": "2026-10-07", "type": "rattrapage", "r_net": 0.01, "equite": 1.01,
         "equite_btc": 1.02, "etat": "veille"},
        {"date": "2026-10-08", "type": "live", "r_net": -0.02, "equite": 0.9898,
         "equite_btc": 1.0, "etat": "haussier", "votes": {"momentum_btc": 1}, "somme": 2,
         "consigne_lendemain": {"date": "2026-10-09", "trade": False}}])
    s = next(x for x in forward.vue(tmp_path)["voies"] if x["nom"] == "VC3")["suivi"]
    assert s["debut_live"] == "2026-10-08" and s["live"]["n"] == 1
    assert s["tout"]["net"] == pytest.approx(1.01 * 0.98 - 1)
    assert s["derniere"]["etat"] == "haussier" and s["consigne"]["trade"] is False
    assert [p["live"] for p in s["points"]] == [False, True]


# ------------------------------------------------------------------- serveur en lecture seule

@pytest.fixture
def lancer():
    serveurs = []

    def demarrer(lecture_seule):
        srv = serveur.ServeurExclusif(("127.0.0.1", 0), serveur.Handler)
        srv.lecture_seule, srv.lien_vps = lecture_seule, "http://127.0.0.1:7580"
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        serveurs.append(srv)
        return srv.server_address[1]

    yield demarrer
    for srv in serveurs:
        srv.shutdown()
        srv.server_close()


def _requete(port, methode, chemin, hote=None, corps=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    entetes = {"Host": hote} if hote else {}
    c.request(methode, chemin, body=corps, headers=entetes)
    r = c.getresponse()
    return r.status, json.loads(r.read() or b"{}")


def test_lecture_seule_refuse_les_post_et_les_hotes_etrangers(lancer):
    port = lancer(True)
    assert _requete(port, "GET", "/api/serveur") == (
        200, {"lecture_seule": True, "lien_vps": "http://127.0.0.1:7580"})
    statut, corps = _requete(port, "POST", "/api/idee", corps=b'{"texte": "x"}')
    assert statut == 403 and "lecture seule" in corps["erreur"]
    assert _requete(port, "GET", "/api/serveur", hote="attaquant.example:7474")[0] == 403
    assert _requete(port, "GET", "/api/serveur", hote="localhost:7574")[0] == 200


def test_sur_le_pc_rien_ne_change(lancer):
    port = lancer(False)
    statut, corps = _requete(port, "GET", "/api/serveur", hote="nom-de-machine:7474")
    assert statut == 200 and corps["lecture_seule"] is False
