"""Voie A — allocation multi-actifs inverse-vol avec tilt de regime, optimisee train/test.

    ARIT_HOME=/root/ARIT2.0 PYTHONPATH=/root/BETA- \
        /root/venvs/arit/bin/python beta/strategies/voie_a_allocation.py

Ce que fait ce script, dans l'ordre :

1. **Fenetre commune.** 11 actifs (6 perpetuels + 5 indices), intersection stricte des dates
   quotidiennes. L'intersection est un calendrier de jours OUVRES : c'est SOL (listee le
   2020-09-14) qui fixe le debut, et l'union des jours feries NY/Paris qui creuse le reste.
   Les rendements crypto sont calcules SUR CE CALENDRIER : un rendement du lundi couvre donc
   reellement vendredi->lundi. Le faire autrement sous-estimerait la vol crypto.

2. **Boite a outils de regime.** Sept indicateurs, tous ramenes a un percentile glissant 180j
   dans [0, 1] — c'est ce qui permet un seuil unique et comparable d'un indicateur a l'autre.
   Macro (VIX, spread credit Baa10Y, pente 2s10s, breakeven 10 ans, DXY) et crypto (funding
   moyen des 6 paires, Fear & Greed).

3. **Poids.** Inverse-vol (vol realisee glissante 180j), puis tilt de regime : risk-off
   favorise les refuges (XAUUSD, SP500), risk-on favorise le risque (crypto, NASDAQ).

4. **Optimisation.** Grid-search des seuils de regime et du tilt sur le TRAIN (<= 2023-12-31),
   au Sharpe. Une seule combinaison retenue, appliquee telle quelle sur le TEST (2024+).

Causalite — la seule chose qui rende ces chiffres lisibles :
- toute la matrice de poids subit un `shift(1)` avant de rencontrer les rendements, donc le
  poids du jour t est entierement determine par des donnees <= t-1 ;
- les series FRED subissent un decalage SUPPLEMENTAIRE d'un jour (`DECALAGE_FRED`) : une
  observation datee du jour d n'est publiee qu'apres la cloture de d. Le signal du jour t ne
  voit donc la macro que jusqu'a t-2. Conservateur a dessein ;
- les percentiles glissants sont des `rolling(...).rank(pct=True)` : le rang de l'observation
  courante DANS SA PROPRE fenetre passee, jamais dans la serie entiere.

Ce que ce script ne fait PAS : il ne prouve rien. 216 combinaisons sont essayees sur le
train ; le Sharpe train retenu est un maximum d'echantillon, donc biaise vers le haut par
construction. Le rapport imprime l'ecart best/median du grid pour que la prime de selection
se voie. Seul le bloc TEST compte, et il n'a ete regarde qu'une fois.
"""

from __future__ import annotations

import itertools
import logging
import math
import warnings

import numpy as np
import pandas as pd

from beta.lake.lecture import fear_greed, funding, load, macro_globales

log = logging.getLogger("beta.strategies.voie_a")

# --- Univers -----------------------------------------------------------------------------

CRYPTO = ("BTC", "ETH", "SOL", "BNB", "LINK", "XRP")
INDICES = ("SP500", "NASDAQ", "CAC40", "MSCIWORLD", "XAUUSD")
ACTIFS = CRYPTO + INDICES

# Qui est favorise dans quel regime. Les refuges sont l'or et le SP500 (le grand indice
# large, pas le NASDAQ qui est un actif de duration donc de risque) ; le risque est la crypto
# et le NASDAQ. CAC40 et MSCIWORLD ne sont dans aucun des deux camps : ils subissent la
# renormalisation, ce qui suffit a les faire bouger dans le bon sens.
REFUGES = ("XAUUSD", "SP500")
RISQUES = CRYPTO + ("NASDAQ",)

# --- Fenetres et dates -------------------------------------------------------------------

FENETRE_VOL = 180            # vol realisee, en jours du calendrier commun
FENETRE_PCT = 180            # percentile glissant des indicateurs de regime
FIN_TRAIN = "2023-12-31"
DEBUT_TEST = "2024-01-01"

# Publication FRED : une observation datee du jour d sort apres la cloture de d. Un jour de
# decalage en plus du shift(1) general — on prefere perdre un jour d'information que de
# fabriquer un look-ahead invisible.
DECALAGE_FRED = 1

# --- Grille d'optimisation ---------------------------------------------------------------

# Un seuil par indicateur, exprime en percentile. Lecture : `s` est la coupure haute,
# `1 - s` la coupure basse. 0.667 = les tiers exacts.
SEUILS_VIX = (0.60, 0.667, 0.80)
SEUILS_BAA = (0.60, 0.667, 0.80)
SEUILS_AUX = (0.65, 0.80)      # partage par les 5 indicateurs secondaires
VOTES_MIN = (1, 2, 3)          # combien de voix nettes font basculer le regime
TILTS = (0.1, 0.2, 0.3, 0.5)

COUT_BPS = 10.0                # cout aller-retour suppose, pour le diagnostic net de frais


class StrategieError(RuntimeError):
    """Donnee insuffisante pour construire l'allocation."""


# =========================================================================================
# Chargement
# =========================================================================================

def index_commun() -> pd.DatetimeIndex:
    """Intersection stricte des dates quotidiennes des 11 actifs."""
    commun: set | None = None
    for actif in ACTIFS:
        dates = set(load(actif, "1d", colonnes=("close",))["date"])
        commun = dates if commun is None else (commun & dates)
    if not commun:
        raise StrategieError("intersection des dates vide")
    return pd.DatetimeIndex(sorted(commun), name="date")


def cloture(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Matrice des cloture, une colonne par actif, sur le calendrier commun."""
    colonnes = {}
    for actif in ACTIFS:
        df = load(actif, "1d", colonnes=("close",)).set_index("date")["close"]
        colonnes[actif] = df.reindex(index).astype(float)
    out = pd.DataFrame(colonnes, index=index)
    if out.isna().any().any():
        raise StrategieError("trous dans la matrice de cloture malgre l'intersection")
    return out


def _reindexer_ffill(serie: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    """Derniere valeur connue a chaque date du calendrier commun (niveau, pas flux)."""
    union = serie.index.union(index)
    return serie.reindex(union).ffill().reindex(index)


def _moyenne_par_intervalle(serie: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    """Moyenne des valeurs quotidiennes tombant dans (index[i-1], index[i]].

    Pour un FLUX (le funding est paye trois fois par jour, week-end compris), la derniere
    valeur connue perdrait le week-end entier. On moyenne sur l'intervalle reellement couvert
    par le pas du calendrier commun.
    """
    pos = index.searchsorted(serie.index, side="left")
    garde = pos < len(index)
    agg = serie[garde].groupby(pos[garde]).mean()
    out = pd.Series(np.nan, index=index, dtype=float)
    out.iloc[agg.index.to_numpy()] = agg.to_numpy()
    return out


def funding_moyen(index: pd.DatetimeIndex) -> pd.Series:
    """Taux de financement moyen des 6 perpetuels, agrege sur le calendrier commun."""
    morceaux = []
    for paire in CRYPTO:
        try:
            f = funding(paire).set_index("date")["funding_rate"].astype(float)
        except Exception as exc:                       # une paire sans funding ne tue pas tout
            log.warning("funding indisponible pour %s : %s", paire, exc)
            continue
        morceaux.append(_moyenne_par_intervalle(f, index).rename(paire))
    if not morceaux:
        raise StrategieError("aucun funding lisible")
    return pd.concat(morceaux, axis=1).mean(axis=1, skipna=True)


# =========================================================================================
# Boite a outils de regime
# =========================================================================================

def percentile_glissant(serie: pd.Series, fenetre: int = FENETRE_PCT) -> pd.Series:
    """Rang de l'observation courante dans sa fenetre passee, en [0, 1].

    `rolling.rank` classe le point courant PARMI les `fenetre` derniers points, lui compris :
    aucune valeur future n'entre dans le calcul.
    """
    return serie.rolling(fenetre, min_periods=fenetre // 2).rank(pct=True)


def boite_a_outils(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Les 7 indicateurs de regime, tous en percentile glissant 180j, tous causaux.

    Colonnes rendues, et le sens du risk-off pour chacune :
      vix          percentile haut  -> stress
      baa10y       percentile haut  -> stress credit
      dxy          percentile haut  -> squeeze dollar
      courbe       percentile BAS   -> 2s10s aplatie/inversee, signal de recession
      breakeven    percentile BAS   -> effondrement des anticipations d'inflation
      funding      percentile haut  -> longs crypto surpeuples (lecture contrarienne)
      fng          percentile haut  -> avidite (lecture contrarienne)

    Les deux dernieres sont contrariennes ; c'est une HYPOTHESE, pas un fait, et c'est
    exactement le genre d'hypothese que le train/test est la pour tuer.
    """
    macro = macro_globales()
    manquantes = [c for c in ("vix", "baa10y", "dxy", "spread_2s10s", "breakeven10y")
                  if c not in macro.columns]
    if manquantes:
        raise StrategieError(f"series macro absentes : {', '.join(manquantes)}")

    feats = pd.DataFrame(index=index)
    # Decalage FRED applique sur le NIVEAU, avant le percentile : la fenetre glissante ne
    # doit pas non plus contenir l'observation non encore publiee.
    for colonne, nom in (("vix", "vix"), ("baa10y", "baa10y"), ("dxy", "dxy"),
                         ("spread_2s10s", "courbe"), ("breakeven10y", "breakeven")):
        niveau = _reindexer_ffill(macro[colonne].dropna().astype(float), index)
        feats[nom] = percentile_glissant(niveau.shift(DECALAGE_FRED))

    feats["funding"] = percentile_glissant(funding_moyen(index))
    fng = fear_greed().set_index("date")["fng"].astype(float)
    feats["fng"] = percentile_glissant(_reindexer_ffill(fng, index))
    return feats


def votes(feats: pd.DataFrame, s_vix: float, s_baa: float, s_aux: float) -> pd.Series:
    """Score net de risk-off : somme de 7 voix dans {-1, 0, +1}.

    Une voix vaut +1 quand l'indicateur crie risk-off, -1 quand il crie risk-on, 0 entre les
    deux. Un NaN (debut de fenetre) vaut 0 : l'indicateur s'abstient, il ne penche pas.
    """
    def voix(col: str, seuil: float, inverse: bool = False) -> pd.Series:
        p = feats[col]
        haut, bas = (p > seuil).astype(int), (p < 1.0 - seuil).astype(int)
        v = (bas - haut) if inverse else (haut - bas)
        return v.where(p.notna(), 0)

    return (voix("vix", s_vix) + voix("baa10y", s_baa)
            + voix("dxy", s_aux)
            + voix("courbe", s_aux, inverse=True)
            + voix("breakeven", s_aux, inverse=True)
            + voix("funding", s_aux) + voix("fng", s_aux))


def regime(score: pd.Series, votes_min: int) -> pd.Series:
    """{-1 risk-on, 0 neutre, +1 risk-off} a partir du score net."""
    return pd.Series(np.where(score >= votes_min, 1,
                              np.where(score <= -votes_min, -1, 0)),
                     index=score.index, dtype=int)


# =========================================================================================
# Poids
# =========================================================================================

def poids_inverse_vol(rendements: pd.DataFrame, fenetre: int = FENETRE_VOL) -> pd.DataFrame:
    """w_i = (1/sigma_i) / somme(1/sigma_j), sigma = vol realisee glissante."""
    sigma = rendements.rolling(fenetre, min_periods=fenetre).std(ddof=1)
    inverse = 1.0 / sigma.replace(0.0, np.nan)
    return inverse.div(inverse.sum(axis=1), axis=0)


def appliquer_tilt(base: pd.DataFrame, reg: pd.Series, tilt: float) -> pd.DataFrame:
    """Multiplie le camp favorise par (1 + tilt), puis renormalise la ligne a 1."""
    mult = pd.DataFrame(1.0, index=base.index, columns=base.columns)
    off, on = (reg == 1).to_numpy(), (reg == -1).to_numpy()
    for actif in REFUGES:
        mult.loc[off, actif] = 1.0 + tilt
    for actif in RISQUES:
        mult.loc[on, actif] = 1.0 + tilt
    tilte = base * mult
    return tilte.div(tilte.sum(axis=1), axis=0)


def rendement_portefeuille(poids: pd.DataFrame, rendements: pd.DataFrame) -> pd.Series:
    """Le `shift(1)` est le verrou de causalite : le poids du jour t vient de t-1."""
    return (poids.shift(1) * rendements).sum(axis=1, skipna=False)


# =========================================================================================
# Mesure
# =========================================================================================

def periodes_par_an(index: pd.DatetimeIndex) -> float:
    annees = (index[-1] - index[0]).days / 365.25
    return len(index) / annees


def performance(rendements: pd.Series, ppa: float) -> dict:
    """CAGR, vol annualisee, Sharpe (rf = 0), max drawdown."""
    r = rendements.dropna()
    if len(r) < 2:
        return {"cagr": np.nan, "vol": np.nan, "sharpe": np.nan, "mdd": np.nan, "n": len(r)}
    equity = (1.0 + r).cumprod()
    annees = (r.index[-1] - r.index[0]).days / 365.25
    sigma = r.std(ddof=1)
    return {
        "cagr": equity.iloc[-1] ** (1.0 / annees) - 1.0,
        "vol": sigma * math.sqrt(ppa),
        "sharpe": (r.mean() / sigma * math.sqrt(ppa)) if sigma > 0 else np.nan,
        "mdd": (equity / equity.cummax() - 1.0).min(),
        "n": len(r),
    }


def rotation(poids: pd.DataFrame) -> pd.Series:
    """Rotation quotidienne = somme des |variations de poids| / 2 (un sens de l'echange)."""
    return poids.diff().abs().sum(axis=1) / 2.0


# =========================================================================================
# Optimisation train / test
# =========================================================================================

def sharpe(rendements: pd.Series, ppa: float) -> float:
    r = rendements.dropna()
    if len(r) < 30 or r.std(ddof=1) == 0:
        return float("-inf")
    return float(r.mean() / r.std(ddof=1) * math.sqrt(ppa))


def grid_search(base: pd.DataFrame, feats: pd.DataFrame, rendements: pd.DataFrame,
                masque_train: pd.Series, ppa: float) -> tuple[dict, list[tuple[float, dict]]]:
    """Maximise le Sharpe TRAIN. Rend la combinaison gagnante et le classement complet.

    Le classement complet n'est pas decoratif : l'ecart entre le meilleur et la mediane du
    grid est la mesure directe de ce que la selection a offert au hasard.
    """
    resultats: list[tuple[float, dict]] = []
    for s_vix, s_baa, s_aux, votes_min in itertools.product(
            SEUILS_VIX, SEUILS_BAA, SEUILS_AUX, VOTES_MIN):
        reg = regime(votes(feats, s_vix, s_baa, s_aux), votes_min)
        for tilt in TILTS:
            poids = appliquer_tilt(base, reg, tilt)
            rp = rendement_portefeuille(poids, rendements)[masque_train]
            resultats.append((sharpe(rp, ppa),
                              {"s_vix": s_vix, "s_baa": s_baa, "s_aux": s_aux,
                               "votes_min": votes_min, "tilt": tilt}))
    resultats.sort(key=lambda x: x[0], reverse=True)
    return resultats[0][1], resultats


# =========================================================================================
# Rapport
# =========================================================================================

def _ligne(nom: str, perf: dict) -> str:
    return (f"  {nom:<26s} {perf['cagr']:>8.2%} {perf['vol']:>9.2%} "
            f"{perf['sharpe']:>8.2f} {perf['mdd']:>9.2%}")


def main() -> None:
    warnings.filterwarnings("ignore", category=FutureWarning)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    index = index_commun()
    ppa = periodes_par_an(index)
    closes = cloture(index)
    rendements = closes.pct_change()

    feats = boite_a_outils(index)
    base = poids_inverse_vol(rendements)

    # Premiere date ou TOUT est pret : vol des 11 actifs et rendement du jour.
    utilisable = base.notna().all(axis=1) & rendements.notna().all(axis=1)
    depart = index[utilisable.to_numpy()][0]
    masque = pd.Series(index >= depart, index=index)
    masque_train = masque & (index <= pd.Timestamp(FIN_TRAIN, tz="UTC"))
    masque_test = pd.Series(index >= pd.Timestamp(DEBUT_TEST, tz="UTC"), index=index)

    print("=" * 84)
    print("VOIE A — allocation multi-actifs inverse-vol + tilt de regime (train/test)")
    print("=" * 84)
    print(f"Univers          : {len(ACTIFS)} actifs — {', '.join(CRYPTO)} | {', '.join(INDICES)}")
    print(f"Fenetre commune  : {index[0]:%Y-%m-%d} -> {index[-1]:%Y-%m-%d} "
          f"({len(index)} jours communs, {ppa:.1f}/an)")
    print(f"Rodage           : {FENETRE_VOL}j de vol + {FENETRE_PCT}j de percentile "
          f"-> allocation active a partir du {depart:%Y-%m-%d}")
    print(f"TRAIN            : {depart:%Y-%m-%d} -> {FIN_TRAIN}  "
          f"({int(masque_train.sum())} jours)")
    print(f"TEST (OOS)       : {DEBUT_TEST} -> {index[-1]:%Y-%m-%d}  "
          f"({int(masque_test.sum())} jours)")
    print(f"Causalite        : poids decales de 1j ; macro FRED decalee de "
          f"{DECALAGE_FRED}j en plus (signal du jour t <= macro de t-2)")

    # --- Optimisation sur le TRAIN uniquement --------------------------------------------
    gagnante, classement = grid_search(base, feats, rendements, masque_train, ppa)
    scores = [s for s, _ in classement if np.isfinite(s)]

    print("\n" + "-" * 84)
    print("OPTIMISATION (TRAIN seul)")
    print("-" * 84)
    print(f"Combinaisons essayees : {len(classement)}")
    print(f"Parametres retenus    : VIX>{gagnante['s_vix']:.3f} | "
          f"BAA>{gagnante['s_baa']:.3f} | AUX>{gagnante['s_aux']:.3f} | "
          f"votes_min={gagnante['votes_min']} | t={gagnante['tilt']}")
    print(f"Sharpe TRAIN retenu   : {classement[0][0]:.3f}")
    print(f"Grid TRAIN            : median {np.median(scores):.3f} | "
          f"pire {min(scores):.3f} | prime de selection "
          f"{classement[0][0] - np.median(scores):+.3f} Sharpe")

    # --- Application a l'identique sur le TEST -------------------------------------------
    reg = regime(votes(feats, gagnante["s_vix"], gagnante["s_baa"], gagnante["s_aux"]),
                 gagnante["votes_min"])
    poids = appliquer_tilt(base, reg, gagnante["tilt"])
    r_opt = rendement_portefeuille(poids, rendements)

    equi = pd.DataFrame(1.0 / len(ACTIFS), index=index, columns=ACTIFS)
    r_equi = rendement_portefeuille(equi, rendements)
    r_btc = rendements["BTC"]

    test = masque_test.to_numpy()
    perfs = {
        "Allocation optimisee": performance(r_opt[test], ppa),
        "Equipondere (1/11)": performance(r_equi[test], ppa),
        "BTC seul (buy & hold)": performance(r_btc[test], ppa),
    }

    print("\n" + "-" * 84)
    print(f"TEST / HORS ECHANTILLON — {DEBUT_TEST} -> {index[-1]:%Y-%m-%d}")
    print("-" * 84)
    print(f"  {'':<26s} {'CAGR':>8s} {'VOL ANN.':>9s} {'SHARPE':>8s} {'MAX DD':>9s}")
    for nom, perf in perfs.items():
        print(_ligne(nom, perf))

    rot = rotation(poids)[test].mean()
    cout = rot * (COUT_BPS / 1e4)
    net = performance((r_opt[test] - cout), ppa)
    print(f"\n  Rotation quotidienne moyenne : {rot:.2%} du portefeuille")
    print(f"  Net de frais ({COUT_BPS:.0f} bps)        : CAGR {net['cagr']:.2%} | "
          f"Sharpe {net['sharpe']:.2f}")

    # --- Ablation : le regime sert-il a quelque chose ? -----------------------------------
    # La question qui decide du verdict. Si l'inverse-vol NU fait aussi bien, alors tout le
    # resultat vient de la diversification et la boite a outils n'a rien detecte du tout.
    r_nu = rendement_portefeuille(base, rendements)
    perf_nu = performance(r_nu[test], ppa)
    delta = perfs["Allocation optimisee"]["sharpe"] - perf_nu["sharpe"]

    print("\n" + "-" * 84)
    print("ABLATION — ce que le TILT DE REGIME ajoute a l'inverse-vol nu (TEST)")
    print("-" * 84)
    print(f"  {'':<26s} {'CAGR':>8s} {'VOL ANN.':>9s} {'SHARPE':>8s} {'MAX DD':>9s}")
    print(_ligne("Inverse-vol nu (t=0)", perf_nu))
    print(_ligne("+ tilt de regime", perfs["Allocation optimisee"]))
    print(f"\n  Apport du regime : {delta:+.3f} Sharpe")

    # Rang du gagnant TRAIN dans la distribution OOS des 216 combinaisons. DIAGNOSTIC SEUL :
    # aucune de ces valeurs ne choisit quoi que ce soit, la selection est deja close. Un
    # gagnant qui atterrit au milieu du peloton OOS signe une optimisation qui n'a rien appris.
    oos = []
    for _, params in classement:
        r2 = regime(votes(feats, params["s_vix"], params["s_baa"], params["s_aux"]),
                    params["votes_min"])
        oos.append(sharpe(rendement_portefeuille(
            appliquer_tilt(base, r2, params["tilt"]), rendements)[test], ppa))
    oos_arr = np.array(oos)
    rang = int((oos_arr > oos_arr[0]).sum()) + 1      # le gagnant TRAIN est en tete du tri
    print(f"  Sharpe OOS du gagnant TRAIN : {oos_arr[0]:.3f} — rang {rang}/{len(oos_arr)} "
          f"de la grille OOS (median {np.median(oos_arr):.3f}, "
          f"meilleur possible {oos_arr.max():.3f})")
    print("  (diagnostic : cette ligne ne selectionne rien, la combinaison etait deja figee)")

    # --- Regime et poids ------------------------------------------------------------------
    print("\n" + "-" * 84)
    print("REGIME DETECTE (part des jours)")
    print("-" * 84)
    etiquettes = {1: "risk-off", 0: "neutre", -1: "risk-on"}
    for bloc, m in (("TRAIN", masque_train.to_numpy()), ("TEST ", test)):
        parts = reg[m].value_counts(normalize=True)
        detail = " | ".join(f"{etiquettes[k]} {parts.get(k, 0.0):>6.1%}" for k in (1, 0, -1))
        print(f"  {bloc} : {detail}")

    # Contenu du regime : le rendement du jour t, classe par le regime decide en t-1, sur le
    # portefeuille NU. C'est la question de fond — un tilt ne peut pas rattraper un signal
    # qui ne separe rien. On attend risk-off < neutre < risk-on ; si l'ordre ne tient pas sur
    # le TEST, la boite a outils n'a rien detecte d'exploitable hors echantillon.
    print("\n  Rendement annualise du portefeuille nu, selon le regime decide la veille :")
    print(f"    {'bloc':<7s} {'risk-off':>12s} {'neutre':>12s} {'risk-on':>12s}")
    reg_hier = reg.shift(1)
    for bloc, m in (("TRAIN", masque_train.to_numpy()), ("TEST", test)):
        cases = []
        for k in (1, 0, -1):
            r = r_nu[m & (reg_hier == k).to_numpy()].dropna()
            cases.append(f"{(1 + r.mean()) ** ppa - 1:>11.2%}" if len(r) else f"{'--':>11s}")
        print(f"    {bloc:<7s} " + " ".join(cases))

    print("\n" + "-" * 84)
    print("POIDS MOYENS PAR ACTIF — allocation optimisee (TEST)")
    print("-" * 84)
    moyens = poids[test].mean().sort_values(ascending=False)
    for actif, w in moyens.items():
        camp = "refuge" if actif in REFUGES else ("risque" if actif in RISQUES else "neutre")
        barre = "#" * int(round(w * 200))
        print(f"  {actif:<10s} {w:>7.2%}  [{camp:<6s}] {barre}")
    print(f"  {'TOTAL':<10s} {moyens.sum():>7.2%}")

    print("\n" + "=" * 84)
    print("VERDICT")
    print("=" * 84)
    opt = perfs["Allocation optimisee"]["sharpe"]
    print(f"  Diversification inverse-vol : Sharpe OOS {perf_nu['sharpe']:.2f} contre "
          f"{perfs['BTC seul (buy & hold)']['sharpe']:.2f} pour BTC seul et "
          f"{perfs['Equipondere (1/11)']['sharpe']:.2f} equipondere.")
    if delta > 0.10 and oos_arr[0] >= np.median(oos_arr):
        print(f"  Tilt de regime : apport OOS {delta:+.2f} Sharpe, gagnant TRAIN au-dessus "
              "de la mediane OOS. A creuser — pas a conclure.")
    else:
        print(f"  Tilt de regime : apport OOS {delta:+.2f} Sharpe (optimisee {opt:.2f} vs "
              f"nu {perf_nu['sharpe']:.2f}), gagnant TRAIN rang {rang}/{len(oos_arr)} OOS, "
              f"meilleur tilt possible OOS {oos_arr.max():.2f}.")
        print("  => La boite a outils n'ajoute RIEN hors echantillon. Le resultat vient de "
              "l'inverse-vol,")
        print("     pas de la detection de regime. Hypothese INFIRMEE sur ce decoupage.")
    print(f"\n  Rappel : Sharpe TRAIN = maximum sur {len(classement)} essais, biaise vers le "
          "haut par construction.")
    print("  Seule la ligne TEST est interpretable, et elle ne vaut qu'une fois.")
    print("=" * 84)


if __name__ == "__main__":
    main()
