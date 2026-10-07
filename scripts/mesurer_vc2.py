"""Voie C2 — la mesure preenregistree de VC2 et VC2T (backtest INFORMATIF, porte d'entree).

    ARIT_HOME=/root/ARIT2.0 /root/venvs/arit/bin/python scripts/mesurer_vc2.py

Applique la regle de decision ecrite le 07/10 AVANT la mesure (`preenregistrer_vc2.py`) :
    admise au forward (confirmee) : maxDD net >= -25 % ET Sharpe net > Sharpe du hold BTC
                                   (perpetuel, funding paye) ET causalite passee
    infirmee                      : sinon
Fenetre 2021-06-12 -> 2026-09-05, rien n'est charge apres. Elle a deja servi a la voie C :
ce backtest elimine le manifestement faux, il ne confirme rien.

Un run par hypothese, identifiant deterministe : relancer ne compte pas un essai de plus.

RESULTAT DU 07/10 (run unique, VC2 1fc6b17a8880, VC2T ecca82917d20) — les deux INFIRMEES :
- VC2  Sharpe 0,72 | CAGR 20,7 % | vol 21,3 % | maxDD -34,8 % | turnover 2,7x/an
- VC2T Sharpe 0,78 | CAGR 23,7 % | vol 22,1 % | maxDD -38,2 % | turnover 5,9x/an
- hold BTC 0,33 / -78 % ; hold equipondere 0,40 / -82 % ; voie C figee (5 pb) 1,11 / -21 %.
  Le Sharpe bat largement le hold ; le maxDD creve le budget de -25 %.
- Cause (decomposition exacte du run, refaite le 07/10, rien remesure) : la baisse
  2021-11-08 -> 2022-11-21. -16,8 points pendant le retard du signal (1er jour baissier le
  19/12/2021, momentum 126 j ; alts -11,8), -15,4 points sur la poche BTC, constituee par un
  ACHAT au signal (BTC 7 % -> 30 % du capital, puis -66 %), -2,6 de reste. La poche est un
  achat dans 9 episodes sur 9 : le moteur ne tient qu'environ 15 % de BTC en haussier.
  Suite : VC3 (`mesurer_vc3.py`), poche « maximum » et spot.
- Apport de la macro (VC2 - VC2T) : -2,7 %/an, IC 95 % [-8,0 ; +2,9] => indecidable.
"""

from __future__ import annotations

import hashlib
import importlib.util
import logging
import pathlib
import sys

import numpy as np
import pandas as pd

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from beta.protocole import experiences  # noqa: E402
from beta.stats import bootstrap  # noqa: E402
from beta.strategies import voie_c2 as c2  # noqa: E402
from beta.strategies import voie_c_optim as vo  # noqa: E402
from beta.strategies import voie_c_verif as vv  # noqa: E402
from beta.strategies import voie_c_voltarget as vc  # noqa: E402

log = logging.getLogger("beta.mesurer_vc2")

IDS = ("VC2", "VC2T")
DATES_CAUSALITE = ("2022-11-09", "2025-04-07")
MAXDD_MIN = -0.25


def run_id(id_exp: str, signe: str) -> str:
    cle = f"{id_exp}|{signe}|{c2.DEPART_SIMULATION:%Y-%m-%d}|{c2.FIN_BACKTEST:%Y-%m-%d}"
    return hashlib.sha256(cle.encode()).hexdigest()[:12]


def config_figee() -> dict:
    spec = importlib.util.spec_from_file_location("suivi", RACINE / "scripts" / "voie_c_suivi.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.CONFIG_FIGEE


def references(d: dict, jours: pd.DatetimeIndex) -> dict[str, pd.Series]:
    rend = d["closes"].pct_change().reindex(jours)
    fund = d["funding"].reindex(jours)
    net = (rend - fund).fillna(0.0)
    croissance = (1.0 + net).cumprod()
    ew = croissance.mean(axis=1)
    figee = config_figee()
    ch = vv.chaine(d["closes"], d["funding"], figee)
    r_fig, _ = vo.derouler_bande(ch["cible"].reindex(jours).to_numpy(float),
                                 rend.to_numpy(float), fund.to_numpy(float),
                                 figee["pas"], figee["bande"], vc.BPS_TAKER)
    return {"hold BTC": net["BTC"],
            "hold equipondere": ew.pct_change().fillna(ew.iloc[0] - 1.0),
            "voie C figee (3 jambes, 5 pb)": pd.Series(r_fig, index=jours)}


def ligne(nom: str, r: pd.Series, extra: str = "") -> str:
    p = vc.performance(r)
    return (f"  {nom:<34s} Sharpe {p['sharpe']:5.2f} | CAGR {p['cagr']:7.1%} | "
            f"vol {p['vol']:5.1%} | maxDD {p['mdd']:7.1%}{extra}")


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)-7s %(name)s  %(message)s")
    cfgs = {i: c2.config(i) for i in IDS}                   # le verrou : preenregistre ou rien
    d = c2.donnees(fin=c2.FIN_BACKTEST)
    assert d["closes"].index.max() <= c2.FIN_BACKTEST

    causalite = {}
    for i, cfg in cfgs.items():
        ecarts = {}
        for t in DATES_CAUSALITE:
            for k, v in c2.epreuve_causalite(d, cfg, pd.Timestamp(t, tz="UTC")).items():
                ecarts[f"{t} {k}"] = v
        causalite[i] = all(v == 0.0 for v in ecarts.values())
        if not causalite[i]:
            log.error("%s : causalite en echec %s", i, ecarts)

    res = {i: c2.calculer(d, cfg) for i, cfg in cfgs.items()}
    jours = res["VC2"]["jours"]
    refs = references(d, jours)
    m_train = jours <= c2.FIN_TRAIN
    m_oos = jours > c2.FIN_TRAIN

    print(f"VOIE C2 — mesure preenregistree, {jours[0]:%Y-%m-%d} -> {jours[-1]:%Y-%m-%d} "
          f"({len(jours)} j). Sharpe en racine de 252 (convention du projet).")
    print("Frais VC2/VC2T : taker 5 pb + slippage 5 (BTC/ETH) / 10 pb par cote ; funding deduit.")
    sh_hold = vc.performance(refs["hold BTC"])["sharpe"]
    verdicts = {}
    for titre, m in (("PLEINE FENETRE (porte)", np.ones(len(jours), bool)),
                     ("TRAIN <= 2024-06-30 (informatif)", m_train),
                     ("OOS >= 2024-07-01 (informatif, deja brule)", m_oos)):
        print(f"\n{titre}")
        for i in IDS:
            r = pd.Series(res[i]["r_net"], index=jours)[m]
            to = res[i]["turnover"][m].mean() * vc.JOURS_AN
            fr = res[i]["frais"][m].mean() * vc.JOURS_AN
            fu = res[i]["funding"][m].mean() * vc.JOURS_AN
            print(ligne(i, r, f" | turnover {to:5.1f}x/an | frais {fr:5.2%}/an | "
                              f"funding {fu:5.2%}/an"))
        for nom, r in refs.items():
            print(ligne(nom, r[m]))

    print("\nETATS (pleine fenetre)")
    for i in IDS:
        part = res[i]["etat"].value_counts(normalize=True)
        brut = np.abs(res[i]["positions"]).sum(axis=1)
        print(f"  {i:<5s} " + " | ".join(f"{e} {part.get(e, 0):5.1%}"
                                          for e in (c2.HAUSSIER, c2.BAISSIER, c2.VEILLE))
              + f" | episodes baissiers {res[i]['episodes']} | brut moyen {brut.mean():.2f}"
              f" (max {brut.max():.2f})")
    print("  votes VC2, part du temps a -1 / 0 / +1 :")
    for nom, col in res["VC2"]["votes"].items():
        print(f"    {nom:<24s} " + " / ".join(f"{(col == x).mean():5.1%}" for x in (-1, 0, 1)))

    print("\nPORTE (regle preenregistree)")
    for i in IDS:
        p = vc.performance(pd.Series(res[i]["r_net"], index=jours))
        ok_dd, ok_sh = p["mdd"] >= MAXDD_MIN, p["sharpe"] > sh_hold
        verdicts[i] = "confirmee" if (ok_dd and ok_sh and causalite[i]) else "infirmee"
        print(f"  {i:<5s} maxDD {p['mdd']:7.1%} >= -25 % : {'oui' if ok_dd else 'NON'} | "
              f"Sharpe {p['sharpe']:.2f} > hold BTC {sh_hold:.2f} : {'oui' if ok_sh else 'NON'} | "
              f"causalite : {'oui' if causalite[i] else 'NON'}  =>  {verdicts[i].upper()}")

    diff = res["VC2"]["r_net"] - res["VC2T"]["r_net"]
    b = bootstrap.intervalle(diff)
    apport = ("apporte" if b["ic_bas"] > 0 else "detruit" if b["ic_haut"] < 0
              else "indecidable")
    dsh = (vc.performance(pd.Series(res["VC2"]["r_net"], index=jours))["sharpe"]
           - vc.performance(pd.Series(res["VC2T"]["r_net"], index=jours))["sharpe"])
    print(f"\nAPPORT DE LA MACRO (VC2 - VC2T) : {b['observe'] * vc.JOURS_AN:+.2%}/an, IC 95 % "
          f"[{b['ic_bas'] * vc.JOURS_AN:+.2%} ; {b['ic_haut'] * vc.JOURS_AN:+.2%}], "
          f"delta Sharpe {dsh:+.2f}  =>  {apport.upper()} (attendu : indecidable)")

    deja = {e.get("run_id") for e in experiences.runs_journalises()}
    for i, cfg in cfgs.items():
        rid = run_id(i, c2.empreinte(cfg))
        if rid in deja:
            print(f"  {i} : run {rid} deja journalise — aucun essai de plus")
            continue
        experiences.enregistrer_run(rid, i, "voie_c2", c2.empreinte(cfg), verdicts[i])
        experiences.marquer_mesuree(i, rid, verdicts[i])
        print(f"  {i} : run {rid} journalise ({verdicts[i]})")
    print(f"  compteur d'essais : {experiences.compteur()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
