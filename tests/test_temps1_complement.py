"""T1C (complement ETH et SOL du Temps 1, Jonas 01/11/2026) : ce que ces tests protegent.

Le gel (regles, texte du preenregistrement, marque diagnostic) ; les modules de T1J et de T1F
identiques a leurs commits ; sigma_SP_ref recalcule sur la copie figee de T1J ; la lecture des
copies figees (SHA-256, convention du jour UTC, coupe a la date de fin) ; la regle de decision
(p_justesse < 0,05 strict) ; l'actif indecidable ; l'epreuve de causalite ; le rapport. Aucun
calcul n'est fait sur les vraies donnees d'ETH ou de SOL ici : series synthetiques seulement.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd
import pytest

from beta.protocole import experiences
from beta.temps1_complement import campagne as ca
from beta.temps1_complement import donnees as dc
from beta.temps1_complement import regles as R
from beta.temps1_fiabilite import regles as RF


def _cycles(n: int = 2555, debut: str = "2015-01-01", graine: int = 3) -> pd.Series:
    """Prix synthetique a grands cycles (bears et bulls nets) plus une marche aleatoire."""
    rng = np.random.default_rng(graine)
    t = np.arange(n)
    lp = np.log(100.0) + 1.2 * np.sin(2 * np.pi * t / 700) + np.cumsum(rng.normal(0, 0.01, n))
    return pd.Series(np.exp(lp), index=pd.date_range(debut, periods=n, freq="D"), name="close")


def _hausse(n: int = 2555, debut: str = "2015-01-01", graine: int = 4) -> pd.Series:
    """Prix qui ne fait que monter, a un bruit stationnaire pres : aucun bear du juge."""
    rng = np.random.default_rng(graine)
    lp = np.log(100.0) + 0.002 * np.arange(n) + rng.normal(0, 0.005, n)
    return pd.Series(np.exp(lp), index=pd.date_range(debut, periods=n, freq="D"), name="close")


def test_t1c_est_un_diagnostic_gele_qui_ne_compte_pas():
    pre = ca.verifier_gel()
    assert pre["diagnostic"] is True and pre["famille_compteur"] == "invest"
    assert pre["empreinte"] == R.empreinte() == "56f2183129b16e66"
    assert pre["empreinte_preenregistrement"] == ca.empreinte_texte()
    assert R.ID_EXP not in {x.get("experience") for x in experiences.runs_journalises()}


def test_les_modules_du_temps1_sont_ceux_de_leurs_commits():
    assert ca.verifier_modules() == []


def test_sigma_sp_ref_recalcule_sur_la_copie_figee_de_t1j():
    assert dc.sigma_sp_ref() == R.SIGMA_SP_REF_T1J


def test_la_copie_est_verifiee_par_son_sha256_et_coupee_a_la_fin(tmp_path, monkeypatch):
    jours = pd.date_range("2026-10-25", "2026-11-02", freq="D", tz="UTC")
    df = pd.DataFrame({"date": jours, "open": 1.0, "high": 1.0, "low": 1.0,
                       "close": np.arange(1.0, len(jours) + 1), "volume": 1.0})
    chemin = tmp_path / "X_1d.parquet"
    df.to_parquet(chemin, index=False)
    bon = hashlib.sha256(chemin.read_bytes()).hexdigest()
    monkeypatch.setattr(R, "ACTIFS", {"X": {"copie": str(chemin), "sha256": bon, "serie": "x"}})
    s = dc.close("X")
    assert s.index.tz is None and s.index.max() == pd.Timestamp(R.FIN)
    assert s.loc[pd.Timestamp("2026-10-25")] == 1.0               # jour D = bougie ouverte en D
    assert dc.couverture(s) == {"debut": "2026-10-25", "fin": "2026-10-31", "n": 7,
                                "jours_manquants": 0}
    monkeypatch.setattr(R, "ACTIFS", {"X": {"copie": str(chemin), "sha256": "0" * 64,
                                            "serie": "x"}})
    with pytest.raises(dc.DonneesError, match="change depuis le gel"):
        dc.close("X")


def test_regle_de_decision_stricte():
    assert ca.decision(0.0499) == ca.RETENU
    assert ca.decision(0.05) == ca.SINON
    assert ca.decision(0.9) == ca.SINON
    assert ca.decision(None) == ca.INDECIDABLE


def test_un_actif_synthetique_de_bout_en_bout(monkeypatch):
    monkeypatch.setattr(RF, "N_TIRAGES", 30)
    close = _cycles()
    a = ca.mesurer_actif(close, R.SIGMA_SP_REF_T1J)
    assert a["statut"] == ca.decision(a["test_1"]["p_justesse"])
    assert a["observe"]["n_bears"] >= 1 and a["causalite"] == []
    assert len(a["tirages"]["test_1"]["justesse"]) == 30
    assert all(b["dans_m"] for b in a["juge"]["bears"]
               if a["observe"]["mesuree"][0] <= b["pic"] and b["creux"] <= a["plage"]["fin"])
    b = ca.mesurer_actif(close, R.SIGMA_SP_REF_T1J)                   # graine 0 : reproductible
    assert a["test_1"] == b["test_1"] and a["test_1_bis"] == b["test_1_bis"]


def test_un_actif_sans_bear_complet_est_indecidable():
    a = ca.mesurer_actif(_hausse(), R.SIGMA_SP_REF_T1J)
    assert a["statut"] == ca.INDECIDABLE and "pivots" in a["raison"]
    assert "test_1" not in a


def test_l_epreuve_de_causalite_attrape_un_regard_vers_le_futur(monkeypatch):
    close = _cycles()
    assert ca.causalite(close) == []

    def centree(c, n):
        return c.rolling(n, center=True, min_periods=1).mean()

    monkeypatch.setattr(ca.det, "sma", centree)
    assert ca.causalite(close) != []


def test_le_rapport_s_ecrit_sur_une_synthese_fabriquee(tmp_path, monkeypatch):
    from beta.temps1_complement import rapport

    monkeypatch.setattr(RF, "N_TIRAGES", 30)
    actifs = {}
    for nom, close in (("ETH", _cycles()), ("SOL", _hausse())):
        actifs[nom] = {"couverture": dc.couverture(close),
                       **ca.mesurer_actif(close, R.SIGMA_SP_REF_T1J)}
    s = ca._propre({
        "experience": R.ID_EXP, "code": "x", "regles": R.empreinte(), "preenregistrement": "p",
        "modules": {"t1j": R.COMMIT_JUSTESSE, "t1f": R.COMMIT_FIABILITE, "identiques": True},
        "calcule_le": "2026-11-01T00:00:00+00:00",
        "donnees": {"empreinte": "e", "fin": R.FIN,
                    "copies": {a: {"copie": "c", "sha256": "h", "serie": "s"} for a in actifs}},
        "sigma_sp_ref": R.SIGMA_SP_REF_T1J, "regles_t1j": "r", "regles_t1f": "f",
        "tirages_par_test": 30, "graine": 0,
        "compteur": {"avant": {"global": 1, "invest": 1, "trading": 0},
                     "apres": {"global": 1, "invest": 1, "trading": 0}, "diagnostic": True},
        "actifs": actifs})
    md = rapport.markdown(s)
    for titre in ("## 1. Résultat par actif", "### ETH", "### SOL", "## 2. Empreintes",
                  "## 3. Les bears du juge", "## 4. Mesures observées", "## 5. Tests contre",
                  "## 6. Test 2", "## 7. Épreuve de causalité", "## 8. Écarts"):
        assert titre in md
    assert "| p_justesse | fiabilité | phases baissières couvertes | période |" in md
    assert "**Conclusion SOL : indécidable**" in md
    assert ("**Conclusion ETH : retenu**" in md) or ("**Conclusion ETH : non retenu**" in md)
    monkeypatch.setattr(ca, "SORTIE", tmp_path)
    rapport.ecrire(s)
    for f in ("RAPPORT_COMPLEMENT.md", "RAPPORT_COMPLEMENT.csv",
              "RAPPORT_COMPLEMENT_episodes.csv", "RESUME_DISCORD.md"):
        assert (tmp_path / f).exists()
    assert "🟠" in (tmp_path / "RESUME_DISCORD.md").read_text(encoding="utf-8")
