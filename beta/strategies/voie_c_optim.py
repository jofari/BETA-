"""Voie C — optimisation des parametres de GESTION, sur le TRAIN seul, par plateau.

    ARIT_HOME=/root/ARIT2.0 PYTHONPATH=/root/BETA- \
        /root/venvs/arit/bin/python beta/strategies/voie_c_optim.py

Ce qui est optimise : la gestion du portefeuille, jamais les jambes. Les trois jambes et leur
melange 1/3 restent ceux de `voie_c_voltarget` (fixes a priori). La grille, declaree ICI et
commitee AVANT le premier lancement :

    sigma cible     0,15 0,20 0,25 0,30 0,35 0,45
    estimateur      ecart-type glissant | EWMA (demi-vie = fenetre / 2)
    fenetre vol     20 30 45 60 90 jours
    levier max      1,0 1,5 2,0 3,0
    levier min      0 | 0,33
    pas de reequil. 1 3 7 jours
    bande           0 5 10 20 % : au jour de reequilibrage, on ne trade que si l'ecart
                    brut sum|voulu - tenu derive| depasse la bande (sinon on laisse deriver)

Regle de choix, fixee avant de voir un seul chiffre :

1. Les parametres de STRUCTURE (estimateur, fenetre, bornes, pas, bande) sont choisis sur le
   Sharpe NET du TRAIN, lisse par PLATEAU : chaque config est notee par la mediane de son
   Sharpe et de celui de ses voisines immediates sur chaque axe ordonne. Un pic isole entoure
   de mauvais voisins est du bruit de selection ; un plateau est une propriete.
2. La sigma CIBLE n'est pas un parametre de performance (a levier libre elle ne change pas le
   Sharpe) : c'est un BUDGET DE RISQUE. On retient la plus haute cible dont le maxDD net du
   TRAIN reste au-dessus de -25 % (livrable de A2).
3. L'OOS (2024-07-01 -> 2026-09-05) est imprime pour la config retenue et la reference
   precedente, A TITRE D'INFORMATION : il est deja brule par `voie_c_voltarget`, il ne sert
   a rien choisir ici.

SCELLE : tout ce qui est posterieur a FIN_VUE (2026-09-05, derniere date que la mesure du
22/09 avait vue) n'est jamais charge dans ce script. Ce mois-la est le debut du suivi forward
de la config figee ; le regarder pour choisir le brulerait.
"""

from __future__ import annotations

import itertools
import logging
import math

import numpy as np
import pandas as pd

from beta.strategies import voie_c_voltarget as vc

log = logging.getLogger("beta.strategies.voie_c_optim")

FIN_VUE = pd.Timestamp("2026-09-05", tz="UTC")
FIN_TRAIN = pd.Timestamp(vc.FIN_TRAIN, tz="UTC")
DEBUT_OOS = pd.Timestamp(vc.DEBUT_TEST, tz="UTC")

CIBLES = (0.15, 0.20, 0.25, 0.30, 0.35, 0.45)
ESTIMATEURS = ("glissant", "ewma")
FENETRES = (20, 30, 45, 60, 90)
LEVIERS_MAX = (1.0, 1.5, 2.0, 3.0)
LEVIERS_MIN = (0.0, 0.33)
PAS = (1, 3, 7)
BANDES = (0.0, 0.05, 0.10, 0.20)

DD_BUDGET = -0.25
REFERENCE = {"cible": 0.25, "estimateur": "glissant", "fenetre": 30, "lmax": 2.0,
             "lmin": 0.33, "pas": 1, "bande": 0.0}

# Axes ordonnes sur lesquels on cherche les voisines (l'estimateur n'est pas ordonne : une
# voisine « de l'autre estimateur » n'a pas de sens de proximite).
AXES = {"fenetre": FENETRES, "lmax": LEVIERS_MAX, "lmin": LEVIERS_MIN, "pas": PAS,
        "bande": BANDES}


# =========================================================================================
# Donnees, tronquees a FIN_VUE
# =========================================================================================

def donnees() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """closes, rendements, funding quotidien — rien apres FIN_VUE, verifie et non suppose."""
    index = vc.calendrier_commun(vc.PAIRES)
    index = index[index <= FIN_VUE]
    closes = vc.clotures(vc.PAIRES, index)
    funding_j = vc.funding_quotidien(vc.PAIRES, index)
    assert closes.index.max() <= FIN_VUE and funding_j.index.max() <= FIN_VUE
    return closes, closes.pct_change(), funding_j


def sigma_composite(r_comp: pd.Series, estimateur: str, fenetre: int) -> pd.Series:
    """Vol annualisee du composite non levier. EWMA : demi-vie fenetre/2, meme rodage."""
    if estimateur == "glissant":
        s = r_comp.rolling(fenetre, min_periods=fenetre).std(ddof=1)
    else:
        s = r_comp.ewm(halflife=fenetre / 2, min_periods=fenetre).std()
    return s * math.sqrt(vc.PPA)


# =========================================================================================
# Moteur : celui de voie_c_voltarget, plus une bande de non-reequilibrage
# =========================================================================================

def derouler_bande(cible: np.ndarray, rend: np.ndarray, fund: np.ndarray, pas: int,
                   bande: float, bps: float) -> tuple[np.ndarray, np.ndarray]:
    """Meme derive, memes frais que `vc.derouler` ; bande = 0 le reproduit a l'identique.

    Rend (r_net, r_brut). La bande s'applique a l'ecart BRUT total : un portefeuille dont
    l'ecart a la cible reste sous la bande continue de deriver, et ne paie rien.
    """
    n_jours, n_actifs = cible.shape
    cout = bps / 1e4
    r_brut = np.zeros(n_jours)
    r_net = np.zeros(n_jours)
    tenu = np.zeros(n_actifs)
    derive = np.zeros(n_actifs)
    for i in range(n_jours):
        if i > 0:
            derive = tenu * (1.0 + rend[i - 1]) / (1.0 + r_brut[i - 1])
        tenu = derive
        if i % pas == 0:
            voulu = np.where(np.isnan(cible[i]), 0.0, cible[i])
            ecart = np.abs(voulu - derive).sum()
            # Premier jour, ou tenu a plat : la bande ne doit pas empecher d'ENTRER.
            if ecart > bande or not derive.any():
                tenu = voulu
        turnover = np.abs(tenu - derive).sum()
        r_brut[i] = np.nansum(tenu * rend[i])
        r_net[i] = r_brut[i] - turnover * cout - np.nansum(tenu * fund[i])
    return r_net, r_brut


# =========================================================================================
# Grille
# =========================================================================================

def evaluer() -> tuple[pd.DataFrame, dict]:
    closes, rendements, funding_j = donnees()
    comp = vc.composite(vc.jambe_base(rendements), vc.jambe_trend(closes, rendements),
                        vc.jambe_carry(funding_j))
    r_comp = (comp.shift(1) * rendements).sum(axis=1, skipna=False)

    sigmas = {(e, f): sigma_composite(r_comp, e, f) for e in ESTIMATEURS for f in FENETRES}

    # Une fenetre d'evaluation COMMUNE a toutes les configs : la plus lente (90j) doit exister.
    causal = comp.shift(1).notna().all(axis=1) & rendements.notna().all(axis=1)
    for s in sigmas.values():
        causal &= s.shift(1).notna()
    depart = closes.index[causal.to_numpy()][0]
    fenetre = closes.index[closes.index >= depart]

    rend = rendements.reindex(fenetre).to_numpy(dtype=float)
    fund = funding_j.reindex(fenetre).to_numpy(dtype=float)
    poids = comp.shift(1).reindex(fenetre).to_numpy(dtype=float)
    m_train = np.asarray(fenetre <= FIN_TRAIN)
    m_oos = np.asarray(fenetre >= DEBUT_OOS)
    milieu = fenetre[m_train][m_train.sum() // 2]
    m_t1 = m_train & np.asarray(fenetre < milieu)
    m_t2 = m_train & np.asarray(fenetre >= milieu)

    lignes = []
    combos = list(itertools.product(CIBLES, ESTIMATEURS, FENETRES, LEVIERS_MAX, LEVIERS_MIN,
                                    PAS, BANDES))
    log.warning("%d configurations, fenetre %s -> %s", len(combos),
                f"{fenetre[0]:%Y-%m-%d}", f"{fenetre[-1]:%Y-%m-%d}")
    for cible, est, fen, lmax, lmin, pas, bande in combos:
        lev = (cible / sigmas[(est, fen)].replace(0.0, np.nan)).clip(lmin, lmax)
        lev = lev.shift(1).reindex(fenetre).to_numpy(dtype=float)
        r_net, _ = derouler_bande(poids * lev[:, None], rend, fund, pas, bande, vc.BPS_TAKER)
        r = pd.Series(r_net, index=fenetre)
        tr, oos = vc.performance(r[m_train]), vc.performance(r[m_oos])
        lignes.append({
            "cible": cible, "estimateur": est, "fenetre": fen, "lmax": lmax, "lmin": lmin,
            "pas": pas, "bande": bande,
            "sh_train": tr["sharpe"], "dd_train": tr["mdd"], "cagr_train": tr["cagr"],
            "sh_t1": vc.performance(r[m_t1])["sharpe"],
            "sh_t2": vc.performance(r[m_t2])["sharpe"],
            "sh_oos": oos["sharpe"], "dd_oos": oos["mdd"], "cagr_oos": oos["cagr"],
            "vol_oos": oos["vol"],
        })
    contexte = {"debut": fenetre[0], "fin": fenetre[-1], "milieu_train": milieu,
                "n_train": int(m_train.sum()), "n_oos": int(m_oos.sum())}
    return pd.DataFrame(lignes), contexte


def plateau(grille: pd.DataFrame) -> pd.Series:
    """Mediane du Sharpe TRAIN de la config et de ses voisines immediates, axe par axe."""
    cles = ["cible", "estimateur", *AXES]
    sh = grille.set_index(cles)["sh_train"]
    notes = []
    for ligne in grille[cles].itertuples(index=False):
        point = dict(zip(cles, ligne))
        valeurs = [sh[tuple(point.values())]]
        for axe, niveaux in AXES.items():
            k = niveaux.index(point[axe])
            for j in (k - 1, k + 1):
                if 0 <= j < len(niveaux):
                    voisin = {**point, axe: niveaux[j]}
                    valeurs.append(sh[tuple(voisin.values())])
        notes.append(float(np.median(valeurs)))
    return pd.Series(notes, index=grille.index)


# =========================================================================================
# Rapport
# =========================================================================================

def nom(c: dict | pd.Series) -> str:
    return (f"{c['cible']:.0%} {c['estimateur']:<8s} {int(c['fenetre']):>2d}j "
            f"L[{c['lmin']:.2f};{c['lmax']:.1f}] pas {int(c['pas'])} bande {c['bande']:.0%}")


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    grille, ctx = evaluer()
    grille["plateau"] = plateau(grille)

    print("=" * 100)
    print("VOIE C — optimisation de la GESTION, choix sur le TRAIN seul, par plateau")
    print("=" * 100)
    print(f"Fenetre commune : {ctx['debut']:%Y-%m-%d} -> {ctx['fin']:%Y-%m-%d} "
          f"(scelle apres {FIN_VUE:%Y-%m-%d})")
    print(f"TRAIN {ctx['n_train']} j (moities coupees au {ctx['milieu_train']:%Y-%m-%d}) | "
          f"OOS {ctx['n_oos']} j, deja brule, informatif")
    print(f"{len(grille)} configurations | Sharpe net TRAIN : mediane "
          f"{grille['sh_train'].median():.2f}, max {grille['sh_train'].max():.2f}")

    # Etape 1 — structure, cible mise de cote : on agrege le plateau sur les cibles, puisque
    # la cible n'est qu'un budget de risque.
    struct = ["estimateur", *AXES]
    par_struct = grille.groupby(struct)[["plateau", "sh_train", "sh_t1", "sh_t2"]].median()
    par_struct = par_struct.sort_values("plateau", ascending=False)
    print("\nETAPE 1 — STRUCTURE : 10 meilleurs plateaux (medianes sur les 6 cibles)")
    print(f"  {'estim.':<9s}{'fen':>4s}{'Lmax':>6s}{'Lmin':>6s}{'pas':>5s}{'bande':>7s}"
          f"{'plateau':>9s}{'Sh train':>10s}{'moitie 1':>10s}{'moitie 2':>10s}")
    for cle, v in par_struct.head(10).iterrows():
        est, fen, lmax, lmin, pas, bande = cle
        print(f"  {est:<9s}{fen:>4d}{lmax:>6.1f}{lmin:>6.2f}{pas:>5d}{bande:>7.0%}"
              f"{v['plateau']:>9.2f}{v['sh_train']:>10.2f}{v['sh_t1']:>10.2f}{v['sh_t2']:>10.2f}")
    retenue_struct = dict(zip(struct, par_struct.index[0]))

    # Sensibilite : chaque axe, les autres figes a la structure retenue.
    print("\n  Sensibilite autour de la structure retenue (Sharpe net TRAIN, mediane des cibles)")
    for axe in ["estimateur", *AXES]:
        autres = {k: v for k, v in retenue_struct.items() if k != axe}
        sel = grille
        for k, v in autres.items():
            sel = sel[sel[k] == v]
        prof = sel.groupby(axe)["sh_train"].median()
        print(f"    {axe:<11s}" + "  ".join(f"{k}: {v:.2f}" for k, v in prof.items()))

    # Etape 2 — budget de risque.
    sel = grille
    for k, v in retenue_struct.items():
        sel = sel[sel[k] == v]
    sel = sel.sort_values("cible")
    print("\nETAPE 2 — BUDGET DE RISQUE : plus haute cible avec maxDD net TRAIN > "
          f"{DD_BUDGET:.0%}")
    print(f"  {'cible':>6s}{'Sh train':>10s}{'DD train':>10s}{'CAGR train':>12s}")
    for _, v in sel.iterrows():
        print(f"  {v['cible']:>6.0%}{v['sh_train']:>10.2f}{v['dd_train']:>10.1%}"
              f"{v['cagr_train']:>12.1%}")
    admissibles = sel[sel["dd_train"] > DD_BUDGET]
    if admissibles.empty:
        print("  Aucune cible ne tient le budget : on retient la plus basse.")
        retenue = sel.iloc[0]
    else:
        retenue = admissibles.iloc[-1]

    ref = grille
    for k, v in REFERENCE.items():
        ref = ref[ref[k] == v]
    ref = ref.iloc[0]
    meilleure_brute = grille.loc[grille["sh_train"].idxmax()]

    print("\n" + "=" * 100)
    print("RESULTAT — la config retenue, la reference du 22/09, et le pic brut du train")
    print("=" * 100)
    print(f"  {'':<52s}{'Sh tr':>7s}{'DD tr':>8s}{'Sh OOS':>8s}{'DD OOS':>8s}"
          f"{'CAGR OOS':>10s}{'vol OOS':>9s}")
    for titre, c in (("RETENUE  ", retenue), ("reference", ref), ("pic brut ", meilleure_brute)):
        print(f"  {titre} {nom(c):<42s}{c['sh_train']:>7.2f}{c['dd_train']:>8.1%}"
              f"{c['sh_oos']:>8.2f}{c['dd_oos']:>8.1%}{c['cagr_oos']:>10.1%}{c['vol_oos']:>9.1%}")
    rang = grille["sh_oos"].rank(pct=True)
    print(f"\n  Rang OOS de la retenue parmi les {len(grille)} configs : "
          f"{rang[retenue.name]:.0%} (50 % = ce qu'un tirage au hasard ferait)")
    print("  L'OOS est informatif : il a deja servi le 22/09, il ne confirme rien. La seule")
    print(f"  validation qui reste est le suivi forward, a partir du {FIN_VUE + pd.Timedelta(days=1):%Y-%m-%d}.")


if __name__ == "__main__":
    main()
