"""S6 — walk-forward avec purge et embargo (CPCV, Lopez de Prado ch. 7 et 12).

Une validation croisee ordinaire est FAUSSE sur des series financieres, pour une raison qui
n'a rien de subtil : un trade ouvert le 3 et ferme le 9 chevauche la frontiere entre un pli
d'entrainement finissant le 5 et un pli de test commencant le 6. L'information du test est
donc deja dans le train. Le score obtenu est trop bon, systematiquement, et rien ne le
signale.

Deux corrections, toutes deux indispensables :

- **purge** — on retire du train tout trade dont la fenetre [entree, sortie] chevauche le
  test. C'est la fuite directe ;
- **embargo** — on retire en plus une bande de temps APRES le test. C'est la fuite indirecte
  par autocorrelation : les rendements juste apres la periode de test lui ressemblent encore.

Ce module ne reoptimise rien : BETA ne fait pas d'hyperoptimisation (interdit n° 5 cote
ARIT, repris ici). Le walk-forward y sert a mesurer la STABILITE d'un edge dans le temps —
la question « ce resultat vient-il de toute la periode, ou de six mois de 2021 ? », qui tue
plus de candidates que la p-value.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

N_PLIS = 6
EMBARGO_PCT = 1.0            # part de la periode totale mise en quarantaine apres le test
K_TEST_CPCV = 2              # nombre de plis de test par combinaison


def _bornes(dates: pd.Series, n_plis: int) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Decoupage en plis de DUREE egale, pas d'effectif egal.

    A effectif egal, un pli pourrait couvrir trois ans calmes et le suivant deux mois de
    2021 : les plis ne seraient plus comparables entre eux, et la dispersion mesuree
    melangerait instabilite de l'edge et decoupage arbitraire.
    """
    debut, fin = dates.min(), dates.max()
    if pd.isna(debut) or pd.isna(fin) or debut == fin:
        return []
    coupures = pd.date_range(debut, fin, periods=n_plis + 1)
    return [(coupures[i], coupures[i + 1]) for i in range(n_plis)]


def _masque_test(trades: pd.DataFrame, plis: list[tuple]) -> np.ndarray:
    entrees = pd.to_datetime(trades["ts_entree"], utc=True)
    masque = np.zeros(len(trades), dtype=bool)
    for debut, fin in plis:
        masque |= ((entrees >= debut) & (entrees < fin)).to_numpy()
    return masque


def purger(trades: pd.DataFrame, plis_test: list[tuple], embargo_pct: float = EMBARGO_PCT,
           ) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """(train purge, test, comptes). L'ordre des retraits est ce qui garantit l'absence de fuite."""
    entrees = pd.to_datetime(trades["ts_entree"], utc=True)
    sorties = pd.to_datetime(trades["ts_sortie"], utc=True)
    duree_totale = entrees.max() - entrees.min()
    embargo = duree_totale * (embargo_pct / 100.0) if pd.notna(duree_totale) else pd.Timedelta(0)

    est_test = _masque_test(trades, plis_test)
    chevauche = np.zeros(len(trades), dtype=bool)
    for debut, fin in plis_test:
        # Purge : la fenetre du trade touche le pli de test, par un bout ou par l'autre.
        chevauche |= ((sorties >= debut) & (entrees <= fin)).to_numpy()
        # Embargo : la bande juste apres le test reste contaminee par autocorrelation.
        chevauche |= ((entrees > fin) & (entrees <= fin + embargo)).to_numpy()

    train = trades[~est_test & ~chevauche]
    test = trades[est_test]
    comptes = {"n_train": len(train), "n_test": len(test),
               "n_purges": int((~est_test & chevauche).sum()),
               "embargo_h": float(embargo / pd.Timedelta(hours=1)) if embargo else 0.0}
    return train, test, comptes


def _metrique(trades: pd.DataFrame, colonne: str = "r") -> float:
    valeurs = trades[colonne].dropna() if colonne in trades.columns else pd.Series(dtype=float)
    return float(valeurs.mean()) if len(valeurs) else float("nan")


def marche_en_avant(trades: pd.DataFrame, n_plis: int = N_PLIS,
                    embargo_pct: float = EMBARGO_PCT, colonne: str = "r") -> dict:
    """Walk-forward ancre : chaque pli sert de test, tout ce qui precede sert de train.

    `efficacite` = metrique OOS moyenne / metrique IS moyenne. Sous 0,5, l'edge mesure en
    train ne se retrouve pas hors echantillon, meme s'il reste positif : c'est le signe
    d'un sur-ajustement, pas d'une strategie fragile.
    """
    if trades.empty or "ts_entree" not in trades.columns:
        return {"n_plis": 0, "plis": [], "efficacite": float("nan")}
    dates = pd.to_datetime(trades["ts_entree"], utc=True)
    bornes = _bornes(dates, n_plis)
    lignes = []
    for i, (debut, fin) in enumerate(bornes):
        if i == 0:
            continue                     # aucun passe disponible pour entrainer
        train, test, comptes = purger(trades, [(debut, fin)], embargo_pct)
        train = train[pd.to_datetime(train["ts_entree"], utc=True) < debut]
        if not len(test) or not len(train):
            continue
        is_, oos = _metrique(train, colonne), _metrique(test, colonne)
        lignes.append({"pli": i + 1, "debut": str(debut.date()), "fin": str(fin.date()),
                       "is": is_, "oos": oos, **comptes,
                       "positif": bool(np.isfinite(oos) and oos > 0)})
    if not lignes:
        return {"n_plis": 0, "plis": [], "efficacite": float("nan")}
    is_moyen = float(np.nanmean([l["is"] for l in lignes]))
    oos_moyen = float(np.nanmean([l["oos"] for l in lignes]))
    return {"n_plis": len(lignes), "plis": lignes,
            "is_moyen": is_moyen, "oos_moyen": oos_moyen,
            "efficacite": oos_moyen / is_moyen if is_moyen else float("nan"),
            "plis_positifs": sum(l["positif"] for l in lignes),
            "dispersion_oos": float(np.nanstd([l["oos"] for l in lignes], ddof=1))
            if len(lignes) > 1 else float("nan")}


def cpcv(trades: pd.DataFrame, n_plis: int = N_PLIS, k_test: int = K_TEST_CPCV,
         embargo_pct: float = EMBARGO_PCT, colonne: str = "r") -> dict:
    """Combinatorial purged CV : toutes les combinaisons de `k_test` plis de test.

    Le walk-forward ancre ne donne qu'UN chemin de validation, celui de la chronologie
    reelle. CPCV en donne C(n, k), donc une DISTRIBUTION de performances hors echantillon —
    dont on lit la part de chemins perdants, la seule statistique qui repond a « quelle est
    la probabilite que ce systeme soit en perte sur une periode que je n'ai pas vue ? ».
    """
    if trades.empty:
        return {"n_combinaisons": 0, "part_chemins_perdants": float("nan")}
    dates = pd.to_datetime(trades["ts_entree"], utc=True)
    bornes = _bornes(dates, n_plis)
    if len(bornes) < k_test + 1:
        return {"n_combinaisons": 0, "part_chemins_perdants": float("nan")}

    scores = []
    for combinaison in itertools.combinations(range(len(bornes)), k_test):
        plis_test = [bornes[i] for i in combinaison]
        train, test, _ = purger(trades, plis_test, embargo_pct)
        if not len(test) or not len(train):
            continue
        scores.append(_metrique(test, colonne))
    scores = [s for s in scores if np.isfinite(s)]
    if not scores:
        return {"n_combinaisons": 0, "part_chemins_perdants": float("nan")}
    return {"n_combinaisons": len(scores), "oos_median": float(np.median(scores)),
            "oos_p5": float(np.percentile(scores, 5)),
            "oos_p95": float(np.percentile(scores, 95)),
            "part_chemins_perdants": float(np.mean(np.array(scores) <= 0)),
            "scores": [float(s) for s in scores]}
