"""S8 — buy-and-hold : la reference imposee de toute candidate.

Invariant n° 6 de la doctrine. Une strategie qui gagne 40 % sur une periode ou BTC en a fait
300 n'a pas d'edge : elle a une exposition, mal reglee. C'est le resultat le plus frequent
d'un banc d'essai, et le plus facile a ne pas voir quand on ne compare qu'a zero.

La comparaison se fait sur la MEME periode, les MEMES paires, et avec les MEMES COUTS.
Toute autre facon de la faire avantage l'un des deux camps.

Le hold de reference est equipondere sur les paires de l'univers du run, rebalance jamais :
c'est le portefeuille naif que quelqu'un aurait pu tenir sans rien savoir. Le battre est le
minimum exigible, pas un exploit.

Ce hold est un LONG PERPETUEL, pas un achat au comptant : il paie donc, en plus des frais
d'aller-retour, les deux couts de DETENTION que la candidate paie depuis le chantier des
frais — le spread bid-ask estime et le funding cumule sur toute la duree de detention. Les
laisser de cote donnerait a la reference un avantage qu'aucun portefeuille reel n'a, et
S8 sacrerait des candidates qui ne battent qu'un hold imaginaire. Les deux estimateurs sont
ceux du moteur (`espace_r`), importes et non recopies : une reference qui paierait un cout
calcule autrement ne serait plus comparable a ce qu'elle juge.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from beta.moteur import espace_r

JOURS_AN = 365.0


def _serie_journaliere(df: pd.DataFrame) -> pd.Series:
    """Clotures ramenees au pas journalier, indexees par date UTC."""
    serie = df.set_index(pd.to_datetime(df["date"], utc=True))["close"]
    return serie.resample("1D").last().dropna()


def _cout_detention_pct(df: pd.DataFrame, debut: pd.Timestamp, fin: pd.Timestamp, *,
                        spread: bool, funding: bool, fenetre_spread: int,
                        heures_funding: float) -> dict:
    """Ce qu'un long tenu de `debut` a `fin` paie sur UNE paire, en % du notionnel d'entree.

    Les deux couts se lisent avec les estimateurs du moteur, sur la serie ENTIERE puis
    tranches a la fenetre : le lissage du spread a besoin des bougies qui precedent le
    debut, et recalculer sur la seule tranche donnerait un warm-up different de celui que
    paient les trades de la candidate.

    - spread : un demi a l'entree, un demi a la sortie, soit un spread complet, exactement
      comme un aller-retour du moteur ;
    - funding : somme des taux au prorata sur les bougies TENUES, de celle qui SUIT
      l'entree a celle de sortie incluse. Le signe est celui du long (+1), donc un funding
      positif est un cout. Colonne absente (indice) => zero, sans erreur.
    """
    vide = {"spread_pct": 0.0, "funding_pct": 0.0, "total_pct": 0.0}
    if df.empty or "date" not in df.columns:
        return vide
    dates = pd.to_datetime(df["date"], utc=True)
    # `fin` est un horodatage JOURNALIER (minuit) : la courbe du hold s'arrete a la derniere
    # bougie de ce jour-la, pas a minuit. Sans le jour entier, on amputerait la detention.
    dans = (dates >= debut) & (dates < fin + pd.Timedelta(days=1))
    positions = np.flatnonzero(dans.to_numpy())
    if len(positions) < 2:
        return vide

    entree, sortie = int(positions[0]), int(positions[-1])
    spread_pct = funding_pct = 0.0
    if spread:
        estimes = espace_r._serie_spread(df, fenetre_spread)
        spread_pct = 100.0 * 0.5 * float(estimes[entree] + estimes[sortie])
    if funding:
        taux = espace_r._serie_funding(df, heures_funding)
        funding_pct = 100.0 * float(np.nansum(taux[entree + 1:sortie + 1]))
    return {"spread_pct": spread_pct, "funding_pct": funding_pct,
            "total_pct": spread_pct + funding_pct}


def hold(series: dict[str, pd.DataFrame], cout_aller_retour_pct: float = 0.0, *,
         spread: bool = False, funding: bool = False,
         fenetre_spread: int = espace_r.FENETRE_SPREAD,
         heures_funding: float = espace_r.HEURES_FUNDING) -> dict:
    """Buy-and-hold equipondere sur `series` : {paire: OHLCV}. Rendements journaliers.

    `spread` et `funding` sont a False ici et a True dans le `Run` (via `batterie.evaluer`),
    par la meme convention que `espace_r.evaluer` : appelee seule, la fonction rend le hold
    nu ; c'est le Run qui porte la politique de couts du banc. Appeler `hold()` sans eux
    reste donc exactement l'ancien comportement — aucun appelant existant ne change de
    resultat sans l'avoir demande.

    Les couts de detention sont moyennes sur les paires, a poids EGAUX — le poids qu'elles
    ont a l'entree, pas celui qu'elles ont pris depuis. C'est une approximation, et elle
    porte dans le bon sens : une paire qui a beaucoup monte pese plus que 1/n a la fin et
    paie donc, en vrai, plus de funding que ce qu'on lui compte ici. Le hold sort donc
    legerement MEILLEUR que le hold reel, ce qui durcit S8 au lieu de la relacher — le seul
    sens d'erreur qu'une porte a le droit d'avoir.

    Comme `cout_aller_retour_pct` avant eux, les deux couts viennent en deduction du
    RENDEMENT TOTAL seulement : ni le Sharpe, ni le drawdown, ni le CAGR de la reference ne
    les voient. C'est le comportement d'origine, conserve tel quel.
    """
    journalieres = {p: _serie_journaliere(df) for p, df in series.items() if not df.empty}
    if not journalieres:
        return {"n_paires": 0, "rendement_total_pct": float("nan")}
    normalisees = pd.DataFrame({p: s / s.iloc[0] for p, s in journalieres.items()}).dropna()
    if normalisees.empty:
        return {"n_paires": len(journalieres), "rendement_total_pct": float("nan")}
    courbe = normalisees.mean(axis=1)
    rendements = courbe.pct_change().dropna()

    couts = [_cout_detention_pct(series[p], courbe.index[0], courbe.index[-1],
                                 spread=spread, funding=funding,
                                 fenetre_spread=fenetre_spread,
                                 heures_funding=heures_funding)
             for p in normalisees.columns]
    detention_pct = float(np.mean([c["total_pct"] for c in couts])) if couts else 0.0
    total = float(courbe.iloc[-1] - 1.0) * 100.0 - cout_aller_retour_pct - detention_pct
    sommet = courbe.cummax()
    return {
        "n_paires": len(journalieres), "n_jours": len(courbe),
        "debut": str(courbe.index[0].date()), "fin": str(courbe.index[-1].date()),
        "rendement_total_pct": total,
        "cagr_pct": _cagr(courbe),
        "sharpe_annuel": sharpe_annuel(rendements),
        "drawdown_max_pct": float(((courbe / sommet - 1.0) * 100.0).min()),
        "cout_aller_retour_pct": float(cout_aller_retour_pct),
        "cout_spread_pct": float(np.mean([c["spread_pct"] for c in couts])) if couts else 0.0,
        "cout_funding_pct": (float(np.mean([c["funding_pct"] for c in couts]))
                             if couts else 0.0),
        "cout_detention_pct": detention_pct,
        "courbe": {"ts": [d.isoformat() for d in courbe.index],
                   "valeur": [float(v) for v in courbe.to_numpy()]},
    }


def _cagr(courbe: pd.Series) -> float:
    jours = (courbe.index[-1] - courbe.index[0]).days
    if jours <= 0 or courbe.iloc[0] <= 0:
        return float("nan")
    return float((courbe.iloc[-1] / courbe.iloc[0]) ** (JOURS_AN / jours) - 1.0) * 100.0


def sharpe_annuel(rendements: pd.Series) -> float:
    if len(rendements) < 2:
        return float("nan")
    sigma = float(rendements.std(ddof=1))
    return float(rendements.mean() / sigma * np.sqrt(JOURS_AN)) if sigma else float("nan")


def strategie_journaliere(equity: pd.DataFrame) -> dict:
    """Les memes metriques, calculees sur la courbe d'equity d'une candidate.

    Passer par une courbe journaliere plutot que par les R par trade est ce qui rend les
    deux comparables : un Sharpe par trade et un Sharpe journalier ne vivent pas sur la
    meme echelle, et les comparer directement est une erreur silencieuse.
    """
    if equity.empty:
        return {"rendement_total_pct": float("nan")}
    courbe = (equity.set_index(pd.to_datetime(equity["ts"], utc=True))["equity"]
              .resample("1D").last().ffill().dropna())
    if len(courbe) < 2:
        return {"rendement_total_pct": float("nan")}
    rendements = courbe.pct_change().dropna()
    sommet = courbe.cummax()
    return {"n_jours": len(courbe),
            "debut": str(courbe.index[0].date()), "fin": str(courbe.index[-1].date()),
            "rendement_total_pct": float(courbe.iloc[-1] / courbe.iloc[0] - 1.0) * 100.0,
            "cagr_pct": _cagr(courbe),
            "sharpe_annuel": sharpe_annuel(rendements),
            "drawdown_max_pct": float(((courbe / sommet - 1.0) * 100.0).min()),
            "courbe": {"ts": [d.isoformat() for d in courbe.index],
                       "valeur": [float(v) for v in courbe.to_numpy()]}}


def comparer(candidate: dict, reference: dict) -> dict:
    """La porte S8. `passe` exige de battre le hold en rendement ET en Sharpe.

    Les deux ensemble, parce qu'ils se compensent trop facilement : une strategie tres
    levieree bat le hold en rendement tout en etant pire a tenir, et une strategie a peine
    investie a un meilleur Sharpe sans rien rapporter.
    """
    ecart_rendement = candidate.get("rendement_total_pct", float("nan")) \
        - reference.get("rendement_total_pct", float("nan"))
    ecart_sharpe = candidate.get("sharpe_annuel", float("nan")) \
        - reference.get("sharpe_annuel", float("nan"))
    passe = bool(np.isfinite(ecart_rendement) and np.isfinite(ecart_sharpe)
                 and ecart_rendement > 0 and ecart_sharpe > 0)
    return {"ecart_rendement_pct": float(ecart_rendement),
            "ecart_sharpe": float(ecart_sharpe),
            "ecart_drawdown_pct": float(candidate.get("drawdown_max_pct", float("nan"))
                                        - reference.get("drawdown_max_pct", float("nan"))),
            "passe": passe}
