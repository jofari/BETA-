"""Le hold-out scelle : la periode qu'on n'a pas le droit de regarder.

Un hold-out qu'on consulte « juste pour voir » est brule. Il n'y a pas de demi-mesure : soit
il n'a jamais servi a choisir quoi que ce soit, soit il ne vaut plus rien. D'ou un refus
MATERIEL plutot qu'une consigne — la consigne, on la contourne un soir de fatigue.

Date alignee sur celle d'ARIT (`analysis/dataset.py:HOLDOUT_DEBUT`) pour que les resultats
des deux projets restent comparables sur la meme coupure.
"""

from __future__ import annotations

import pandas as pd

# ⚠️ Une fois scellee, cette date ne bouge plus. La deplacer, meme « juste un peu »,
# equivaut a supprimer le hold-out : on choisirait la coupure en fonction du resultat.
DEBUT = pd.Timestamp("2025-01-01", tz="UTC")

TRAIN, HOLDOUT = "train", "holdout"


class HoldoutError(RuntimeError):
    """Tentative de lire le hold-out sans autorisation explicite."""


def split(dates: pd.Series) -> pd.Series:
    """Etiquette chaque horodatage `train` ou `holdout`. Materialise la coupure en colonne.

    L'ecrire en colonne plutot que de la recalculer partout est ce qui rend l'oubli
    impossible : un filtre absent se voit, un filtre jamais ecrit ne se voit pas.
    """
    return pd.Series([HOLDOUT if d >= DEBUT else TRAIN
                      for d in pd.to_datetime(dates, utc=True)], index=dates.index)


def exiger_train(df: pd.DataFrame, colonne: str = "split") -> pd.DataFrame:
    """Refuse de laisser passer une ligne de hold-out. A appeler avant toute mesure."""
    if colonne not in df.columns:
        raise HoldoutError(f"colonne '{colonne}' absente : impossible de garantir que le "
                           "hold-out est exclu. Poser la colonne avec split().")
    intrus = int((df[colonne] == HOLDOUT).sum())
    if intrus:
        raise HoldoutError(f"{intrus} ligne(s) de hold-out dans un jeu de mesure. "
                           "Le regarder, c'est le bruler.")
    return df


def filtrer_train(df: pd.DataFrame, colonne_date: str = "ts_entree") -> pd.DataFrame:
    """Ne garde que l'avant-coupure. La voie normale d'acces aux donnees de mesure."""
    if colonne_date not in df.columns:
        raise HoldoutError(f"colonne '{colonne_date}' absente")
    return df[pd.to_datetime(df[colonne_date], utc=True) < DEBUT].copy()
