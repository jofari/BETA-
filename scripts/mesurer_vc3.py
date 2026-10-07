"""Voie C2 — la mesure preenregistree de VC3 et sa batterie anti-surapprentissage.

    ARIT_HOME=/root/ARIT2.0 /root/venvs/arit/bin/python scripts/mesurer_vc3.py

Applique la regle ecrite le 07/10 AVANT la mesure (`preenregistrer_vc3.py`, commit b342ea0) :
    confirmee : maxDD net >= -25 % ET Sharpe net > Sharpe du hold BTC SPOT ET causalite
                ET R1 (la mediane des 10 voisins de calendrier passe aussi la porte)
    infirmee  : sinon
R2 (Sharpe degonfle), R3 (cone de drawdown, ecart de Sharpe au hold) et R4 (stabilite dans
le temps) informent et alertent ; ils ne changent pas le verdict.

Fenetre 2021-06-12 -> 2026-09-05, rien n'est charge apres. Elle a deja servi (voie C, VC2,
VC2T) : ce backtest elimine le manifestement faux, il ne confirme rien. Un run pour VC3 et
un par voisin, identifiants deterministes : relancer ne compte pas un essai de plus.

RESULTAT DU 07/10 (run unique 02a300c116bb ; compteur 60 -> 70 avec les 10 voisins) —
CONFIRMEE, de justesse, avec deux alertes :
- VC3  Sharpe 0,80 | CAGR 22,1 % | vol 19,7 % | maxDD -23,2 % (08/11/2021 -> 14/06/2023) |
  turnover 2,2x/an | frais 0,40 %/an. Hold BTC spot 0,45 / -76,7 % ; VC2 0,72 / -34,8 %.
  OOS (>= 2024-07-01) : 0,72 / -19,6 %.
- R1 plateau : mediane des voisins -24,3 % / Sharpe 0,75 => passe. Mais 4 voisins sur 10
  crevent le budget, tous sur les fenetres de momentum (vote BTC 90/180 j : -25,9 / -29,4 % ;
  moteur 90/180 j : -25,8 / -27,6 %) : le budget tient a la fenetre de 126 j.
- R2 DSR 0,42 (N = 70) et 0,06 (N = 5 880) : le Sharpe ne resiste pas au nombre d'essais.
- R3 ALERTE : maxDD bootstrap median -28 %, P(maxDD < -25 %) = 66 a 68 % selon l ; Sharpe
  VC3 - hold +0,35, IC 95 % [-0,31 ; +0,98].
- R4 ALERTE : 2024 fait 50 % du gain (en log) ; 2022 : -5,0 % seulement.
Lecture : pas encore tuee, pas validee. Dans une vraie baisse, attendre plutot -30 % que -23 %.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
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
from beta.strategies import voie_c_verif as vv  # noqa: E402
from beta.strategies import voie_c_voltarget as vc  # noqa: E402

log = logging.getLogger("beta.mesurer_vc3")

ID = "VC3"
DATES_CAUSALITE = ("2022-11-09", "2025-04-07")
MAXDD_MIN = -0.25
L_ALERTE = 20                       # longueur de bloc de l'alerte R3, fixee au preenregistrement
N_REPETITIONS = 2000


def run_id(id_exp: str, signe: str) -> str:
    cle = f"{id_exp}|{signe}|{c2.DEPART_SIMULATION:%Y-%m-%d}|{c2.FIN_BACKTEST:%Y-%m-%d}"
    return hashlib.sha256(cle.encode()).hexdigest()[:12]


def voisin(cfg: dict, chemin: str, valeur) -> dict:
    """La config de VC3 avec UN parametre change (chemin « bloc.cle » du preenregistrement)."""
    v = copy.deepcopy(cfg)
    bloc, cle = chemin.split(".")
    if cle not in v[bloc]:
        raise KeyError(f"voisin {chemin} : cle absente de la config VC3")
    v[bloc][cle] = valeur
    v["version"] = f"{ID}~{chemin}={valeur}"
    return v


def references_vc2(d: dict, jours: pd.DatetimeIndex) -> dict[str, pd.Series]:
    """Les references de la mesure de VC2 (perpetuels), relues dans son script."""
    spec = importlib.util.spec_from_file_location("mesurer_vc2",
                                                  RACINE / "scripts" / "mesurer_vc2.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.references(d, jours)


def maxdd(r: np.ndarray) -> float:
    """Meme convention que `voie_c_voltarget.performance`."""
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
    sommet = equite.loc[:creux].idxmax()
    return sommet, creux, float(dd.min())


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
        log.error("VC3 : causalite en echec %s", ecarts)

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
    refs["VC2 (mesuree le 07/10, perpetuels)"] = pd.Series(
        c2.calculer(d, c2.config("VC2"))["r_net"], index=jours)
    m_train = np.asarray(jours <= c2.FIN_TRAIN)
    m_oos = np.asarray(jours > c2.FIN_TRAIN)

    print(f"VOIE C2 — VC3 (poche maximum, spot), mesure preenregistree, {jours[0]:%Y-%m-%d} -> "
          f"{jours[-1]:%Y-%m-%d} ({len(jours)} j). Sharpe en racine de 252.")
    print("Frais VC3 : spot 10 pb + slippage 5 (BTC/ETH) / 10 pb par cote ; aucun funding.")
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

    p3 = vc.performance(r3)
    sh_hold = vc.performance(hold_spot)["sharpe"]
    ok_dd, ok_sh = p3["mdd"] >= MAXDD_MIN, p3["sharpe"] > sh_hold
    print("\nPORTE (regle preenregistree)")
    print(f"  maxDD {p3['mdd']:6.1%} >= -25 % : {'oui' if ok_dd else 'NON'} | Sharpe "
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
    print(f"  {'VC3 (reglages preenregistres)':<34s}{p3['sharpe']:>8.2f}{p3['cagr']:>8.1%}"
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
              f"{np.percentile(dd, 5):6.1%}, P(maxDD < -25 %) = {p_budget:5.1%} | Sharpe VC3 - "
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

    print(f"\nVERDICT VC3 : {verdict.upper()}"
          + ("" if verdict == "infirmee" else " — admise au forward (dry-run 6 mois des le 08/10)"))
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
