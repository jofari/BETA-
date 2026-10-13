"""Voie C2 — la mesure preenregistree de VC5 (VC3 avec une cible de vol de 35 %).

    ARIT_HOME=/root/ARIT2.0 /root/venvs/arit/bin/python scripts/mesurer_vc5.py

Applique la regle ecrite le 10/10 AVANT la mesure (`preenregistrer_vc5.py`, commit d7f82f3) :
    confirmee : maxDD net >= -40 % ET Sharpe net > Sharpe du hold BTC SPOT ET causalite
                ET R1 (la mediane des 10 voisins de calendrier passe aussi la porte)
    infirmee  : sinon
R2, R3 (alerte a P(maxDD < -40 %) > 50 %), R4 et la comparaison a VC3 informent ; ils ne
changent pas le verdict. Meme fenetre, memes voisins et memes conventions que VC3
(`mesurer_vc3.py`) ; identifiants de run deterministes : relancer ne compte rien de plus.

RESULTAT DU 10/10 ~23:25 UTC (run 3932e75c1dd6 ; compteur 71 -> 81 avec les 10 voisins) —
CONFIRMEE, avec deux alertes :
- VC5  Sharpe 0,75 | CAGR 28,5 % | vol 28,3 % | maxDD -31,1 % (08/11/2021 -> 18/01/2023) |
  turnover 4,1x/an | frais 0,75 %/an. VC3 0,80 / 22,1 % / -23,2 % ; hold BTC spot 0,45 / -76,7 %.
  OOS (>= 2024-07-01) : 0,61 / -28,9 % (VC3 0,72 / -19,6 %).
- Exposition en haussier : moyenne 0,84, mediane 0,90 (VC3 0,61 / 0,60) ; 30 % des jours
  haussiers au plafond de 100 %. La cible plus haute rapporte plus (CAGR +6,4 pts) pour un
  risque plus haut (maxDD -8 pts) : Sharpe un peu plus BAS que VC3, pas meilleur.
- R1 plateau : 10/10 voisins passent, mediane maxDD -35,0 % / Sharpe 0,74.
- R2 DSR 0,35 (N = 81) et 0,05 (N = 5 891).
- R3 ALERTE : maxDD bootstrap median -41,6 % (l = 20 j), P(maxDD < -40 %) = 50 a 56 % ;
  Sharpe VC5 - hold +0,30, IC 95 % [-0,34 ; +0,90].
- R4 ALERTE : 2023 et 2024 font chacune +100 % ; la meilleure annee = 53 % du gain (en log).
Lecture : comme VC3, pas encore tuee, pas validee ; dans une vraie baisse, attendre plutot
-40 % que -31 %.
"""

from __future__ import annotations

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
from beta.strategies import mesure_c2 as mc  # noqa: E402
from beta.strategies import voie_c2 as c2  # noqa: E402
from beta.strategies import voie_c_verif as vv  # noqa: E402
from beta.strategies import voie_c_voltarget as vc  # noqa: E402

log = logging.getLogger("beta.mesurer_vc5")

ID = "VC5"
DATES_CAUSALITE = ("2022-11-09", "2025-04-07")
MAXDD_MIN = -0.40
L_ALERTE = 20                       # longueur de bloc de l'alerte R3, fixee au preenregistrement
N_REPETITIONS = 2000


# Fonctions communes a VC3, VC4 et VC5, a l'identique depuis le 13/10 :
# `beta.strategies.mesure_c2` (la procedure `main` ci-dessous reste celle qui a tourne).
run_id, references_vc2, maxdd, sharpe_an, ligne, pire_baisse = (
    mc.run_id, mc.references_vc2, mc.maxdd, mc.sharpe_an, mc.ligne, mc.pire_baisse)


def voisin(cfg: dict, chemin: str, valeur) -> dict:
    return mc.voisin(cfg, chemin, valeur, ID)


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)-7s %(name)s  %(message)s")
    entree = experiences.exiger(ID)                          # le verrou : preenregistre ou rien
    cfg = c2.config(ID)
    voisins = entree["surapprentissage"]["R1_plateau"]["voisins"]
    d = c2.donnees(fin=c2.FIN_BACKTEST)
    assert d["closes"].index.max() <= c2.FIN_BACKTEST

    ecarts = {}
    for t in DATES_CAUSALITE:
        for k, v in c2.epreuve_causalite(d, cfg, pd.Timestamp(t, tz="UTC")).items():
            ecarts[f"{t} {k}"] = v
    causalite = all(v == 0.0 for v in ecarts.values())
    if not causalite:
        log.error("VC5 : causalite en echec %s", ecarts)

    res = c2.calculer(d, cfg)
    jours = res["jours"]
    r3 = pd.Series(res["r_net"], index=jours)
    rend = d["closes"].pct_change().reindex(jours).fillna(0.0)
    hold_spot = rend["BTC"]
    croissance = (1.0 + rend).cumprod().mean(axis=1)
    refs = {"hold BTC spot (porte)": hold_spot,
            "hold equipondere spot": croissance.pct_change().fillna(croissance.iloc[0] - 1.0)}
    for nom, r in references_vc2(d, jours).items():
        refs[nom.replace("hold BTC", "hold BTC perpetuel")
                .replace("hold equipondere", "hold equipondere perpetuel")] = r
    res_vc3 = c2.calculer(d, c2.config("VC3"))
    refs["VC3 (cible 20 %, mesuree le 07/10)"] = pd.Series(res_vc3["r_net"], index=jours)
    m_train = np.asarray(jours <= c2.FIN_TRAIN)
    m_oos = np.asarray(jours > c2.FIN_TRAIN)

    print(f"VOIE C2 — VC5 (VC3, cible de vol 35 %), mesure preenregistree, "
          f"{jours[0]:%Y-%m-%d} -> {jours[-1]:%Y-%m-%d} ({len(jours)} j). Sharpe en racine de 252.")
    print("Frais VC5 (ceux de VC3) : spot 10 pb + slippage 5 (BTC/ETH) / 10 pb par cote ; "
          "aucun funding.")
    for titre, m in (("PLEINE FENETRE (porte)", np.ones(len(jours), bool)),
                     ("TRAIN <= 2024-06-30 (informatif)", m_train),
                     ("OOS >= 2024-07-01 (informatif, deja vu)", m_oos)):
        print(f"\n{titre}")
        to = res["turnover"][m].mean() * vc.JOURS_AN
        fr = res["frais"][m].mean() * vc.JOURS_AN
        print(ligne(ID, r3[m], f" | turnover {to:4.1f}x/an | frais {fr:5.2%}/an"))
        for nom, r in refs.items():
            print(ligne(nom, r[m]))

    part = res["etat"].value_counts(normalize=True)
    brut = np.abs(res["positions"]).sum(axis=1)
    sommet, creux, pire = pire_baisse(r3)
    print("\nETATS ET EXPOSITION (pleine fenetre)")
    print("  " + " | ".join(f"{e} {part.get(e, 0):5.1%}"
                            for e in (c2.HAUSSIER, c2.BAISSIER, c2.VEILLE))
          + f" | episodes baissiers {res['episodes']} | brut moyen {brut.mean():.2f}"
          f" (max {brut.max():.2f})")
    print(f"  pire baisse : {pire:.1%}, du {sommet:%Y-%m-%d} au {creux:%Y-%m-%d}")
    haussier = np.asarray(res["etat"] == c2.HAUSSIER)
    brut3 = np.abs(res_vc3["positions"]).sum(axis=1)
    print(f"\nCOMPARAISON A VC3 (informatif) — exposition brute en haussier : VC5 moyenne "
          f"{brut[haussier].mean():.2f} / mediane {np.median(brut[haussier]):.2f} | VC3 moyenne "
          f"{brut3[haussier].mean():.2f} / mediane {np.median(brut3[haussier]):.2f} | jours "
          f"haussiers au plafond (brut >= 0,999) : VC5 {(brut[haussier] >= 0.999).mean():.0%}")

    p3 = vc.performance(r3)
    sh_hold = vc.performance(hold_spot)["sharpe"]
    ok_dd, ok_sh = p3["mdd"] >= MAXDD_MIN, p3["sharpe"] > sh_hold
    print("\nPORTE (regle preenregistree)")
    print(f"  maxDD {p3['mdd']:6.1%} >= -40 % : {'oui' if ok_dd else 'NON'} | Sharpe "
          f"{p3['sharpe']:.2f} > hold BTC spot {sh_hold:.2f} : {'oui' if ok_sh else 'NON'} | "
          f"causalite : {'oui' if causalite else 'NON'}")

    # R1 — plateau : un parametre de calendrier a la fois, deux valeurs.
    print("\nR1 PLATEAU (porte) — un reglage de calendrier a la fois")
    print(f"  {'voisin':<34s}{'Sharpe':>8s}{'CAGR':>8s}{'maxDD':>8s}  porte")
    lot = []
    for chemin, valeurs in voisins.items():
        for valeur in valeurs:
            cv = voisin(cfg, chemin, valeur)
            rv = pd.Series(c2.calculer(d, cv)["r_net"], index=jours)
            pv = vc.performance(rv)
            passe = pv["mdd"] >= MAXDD_MIN and pv["sharpe"] > sh_hold
            lot.append({"nom": f"{chemin}={valeur}", "cfg": cv, "perf": pv, "passe": passe})
            print(f"  {chemin + ' = ' + str(valeur):<34s}{pv['sharpe']:>8.2f}{pv['cagr']:>8.1%}"
                  f"{pv['mdd']:>8.1%}  {'oui' if passe else 'NON'}")
    med_dd = float(np.median([v["perf"]["mdd"] for v in lot]))
    med_sh = float(np.median([v["perf"]["sharpe"] for v in lot]))
    ok_r1 = med_dd >= MAXDD_MIN and med_sh > sh_hold
    print(f"  {'VC5 (reglages preenregistres)':<34s}{p3['sharpe']:>8.2f}{p3['cagr']:>8.1%}"
          f"{p3['mdd']:>8.1%}")
    print(f"  mediane des {len(lot)} voisins : maxDD {med_dd:.1%}, Sharpe {med_sh:.2f}, "
          f"{sum(v['passe'] for v in lot)}/{len(lot)} passent la porte  =>  "
          f"{'PLATEAU' if ok_r1 else 'FRAGILE'}")

    verdict = "confirmee" if (ok_dd and ok_sh and causalite and ok_r1) else "infirmee"

    # Les runs de ce lot sont payes d'avance (A1) : le N du DSR les compte deja.
    deja = {e.get("run_id") for e in experiences.runs_journalises()}
    nouveaux = [v for v in lot if run_id(ID, c2.empreinte(v["cfg"])) not in deja]
    n_banc = experiences.compteur() + len(nouveaux)
    n_famille = n_banc + vv.ESSAIS_VOIE_C
    print(f"\nR2 SHARPE DEGONFLE (informatif) — N banc = {n_banc}, N famille = {n_banc} + "
          f"{vv.ESSAIS_VOIE_C} configs de la voie C = {n_famille}")
    print(f"  {'':<8s}{'Sharpe an.':>11s}{'DSR N banc':>12s}{'DSR N famille':>15s}"
          f"{'skew':>7s}{'kurt':>7s}")
    for titre, m in (("PLEINE", np.ones(len(jours), bool)), ("TRAIN", m_train), ("OOS", m_oos)):
        x = r3[m].to_numpy()
        a, b = multitest.sharpe_degonfle(x, n_banc), multitest.sharpe_degonfle(x, n_famille)
        print(f"  {titre:<8s}{a['sharpe'] * math.sqrt(vc.PPA):>11.2f}{a['dsr']:>12.2f}"
              f"{b['dsr']:>15.2f}{a['skew']:>7.2f}{a['kurtosis']:>7.1f}")

    print("\nR3 CONE DE DRAWDOWN ET ECART AU HOLD (informatif, alerte a l = 20 j)")
    apparie = np.column_stack([r3.to_numpy(), hold_spot.to_numpy()])
    alerte_r3 = False
    for ell in bootstrap.LONGUEURS_SENSIBILITE:
        dd = bootstrap.distribution(r3.to_numpy(), maxdd, float(ell), N_REPETITIONS, graine=0)
        ecart = bootstrap.distribution(
            apparie, lambda m: sharpe_an(m[:, 0]) - sharpe_an(m[:, 1]), float(ell),
            N_REPETITIONS, graine=0)
        p_budget = float((dd < MAXDD_MIN).mean())
        if ell == L_ALERTE and p_budget > 0.5:
            alerte_r3 = True
        print(f"  l = {ell:>2d} j : maxDD median {np.median(dd):6.1%}, 5e centile "
              f"{np.percentile(dd, 5):6.1%}, P(maxDD < -40 %) = {p_budget:5.1%} | Sharpe VC5 - "
              f"hold {sharpe_an(apparie[:, 0]) - sharpe_an(apparie[:, 1]):+.2f}, IC 95 % "
              f"[{np.percentile(ecart, 2.5):+.2f} ; {np.percentile(ecart, 97.5):+.2f}], "
              f"P(<= 0) = {float((ecart <= 0).mean()):.3f}")

    print("\nR4 STABILITE (informatif, alerte : Sharpe OOS < 0 ou > 50 % du gain sur une annee)")
    log_r = np.log1p(r3)
    par_an = log_r.groupby(r3.index.year).sum()
    for annee, gr in r3.groupby(r3.index.year):
        p = vc.performance(gr)
        print(f"  {annee}  rendement {math.expm1(par_an[annee]):7.1%} | Sharpe {p['sharpe']:5.2f}"
              f" | maxDD {p['mdd']:6.1%} | {len(gr)} j")
    part_max = float(par_an.max() / log_r.sum()) if log_r.sum() > 0 else float("nan")
    sh_oos = vc.performance(r3[m_oos])["sharpe"]
    alerte_r4 = bool(sh_oos < 0 or part_max > 0.5)
    print(f"  meilleure annee : {part_max:.0%} du gain total (en log) | Sharpe OOS {sh_oos:.2f}")

    print(f"\nVERDICT VC5 : {verdict.upper()}"
          + ("" if verdict == "infirmee" else " — admise au forward (dry-run 6 mois des le 11/10)"))
    print(f"  alertes : R3 {'OUI' if alerte_r3 else 'non'} | R4 {'OUI' if alerte_r4 else 'non'}")

    rid = run_id(ID, c2.empreinte(cfg))
    if rid in deja:
        print(f"  {ID} : run {rid} deja journalise — aucun essai de plus")
    else:
        experiences.enregistrer_run(rid, ID, "voie_c2", c2.empreinte(cfg), verdict)
        experiences.marquer_mesuree(ID, rid, verdict)
        print(f"  {ID} : run {rid} journalise ({verdict})")
    for v in nouveaux:
        rv = run_id(ID, c2.empreinte(v["cfg"]))
        experiences.enregistrer_run(rv, ID, f"voie_c2:voisin:{v['nom']}",
                                    c2.empreinte(v["cfg"]),
                                    "passe" if v["passe"] else "echoue")
    print(f"  {len(nouveaux)} voisins journalises | compteur d'essais : {experiences.compteur()}"
          f" (attendu {n_banc})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
