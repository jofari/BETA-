"""S10 : la PBO (CSCV) d'une selection « la meilleure parmi plusieurs ».

Decisions de Jonas du 26/10/2026 (`DECISIONS.md`) : porte OBLIGATOIRE de la batterie, franchie
si la PBO est < 20 % (`batterie.SEUIL_PBO`), calculee comme PBOC (`pbo_voie_c/`) : rendements
quotidiens, S = 16 blocs CONTIGUS, Sharpe, `beta.stats.cscv`.

- Lot de trading : le rendement du jour d'une candidate est la somme des R des trades clotures
  ce jour-la, 0 sans cloture, du premier au dernier jour de cloture du LOT. Pas la variation en
  % de l'equity : la courbe du moteur est a risque fixe, non composee, et passe sous zero chez
  une candidate tres perdante (R10 disjonction : -234 R), ou un pourcentage ne veut plus rien
  dire. A risque fixe, la somme des R est le P&L du jour a un facteur constant pres : memes
  Sharpe relatifs, memes rangs.
- Les jours les plus ANCIENS sont retires pour que T soit un multiple de S (blocs egaux).
- Doublons exacts (rendements identiques bit a bit) : on garde le premier dans l'ordre des
  colonnes. Les colonnes d'un lot sont dans l'ordre des noms : le meme lot rend la meme PBO
  quel que soit l'ordre d'arrivee (une egalite de Sharpe IS se departage par la premiere).

Une PBO incalculable rend `passe = None` : moins d'un jour par bloc, moins de 2 configurations
distinctes, ecart-type nul sur une moitie (une candidate sans trade sur 8 blocs sur 16). La
porte n'est alors pas executee, et la candidate reste au mieux INDECIDABLE : jamais franchie
par defaut.
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from beta.stats import cscv

S = 16
PPA = 252.0      # comme PBOC ; l'annualisation ne change aucun rang, donc aucune PBO
QUANTILES = (0.05, 0.25, 0.5, 0.75, 0.95)


def rendements_lot(trades: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Matrice jours x candidates : somme des R clotures chaque jour (UTC), 0 sans cloture.

    Un R manquant compte 0, comme dans `espace_r.equity`. Une candidate sans trade est une
    colonne de zeros : elle a fait partie du choix, elle reste dans la matrice.
    """
    par_jour: dict[str, pd.Series] = {}
    for nom in sorted(trades):
        t = trades[nom]
        if t is None or t.empty or not {"ts_sortie", "r"} <= set(t.columns):
            par_jour[nom] = pd.Series(dtype=float)
            continue
        jours = pd.DatetimeIndex(pd.to_datetime(t["ts_sortie"], utc=True)).floor("D")
        r = pd.Series(t["r"].fillna(0.0).to_numpy(dtype=float), index=jours)
        par_jour[nom] = r.groupby(level=0).sum()
    remplies = [s for s in par_jour.values() if not s.empty]
    if not remplies:
        return pd.DataFrame(columns=list(par_jour), dtype=float)
    index = pd.date_range(min(s.index.min() for s in remplies),
                          max(s.index.max() for s in remplies), freq="D")
    return pd.DataFrame({nom: s.reindex(index, fill_value=0.0)
                         for nom, s in par_jour.items()}, index=index)


def couper(m: pd.DataFrame, s: int = S) -> pd.DataFrame:
    """Retire les jours les plus ANCIENS pour que T soit un multiple de S (comme PBOC)."""
    return m.iloc[len(m) % s:]


def dedoublonner(m: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Retire les colonnes identiques bit a bit a une colonne precedente."""
    vus: dict[str, str] = {}
    gardees, doublons = [], []
    for nom in m.columns:
        cle = hashlib.sha256(
            np.ascontiguousarray(m[nom].to_numpy(dtype=float)).tobytes()).hexdigest()
        if cle in vus:
            doublons.append({"nom": nom, "identique_a": vus[cle]})
        else:
            vus[cle] = nom
            gardees.append(nom)
    return m[gardees], doublons


def _jour(x) -> str:
    return f"{pd.Timestamp(x):%Y-%m-%d}"


def calculer(rendements: pd.DataFrame, seuil: float, s: int = S, ppa: float = PPA) -> dict:
    """La PBO d'une matrice jours x configurations, et la porte qui en sort (PBO < seuil)."""
    m = couper(rendements, s)
    base = {"seuil": seuil, "s": s, "n_configs_avant": int(rendements.shape[1]),
            "n_jours_avant": int(len(rendements)), "n_jours": int(len(m)), "doublons": [],
            "n_configs": int(rendements.shape[1]),
            "debut": _jour(m.index[0]) if len(m) else None,
            "fin": _jour(m.index[-1]) if len(m) else None,
            "pbo": None, "passe": None, "raison": None}
    if len(m) < s:
        return {**base, "raison": f"{len(rendements)} jour(s) : moins d'un jour par bloc "
                                  f"({s} blocs)"}
    m, doublons = dedoublonner(m)
    base.update(doublons=doublons, n_configs=int(m.shape[1]))
    if m.shape[1] < 2:
        return {**base, "raison": f"{m.shape[1]} configuration(s) distincte(s) : aucune "
                                  "selection a juger"}
    try:
        r = cscv.pbo(m.to_numpy(dtype=float), s, ppa)
    except cscv.CSCVError as exc:
        return {**base, "raison": f"PBO incalculable : {exc}"}
    noms = list(m.columns)
    etoiles, nb = np.unique(r.etoiles, return_counts=True)
    return {**base, "pbo": r.pbo, "passe": bool(r.pbo < seuil),
            "jours_par_bloc": r.jours_par_bloc, "n_combinaisons": r.n_combinaisons,
            "w": {f"{q:g}": float(np.quantile(r.w, q)) for q in QUANTILES},
            "etoiles": {noms[int(i)]: float(k / r.n_combinaisons)
                        for i, k in zip(etoiles, nb, strict=True)}}
