"""Voie C — la config retenue le 03/10, passee par les garde-fous du banc.

    ARIT_HOME=/root/ARIT2.0 PYTHONPATH=/root/BETA- \
        /root/venvs/arit/bin/python beta/strategies/voie_c_verif.py

Config : cible 20 %, ecart-type glissant 30 j, levier borne [0,25 ; 3], hysteresis 0,25 sur
le levier, reequilibrage quotidien avec bande de 20 %. Les jambes sont celles de
`voie_c_voltarget`, inchangees.

Ce que ce script verifie, et seulement ca :

1. CAUSALITE de toute la chaine (poids, sigma, levier, hysteresis, positions cibles) :
   recalculee sur la serie tronquee aux 2/3, elle doit rendre exactement le debut de la
   chaine complete — trous compris.
2. S2 Sharpe degonfle, avec N = compteur cumulatif du banc + toutes les configs regardees
   pour la voie C (grille 5760 + mesures du 22/09 + variantes du 03/10).
3. Bootstrap par blocs : intervalle du rendement quotidien moyen, TRAIN et OOS.
4. S7 Reality Check sur l'excedent contre BTC buy & hold, univers = les variantes de
   levier du 03/10 (la gagnante prise isolement n'a pas de p-value).

Ces outils ne peuvent que rendre un resultat PIRE. Rien n'est charge apres FIN_VUE.
"""

from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd

from beta.protocole import experiences
from beta.stats import bootstrap, multitest
from beta.strategies import voie_c_optim as vo
from beta.strategies import voie_c_voltarget as vc

log = logging.getLogger("beta.strategies.voie_c_verif")

CONFIG = {"cible": 0.20, "fenetre": 30, "lmin": 0.25, "lmax": 3.0, "seuil_levier": 0.25,
          "pas": 1, "bande": 0.20}

# Configs regardees pour la voie C, hors compteur du banc (scripts de mesure, pas de run
# journalise) : grille du 03/10 + 30 lignes du 22/09 + ~20 variantes de phase/levier du 03/10.
ESSAIS_VOIE_C = 5760 + 30 + 20


def hysteresis(levier: pd.Series, seuil: float) -> pd.Series:
    """Le levier en vigueur ne change que si le levier calcule s'en ecarte de plus du seuil.

    Causal par construction : la valeur en t ne depend que des valeurs <= t.
    """
    v = levier.to_numpy(dtype=float).copy()
    en_vigueur = np.nan
    for i, x in enumerate(v):
        if np.isnan(x):
            continue
        if np.isnan(en_vigueur) or abs(x - en_vigueur) > seuil:
            en_vigueur = x
        v[i] = en_vigueur
    return pd.Series(v, index=levier.index)


def chaine(closes: pd.DataFrame, funding_j: pd.DataFrame, cfg: dict = CONFIG) -> dict:
    """Toute la construction, des clotures aux positions cibles du jour (deja decalees)."""
    rendements = closes.pct_change()
    comp = vc.composite(vc.jambe_base(rendements), vc.jambe_trend(closes, rendements),
                        vc.jambe_carry(funding_j))
    r_comp = (comp.shift(1) * rendements).sum(axis=1, skipna=False)
    sigma = vo.sigma_composite(r_comp, "glissant", cfg["fenetre"])
    levier = hysteresis((cfg["cible"] / sigma.replace(0.0, np.nan))
                        .clip(cfg["lmin"], cfg["lmax"]), cfg["seuil_levier"])
    cible = comp.shift(1).mul(levier.shift(1), axis=0)
    return {"composite": comp, "sigma": sigma, "levier": levier, "cible": cible}


def epreuve_causalite(closes: pd.DataFrame, funding_j: pd.DataFrame) -> list[tuple[str, float]]:
    complet = chaine(closes, funding_j)
    t = closes.index[len(closes) * 2 // 3]
    court = chaine(closes.loc[:t], funding_j.loc[:t])
    ecarts = []
    for nom in complet:
        g, d = court[nom], complet[nom].loc[:t]
        if not g.isna().equals(d.isna()):
            ecarts.append((nom, float("inf")))
            continue
        e = (g - d).abs().to_numpy()
        e = e[~np.isnan(e)]
        ecarts.append((nom, float(e.max()) if e.size else 0.0))
    return ecarts


def serie_nette(cible: pd.DataFrame, rendements: pd.DataFrame, funding_j: pd.DataFrame,
                index: pd.DatetimeIndex, pas: int, bande: float) -> pd.Series:
    r_net, _ = vo.derouler_bande(cible.reindex(index).to_numpy(dtype=float),
                                 rendements.reindex(index).to_numpy(dtype=float),
                                 funding_j.reindex(index).to_numpy(dtype=float),
                                 pas, bande, vc.BPS_TAKER)
    return pd.Series(r_net, index=index)


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    closes, rendements, funding_j = vo.donnees()

    print("=" * 96)
    print("VOIE C — config du 03/10 passee par les garde-fous du banc")
    print("=" * 96)
    print("  " + ", ".join(f"{k}={v}" for k, v in CONFIG.items()))

    print("\n1. CAUSALITE — toute la chaine recalculee sur la serie tronquee aux 2/3")
    ecarts = epreuve_causalite(closes, funding_j)
    for nom, e in ecarts:
        print(f"  [{'OK' if e < 1e-12 else 'ECHEC':<5s}] {nom:<10s} plus grand ecart {e:.3e}")
    if any(e >= 1e-12 for _, e in ecarts):
        raise vc.MesureError("epreuve de causalite echouee")

    c = chaine(closes, funding_j)
    depart = pd.Timestamp("2021-06-12", tz="UTC")       # fenetre commune de voie_c_optim
    index = closes.index[closes.index >= depart]
    net = serie_nette(c["cible"], rendements, funding_j, index, CONFIG["pas"], CONFIG["bande"])
    m_train = np.asarray(index <= vo.FIN_TRAIN)
    m_oos = np.asarray(index >= vo.DEBUT_OOS)

    n_banc = experiences.compteur()
    n = n_banc + ESSAIS_VOIE_C
    print(f"\n2. S2 SHARPE DEGONFLE — N = {n_banc} (compteur du banc) + {ESSAIS_VOIE_C} "
          f"(voie C) = {n}")
    print(f"  {'':<8s}{'Sharpe/j':>10s}{'Sharpe an.':>11s}{'seuil/j':>9s}{'DSR':>7s}"
          f"{'skew':>7s}{'kurt':>7s}")
    for titre, m in (("TRAIN", m_train), ("OOS", m_oos), ("PLEINE", np.ones(len(index), bool))):
        d = multitest.sharpe_degonfle(net[m].to_numpy(), n)
        print(f"  {titre:<8s}{d['sharpe']:>10.4f}{d['sharpe'] * math.sqrt(vc.PPA):>11.2f}"
              f"{d['sharpe_seuil']:>9.4f}{d['dsr']:>7.2f}{d['skew']:>7.2f}{d['kurtosis']:>7.1f}")
    print("  DSR > 0,95 = le Sharpe resiste au hasard de N essais. Ce n'est pas une proba que")
    print("  la strategie marche.")

    print("\n3. BOOTSTRAP PAR BLOCS — rendement net quotidien moyen, IC 95 %, annualise x365")
    for titre, m in (("TRAIN", m_train), ("OOS", m_oos)):
        b = bootstrap.intervalle(net[m].to_numpy())
        print(f"  {titre:<6s} moyenne {b['observe'] * 365:>7.1%}/an  IC [{b['ic_bas'] * 365:>7.1%} ; "
              f"{b['ic_haut'] * 365:>7.1%}]  p(<=0) = {b['p_value']:.3f}  bloc {b['ell']:.0f} j")

    print("\n4. S7 REALITY CHECK (SPA) — excedent quotidien contre BTC buy & hold")
    btc = rendements["BTC"].reindex(index).fillna(0.0) - funding_j["BTC"].reindex(index).fillna(0.0)
    univers = {}
    for lmin, lmax, seuil in ((0.0, 2.0, 0.0), (0.25, 3.0, 0.0), (0.25, 3.0, 0.10),
                              (0.25, 3.0, 0.25), (0.25, 3.0, 0.50)):
        cfg = {**CONFIG, "lmin": lmin, "lmax": lmax, "seuil_levier": seuil}
        r = serie_nette(chaine(closes, funding_j, cfg)["cible"], rendements, funding_j,
                        index, cfg["pas"], cfg["bande"])
        univers[f"L[{lmin};{lmax}] seuil {seuil}"] = r
    for titre, m in (("TRAIN", m_train), ("OOS", m_oos)):
        rc = multitest.reality_check({k: (v - btc)[m].to_numpy() for k, v in univers.items()})
        print(f"  {titre:<6s} {rc['n_candidates']} variantes, meilleure : {rc['meilleure']}, "
              f"p = {rc['p_value']:.3f}")
    print("  Limite : l'univers ne contient que les 5 variantes de levier, pas les 5760 de la")
    print("  grille. Le DSR (point 2) est la que pour compter ces dernieres.")


if __name__ == "__main__":
    main()
