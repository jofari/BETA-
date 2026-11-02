"""VC6 V2 : campagne et rapport de bout en bout sur donnees synthetiques (B = 5, aucune source
vivante). Eprouve tout le calcul et l'ecriture du rapport avant le vrai run du GO."""

import numpy as np
import pandas as pd
import pytest

from beta.vc6_v2 import campagne, rapport
from beta.vc6_v2 import moteur as mt
from beta.vc6_v2 import regles as R


def _entrees(n, poches, graine):
    rng = np.random.default_rng(graine)
    jours = pd.date_range("2030-01-01", periods=n, freq="D")
    baissier = np.repeat(rng.random(n // 20 + 1) < 0.4, 20)[:n]
    rend = {a: rng.normal(0.0005, 0.04, n) for a in poches}
    for a in poches:
        rend[a][0] = np.nan
    return mt.Entrees(
        jours=jours, baissier=baissier,
        sigma={a: rng.uniform(0.08, 1.5, n) for a in poches},
        funding_annuel={a: rng.uniform(-0.1, 0.4, n) for a in poches},
        funding_jour={a: rng.uniform(-0.0003, 0.001, n) for a in poches},
        rendements=rend)


def _coherence():
    return {
        "a": {"valeur_finale_v2": 1.5, "valeur_finale_v1": 1.5, "ulcer_v2": 0.1, "ulcer_v1": 0.1,
              "jours": 10, "rendements_identiques_moteur_v1": True,
              "rendements_identiques_mesure_v1": True, "ecart_max": 0.0, "passe": True},
        "b": {"moteur": 2.0, "independant": 2.0, "ecart_relatif": 0.0,
              "expositions_toutes_a_1": True, "passe": True},
        "c": {"sharpe_normal": 0.5, "sharpe_anticipe": 0.6, "ulcer_normal": 0.2,
              "ulcer_anticipe": 0.15, "statut": "passe", "passe": True,
              "jours_sans_rv_sigma_garde": {"BTC": 0, "ETH": 0, "SOL": 0}},
        "d": {"har_sans_regime": {"circulaire_0_rendements_identiques": True,
                                  "circulaire_0_ulcer_identique": True,
                                  "blocs_identite_rendements_identiques": True, "blocs": 7},
              "poche_baissiere_har": {"mode_identique": True,
                                      "circulaire_0_rendements_identiques": True,
                                      "circulaire_0_ulcer_identique": True},
              "passe": True},
        "passe": True}


@pytest.fixture(scope="module")
def resultats():
    ent = _entrees(420, R.POCHES, 1)
    ent_r = _entrees(380, ("BTC",), 2)
    rng = np.random.default_rng(3)
    refs = {"panier": rng.normal(0.0004, 0.03, ent.n), "etf_monde": rng.normal(0.0003, 0.01, ent.n)}
    refs_r = {"btc": rng.normal(0.001, 0.04, ent_r.n),
              "etf_monde": rng.normal(0.0003, 0.01, ent_r.n)}
    return campagne.assembler(ent, ent_r, refs, refs_r, _coherence(), 61,
                              {"invest": 61, "trading": 93, "global": 154}, b=5)


def test_assembler(resultats):
    res = resultats
    assert list(res["runs"]) == ["har_sans_regime", "poche_baissiere_har"]
    for run in list(res["runs"].values()) + list(res["robustesse"]["runs"].values()):
        assert set(run["nulls"]) >= {"p_circulaire", "p_segments", "p_retenue"}
        assert run["nulls"]["p_retenue"] == max(run["nulls"]["p_circulaire"],
                                                run["nulls"]["p_segments"])
        assert run["mesures"]["dsr"] is not None
        assert set(run["analyses"]) == {"pires_drawdowns", "contributions", "vol_realisee",
                                        "levier"}
    # essai 1 sans poche baissiere ni regime ; essai 2 avec la poche baissiere sous HAR
    assert not res["runs"]["har_sans_regime"]["sim"]["baissier"].any()
    s2 = res["runs"]["poche_baissiere_har"]["sim"]
    assert s2["baissier"].any() and ("baissiere", "BTC") in s2["lignes"]
    assert (s2["y"][:, -1] <= 0.25 + 1e-12).all()
    # B = 5 : p >= 1/6, aucun essai utile -> aucune configuration retenue
    assert res["regles"]["2"]["retenue"] is None
    assert res["regles"]["3"]["essai"]["baissiere_pendant_mdd"] is not None
    assert res["regles"]["3"]["v1"]["baissiere_pendant_mdd"] is not None
    assert res["pbo"]["n_configs"] == 2
    assert set(res["verdict_vc6"]) == set(res["runs"])


def test_rapport_s_ecrit(resultats, tmp_path, monkeypatch):
    monkeypatch.setattr(rapport, "SORTIE", tmp_path / "rapport_v2.md")
    texte = open(rapport.ecrire(resultats), encoding="utf-8").read()
    for titre in ("## 1. Tests de cohérence", "## 2. Mesures", "## 3. Règles de décision",
                  "## 4. Règle 3", "## 5. Grille du verdict", "## 6. Détail par essai",
                  "## 7. Robustesse"):
        assert titre in texte
    assert "V2 – HAR sans régime" in texte and "V2 – poche baissière sous HAR" in texte
    assert "Configuration retenue : **aucune**" in texte
    assert "nan" not in texte.lower().replace("financement", "")


def test_rapport_avec_une_configuration_retenue(resultats, tmp_path, monkeypatch):
    monkeypatch.setattr(rapport, "SORTIE", tmp_path / "rapport_v2.md")
    res = dict(resultats)
    res["regles"] = dict(resultats["regles"])
    res["regles"]["2"] = {"retenue": "har_sans_regime", "utiles": ["har_sans_regime"],
                          "conclusion": "un seul essai utile : V2 – HAR sans régime"}
    texte = open(rapport.ecrire(res), encoding="utf-8").read()
    assert "Configuration retenue : **V2 – HAR sans régime**" in texte
