"""Le rapport d'experience ecrit par le programme (Jonas, 04/11/2026).

Ce qu'on verifie : le rapport dit ce que le registre et les runs disent, mot pour mot ; ce
qu'il recalcule se controle contre le moteur, et un ecart se voit au lieu de se corriger ;
l'avis de Claude n'apparait que s'il est fourni, et toujours marque comme tel ; le resume
Discord n'a pas de tableau Markdown et signe « ecrit par le programme ».

Registre, journal et runs fabriques par le test dans un dossier temporaire.
"""
from __future__ import annotations

import json

import pandas as pd
import pytest

from beta.protocole import experiences
from beta.rapport import experience as rx
from beta.stats.batterie import PORTES

HYPOTHESE = "Une regle de test, ecrite AVANT la mesure, mot pour mot."


def _trades(r_brut: list[float], cout: float) -> pd.DataFrame:
    n = len(r_brut)
    frais, spread = 0.8 * cout, 0.2 * cout
    return pd.DataFrame({
        "ts_sortie": pd.date_range("2023-12-28", periods=n, freq="1D", tz="UTC"),
        "sens": ["long" if i % 2 else "short" for i in range(n)],
        "raison_sortie": ["TP" if x > 0 else "SL" for x in r_brut],
        "r_brut": r_brut, "frais_r": frais, "spread_r": spread, "funding_r": 0.0,
        "cout_r": frais + spread + 0.0,
        "r": [x - (frais + spread + 0.0) for x in r_brut],
        "rendement_pct": [x / 10 for x in r_brut], "mfe_r": 1.0, "mae_r": -0.5,
        "duree_h": 2.0})


def _verdict(nom: str, run_id: str, trades: pd.DataFrame) -> dict:
    portes = dict.fromkeys(PORTES, False)
    portes["S5_synthetique"] = True
    return {"run_id": run_id, "experience": "TX", "candidate": nom,
            "empreinte": f"emp_{nom}", "titre": f"Regle de test (1h) — {nom.replace('_', ' ')}",
            "paires": ["XAU_SPOT"], "timeframe": "1h", "split": "train",
            "debut": "2023-12-01", "fin": None, "stop_atr": 2.0, "take_profit_r": 3.0,
            "horizon_bougies": 6, "cout_aller_retour_pct": 0.12, "frais_pct": 0.1,
            "slippage_pct": 0.02, "spread": True, "funding": True, "spread_modele": "tick",
            "parametres": {"fraction_stop": 1.0}, "lance_le": "2026-11-04T12:00:00+00:00",
            "issue": "infirmee",
            "metriques": {"n": len(trades), "r_moyen": float(trades["r"].mean()),
                          "r_median": float(trades["r"].median()), "r_sigma": 1.0,
                          "mde_r": 0.25, "win_rate": float((trades["r"] > 0).mean()),
                          "profit_factor": 0.5, "mfe_r_moyen": 1.0, "mae_r_moyen": -0.5,
                          "duree_h_mediane": 2.0, "n_essais_cumules": 42},
            "portes": portes, "portes_echouees": sorted(p for p, ok in portes.items() if not ok),
            "portes_non_executees": [],
            "reserves": ["une reserve du moteur, telle quelle",
                         f"{len(trades) + 1} signaux mesures, {len(trades)} retenus apres "
                         "elimination des chevauchements"],
            "n_essais_cumules": 42}


@pytest.fixture
def labo(tmp_path, monkeypatch):
    """Une experience TX close, deux variantes mesurees, tout dans un dossier temporaire."""
    registre, journal = tmp_path / "EXPERIMENTS.jsonl", tmp_path / "RUNS.jsonl"
    runs = tmp_path / "runs"
    monkeypatch.setattr(experiences, "REGISTRE", registre)
    monkeypatch.setattr(experiences, "JOURNAL_RUNS", journal)
    experiences.preenregistrer(
        "TX", HYPOTHESE, "R moyen net par trade",
        {"confirmee": "R moyen > 0 et dix portes", "infirmee": "sinon"},
        issue_attendue="infirmee", famille_taille=2, deja_connu="rien, c'est un test")
    detail = {}
    for nom, run_id, brut in (("variante_a", "aaaaaaaaaaaa", [3.0, -1.0, -1.0, 3.0, -1.0]),
                              ("variante_b", "bbbbbbbbbbbb", [-1.0, -1.0, 3.0, -1.0, -1.0])):
        trades = _trades(brut, cout=0.1)
        verdict = _verdict(nom, run_id, trades)
        dossier = runs / run_id
        dossier.mkdir(parents=True)
        (dossier / "verdict.json").write_text(json.dumps(verdict), encoding="utf-8")
        (dossier / "batterie.json").write_text(json.dumps({
            "S8_buy_and_hold": {"hold": {"debut": "2023-12-01", "fin": "2024-12-31",
                                         "rendement_total_pct": 12.5, "sharpe_annuel": 1.0,
                                         "drawdown_max_pct": -5.0},
                                "candidate": {"rendement_total_pct": -3.0},
                                "passe": False},
            "S10_pbo": {"pbo": 0.5, "seuil": 0.2}}), encoding="utf-8")
        trades.to_parquet(dossier / "trades.parquet", index=False)
        experiences.enregistrer_run(run_id, "TX", nom, verdict["empreinte"], "infirmee")
        detail[nom] = {"run": run_id, "issue": "infirmee",
                       "r_moyen": verdict["metriques"]["r_moyen"],
                       "portes_echouees": verdict["portes_echouees"]}
    experiences.clore("TX", "infirmee", "texte de cloture du registre", lot=list(detail),
                      runs=[d["run"] for d in detail.values()], detail=detail,
                      donnees={"sha256": "0123456789abcdef", "bougies": 120,
                               "premiere": "2023-12-01 00:00:00+00:00",
                               "derniere": "2024-12-31 20:00:00+00:00"})
    return {"runs": runs, "chemin": tmp_path}


def _exp(labo) -> rx.Experience:
    return rx.charger("TX", resultats=labo["runs"])


# --- lecture --------------------------------------------------------------------------------------

def test_les_runs_retenus_sont_ceux_de_la_ligne_de_cloture(labo):
    exp = _exp(labo)
    assert [v.run_id for v in exp.variantes] == ["aaaaaaaaaaaa", "bbbbbbbbbbbb"]
    assert exp.origine_runs == "cloture" and all(v.present for v in exp.variantes)


def test_une_experience_inconnue_est_refusee(labo):
    with pytest.raises(rx.RapportError, match="inconnue"):
        rx.charger("ZZ", resultats=labo["runs"])


def test_les_noms_viennent_des_titres_des_candidates(labo):
    nom, libelles = rx.noms(_exp(labo))
    assert nom == "Regle de test (1h)"
    assert libelles == {"variante_a": "variante a", "variante_b": "variante b"}


# --- controles : refaits, jamais corriges ---------------------------------------------------------

def test_des_runs_coherents_passent_tous_les_controles(labo):
    resultats = rx.controles(_exp(labo))
    assert resultats and all(c["ok"] is True for c in resultats), resultats
    assert rx.pastille([_exp(labo)])[0] == "🟢"


def test_un_r_moyen_qui_ne_correspond_pas_aux_trades_se_voit(labo):
    chemin = labo["runs"] / "aaaaaaaaaaaa" / "verdict.json"
    verdict = json.loads(chemin.read_text(encoding="utf-8"))
    verdict["metriques"]["r_moyen"] += 0.01
    chemin.write_text(json.dumps(verdict), encoding="utf-8")
    exp = _exp(labo)
    ecarts = [c for c in rx.controles(exp) if c["ok"] is False]
    assert {c["controle"] for c in ecarts} >= {"R moyen recalculé = verdict.json"}
    assert rx.pastille([exp])[0] == "🔴"
    assert "**ÉCART**" in rx.markdown([exp], commande="test")


def test_un_run_disparu_de_data_est_dit_et_rend_la_pastille_rouge(labo):
    (labo["runs"] / "bbbbbbbbbbbb" / "verdict.json").unlink()
    exp = _exp(labo)
    assert rx.pastille([exp])[0] == "🔴"
    assert "run absent" in rx.markdown([exp], commande="test")


def test_la_decomposition_est_recalculee_depuis_les_trades(labo):
    v = _exp(labo).variantes[0]
    d = rx.decomposition(v.trades)
    assert d["r_brut"] == pytest.approx(0.6)            # (3 - 1 - 1 + 3 - 1) / 5
    assert d["cout_r"] == pytest.approx(0.1)
    assert d["r"] == pytest.approx(0.5)


# --- le rapport complet ---------------------------------------------------------------------------

def test_le_rapport_cite_le_preenregistrement_et_le_verdict_du_registre(labo):
    texte = rx.markdown([_exp(labo)], commande="scripts/rapport_experience.py TX")
    assert f"> {HYPOTHESE}" in texte
    assert "**INFIRMÉE** — ligne de clôture du registre" in texte
    assert "> texte de cloture du registre" in texte
    assert "- une reserve du moteur, telle quelle" in texte
    assert "0123456789abcdef" in texte
    assert texte.rstrip().endswith("sans interprétation.")


def test_sans_avis_fourni_le_rapport_n_a_aucune_section_de_claude(labo):
    assert "Avis de Claude" not in rx.markdown([_exp(labo)], commande="test")


def test_l_avis_de_claude_est_separe_et_marque(labo):
    texte = rx.markdown([_exp(labo)], commande="test", avis="Mon avis : a lire a part.")
    section = texte.split("## Avis de Claude — ce n'est PAS le programme", 1)
    assert len(section) == 2
    assert "Mon avis : a lire a part." in section[1]
    assert "Mon avis" not in section[0]


# --- le resume Discord ----------------------------------------------------------------------------

def test_le_resume_discord_n_a_pas_de_tableau_markdown(labo):
    texte = rx.resume([_exp(labo)], chemin_rapport="rapports/TX/RAPPORT.md")
    assert texte.startswith("# 🟢 Regle de test (1h) — rapport du programme")
    assert "|---" not in texte
    assert "**Verdicts au registre : TX INFIRMÉE.**" in texte
    assert "+12,50 %" in texte                           # le hold de S8, tel quel
    assert texte.rstrip().endswith("sans interprétation.")


def test_l_ecriture_pose_les_deux_fichiers(labo, monkeypatch):
    from beta.moteur import pipeline
    monkeypatch.setattr(pipeline, "RESULTATS", labo["runs"])
    chemins = rx.ecrire(["TX"], sortie=labo["chemin"] / "sortie")
    assert chemins["rapport"].read_text(encoding="utf-8").startswith("# Regle de test (1h)")
    assert chemins["resume"].exists() and chemins["epreuves"] is None


# --- format : les seuls arrondis ------------------------------------------------------------------

@pytest.mark.parametrize(("valeur", "attendu"), [
    ((-0.5652905604868422, 2, True), "−0,57"), ((0.0948, 4, True), "+0,0948"),
    ((float("nan"), 2, False), "—"), ((None, 2, False), "—")])
def test_les_nombres_s_ecrivent_a_la_francaise(valeur, attendu):
    assert rx.nb(*valeur) == attendu


def test_les_entiers_et_les_dates():
    assert rx.entier(108528) == "108 528"
    assert rx.date_fr("2026-11-04T12:48:33+00:00") == "04/11/2026 12:48 UTC"
    assert rx.date_fr("2023-06-21 00:00:00+00:00") == "21/06/2023"
