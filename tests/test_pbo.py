"""S10 : la PBO d'un lot (`beta.stats.pbo`), porte obligatoire depuis le 26/10/2026 (Jonas).

Comme les autres portes, elle doit surtout savoir TUER : un lot de bruit pur ne la franchit
pas, et une PBO qu'on ne peut pas calculer ne vaut jamais « franchie ».
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from beta.protocole import experiences
from beta.stats import batterie, pbo

JOUR = pd.Timestamp("2022-01-03", tz="UTC")


def _trades(decalages_jours, r) -> pd.DataFrame:
    """Des trades clotures a 13:00 UTC, `decalages_jours` jours apres JOUR."""
    ts = [JOUR + pd.Timedelta(days=int(d), hours=13) for d in decalages_jours]
    return pd.DataFrame({"ts_sortie": pd.DatetimeIndex(ts), "r": np.asarray(r, dtype=float)})


def _lot(n_candidates=20, n_jours=640, graine=0, avantage=0.0) -> dict[str, pd.DataFrame]:
    """Un trade clos par jour et par candidate, R ~ N(0, 1) ; c00 recoit `avantage` par jour."""
    rng = np.random.default_rng(graine)
    jours = range(n_jours)
    return {f"c{k:02d}": _trades(jours, rng.standard_normal(n_jours) + (avantage if k == 0
                                                                       else 0.0))
            for k in range(n_candidates)}


# --- les rendements quotidiens d'un lot ------------------------------------------------

def test_le_rendement_du_jour_est_la_somme_des_r_clotures_ce_jour_la():
    m = pbo.rendements_lot({"b": _trades([1], [1.0]), "a": _trades([0, 0, 2], [1.0, -0.5, 2.0])})
    assert list(m.columns) == ["a", "b"]
    assert list(m.index) == [JOUR + pd.Timedelta(days=d) for d in range(3)]
    assert m["a"].tolist() == [0.5, 0.0, 2.0]
    assert m["b"].tolist() == [0.0, 1.0, 0.0]


def test_la_periode_va_du_premier_au_dernier_jour_de_cloture_du_lot():
    m = pbo.rendements_lot({"a": _trades([4, 9], [1.0, 1.0]), "b": _trades([0], [-1.0])})
    assert len(m) == 10
    assert m.index[0] == JOUR and m.index[-1] == JOUR + pd.Timedelta(days=9)
    assert m["a"].sum() == 2.0 and (m["a"] != 0).sum() == 2


def test_un_r_manquant_compte_zero_comme_dans_la_courbe_d_equity():
    m = pbo.rendements_lot({"a": _trades([0, 1], [np.nan, 1.0]), "b": _trades([1], [1.0])})
    assert m["a"].tolist() == [0.0, 1.0]


def test_une_candidate_sans_trade_est_une_colonne_de_zeros():
    vide = pd.DataFrame({"ts_sortie": pd.DatetimeIndex([], tz="UTC"), "r": []})
    m = pbo.rendements_lot({"a": _trades([0, 3], [1.0, -1.0]), "b": vide})
    assert len(m) == 4 and (m["b"] == 0.0).all()


def test_couper_retire_les_jours_les_plus_anciens():
    m = pd.DataFrame({"a": np.arange(35.0)},
                     index=pd.date_range("2022-01-01", periods=35, tz="UTC"))
    coupe = pbo.couper(m, 16)
    assert len(coupe) == 32
    assert coupe["a"].iloc[0] == 3.0 and coupe.index[-1] == m.index[-1]


def test_les_doublons_exacts_sont_retires_en_gardant_le_premier():
    m = pd.DataFrame({"a": [1.0, 2.0], "b": [1.0, 2.0], "c": [1.0, 2.0 + 1e-15]})
    gardee, doublons = pbo.dedoublonner(m)
    assert list(gardee.columns) == ["a", "c"]
    assert doublons == [{"nom": "b", "identique_a": "a"}]


# --- la porte --------------------------------------------------------------------------

def test_un_lot_de_bruit_ne_franchit_pas_la_porte():
    res = pbo.calculer(pbo.rendements_lot(_lot()), batterie.SEUIL_PBO)
    assert res["n_configs"] == 20 and res["n_jours"] == 640 and res["jours_par_bloc"] == 40
    assert res["pbo"] > 0.2
    assert res["passe"] is False


def test_une_vraie_gagnante_dans_le_lot_franchit_la_porte():
    res = pbo.calculer(pbo.rendements_lot(_lot(avantage=0.3)), batterie.SEUIL_PBO)
    assert res["pbo"] < 0.05
    assert res["passe"] is True
    assert max(res["etoiles"], key=res["etoiles"].get) == "c00"


def test_le_resultat_ne_depend_pas_de_l_ordre_d_arrivee_du_lot():
    lot = _lot(n_candidates=6, n_jours=320, graine=3)
    envers = dict(reversed(list(lot.items())))
    a = pbo.calculer(pbo.rendements_lot(lot), batterie.SEUIL_PBO)
    b = pbo.calculer(pbo.rendements_lot(envers), batterie.SEUIL_PBO)
    assert a["pbo"] == b["pbo"] and a["etoiles"] == b["etoiles"]


def test_les_jours_anciens_sont_retires_pour_avoir_seize_blocs_egaux():
    res = pbo.calculer(pbo.rendements_lot(_lot(n_candidates=4, n_jours=650)),
                       batterie.SEUIL_PBO)
    assert res["n_jours_avant"] == 650 and res["n_jours"] == 640
    assert res["debut"] == f"{JOUR + pd.Timedelta(days=10):%Y-%m-%d}"


def test_une_candidate_sans_trade_sur_une_moitie_rend_la_porte_non_executee():
    lot = _lot(n_candidates=3, n_jours=320)
    lot["muette"] = _trades([0, 319], [0.5, -0.5])
    res = pbo.calculer(pbo.rendements_lot(lot), batterie.SEUIL_PBO)
    assert res["pbo"] is None and res["passe"] is None
    assert "ecart-type" in res["raison"]


def test_moins_de_deux_candidates_distinctes_rend_la_porte_non_executee():
    seule = _lot(n_candidates=1, n_jours=320)["c00"]
    res = pbo.calculer(pbo.rendements_lot({"a": seule, "b": seule.copy()}),
                       batterie.SEUIL_PBO)
    assert res["passe"] is None and res["n_configs"] == 1
    assert res["doublons"] == [{"nom": "b", "identique_a": "a"}]


def test_un_historique_plus_court_que_les_blocs_rend_la_porte_non_executee():
    res = pbo.calculer(pbo.rendements_lot(_lot(n_candidates=3, n_jours=10)),
                       batterie.SEUIL_PBO)
    assert res["passe"] is None and "bloc" in res["raison"]


# --- dans la batterie ------------------------------------------------------------------

def test_s10_est_la_dixieme_porte_et_le_seuil_est_20_pourcent():
    assert batterie.PORTES[-1] == "S10_pbo" and len(batterie.PORTES) == 10
    assert batterie.SEUIL_PBO == 0.20


@pytest.mark.parametrize("s10, attendu", [(True, "confirmee"), (None, "indecidable"),
                                          (False, "infirmee")])
def test_confirmee_exige_aussi_s10(s10, attendu):
    portes = dict.fromkeys(batterie.PORTES, True)
    portes["S10_pbo"] = s10
    assert batterie.issue(portes, n_trades=100) == attendu


def test_la_batterie_juge_s10_sur_le_lot_entier():
    gagnant = _lot(avantage=0.3)
    res = batterie.evaluer(gagnant["c00"], n_essais=36, nom="c00", trades_lot=gagnant)
    assert res["portes"]["S10_pbo"] is True
    assert res["detail"]["S10_pbo"]["n_configs"] == 20

    bruit = _lot()
    res = batterie.evaluer(bruit["c00"], n_essais=36, nom="c00", trades_lot=bruit)
    assert res["portes"]["S10_pbo"] is False
    assert any("PBO du lot" in r for r in res["reserves"])


def test_s10_reste_non_executee_hors_lot_ou_si_la_pbo_est_incalculable():
    lot = _lot(n_candidates=3, n_jours=320)
    assert batterie.evaluer(lot["c00"], n_essais=36, nom="c00")["portes"]["S10_pbo"] is None
    dehors = batterie.evaluer(lot["c00"], n_essais=36, nom="autre", trades_lot=lot)
    assert dehors["portes"]["S10_pbo"] is None

    lot["muette"] = _trades([0, 319], [0.5, -0.5])
    res = batterie.evaluer(lot["c00"], n_essais=36, nom="c00", trades_lot=lot)
    assert res["portes"]["S10_pbo"] is None
    assert any(r.startswith("S10 non executee") for r in res["reserves"])


# --- cote invest : le preenregistrement ------------------------------------------------

def test_choisir_parmi_plusieurs_reglages_exige_la_pbo_au_preenregistrement(tmp_path):
    registre = tmp_path / "exp.jsonl"
    with pytest.raises(experiences.ProtocoleError, match="PBO"):
        experiences.preenregistrer("I1", "h", "m", {"confirmee": "x"}, n_configurations=6,
                                   famille_compteur="invest", chemin=registre)
    ligne = experiences.preenregistrer(
        "I1", "h", "m", {"confirmee": "x", "pbo": "S10 : PBO < 20 %"}, n_configurations=6,
        famille_compteur="invest", chemin=registre)
    assert ligne["n_configurations"] == 6
    seule = experiences.preenregistrer("I2", "h", "m", {"confirmee": "x"},
                                       famille_compteur="invest", chemin=registre)
    assert "n_configurations" not in seule
