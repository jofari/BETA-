"""voie_b_trading — suivi de tendance LONG/SHORT sur les 6 perpetuels, parametres optimises.

Trois briques combinees, toutes causales (decalage d'un jour avant usage) :

  1. momentum : close vs SMA(N) -> candidat long (au-dessus) ou short (en-dessous) ;
  2. funding  : percentile glissant 180j du funding quotidien (moyenne des 3 reglements),
                <= p_lo exige pour un long, >= p_hi exige pour un short ;
  3. macro    : percentile glissant 180j du VIX > 0.8 = stress -> aucun long ce jour-la
                (les shorts restent permis : c'est la lecture de « forcer flat (aucun long) »).

Plus un stop intraday : sortie le jour meme si la position perd s % depuis son prix d'entree.

Les parametres {N, p_lo, p_hi, s, macro on/off} sont choisis par grid-search sur TRAIN
(<= 2023-12-31) au Sharpe de l'agregat equipondere, puis appliques tels quels sur TEST
(>= 2024-01-01), sans la moindre re-optimisation.

Ce fichier est un SCRIPT DE RECHERCHE, pas une candidate du moteur : il ne passe ni par
`contrats.Run`, ni par le preenregistrement, ni par la batterie S1-S9. Le chiffre OOS qu'il
imprime est donc une HYPOTHESE (invariant n° 7), pas un edge : 1176 combinaisons ont ete
essayees sur la meme fenetre, et le Sharpe du gagnant du train est un maximum d'echantillon,
pas une esperance.

    ARIT_HOME=/root/ARIT2.0 PYTHONPATH=/root/BETA- \
        /root/venvs/arit/bin/python beta/strategies/voie_b_trading.py
"""

from __future__ import annotations

import itertools
import math

import numpy as np
import pandas as pd

from beta.lake.lecture import funding, load, macro_globales

PAIRES = ("BTC", "ETH", "SOL", "BNB", "LINK", "XRP")
TIMEFRAME = "1d"

FIN_TRAIN = pd.Timestamp("2023-12-31", tz="UTC")
DEBUT_TEST = pd.Timestamp("2024-01-01", tz="UTC")

GRILLE_N = (20, 50, 100, 200)
GRILLE_P = (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8)
GRILLE_STOP = (2.0, 3.0, 5.0)
GRILLE_MACRO = (False, True)

FENETRE_PERCENTILE = 180
SEUIL_STRESS_VIX = 0.8
JOURS_AN = 365

# Bloc de sensibilite, EN PLUS de ce qui est demande : le resultat principal est brut, mais
# un perpetuel se paie — taker Binance ~4,5 bps par cote (arrondi a 5) plus le funding
# reellement regle (somme des 3 reglements du jour, paye par le long quand il est positif).
FRAIS_PAR_COTE_PCT = 0.05


# --------------------------------------------------------------------------------------
# Donnees
# --------------------------------------------------------------------------------------

def stress_vix(calendrier: pd.DatetimeIndex) -> np.ndarray:
    """Percentile glissant 180j du VIX > 0.8, projete sur un calendrier quotidien.

    Le VIX du jour d est publie en fin de seance : suivant la convention du pipeline
    (`_joindre_macro`), il est attribue au jour d+1 avant tout usage. Le decalage d'un jour
    du signal s'y ajoute — une position du jour t ne voit donc que le VIX de t-2.
    """
    macro = macro_globales()
    if macro.empty or "vix" not in macro.columns:
        raise RuntimeError("serie VIX absente : le filtre macro regime n'est pas evaluable")
    vix = macro["vix"].dropna()
    vix.index = vix.index + pd.Timedelta(days=1)
    vix = vix[~vix.index.duplicated(keep="last")]
    quotidien = vix.reindex(calendrier, method="ffill")
    rang = quotidien.rolling(FENETRE_PERCENTILE, min_periods=FENETRE_PERCENTILE).rank(pct=True)
    return (rang > SEUIL_STRESS_VIX).to_numpy()


def funding_quotidien(paire: str, calendrier: pd.DatetimeIndex) -> pd.DataFrame:
    """Funding 8h agrege au jour : moyenne des 3 reglements (signal) et somme (cout reel).

    Les reglements du jour d tombent a 00:00, 08:00 et 16:00 UTC : les trois sont connus
    avant la fin de la bougie quotidienne d, qui se ferme a 00:00 UTC du jour d+1. Le
    decalage d'un jour applique au signal suffit donc a la causalite.
    """
    brut = funding(paire)
    jour = brut["date"].dt.floor("D")
    groupes = brut.groupby(jour)["funding_rate"]
    out = pd.DataFrame({"moyenne": groupes.mean(), "somme": groupes.sum()})
    return out.reindex(calendrier)


def preparer(paire: str, stress: pd.Series) -> dict:
    """Tout ce dont la simulation a besoin pour une paire, deja decale d'un jour.

    Les features sont calculees sur la serie ENTIERE puis tranchees par periode : une
    fenetre glissante du debut du test qui deborde sur la fin du train est legitime (c'est
    du passe), la re-calculer par periode ne ferait que mutiler le debut du test.
    """
    df = load(paire, TIMEFRAME).set_index("date").sort_index()
    fund = funding_quotidien(paire, df.index)

    rang_fund = fund["moyenne"].rolling(FENETRE_PERCENTILE,
                                        min_periods=FENETRE_PERCENTILE).rank(pct=True)
    prep = {
        "dates": df.index,
        "ouv": df["open"].to_numpy(dtype=float).tolist(),
        "haut": df["high"].to_numpy(dtype=float).tolist(),
        "bas": df["low"].to_numpy(dtype=float).tolist(),
        "clot": df["close"].to_numpy(dtype=float).tolist(),
        "funding_paye": fund["somme"].fillna(0.0).to_numpy(dtype=float).tolist(),
        "rang": rang_fund.shift(1).to_numpy(dtype=float),
        "stress": stress.reindex(df.index).astype(float).shift(1).fillna(0.0).to_numpy() > 0.5,
        "sur": {},
        "sous": {},
    }
    sma_longue = df["close"].rolling(max(GRILLE_N), min_periods=max(GRILLE_N)).mean()
    for n in GRILLE_N:
        sma = df["close"].rolling(n, min_periods=n).mean()
        prep["sur"][n] = (df["close"] > sma).astype(float).shift(1).to_numpy() > 0.5
        prep["sous"][n] = (df["close"] < sma).astype(float).shift(1).to_numpy() > 0.5

    # Fenetre d'evaluation commune a TOUTES les combinaisons : le premier jour ou la SMA la
    # plus longue ET le percentile de funding existent. Sans ce plancher commun, un N=20
    # serait mesure sur 180 jours de plus qu'un N=200 et gagnerait la grille pour ca.
    dispo = (sma_longue.notna() & rang_fund.notna()).shift(1).fillna(False).to_numpy()
    prep["premier"] = int(np.argmax(dispo)) if dispo.any() else len(dispo)
    return prep


# --------------------------------------------------------------------------------------
# Signal et simulation
# --------------------------------------------------------------------------------------

def positions_voulues(prep: dict, n: int, p_lo: float, p_hi: float,
                      macro_on: bool) -> list[int]:
    """Position souhaitee pour chaque jour, dans {+1, -1, 0}. NaN -> False -> flat."""
    longue = prep["sur"][n] & (prep["rang"] <= p_lo)
    courte = prep["sous"][n] & (prep["rang"] >= p_hi)
    if macro_on:
        longue = longue & ~prep["stress"]
    return np.where(longue, 1, np.where(courte, -1, 0)).tolist()


def simuler(prep: dict, voulue: list[int], stop_pct: float, i0: int, i1: int) -> dict:
    """Deroule la position jour par jour sur [i0, i1], stop intraday a `stop_pct` %.

    Conventions :
    - la position du jour i est prise au close du jour i-1 (= ouverture du jour i) et porte
      le rendement close-a-close du jour i ;
    - le stop sort au niveau du stop, ou a l'ouverture si le marche a deja ouvert au-dela ;
    - apres un stop la journee se termine flat, et le signal peut rouvrir DES LE LENDEMAIN
      (le stop est un controle de risque, pas une mise a l'ecart) ;
    - chaque periode demarre flat : aucune position n'est heritee du train par le test.
    """
    ouv, haut, bas, clot = prep["ouv"], prep["haut"], prep["bas"], prep["clot"]
    paye = prep["funding_paye"]
    taille = i1 - i0 + 1
    rendement = [0.0] * taille
    exposition = [0.0] * taille
    frais = [0.0] * taille
    carry = [0.0] * taille
    trades: list[tuple[int, int, int]] = []

    sens = 0
    prix_entree = 0.0
    debut = 0
    frais_cote = FRAIS_PAR_COTE_PCT / 100.0

    for i in range(max(i0, 1), i1 + 1):
        k = i - i0
        cible = voulue[i]
        if sens != 0 and cible != sens:          # sortie au close de la veille
            trades.append((debut, k - 1, sens))
            sens = 0
            frais[k] += frais_cote
        if sens == 0 and cible != 0:             # entree au close de la veille
            sens = cible
            prix_entree = clot[i - 1]
            debut = k
            frais[k] += frais_cote
        if sens == 0:
            continue

        reference = clot[i - 1]
        exposition[k] = 1.0
        carry[k] = sens * paye[i]
        if sens == 1:
            niveau = prix_entree * (1.0 - stop_pct / 100.0)
            if bas[i] <= niveau:
                sortie = niveau if ouv[i] > niveau else ouv[i]
                rendement[k] = sortie / reference - 1.0
                frais[k] += frais_cote
                trades.append((debut, k, sens))
                sens = 0
            else:
                rendement[k] = clot[i] / reference - 1.0
        else:
            niveau = prix_entree * (1.0 + stop_pct / 100.0)
            if haut[i] >= niveau:
                sortie = niveau if ouv[i] < niveau else ouv[i]
                rendement[k] = -(sortie / reference - 1.0)
                frais[k] += frais_cote
                trades.append((debut, k, sens))
                sens = 0
            else:
                rendement[k] = -(clot[i] / reference - 1.0)

    if sens != 0:
        trades.append((debut, taille - 1, sens))

    return {"rendement": np.asarray(rendement), "exposition": np.asarray(exposition),
            "frais": np.asarray(frais), "carry": np.asarray(carry), "trades": trades}


# --------------------------------------------------------------------------------------
# Mesures
# --------------------------------------------------------------------------------------

def metriques(rendement: np.ndarray) -> dict:
    """CAGR, vol, Sharpe (rf=0), maxDD d'une serie de rendements quotidiens composes."""
    r = np.asarray(rendement, dtype=float)
    r = r[~np.isnan(r)]
    if len(r) < 2:
        return {"cagr": float("nan"), "vol": float("nan"), "sharpe": float("nan"),
                "maxdd": float("nan"), "total": float("nan"), "jours": len(r)}
    equite = np.cumprod(1.0 + r)
    ecart = float(r.std(ddof=1))
    pic = np.maximum.accumulate(equite)
    return {
        "cagr": float(equite[-1]) ** (JOURS_AN / len(r)) - 1.0,
        "vol": ecart * math.sqrt(JOURS_AN),
        "sharpe": (float(r.mean()) / ecart * math.sqrt(JOURS_AN)) if ecart > 0 else 0.0,
        "maxdd": float((equite / pic - 1.0).min()),
        "total": float(equite[-1]) - 1.0,
        "jours": len(r),
    }


def compte_trades(resultat: dict) -> tuple[int, float]:
    """(nombre de trades, taux de gagnants). Un trade = une detention continue d'un sens."""
    r = resultat["rendement"]
    gains = [float(np.prod(1.0 + r[a:b + 1])) - 1.0 for a, b, _ in resultat["trades"] if b >= a]
    if not gains:
        return 0, float("nan")
    return len(gains), sum(1 for g in gains if g > 0) / len(gains)


def agreger(series: dict[str, np.ndarray], lignes: dict[str, np.ndarray],
            taille: int) -> np.ndarray:
    """Portefeuille equipondere : moyenne des paires DISPONIBLES chaque jour."""
    matrice = np.full((taille, len(series)), np.nan)
    for colonne, paire in enumerate(series):
        matrice[lignes[paire], colonne] = series[paire]
    return np.nanmean(matrice, axis=1)


# --------------------------------------------------------------------------------------
# Rapport
# --------------------------------------------------------------------------------------

EN_TETE = (f"{'':<12}{'CAGR':>9}{'vol':>9}{'Sharpe':>8}{'maxDD':>9}"
           f"{'trades':>8}{'win-rate':>10}{'exposure':>10}")


def ligne(nom: str, m: dict, trades: int | str, win: float, expo: float) -> str:
    win_txt = "      n/a" if win != win else f"{win:>9.1%}"
    trades_txt = f"{trades:>8}" if isinstance(trades, str) else f"{trades:>8d}"
    return (f"{nom:<12}{m['cagr']:>8.1%} {m['vol']:>8.1%} {m['sharpe']:>7.2f} "
            f"{m['maxdd']:>8.1%} {trades_txt}{win_txt} {expo:>9.1%}")


def main() -> None:
    calendrier_global = pd.date_range("2019-01-01", "2027-01-01", freq="D", tz="UTC")
    stress = pd.Series(stress_vix(calendrier_global), index=calendrier_global)

    prep = {p: preparer(p, stress) for p in PAIRES}

    # Bornes de chaque periode, par paire.
    bornes = {}
    for p in PAIRES:
        dates = prep[p]["dates"]
        i_train_fin = int(np.searchsorted(dates, FIN_TRAIN, side="right")) - 1
        i_test_debut = int(np.searchsorted(dates, DEBUT_TEST, side="left"))
        bornes[p] = {"train": (prep[p]["premier"], i_train_fin),
                     "test": (i_test_debut, len(dates) - 1)}

    # Calendriers communs pour l'agregat, et la ligne de chaque paire dedans.
    calendriers, lignes = {}, {}
    for periode in ("train", "test"):
        debuts = [prep[p]["dates"][bornes[p][periode][0]] for p in PAIRES]
        fins = [prep[p]["dates"][bornes[p][periode][1]] for p in PAIRES]
        cal = pd.date_range(min(debuts), max(fins), freq="D", tz="UTC")
        calendriers[periode] = cal
        lignes[periode] = {p: np.searchsorted(
            cal, prep[p]["dates"][bornes[p][periode][0]:bornes[p][periode][1] + 1])
            for p in PAIRES}

    print("=" * 94)
    print("VOIE B — suivi de tendance LONG/SHORT combine (momentum + funding + macro regime)")
    print("=" * 94)
    for p in PAIRES:
        d = prep[p]["dates"]
        b = bornes[p]
        print(f"  {p:<5} donnees {d[0]:%Y-%m-%d} -> {d[-1]:%Y-%m-%d} | "
              f"train {d[b['train'][0]]:%Y-%m-%d} -> {d[b['train'][1]]:%Y-%m-%d} | "
              f"test {d[b['test'][0]]:%Y-%m-%d} -> {d[b['test'][1]]:%Y-%m-%d}")
    combinaisons = (len(GRILLE_N) * len(GRILLE_P) ** 2 * len(GRILLE_STOP) * len(GRILLE_MACRO))
    print(f"\n  Grille : N{list(GRILLE_N)} x p_lo{list(GRILLE_P)} x p_hi{list(GRILLE_P)} x "
          f"stop{list(GRILLE_STOP)} x macro[off, on]")
    print(f"  soit {combinaisons} combinaisons essayees sur le TRAIN.")

    # ---------------- grid-search sur le train ----------------
    taille_train = len(calendriers["train"])
    resultats = []
    for n, p_lo, p_hi, macro_on in itertools.product(GRILLE_N, GRILLE_P, GRILLE_P,
                                                     GRILLE_MACRO):
        voulues = {p: positions_voulues(prep[p], n, p_lo, p_hi, macro_on) for p in PAIRES}
        for stop in GRILLE_STOP:
            series = {p: simuler(prep[p], voulues[p], stop, *bornes[p]["train"])["rendement"]
                      for p in PAIRES}
            agregat = agreger(series, lignes["train"], taille_train)
            resultats.append((metriques(agregat)["sharpe"], (n, p_lo, p_hi, stop, macro_on)))

    resultats.sort(key=lambda x: -x[0])
    sharpe_train, retenus = resultats[0]
    n, p_lo, p_hi, stop, macro_on = retenus
    sharpes = np.array([s for s, _ in resultats])

    print("\n" + "-" * 94)
    print("PARAMETRES RETENUS (optimises sur le TRAIN, jamais retouches ensuite)")
    print("-" * 94)
    print(f"  SMA N              : {n}")
    print(f"  funding p_lo (long): {p_lo}")
    print(f"  funding p_hi (short): {p_hi}")
    print(f"  stop               : {stop:.0f} %")
    print(f"  filtre macro VIX   : {'ACTIF' if macro_on else 'inactif'}")
    print(f"  Sharpe TRAIN agrege: {sharpe_train:.3f}")
    print(f"  (grille : Sharpe train median {np.median(sharpes):.3f}, "
          f"min {sharpes.min():.3f}, max {sharpes.max():.3f} — "
          f"le retenu EST le maximum de {combinaisons} essais)")

    # ---------------- application au test, sans re-optimisation ----------------
    voulues = {p: positions_voulues(prep[p], n, p_lo, p_hi, macro_on) for p in PAIRES}
    sorties, bh = {}, {}
    for p in PAIRES:
        i0, i1 = bornes[p]["test"]
        sorties[p] = simuler(prep[p], voulues[p], stop, i0, i1)
        clot = np.asarray(prep[p]["clot"][i0 - 1:i1 + 1])
        bh[p] = clot[1:] / clot[:-1] - 1.0

    taille_test = len(calendriers["test"])
    agregat = agreger({p: sorties[p]["rendement"] for p in PAIRES}, lignes["test"], taille_test)
    agregat_bh = agreger(bh, lignes["test"], taille_test)
    expo_agregat = float(np.mean([sorties[p]["exposition"].mean() for p in PAIRES]))
    trades_agregat = sum(compte_trades(sorties[p])[0] for p in PAIRES)
    gagnants = [g for p in PAIRES for g in
                [float(np.prod(1.0 + sorties[p]["rendement"][a:b + 1])) - 1.0
                 for a, b, _ in sorties[p]["trades"] if b >= a]]
    win_agregat = sum(1 for g in gagnants if g > 0) / len(gagnants) if gagnants else float("nan")

    cal = calendriers["test"]
    print("\n" + "-" * 94)
    print(f"TEST (OOS) {cal[0]:%Y-%m-%d} -> {cal[-1]:%Y-%m-%d} — AGREGAT "
          "(equipondere, moyenne egale des 6 paires)")
    print("-" * 94)
    print(EN_TETE)
    print(ligne("strategie", metriques(agregat), trades_agregat, win_agregat, expo_agregat))
    print(ligne("buy & hold", metriques(agregat_bh), 6, float("nan"), 1.0))

    print("\n" + "-" * 94)
    print("TEST (OOS) — PAR PAIRE (strategie vs buy & hold de la meme paire)")
    print("-" * 94)
    print(EN_TETE)
    for p in PAIRES:
        nb, win = compte_trades(sorties[p])
        print(ligne(f"{p} strat", metriques(sorties[p]["rendement"]), nb, win,
                    float(sorties[p]["exposition"].mean())))
        print(ligne(f"{p} B&H", metriques(bh[p]), 1, float("nan"), 1.0))

    # ---------------- ce que le prompt ne demande pas, et qui decide pourtant ----------
    print("\n" + "-" * 94)
    print("SENSIBILITE AUX COUTS (hors demande — un perpetuel se paie)")
    print("-" * 94)
    print(f"  frais {FRAIS_PAR_COTE_PCT} % par cote + funding reellement regle sur la position")
    net = {p: sorties[p]["rendement"] - sorties[p]["frais"] - sorties[p]["carry"]
           for p in PAIRES}
    agregat_net = agreger(net, lignes["test"], taille_test)
    print(EN_TETE)
    print(ligne("net agrege", metriques(agregat_net), trades_agregat, float("nan"),
                expo_agregat))

    print("\n" + "-" * 94)
    print("STABILITE DE LA SELECTION — top 5 du TRAIN et ce qu'ils rendent en OOS")
    print("-" * 94)
    print(f"{'N':>5}{'p_lo':>7}{'p_hi':>7}{'stop':>7}{'macro':>8}"
          f"{'Sharpe train':>14}{'Sharpe OOS':>13}")
    for sharpe_t, combo in resultats[:5]:
        cn, cp_lo, cp_hi, cstop, cmacro = combo
        v = {p: positions_voulues(prep[p], cn, cp_lo, cp_hi, cmacro) for p in PAIRES}
        s = {p: simuler(prep[p], v[p], cstop, *bornes[p]["test"])["rendement"] for p in PAIRES}
        sharpe_oos = metriques(agreger(s, lignes["test"], taille_test))["sharpe"]
        print(f"{cn:>5}{cp_lo:>7.1f}{cp_hi:>7.1f}{cstop:>7.0f}"
              f"{'on' if cmacro else 'off':>8}{sharpe_t:>14.3f}{sharpe_oos:>13.3f}")

    print("\n" + "=" * 94)
    print("Rappel : ce script n'est pas un verdict. Le Sharpe retenu est le MAXIMUM de "
          f"{combinaisons} essais")
    print("sur la meme fenetre ; rien ici n'est passe par le preenregistrement ni par la "
          "batterie S1-S9.")
    print("=" * 94)


if __name__ == "__main__":
    main()
