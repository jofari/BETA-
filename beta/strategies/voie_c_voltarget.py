"""Voie C — portefeuille ARP vol-cible, levier borne [0,33 ; 2,0], NET de frais.

    ARIT_HOME=/root/ARIT2.0 PYTHONPATH=/root/BETA- \
        /root/venvs/arit/bin/python beta/strategies/voie_c_voltarget.py

Ce script ne cherche pas une strategie : il chiffre si la GESTION DE PORTEFEUILLE
(diversification + vol-targeting + levier borne) tient debout une fois les frais payes.

Trois jambes, sur les 6 perpetuels Binance, toutes causales :

  1. base   inverse-vol         w_i = (1/sigma_i) / somme(1/sigma_j), sigma = vol 180j
  2. trend  TSMOM               w_i = signe(rendement 126j) * (1/sigma_i) / somme(1/sigma_j)
  3. carry  funding transversal long les 3 funding quotidiens les plus bas, short les 3
                                plus hauts, +-1/6 chacun

Les trois jambes ont la meme exposition brute (somme des |poids| = 1), ce qui rend le
melange a poids egaux (1/3 chacun, FIXE a priori, jamais optimise) comparable jambe a jambe.
La jambe carry est dollar-neutre (somme des poids = 0), la jambe base est nette longue a
+1, la jambe trend porte le signe du momentum.

Vol-targeting : sigma_realisee(t) = vol annualisee (sqrt 252) du composite NON LEVIER sur
30 ou 60 jours ; L(t) = clamp(sigma_cible / sigma_realisee(t), 0.33, 2.0).

Causalite — tout est decale d'un jour avant de rencontrer un rendement :
- les poids du jour t ne sont calcules que sur des donnees <= t-1 ;
- le levier du jour t n'utilise que des rendements de composite <= t-1 ;
- le funding du jour d (3 reglements a 00:00, 08:00 et 16:00 UTC) est entierement connu
  avant la cloture de la bougie quotidienne d (00:00 UTC de d+1) : le decalage d'un jour
  suffit, et c'est la convention deja retenue par `voie_b_trading.funding_quotidien`.

Ce fichier est un SCRIPT DE MESURE, pas une candidate du moteur : il ne passe ni par
`contrats.Run`, ni par le preenregistrement, ni par la batterie S1-S9. Ce qu'il imprime est
une mesure descriptive, pas un verdict d'edge (invariant n° 7).
"""

from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd

from beta.lake.lecture import funding, load

log = logging.getLogger("beta.strategies.voie_c")

# --- Univers et fenetres -----------------------------------------------------------------

PAIRES = ("BTC", "ETH", "SOL", "BNB", "LINK", "XRP")
TIMEFRAME = "1d"

FENETRE_VOL = 180          # vol realisee de la jambe base et de la jambe trend
FENETRE_MOM = 126          # rendement cumule du TSMOM
FENETRES_CIBLE = (30, 60)  # fenetres de vol realisee du composite, pour le vol-targeting
CIBLES = (0.25, 0.45, 0.70)

LEVIER_MIN, LEVIER_MAX = 0.33, 2.0

FIN_TRAIN = "2024-06-30"
DEBUT_TEST = "2024-07-01"

# Annualisation. sqrt(252) est ce que le brief impose pour sigma_realisee, et c'est aussi ce
# qui reproduit le chiffre de controle (inverse-vol nu ~0,86 pleine periode / 0,45 OOS).
# On l'utilise donc PARTOUT, y compris pour les Sharpe rapportes, pour que tout le rapport
# soit sur la meme echelle. Un calendrier crypto est 7/7 : sqrt(365) serait plus naturel et
# multiplierait tous les Sharpe par 1,20. C'est une convention d'affichage, pas un resultat.
PPA = 252
JOURS_AN = 365.25          # pour le CAGR et le turnover annuel : des annees CALENDAIRES

# --- Couts -------------------------------------------------------------------------------

BPS_TAKER = 5.0            # taker Binance, par cote, sur chaque unite de turnover
BPS_SLIPPAGE = 2.0         # variante severe : 5 + 2 = 7 bps

REBALANCEMENTS = {"quotidien": 1, "hebdo": 7}


class MesureError(RuntimeError):
    """Donnee insuffisante pour construire le portefeuille."""


# =========================================================================================
# Donnees
# =========================================================================================

def calendrier_commun(paires: tuple[str, ...]) -> pd.DatetimeIndex:
    """Intersection stricte des dates quotidiennes des paires demandees."""
    commun: pd.DatetimeIndex | None = None
    for paire in paires:
        dates = load(paire, TIMEFRAME, colonnes=("close",))["date"]
        idx = pd.DatetimeIndex(dates)
        commun = idx if commun is None else commun.intersection(idx)
    if commun is None or commun.empty:
        raise MesureError("intersection des dates vide")
    return commun.sort_values()


def calendrier_union(paires: tuple[str, ...]) -> pd.DatetimeIndex:
    """Union des dates : chaque paire entre des qu'elle existe. Sert au bloc de controle."""
    union: pd.DatetimeIndex | None = None
    for paire in paires:
        idx = pd.DatetimeIndex(load(paire, TIMEFRAME, colonnes=("close",))["date"])
        union = idx if union is None else union.union(idx)
    if union is None or union.empty:
        raise MesureError("union des dates vide")
    return union.sort_values()


def clotures(paires: tuple[str, ...], index: pd.DatetimeIndex) -> pd.DataFrame:
    """Matrice des clotures, une colonne par paire, sur le calendrier demande."""
    colonnes = {}
    for paire in paires:
        serie = load(paire, TIMEFRAME, colonnes=("close",)).set_index("date")["close"]
        colonnes[paire] = serie.astype(float).reindex(index)
    return pd.DataFrame(colonnes, index=index)


def funding_quotidien(paires: tuple[str, ...], index: pd.DatetimeIndex) -> pd.DataFrame:
    """Somme des 3 reglements 8h du jour, par paire, sur le calendrier demande.

    La SOMME et pas la moyenne : c'est le cout reellement regle sur une journee de detention.
    """
    colonnes = {}
    for paire in paires:
        brut = funding(paire)
        jour = brut["date"].dt.floor("D")
        colonnes[paire] = brut.groupby(jour)["funding_rate"].sum().reindex(index)
    return pd.DataFrame(colonnes, index=index)


# =========================================================================================
# Les trois jambes
# =========================================================================================

def inverse_vol(rendements: pd.DataFrame, fenetre: int = FENETRE_VOL) -> pd.DataFrame:
    """1/sigma_i, sigma = vol realisee glissante. Brique commune aux jambes base et trend."""
    sigma = rendements.rolling(fenetre, min_periods=fenetre).std(ddof=1)
    return 1.0 / sigma.replace(0.0, np.nan)


def jambe_base(rendements: pd.DataFrame) -> pd.DataFrame:
    """w_i = (1/sigma_i) / somme(1/sigma_j). Long-only, brut = net = 1."""
    inverse = inverse_vol(rendements)
    return inverse.div(inverse.sum(axis=1), axis=0)


def jambe_trend(closes: pd.DataFrame, rendements: pd.DataFrame) -> pd.DataFrame:
    """m_i / sigma_i normalise par somme(1/sigma_j) : le signe porte la direction.

    Le denominateur est la somme des 1/sigma NON signes : la jambe garde donc une exposition
    BRUTE de 1 quel que soit le nombre de longs et de shorts, exactement comme la jambe base.
    Normaliser par la somme signee ferait exploser le levier les jours ou les signes
    s'annulent — un artefact de normalisation, pas une decision de portefeuille.
    """
    inverse = inverse_vol(rendements)
    momentum = np.sign(closes / closes.shift(FENETRE_MOM) - 1.0)
    return (inverse * momentum).div(inverse.sum(axis=1), axis=0)


def jambe_carry(funding_j: pd.DataFrame) -> pd.DataFrame:
    """Transversale : long les 3 funding les plus bas, short les 3 plus hauts, +-1/6.

    +-1/6 et pas +-1/3 : l'exposition BRUTE vaut alors 1, comme les deux autres jambes. Le
    melange a 1/3 chacun ne mesure une combinaison de trois jambes que si les trois sont a
    la meme echelle. La jambe est dollar-neutre par construction.
    """
    rang = funding_j.rank(axis=1, method="first")
    n = funding_j.shape[1]
    haut = n - 3
    poids = np.where(rang <= 3, 1.0 / 6.0, np.where(rang > haut, -1.0 / 6.0, 0.0))
    sortie = pd.DataFrame(poids, index=funding_j.index, columns=funding_j.columns)
    return sortie.where(funding_j.notna().all(axis=1), np.nan)


def composite(base: pd.DataFrame, trend: pd.DataFrame, carry: pd.DataFrame) -> pd.DataFrame:
    """Somme des 3 jambes a poids egaux. 1/3 FIXE a priori, jamais optimise."""
    return (base + trend + carry) / 3.0


# =========================================================================================
# Moteur : deroule une matrice de positions cibles, avec derive entre reequilibrages
# =========================================================================================

def derouler(cible: pd.DataFrame, rendements: pd.DataFrame, funding_j: pd.DataFrame,
             pas_rebal: int, bps: float) -> pd.DataFrame:
    """Deroule jour par jour la position reellement tenue, et compte ce qu'elle coute.

    `cible` est DEJA causale : la ligne t est la position voulue POUR la journee t, calculee
    sur des donnees <= t-1.

    Entre deux reequilibrages on ne touche a rien : la position DERIVE avec les prix, comme
    une vraie position. C'est ce qui distingue un hebdo d'un quotidien autrement que par un
    sous-echantillonnage cosmetique — sans la derive, l'hebdo ne paierait pas ses frais au
    bon endroit et ne porterait pas le bon risque en milieu de semaine.

        derive_i(t) = tenu_i(t-1) * (1 + r_i(t-1)) / (1 + r_brut(t-1))

    La derive est calculee sur le rendement BRUT : brut et net partagent donc exactement le
    meme chemin de positions, et leur ecart ne mesure QUE les frais — ce qui est precisement
    la question posee. Turnover = somme des |tenu - derive| : un reequilibrage quotidien a
    poids constants paie donc quand meme la derive, ce qu'un simple diff() des poids cibles
    ignorerait.

    Rend un DataFrame indexe par date : r_brut, r_net, turnover, frais, carry_funding.
    """
    dates = cible.index
    matrice_cible = cible.to_numpy(dtype=float)
    matrice_rend = rendements.reindex(dates).to_numpy(dtype=float)
    matrice_fund = funding_j.reindex(dates).to_numpy(dtype=float)
    cout_unitaire = bps / 1e4

    n_jours, n_actifs = matrice_cible.shape
    r_brut = np.zeros(n_jours)
    r_net = np.zeros(n_jours)
    turnover = np.zeros(n_jours)
    frais = np.zeros(n_jours)
    carry = np.zeros(n_jours)

    tenu = np.zeros(n_actifs)
    derive = np.zeros(n_actifs)

    for i in range(n_jours):
        if i > 0:
            croissance = 1.0 + matrice_rend[i - 1]
            derive = tenu * croissance / (1.0 + r_brut[i - 1])

        if i % pas_rebal == 0:                       # jour de reequilibrage
            voulu = matrice_cible[i]
            tenu = np.where(np.isnan(voulu), 0.0, voulu)
        else:                                        # on ne touche a rien
            tenu = derive

        turnover[i] = float(np.abs(tenu - derive).sum())
        frais[i] = turnover[i] * cout_unitaire
        r_brut[i] = float(np.nansum(tenu * matrice_rend[i]))
        carry[i] = float(np.nansum(tenu * matrice_fund[i]))
        r_net[i] = r_brut[i] - frais[i] - carry[i]

    return pd.DataFrame({"r_brut": r_brut, "r_net": r_net, "turnover": turnover,
                         "frais": frais, "carry_funding": carry}, index=dates)


# =========================================================================================
# Mesure
# =========================================================================================

def performance(rendements: pd.Series) -> dict:
    """Sharpe (rf=0), vol annualisee, max drawdown, CAGR."""
    r = rendements.dropna()
    if len(r) < 30:
        return {"sharpe": np.nan, "vol": np.nan, "mdd": np.nan, "cagr": np.nan, "n": len(r)}
    sigma = float(r.std(ddof=1))
    equite = (1.0 + r).cumprod()
    annees = (r.index[-1] - r.index[0]).days / JOURS_AN
    return {
        "sharpe": (float(r.mean()) / sigma * math.sqrt(PPA)) if sigma > 0 else np.nan,
        "vol": sigma * math.sqrt(PPA),
        "mdd": float((equite / equite.cummax() - 1.0).min()),
        "cagr": float(equite.iloc[-1]) ** (1.0 / annees) - 1.0 if annees > 0 else np.nan,
        "n": len(r),
    }


def mesurer(sortie: pd.DataFrame, masque: pd.Series, levier: pd.Series | None) -> dict:
    """Les 6 metriques demandees, brut et net, sur une tranche de temps."""
    tranche = sortie[masque.to_numpy()]
    brut = performance(tranche["r_brut"])
    net = performance(tranche["r_net"])
    brut["turnover"] = float(tranche["turnover"].mean()) * JOURS_AN
    net["turnover"] = brut["turnover"]
    lev = 1.0 if levier is None else float(levier[masque.to_numpy()].mean())
    brut["levier"] = net["levier"] = lev
    net["frais"] = float(tranche["frais"].mean()) * JOURS_AN
    net["carry"] = float(tranche["carry_funding"].mean()) * JOURS_AN
    brut["frais"] = brut["carry"] = 0.0
    return {"brut": brut, "net": net}


# =========================================================================================
# Rapport
# =========================================================================================

EN_TETE = (f"  {'':<30s}{'':<7s}{'Sharpe':>8s}{'vol an.':>9s}{'maxDD':>9s}{'CAGR':>9s}"
           f"{'turn/an':>9s}{'levier':>8s}")
SEPARATEUR = "  " + "-" * 87


def ligne(nom: str, genre: str, perf: dict) -> str:
    return (f"  {nom:<30s}{genre:<7s}{perf['sharpe']:>8.2f}{perf['vol']:>9.1%}"
            f"{perf['mdd']:>9.1%}{perf['cagr']:>9.1%}{perf['turnover']:>8.1f}x"
            f"{perf['levier']:>8.2f}")


def bloc(titre: str, entrees: list[tuple[str, dict]]) -> None:
    """Un tableau : pour chaque variante, la ligne brute puis la ligne nette."""
    print(f"\n{titre}")
    print(EN_TETE)
    print(SEPARATEUR)
    for nom, resultat in entrees:
        print(ligne(nom, "brut", resultat["brut"]))
        print(ligne("", "net", resultat["net"]))


# =========================================================================================
# Epreuve de causalite
# =========================================================================================

def epreuve_causalite(index: pd.DatetimeIndex, closes: pd.DataFrame,
                      funding_j: pd.DataFrame, comp: pd.DataFrame,
                      sigmas: dict[int, pd.Series]) -> list[tuple[str, float]]:
    """`signaux(df[:t])` doit rendre exactement `signaux(df)[:t]`, levier compris.

    C'est l'epreuve que le projet oppose aux listes de motifs interdits : une liste attrape
    ce qu'elle connait, la causalite attrape ce qu'on n'avait pas prevu. On rejoue tout le
    calcul sur une serie TRONQUEE aux deux tiers et on compare au calcul sur la serie
    entiere. Un seul ecart non nul, et tous les chiffres du rapport sont faux.

    Rend une liste (nom de la grandeur, plus grand ecart absolu observe).

    Comparer deux series trouees demande deux verifications et pas une : les VALEURS la ou
    les deux existent, et le DESSIN des trous. `NaN - NaN` vaut NaN, et un `.max()` qui
    ignore les NaN declarerait identiques deux series dont les periodes de rodage different.
    Un trou qui se deplace est exactement ce qu'un look-ahead produit.
    """
    def comparer(gauche: pd.DataFrame | pd.Series,
                 droite: pd.DataFrame | pd.Series) -> float:
        manque_g, manque_d = gauche.isna(), droite.isna()
        if not manque_g.equals(manque_d):
            return float("inf")            # les trous ne tombent pas au meme endroit
        ecart = (gauche - droite).abs().to_numpy()
        fini = ecart[~np.isnan(ecart)]
        return float(fini.max()) if fini.size else 0.0

    t = index[len(index) * 2 // 3]
    court = index[index <= t]
    closes_t = closes.loc[court]
    rend_t = closes_t.pct_change()
    comp_t = composite(jambe_base(rend_t), jambe_trend(closes_t, rend_t),
                       jambe_carry(funding_j.loc[court]))

    ecarts = [("poids du composite", comparer(comp_t, comp.loc[court]))]
    r_comp_t = (comp_t.shift(1) * rend_t).sum(axis=1, skipna=False)
    for fen in FENETRES_CIBLE:
        sigma_t = r_comp_t.rolling(fen, min_periods=fen).std(ddof=1) * math.sqrt(PPA)
        ecarts.append((f"sigma realisee {fen}j", comparer(sigma_t, sigmas[fen].loc[court])))
    return ecarts


# =========================================================================================
# Bloc de controle : reproduire l'inverse-vol nu de reference
# =========================================================================================

def controle_inverse_vol() -> None:
    """Reproduit le chiffre de controle (~0,86 pleine periode / 0,45 OOS) avant tout le reste.

    Deux constructions donnent deux nombres tres differents en PLEINE PERIODE, et il faut
    savoir laquelle est laquelle avant de lire quoi que ce soit :

    - UNION : chaque paire entre des qu'elle a 180 jours d'historique, les poids sont
      renormalises sur les paires disponibles. Le portefeuille demarre donc en 2020-03 avec
      BTC seul, puis BTC+ETH... Il capte le marche haussier 2020-2021 en portefeuille
      CONCENTRE. C'est la construction qui rend ~0,9 en pleine periode.
    - INTERSECTION : les 6 paires ensemble ou rien. Demarre en 2021-03, et rend 0,53.

    L'ecart (0,9 contre 0,53) ne mesure pas une meilleure allocation : il mesure le fait que
    la premiere construction contient du BTC seul en 2020. Le composite de la voie C exige
    les 6 paires (la jambe carry est transversale), donc la seule reference comparable ligne
    a ligne est l'INTERSECTION. Les deux sont imprimees pour que rien ne soit cache.

    Le chiffre de controle annonce est 0,86 pleine periode / 0,45 OOS. L'OOS retombe a
    0,457 et le maxDD OOS a -60,6 % (annonce -61 %) : le controle est reproduit. La pleine
    periode UNION sort a 0,908 en ne comptant que les jours reellement investis, et a 0,875
    si l'on laisse dans la serie les jours anterieurs a plat (un zero avant le premier jour
    investi) — la seconde lecture est celle qui colle a 0,86. L'ecart residuel est cette
    convention de bord, pas une divergence de construction.
    """
    for nom, index, skipna in (("UNION (chaque paire des qu'elle existe)",
                                calendrier_union(PAIRES), True),
                               ("INTERSECTION (les 6 ensemble)",
                                calendrier_commun(PAIRES), False)):
        closes = clotures(PAIRES, index)
        rendements = closes.pct_change()
        poids = jambe_base(rendements)
        brute = (poids.shift(1) * rendements).sum(axis=1, skipna=skipna)
        r = brute[poids.shift(1).notna().any(axis=1).to_numpy()]
        pleine = performance(r)
        bord = performance(brute.fillna(0.0))       # convention de bord : jours a plat gardes
        train = performance(r[r.index <= pd.Timestamp(FIN_TRAIN, tz="UTC")])
        oos = performance(r[r.index >= pd.Timestamp(DEBUT_TEST, tz="UTC")])
        print(f"  {nom}")
        print(f"      depart {r.index[0]:%Y-%m-%d} | pleine periode Sharpe "
              f"{pleine['sharpe']:.3f} ({bord['sharpe']:.3f} jours a plat gardes) "
              f"| train {train['sharpe']:.3f} | OOS {oos['sharpe']:.3f} "
              f"(maxDD {oos['mdd']:.1%})")


# =========================================================================================
# Main
# =========================================================================================

def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    index = calendrier_commun(PAIRES)
    closes = clotures(PAIRES, index)
    rendements = closes.pct_change()
    funding_j = funding_quotidien(PAIRES, index)
    if funding_j.isna().any().any():
        log.warning("trous de funding sur le calendrier commun : %d cellules",
                    int(funding_j.isna().sum().sum()))

    jambes = {
        "jambe base (inv-vol)": jambe_base(rendements),
        "jambe trend (TSMOM)": jambe_trend(closes, rendements),
        "jambe carry (funding)": jambe_carry(funding_j),
    }
    comp = composite(*jambes.values())

    # Le levier ne regarde que le composite NON LEVIER, quotidien, brut : une seule serie de
    # sigma_realisee pour toutes les variantes, donc aucune circularite entre le levier et
    # la variante qu'il pilote.
    r_composite = (comp.shift(1) * rendements).sum(axis=1, skipna=False)
    leviers, sigmas = {}, {}
    for fen in FENETRES_CIBLE:
        sigma = r_composite.rolling(fen, min_periods=fen).std(ddof=1) * math.sqrt(PPA)
        sigmas[fen] = sigma
        for cible in CIBLES:
            brut = cible / sigma.replace(0.0, np.nan)
            leviers[(cible, fen)] = brut.clip(LEVIER_MIN, LEVIER_MAX)

    # Fenetre d'evaluation : le premier jour ou TOUTES les variantes existent — composite ET
    # levier le plus lent (60j). Toutes les lignes du rapport, references comprises, sont
    # mesurees sur exactement cette fenetre. Demarrer chaque variante a sa propre date
    # rendrait la comparaison fausse dans le sens le plus sournois : la variante la plus
    # rapide gagnerait ou perdrait sur des jours que les autres n'ont jamais vus.
    causal = (comp.shift(1).notna().all(axis=1) & rendements.notna().all(axis=1)
              & sigmas[max(FENETRES_CIBLE)].shift(1).notna())
    depart = index[causal.to_numpy()][0]
    fenetre = index[index >= depart]

    masque_train = pd.Series(fenetre <= pd.Timestamp(FIN_TRAIN, tz="UTC"), index=fenetre)
    masque_oos = pd.Series(fenetre >= pd.Timestamp(DEBUT_TEST, tz="UTC"), index=fenetre)

    print("=" * 96)
    print("VOIE C — portefeuille ARP vol-cible, levier borne [0,33 ; 2,0], NET de frais")
    print("=" * 96)
    print(f"Univers          : {len(PAIRES)} perpetuels Binance — {', '.join(PAIRES)}")
    print(f"Calendrier commun: {index[0]:%Y-%m-%d} -> {index[-1]:%Y-%m-%d} "
          f"({len(index)} jours, 7/7)")
    print(f"Rodage           : vol {FENETRE_VOL}j + momentum {FENETRE_MOM}j "
          f"-> composite actif a partir du {depart:%Y-%m-%d}")
    print(f"TRAIN            : {depart:%Y-%m-%d} -> {FIN_TRAIN}   "
          f"({int(masque_train.sum())} jours)")
    print(f"OOS              : {DEBUT_TEST} -> {fenetre[-1]:%Y-%m-%d}   "
          f"({int(masque_oos.sum())} jours)")
    print(f"Couts            : taker {BPS_TAKER:.0f} bps par cote sur le turnover "
          f"+ funding reellement regle sur la position tenue")
    print(f"Annualisation    : sqrt({PPA}) partout (impose, et c'est l'echelle du chiffre "
          "de controle) ; CAGR et turnover en annees calendaires")

    print("\n" + "-" * 96)
    print("BLOC 0 — CONTROLE : l'inverse-vol nu doit retomber sur ~0,86 / 0,45")
    print("-" * 96)
    controle_inverse_vol()

    print("\n" + "-" * 96)
    print("EPREUVE DE CAUSALITE — tout recalcule sur la serie tronquee aux 2/3")
    print("-" * 96)
    ecarts = epreuve_causalite(index, closes, funding_j, comp, sigmas)
    for nom, ecart in ecarts:
        etat = "OK" if ecart < 1e-12 else "ECHEC"
        print(f"  [{etat:<5s}] {nom:<28s} plus grand ecart {ecart:.3e}")
    if any(ecart >= 1e-12 for _, ecart in ecarts):
        raise MesureError("epreuve de causalite echouee : tout le rapport serait faux")

    # ---------------------------------------------------------------------------------
    # Les variantes
    # ---------------------------------------------------------------------------------
    def cibles_de(poids: pd.DataFrame, levier: pd.Series | None = None) -> pd.DataFrame:
        """Passe des poids bruts a une matrice de positions cibles causale et leviere."""
        decale = poids.shift(1).reindex(fenetre)
        if levier is not None:
            decale = decale.mul(levier.shift(1).reindex(fenetre), axis=0)
        return decale

    rend_f = rendements.reindex(fenetre)
    fund_f = funding_j.reindex(fenetre)

    def lancer(poids: pd.DataFrame, pas: int, levier: pd.Series | None = None,
               bps: float = BPS_TAKER) -> tuple[pd.DataFrame, pd.Series | None]:
        cible = cibles_de(poids, levier)
        sortie = derouler(cible, rend_f, fund_f, pas, bps)
        lev = None if levier is None else levier.shift(1).reindex(fenetre)
        if lev is not None and pas > 1:
            # A l'hebdo le levier n'est rafraichi qu'au reequilibrage : le levier EN FORCE
            # est celui du dernier jour de rebalancement, pas celui du jour courant.
            grille = pd.Series(np.nan, index=fenetre)
            grille.iloc[::pas] = lev.iloc[::pas]
            lev = grille.ffill()
        return sortie, lev

    # Reference : BTC buy-and-hold, dans le meme moteur (donc il paie SON funding).
    btc_poids = pd.DataFrame(0.0, index=index, columns=list(PAIRES))
    btc_poids["BTC"] = 1.0

    references: list[tuple[str, pd.DataFrame, int, pd.Series | None]] = [
        ("BTC buy & hold", btc_poids, 1, None),
        ("inverse-vol nu · quotidien", jambes["jambe base (inv-vol)"], 1, None),
        ("inverse-vol nu · hebdo", jambes["jambe base (inv-vol)"], 7, None),
    ]
    jambes_seules: list[tuple[str, pd.DataFrame, int, pd.Series | None]] = [
        (f"{nom} · quot.", poids, 1, None) for nom, poids in jambes.items()
    ] + [
        ("composite 1/3 · quotidien", comp, 1, None),
        ("composite 1/3 · hebdo", comp, 7, None),
    ]

    variantes: list[tuple[str, pd.DataFrame, int, pd.Series | None]] = []
    for fen in FENETRES_CIBLE:
        for cible in CIBLES:
            for nom_freq, pas in REBALANCEMENTS.items():
                variantes.append((f"vt {cible:.0%} / {fen}j / {nom_freq}", comp, pas,
                                  leviers[(cible, fen)]))

    # ABLATION, hors demande et pourtant decisive. Un levier CONSTANT ne peut pas changer le
    # Sharpe brut d'une strategie : il multiplie moyenne et ecart-type par le meme nombre.
    # Donc tout ecart de Sharpe BRUT entre le composite nu et une variante vol-cible vient
    # du CALENDRIER du levier, pas de son niveau. Ces lignes le rendent verifiable a l'oeil :
    # elles rejouent chaque cible a levier fige au niveau moyen effectivement porte.
    ablations: list[tuple[str, pd.DataFrame, int, pd.Series | None]] = []
    for fen in FENETRES_CIBLE:
        for cible in CIBLES:
            moyen = float(leviers[(cible, fen)].reindex(fenetre).mean())
            constant = pd.Series(moyen, index=index)
            ablations.append((f"levier CONSTANT {moyen:.2f} (={cible:.0%}/{fen}j)",
                              comp, 1, constant))

    tout = references + jambes_seules + variantes + ablations
    resultats: dict[str, dict] = {}
    sorties: dict[str, pd.DataFrame] = {}
    for nom, poids, pas, levier in tout:
        sortie, lev = lancer(poids, pas, levier)
        sorties[nom] = sortie
        resultats[nom] = {
            "train": mesurer(sortie, masque_train, lev),
            "oos": mesurer(sortie, masque_oos, lev),
        }

    for periode, titre in (("train", f"TRAIN   {depart:%Y-%m-%d} -> {FIN_TRAIN}"),
                           ("oos", f"OOS     {DEBUT_TEST} -> {fenetre[-1]:%Y-%m-%d}")):
        print("\n" + "=" * 96)
        print(titre)
        print("=" * 96)
        bloc("REFERENCES IMPOSEES", [(n, resultats[n][periode]) for n, *_ in references])
        bloc("LES 3 JAMBES SEPAREES, ET LE COMPOSITE",
             [(n, resultats[n][periode]) for n, *_ in jambes_seules])
        bloc("COMPOSITE VOL-CIBLE — 3 cibles x 2 fenetres x 2 frequences",
             [(n, resultats[n][periode]) for n, *_ in variantes])

    # ---------------------------------------------------------------------------------
    # Ablation : le vol-target, est-ce le NIVEAU du levier ou son CALENDRIER ?
    # ---------------------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("ABLATION — levier VARIABLE contre levier CONSTANT de meme niveau moyen (OOS)")
    print("=" * 96)
    print(f"  {'cible / fenetre':<22s}{'L moyen':>9s}{'Sharpe brut':>13s}"
          f"{'Sharpe brut':>13s}{'ecart':>9s} {'meme, net':>18s}")
    print(f"  {'':<22s}{'':>9s}{'VARIABLE':>13s}{'CONSTANT':>13s}{'':>9s}"
          f"{'var.':>9s}{'const.':>9s}")
    print(SEPARATEUR)
    for i, fen in enumerate(FENETRES_CIBLE):
        for j, cible in enumerate(CIBLES):
            nom_var = f"vt {cible:.0%} / {fen}j / quotidien"
            nom_abl = ablations[i * len(CIBLES) + j][0]
            v, c = resultats[nom_var]["oos"], resultats[nom_abl]["oos"]
            print(f"  cible {cible:.0%} / {fen}j{'':<7s}{v['brut']['levier']:>9.2f}"
                  f"{v['brut']['sharpe']:>13.2f}{c['brut']['sharpe']:>13.2f}"
                  f"{v['brut']['sharpe'] - c['brut']['sharpe']:>9.2f}"
                  f"{v['net']['sharpe']:>9.2f}{c['net']['sharpe']:>9.2f}")
    print("  Un levier constant ne PEUT PAS changer un Sharpe brut : il multiplie moyenne et")
    print("  ecart-type par le meme nombre. La colonne CONSTANT retombe donc sur le composite")
    print("  nu, et la colonne 'ecart' est exactement ce que le CALENDRIER du levier apporte.")

    # ---------------------------------------------------------------------------------
    # Ou part l'argent
    # ---------------------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("DECOMPOSITION DU COUT — ce que le brut perd, et par quelle porte")
    print("=" * 96)
    print(f"  {'':<28s}{'brut':>10s}{'frais':>10s}{'funding':>10s}{'net':>10s}"
          f"{'turn/an':>10s}")
    print(SEPARATEUR)
    interessants = [n for n, *_ in references + jambes_seules]
    for nom in interessants:
        tranche = sorties[nom][masque_oos.to_numpy()]
        brut = float(tranche["r_brut"].mean()) * JOURS_AN
        frais = float(tranche["frais"].mean()) * JOURS_AN
        carry = float(tranche["carry_funding"].mean()) * JOURS_AN
        print(f"  {nom:<28s}{brut:>10.1%}{-frais:>10.1%}{-carry:>10.1%}"
              f"{brut - frais - carry:>10.1%}{tranche['turnover'].mean() * JOURS_AN:>9.1f}x")
    print("  (rendements arithmetiques annualises sur l'OOS, pas des CAGR : ils s'additionnent)")

    # ---------------------------------------------------------------------------------
    # Pourquoi la jambe carry ne recolte rien : le rang de funding ne tient pas un jour
    # ---------------------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("JAMBE CARRY — le signal survit-il aux 24 h qui separent le rang du reglement ?")
    print("=" * 96)
    rang = funding_j.rank(axis=1, method="first")
    persistance = float(rang.corrwith(rang.shift(1), axis=1).mean())
    w_carry = jambes["jambe carry (funding)"]
    fund_oos = funding_j.reindex(fenetre)[masque_oos.to_numpy()]
    causal_rev = -(w_carry.shift(1).reindex(fenetre)[masque_oos.to_numpy()]
                   * fund_oos).sum(axis=1).mean() * JOURS_AN
    triche = -(w_carry.reindex(fenetre)[masque_oos.to_numpy()]
               * fund_oos).sum(axis=1).mean() * JOURS_AN
    frais_carry = float(sorties["jambe carry (funding) · quot."][masque_oos.to_numpy()]
                        ["frais"].mean()) * JOURS_AN
    print(f"  correlation du rang de funding avec celui de la veille : {persistance:+.3f}")
    print(f"  revenu de funding recolte, classement CAUSAL (rang de t-1)  : {causal_rev:>7.2%} /an")
    print(f"  revenu de funding si l'on classait sur le jour MEME (triche): {triche:>7.2%} /an")
    print(f"  frais de rotation payes pour aller le chercher              : {-frais_carry:>7.2%} /an")
    print("  La ligne 'triche' est un LOOK-AHEAD volontaire : elle ne mesure pas une")
    print("  strategie, elle borne par le haut ce que ce signal pourrait rapporter si le")
    print("  rang de funding etait connu a l'avance. Meme cette borne ne paie pas la rotation.")

    # ---------------------------------------------------------------------------------
    # Le levier est-il un vol-target, ou une constante deguisee ?
    # ---------------------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("LE CLAMP MORD-IL ? — un levier colle a sa borne n'est plus un vol-target")
    print("=" * 96)
    print(f"  {'variante':<20s}{'L moyen':>10s}{'% a 0,33':>11s}{'% libre':>10s}"
          f"{'% a 2,00':>11s}")
    print(SEPARATEUR)
    for fen in FENETRES_CIBLE:
        sigma = r_composite.rolling(fen, min_periods=fen).std(ddof=1) * math.sqrt(PPA)
        for cible in CIBLES:
            libre = (cible / sigma.replace(0.0, np.nan)).reindex(fenetre).dropna()
            bas = float((libre < LEVIER_MIN).mean())
            haut = float((libre > LEVIER_MAX).mean())
            lev = leviers[(cible, fen)].reindex(fenetre)
            print(f"  cible {cible:.0%} / {fen}j{'':<6s}{lev.mean():>10.2f}{bas:>11.1%}"
                  f"{1 - bas - haut:>10.1%}{haut:>11.1%}")

    # ---------------------------------------------------------------------------------
    # Selection sur le TRAIN, puis variante severe
    # ---------------------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("SELECTION DE (sigma_cible, fenetre) SUR LE TRAIN SEUL — puis figee")
    print("=" * 96)
    print(f"  {'variante':<24s}{'Sharpe net TRAIN':>18s}{'Sharpe net OOS':>18s}")
    print(SEPARATEUR)
    grille = [(nom, resultats[nom]) for nom, *_ in variantes if "quotidien" in nom]
    grille.sort(key=lambda x: -x[1]["train"]["net"]["sharpe"])
    for nom, res in grille:
        print(f"  {nom:<24s}{res['train']['net']['sharpe']:>18.2f}"
              f"{res['oos']['net']['sharpe']:>18.2f}")
    retenue = grille[0][0]
    print(f"\n  Retenue sur le TRAIN : {retenue}")
    print("  (le classement TRAIN n'est imprime qu'apres coup : la selection ne regarde que")
    print("   la colonne TRAIN, et la colonne OOS est la pour montrer si elle a servi a"
          " quelque chose)")

    print("\n" + "=" * 96)
    print(f"VARIANTE SEVERE — {BPS_TAKER + BPS_SLIPPAGE:.0f} bps par cote "
          f"({BPS_TAKER:.0f} taker + {BPS_SLIPPAGE:.0f} slippage), OOS")
    print("=" * 96)
    print(f"  {'':<30s}{'net 5 bps':>12s}{'net 7 bps':>12s}{'ecart':>10s}")
    print(SEPARATEUR)
    for nom, poids, pas, levier in references + jambes_seules + variantes:
        severe, _ = lancer(poids, pas, levier, bps=BPS_TAKER + BPS_SLIPPAGE)
        s5 = resultats[nom]["oos"]["net"]["sharpe"]
        s7 = performance(severe[masque_oos.to_numpy()]["r_net"])["sharpe"]
        print(f"  {nom:<30s}{s5:>12.2f}{s7:>12.2f}{s7 - s5:>10.2f}")

    # ---------------------------------------------------------------------------------
    # L'OOS tient-il sur toute sa longueur, ou sur un seul episode ?
    # ---------------------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("STABILITE DANS L'OOS — l'OOS coupe en deux moities egales (Sharpe net)")
    print("=" * 96)
    jours_oos = fenetre[masque_oos.to_numpy()]
    milieu = jours_oos[len(jours_oos) // 2]
    m1 = pd.Series((fenetre >= jours_oos[0]) & (fenetre < milieu), index=fenetre)
    m2 = pd.Series(fenetre >= milieu, index=fenetre)
    print(f"  moitie 1 : {jours_oos[0]:%Y-%m-%d} -> {milieu:%Y-%m-%d}  "
          f"({int(m1.sum())} jours)    "
          f"moitie 2 : {milieu:%Y-%m-%d} -> {jours_oos[-1]:%Y-%m-%d} "
          f"({int(m2.sum())} jours)")
    print(f"  {'':<30s}{'OOS complet':>13s}{'moitie 1':>11s}{'moitie 2':>11s}")
    print(SEPARATEUR)
    for nom, *_ in references + jambes_seules + variantes:
        tranche = sorties[nom]
        s1 = performance(tranche[m1.to_numpy()]["r_net"])["sharpe"]
        s2 = performance(tranche[m2.to_numpy()]["r_net"])["sharpe"]
        print(f"  {nom:<30s}{resultats[nom]['oos']['net']['sharpe']:>13.2f}"
              f"{s1:>11.2f}{s2:>11.2f}")
    print("  Un resultat porte par une seule moitie n'est pas un edge, c'est un episode.")

    # ---------------------------------------------------------------------------------
    # Le levier est-il un signal LENT, ou un reglage au jour pres ?
    # ---------------------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("RETARD SUPPLEMENTAIRE SUR LE LEVIER — un vrai signal de vol doit etre LENT")
    print("=" * 96)
    print(f"  {'variante':<26s}" + "".join(f"{f'+{k}j':>9s}" for k in (0, 1, 2, 3, 5, 10)))
    print(SEPARATEUR)
    for fen in FENETRES_CIBLE:
        for cible in (0.25,):
            for nom_freq, pas in REBALANCEMENTS.items():
                cases = []
                for retard in (0, 1, 2, 3, 5, 10):
                    lev = leviers[(cible, fen)].shift(retard)
                    sortie, _ = lancer(comp, pas, lev)
                    cases.append(performance(sortie[masque_oos.to_numpy()]["r_net"])["sharpe"])
                print(f"  vt {cible:.0%} / {fen}j / {nom_freq:<10s}"
                      + "".join(f"{c:>9.2f}" for c in cases))
    print("  La vol realisee bouge lentement : un edge qui s'effondre en decalant d'un jour")
    print("  serait un artefact de calage, pas une gestion du risque.")

    # ---------------------------------------------------------------------------------
    # Et si l'on retirait la jambe qui saigne ?
    # ---------------------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("SANS LA JAMBE CARRY — composite a 2 jambes (base + trend), 1/2 chacune")
    print("=" * 96)
    print("  Hors demande : la jambe carry paie 12 %/an de rotation pour recolter 2 %. La")
    print("  question 'le composite tient-il sans elle' est celle que le tableau pose ensuite.")
    comp2 = (jambes["jambe base (inv-vol)"] + jambes["jambe trend (TSMOM)"]) / 2.0
    r_comp2 = (comp2.shift(1) * rendements).sum(axis=1, skipna=False)
    print(EN_TETE)
    print(SEPARATEUR)
    for fen in FENETRES_CIBLE:
        sigma2 = r_comp2.rolling(fen, min_periods=fen).std(ddof=1) * math.sqrt(PPA)
        for cible in (0.25,):
            lev2 = (cible / sigma2.replace(0.0, np.nan)).clip(LEVIER_MIN, LEVIER_MAX)
            for nom_freq, pas in REBALANCEMENTS.items():
                sortie, lev = lancer(comp2, pas, lev2)
                res = mesurer(sortie, masque_oos, lev)
                print(ligne(f"2 jambes vt {cible:.0%}/{fen}j/{nom_freq}", "brut", res["brut"]))
                print(ligne("", "net", res["net"]))
    for nom_freq, pas in REBALANCEMENTS.items():
        sortie, _ = lancer(comp2, pas)
        res = mesurer(sortie, masque_oos, None)
        print(ligne(f"2 jambes nues · {nom_freq}", "brut", res["brut"]))
        print(ligne("", "net", res["net"]))

    print("\n" + "=" * 96)
    print("Rappel de protocole : ce script ne passe ni par le preenregistrement, ni par la")
    print("batterie S1-S9. Il MESURE une construction fixee a l'avance ; il ne CONFIRME rien.")
    print("=" * 96)


if __name__ == "__main__":
    main()
