"""Tests des donnees de strategie et du protocole experimental.

Deux pieges valent a eux seuls la moitie de ce fichier, parce que tous deux produisent des
chiffres FAUX ET CREDIBLES — la pire categorie de panne :

1. le R calcule depuis le stoploss de secours de freqtrade (-0,99) au lieu du stop
   structurel : le R devient numeriquement egal au rendement, avec un ecart-type de 0,02 la
   ou un vrai R vaut ~1,1 ;
2. `ts_utc` du journal, qui porte l'heure d'EXECUTION du backtest sur les evenements
   `gestion` : cinq ans d'historique basculent dans le hold-out et toute mesure se vide.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pandas as pd
import pytest

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from beta.lake import strategie  # noqa: E402
from beta.protocole import experiences, holdout  # noqa: E402
from beta.stats import descriptif  # noqa: E402

# --- le piege des dates ---------------------------------------------------------------

def test_ts_depuis_signal_id():
    ts = strategie._ts_depuis_signal_id("BNBUSDT-2021.01.05.T000000Z")
    assert ts == pd.Timestamp("2021-01-05 00:00:00", tz="UTC")


def test_ts_depuis_signal_id_tolere_les_formes_inattendues():
    for entree in (None, "", "sans-separateur-valide", 42, "PAIRE-pas-une-date"):
        assert pd.isna(strategie._ts_depuis_signal_id(entree))


def test_horodatage_prefere_le_signal_id_a_ts_utc():
    """Le cas reel : un evenement de 2021 horodate 2026 par le backtest qui l'a produit."""
    df = pd.DataFrame({"signal_id": ["SOLUSDT-2021.01.09.T040000Z"],
                       "ts_utc": ["2026-08-04T15:28:50+00:00"]})
    out = strategie._horodater(df)
    assert out["ts_bougie"].iloc[0] == pd.Timestamp("2021-01-09 04:00", tz="UTC")
    assert out["split"].iloc[0] == holdout.TRAIN     # et NON holdout, comme avec ts_utc


def test_horodatage_replie_sur_ts_utc_si_signal_id_absent():
    df = pd.DataFrame({"ts_utc": ["2021-03-01T00:00:00+00:00"]})
    out = strategie._horodater(df)
    assert out["ts_bougie"].iloc[0] == pd.Timestamp("2021-03-01", tz="UTC")


# --- le piege du R --------------------------------------------------------------------

def test_risque_unitaire():
    assert strategie._risque_unitaire(100.0, 95.0) == pytest.approx(5.0)
    assert strategie._risque_unitaire(95.0, 100.0) == pytest.approx(5.0)   # short


def test_risque_unitaire_refuse_de_rendre_un_nombre_faux():
    for entree, sl in ((100.0, 100.0), (100.0, None), (None, 95.0), (0, 95.0)):
        assert pd.isna(strategie._risque_unitaire(entree, sl))


def _trade(prix=100.0, rendement_pct=2.0, favorable=106.0, adverse=99.0):
    return pd.DataFrame([{
        "paire": "BTC/USDT:USDT", "ts_entree": pd.Timestamp("2021-01-05", tz="UTC"),
        "prix_entree": prix, "rendement_pct": rendement_pct, "sl_initial": float("nan"),
        "r": float("nan"), "mfe_r": float("nan"), "mae_r": float("nan"),
        "_favorable": favorable, "_adverse": adverse, "_signe": 1.0,
    }])


def _entree_journal(sl=95.0):
    return pd.DataFrame([{"pair": "BTC/USDT:USDT", "ts_utc": "2021-01-05T00:00:00+00:00",
                          "sl_initial": sl, "conviction": 0.7, "regime": "TREND"}])


def test_r_calcule_depuis_le_stop_du_journal():
    """+2 % sur un prix de 100 avec un stop a 95 : risque 5, gain 2 -> R = 0,4."""
    out = strategie.attacher_stop_du_journal(_trade(), _entree_journal())
    assert out["r"].iloc[0] == pytest.approx(0.4)
    assert out["mfe_r"].iloc[0] == pytest.approx(1.2)      # (106-100)/5
    assert out["mae_r"].iloc[0] == pytest.approx(-0.2)     # (99-100)/5
    assert out["sl_initial"].iloc[0] == 95.0


def test_r_reste_nan_sans_stop_retrouve():
    """Mieux vaut un trou declare qu'un R invente."""
    orphelin = _entree_journal()
    orphelin["ts_utc"] = "2021-06-01T00:00:00+00:00"     # ne correspond a aucun trade
    out = strategie.attacher_stop_du_journal(_trade(), orphelin)
    assert pd.isna(out["r"].iloc[0])


def test_colonnes_internes_retirees_apres_jointure():
    out = strategie.attacher_stop_du_journal(_trade(), _entree_journal())
    assert not [c for c in out.columns if c.startswith("_")]


def test_journal_vide_ne_fait_pas_tomber_l_import():
    out = strategie.attacher_stop_du_journal(_trade(), pd.DataFrame())
    assert len(out) == 1 and pd.isna(out["r"].iloc[0])


# --- lecture des sources ---------------------------------------------------------------

def test_lire_zip_absent():
    with pytest.raises(strategie.StrategieError):
        strategie.lire_zip(pathlib.Path("nexistepas.zip"))


def test_chemin_table_refuse_une_table_inconnue():
    with pytest.raises(strategie.StrategieError, match="table inconnue"):
        strategie.chemin_table("inventee")


# --- hold-out ---------------------------------------------------------------------------

def test_split_coupe_a_la_date_scellee():
    dates = pd.Series(pd.to_datetime(["2024-12-31", "2025-01-01", "2025-06-01"], utc=True))
    assert holdout.split(dates).tolist() == [holdout.TRAIN, holdout.HOLDOUT,
                                             holdout.HOLDOUT]


def test_une_lecture_de_train_s_arrete_avant_la_premiere_bougie_du_hold_out():
    """Audit du 13/10 : `lecture.load` a des bornes INCLUSIVES ; couper a 2025-01-01 lisait
    la bougie qui ouvre a 00:00 ce jour-la — une journee entiere de hold-out en 1d."""
    assert holdout.borner_train() == "2024-12-31T23:59:59.999999"
    assert pd.Timestamp(holdout.borner_train(), tz="UTC") < holdout.DEBUT
    assert holdout.borner_train("2023-06-01") == "2023-06-01T00:00:00"
    assert holdout.borner_train("2026-03-01") == holdout.borner_train()
    assert holdout.borner_train("2025-03-01T00:00:00+00:00") == holdout.borner_train()


def test_le_pipeline_ne_lit_plus_la_bougie_du_1er_janvier():
    from types import SimpleNamespace

    from beta.moteur import pipeline
    train = SimpleNamespace(split=holdout.TRAIN, debut=None, fin=None)
    _, fin = pipeline._bornes_du_split(train)
    assert pd.Timestamp(fin, tz="UTC") < holdout.DEBUT
    tard = SimpleNamespace(split=holdout.TRAIN, debut=None, fin="2026-01-01")
    assert pipeline._bornes_du_split(tard)[1] == fin
    hold = SimpleNamespace(split=holdout.HOLDOUT, debut=None, fin=None)
    assert pipeline._bornes_du_split(hold)[0] == "2025-01-01"


def test_l_outil_mcp_ne_sert_pas_le_hold_out(monkeypatch):
    """Un agent passait par `beta_load_ohlcv` pour lire 2025+ sans aucune garde."""
    from beta.lake import lecture
    from beta.mcp import serveur
    lu = {}

    def faux_load(paire, timeframe, debut=None, fin=None):
        lu["fin"] = fin
        return pd.DataFrame({"date": pd.to_datetime(["2024-12-31"], utc=True), "close": [1.0]})

    monkeypatch.setattr(lecture, "load", faux_load)
    rendu = serveur._ohlcv("BTC", "1d", fin="2026-10-01")
    assert pd.Timestamp(lu["fin"], tz="UTC") < holdout.DEBUT
    assert rendu["fin_lue"] == lu["fin"] and "2025-01-01" in rendu["hold_out_exclu"]


# --- protocole : le verrou --------------------------------------------------------------

@pytest.fixture
def registre(tmp_path):
    return tmp_path / "EXPERIMENTS.jsonl"


def test_exiger_refuse_une_experience_non_preenregistree(registre):
    with pytest.raises(experiences.ProtocoleError, match="non preenregistree"):
        experiences.exiger("jamais-declaree", registre)


def test_exiger_refuse_un_preenregistrement_incomplet(registre):
    registre.write_text(json.dumps({"id": "x", "hypothese": "quelque chose"}) + "\n",
                        encoding="utf-8")
    with pytest.raises(experiences.ProtocoleError, match="incomplet"):
        experiences.exiger("x", registre)


def test_preenregistrer_puis_exiger(registre):
    experiences.preenregistrer("essai-1", hypothese="H", metrique_primaire="R moyen",
                               regle_de_decision={"ok": "R > 0"}, chemin=registre)
    entree = experiences.exiger("essai-1", registre)
    assert entree["statut"] == "preenregistre"
    assert entree["split_autorise"] == "train"


def test_preenregistrer_refuse_d_ecraser(registre):
    experiences.preenregistrer("essai-1", hypothese="H", metrique_primaire="R",
                               regle_de_decision={"ok": "x"}, chemin=registre)
    with pytest.raises(experiences.ProtocoleError, match="deja preenregistre"):
        experiences.preenregistrer("essai-1", hypothese="H2", metrique_primaire="R",
                                   regle_de_decision={"ok": "y"}, chemin=registre)


def test_clore_conserve_le_preenregistrement(registre):
    experiences.preenregistrer("essai-1", hypothese="H", metrique_primaire="R",
                               regle_de_decision={"ok": "x"}, issue_attendue="indecidable",
                               chemin=registre)
    fin = experiences.clore("essai-1", verdict="indecidable", resultat="n trop petit",
                            chemin=registre)
    assert fin["conforme_a_l_issue_attendue"] is True
    assert len(registre.read_text(encoding="utf-8").strip().splitlines()) == 2
    assert experiences.etat(registre)["essai-1"]["statut"] == "clos"


def test_compteur_part_de_la_dette_et_ne_redescend_pas(registre):
    assert experiences.compteur(registre) == experiences.ESSAIS_INITIAUX
    experiences.preenregistrer("a", hypothese="H", metrique_primaire="R",
                               regle_de_decision={"ok": "x"}, chemin=registre)
    experiences.clore("a", verdict="v", resultat="r", chemin=registre)
    assert experiences.compteur(registre) == experiences.ESSAIS_INITIAUX + 1


# --- deux compteurs : trading actif et invest (Jonas, 23/10) ------------------------------

def _preenregistrer(id_exp, registre, **options):
    return experiences.preenregistrer(id_exp, hypothese="H", metrique_primaire="R",
                                      regle_de_decision={"ok": "x"}, chemin=registre,
                                      **options)


def test_un_test_invest_ne_touche_pas_au_compteur_du_trading_actif(registre):
    _preenregistrer("I1", registre, famille_compteur="invest")
    assert experiences.compteur(registre, famille="invest") == 1
    assert experiences.compteur(registre, famille="trading") == 30


def test_un_test_sans_famille_declaree_compte_en_trading_actif(registre):
    _preenregistrer("T1", registre)
    assert experiences.compteur(registre, famille="trading") == 31
    assert experiences.compteur(registre, famille="invest") == 0


def test_une_mesure_compte_dans_la_famille_de_son_experience(registre):
    _preenregistrer("I1", registre, famille_compteur="invest")
    runs = registre.parent / "RUNS.jsonl"
    for rid in ("r1", "r2", "r3"):
        experiences.enregistrer_run(rid, "I1", "c", "e", chemin=runs)
    assert experiences.compteur(registre, famille="invest") == 3
    assert experiences.compteur(registre, famille="trading") == 30


def test_l_historique_sans_famille_range_ti1_et_t1a_en_invest(registre):
    """Les lignes d'avant le 23/10 n'ont pas de famille : TI1 et T1A sont de l'invest, tout
    le reste (les 93 de Jonas) du trading actif."""
    lignes = [{"id": i, "statut": "preenregistre", "hypothese": "H", "metrique_primaire": "R",
               "regle_de_decision": {"ok": "x"}, "split_autorise": "train"}
              for i in ("R7", "VC3", "TI1", "T1A")]
    registre.write_text("".join(json.dumps(x) + "\n" for x in lignes), encoding="utf-8")
    assert experiences.compteur(registre, famille="invest") == 2
    assert experiences.compteur(registre, famille="trading") == 32


def test_le_total_additionne_les_deux_familles(registre):
    _preenregistrer("I1", registre, famille_compteur="invest")
    _preenregistrer("T1", registre)
    assert experiences.compteur_total(registre) == 32


def test_le_preenregistrement_porte_sa_famille_et_son_rang_dans_la_famille(registre):
    _preenregistrer("T1", registre)
    entree = _preenregistrer("I1", registre, famille_compteur="invest")
    assert entree["famille_compteur"] == "invest"
    assert entree["n_essais_cumules"] == 1


def test_un_diagnostic_est_journalise_sans_avancer_le_compteur(registre):
    """T1F (Jonas 24/10) : ecrit au registre, aucune hypothese en attente comptee."""
    entree = _preenregistrer("D1", registre, famille_compteur="invest", diagnostic=True)
    assert entree["diagnostic"] is True and entree["n_essais_cumules"] == 0
    assert experiences.etat(registre)["D1"]["statut"] == "preenregistre"
    assert experiences.compteur(registre, famille="invest") == 0
    experiences.marquer_mesuree("D1", "x", "diagnostic", chemin=registre)
    assert experiences.etat(registre)["D1"]["diagnostic"] is True     # la fusion le garde
    assert experiences.compteur(registre, famille="invest") == 0
    _preenregistrer("I1", registre, famille_compteur="invest")
    assert experiences.compteur(registre, famille="invest") == 1


def test_une_mesure_journalisee_sous_un_diagnostic_compte_quand_meme(registre):
    _preenregistrer("D1", registre, famille_compteur="invest", diagnostic=True)
    experiences.enregistrer_run("r1", "D1", "c", "e", chemin=registre.parent / "RUNS.jsonl")
    assert experiences.compteur(registre, famille="invest") == 1


def test_une_famille_inconnue_est_refusee(registre):
    with pytest.raises(experiences.ProtocoleError, match="famille"):
        _preenregistrer("X1", registre, famille_compteur="swing")
    with pytest.raises(experiences.ProtocoleError, match="famille"):
        experiences.compteur(registre, famille="swing")


def test_n_essais_pour_lit_le_compteur_de_la_famille_de_l_experience(registre):
    _preenregistrer("T1", registre)
    _preenregistrer("I1", registre, famille_compteur="invest")
    assert experiences.n_essais_pour("I1", registre) == 1
    assert experiences.n_essais_pour("T1", registre) == 31


def test_le_detail_d_une_famille_separe_dette_mesures_et_attente(registre):
    _preenregistrer("I1", registre, famille_compteur="invest")
    _preenregistrer("I2", registre, famille_compteur="invest")
    _preenregistrer("T1", registre)
    for rid in ("r1", "r2"):
        experiences.enregistrer_run(rid, "I1", "c", "e", chemin=registre.parent / "RUNS.jsonl")
    assert experiences.detail_compteur(registre, famille="invest") == {
        "famille": "invest", "dette": 0, "mesures": 2, "en_attente": 1, "total": 3}


def test_marquer_mesuree_note_le_compteur_de_la_famille(registre):
    _preenregistrer("T1", registre)
    _preenregistrer("I1", registre, famille_compteur="invest")
    experiences.enregistrer_run("r1", "I1", "c", "e", chemin=registre.parent / "RUNS.jsonl")
    entree = experiences.marquer_mesuree("I1", "r1", "mesure", registre)
    assert entree["n_essais_cumules"] == 1


# --- statistiques descriptives ------------------------------------------------------------

def _trades(rs):
    return pd.DataFrame({"r": rs, "rendement_pct": [r * 2 for r in rs]})


def test_resumer_calcule_r_et_mde():
    resume = descriptif.resumer(_trades([1.5, -1.0, 1.5, -1.0]))
    assert resume["n"] == 4
    assert resume["r_moyen"] == pytest.approx(0.25)
    assert resume["win_rate"] == pytest.approx(0.5)
    assert resume["mde_r"] > 0


def test_resumer_ensemble_vide():
    assert descriptif.resumer(pd.DataFrame()) == {"n": 0}


def test_mde_decroit_avec_n():
    assert descriptif.mde(400, 1.2) < descriptif.mde(50, 1.2) < descriptif.mde(5, 1.2)


def test_mde_nan_sur_echantillon_inexploitable():
    assert pd.isna(descriptif.mde(1, 1.2))
    assert pd.isna(descriptif.mde(50, float("nan")))


def test_profit_factor_sans_perte_est_nan():
    """Un `inf` contaminerait toute moyenne qui le croiserait."""
    assert pd.isna(descriptif.profit_factor(pd.Series([1.0, 2.0])))


def test_profit_factor():
    assert descriptif.profit_factor(pd.Series([3.0, -1.0])) == pytest.approx(3.0)


def test_par_ventile_et_conserve_les_petits_groupes():
    trades = _trades([1.0, -1.0, 1.0])
    trades["paire"] = ["BTC", "BTC", "ETH"]
    out = descriptif.par(trades, "paire")
    assert set(out["paire"]) == {"BTC", "ETH"}
    assert out.loc[out["paire"] == "ETH", "n"].iloc[0] == 1


def test_raisons_de_rejet_compte_les_portes():
    ev = pd.DataFrame({"failed_gate": ["news_window", "news_window", None]})
    out = descriptif.raisons_de_rejet(ev)
    assert out.loc[out["failed_gate"] == "news_window", "n"].iloc[0] == 2
    assert out["part_pct"].sum() == pytest.approx(100.0)
