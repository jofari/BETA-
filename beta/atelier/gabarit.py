"""Le gabarit d'une candidate : la voie « a la main ».

Un squelette qui porte le contrat en clair, pour qu'on n'ait jamais a relire
`moteur/contrats.py` avant d'ecrire une regle. Il sert deux fois : quand Jonas ecrit sa
candidate lui-meme, et comme EXEMPLE joint au prompt d'un modele local — un modele a qui
l'on montre un fichier conforme en produit un conforme bien plus souvent qu'un modele a qui
on decrit le contrat en prose.

Le gabarit ne signale RIEN volontairement (`sens` reste a 0). L'epreuve le refusera donc
tant que la regle n'est pas ecrite, et c'est le comportement voulu : un squelette qui
passerait le sas serait un squelette qu'on peut mesurer par distraction.
"""

from __future__ import annotations

GABARIT = '''"""{titre}

Hypothese ({hypothese}) : {intention}

Regle, ecrite nue — sans filtre de regime, sans confirmation, sans porte macro. Une
candidate riche ne se teste pas : quand elle echoue on ne sait pas laquelle de ses six
regles a echoue, et quand elle reussit on ne sait pas laquelle a reussi. Les raffinements
viendront APRES un verdict sur la forme nue, et chacun sera une candidate distincte avec
son propre preenregistrement.
"""

from __future__ import annotations

import pandas as pd

from beta.moteur.contrats import Candidate

# Constantes en haut, jamais de nombre magique dans la regle : deux jeux de parametres sont
# deux candidates differentes, et l'empreinte du code doit pouvoir les distinguer.
FENETRE = 20


def signaux(df: pd.DataFrame, fenetre: int = FENETRE) -> pd.DataFrame:
    """Le coeur de la candidate. Fonction PURE : meme df, memes signaux.

    Recoit un OHLCV en UTC, index croissant, colonnes open/high/low/close/volume.
    Rend un DataFrame de MEME longueur, aligne ligne a ligne, avec au moins `sens` :
    +1 long, -1 short, 0 rien. Facultatif : `stop_distance` (distance en PRIX entre
    l'entree et le stop, qui definit l'unite de risque R), `force`, `note`.

    Trois interdits, verifies par l'epreuve et non par la relecture :

    - **ne jamais regarder apres la ligne qu'on decide.** Pas de `shift(-1)`, pas de
      `center=True`, pas de statistique calculee sur la serie ENTIERE (`close.max()`,
      `close.mean()`, une normalisation min-max) : toutes appliquent une valeur future aux
      lignes du passe. Une fenetre glissante (`rolling`, `ewm`) est causale, elle est la
      bonne facon d'ecrire a peu pres tout.
    - **ne jamais garder d'etat** entre deux appels, ni lire l'horloge, ni tirer au hasard
      sans graine : la meme entree doit rendre la meme sortie, toujours.
    - **ne jamais aller chercher de donnees.** La candidate recoit son DataFrame, elle
      n'ouvre rien.
    """
    # REMPLACER — pour l'instant la candidate ne signale rien, donc l'epreuve la refuse.
    # Exemple de forme causale attendue :
    #     moyenne = df["close"].rolling(fenetre, min_periods=fenetre).mean()
    #     sens[df["close"] > moyenne] = 1
    sens = pd.Series(0, index=df.index, dtype=int)
    return pd.DataFrame({{"sens": sens}})


def creer() -> Candidate:
    """La seule fonction que le registre cherche. Une candidate par fichier."""
    return Candidate(
        nom="{nom}",
        hypothese="{hypothese}",
        signaux=signaux,
        parametres={{"fenetre": FENETRE}},
        description="{intention}")
'''

# Montre au modele local a quoi ressemble une candidate finie et CAUSALE. C'est le meme
# fichier que `beta/candidates/r2_mean_reversion.py`, reduit a l'os : un exemple plus long
# ferait recopier ses commentaires plutot que sa forme.
EXEMPLE = '''"""R2 — mean-reversion : apres un ecart marque a sa moyenne, le prix revient."""

from __future__ import annotations

import pandas as pd

from beta.moteur.contrats import Candidate

FENETRE = 48
SEUIL_Z = 2.0


def signaux(df: pd.DataFrame, fenetre: int = FENETRE,
            seuil: float = SEUIL_Z) -> pd.DataFrame:
    close = df["close"]
    moyenne = close.rolling(fenetre, min_periods=fenetre).mean()
    ecart = close.rolling(fenetre, min_periods=fenetre).std(ddof=1)
    z = (close - moyenne) / ecart.where(ecart > 0)
    sens = pd.Series(0, index=df.index, dtype=int)
    sens[z <= -seuil] = 1
    sens[z >= seuil] = -1
    return pd.DataFrame({"sens": sens.fillna(0).astype(int), "force": z.abs()})


def creer() -> Candidate:
    return Candidate(
        nom="mean_reversion_z",
        hypothese="R2",
        signaux=signaux,
        parametres={"fenetre": FENETRE, "seuil_z": SEUIL_Z},
        description="retour a la moyenne sur ecart de z-score, sans aucun filtre")
'''


def ecrire(module: str, hypothese: str, nom: str = "", intention: str = "") -> str:
    """Rend le code d'un squelette. N'ecrit rien sur le disque : c'est l'appelant qui pose."""
    nom = nom or module
    intention = intention or "a decrire en une phrase falsifiable"
    titre = f"{hypothese} — {nom}"
    return GABARIT.format(titre=titre, hypothese=hypothese, nom=nom, intention=intention)
