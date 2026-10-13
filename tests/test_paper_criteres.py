"""Criteres du dry-run juges par le paper : ecart au suivi (+/-1 pt, Jonas 10/10) et cout au
carnet <= 2x le slippage du modele ; la voie C figee jugee sur sa variante severe."""

import importlib.util
import json
from pathlib import Path

from beta import paper
from beta.strategies import voie_c_voltarget as vc

_spec = importlib.util.spec_from_file_location(
    "paper_script", Path(__file__).resolve().parents[1] / "scripts" / "paper.py")
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)


def _ecrire(chemin, lignes):
    chemin.write_text("".join(json.dumps(l) + "\n" for l in lignes), encoding="utf-8")


def _ordre(carnet_pb, notional=1000.0):
    return {"notional": notional, "cout_carnet_pb": carnet_pb, "ecart_ouverture_pb": 0.0,
            "slippage_modele_pb": 5.0}


def _mesures(tmp_path, nom, equite_avant, r_suivi, carnet_pb):
    voie = paper.voies()[nom]
    _ecrire(paper.journal_paper(voie, tmp_path), [
        {"date": "2026-10-09", "equite_avant": 10_000.0, "equite": 10_000.0, "frais": 0.0,
         "funding": {}, "ordres": [_ordre(carnet_pb)]},
        {"date": "2026-10-10", "equite_avant": equite_avant, "equite": equite_avant,
         "frais": 0.0, "funding": {}, "ordres": []}])
    _ecrire(tmp_path / voie.suivi, [{"date": "2026-10-09", "r_net": r_suivi},
                                    {"date": "2026-10-10", "r_net": 0.5}])
    return script.mesures(voie, tmp_path, tmp_path)


def test_l_ecart_se_juge_aux_prix_du_modele_pas_a_l_heure_du_passage(tmp_path):
    """13/10 : -0,93 pt d'ecart au passage, presque tout dans le mouvement du marche de 00:00
    a 01:00. Aux prix du modele, il ne reste que le cout d'execution : pas d'alarme."""
    voie = paper.voies()["VC3"]
    _ecrire(paper.journal_paper(voie, tmp_path), [
        {"date": "2026-10-09", "equite_avant": 10_000.0, "equite": 10_000.0, "frais": 0.0,
         "funding": {}, "ordres": [_ordre(0.2)]},
        {"date": "2026-10-10", "equite_avant": 9_900.0, "equite_modele_avant": 9_995.0,
         "equite": 9_900.0, "frais": 0.0, "funding": {}, "ordres": []}])
    _ecrire(tmp_path / voie.suivi, [{"date": "2026-10-09", "r_net": 0.0},
                                    {"date": "2026-10-10", "r_net": 0.5}])
    m = script.mesures(voie, tmp_path, tmp_path)
    assert m["rendement"] < -0.009 and abs(m["rendement_prix_modele"]) < 0.001
    assert script.franchis(m) == []
    # Un vrai cout d'execution de plus d'un point, lui, declenche l'alarme.
    lignes = paper.lire_journal(paper.journal_paper(voie, tmp_path))
    lignes[-1]["equite_modele_avant"] = 9_880.0
    _ecrire(paper.journal_paper(voie, tmp_path), lignes)
    alertes = script.franchis(script.mesures(voie, tmp_path, tmp_path))
    assert len(alertes) == 1 and "aux prix du modele" in alertes[0]


def test_rien_de_franchi(tmp_path):
    m = _mesures(tmp_path, "VC3", 10_050.0, 0.004, 0.4)
    assert script.franchis(m) == []


def test_ecart_au_suivi_au_dela_d_un_point(tmp_path):
    m = _mesures(tmp_path, "VC3", 10_000.0, 0.02, 0.4)
    assert len(script.franchis(m)) == 1 and "ecart" in script.franchis(m)[0]


def test_slippage_au_carnet_au_dela_de_deux_fois_le_modele(tmp_path):
    m = _mesures(tmp_path, "VC3", 10_000.0, 0.0, 10.5)     # modele 5 pb sur cet ordre
    assert len(script.franchis(m)) == 1 and "slippage" in script.franchis(m)[0]


def test_voie_c_jugee_sur_sa_variante_severe(tmp_path):
    m = _mesures(tmp_path, "VOIE_C", 10_000.0, 0.0, 2 * vc.BPS_SLIPPAGE + 0.1)
    assert m["modele_pb"] == vc.BPS_SLIPPAGE
    assert "slippage" in script.franchis(m)[0]


def test_vc2_jamais_jugee():
    assert "VC2" not in script.JUGEES


def test_vc4_comparee_a_son_modele_quotidien_pas_a_ses_consignes(tmp_path):
    # Panne du 11/10 01:00 : le bilan lisait CONSIGNES_VC4 (cle « instant ») -> KeyError 'date'.
    voie = paper.voies()["VC4"]
    _ecrire(tmp_path / voie.suivi, [{"instant": "2026-10-09T00:00:00+00:00", "position": {}}])
    _ecrire(paper.journal_paper(voie, tmp_path), [
        {"date": "2026-10-09", "equite_avant": 10_000.0, "equite": 10_000.0, "frais": 0.0,
         "funding": {}, "ordres": [_ordre(0.4)]},
        {"date": "2026-10-10", "equite_avant": 10_040.0, "equite": 10_040.0, "frais": 0.0,
         "funding": {}, "ordres": []}])
    _ecrire(tmp_path / voie.journal_modele, [{"date": "2026-10-09", "r_net": 0.004},
                                             {"date": "2026-10-10", "r_net": 0.5}])
    m = script.mesures(voie, tmp_path, tmp_path)
    assert voie.journal_modele == "SUIVI_VC4.jsonl" and m["jours_modele"] == 1
    assert script.franchis(m) == []
