"""Paper de plomberie VC6 V2 : execution, decision du jour, donnee manquante, fantome, rejeu.
Donnees synthetiques ; aucun appel reseau, aucune lecture du lake vivant."""

import datetime as dt
import json
import math

import numpy as np
import pandas as pd
import pytest

from beta import paper as bp
from beta.vc6_v2 import moteur as mt
from beta.vc6_v2 import paper as pp
from beta.vc6_v2 import regles as R
from beta.vc6_v2 import rejeu as rj
from beta.vc6_v2 import vivant

REGLES = {"BTC": bp.Regles("0.00001", 1e-5, 5.0), "ETH": bp.Regles("0.0001", 1e-4, 5.0),
          "SOL": bp.Regles("0.001", 1e-3, 5.0)}
PRIX = {"BTC": 80_000.0, "ETH": 2_500.0, "SOL": 100.0}


# ----------------------------------------------------------------------------- execution

def test_premier_jour_construit_toute_la_position():
    poids = {"BTC": 0.165, "ETH": 0.08, "SOL": 0.05}
    e = pp.executer(None, poids, [], PRIX, REGLES, 10.0)
    assert e["premiere"] and e["a_traiter"] == ["BTC", "ETH", "SOL"]
    assert e["quantites"] == {"BTC": 0.02062, "ETH": 0.32, "SOL": 5.0}
    notional = sum(e["quantites"][a] * PRIX[a] for a in PRIX)
    assert e["frais"] == pytest.approx(notional * 1e-3)
    assert e["cash"] == pytest.approx(10_000 - notional - e["frais"])
    assert e["valeur"] == pytest.approx(10_000 - e["frais"])
    assert e["poids"]["BTC"] == pytest.approx(0.02062 * 80_000 / e["valeur"])


def test_seules_les_paires_a_traiter_bougent_et_minimum():
    etat = {"cash": 7_000.0, "quantites": {"BTC": 0.02, "ETH": 0.3, "SOL": 5.0}}
    poids = {"BTC": 0.10, "ETH": 0.50, "SOL": 0.0501}
    # ETH n'est pas a traiter : sa cible differente est ignoree ; SOL : 0,1 SOL = 10 USDT ok
    e = pp.executer(etat, poids, ["BTC", "SOL"], PRIX, REGLES, 10.0)
    assert e["quantites"]["ETH"] == 0.3
    assert {o["actif"] for o in e["ordres"]} == {"BTC", "SOL"}
    assert all(o["sens"] == "vente" for o in e["ordres"])
    # un achat et une vente : la vente passe d'abord
    e = pp.executer(etat, {"BTC": 0.10, "ETH": 0.2, "SOL": 0.05}, ["BTC", "ETH"], PRIX, REGLES,
                    10.0)
    assert [o["sens"] for o in e["ordres"]] == ["vente", "achat"]
    poids["SOL"] = 4.998 / 98.5     # valeur 9 850 : cible 4,998 SOL, ordre 0,002 SOL < 5 USDT
    e = pp.executer(etat, poids, ["SOL"], PRIX, REGLES, 10.0)
    assert e["ordres"] == [] and e["ignores"][0]["actif"] == "SOL"


def test_jamais_de_decouvert_au_comptant():
    etat = {"cash": 100.0, "quantites": {"BTC": 0.0, "ETH": 0.0, "SOL": 0.0}}
    e = pp.executer(etat, {"BTC": 0.9, "ETH": 0.0, "SOL": 0.0}, ["BTC"], PRIX, REGLES, 10.0)
    assert e["cash"] >= -1e-9
    assert e["quantites"]["BTC"] * PRIX["BTC"] <= 100.0


# ----------------------------------------------------------------------------- decision du jour

def _entrees(n=400, graine=1):
    rng = np.random.default_rng(graine)
    jours = pd.date_range("2030-01-01", periods=n, freq="D")
    baissier = np.repeat(rng.random(n // 15 + 1) < 0.4, 15)[:n]
    rend = {a: rng.normal(0.0, 0.03, n) for a in R.POCHES}
    for a in R.POCHES:
        rend[a][0] = np.nan
    return mt.Entrees(jours=jours, baissier=baissier,
                      sigma={a: rng.uniform(0.3, 1.5, n) for a in R.POCHES},
                      funding_annuel={a: rng.uniform(0.0, 0.3, n) for a in R.POCHES},
                      funding_jour={a: rng.uniform(0.0, 0.0008, n) for a in R.POCHES},
                      rendements=rend)


def _couper(ent, m):
    """Les m + 1 premiers jours (decisions D_0 .. D_m)."""
    return mt.Entrees(jours=ent.jours[:m + 1], baissier=ent.baissier[:m + 1],
                      sigma={a: s[:m + 1] for a, s in ent.sigma.items()},
                      funding_annuel={a: s[:m + 1] for a, s in ent.funding_annuel.items()},
                      funding_jour={a: s[:m + 1] for a, s in ent.funding_jour.items()},
                      rendements={a: s[:m + 1] for a, s in ent.rendements.items()})


def test_la_journee_fictive_redonne_la_decision_de_la_chaine():
    ent = _entrees()
    p = mt.parametres_essai(vivant.ESSAI)
    plein = mt.simuler(ent, p)
    for m in (50, 137, 200, 398):
        ext = mt.simuler(vivant.prolonger(_couper(ent, m)), p)
        assert np.array_equal(ext["y"][m], plein["y"][m])         # decision a la cloture D_m
        assert np.array_equal(ext["y"][:m], plein["y"][:m])


def test_nets_additionne_la_poche_baissiere_au_btc():
    lignes = [("poche", "BTC"), ("poche", "ETH"), ("poche", "SOL"), ("baissiere", "BTC")]
    assert vivant.nets(np.array([0.1, 0.2, 0.3, 0.05]), lignes) == pytest.approx(
        {"BTC": 0.15, "ETH": 0.2, "SOL": 0.3})


# ----------------------------------------------------------------------------- donnees vivantes

def _barres_5m(jour_fin, sans_2355=False):
    t = pd.date_range("2030-01-01", f"{jour_fin} 23:55", freq="5min", tz="UTC")
    if sans_2355:
        t = t[:-1]
    return pd.DataFrame({"date": t, "close": np.linspace(100, 110, len(t)), "volume": 1.0})


def _funding(jusqu_a):
    t = pd.date_range("2030-01-01 08:00", jusqu_a, freq="8h", tz="UTC")
    return pd.DataFrame({"date": t, "funding_rate": 0.0001})


def test_barre_de_23h55_absente_ou_funding_incomplet(monkeypatch):
    jour = "2030-01-05"
    monkeypatch.setattr(vivant.lecture, "load",
                        lambda a, tf, colonnes=None: _barres_5m(jour, sans_2355=(a == "ETH")))
    monkeypatch.setattr(vivant.lecture, "funding", lambda a: _funding("2030-01-06 00:00"))
    with pytest.raises(vivant.DonneeManquante, match="ETH : barre 5 min de 23:55"):
        vivant.charger(jour)
    monkeypatch.setattr(vivant.lecture, "load", lambda a, tf, colonnes=None: _barres_5m(jour))
    monkeypatch.setattr(vivant.lecture, "funding", lambda a: _funding("2030-01-05 16:00"))
    with pytest.raises(vivant.DonneeManquante, match="funding du 2030-01-05 incomplet"):
        vivant.charger(jour)


def test_funding_du_jour():
    s = pd.Series(0.0001, index=pd.date_range("2030-01-01 08:00", "2030-01-03 00:00", freq="8h",
                                                tz="UTC"))
    f = vivant.funding_jour(s)
    # ]D 00:00 ; D+1 00:00] : le 01/01 a 08:00, 16:00 et 02/01 00:00
    assert f["nombre"].tolist() == [3, 3]
    assert f["somme"].tolist() == pytest.approx([0.0003, 0.0003])


def test_garman_klass():
    ohlc = pd.DataFrame({"open": [100.0], "high": [110.0], "low": [95.0], "close": [105.0]})
    attendu = 0.5 * math.log(110 / 95) ** 2 - (2 * math.log(2) - 1) * math.log(105 / 100) ** 2
    assert vivant.garman_klass(ohlc).iloc[0] == pytest.approx(attendu)
    rng = np.random.default_rng(0)
    o = rng.uniform(50, 150, 500)
    c = o * np.exp(rng.normal(0, 0.05, 500))
    h = np.maximum(o, c) * np.exp(np.abs(rng.normal(0, 0.03, 500)))
    lo = np.minimum(o, c) * np.exp(-np.abs(rng.normal(0, 0.03, 500)))
    gk = vivant.garman_klass(pd.DataFrame({"open": o, "high": h, "low": lo, "close": c}))
    assert (gk >= 0).all()


# ----------------------------------------------------------------------------- une journee

class MarcheFactice:
    def prix_a(self, instrument, symbole, instant):
        assert instrument == bp.SPOT and instant.hour == 0 and instant.minute == 0
        return PRIX[symbole.removesuffix("USDT")]

    def regles(self, instrument, symbole):
        return REGLES[symbole.removesuffix("USDT")]


def _decision():
    poches = {a: {"sigma_har": 0.5, "ecart_type_30j": 0.45, "funding_annualise": 0.05,
                  "e_cible": 0.5, "e_modele": 0.5, "contraint": False} for a in R.POCHES}
    return {"jour_decision": "2030-03-01", "mode_btc": "haussier", "en_rampe": False,
            "poches": poches,
            "poche_baissiere": {"e_btc_formule": 0.5, "cible": 0.0, "modele": 0.0},
            "poids_modele": {"BTC": 0.25, "ETH": 0.125, "SOL": 0.125},
            "poids_modele_veille": {"BTC": 0.25, "ETH": 0.125, "SOL": 0.125},
            "a_traiter": [], "levier_modele": False}


def _donnees_factices():
    s = pd.Series(0.0001, index=pd.DatetimeIndex(["2030-03-01 08:00", "2030-03-01 16:00",
                                                  "2030-03-02 00:00"], tz="UTC"))
    return {"jour": pd.Timestamp("2030-03-01"), "reglements": dict.fromkeys(R.POCHES, s)}


def test_journee_executee_puis_idempotente(tmp_path, monkeypatch):
    monkeypatch.setattr(vivant, "charger", lambda jour: _donnees_factices())
    monkeypatch.setattr(vivant, "decider", lambda d: _decision())
    monkeypatch.setattr(vivant, "fantome", lambda d: {a: {"sigma_har_gk": 0.4} for a in R.POCHES})
    chemin = tmp_path / "PAPER_VC6.jsonl"
    maintenant = dt.datetime(2030, 3, 2, 0, 40, tzinfo=dt.UTC)
    ligne = pp.journee(maintenant, MarcheFactice(), chemin)
    assert ligne["statut"] == "execute" and ligne["premiere"]
    assert ligne["decision"]["cloture"] == "2030-03-01" and ligne["date"] == "2030-03-02"
    assert len(ligne["ordres"]) == 3 and ligne["frais"] > 0
    btc = ligne["actifs"]["BTC"]
    for cle in ("sigma_har", "sigma_har_gk_fantome", "ecart_type_30j", "e_cible", "e_modele",
                "e_paper", "poids_modele", "poids_paper", "funding_annualise"):
        assert btc[cle] is not None
    assert len(ligne["funding_info"]["BTC"]) == 3
    assert pp.journee(maintenant, MarcheFactice(), chemin) is None
    assert len(chemin.read_text().splitlines()) == 1


def test_donnee_manquante_aucun_ordre(tmp_path, monkeypatch):
    chemin = tmp_path / "PAPER_VC6.jsonl"
    veille = {"date": "2030-03-01", "statut": "execute", "cash": 6_000.0,
              "quantites": {"BTC": 0.02, "ETH": 0.5, "SOL": 10.0}}
    chemin.write_text(json.dumps(veille) + "\n")

    def manque(jour):
        raise vivant.DonneeManquante("SOL : barre 5 min de 23:55 du 2030-03-01 absente")
    monkeypatch.setattr(vivant, "charger", manque)
    ligne = pp.journee(dt.datetime(2030, 3, 2, 0, 40, tzinfo=dt.UTC), MarcheFactice(), chemin)
    assert ligne["statut"] == "donnee_manquante" and ligne["alerte"]
    assert ligne["ordres"] == [] and ligne["quantites"] == veille["quantites"]
    assert ligne["valeur"] == pytest.approx(6_000 + 0.02 * 80_000 + 0.5 * 2_500 + 10 * 100)


# ----------------------------------------------------------------------------- rejeu

def _ligne(date, poids_paper, poids_modele, a_traiter=(), ignores=(), statut="execute"):
    if statut == "donnee_manquante":
        q = {a: poids_paper[a] * 10_000 / PRIX[a] for a in R.POCHES}
        return {"date": date, "statut": statut, "quantites": q, "prix": PRIX, "valeur": 10_000.0,
                "valeur_avant": 10_000.0, "ignores": [], "ordres": []}
    return {"date": date, "statut": statut, "a_traiter": list(a_traiter),
            "ignores": [{"actif": a, "raison": "sous le minimum"} for a in ignores],
            "actifs": {a: {"poids_paper": poids_paper[a], "poids_modele": poids_modele[a]}
                       for a in R.POCHES}}


def test_rejeu_explique_les_ecarts():
    m = {"BTC": 0.20, "ETH": 0.10, "SOL": 0.10}
    derive = {"BTC": 0.27, "ETH": 0.10, "SOL": 0.10}
    lignes = [
        _ligne("2030-03-02", derive, m),                                   # derive (choix B)
        _ligne("2030-03-03", derive, m, statut="donnee_manquante"),        # donnee manquante
        _ligne("2030-03-04", derive, m, a_traiter=["BTC"], ignores=["BTC"]),  # ignore
        _ligne("2030-03-05", derive, {"BTC": 0.26, "ETH": 0.1, "SOL": 0.1}),  # revisee
        _ligne("2030-03-06", derive, m, a_traiter=["BTC"]),                # non explique
        _ligne("2030-03-07", m, m),                                        # pas d'ecart
    ]
    rejoue = {x["date"]: m for x in lignes}
    ecarts = rj.comparer(lignes, rejoue)
    assert [e["jour"] for e in ecarts] == ["2030-03-02", "2030-03-03", "2030-03-04",
                                           "2030-03-05", "2030-03-06"]
    assert all(e["actif"] == "BTC" and e["ecart_points"] == pytest.approx(7.0) for e in ecarts)
    expl = [e["explication"] for e in ecarts]
    assert expl[0].startswith("dérive des prix")
    assert expl[1].startswith("aucun ordre ce jour-là")
    assert expl[2].startswith("ordre ignoré")
    assert expl[3].startswith("la décision rejouée diffère")
    assert expl[4] == "non expliqué"
    assert rj.alerte({"non_expliques": 1}) and not rj.alerte({"non_expliques": 0})
    assert rj.alerte({"controle_backtest_fige": {"identique": False, "ecart_max": 1e-3}})
