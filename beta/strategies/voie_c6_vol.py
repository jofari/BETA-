"""VC6 — prevision de volatilite : HAR-RV, EGARCH, leur combinaison, contre la vol 30j.

    PYTHONPATH=/root/BETA- /root/venvs/arit/bin/python beta/strategies/voie_c6_vol.py

Question unique : un modele de vol propre (HAR-RV + EGARCH) prevoit-il la variance du
lendemain mieux que la vol realisee glissante 30j qu'utilise la voie C ?

Cible (proxy de la variance du jour t) : variance de Garman-Klass de la bougie 1d du jour t,
    RV_t = 0.5 * ln(H/L)^2 - (2 ln 2 - 1) * ln(C/O)^2
Perpetuels 24/7 : l'ouverture d'une bougie est la cloture de la precedente, le proxy ne
manque donc aucun saut de nuit. Robustesse : meme evaluation contre r_t^2 (rendement
cloture a cloture au carre), le proxy que le benchmark et l'EGARCH visent eux-memes.

Previsions h_t de la variance du jour t, toutes construites sur des donnees <= t-1 :
  R30      variance des log-rendements cloture a cloture sur 30j (ddof=1), decalee d'un jour
           (le sigma de la voie C, `voie_c_voltarget`, au carre) ;
  RV30     moyenne 30j de RV_t (diagnostic : meme fenetre, meilleur estimateur) ;
  HAR      Corsi (2009) en niveaux, MCO sur le train :
           RV_t = b0 + b1 RV_{t-1} + b2 moy5(RV)_{t-1} + b3 moy22(RV)_{t-1} ;
  EGARCH   Nelson (1991), EGARCH(1,1) gaussien, QMLE scipy sur le train :
           ln s2_t = w + a (|z_{t-1}| - E|z|) + g z_{t-1} + b ln s2_{t-1} ;
  C50      exp(0.5 ln HAR + 0.5 ln EGARCH) ;
  CINV     meme combinaison en log-variance, poids inversement proportionnels a la QLIKE
           moyenne des 250 jours precedents (pertes connues a t-1, decalees d'un jour).

Parametres estimes UNE fois sur le train (<= 2024-06-30), figes ensuite : l'OOS ne
re-estime rien. Les 250 premiers jours de poids CINV de l'OOS lisent des pertes du train,
calculees avec des parametres ajustes sur ce train (biais in-sample assume, connu a t-1).

Evaluation : QLIKE de Patton (2011), L = RV/h - ln(RV/h) - 1, robuste au bruit d'un proxy
sans biais ; Diebold-Mariano (HAC Newey-West) sur l'ecart de pertes, par paire et en pool
(moyenne transversale par jour, ce qui absorbe la correlation entre paires) ; couverture de
l'intervalle a 95 % |r_t - mu| <= 1.96 sqrt(h_t), test de Kupiec.

⚠️ Hold-out : l'OOS demande (apres 2024-06-30) deborde sur le hold-out (>= 2025-01-01),
deja CONSOMME pour l'allocation quotidienne (invariant 5, VC2-VC5) — VC6 en releve. Les
resultats sont donc decoupes : 2024S2 (propre, cote train) et 2025+ (deja regarde).

Ce fichier est un SCRIPT DE MESURE, pas une candidate du moteur : il ne passe ni par
`contrats.Run`, ni par le preenregistrement, ni par la batterie S1-S9. Ce qu'il imprime est
une mesure descriptive, pas un verdict d'edge (invariant n° 7).
"""

from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd
from scipy import optimize, stats

from beta.lake.lecture import load
from beta.protocole import holdout
from beta.stats.multitest import benjamini_hochberg

log = logging.getLogger("beta.strategies.voie_c6")

PAIRES = ("BTC", "ETH", "SOL", "BNB", "LINK", "XRP")
FIN_TRAIN = pd.Timestamp("2024-06-30", tz="UTC")
FENETRE_BENCH = 30
FENETRE_POIDS = 250
Z95 = stats.norm.ppf(0.975)
E_ABS_Z = math.sqrt(2.0 / math.pi)

MODELES = ("R30", "RV30", "HAR", "EGARCH", "C50", "CINV")
SEGMENTS = {
    "OOS total": (FIN_TRAIN + pd.Timedelta(days=1), None),
    "2024S2 (propre)": (FIN_TRAIN + pd.Timedelta(days=1), holdout.FIN_TRAIN),
    "2025+ (consomme)": (holdout.DEBUT, None),
}
# Famille DM declaree AVANT le calcul : BH s'applique a elle entiere, rien n'en sort apres.
FAMILLE_DM = (("HAR", "R30"), ("EGARCH", "R30"), ("C50", "R30"), ("CINV", "R30"),
              ("HAR", "EGARCH"), ("CINV", "HAR"), ("CINV", "EGARCH"))


# --- Donnees -----------------------------------------------------------------------------

def donnees(paire: str) -> pd.DataFrame:
    """OHLC 1d, log-rendement cloture a cloture et variance de Garman-Klass du jour."""
    df = load(paire, "1d", colonnes=("open", "high", "low", "close")).set_index("date")
    o, h, l, c = (df[k].astype(float) for k in ("open", "high", "low", "close"))
    out = pd.DataFrame(index=df.index)
    out["r"] = np.log(c).diff()
    gk = 0.5 * np.log(h / l) ** 2 - (2.0 * math.log(2.0) - 1.0) * np.log(c / o) ** 2
    out["rv"] = gk.clip(lower=0.0)
    return out.dropna()


# --- Modeles -----------------------------------------------------------------------------

def prevision_har(rv: pd.Series, train: pd.Series) -> tuple[pd.Series, np.ndarray]:
    """HAR-RV en niveaux. Regresseurs a t-1, cible a t ; MCO sur les seules dates du train."""
    x = pd.DataFrame({"d": rv, "w": rv.rolling(5).mean(), "m": rv.rolling(22).mean()}).shift(1)
    x.insert(0, "c", 1.0)
    ok = x.notna().all(axis=1)
    fit = ok & train
    beta, *_ = np.linalg.lstsq(x[fit].to_numpy(), rv[fit].to_numpy(), rcond=None)
    plancher = rv[train & (rv > 0)].min()
    h = pd.Series(x[ok].to_numpy() @ beta, index=x.index[ok])
    n_clip = int((h < plancher).sum())
    if n_clip:
        log.info("HAR : %d previsions sous le plancher %.2e, relevees", n_clip, plancher)
    return h.clip(lower=plancher).reindex(rv.index), beta


def _egarch_filtre(params: np.ndarray, e: np.ndarray, ls0: float) -> np.ndarray:
    """ln s2_t pour t = 0..n-1 ; ln s2_t ne depend que de e_{<t}."""
    w, a, g, b = params
    ls = np.empty(len(e))
    ls[0] = ls0
    for t in range(1, len(e)):
        z = e[t - 1] * math.exp(-0.5 * ls[t - 1])
        # Borne numerique seulement : l'optimiseur explore des regions explosives.
        ls[t] = min(max(w + a * (abs(z) - E_ABS_Z) + g * z + b * ls[t - 1], -30.0), 5.0)
    return ls


def prevision_egarch(r: pd.Series, train: pd.Series) -> tuple[pd.Series, np.ndarray, float]:
    """EGARCH(1,1) gaussien. QMLE sur le train, puis filtre a parametres figes sur tout."""
    mu = float(r[train].mean())
    e = (r - mu).to_numpy()
    n_tr = int(train.sum())
    ls0 = math.log(float(np.var(e[:n_tr])))

    def nll(p):
        ls = _egarch_filtre(p, e[:n_tr], ls0)
        return 0.5 * np.sum(ls + e[:n_tr] ** 2 * np.exp(-ls))

    depart = np.array([ls0 * 0.05, 0.15, -0.02, 0.95])
    res = optimize.minimize(nll, depart, method="L-BFGS-B",
                            bounds=[(-5, 5), (-1, 1), (-1, 1), (-0.999, 0.999)])
    if not res.success:
        log.warning("EGARCH : optimisation non convergee (%s)", res.message)
    h = pd.Series(np.exp(_egarch_filtre(res.x, e, ls0)), index=r.index)
    return h, res.x, mu


def qlike(rv: pd.Series, h: pd.Series) -> pd.Series:
    """Perte de Patton. Jours a RV = 0 exclus (ln 0) : NaN, ecartes pour tous les modeles."""
    ratio = rv / h
    return (ratio - np.log(ratio) - 1.0).where(rv > 0)


def previsions(paire: str) -> tuple[pd.DataFrame, dict]:
    df = donnees(paire)
    train = pd.Series(df.index <= FIN_TRAIN, index=df.index)
    p = pd.DataFrame(index=df.index)
    p["R30"] = df["r"].rolling(FENETRE_BENCH).var(ddof=1).shift(1)
    p["RV30"] = df["rv"].rolling(FENETRE_BENCH).mean().shift(1)
    p["HAR"], b_har = prevision_har(df["rv"], train)
    p["EGARCH"], b_eg, mu = prevision_egarch(df["r"], train)
    lh, le = np.log(p["HAR"]), np.log(p["EGARCH"])
    p["C50"] = np.exp(0.5 * lh + 0.5 * le)
    # Pertes du jour t-1 connues a la cloture de t-1 : moyenne glissante decalee d'un jour.
    q_h = qlike(df["rv"], p["HAR"]).rolling(FENETRE_POIDS, min_periods=60).mean().shift(1)
    q_e = qlike(df["rv"], p["EGARCH"]).rolling(FENETRE_POIDS, min_periods=60).mean().shift(1)
    w = ((1 / q_h) / (1 / q_h + 1 / q_e)).fillna(0.5)
    p["CINV"] = np.exp(w * lh + (1 - w) * le)
    p["w_har"] = w
    p = p.join(df)
    return p, {"har": b_har, "egarch": b_eg, "mu": mu}


# --- Tests -------------------------------------------------------------------------------

def diebold_mariano(d: pd.Series) -> tuple[float, float]:
    """Stat DM et p-value bilaterale ; variance HAC Newey-West, noyau de Bartlett."""
    d = d.dropna().to_numpy()
    n = len(d)
    if n < 30:
        return math.nan, math.nan
    lag = int(4 * (n / 100) ** (2 / 9))
    u = d - d.mean()
    var = u @ u / n
    for k in range(1, lag + 1):
        var += 2 * (1 - k / (lag + 1)) * (u[k:] @ u[:-k]) / n
    stat = d.mean() / math.sqrt(var / n)
    return stat, 2 * stats.norm.sf(abs(stat))


def couverture(e: pd.Series, h: pd.Series) -> tuple[float, float]:
    """Taux de couverture de |e| <= 1.96 sqrt(h) et p-value de Kupiec (LR, chi2 a 1 ddl)."""
    ok = e.notna() & h.notna()
    hors = (e[ok].abs() > Z95 * np.sqrt(h[ok])).to_numpy()
    n, x = len(hors), int(hors.sum())
    pi0, pi1 = 0.05, x / n
    ll0 = x * math.log(pi0) + (n - x) * math.log(1 - pi0)
    ll1 = (x * math.log(pi1) if x else 0.0) + ((n - x) * math.log(1 - pi1) if x < n else 0.0)
    return 1 - pi1, stats.chi2.sf(-2 * (ll0 - ll1), 1)


def masque(index: pd.Index, debut, fin) -> np.ndarray:
    m = index >= debut
    if fin is not None:
        m &= index <= fin
    return m


# --- Rapport -----------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s : %(message)s")
    toutes, params = {}, {}
    for paire in PAIRES:
        toutes[paire], params[paire] = previsions(paire)

    print("=" * 100)
    print("VC6 — prevision de variance 1 jour, parametres figes sur le train (<= 2024-06-30)")
    print("=" * 100)
    print(f"{'paire':6} {'debut':>11} {'HAR b0':>9} {'b1':>6} {'b2':>6} {'b3':>6}   "
          f"{'EG w':>7} {'a':>6} {'g':>7} {'b':>6}")
    for paire in PAIRES:
        bh, be = params[paire]["har"], params[paire]["egarch"]
        print(f"{paire:6} {toutes[paire].index[0]:%Y-%m-%d} {bh[0]:9.2e} {bh[1]:6.3f} "
              f"{bh[2]:6.3f} {bh[3]:6.3f}   {be[0]:7.3f} {be[1]:6.3f} {be[2]:7.3f} {be[3]:6.3f}")

    for proxy, nom_proxy in (("rv", "Garman-Klass"), ("r2", "r^2 cloture-cloture")):
        for seg, (debut, fin) in SEGMENTS.items():
            pertes = {}      # modele -> DataFrame (dates x paires)
            for m in MODELES:
                cols = {}
                for paire, p in toutes.items():
                    sel = p[masque(p.index, debut, fin)]
                    cible = sel["rv"] if proxy == "rv" else (sel["r"] - params[paire]["mu"]) ** 2
                    if proxy == "rv":
                        cols[paire] = qlike(cible, sel[m])
                    else:
                        # r^2 = 0 rend ln(r^2/h) infini : forme ln h + r^2/h, memes ecarts.
                        cols[paire] = np.log(sel[m]) + cible / sel[m]
                pertes[m] = pd.DataFrame(cols)
            # Meme echantillon pour tous les modeles : jours ou chacun a une perte finie.
            commun = np.isfinite(pd.concat(pertes.values(), axis=1)).all(axis=1)
            for m in MODELES:
                pertes[m] = pertes[m][commun]
            n_j = int(commun.sum())

            print("\n" + "=" * 100)
            print(f"[{seg}]  proxy = {nom_proxy}  ·  {n_j} jours communs  ·  "
                  f"QLIKE moyenne (plus bas = mieux)"
                  + ("" if proxy == "rv" else "  [forme ln h + r2/h]"))
            print("=" * 100)
            print(f"{'modele':8}" + "".join(f"{x:>9}" for x in PAIRES) + f"{'POOL':>9}"
                  + f"{'vs R30':>9}")
            ref = pertes["R30"].mean(axis=1).mean()
            for m in MODELES:
                moy = pertes[m].mean()
                pool = pertes[m].mean(axis=1).mean()
                rel = f"{pool / ref - 1:+8.1%}" if proxy == "rv" else f"{pool - ref:+8.3f}"
                print(f"{m:8}" + "".join(f"{v:9.3f}" for v in moy) + f"{pool:9.3f}" + f" {rel}")

            lignes = []
            for a, b in FAMILLE_DM:
                d_pool = (pertes[a] - pertes[b]).mean(axis=1)
                s, pv = diebold_mariano(d_pool)
                par_paire = [diebold_mariano(pertes[a][x] - pertes[b][x]) for x in PAIRES]
                lignes.append({"test": f"{a} - {b}", "dm": s, "p_brute": pv,
                               "gagne": a if s < 0 else b,
                               "paires": " ".join(f"{x}:{'+' if st < 0 else '-'}{pp:.2f}"
                                                  for x, (st, pp) in zip(PAIRES, par_paire))})
            table = benjamini_hochberg(pd.DataFrame(lignes))
            print(f"\n  Diebold-Mariano en pool (DM < 0 : le premier a la perte la plus basse)"
                  f" · BH FDR 10 % sur les {len(FAMILLE_DM)} tests")
            print(f"  {'test':16} {'DM':>7} {'p':>8} {'BH':>4}  {'meilleur':8}  "
                  f"par paire (+ = premier meilleur : p)")
            for _, l in table.sort_values("test", key=lambda s: s.map(
                    {f'{a} - {b}': i for i, (a, b) in enumerate(FAMILLE_DM)})).iterrows():
                print(f"  {l['test']:16} {l['dm']:7.2f} {l['p_brute']:8.4f} "
                      f"{'oui' if l['signif_BH'] else 'non':>4}  {l['gagne']:8}  {l['paires']}")

            if proxy == "rv":
                print(f"\n  Couverture de l'intervalle 95 % sur le rendement "
                      f"(taux · p Kupiec), memes jours")
                print(f"  {'modele':8}" + "".join(f"{x:>14}" for x in PAIRES) + f"{'POOL':>9}")
                for m in MODELES:
                    cells, tot_in, tot_n = [], 0, 0
                    for paire in PAIRES:
                        p = toutes[paire].loc[pertes[m].index]
                        e = p["r"] - params[paire]["mu"]
                        taux, pk = couverture(e, p[m])
                        cells.append(f"{taux:7.1%} ({pk:.2f})")
                        tot_in += taux * len(p)
                        tot_n += len(p)
                    print(f"  {m:8}" + "".join(f"{c:>14}" for c in cells)
                          + f"{tot_in / tot_n:9.1%}")

    w = pd.concat({x: toutes[x]["w_har"][toutes[x].index > FIN_TRAIN] for x in PAIRES}, axis=1)
    print(f"\nPoids HAR moyen de CINV sur l'OOS : "
          + " ".join(f"{x}:{v:.2f}" for x, v in w.mean().items()))
    print("\n" + "=" * 100)
    print("Rappel de protocole : ce script ne passe ni par le preenregistrement, ni par la")
    print("batterie S1-S9. Il MESURE une construction fixee a l'avance ; il ne CONFIRME rien.")
    print("=" * 100)


if __name__ == "__main__":
    main()
