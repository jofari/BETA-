"""S8 — buy-and-hold : la reference imposee de toute candidate.

Invariant n° 6 de la doctrine. Une strategie qui gagne 40 % sur une periode ou BTC en a fait
300 n'a pas d'edge : elle a une exposition, mal reglee. C'est le resultat le plus frequent
d'un banc d'essai, et le plus facile a ne pas voir quand on ne compare qu'a zero.

La comparaison se fait sur la MEME periode, les MEMES paires, et avec les memes couts a
l'entree et a la sortie. Toute autre facon de la faire avantage l'un des deux camps.

Le hold de reference est equipondere sur les paires de l'univers du run, rebalance jamais :
c'est le portefeuille naif que quelqu'un aurait pu tenir sans rien savoir. Le battre est le
minimum exigible, pas un exploit.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

JOURS_AN = 365.0


def _serie_journaliere(df: pd.DataFrame) -> pd.Series:
    """Clotures ramenees au pas journalier, indexees par date UTC."""
    serie = df.set_index(pd.to_datetime(df["date"], utc=True))["close"]
    return serie.resample("1D").last().dropna()


def hold(series: dict[str, pd.DataFrame], cout_aller_retour_pct: float = 0.0) -> dict:
    """Buy-and-hold equipondere sur `series` : {paire: OHLCV}. Rendements journaliers."""
    journalieres = {p: _serie_journaliere(df) for p, df in series.items() if not df.empty}
    if not journalieres:
        return {"n_paires": 0, "rendement_total_pct": float("nan")}
    normalisees = pd.DataFrame({p: s / s.iloc[0] for p, s in journalieres.items()}).dropna()
    if normalisees.empty:
        return {"n_paires": len(journalieres), "rendement_total_pct": float("nan")}
    courbe = normalisees.mean(axis=1)
    rendements = courbe.pct_change().dropna()
    total = float(courbe.iloc[-1] - 1.0) * 100.0 - cout_aller_retour_pct
    sommet = courbe.cummax()
    return {
        "n_paires": len(journalieres), "n_jours": len(courbe),
        "debut": str(courbe.index[0].date()), "fin": str(courbe.index[-1].date()),
        "rendement_total_pct": total,
        "cagr_pct": _cagr(courbe),
        "sharpe_annuel": sharpe_annuel(rendements),
        "drawdown_max_pct": float(((courbe / sommet - 1.0) * 100.0).min()),
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
