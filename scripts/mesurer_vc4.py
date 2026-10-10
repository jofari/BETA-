"""Voie C2 — la mesure preenregistree de VC4 (VC3 decidee a chaque ouverture de session).

    ARIT_HOME=/root/ARIT2.0 /root/venvs/arit/bin/python scripts/mesurer_vc4.py

Applique la regle ecrite le 10/10 AVANT la mesure (`preenregistrer_vc4.py`, commit c826290) :
    confirmee : maxDD net >= -25 % ET Sharpe net > Sharpe du hold BTC SPOT ET causalite
                ET R1 (la mediane des 10 voisins de calendrier passe aussi la porte)
    infirmee  : sinon
R2, R3, R4 et la comparaison a VC3 (meme chaine, une decision par jour) informent ; ils ne
changent pas le verdict. Serie quotidienne 00:00 -> 00:00 UTC (produit des periodes entre
instants), meme fenetre et memes conventions que VC3 ; prix : bougies 5 min du lake jusqu'au
2026-09-06 00:00 UTC (la meme borne d'information que la derniere bougie 1d de VC3).

RESULTAT DU 10/10 ~23:50 UTC (run bb92355d4e3c ; compteur 82 -> 92 avec les 10 voisins) —
CONFIRMEE par sa porte, mais SANS APPORT sur VC3 :
- VC4  Sharpe 0,76 | CAGR 18,7 % | vol 17,5 % | maxDD -21,6 % (13/03/2024 -> 04/11/2024) |
  turnover 12,6x/an | frais 2,27 %/an (4 642 decisions). VC3 : 0,80 / 22,1 % / -23,2 %,
  turnover 2,2x/an, frais 0,40 %/an. OOS : 0,64 / -20,2 % (VC3 0,72 / -19,6 %).
- Sharpe VC4 - VC3 = -0,04, IC 95 % [-0,19 ; +0,11] (bootstrap apparie, l = 20 j) ;
  correlation quotidienne 0,969. 224 changements d'etat, dont 19 seulement en cours de
  journee : la reactivite attendue existe a peine, et la bande de 20 points franchie 3 fois
  par jour multiplie le turnover par 5,7 — c'est la que part le rendement (-1,9 pt/an).
- R1 : 6/10 voisins passent, mediane -23,8 % / 0,72 => plateau, mais 4 voisins crevent le
  budget (vote 180 j, moteur 90/180 j, sigma 20 j), comme pour VC3.
- R2 DSR 0,34 (N = 92) / 0,05 (N = 5 902). R3 ALERTE : P(maxDD < -25 %) = 58-64 %.
  R4 ALERTE : 2024 = 50 % du gain (en log).
Lecture : la cadence par session ne gagne rien sur ce backtest ; elle coute des frais. Le
forward dira si la reactivite paie dans une vraie cassure intraday, ce que 5 ans n'ont pas.
"""

from __future__ import annotations

import copy
import hashlib
import logging
import math
import pathlib
import sys

import numpy as np
import pandas as pd

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from beta.protocole import experiences  # noqa: E402
from beta.stats import bootstrap, multitest  # noqa: E402
from beta.strategies import voie_c2 as c2  # noqa: E402
from beta.strategies import voie_c4 as c4  # noqa: E402
from beta.strategies import voie_c_verif as vv  # noqa: E402
from beta.strategies import voie_c_voltarget as vc  # noqa: E402

log = logging.getLogger("beta.mesurer_vc4")

ID = "VC4"
INSTANTS_CAUSALITE = ("2022-11-09 14:30", "2025-04-07 07:00", "2025-04-07 13:30")
MAXDD_MIN = -0.25
L_ALERTE = 20
N_REPETITIONS = 2000


def run_id(id_exp: str, signe: str) -> str:
    cle = f"{id_exp}|{signe}|{c2.DEPART_SIMULATION:%Y-%m-%d}|{c2.FIN_BACKTEST:%Y-%m-%d}"
    return hashlib.sha256(cle.encode()).hexdigest()[:12]


def voisin(cfg: dict, chemin: str, valeur) -> dict:
    v = copy.deepcopy(cfg)
    bloc, cle = chemin.split(".")
    if cle not in v[bloc]:
        raise KeyError(f"voisin {chemin} : cle absente de la config VC4")
    v[bloc][cle] = valeur
    v["version"] = f"{ID}~{chemin}={valeur}"
    return v


def maxdd(r: np.ndarray) -> float:
    equite = np.cumprod(1.0 + np.asarray(r, dtype=float))
    return float((equite / np.maximum.accumulate(equite) - 1.0).min())


def sharpe_an(r: np.ndarray) -> float:
    return multitest.sharpe(r) * math.sqrt(vc.PPA)


def ligne(nom: str, r: pd.Series, extra: str = "") -> str:
    p = vc.performance(r)
    return (f"  {nom:<34s} Sharpe {p['sharpe']:5.2f} | CAGR {p['cagr']:7.1%} | "
            f"vol {p['vol']:5.1%} | maxDD {p['mdd']:7.1%}{extra}")


def pire_baisse(r: pd.Series) -> tuple[pd.Timestamp, pd.Timestamp, float]:
    equite = (1.0 + r).cumprod()
    dd = equite / equite.cummax() - 1.0
    creux = dd.idxmin()
    return equite.loc[:creux].idxmax(), creux, float(dd.min())


def par_jour(valeurs: np.ndarray, instants: pd.DatetimeIndex) -> pd.Series:
    return pd.Series(valeurs, index=instants).groupby(instants.normalize()).sum()


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)-7s %(name)s  %(message)s")
    entree = experiences.exiger(ID)                          # le verrou : preenregistre ou rien
    cfg = c2.config(ID)
    voisins = entree["surapprentissage"]["R1_plateau"]["voisins"]
    d = c2.donnees(fin=c2.FIN_BACKTEST)
    assert d["closes"].index.max() <= c2.FIN_BACKTEST
    cinq = c4.donnees_5m(debut=d["closes"].index[0], fin=c2.FIN_BACKTEST + c4.UN_JOUR)
    assert max(s.index.max() for s in cinq.values()) <= c2.FIN_BACKTEST + c4.UN_JOUR

    ecarts = {}
    for t in INSTANTS_CAUSALITE:
        for k, v in c4.epreuve_causalite(d, cinq, cfg, pd.Timestamp(t, tz="UTC")).items():
            ecarts[f"{t} {k}"] = v
    causalite = all(v == 0.0 for v in ecarts.values())
    if not causalite:
        log.error("VC4 : causalite en echec %s", ecarts)

    res = c4.calculer(d, cinq, cfg)
    jours = res["jours"]
    r4 = res["r_net_jour"]
    res3 = c2.calculer(d, c2.config("VC3"))
    assert res3["jours"].equals(jours)
    r3 = pd.Series(res3["r_net"], index=jours)
    rend = d["closes"].pct_change().reindex(jours).fillna(0.0)
    hold_spot = rend["BTC"]
    croissance = (1.0 + rend).cumprod().mean(axis=1)
    refs = {"hold BTC spot (porte)": hold_spot,
            "hold equipondere spot": croissance.pct_change().fillna(croissance.iloc[0] - 1.0),
            "VC3 (1 decision/jour, 07/10)": r3}
    m_train = np.asarray(jours <= c2.FIN_TRAIN)
    m_oos = np.asarray(jours > c2.FIN_TRAIN)
    to_jour = par_jour(res["turnover"], res["instants"]).reindex(jours).fillna(0.0)
    fr_jour = par_jour(res["frais"], res["instants"]).reindex(jours).fillna(0.0)

    print(f"VOIE C2 — VC4 (VC3 a chaque ouverture de session), mesure preenregistree, "
          f"{jours[0]:%Y-%m-%d} -> {jours[-1]:%Y-%m-%d} ({len(jours)} j, "
          f"{len(res['instants'])} decisions). Sharpe en racine de 252.")
    print("Frais (ceux de VC3) : spot 10 pb + slippage 5 (BTC/ETH) / 10 pb par cote, a chaque "
          "echange ; aucun funding.")
    for titre, m in (("PLEINE FENETRE (porte)", np.ones(len(jours), bool)),
                     ("TRAIN <= 2024-06-30 (informatif)", m_train),
                     ("OOS >= 2024-07-01 (informatif, deja vu)", m_oos)):
        print(f"\n{titre}")
        print(ligne(ID, r4[m], f" | turnover {to_jour[m].mean() * vc.JOURS_AN:4.1f}x/an | "
                               f"frais {fr_jour[m].mean() * vc.JOURS_AN:5.2%}/an"))
        to3 = res3["turnover"][m].mean() * vc.JOURS_AN
        fr3 = res3["frais"][m].mean() * vc.JOURS_AN
        for nom, r in refs.items():
            extra = (f" | turnover {to3:4.1f}x/an | frais {fr3:5.2%}/an"
                     if nom.startswith("VC3") else "")
            print(ligne(nom, r[m], extra))

    etat = res["etat"]
    part = etat.value_counts(normalize=True)
    brut = np.abs(res["positions"]).sum(axis=1)
    minuit = np.asarray(res["instants"] == res["instants"].normalize())
    change = np.r_[False, etat.to_numpy()[1:] != etat.to_numpy()[:-1]]
    sommet, creux, pire = pire_baisse(r4)
    print("\nETATS ET EXPOSITION (pleine fenetre, par decision)")
    print("  " + " | ".join(f"{e} {part.get(e, 0):5.1%}"
                            for e in (c2.HAUSSIER, c2.BAISSIER, c2.VEILLE))
          + f" | episodes baissiers {res['episodes']} | brut moyen {brut.mean():.2f}"
          f" (max {brut.max():.2f})")
    print(f"  changements d'etat : {int(change.sum())} dont {int((change & ~minuit).sum())} en "
          f"cours de journee (Londres ou New York) ; VC3 : "
          f"{int((res3['etat'].to_numpy()[1:] != res3['etat'].to_numpy()[:-1]).sum())}")
    print(f"  pire baisse : {pire:.1%}, du {sommet:%Y-%m-%d} au {creux:%Y-%m-%d}")

    p4 = vc.performance(r4)
    sh_hold = vc.performance(hold_spot)["sharpe"]
    ok_dd, ok_sh = p4["mdd"] >= MAXDD_MIN, p4["sharpe"] > sh_hold
    print("\nPORTE (regle preenregistree)")
    print(f"  maxDD {p4['mdd']:6.1%} >= -25 % : {'oui' if ok_dd else 'NON'} | Sharpe "
          f"{p4['sharpe']:.2f} > hold BTC spot {sh_hold:.2f} : {'oui' if ok_sh else 'NON'} | "
          f"causalite : {'oui' if causalite else 'NON'}")

    print("\nR1 PLATEAU (porte) — un reglage de calendrier a la fois")
    print(f"  {'voisin':<34s}{'Sharpe':>8s}{'CAGR':>8s}{'maxDD':>8s}  porte")
    lot = []
    for chemin, valeurs in voisins.items():
        for valeur in valeurs:
            cv = voisin(cfg, chemin, valeur)
            pv = vc.performance(c4.calculer(d, cinq, cv)["r_net_jour"])
            passe = pv["mdd"] >= MAXDD_MIN and pv["sharpe"] > sh_hold
            lot.append({"nom": f"{chemin}={valeur}", "cfg": cv, "perf": pv, "passe": passe})
            print(f"  {chemin + ' = ' + str(valeur):<34s}{pv['sharpe']:>8.2f}{pv['cagr']:>8.1%}"
                  f"{pv['mdd']:>8.1%}  {'oui' if passe else 'NON'}")
    med_dd = float(np.median([v["perf"]["mdd"] for v in lot]))
    med_sh = float(np.median([v["perf"]["sharpe"] for v in lot]))
    ok_r1 = med_dd >= MAXDD_MIN and med_sh > sh_hold
    print(f"  {'VC4 (reglages preenregistres)':<34s}{p4['sharpe']:>8.2f}{p4['cagr']:>8.1%}"
          f"{p4['mdd']:>8.1%}")
    print(f"  mediane des {len(lot)} voisins : maxDD {med_dd:.1%}, Sharpe {med_sh:.2f}, "
          f"{sum(v['passe'] for v in lot)}/{len(lot)} passent la porte  =>  "
          f"{'PLATEAU' if ok_r1 else 'FRAGILE'}")

    verdict = "confirmee" if (ok_dd and ok_sh and causalite and ok_r1) else "infirmee"

    deja = {e.get("run_id") for e in experiences.runs_journalises()}
    nouveaux = [v for v in lot if run_id(ID, c2.empreinte(v["cfg"])) not in deja]
    n_banc = experiences.compteur() + len(nouveaux)
    n_famille = n_banc + vv.ESSAIS_VOIE_C
    print(f"\nR2 SHARPE DEGONFLE (informatif) — N banc = {n_banc}, N famille = {n_famille}")
    print(f"  {'':<8s}{'Sharpe an.':>11s}{'DSR N banc':>12s}{'DSR N famille':>15s}")
    for titre, m in (("PLEINE", np.ones(len(jours), bool)), ("TRAIN", m_train), ("OOS", m_oos)):
        x = r4[m].to_numpy()
        a, b = multitest.sharpe_degonfle(x, n_banc), multitest.sharpe_degonfle(x, n_famille)
        print(f"  {titre:<8s}{a['sharpe'] * math.sqrt(vc.PPA):>11.2f}{a['dsr']:>12.2f}"
              f"{b['dsr']:>15.2f}")

    print("\nR3 CONE DE DRAWDOWN ET ECART AU HOLD (informatif, alerte a l = 20 j)")
    apparie = np.column_stack([r4.to_numpy(), hold_spot.to_numpy()])
    alerte_r3 = False
    for ell in bootstrap.LONGUEURS_SENSIBILITE:
        dd = bootstrap.distribution(r4.to_numpy(), maxdd, float(ell), N_REPETITIONS, graine=0)
        ecart = bootstrap.distribution(
            apparie, lambda m: sharpe_an(m[:, 0]) - sharpe_an(m[:, 1]), float(ell),
            N_REPETITIONS, graine=0)
        p_budget = float((dd < MAXDD_MIN).mean())
        alerte_r3 |= ell == L_ALERTE and p_budget > 0.5
        print(f"  l = {ell:>2d} j : maxDD median {np.median(dd):6.1%}, 5e centile "
              f"{np.percentile(dd, 5):6.1%}, P(maxDD < -25 %) = {p_budget:5.1%} | Sharpe VC4 - "
              f"hold IC 95 % [{np.percentile(ecart, 2.5):+.2f} ; {np.percentile(ecart, 97.5):+.2f}]")

    print("\nCOMPARAISON A VC3 (informatif) — ce que la cadence apporte ou coute")
    paire = np.column_stack([r4.to_numpy(), r3.to_numpy()])
    ecart = bootstrap.distribution(paire, lambda m: sharpe_an(m[:, 0]) - sharpe_an(m[:, 1]),
                                   float(L_ALERTE), N_REPETITIONS, graine=0)
    p3 = vc.performance(r3)
    print(f"  Sharpe VC4 - VC3 {p4['sharpe'] - p3['sharpe']:+.2f}, IC 95 % "
          f"[{np.percentile(ecart, 2.5):+.2f} ; {np.percentile(ecart, 97.5):+.2f}], "
          f"P(<= 0) = {float((ecart <= 0).mean()):.3f} | maxDD {p4['mdd']:.1%} contre "
          f"{p3['mdd']:.1%} | CAGR {p4['cagr']:.1%} contre {p3['cagr']:.1%}")
    print(f"  correlation des rendements quotidiens VC4 / VC3 : {np.corrcoef(paire.T)[0, 1]:.3f}")

    print("\nR4 STABILITE (informatif, alerte : Sharpe OOS < 0 ou > 50 % du gain sur une annee)")
    log_r = np.log1p(r4)
    par_an = log_r.groupby(r4.index.year).sum()
    for annee, gr in r4.groupby(r4.index.year):
        p = vc.performance(gr)
        print(f"  {annee}  rendement {math.expm1(par_an[annee]):7.1%} | Sharpe {p['sharpe']:5.2f}"
              f" | maxDD {p['mdd']:6.1%} | {len(gr)} j")
    part_max = float(par_an.max() / log_r.sum()) if log_r.sum() > 0 else float("nan")
    sh_oos = vc.performance(r4[m_oos])["sharpe"]
    alerte_r4 = bool(sh_oos < 0 or part_max > 0.5)
    print(f"  meilleure annee : {part_max:.0%} du gain total (en log) | Sharpe OOS {sh_oos:.2f}")

    print(f"\nVERDICT VC4 : {verdict.upper()}"
          + ("" if verdict == "infirmee" else " — admise au forward (dry-run 6 mois des le 12/10)"))
    print(f"  alertes : R3 {'OUI' if alerte_r3 else 'non'} | R4 {'OUI' if alerte_r4 else 'non'}")

    rid = run_id(ID, c2.empreinte(cfg))
    if rid in deja:
        print(f"  {ID} : run {rid} deja journalise — aucun essai de plus")
    else:
        experiences.enregistrer_run(rid, ID, "voie_c4", c2.empreinte(cfg), verdict)
        experiences.marquer_mesuree(ID, rid, verdict)
        print(f"  {ID} : run {rid} journalise ({verdict})")
    for v in nouveaux:
        rv = run_id(ID, c2.empreinte(v["cfg"]))
        experiences.enregistrer_run(rv, ID, f"voie_c4:voisin:{v['nom']}",
                                    c2.empreinte(v["cfg"]),
                                    "passe" if v["passe"] else "echoue")
    print(f"  {len(nouveaux)} voisins journalises | compteur d'essais : {experiences.compteur()}"
          f" (attendu {n_banc})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
