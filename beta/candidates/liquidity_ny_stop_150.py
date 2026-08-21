"""liquidity_ny_stop_150 — R8 : fader la premiere bougie de l'open New York.

Variante du balayage de la distance de stop : stop hors de portee d'un second
balayage de la meme fenetre.

Les trois variantes du lot sont IDENTIQUES sauf `FRACTION_STOP`, et generees d'un meme
gabarit. C'est ce qui permet de lire l'ecart entre elles comme un effet de la distance de
stop, et pas comme une difference de code qui aurait derive en cours de route.

Hypothese de mecanisme : les 45 premieres minutes de la seance americaine sont le moment ou
le carnet est le plus epais et ou les clusters de stops accumules pendant la nuit asiatique
et la seance europeenne sont les plus rentables a aller chercher. Le mouvement de cette
fenetre serait donc, en partie, une prise de liquidite plutot qu'une information — et ce qui
suit, un retour.

La regle est NUE : un sens, un stop, rien d'autre. Pas de filtre de regime, pas de
confirmation de volume, pas de condition de meche. Une candidate riche qui echoue n'apprend
rien a personne.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from beta.moteur.contrats import Candidate

# Ancrage sur l'heure de NEW YORK, jamais sur UTC. 09:30 a New York, c'est 13:30 UTC en heure
# d'ete et 14:30 UTC en heure d'hiver : figer le creneau en UTC raterait l'ouverture pendant
# la moitie de l'annee, et pas la meme moitie selon les annees. Le decalage se verrait dans
# le resultat sans jamais se voir dans le code.
FUSEAU = "America/New_York"
MINUTE_DEBUT = 9 * 60 + 30            # 09:30 — l'ouverture des actions americaines
MINUTE_FIN = 10 * 60 + 15             # 10:15 — exclue
BOUGIES_ATTENDUES = 9                 # 45 minutes en 5m : une fenetre trouee ne signale pas

# Le stop vaut la moitie de l'amplitude de la fenetre. Jonas a ecrit « 50 % du volume » ;
# le volume est en unites de coin et un stop en unites de PRIX, la conversion n'existe pas.
# C'est donc l'amplitude (high - low) de la fenetre qui sert d'unite de risque.
FRACTION_STOP = 1.5


def signaux(df: pd.DataFrame, fraction_stop: float = FRACTION_STOP,
            bougies_attendues: int = BOUGIES_ATTENDUES) -> pd.DataFrame:
    """Un signal par jour, pose sur la bougie qui CLOTURE la fenetre (10:15 New York).

    Le moteur entre a la cloture de la bougie de signal : le signal appartient donc a la
    derniere bougie de la fenetre, jamais a la premiere. Chaque valeur agregee ne lit que des
    bougies de cette meme fenetre, toutes anterieures ou egales a la ligne decidee — rien
    n'est lu apres.

    Rend `stop_distance` : le moteur s'en sert comme unite de risque R a la place de son stop
    ATR par defaut. Le take-profit, lui, n'appartient pas a la candidate — c'est
    `take_profit_r` du Run, et il vaut 3.0 pour obtenir la cible a 150 % de l'amplitude.
    """
    heure = pd.to_datetime(df["date"], utc=True).dt.tz_convert(FUSEAU)
    minute = heure.dt.hour * 60 + heure.dt.minute
    dans_la_fenetre = (minute >= MINUTE_DEBUT) & (minute < MINUTE_FIN)

    sens = pd.Series(0, index=df.index, dtype=int)
    stop = pd.Series(np.nan, index=df.index, dtype=float)
    fenetre = df.loc[dans_la_fenetre]
    if fenetre.empty:
        return pd.DataFrame({"sens": sens, "stop_distance": stop})

    jour = heure.loc[dans_la_fenetre].dt.normalize()
    groupes = fenetre.groupby(jour, sort=False)
    seance = pd.DataFrame({
        "ouverture": groupes["open"].first(),
        "cloture": groupes["close"].last(),
        "haut": groupes["high"].max(),
        "bas": groupes["low"].min(),
        "bougies": groupes["close"].size(),
    })
    # La ligne ou le signal se pose : la DERNIERE bougie de la fenetre. Les series du lake
    # sont triees par date, donc la derniere valeur du groupe est bien la plus tardive.
    seance["fin"] = pd.Series(fenetre.index.to_numpy(),
                              index=jour.to_numpy()).groupby(level=0).last()

    amplitude = seance["haut"] - seance["bas"]
    corps = seance["cloture"] - seance["ouverture"]
    # Une fenetre incomplete ne signale pas : elle mesurerait autre chose que les 45 minutes
    # d'ouverture. Une fenetre plate non plus — sans amplitude il n'y a pas d'unite de risque,
    # et un corps nul ne donne aucun sens a fader.
    retenues = seance[(seance["bougies"] == bougies_attendues) & (amplitude > 0)
                      & (corps != 0)]
    if retenues.empty:
        return pd.DataFrame({"sens": sens, "stop_distance": stop})

    lignes = retenues["fin"].to_numpy()
    # Le fade : sens OPPOSE au corps de la fenetre. Une fenetre haussiere est lue comme une
    # prise des stops au-dessus, donc on vend.
    sens.loc[lignes] = np.where(retenues["cloture"] > retenues["ouverture"], -1, 1)
    stop.loc[lignes] = fraction_stop * (retenues["haut"] - retenues["bas"]).to_numpy()

    return pd.DataFrame({"sens": sens.astype(int), "stop_distance": stop})


def creer() -> Candidate:
    return Candidate(
        nom="liquidity_ny_stop_150",
        titre="Fade open NY — stop 1,5x amplitude",
        hypothese="R8",
        signaux=signaux,
        parametres={"fuseau": FUSEAU, "minute_debut": MINUTE_DEBUT,
                    "minute_fin": MINUTE_FIN, "bougies_attendues": BOUGIES_ATTENDUES,
                    "fraction_stop": FRACTION_STOP},
        description="entrer a 10:15 New York dans le sens oppose au corps de la fenetre "
                    "09:30-10:15, stop a 1.5x son amplitude")
