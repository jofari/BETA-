"""Triple barriere vectorisee : la geometrie d'un signal, mesuree en R.

Portage de `ARIT2.0/analysis/dataset.py:_issue` et `replay_entries.py`, avec deux
differences qui comptent :

- **vectorise par blocs** plutot que boucle par signal. Cribler des centaines de candidates
  sur 4,5 M de bougies en boucle Python prendrait des heures ; ici une candidate sur 6
  paires se mesure en quelques secondes ;
- **les couts sont soustraits**. ARIT mesurait la geometrie nue. Un banc d'essai qui compare
  des candidates entre elles doit inclure frais et slippage, sinon il classe en tete celles
  qui tradent le plus.

Ce que ce module NE fait PAS, et ne fera jamais :

> **Il ne produit pas de verdict portefeuille.** Un chiffre qui sort d'ici se lit en R par
> trade. Ni frais de financement, ni slots concurrents, ni compounding, ni taille de
> position variable. Confondre les deux est l'erreur qui rend un banc d'essai dangereux —
> c'est le role du pont freqtrade (M3) de rendre l'autre verdict.

Conventions, identiques a ARIT pour que les deux projets restent comparables :

- entree a la CLOTURE de la bougie de signal, fenetre ouverte a la bougie suivante. Entrer
  au close de la bougie qui produit le signal est la seule convention sans look-ahead ;
- bougie ambigue (SL et TP touches dans la meme bougie) => **SL**. Choix pessimiste, et le
  seul honnete sans donnee intra-bougie ;
- R = (prix de sortie - entree) * sens / risque, ou risque est la distance entree-stop.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger("beta.moteur.espace_r")

TP, SL, HORIZON = "TP", "SL", "horizon"

# Taille de bloc : nombre de cellules (signaux x horizon) traitees d'un coup. 4 M cellules
# font ~32 Mo par matrice float64, et l'on en manipule quatre. Sur une machine a 16 Go on
# reste tres au large, tout en evitant la materialisation d'une matrice de 600 000 x 96.
CELLULES_PAR_BLOC = 4_000_000

PERIODE_ATR = 14


def atr(df: pd.DataFrame, periode: int = PERIODE_ATR) -> pd.Series:
    """True range moyen, en prix. Le stop par defaut s'exprime en multiples de cette unite.

    Moyenne mobile simple plutot que Wilder : la difference est invisible a l'echelle d'un
    stop, et une SMA ne traine pas d'etat initial dependant du debut de serie — donc deux
    fenetres de dates differentes donnent le meme ATR sur leur partie commune.
    """
    haut, bas, cloture = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat([haut - bas, (haut - cloture).abs(), (bas - cloture).abs()],
                   axis=1).max(axis=1)
    return tr.rolling(periode, min_periods=periode).mean()


def _fenetres(valeurs: np.ndarray, depart: np.ndarray, horizon: int) -> np.ndarray:
    """Matrice (n_signaux, horizon) des valeurs futures. NaN au-dela de la fin de serie."""
    tampon = np.full(len(valeurs) + horizon, np.nan)
    tampon[:len(valeurs)] = valeurs
    vue = np.lib.stride_tricks.sliding_window_view(tampon, horizon)
    return vue[depart]


def _premier(touche: np.ndarray) -> np.ndarray:
    """Index du premier True de chaque ligne, -1 si la ligne n'en contient aucun."""
    trouve = touche.any(axis=1)
    index = np.argmax(touche, axis=1)
    return np.where(trouve, index, -1)


def evaluer(df: pd.DataFrame, signaux: pd.DataFrame, *, take_profit_r: float = 2.0,
            horizon_bougies: int = 96, stop_atr: float = 2.0,
            cout_aller_retour_pct: float = 0.0, paire: str = "",
            periode_atr: int = PERIODE_ATR) -> pd.DataFrame:
    """Rejoue chaque signal en triple barriere. Une ligne par signal, en R.

    `df` : OHLCV du lake (colonnes date/open/high/low/close). `signaux` : la sortie de
    `Candidate.appliquer`, alignee ligne a ligne, colonne `sens` (-1/0/+1) et, si la
    candidate en fournit un, `stop_distance` (distance en PRIX entre entree et stop).

    Les signaux sont evalues INDEPENDAMMENT les uns des autres, y compris s'ils se
    chevauchent : c'est une mesure de geometrie, pas une simulation de compte. Pour une
    courbe d'equity, passer le resultat a `enchainer()`.
    """
    if len(signaux) != len(df):
        raise ValueError(f"signaux ({len(signaux)}) et df ({len(df)}) desalignes")
    n = len(df)
    sens_tout = signaux["sens"].to_numpy(dtype=np.int8)
    # Un signal sur la derniere bougie n'a aucune bougie future : il n'est pas mesurable.
    positions = np.flatnonzero((sens_tout != 0))
    positions = positions[positions < n - 1]
    if not len(positions):
        return _vide()

    # Une candidate entre au close de sa bougie de signal. Rejouer des trades DEJA pris
    # (mesures R1/R5) demande au contraire le prix d'entree reel : sans lui, l'ecart mesure
    # melangerait l'effet etudie et un decalage d'entree de quelques dizaines de points.
    entree_tout = (signaux["prix_entree"].to_numpy(dtype=float)
                   if "prix_entree" in signaux.columns
                   else df["close"].to_numpy(dtype=float))
    if "stop_distance" in signaux.columns:
        risque_tout = signaux["stop_distance"].to_numpy(dtype=float)
    else:
        risque_tout = stop_atr * atr(df, periode_atr).to_numpy(dtype=float)

    valides = np.isfinite(risque_tout[positions]) & (risque_tout[positions] > 0) \
        & np.isfinite(entree_tout[positions])
    ecartes = int((~valides).sum())
    if ecartes:
        log.info("%s : %d signal(aux) ecarte(s) — risque non defini (warm-up ATR)",
                 paire or "serie", ecartes)
    positions = positions[valides]
    if not len(positions):
        return _vide()

    horizon = max(1, int(horizon_bougies))
    hauts, bas, clotures = (df[c].to_numpy(dtype=float) for c in ("high", "low", "close"))
    dates = pd.to_datetime(df["date"], utc=True).to_numpy()

    taille_bloc = max(1, CELLULES_PAR_BLOC // horizon)
    morceaux = []
    for debut in range(0, len(positions), taille_bloc):
        morceaux.append(_bloc(
            positions[debut:debut + taille_bloc], hauts, bas, clotures, dates,
            sens_tout, entree_tout, risque_tout, horizon, take_profit_r,
            cout_aller_retour_pct, n))
    trades = pd.concat(morceaux, ignore_index=True)
    trades.insert(0, "paire", paire)
    return trades


def _bloc(positions, hauts, bas, clotures, dates, sens_tout, entree_tout, risque_tout,
          horizon, take_profit_r, cout_pct, n) -> pd.DataFrame:
    """Le calcul lui-meme, sur un paquet de signaux. Aucune boucle sur les signaux."""
    depart = positions + 1                       # la fenetre s'ouvre APRES la bougie d'entree
    sens = sens_tout[positions].astype(float)
    entree = entree_tout[positions]
    risque = risque_tout[positions]

    f_haut = _fenetres(hauts, depart, horizon)
    f_bas = _fenetres(bas, depart, horizon)
    f_cloture = _fenetres(clotures, depart, horizon)

    stop = entree - sens * risque
    cible = entree + sens * risque * take_profit_r
    long = (sens > 0)[:, None]
    touche_sl = np.where(long, f_bas <= stop[:, None], f_haut >= stop[:, None])
    touche_tp = np.where(long, f_haut >= cible[:, None], f_bas <= cible[:, None])
    # NaN de fin de serie : les comparaisons rendent False, donc aucune barriere fantome.

    i_sl, i_tp = _premier(touche_sl), _premier(touche_tp)
    # Bougie ambigue => SL : le TP ne gagne qu'en touchant STRICTEMENT avant.
    tp_gagne = (i_tp >= 0) & ((i_sl < 0) | (i_tp < i_sl))
    sl_gagne = (i_sl >= 0) & ~tp_gagne

    # Derniere bougie disponible de la fenetre, pour les sorties a l'horizon.
    dispo = np.minimum(horizon - 1, n - 1 - depart)
    i_fin = np.where(tp_gagne, i_tp, np.where(sl_gagne, i_sl, dispo))

    r_brut = np.where(tp_gagne, take_profit_r, np.where(sl_gagne, -1.0, np.nan))
    lignes = np.arange(len(positions))
    cloture_fin = f_cloture[lignes, i_fin]
    r_horizon = sens * (cloture_fin - entree) / risque
    r_brut = np.where(np.isnan(r_brut), r_horizon, r_brut)

    # Cout en R : un cout en % du prix vaut d'autant plus de R que le stop est serre. C'est
    # exactement ce qui tue les strategies a stop tres serre, et qu'un backtest sans frais
    # ne montre jamais.
    cout_r = (cout_pct / 100.0) * entree / risque
    r_net = r_brut - cout_r

    masque = np.arange(horizon)[None, :] <= i_fin[:, None]
    haut_masque = np.where(masque, f_haut, -np.inf)
    bas_masque = np.where(masque, f_bas, np.inf)
    extreme_favorable = np.where(sens > 0, np.nanmax(haut_masque, axis=1),
                                 np.nanmin(bas_masque, axis=1))
    extreme_defavorable = np.where(sens > 0, np.nanmin(bas_masque, axis=1),
                                   np.nanmax(haut_masque, axis=1))
    mfe_r = sens * (extreme_favorable - entree) / risque
    mae_r = sens * (extreme_defavorable - entree) / risque

    ts_entree = dates[positions]
    ts_sortie = dates[np.minimum(depart + i_fin, n - 1)]
    duree_h = (ts_sortie - ts_entree) / np.timedelta64(1, "h")

    raison = np.where(tp_gagne, TP, np.where(sl_gagne, SL, HORIZON))
    return pd.DataFrame({
        "ts_entree": ts_entree, "ts_sortie": ts_sortie,
        "sens": np.where(sens > 0, "long", "short"),
        "prix_entree": entree, "prix_sortie": cloture_fin,
        "stop": stop, "cible": cible, "risque": risque,
        "r": r_net, "r_brut": r_brut, "cout_r": cout_r,
        "rendement_pct": sens * (cloture_fin / entree - 1.0) * 100.0 - cout_pct,
        "mfe_r": np.where(np.isfinite(mfe_r), mfe_r, np.nan),
        "mae_r": np.where(np.isfinite(mae_r), mae_r, np.nan),
        "duree_h": duree_h, "duree_bougies": i_fin + 1,
        "raison_sortie": raison, "index_entree": positions,
    })


def _vide() -> pd.DataFrame:
    colonnes = ("paire", "ts_entree", "ts_sortie", "sens", "prix_entree", "prix_sortie",
                "stop", "cible", "risque", "r", "r_brut", "cout_r", "rendement_pct",
                "mfe_r", "mae_r", "duree_h", "duree_bougies", "raison_sortie",
                "index_entree")
    return pd.DataFrame({c: pd.Series(dtype="object" if c in
                                      ("paire", "sens", "raison_sortie") else float)
                         for c in colonnes})


def enchainer(trades: pd.DataFrame) -> pd.DataFrame:
    """Ne garde que les trades qui n'auraient pas chevauche le precedent, paire par paire.

    `evaluer()` mesure la geometrie de TOUS les signaux, y compris pendant qu'un trade est
    deja ouvert. Une courbe d'equity construite sur cet ensemble compterait plusieurs fois
    le meme mouvement : elle serait fausse dans le sens flatteur. Cette fonction rend la
    sequence realisable a une position par paire — la seule sur laquelle un drawdown veut
    dire quelque chose.
    """
    if trades.empty:
        return trades
    gardes = []
    for _, groupe in trades.groupby("paire", dropna=False, sort=False):
        groupe = groupe.sort_values("ts_entree")
        libre_a = None
        for ligne in groupe.itertuples(index=True):
            if libre_a is None or ligne.ts_entree >= libre_a:
                gardes.append(ligne.Index)
                libre_a = ligne.ts_sortie
    return trades.loc[sorted(gardes)].reset_index(drop=True)


def equity(trades: pd.DataFrame, capital: float = 100_000.0,
           risque_par_trade_pct: float = 1.0) -> pd.DataFrame:
    """Courbe d'equity a risque fixe (fraction constante du capital initial, pas composee).

    Le risque fixe en pourcentage du capital INITIAL est volontaire : composer gonfle les
    fins de periode et rend deux candidates incomparables si elles n'ont pas la meme
    chronologie de gains. Le compounding se mesure cote freqtrade (M3), une fois seulement.
    """
    if trades.empty:
        return pd.DataFrame({"ts": [], "equity": [], "drawdown_pct": []})
    ordonnes = trades.sort_values("ts_sortie")
    gain = ordonnes["r"].fillna(0.0) * capital * risque_par_trade_pct / 100.0
    courbe = capital + gain.cumsum()
    sommet = courbe.cummax()
    return pd.DataFrame({"ts": ordonnes["ts_sortie"].to_numpy(),
                         "equity": courbe.to_numpy(),
                         "drawdown_pct": ((courbe / sommet - 1.0) * 100.0).to_numpy()})
