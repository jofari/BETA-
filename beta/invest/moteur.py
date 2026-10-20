"""Test invest — le moteur : panier en buy and hold, score normalise, exposition, rendement.

Conventions (cahier des charges, A1-A3) :
- le panier n'est PAS rebalance : V_B(t) = somme w_i P_i(t) / P_i(0), les poids derivent ;
- jours = jours de RENDEMENT ; V(0) = 1 a la cloture de la veille du premier jour (P0) ;
- `e[i]` est l'exposition decidee a la cloture qui precede le jour i (V-index i) et s'applique
  au rendement r_B[i] de ce jour : R_S(t) = E(t-1) R_B(t) - kappa |E(t-1) - E(t-2)|
  - max(E(t-1) - 1, 0) phi(t), plus rf sur la part en cash. Les votes du socle sont deja
  « en vigueur » le jour t (decides a t 00:00 avec les donnees <= t-1) : `aligner` les pose
  sur le jour de rendement, sans autre decalage ;
- pas de cout d'entree, ni pour la strategie ni pour le hold.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

UN_JOUR = pd.Timedelta(days=1)


@dataclass(frozen=True)
class Mapping:
    """Score normalise -> exposition. « socle » : la veille garde E ; « paliers » : 0,7."""

    nom: str = "socle"
    theta_h: float = 0.4
    theta_b: float = 0.4
    e_haut: float = 1.0
    e_neutre: float = 0.7
    e_def: float = 0.25
    e_init: float = 1.0


def _ns(index: pd.DatetimeIndex) -> np.ndarray:
    return index.as_unit("ns").asi8


def score_normalise(votes: pd.DataFrame, actifs: tuple[str, ...]) -> pd.Series:
    """S~ = somme des votes actifs / leur nombre, dans [-1, 1] quel que soit K."""
    if not actifs:
        raise ValueError("aucun indicateur actif")
    return votes[list(actifs)].sum(axis=1) / len(actifs)


def exposition(score: np.ndarray, m: Mapping) -> np.ndarray:
    """E a chaque decision. Score arrondi a 1e-12 : 2/5 doit valoir +0,4, pas 0,39999..."""
    s = np.round(np.asarray(score, dtype=float), 12)
    haut, bas = s >= m.theta_h, s <= -m.theta_b
    if m.nom == "paliers":
        return np.where(haut, m.e_haut, np.where(bas, m.e_def, m.e_neutre))
    if m.nom == "socle":
        etat = pd.Series(np.where(haut, m.e_haut, np.where(bas, m.e_def, np.nan)))
        return etat.ffill().fillna(m.e_init).to_numpy()
    raise ValueError(f"mapping inconnu : {m.nom}")


def aligner(serie: pd.Series, jours: pd.DatetimeIndex) -> np.ndarray:
    """La valeur en vigueur chaque jour de rendement ; un jour sans valeur est une erreur."""
    x = serie.reindex(jours)
    if x.isna().any():
        raise ValueError(f"aucune valeur le {x.index[x.isna()][0]:%Y-%m-%d}")
    return x.to_numpy(dtype=float)


@dataclass
class Panier:
    jours: pd.DatetimeIndex        # N jours de rendement
    v: np.ndarray                  # N + 1 valeurs, v[0] = 1
    r: np.ndarray                  # N rendements
    poids_debut_jour: np.ndarray   # N x k : composition au debut de chaque jour (derivee)
    colonnes: tuple[str, ...]


def _fenetre(closes: pd.DataFrame, debut: pd.Timestamp, fin: pd.Timestamp) -> pd.DataFrame:
    p0 = debut - UN_JOUR
    if p0 not in closes.index:
        raise ValueError(f"pas de cloture le {p0:%Y-%m-%d} (P0 de la periode)")
    sub = closes.loc[p0:fin]
    if sub.isna().any().any():
        raise ValueError("cloture manquante dans la periode")
    return sub


def panier(closes: pd.DataFrame, poids: dict[str, float], debut: pd.Timestamp,
           fin: pd.Timestamp) -> Panier:
    """Le benchmark : buy and hold du panier, poids initiaux `poids`, jamais rebalance."""
    if abs(sum(poids.values()) - 1.0) > 1e-9:
        raise ValueError(f"les poids font {sum(poids.values())}, pas 1")
    absents = set(poids) - set(closes.columns)
    if absents:
        raise ValueError(f"actif(s) absent(s) des prix : {sorted(absents)}")
    colonnes = tuple(poids)
    sub = _fenetre(closes[list(colonnes)], debut, fin)
    relatif = (sub / sub.iloc[0]).to_numpy(dtype=float)
    w = np.array([poids[c] for c in colonnes])
    v = relatif @ w
    return Panier(jours=sub.index[1:], v=v, r=v[1:] / v[:-1] - 1.0,
                  poids_debut_jour=relatif[:-1] * w / v[:-1, None], colonnes=colonnes)


def hold(closes: pd.DataFrame, actif: str, debut: pd.Timestamp, fin: pd.Timestamp) -> np.ndarray:
    """V d'un seul actif tenu (benchmark secondaire : BTC)."""
    sub = _fenetre(closes[[actif]], debut, fin)[actif].to_numpy(dtype=float)
    return sub / sub[0]


def rendement(e: np.ndarray, r_b: np.ndarray, kappa_pb: float, phi: np.ndarray | None = None,
              rf: np.ndarray | None = None) -> dict:
    """R_S(t) = E R_B - kappa |dE| - max(E - 1, 0) phi + max(1 - E, 0) rf (A3)."""
    e = np.asarray(e, dtype=float)
    precedente = np.concatenate([e[:1], e[:-1]])              # pas de cout d'entree
    rotation = np.abs(e - precedente)
    cout = kappa_pb / 1e4 * rotation
    funding = np.maximum(e - 1.0, 0.0) * (0.0 if phi is None else np.asarray(phi, dtype=float))
    cash = np.maximum(1.0 - e, 0.0) * (0.0 if rf is None else np.asarray(rf, dtype=float))
    r = e * np.asarray(r_b, dtype=float) - cout - funding + cash
    return {"r": r, "cout": cout, "funding": funding * np.ones_like(r),
            "rf": cash * np.ones_like(r), "turnover": float(rotation.sum())}


def funding_panier(p: Panier, funding: pd.DataFrame) -> np.ndarray:
    """phi(t) : le funding du jour des perpetuels, pondere par la composition du matin."""
    f = funding.reindex(p.jours)[list(p.colonnes)]
    if f.isna().any().any():
        raise ValueError("funding manquant dans la periode")
    return (p.poids_debut_jour * f.to_numpy(dtype=float)).sum(axis=1)


def rf_quotidien(dff: pd.Series, jours: pd.DatetimeIndex) -> np.ndarray:
    """rf(t) = DFF (% par an) de la derniere observation <= t - 1 jour, / 100 / 365."""
    s = dff.dropna().sort_index()
    rang = np.searchsorted(_ns(s.index), _ns(jours - UN_JOUR), side="right") - 1
    if (rang < 0).any():
        raise ValueError("taux sans risque indisponible au debut de la periode")
    return s.to_numpy(dtype=float)[rang] / 100.0 / 365.0


def temoin_constant(e: np.ndarray, r_b: np.ndarray, kappa_pb: float) -> dict:
    """La meme exposition MOYENNE, sans timing : separe « moins expose » de « bien place »."""
    moyenne = float(np.mean(e))
    out = rendement(np.full(len(r_b), moyenne), r_b, kappa_pb)
    return {"e": moyenne, **out}
