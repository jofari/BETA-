"""Triple barriere vectorisee : la geometrie d'un signal, mesuree en R.

Portage de `ARIT2.0/analysis/dataset.py:_issue` et `replay_entries.py`, avec deux
differences qui comptent :

- **vectorise par blocs** plutot que boucle par signal. Cribler des centaines de candidates
  sur 4,5 M de bougies en boucle Python prendrait des heures ; ici une candidate sur 6
  paires se mesure en quelques secondes ;
- **les couts sont soustraits**. ARIT mesurait la geometrie nue. Un banc d'essai qui compare
  des candidates entre elles doit inclure frais et slippage, sinon il classe en tete celles
  qui tradent le plus ; et il doit inclure les couts de DETENTION — spread bid-ask, funding
  des perpetuels — sinon il classe en tete celles qui tiennent le plus longtemps.

Ce que ce module NE fait PAS, et ne fera jamais :

> **Il ne produit pas de verdict portefeuille.** Un chiffre qui sort d'ici se lit en R par
> trade. Ni slots concurrents, ni compounding, ni taille de position variable. Confondre les
> deux est l'erreur qui rend un banc d'essai dangereux — c'est le role du pont freqtrade
> (M3) de rendre l'autre verdict.

Conventions, identiques a ARIT pour que les deux projets restent comparables :

- entree a la CLOTURE de la bougie de signal, fenetre ouverte a la bougie suivante. Entrer
  au close de la bougie qui produit le signal est la seule convention sans look-ahead ;
- bougie ambigue (SL et TP touches dans la meme bougie) => **SL**. Choix pessimiste, et le
  seul honnete sans donnee intra-bougie ;
- R = (prix de sortie - entree) * sens / risque, ou risque est la distance entree-stop.

Les trois couts se comptent tous en **% du prix d'entree**, puis se convertissent en R par
le meme facteur `entree / risque` (notionnel 1x, collateral plein, pas de levier) :

- **frais + slippage** — forfaitaires, payes une fois par aller-retour ;
- **spread bid-ask** — estime depuis les high/low du lake (Corwin & Schultz), paye une
  demi-fois a l'entree et une demi-fois a la sortie, soit un spread complet par trade ;
- **funding** — cumule sur les bougies TENUES et signe par le sens : un funding positif
  coute au long et paie le short. C'est le seul cout qui grandit avec la duree du trade,
  donc le seul que le R par trade d'ARIT ne pouvait pas voir.

Aucun de ces trois n'est actif par defaut ici : `evaluer()` mesure la geometrie nue tant
qu'on ne lui demande pas de payer. C'est le `Run` (cf. `contrats.py`) qui porte la politique
de couts du banc, et qui, lui, les active tous.
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

# Fenetre de lissage de l'estimateur de spread, en BOUGIES (pas en jours) : 21 bougies,
# l'ordre de grandeur du mois de bourse de l'article d'origine. En 4h cela fait 3,5 jours —
# c'est voulu, un spread se paie a l'echelle du trade, pas a celle du mois.
FENETRE_SPREAD = 21
_K_CS = 3.0 - 2.0 * np.sqrt(2.0)          # la constante de Corwin & Schultz

# Periode de reglement du funding des perpetuels Binance. Sert a ramener au prorata de la
# bougie un taux que le pipeline a recopie en palier (cf. _serie_funding).
HEURES_FUNDING = 8.0


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


def spread_corwin_schultz(df: pd.DataFrame, fenetre: int = FENETRE_SPREAD) -> pd.Series:
    """Spread effectif RELATIF au prix, estime a partir des seuls high/low (CS 2012).

    Corwin & Schultz, « A Simple Way to Estimate Bid-Ask Spreads from Daily High and Low
    Prices », Journal of Finance 67(2). L'idee tient en une phrase : dans l'amplitude
    haut-bas, la part qui vient de la VOLATILITE grandit avec la duree d'observation, celle
    qui vient du SPREAD n'y grandit pas. Comparer l'amplitude d'une bougie a celle de deux
    bougies collees separe donc les deux composantes, sans aucune donnee de carnet.

    C'est un ESTIMATEUR, jamais une mesure : il n'existe pas de serie libre de spreads
    Binance, et l'invariant n° 2 interdit d'inventer une source. Celui-ci se calcule depuis
    le lake, donc il est reproductible — la seule propriete qui compte ici.

    Rend une FRACTION du prix (0,0004 = 4 points de base), lissee sur `fenetre` bougies.
    Quatre details qui n'en sont pas :

    - les estimations bi-bougies NEGATIVES sont ramenees a zero avant le lissage, comme le
      prescrit l'article : un spread negatif n'existe pas, c'est du bruit d'echantillon ;
    - **ajustement des gaps** (§ II.B de l'article) : un ecart entre la bougie precedente et
      la suivante gonfle l'amplitude a deux bougies sans rien devoir au spread, ce qui tire
      l'estimation vers le bas. On recolle la seconde bougie sur la premiere avant de
      calculer. Sur un perpetuel 24/7 l'ajustement ne change presque rien ; sur un indice
      quotidien, qui ouvre en gap, il change beaucoup ;
    - `min_periods=1` : la fenetre se remplit progressivement au lieu de rendre NaN pendant
      tout le warm-up. Les premieres bougies sont estimees plus grossierement, mais sur le
      seul PASSE — moyenner toute la serie ferait entrer du futur dans un cout ;
    - l'article travaille en bougies quotidiennes. Rien dans la demonstration ne depend du
      pas, mais plus la bougie est courte, plus la part du spread dans son amplitude est
      grande : en 5m l'estimation monte, et c'est le sens d'erreur acceptable pour un cout.
    """
    haut = pd.to_numeric(df["high"], errors="coerce").astype(float)
    bas = pd.to_numeric(df["low"], errors="coerce").astype(float)
    utilisable = (haut > 0) & (bas > 0) & (haut >= bas)
    haut, bas = haut.where(utilisable), bas.where(utilisable)
    haut_prec, bas_prec = haut.shift(1), bas.shift(1)

    # Gap a la hausse (bas_t au-dessus de haut_t-1) ou a la baisse : on translate la bougie
    # courante de l'ecart, ce qui laisse sa propre amplitude intacte et retire du seul
    # intervalle a deux bougies ce que le spread n'a pas paye.
    decalage = ((bas - haut_prec).clip(lower=0.0).fillna(0.0)
                - (bas_prec - haut).clip(lower=0.0).fillna(0.0))
    haut_aj, bas_aj = haut - decalage, bas - decalage

    with np.errstate(divide="ignore", invalid="ignore"):
        beta = np.log(haut_aj / bas_aj) ** 2 + np.log(haut_prec / bas_prec) ** 2
        haut_2b = pd.concat([haut_aj, haut_prec], axis=1).max(axis=1)
        bas_2b = pd.concat([bas_aj, bas_prec], axis=1).min(axis=1)
        gamma = np.log(haut_2b / bas_2b) ** 2
        alpha = (np.sqrt(2.0 * beta) - np.sqrt(beta)) / _K_CS - np.sqrt(gamma / _K_CS)
        bi_bougie = 2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha))

    bi_bougie = bi_bougie.where(np.isfinite(bi_bougie)).clip(lower=0.0)
    return bi_bougie.rolling(max(1, int(fenetre)), min_periods=1).mean()


def _serie_spread(df: pd.DataFrame, fenetre: int = FENETRE_SPREAD) -> np.ndarray:
    """L'estimateur, rendu utilisable bougie par bougie : plus aucun NaN.

    Avec `min_periods=1`, la seule bougie qui reste sans estimation est la PREMIERE de la
    serie — il lui faut une voisine pour exister. On lui donne la moyenne des spreads connus
    plutot que zero : un cout nul est la seule valeur a coup sur fausse, et ecarter le signal
    serait pire encore, parce que l'ensemble des trades mesures changerait selon qu'on paie
    le spread ou non. Un cout doit changer ce qu'un trade RAPPORTE, jamais quels trades
    existent.
    """
    estimes = spread_corwin_schultz(df, fenetre).to_numpy(dtype=float)
    connus = estimes[np.isfinite(estimes)]
    defaut = float(connus.mean()) if len(connus) else 0.0
    return np.where(np.isfinite(estimes), estimes, defaut)


def _heures_par_bougie(df: pd.DataFrame) -> float:
    """Pas de la serie en heures, par la mediane des ecarts. NaN si indeterminable."""
    if "date" not in df.columns or len(df) < 2:
        return float("nan")
    pas = pd.to_datetime(df["date"], utc=True).diff().median()
    if pd.isna(pas):
        return float("nan")
    heures = pas / pd.Timedelta(hours=1)
    return float(heures) if heures > 0 else float("nan")


def _serie_funding(df: pd.DataFrame, heures_funding: float = HEURES_FUNDING) -> np.ndarray:
    """Cout de funding PAR BOUGIE, en fraction du notionnel. Signe brut, non oriente.

    Le pipeline joint `funding_rate` en PALIER : merge_asof recopie le dernier taux regle
    sur toutes les bougies suivantes jusqu'au reglement d'apres. Sommer ce palier tel quel
    sur chaque bougie tenue paierait le meme reglement autant de fois qu'il y a de bougies
    dans une periode de funding — huit fois en 1h, deux fois en 4h — et, en 1d, un seul des
    trois reglements du jour. On ramene donc le taux au PRORATA de la duree de la bougie :
    le total paye sur un trade vaut alors `taux x duree_tenue / 8h`, quel que soit le
    timeframe, ce qui est la seule facon de rendre deux runs de pas differents comparables.

    Colonne absente (indice, chemin synthetique) => zero, sans erreur : une paire sans
    perpetuel ne paie pas de funding, ce n'est pas une donnee manquante. NaN (trou de
    jointure, warm-up) => zero aussi : un trou ne doit pas faire sauter le trade.
    """
    if "funding_rate" not in df.columns:
        return np.zeros(len(df))
    taux = pd.to_numeric(df["funding_rate"], errors="coerce").to_numpy(dtype=float)
    taux = np.where(np.isfinite(taux), taux, 0.0)
    heures = _heures_par_bougie(df)
    if not np.isfinite(heures) or heures_funding <= 0:
        # Pas de pas identifiable : on paie un reglement plein par bougie. Sens de l'erreur
        # volontaire — surestimer un cout n'a jamais fabrique d'edge.
        return taux
    return taux * (heures / float(heures_funding))


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
            cout_aller_retour_pct: float = 0.0, spread: bool = False,
            funding: bool = False, fenetre_spread: int = FENETRE_SPREAD,
            heures_funding: float = HEURES_FUNDING, paire: str = "",
            periode_atr: int = PERIODE_ATR) -> pd.DataFrame:
    """Rejoue chaque signal en triple barriere. Une ligne par signal, en R.

    `df` : OHLCV du lake (colonnes date/open/high/low/close), plus `funding_rate` si le
    pipeline l'a jointe. `signaux` : la sortie de `Candidate.appliquer`, alignee ligne a
    ligne, colonne `sens` (-1/0/+1) et, si la candidate en fournit un, `stop_distance`
    (distance en PRIX entre entree et stop).

    `spread` et `funding` sont a False ici, et a True dans `Run` : appele directement, ce
    module rend la geometrie nue, et c'est le Run qui porte la politique de couts du banc.
    Les activer ne change JAMAIS quels signaux sont mesures, seulement ce qu'ils rapportent.

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

    spread_tout = _serie_spread(df, fenetre_spread) if spread else np.zeros(n)
    funding_tout = _serie_funding(df, heures_funding) if funding else np.zeros(n)
    if funding and "funding_rate" not in df.columns:
        log.debug("%s : funding demande mais colonne absente — cout de funding nul",
                  paire or "serie")

    taille_bloc = max(1, CELLULES_PAR_BLOC // horizon)
    morceaux = []
    for debut in range(0, len(positions), taille_bloc):
        morceaux.append(_bloc(
            positions[debut:debut + taille_bloc], hauts, bas, clotures, dates,
            sens_tout, entree_tout, risque_tout, spread_tout, funding_tout,
            horizon, take_profit_r, cout_aller_retour_pct, n))
    trades = pd.concat(morceaux, ignore_index=True)
    trades.insert(0, "paire", paire)
    return trades


def _bloc(positions, hauts, bas, clotures, dates, sens_tout, entree_tout, risque_tout,
          spread_tout, funding_tout, horizon, take_profit_r, cout_pct, n) -> pd.DataFrame:
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

    masque = np.arange(horizon)[None, :] <= i_fin[:, None]   # les bougies TENUES, sortie incluse

    # --- les trois couts, tous en % du prix d'entree avant conversion en R ---------------
    # Un cout en % du prix vaut d'autant plus de R que le stop est serre : c'est exactement
    # ce qui tue les strategies a stop tres serre, et qu'un backtest sans couts ne montre
    # jamais. Le facteur est le meme pour les trois (notionnel 1x, collateral plein).
    i_sortie = np.minimum(depart + i_fin, n - 1)
    # Un demi-spread a l'entree (estimation de la bougie de signal, connue a sa cloture) et
    # un demi-spread a la sortie : un spread effectif complet par aller-retour.
    spread_pct = 100.0 * 0.5 * (spread_tout[positions] + spread_tout[i_sortie])
    # Funding : cumul sur les bougies tenues, de la premiere bougie APRES l'entree — celle
    # d'avant est deja reglee quand on entre a la cloture — a la bougie de sortie incluse.
    # Signe par le sens : positif = paye par le long, encaisse par le short.
    funding_cumul = np.nansum(np.where(masque, _fenetres(funding_tout, depart, horizon),
                                       0.0), axis=1)
    funding_pct = 100.0 * sens * funding_cumul
    total_pct = cout_pct + spread_pct + funding_pct

    vers_r = entree / risque
    frais_r = (cout_pct / 100.0) * vers_r
    spread_r = (spread_pct / 100.0) * vers_r
    funding_r = (funding_pct / 100.0) * vers_r
    cout_r = (total_pct / 100.0) * vers_r        # ce qui est REELLEMENT retire de r_brut
    r_net = r_brut - cout_r

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
        # Le detail a cote du total : sans lui, on ne peut pas dire si une candidate meurt
        # de trader trop souvent ou de tenir trop longtemps — deux maladies opposees.
        "frais_r": frais_r, "spread_r": spread_r, "funding_r": funding_r,
        "rendement_pct": sens * (cloture_fin / entree - 1.0) * 100.0 - total_pct,
        "mfe_r": np.where(np.isfinite(mfe_r), mfe_r, np.nan),
        "mae_r": np.where(np.isfinite(mae_r), mae_r, np.nan),
        "duree_h": duree_h, "duree_bougies": i_fin + 1,
        "raison_sortie": raison, "index_entree": positions,
    })


def _vide() -> pd.DataFrame:
    colonnes = ("paire", "ts_entree", "ts_sortie", "sens", "prix_entree", "prix_sortie",
                "stop", "cible", "risque", "r", "r_brut", "cout_r", "frais_r", "spread_r",
                "funding_r", "rendement_pct", "mfe_r", "mae_r", "duree_h", "duree_bougies",
                "raison_sortie", "index_entree")
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
