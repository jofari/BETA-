"""Outils communs aux scripts de mesure de la famille C2 (`scripts/mesurer_vc3.py`, `_vc4`,
`_vc5`). Jusqu'au 13/10, chaque script en portait sa copie (audit : `mesurer_vc5.py` identique a
85 % a `mesurer_vc3.py`) ; une correction devait etre faite trois fois.

Ces scripts ont deja rendu leurs verdicts (VC3 le 07/10, VC4 et VC5 le 10/10) : leur procedure
principale (`main`) reste dans chacun, telle qu'elle a tourne, et seules les fonctions
identiques sont venues ici, a l'identique (`tests/test_mesure_c2.py` le verifie contre les
anciennes copies). Relancer un de ces scripts serait une NOUVELLE mesure, a compter comme telle.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import math
import pathlib

import numpy as np
import pandas as pd

from beta.stats import multitest
from beta.strategies import voie_c2 as c2
from beta.strategies import voie_c_voltarget as vc

RACINE = pathlib.Path(__file__).resolve().parents[2]


def run_id(id_exp: str, signe: str) -> str:
    """L'identifiant d'une mesure : experience, empreinte de config et fenetre du backtest."""
    cle = f"{id_exp}|{signe}|{c2.DEPART_SIMULATION:%Y-%m-%d}|{c2.FIN_BACKTEST:%Y-%m-%d}"
    return hashlib.sha256(cle.encode()).hexdigest()[:12]


def voisin(cfg: dict, chemin: str, valeur, id_exp: str) -> dict:
    """La config de `id_exp` avec UN parametre change (chemin « bloc.cle » du preenregistrement)."""
    v = copy.deepcopy(cfg)
    bloc, cle = chemin.split(".")
    if cle not in v[bloc]:
        raise KeyError(f"voisin {chemin} : cle absente de la config {id_exp}")
    v[bloc][cle] = valeur
    v["version"] = f"{id_exp}~{chemin}={valeur}"
    return v


def references_vc2(d: dict, jours: pd.DatetimeIndex) -> dict[str, pd.Series]:
    """Les references de la mesure de VC2 (perpetuels), relues dans son script."""
    spec = importlib.util.spec_from_file_location("mesurer_vc2",
                                                  RACINE / "scripts" / "mesurer_vc2.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.references(d, jours)


def maxdd(r: np.ndarray) -> float:
    """Meme convention que `voie_c_voltarget.performance` : le plus haut part du PREMIER JOUR,
    pas du capital initial. C'est celle des mesures rendues, gardee pour les reproduire ; les
    suivis forward, eux, partent du capital initial depuis le 10/10 (une perte des le premier
    jour y est un drawdown). Sur cinq ans de backtest, l'ecart ne depasse pas la perte du
    premier jour."""
    equite = np.cumprod(1.0 + np.asarray(r, dtype=float))
    return float((equite / np.maximum.accumulate(equite) - 1.0).min())


def sharpe_an(r: np.ndarray) -> float:
    """Sharpe annualise a la convention des voies C (racine de 252, cf. `vc.PPA`)."""
    return multitest.sharpe(r) * math.sqrt(vc.PPA)


def ligne(nom: str, r: pd.Series, extra: str = "") -> str:
    p = vc.performance(r)
    return (f"  {nom:<34s} Sharpe {p['sharpe']:5.2f} | CAGR {p['cagr']:7.1%} | "
            f"vol {p['vol']:5.1%} | maxDD {p['mdd']:7.1%}{extra}")


def pire_baisse(r: pd.Series) -> tuple[pd.Timestamp, pd.Timestamp, float]:
    """Le sommet, le creux et la profondeur de la pire baisse."""
    equite = (1.0 + r).cumprod()
    dd = equite / equite.cummax() - 1.0
    creux = dd.idxmin()
    sommet = equite.loc[:creux].idxmax()
    return sommet, creux, float(dd.min())
