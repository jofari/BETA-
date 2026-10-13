"""Paper trading : le carnet mange, les pas et minimums de l'exchange, la comptabilite spot et
perpetuels (short, funding), une execution par jour, une consigne perimee refusee."""

import datetime as dt
import json

import pytest

from beta import paper

PAIRES = paper.PAIRES
MILIEUX = {"BTC": 80_000.0, "ETH": 2_500.0, "SOL": 110.0, "BNB": 760.0, "LINK": 13.0,
           "XRP": 1.4}
JOUR1 = dt.datetime(2026, 10, 9, 1, 0, tzinfo=dt.UTC)
JOUR2 = JOUR1 + dt.timedelta(days=1)


class MarcheFactice:
    """Carnet symetrique autour du milieu : 5 niveaux de `profondeur` USDT par cote, espaces
    de 1 pb. Trois echeances de funding au taux donne entre deux executions."""

    def __init__(self, milieux=None, profondeur=1e6, taux=0.0001, pas="0.001", notional=5.0):
        self.milieux = dict(milieux or MILIEUX)
        self.profondeur, self.taux = profondeur, taux
        self.pas, self.notional = pas, notional

    def carnet(self, instrument, symbole):
        m = self.milieux[symbole.removesuffix("USDT")]
        cote = lambda s: [(m * (1 + s * (k + 1) * 1e-4), self.profondeur / m)  # noqa: E731
                          for k in range(5)]
        return paper.Carnet(cote(-1), cote(+1), "factice")

    def regles(self, instrument, symbole):
        return paper.Regles(self.pas, float(self.pas), self.notional)

    def ouverture(self, instrument, symbole, jour):
        return self.milieux[symbole.removesuffix("USDT")]

    def prix_a(self, instrument, symbole, instant):
        self.instants_lus = getattr(self, "instants_lus", []) + [instant]
        return self.milieux[symbole.removesuffix("USDT")] * 1.001

    def funding(self, symbole, depuis, jusqu_a):
        return [{"instant": 0, "taux": self.taux, "marque": None}] * 3


def _voie(instrument=paper.SPOT, taker_pb=10.0):
    return paper.Voie("TEST", "SUIVI_TEST.jsonl", instrument, taker_pb, {p: 5.0 for p in PAIRES})


def _consigne(poids, a_traiter=None, jour=JOUR1.date()):
    poids = {p: poids.get(p, 0.0) for p in PAIRES}
    return paper.Consigne(jour, poids, frozenset(a_traiter or ()), "test")


# --------------------------------------------------------------------------- carnet, arrondis

def test_l_ordre_mange_le_carnet_niveau_par_niveau():
    carnet = paper.Carnet([(99.0, 1.0), (98.0, 1.0)], [(100.0, 1.0), (101.0, 1.0)], "t")
    assert paper.executer(1.5, carnet) == (pytest.approx((100 + 0.5 * 101) / 1.5), 2, True)
    assert paper.executer(-1.0, carnet) == (99.0, 1, True)
    prix, niveaux, complet = paper.executer(3.0, carnet)       # plus que le carnet lu
    assert not complet and niveaux == 2 and prix == pytest.approx((100 + 101 + 101) / 3)


def test_quantites_au_pas_de_l_exchange():
    r = paper.Regles("0.001", 0.001, 50.0)
    assert paper.au_pas(0.12349, r) == 0.123
    assert paper.au_pas(0.1236, r) == 0.124
    assert paper.au_pas(0.1239, r, vers_zero=True) == 0.123
    assert paper.au_pas(-0.0129, r, vers_zero=True) == -0.012
    assert paper._pas("10.00000000") == "10" and paper._pas("0.00100000") == "0.001"


# ------------------------------------------------------------------------- une journee spot

def test_premiere_journee_construit_toute_la_position():
    poids = {"BTC": 0.30, "ETH": 0.20, "SOL": 0.10}
    l = paper.journee(_voie(), _consigne(poids), paper.compte_initial(), None, MarcheFactice(),
                      JOUR1)
    assert l["premiere"] and {o["paire"] for o in l["ordres"]} == set(poids)
    for p, w in poids.items():
        assert l["poids"][p] == pytest.approx(w, abs=0.01)    # au pas pres
    # l'execution coute les frais et le demi-ecart (1 pb), rien d'autre
    cout = sum(o["notional"] * 10e-4 + o["qte"] * (o["prix"] - o["milieu"]) for o in l["ordres"])
    assert l["equite_avant"] - l["equite"] == pytest.approx(cout, rel=1e-6)
    assert all(o["cout_carnet_pb"] == pytest.approx(1.0, abs=1e-6) for o in l["ordres"])


def test_spot_jamais_a_decouvert():
    # le modele veut 100 % investi : frais et ecart compris, les achats sont reduits
    poids = {p: 1 / 6 for p in PAIRES}
    l = paper.journee(_voie(), _consigne(poids), paper.compte_initial(), None, MarcheFactice(),
                      JOUR1)
    assert 0.0 <= l["cash"] < 0.01 * paper.CAPITAL_USDT
    assert all(q >= 0 for q in l["quantites"].values())


def test_journee_suivante_ne_touche_que_les_paires_que_le_modele_change():
    marche = MarcheFactice()
    j1 = paper.journee(_voie(), _consigne({"BTC": 0.3, "SOL": 0.2}), paper.compte_initial(),
                       None, marche, JOUR1)
    marche.milieux["BTC"] *= 1.10                               # BTC derive, le modele non
    compte = {"cash": j1["cash"], "quantites": j1["quantites"]}
    c2 = _consigne({"BTC": 0.3, "SOL": 0.0}, a_traiter={"SOL"}, jour=JOUR2.date())
    j2 = paper.journee(_voie(), c2, compte, JOUR1, marche, JOUR2)
    assert [(o["paire"], o["sens"]) for o in j2["ordres"]] == [("SOL", "vente")]
    assert j2["quantites"]["BTC"] == j1["quantites"]["BTC"] and j2["quantites"]["SOL"] == 0.0


class MarcheQuiBouge(MarcheFactice):
    """Le marche a bouge entre 00:00 (prix du modele) et le passage : ouverture != milieu."""

    def __init__(self, ouvertures, **options):
        super().__init__(**options)
        self.ouvertures = ouvertures

    def ouverture(self, instrument, symbole, jour):
        return self.ouvertures[symbole.removesuffix("USDT")]


def test_le_compte_avant_ordres_est_aussi_valorise_aux_prix_du_modele():
    """Nuit du 13/10 : le marche baisse entre 00:00 et le passage. `equite_avant` le subit,
    `equite_modele_avant` non — c'est elle que l'ecart au suivi juge depuis le 13/10."""
    j1 = paper.journee(_voie(), _consigne({"BTC": 0.3, "SOL": 0.2}), paper.compte_initial(),
                       None, MarcheFactice(), JOUR1)
    compte = {"cash": j1["cash"], "quantites": j1["quantites"]}
    a_minuit = dict(MILIEUX)                                  # le prix du modele
    marche = MarcheQuiBouge(a_minuit, milieux={**MILIEUX, "BTC": 79_200.0, "SOL": 107.8})
    j2 = paper.journee(_voie(), _consigne({"BTC": 0.3, "SOL": 0.2}, jour=JOUR2.date()), compte,
                       JOUR1, marche, JOUR2)
    q = j1["quantites"]
    assert j2["equite_modele_avant"] == pytest.approx(
        j1["cash"] + q["BTC"] * 80_000.0 + q["SOL"] * 110.0)
    assert j2["equite_avant"] - j2["equite_modele_avant"] == pytest.approx(
        q["BTC"] * -800.0 + q["SOL"] * -2.2)
    assert set(j2["prix_modele"]) == {"BTC", "SOL"}           # les paires TENUES, sans ordre


def test_premiere_journee_aux_prix_du_modele_vaut_le_capital():
    l = paper.journee(_voie(), _consigne({"BTC": 0.3}), paper.compte_initial(), None,
                      MarcheFactice(), JOUR1)
    assert l["equite_modele_avant"] == paper.CAPITAL_USDT


def test_reliquat_spot_sous_le_minimum_ignore():
    marche = MarcheFactice(pas="0.01", notional=5.0)
    compte = {"cash": 9_000.0, "quantites": {**{p: 0.0 for p in PAIRES}, "XRP": 3.0}}
    c = _consigne({"XRP": 0.0}, a_traiter={"XRP"}, jour=JOUR2.date())
    l = paper.journee(_voie(), c, compte, JOUR1, marche, JOUR2)   # 3 XRP = 4,2 USDT < 5
    assert l["ordres"] == [] and l["ignores"][0]["paire"] == "XRP"


# ------------------------------------------------------------------------ perpetuels, funding

def test_perpetuel_short_paye_par_le_funding_positif():
    voie = _voie(paper.PERPETUEL, taker_pb=5.0)
    marche = MarcheFactice(taux=0.0001)
    j1 = paper.journee(voie, _consigne({"BTC": -0.4}), paper.compte_initial(), None, marche, JOUR1)
    q = j1["quantites"]["BTC"]
    assert q == -0.05 and j1["cash"] > paper.CAPITAL_USDT       # vente a decouvert
    compte = {"cash": j1["cash"], "quantites": j1["quantites"]}
    j2 = paper.journee(voie, _consigne({"BTC": -0.4}, jour=JOUR2.date()), compte, JOUR1, marche,
                       JOUR2)
    # 3 echeances a +1 pb : le short RECOIT |q| * prix * 3e-4 ; aucun ordre (rien a traiter)
    assert j2["funding"]["BTC"] == pytest.approx(q * 80_000.0 * 3e-4)
    assert j2["cash"] - j1["cash"] == pytest.approx(-q * 80_000.0 * 3e-4)
    assert j2["ordres"] == []


def test_reduction_en_perpetuel_exemptee_du_minimum():
    voie = _voie(paper.PERPETUEL, taker_pb=5.0)
    marche = MarcheFactice(pas="0.0001", notional=50.0, taux=0.0)
    compte = {"cash": 9_000.0, "quantites": {**{p: 0.0 for p in PAIRES}, "BTC": 0.0125}}
    # 0,0005 BTC = 40 USDT < 50 : un ajout serait refuse, une reduction (reduceOnly) passe
    cible = (0.0125 - 0.0005) * 80_000.0
    for signe, passe in ((-1, True), (+1, False)):
        w = (cible if signe < 0 else (0.0125 + 0.0005) * 80_000.0) / (9_000.0 + 1_000.0)
        l = paper.journee(voie, _consigne({"BTC": w}, a_traiter={"BTC"}, jour=JOUR2.date()),
                          compte, JOUR1, marche, JOUR2)
        assert (len(l["ordres"]) == 1) is passe, signe


# ------------------------------------------------------------- consignes et journal paper

def _suivi(tmp_path, nom, date, consigne):
    (tmp_path / nom).write_text(json.dumps({"date": date, "consigne_lendemain": consigne})
                                + "\n")


def test_deux_formats_de_consigne(tmp_path):
    # voie C : la cible du moteur ; voie C2 : la position tenue demain
    _suivi(tmp_path, "C.jsonl", "2026-10-08",
           {"trade": True, "cible": {p: 0.1 for p in PAIRES},
            "ordres": {**{p: 0.01 for p in PAIRES}, "XRP": 0.0}})
    _suivi(tmp_path, "C2.jsonl", "2026-10-08",
           {"trade": False, "position": {p: 0.2 for p in PAIRES}, "ordres": {}})
    c = paper.lire_consigne(tmp_path / "C.jsonl")
    assert c.jour == JOUR1.date() and c.poids["BTC"] == 0.1
    assert c.a_traiter == frozenset(PAIRES) - {"XRP"}
    c2 = paper.lire_consigne(tmp_path / "C2.jsonl")
    assert c2.poids["ETH"] == 0.2 and c2.a_traiter == frozenset()


def test_une_execution_par_jour_et_consigne_perimee_refusee(tmp_path):
    voie = paper.Voie("TEST", "SUIVI_TEST.jsonl", paper.SPOT, 10.0, {p: 5.0 for p in PAIRES})
    _suivi(tmp_path, "SUIVI_TEST.jsonl", "2026-10-08",
           {"trade": False, "position": {p: 0.1 for p in PAIRES}, "ordres": {}})
    marche = MarcheFactice()
    assert paper.executer_voie(voie, marche, JOUR1, tmp_path, tmp_path) is not None
    assert paper.executer_voie(voie, marche, JOUR1, tmp_path, tmp_path) is None
    with pytest.raises(paper.PaperError, match="pas de consigne"):    # suivi pas passe le 10/10
        paper.executer_voie(voie, marche, JOUR2, tmp_path, tmp_path)
    lignes = paper.lire_journal(tmp_path / "PAPER_TEST.jsonl")
    assert [l["date"] for l in lignes] == ["2026-10-09"]


def test_les_trois_voies_et_leurs_frais():
    v = paper.voies()
    assert {n: (x.instrument, x.taker_pb) for n, x in v.items()} == {
        "VOIE_C": (paper.PERPETUEL, 5.0), "VC2": (paper.PERPETUEL, 5.0),
        "VC3": (paper.SPOT, 10.0), "VC5": (paper.SPOT, 10.0), "VC4": (paper.SPOT, 10.0)}
    assert v["VC4"].cadence == "instant" and v["VC4"].suivi == "CONSIGNES_VC4.jsonl"
    assert all(x.cadence == "jour" for n, x in v.items() if n != "VC4")
    assert v["VC3"].slippage_modele_pb == {"BTC": 5.0, "ETH": 5.0, "SOL": 10.0, "BNB": 10.0,
                                           "LINK": 10.0, "XRP": 10.0}


# ------------------------------------------------------------- cadence « instant » (VC4)

def _consigne_instant(chemin, instant, poids, ordres):
    with chemin.open("a") as f:
        f.write(json.dumps({"instant": instant.isoformat(), "etat": "haussier", "trade": bool(ordres),
                            "position": {p: poids for p in PAIRES}, "ordres": ordres}) + "\n")


def test_cadence_instant_une_execution_par_instant(tmp_path):
    voie = paper.Voie("I", "CONSIGNES_I.jsonl", paper.SPOT, 10.0, {p: 5.0 for p in PAIRES},
                      cadence="instant")
    marche = MarcheFactice()
    tokyo = dt.datetime(2026, 10, 12, 0, 0, tzinfo=dt.UTC)
    londres = dt.datetime(2026, 10, 12, 7, 0, tzinfo=dt.UTC)
    _consigne_instant(tmp_path / voie.suivi, tokyo, 0.1, {})
    premiere = paper.executer_voie(voie, marche, tokyo + dt.timedelta(minutes=61), tmp_path,
                                   tmp_path)
    assert premiere["instant"] == tokyo.isoformat() and premiere["premiere"]
    # le modele traite au prix de l'INSTANT, pas a l'ouverture du jour
    assert set(marche.instants_lus) == {tokyo}
    assert premiere["ordres"][0]["ouverture"] == pytest.approx(
        MILIEUX[premiere["ordres"][0]["paire"]] * 1.001)
    # meme instant : rien de plus
    assert paper.executer_voie(voie, marche, tokyo + dt.timedelta(hours=2), tmp_path,
                               tmp_path) is None
    # nouvel instant le meme jour : une deuxieme execution, qui ne touche que ce qui change
    _consigne_instant(tmp_path / voie.suivi, londres, 0.15,
                      {**{p: 0.0 for p in PAIRES}, "BTC": 0.05})
    seconde = paper.executer_voie(voie, marche, londres + dt.timedelta(minutes=3), tmp_path,
                                  tmp_path)
    assert seconde["instant"] == londres.isoformat() and [o["paire"] for o in seconde["ordres"]] == ["BTC"]
    lignes = paper.lire_journal(tmp_path / "PAPER_I.jsonl")
    assert [l["date"] for l in lignes] == ["2026-10-12", "2026-10-12"]


def test_cadence_instant_consigne_perimee_refusee(tmp_path):
    voie = paper.Voie("I", "CONSIGNES_I.jsonl", paper.SPOT, 10.0, {p: 5.0 for p in PAIRES},
                      cadence="instant")
    londres = dt.datetime(2026, 10, 12, 7, 0, tzinfo=dt.UTC)
    _consigne_instant(tmp_path / voie.suivi, londres, 0.1, {})
    with pytest.raises(paper.PaperError, match="perimee"):        # suivi en panne depuis 4 h
        paper.executer_voie(voie, MarcheFactice(), londres + dt.timedelta(hours=4), tmp_path,
                            tmp_path)
    with pytest.raises(paper.PaperError, match="perimee"):        # une consigne du futur
        paper.executer_voie(voie, MarcheFactice(), londres - dt.timedelta(minutes=1), tmp_path,
                            tmp_path)
