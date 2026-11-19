"""Momentum trente jours sur le BTC avec garde de baisse - moteur du test invest MOMENTUM30_BTC_GARDE.

Fonctions pures. Tout ce qui n'est pas la garde est REPRIS tel quel de MOMENTUM30_BTC
(`beta.momentum30_btc.moteur` : rendements, funding, couts, metriques, nulls, hold, temoin),
pour que la seule difference entre les deux tests soit la garde. Les regles viennent de
MOMENTUM30_BTC_GARDE/PREENREGISTREMENT.md, dont l'empreinte est au registre.

La garde (application 3 du preenregistrement) :
- signal de base a la cloture de t : s(t) = 1 si close(t) / close(t - 30) - 1 > 0, sinon 0 ;
- un EPISODE est une suite de jours de decision ou s = 1 ; il commence a la premiere cloture
  ou s passe a 1 (ou a la premiere decision si s = 1 des le depart) ;
- plus haut de l'episode : max des clotures depuis la cloture d'entree incluse ;
- garde declenchee a la cloture de t si close(t) / plus_haut - 1 <= -SEUIL_GARDE ; elle reste
  declenchee jusqu'a la fin de l'episode (s repasse a 0) ;
- exposition du jour t + 1 : 1 si s(t) = 1 ET garde non declenchee, sinon 0.
On ne rentre donc qu'au signal NEUF suivant (s passe a 0, puis de nouveau a 1).
"""

from __future__ import annotations

import math

import numpy as np

from beta.momentum30_btc import moteur as base

LOOKBACK = base.LOOKBACK          # 30, identique a MOMENTUM30_BTC
SEUIL_GARDE = 0.20                # sortie a -20 % sous le plus haut de l'episode
KAPPA_PB = base.KAPPA_PB
ID_EXPERIENCE = "MOMENTUM30_BTC_GARDE"
CONFIRMEE, INFIRMEE, INDECIDABLE = base.CONFIRMEE, base.INFIRMEE, base.INDECIDABLE

rendements_bruts = base.rendements_bruts
funding_journalier = base.funding_journalier
rendement_net = base.rendement_net
evaluer = base.evaluer
hold = base.hold
temoin_constant = base.temoin_constant
par_annee = base.par_annee


def exposition(close: np.ndarray, lookback: int = LOOKBACK,
               seuil: float = SEUIL_GARDE) -> tuple[np.ndarray, np.ndarray]:
    """(e, garde) alignes sur les jours : e[i] = exposition tenue le jour i, decidee a la
    cloture de i - 1 ; garde[i] = 1 si la garde coupe le jour i (signal de base a 1 mais sorti).
    NaN avant le warm-up. Causale : e[i] ne lit que close[:i]."""
    close = np.asarray(close, dtype=float)
    n = len(close)
    e = np.full(n, np.nan)
    g = np.full(n, np.nan)
    s_prec, plus_haut, declenchee = 0.0, float("nan"), False
    for t in range(lookback, n - 1):           # decision a la cloture de t, pour le jour t + 1
        s = 1.0 if close[t] / close[t - lookback] - 1.0 > 0.0 else 0.0
        if s == 0.0:
            plus_haut, declenchee = float("nan"), False
        else:
            if s_prec == 0.0:                   # nouvel episode : entree a la cloture de t
                plus_haut, declenchee = close[t], False
            else:
                plus_haut = max(plus_haut, close[t])
            if not declenchee and close[t] / plus_haut - 1.0 <= -seuil:
                declenchee = True
        e[t + 1] = 1.0 if (s == 1.0 and not declenchee) else 0.0
        g[t + 1] = 1.0 if (s == 1.0 and declenchee) else 0.0
        s_prec = s
    return e, g


def _sharpe(e, r_b, phi, rf, kappa_pb=KAPPA_PB) -> float:
    return base._sharpe(e, r_b, phi, rf, kappa_pb)


def nulls_sharpe(e, r_b, phi, rf, kappa_pb=KAPPA_PB, b=base.B_NULLS, graine=0) -> dict:
    """Les deux nulls du test invest (identiques a MOMENTUM30_BTC), flux propres a cet id."""
    return base.nulls_sharpe(e, r_b, phi, rf, kappa_pb, b, graine, id_exp=ID_EXPERIENCE)


def conditions(strategie: dict, reference: dict, sans_garde: dict) -> dict:
    """Les cinq conditions de la regle : (a)-(c) contre le hold, (d)-(e) contre le meme
    momentum SANS garde (MOMENTUM30_BTC recalcule sur les memes donnees)."""
    c = base.conditions(strategie, reference)
    c["drawdown_moins_profond_que_sans_garde"] = bool(strategie["mdd"] > sans_garde["mdd"])
    c["sharpe_au_moins_egal_sans_garde"] = bool(
        strategie["sharpe"] is not None and sans_garde["sharpe"] is not None
        and strategie["sharpe"] >= sans_garde["sharpe"])
    return c


def verdict(cond: dict, p_retenue: float | None) -> str:
    """confirmee : les cinq conditions ET p retenue < 0,05 ; indecidable : les cinq ET
    0,05 <= p < 0,20, ou p incalculable ; infirmee : une condition fausse ou p >= 0,20."""
    if not all(cond.values()):
        return INFIRMEE
    if p_retenue is None or (isinstance(p_retenue, float) and math.isnan(p_retenue)):
        return INDECIDABLE
    if p_retenue < base.SEUIL_REEL:
        return CONFIRMEE
    if p_retenue < base.SEUIL_HASARD:
        return INDECIDABLE
    return INFIRMEE
