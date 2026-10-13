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
    assert [x["nom"] for x in v["voies"]] == ["VOIE_C", "VC3", "VC5", "VC4", "VC2"]
    assert all(x["suivi"] is None and x["paper"] is None for x in v["voies"])
    statuts = {x["nom"]: x["statut"] for x in v["voies"]}
    assert statuts["VC3"].startswith("dry-run") and statuts["VC2"].startswith("informative")
    assert statuts["VC3"].endswith("le 07/10)") and statuts["VC5"] == "dry-run de 6 mois (confirmée le 10/10)"


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


# ------------------------------------------------------------------- allocation, levier

def _execution(cash, quantites, milieux, equite=None):
    equite = equite if equite is not None else cash + sum(q * milieux[p]
                                                          for p, q in quantites.items())
    return {"date": "2026-10-10", "execute_le": "2026-10-10T01:00:18+00:00", "cash": cash,
            "quantites": quantites, "milieux": milieux, "equite": equite}


def test_allocation_spot_sans_levier():
    a = forward.allocation(_execution(3_000.0, {"BTC": 0.05, "ETH": 1.0},
                                      {"BTC": 100_000.0, "ETH": 2_000.0}))
    assert a["equite"] == pytest.approx(10_000.0)
    assert [x["valeur"] for x in a["actifs"]] == pytest.approx([5_000.0, 2_000.0])
    assert a["part_cash"] == pytest.approx(0.30)
    assert a["exposition_brute"] == pytest.approx(0.70) and a["exposition_nette"] == pytest.approx(0.70)
    assert a["effet_levier"] is False


def test_allocation_levier_quand_l_exposition_depasse_l_equite():
    # perpetuels : 13 500 $ de BTC pour 10 000 $ d'equite -> cash negatif, levier x1,35
    a = forward.allocation(_execution(-3_500.0, {"BTC": 0.135}, {"BTC": 100_000.0}))
    assert a["exposition_brute"] == pytest.approx(1.35) and a["effet_levier"] is True
    assert a["part_cash"] == pytest.approx(-0.35)


def test_allocation_un_short_compte_dans_le_brut_pas_dans_le_net():
    a = forward.allocation(_execution(10_000.0, {"BTC": 0.06, "ETH": -3.0},
                                      {"BTC": 100_000.0, "ETH": 2_000.0}, equite=10_000.0))
    assert a["exposition_brute"] == pytest.approx(1.20) and a["exposition_nette"] == pytest.approx(0.0)
    assert a["effet_levier"] is True


def test_allocation_a_100_pourcent_pile_n_est_pas_du_levier():
    a = forward.allocation(_execution(0.0, {"BTC": 0.1}, {"BTC": 100_000.0}))
    assert a["exposition_brute"] == pytest.approx(1.0) and a["effet_levier"] is False


def test_cadence_instant_consigne_et_paper_compares_au_modele_quotidien(tmp_path):
    # VC4 : la consigne en vigueur est la derniere decision de session ; le paper s'execute
    # plusieurs fois par jour, mais se compare au modele quotidien par sa PREMIERE execution
    _jsonl(tmp_path / "SUIVI_VC4.jsonl", [
        {"date": "2026-10-12", "type": "live", "equite": 1.10, "equite_btc": 1.0, "r_net": 0.10,
         "etat": "haussier", "positions": {"BTC": 0.5}, "brut": 0.5}])
    _jsonl(tmp_path / "CONSIGNES_VC4.jsonl", [
        {"instant": "2026-10-13T00:00:00+00:00", "etat": "haussier", "trade": False,
         "position": {"BTC": 0.5}, "brut": 0.5, "ordres": {}, "votes": {}, "somme": 2},
        {"instant": "2026-10-13T07:00:00+00:00", "etat": "veille", "trade": True,
         "position": {"BTC": 0.3}, "brut": 0.3, "ordres": {"BTC": -0.2}, "votes": {}, "somme": 1}])
    def ligne(date, instant, equite_avant):
        return {**_paper(date, equite_avant), "instant": instant}
    _jsonl(tmp_path / "PAPER_VC4.jsonl", [
        ligne("2026-10-12", "2026-10-12T00:00:00+00:00", 10_000.0),
        ligne("2026-10-12", "2026-10-12T07:00:00+00:00", 10_500.0),
        ligne("2026-10-13", "2026-10-13T00:00:00+00:00", 11_000.0),
        ligne("2026-10-13", "2026-10-13T07:00:00+00:00", 11_200.0)])
    v = next(x for x in forward.vue(tmp_path)["voies"] if x["nom"] == "VC4")
    c = v["suivi"]["consigne"]
    assert c["date"] == "2026-10-13 07:00 UTC" and c["etat"] == "veille" and c["trade"]
    p = v["paper"]
    assert [pt["date"] for pt in p["points"]] == ["2026-10-12", "2026-10-13"]
    assert p["rendement"] == pytest.approx(0.10)              # 11 000 a 00:00, pas 11 200
    assert p["modele"] == pytest.approx(0.10) and p["n_jours"] == 2


# ------------------------------------------------------------ valorisation au prix du moment

def test_valorisation_revalorise_le_dernier_passage_aux_prix_actuels(tmp_path):
    passage = {**_execution(3_000.0, {"BTC": 0.05, "ETH": 1.0}, {"BTC": 100_000.0, "ETH": 2_000.0}),
               "instrument": "spot", "capital_initial": 10_000.0}
    _jsonl(tmp_path / "PAPER_VC3.jsonl", [passage])
    prix = {"spot": {"BTC": 110_000.0, "ETH": 2_000.0}, "perpetuel": {}}
    v = forward.valorisation(tmp_path, prix=prix, le="2026-10-13T06:00:00+00:00")
    x = v["voies"]["VC3"]
    assert x["equite"] == pytest.approx(3_000.0 + 5_500.0 + 2_000.0)
    assert x["rendement"] == pytest.approx(0.05) and x["depuis_passage"] == pytest.approx(0.05)
    assert "VOIE_C" not in v["voies"] and v["prix_le"] == "2026-10-13T06:00:00+00:00"


def test_valorisation_sans_prix_de_l_instrument_ne_devine_rien(tmp_path):
    passage = {**_execution(3_000.0, {"BTC": 0.05}, {"BTC": 100_000.0}),
               "instrument": "perpetuel", "capital_initial": 10_000.0}
    _jsonl(tmp_path / "PAPER_VC2.jsonl", [passage])
    assert forward.valorisation(tmp_path, prix={"spot": {"BTC": 1.0}})["voies"] == {}


# ------------------------------------------------------------ allocation pas a pas, verifiee

def _consigne_moteur(*, etat="haussier", momentum_eth=0.2, levier=0.8, levier_calcule=0.7,
                     sigma=0.2 / 0.7, plafond=1.0, tenu=0.70, ecart=0.05, trade=False):
    vols = {"BTC": 0.30, "ETH": 0.60}
    inv = {p: 1 / v for p, v in vols.items()}
    s = sum(inv.values())
    paires, somme = {}, 0.0
    for p, v in vols.items():
        actif = p == "BTC" or momentum_eth > 0
        base = inv[p] / s
        comp = 0.5 * (base + (base if actif else 0.0))
        somme += comp
        paires[p] = {"vol_180j": v, "momentum": 0.3 if p == "BTC" else momentum_eth,
                     "tendance_active": actif, "poids_base": base,
                     "poids_tendance": base if actif else 0.0, "composite": comp, "voulu": None}
    brut = somme * levier
    echelle = plafond / brut if plafond is not None and brut > plafond else 1.0
    for x in paires.values():
        x["voulu"] = x["composite"] * levier * echelle
    moteur = {"lu": "2026-10-12", "cible_vol": 0.2, "sigma": sigma,
              "levier_calcule": levier_calcule, "levier": levier,
              "params": {"fenetre_vol_jambes": 180, "fenetre_mom": 126, "poids_jambes": 0.5,
                         "fenetre": 30, "lmin": 0.25, "lmax": 2.0, "seuil_levier": 0.25,
                         "bande": 0.2},
              "somme_composite": somme, "brut_moteur": brut, "plafond_brut": plafond,
              "brut_voulu": brut * echelle, "paires": paires}
    return {"date": "2026-10-13", "etat": etat, "trade": trade, "brut": tenu,
            "indicateurs": {"etat": etat, "moteur": moteur,
                            "execution": {"brut_tenu": tenu, "brut_voulu": brut * echelle,
                                          "ecart": ecart, "bande": 0.2}}}


def test_pas_a_pas_refait_chaque_etape_et_la_verifie():
    pp = forward.pas_a_pas(_consigne_moteur())
    assert pp["verifie"] and all(c["ok"] for c in pp["controles"])
    btc = pp["etape1"]["paires"][0]
    assert btc["base"] == pytest.approx(2 / 3) and btc["composite"] == pytest.approx(2 / 3)
    assert pp["etape2"]["change"] is False and pp["etape2"]["ecart"] == pytest.approx(0.1)
    assert pp["etape3"]["brut_voulu"] == pytest.approx(0.8)


def test_pas_a_pas_paire_en_baisse_perd_sa_jambe_tendance_sans_renormaliser():
    pp = forward.pas_a_pas(_consigne_moteur(momentum_eth=-0.1))
    eth = pp["etape1"]["paires"][1]
    assert eth["tendance"] == 0.0 and eth["composite"] == pytest.approx(0.5 / 3)
    assert pp["etape1"]["somme_composite"] == pytest.approx(5 / 6) and pp["verifie"]


def test_pas_a_pas_plafond_spot_et_decision_d_ordre():
    pp = forward.pas_a_pas(_consigne_moteur(levier=1.5, levier_calcule=1.5, sigma=0.2 / 1.5,
                                            ecart=0.4, trade=True))
    assert pp["etape3"]["echelle"] == pytest.approx(1 / 1.5) and pp["etape3"]["brut_voulu"] == pytest.approx(1.0)
    assert pp["etape2"]["change"] is True and pp["verifie"]


def test_pas_a_pas_veille_ne_fait_que_reduire():
    assert forward.pas_a_pas(_consigne_moteur(etat="veille", tenu=0.70, ecart=0.3))["verifie"]
    pp = forward.pas_a_pas(_consigne_moteur(etat="veille", tenu=1.10, ecart=0.3, trade=False))
    assert not pp["verifie"]                       # tenu - voulu = 0,3 > bande : il fallait reduire


def test_pas_a_pas_signale_une_valeur_journalisee_qui_ne_se_recoupe_pas():
    c = _consigne_moteur()
    c["indicateurs"]["moteur"]["paires"]["ETH"]["voulu"] += 0.01
    pp = forward.pas_a_pas(c)
    assert not pp["verifie"]
    assert [x["libelle"] for x in pp["controles"] if not x["ok"]] == ["ETH : voulu"]


def test_pas_a_pas_ordre_contraire_a_la_regle_est_signale():
    assert not forward.pas_a_pas(_consigne_moteur(ecart=0.05, trade=True))["verifie"]
    assert forward.pas_a_pas(None) is None and forward.pas_a_pas({"indicateurs": {}}) is None
