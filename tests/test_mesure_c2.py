"""Les fonctions communes des mesures C2 (13/10) rendent exactement ce que rendaient les copies
de `mesurer_vc3.py`, `_vc4` et `_vc5` : les verdicts deja rendus restent reproductibles."""

import copy
import hashlib
import importlib.util
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from beta.stats import multitest
from beta.strategies import mesure_c2 as mc
from beta.strategies import voie_c2 as c2
from beta.strategies import voie_c_voltarget as vc

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


# --- les anciennes copies, recopiees telles qu'elles etaient au commit a689fe5 --------------

def ancien_run_id(id_exp, signe):
    cle = f"{id_exp}|{signe}|{c2.DEPART_SIMULATION:%Y-%m-%d}|{c2.FIN_BACKTEST:%Y-%m-%d}"
    return hashlib.sha256(cle.encode()).hexdigest()[:12]


def ancien_voisin(cfg, chemin, valeur, ID):
    v = copy.deepcopy(cfg)
    bloc, cle = chemin.split(".")
    if cle not in v[bloc]:
        raise KeyError(f"voisin {chemin} : cle absente de la config {ID}")
    v[bloc][cle] = valeur
    v["version"] = f"{ID}~{chemin}={valeur}"
    return v


def ancien_maxdd(r):
    equite = np.cumprod(1.0 + np.asarray(r, dtype=float))
    return float((equite / np.maximum.accumulate(equite) - 1.0).min())


def ancien_sharpe_an(r):
    return multitest.sharpe(r) * math.sqrt(vc.PPA)


def ancien_ligne(nom, r, extra=""):
    p = vc.performance(r)
    return (f"  {nom:<34s} Sharpe {p['sharpe']:5.2f} | CAGR {p['cagr']:7.1%} | "
            f"vol {p['vol']:5.1%} | maxDD {p['mdd']:7.1%}{extra}")


def ancien_pire_baisse(r):
    equite = (1.0 + r).cumprod()
    dd = equite / equite.cummax() - 1.0
    creux = dd.idxmin()
    sommet = equite.loc[:creux].idxmax()
    return sommet, creux, float(dd.min())


# --------------------------------------------------------------------------------------------

def _rendements(graine):
    rng = np.random.default_rng(graine)
    jours = pd.date_range("2021-06-12", periods=400, freq="D", tz="UTC")
    return pd.Series(rng.normal(0.0005, 0.03, len(jours)), index=jours)


@pytest.mark.parametrize("graine", [0, 1, 2])
def test_les_fonctions_numeriques_sont_identiques(graine):
    r = _rendements(graine)
    assert mc.maxdd(r.to_numpy()) == ancien_maxdd(r.to_numpy())
    assert mc.sharpe_an(r.to_numpy()) == ancien_sharpe_an(r.to_numpy())
    assert mc.ligne("VC3", r, " | x") == ancien_ligne("VC3", r, " | x")
    assert mc.pire_baisse(r) == ancien_pire_baisse(r)


def test_identifiants_et_voisins_identiques():
    assert mc.run_id("VC5", "abc123") == ancien_run_id("VC5", "abc123")
    cfg = c2.config("VC3")
    for id_exp in ("VC3", "VC4", "VC5"):
        assert mc.voisin(cfg, "haussier.bande", 0.1, id_exp) == \
            ancien_voisin(cfg, "haussier.bande", 0.1, id_exp)
    with pytest.raises(KeyError, match="config VC4"):
        mc.voisin(cfg, "haussier.inexistante", 1, "VC4")


@pytest.mark.parametrize("nom", ["mesurer_vc3", "mesurer_vc4", "mesurer_vc5"])
def test_les_scripts_utilisent_le_module_commun(nom):
    spec = importlib.util.spec_from_file_location(nom, SCRIPTS / f"{nom}.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)                 # charge le module, ne lance pas main()
    assert script.maxdd is mc.maxdd and script.run_id is mc.run_id
    assert script.voisin(c2.config("VC3"), "haussier.bande", 0.1)["version"] == \
        f"{script.ID}~haussier.bande=0.1"
