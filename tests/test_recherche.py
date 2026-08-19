"""Les mesures R1 et R6. Dependent du lake : sautees s'il n'est pas construit."""

from __future__ import annotations

import numpy as np
import pytest

from beta.lake import strategie
from beta.protocole import experiences, holdout
from beta.recherche import r1_trailing, r6_news_window


def _lake_pret() -> bool:
    try:
        return not strategie.lire("trades", train_seulement=True).empty
    except Exception:                                     # noqa: BLE001
        return False


besoin_de_donnees = pytest.mark.skipif(not _lake_pret(),
                                       reason="lake de strategie absent")


@besoin_de_donnees
def test_r1_n_apparie_aucun_trade_du_holdout():
    apparies = r1_trailing.apparier()
    assert not apparies.empty
    assert (apparies["ts_entree"] < holdout.DEBUT).all()


@besoin_de_donnees
def test_r1_retrouve_le_r_du_trailing_deja_publie():
    """Garde-fou de portage : -0,4683 R cote short, chiffre du 18/08 (CHANTIERS.md R1)."""
    apparies = r1_trailing.apparier()
    shorts = apparies[apparies["sens"] == "short"]
    assert shorts["r_trailing"].mean() == pytest.approx(-0.4683, abs=0.01)


@besoin_de_donnees
def test_r1_conclut_indecidable_quand_l_ecart_est_sous_le_mde():
    resultat = r1_trailing.mesurer(clore=False)
    court = resultat["par_sens"]["short"]
    if abs(court["ecart_moyen"]) < court["mde_r"]:
        assert resultat["verdict"] == "indecidable"


@besoin_de_donnees
def test_r6_voit_que_les_deux_groupes_ne_sont_pas_disjoints():
    _, diagnostic = r6_news_window.partition()
    assert diagnostic["n_signaux_ambigus"] > 0
    assert diagnostic["n_lignes_journal"] > diagnostic["n_signaux_bloques"]


@besoin_de_donnees
def test_r6_ne_conclut_pas_sur_dix_signaux():
    assert r6_news_window.mesurer(clore=False)["verdict"] == "indecidable"


def test_le_registre_refuse_d_amender_une_experience_close(tmp_path, monkeypatch):
    monkeypatch.setattr(experiences, "REGISTRE", tmp_path / "exp.jsonl")
    experiences.preenregistrer("Z1", "h", "m", {"confirmee": "x"})
    experiences.clore("Z1", "infirmee", "rien vu")
    with pytest.raises(experiences.ProtocoleError, match="on n'amende pas"):
        experiences.amender("Z1", "trop tard")


def test_un_amendement_conserve_les_champs_requis(tmp_path, monkeypatch):
    monkeypatch.setattr(experiences, "REGISTRE", tmp_path / "exp.jsonl")
    experiences.preenregistrer("Z2", "h", "m", {"confirmee": "x"}, famille_taille=6)
    experiences.amender("Z2", "donnee manquante", famille_taille=8)
    entree = experiences.etat()["Z2"]
    assert entree["famille_taille"] == 8
    assert entree["amendement"] == "donnee manquante"
    assert entree["hypothese"] == "h"          # l'original n'est pas perdu


def test_le_mde_de_l_ecart_apparie_est_plus_petit_que_celui_des_series():
    """Ce qui justifie l'appariement de R1 : la variance de l'ecart, pas celle des series."""
    from beta.stats import descriptif
    rng = np.random.default_rng(0)
    commun = rng.normal(0, 1.0, 40)
    a = commun + rng.normal(0, 0.2, 40)
    b = commun + rng.normal(0, 0.2, 40)
    mde_serie = descriptif.mde(40, float(np.std(a, ddof=1)))
    mde_ecart = descriptif.mde(40, float(np.std(a - b, ddof=1)))
    assert mde_ecart < mde_serie
