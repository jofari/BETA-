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

# La derniere date du train. La bougie qui OUVRE a DEBUT appartient deja au hold-out.
FIN_TRAIN = DEBUT - pd.Timedelta(microseconds=1)


def split(dates: pd.Series) -> pd.Series:
    """Etiquette chaque horodatage `train` ou `holdout`. Materialise la coupure en colonne.

    L'ecrire en colonne plutot que de la recalculer partout est ce qui rend l'oubli
    impossible : un filtre absent se voit, un filtre jamais ecrit ne se voit pas.
    """
    return pd.Series([HOLDOUT if d >= DEBUT else TRAIN
                      for d in pd.to_datetime(dates, utc=True)], index=dates.index)


def borner_train(fin: str | None = None) -> str:
    """La borne de fin, INCLUSIVE, d'une lecture de train : `fin`, sans jamais atteindre DEBUT.

    `lecture.load` prend des bornes inclusives : couper « a DEBUT » lui faisait lire la
    bougie qui ouvre a DEBUT, la premiere du hold-out (une journee entiere en 1d). Constate
    par l'audit du 13/10 sur toutes les mesures du moteur. Rend une date ISO naive (UTC).
    """
    limite = FIN_TRAIN
    if fin:
        demande = pd.Timestamp(fin)
        demande = (demande.tz_localize("UTC") if demande.tzinfo is None
                   else demande.tz_convert("UTC"))
        limite = min(limite, demande)
    return limite.tz_convert(None).isoformat()
