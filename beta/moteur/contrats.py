"""Les trois contrats geles du banc d'essai : Candidate, Run, Verdict.

Ecrits AVANT toute implementation, et volontairement pauvres. Un contrat riche se
renegocie a chaque nouvelle candidate ; un contrat pauvre force les candidates a se plier
au moteur, jamais l'inverse. C'est la seule facon d'en tester des centaines sans que le
moteur devienne un sac de cas particuliers.

    Candidate  ce qu'une hypothese produit : des signaux, rien d'autre
    Run        une mesure, qui n'existe pas sans preenregistrement
    Verdict    ce qu'on a le droit de conclure, et surtout ce qu'on n'a pas le droit

Trois regles portees par le code plutot que par la discipline :

1. **`signaux(df)` est une fonction pure.** Meme df => memes signaux. Pas d'etat, pas
   d'horloge, pas de lecture disque. Une candidate qui garde un etat entre deux appels
   fabrique du look-ahead que rien ne rattrape ensuite.
2. **Un `Run` sans id de preenregistrement ne se construit pas.** Le refus est materiel
   (`protocole.exiger`), pas conventionnel.
3. **Un `Verdict` ne peut pas etre CONFIRMEE par defaut.** L'issue par defaut est
   INDECIDABLE ; c'est la batterie statistique qui, en echouant a tuer la candidate, la
   fait passer. Un verdict positif se merite, il ne se declare pas.
"""

from __future__ import annotations

import hashlib
import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

import pandas as pd

from beta.protocole import experiences, holdout

log = logging.getLogger("beta.moteur")

# Colonnes que signaux() doit rendre, et celles qu'il peut rendre en plus.
COLONNES_SIGNAUX_REQUISES = ("sens",)
COLONNES_SIGNAUX_OPTIONNELLES = ("stop_distance", "force", "note")

SENS_VALIDES = (-1, 0, 1)

CONFIRMEE, INFIRMEE, INDECIDABLE = "confirmee", "infirmee", "indecidable"
ISSUES = (CONFIRMEE, INFIRMEE, INDECIDABLE)


class ContratError(RuntimeError):
    """Une candidate, un run ou un verdict qui ne respecte pas son contrat."""


@runtime_checkable
class Signaux(Protocol):
    """La seule chose qu'une candidate sait faire."""

    def __call__(self, df: pd.DataFrame) -> pd.DataFrame: ...


@dataclass(frozen=True)
class Candidate:
    """Une hypothese rendue executable. Isolee : elle ne connait pas le moteur.

    `signaux` recoit un OHLCV (colonnes date/open/high/low/close/volume, UTC, croissant) et
    rend un DataFrame de MEME longueur, aligne ligne a ligne, avec au moins `sens`
    (-1 short, 0 rien, +1 long). Il peut porter `stop_distance` — la distance en PRIX entre
    l'entree et le stop, ce qui definit l'unite de risque R du trade. Sans elle, le Run
    impose son stop par defaut.

    `parametres` entre dans l'empreinte : deux jeux de parametres sont deux candidates
    differentes, jamais la meme qu'on aurait « ajustee ».
    """

    nom: str
    hypothese: str                    # id de l'experience preenregistree (ex: "R1")
    signaux: Callable[[pd.DataFrame], pd.DataFrame]
    parametres: dict = field(default_factory=dict)
    description: str = ""

    def __post_init__(self) -> None:
        if not self.nom or not self.nom.strip():
            raise ContratError("une candidate sans nom ne peut pas etre tracee")
        if not callable(self.signaux):
            raise ContratError(f"{self.nom} : `signaux` n'est pas appelable")

    @property
    def empreinte(self) -> str:
        """Identifie la candidate par son CODE et ses parametres, pas par son nom.

        Renommer une candidate ne doit pas la faire passer pour une nouvelle mesure, et
        modifier son code en gardant le nom ne doit pas la faire passer pour l'ancienne.
        """
        try:
            source = inspect.getsource(self.signaux)
        except (OSError, TypeError):        # lambda saisie a la volee, fonction generee
            source = repr(self.signaux)
        graine = f"{source}|{sorted(self.parametres.items())}"
        return hashlib.sha256(graine.encode("utf-8")).hexdigest()[:12]

    def appliquer(self, df: pd.DataFrame) -> pd.DataFrame:
        """Appelle signaux() et VERIFIE le contrat. Le seul chemin d'appel autorise.

        Verifier ici plutot que dans chaque candidate est ce qui permet d'en ecrire des
        dizaines sans repeter la validation — et sans qu'une seule l'oublie.
        """
        sortie = self.signaux(df)
        if not isinstance(sortie, pd.DataFrame):
            raise ContratError(f"{self.nom} : signaux() doit rendre un DataFrame, "
                               f"pas {type(sortie).__name__}")
        if len(sortie) != len(df):
            raise ContratError(f"{self.nom} : signaux() rend {len(sortie)} lignes pour "
                               f"{len(df)} en entree — l'alignement est rompu")
        manquantes = [c for c in COLONNES_SIGNAUX_REQUISES if c not in sortie.columns]
        if manquantes:
            raise ContratError(f"{self.nom} : colonnes manquantes {manquantes}")
        sens = sortie["sens"]
        if sens.isna().any():
            raise ContratError(f"{self.nom} : `sens` contient des NaN — utiliser 0")
        inconnus = set(pd.unique(sens.astype(int))) - set(SENS_VALIDES)
        if inconnus:
            raise ContratError(f"{self.nom} : sens hors {SENS_VALIDES} : {sorted(inconnus)}")
        sortie = sortie.copy()
        sortie["sens"] = sens.astype(int)
        sortie.index = df.index
        return sortie


@dataclass(frozen=True)
class Run:
    """Une mesure datee, reproductible, et rattachee a un preenregistrement.

    Le constructeur APPELLE protocole.exiger(). Il n'existe donc pas de chemin par lequel
    un chiffre sort du moteur sans que l'hypothese ait ete ecrite avant — c'est l'invariant
    n° 4 de la doctrine, rendu materiel.
    """

    candidate: Candidate
    paires: tuple[str, ...]
    timeframe: str
    id_experience: str = ""
    split: str = holdout.TRAIN
    debut: str | None = None
    fin: str | None = None
    # Barriere par defaut, si la candidate ne fournit pas son propre stop.
    stop_atr: float = 2.0
    take_profit_r: float = 2.0
    horizon_bougies: int = 96
    frais_pct: float = 0.05             # aller-retour, taker Binance perp
    slippage_pct: float = 0.02
    graine: int = 0
    preenregistrement: dict = field(default_factory=dict, repr=False)
    lance_le: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self) -> None:
        id_exp = self.id_experience or self.candidate.hypothese
        if not id_exp:
            raise ContratError(
                f"{self.candidate.nom} : aucun id d'experience. Un run sans "
                "preenregistrement ne mesure rien d'interpretable.")
        object.__setattr__(self, "id_experience", id_exp)
        object.__setattr__(self, "preenregistrement", experiences.exiger(id_exp))
        if self.split not in (holdout.TRAIN, holdout.HOLDOUT):
            raise ContratError(f"split inconnu : {self.split}")
        if self.split == holdout.HOLDOUT:
            autorise = self.preenregistrement.get("split_autorise")
            if autorise != holdout.HOLDOUT:
                raise ContratError(
                    f"'{id_exp}' n'autorise pas le hold-out (split_autorise="
                    f"{autorise!r}). Le regarder, c'est le bruler.")
            log.warning("RUN SUR LE HOLD-OUT : '%s'. Une seule fois, sans retour.", id_exp)
        if self.horizon_bougies < 1:
            raise ContratError("horizon_bougies doit valoir au moins 1")
        if not self.paires:
            raise ContratError("un run sans paire ne mesure rien")

    @property
    def id(self) -> str:
        """Identifiant stable d'un run : experience + empreinte de code + parametres."""
        graine = (f"{self.id_experience}|{self.candidate.empreinte}|{self.paires}|"
                  f"{self.timeframe}|{self.split}|{self.debut}|{self.fin}|"
                  f"{self.stop_atr}|{self.take_profit_r}|{self.horizon_bougies}")
        return hashlib.sha256(graine.encode("utf-8")).hexdigest()[:12]

    @property
    def cout_aller_retour_pct(self) -> float:
        """Frais + slippage. Un backtest qui l'oublie surestime toutes les petites edges."""
        return self.frais_pct + self.slippage_pct

    def resume(self) -> dict:
        return {"run_id": self.id, "experience": self.id_experience,
                "candidate": self.candidate.nom, "empreinte": self.candidate.empreinte,
                "paires": list(self.paires), "timeframe": self.timeframe,
                "split": self.split, "debut": self.debut, "fin": self.fin,
                "stop_atr": self.stop_atr, "take_profit_r": self.take_profit_r,
                "horizon_bougies": self.horizon_bougies,
                "cout_aller_retour_pct": self.cout_aller_retour_pct,
                "parametres": dict(self.candidate.parametres),
                "lance_le": self.lance_le}


@dataclass(frozen=True)
class Verdict:
    """Ce qu'on a le droit de conclure. Par defaut : rien.

    `portes` porte le detail de la batterie : {nom_du_test: bool passe}. Une seule porte a
    False suffit a interdire CONFIRMEE — c'est le sens meme d'une batterie de garde-fous,
    dont chaque element ne peut que degrader un resultat.

    `reserves` liste, en clair, ce qui empeche de conclure. Un verdict sans reserve
    explicite est suspect : c'est ce qui manque a la plupart des backtests publies.
    """

    run: Run
    issue: str = INDECIDABLE
    metriques: dict = field(default_factory=dict)
    portes: dict = field(default_factory=dict)
    reserves: tuple[str, ...] = ()
    n_essais_cumules: int = 0

    def __post_init__(self) -> None:
        if self.issue not in ISSUES:
            raise ContratError(f"issue inconnue : {self.issue} (connues : {ISSUES})")
        if self.issue == CONFIRMEE and not self.portes:
            raise ContratError("CONFIRMEE sans aucune porte franchie : impossible. "
                               "Une candidate se confirme en survivant a la batterie.")
        if self.issue == CONFIRMEE and self.portes_echouees:
            raise ContratError(f"CONFIRMEE alors que {self.portes_echouees} ont echoue")
        if self.issue == CONFIRMEE and self.portes_non_executees:
            raise ContratError(f"CONFIRMEE alors que {self.portes_non_executees} n'ont pas "
                               "tourne — une porte non executee ne se presume pas franchie")

    @property
    def portes_echouees(self) -> list[str]:
        """Uniquement celles qui ont ECHOUE. `None` = non executee, ce n'est pas un echec.

        La distinction n'est pas cosmetique : confondre « teste et rate » avec « pas
        teste » ferait passer un verdict pour infirme alors qu'il est indecidable, et
        detruirait la seule information que la batterie apporte vraiment.
        """
        return sorted(nom for nom, passe in self.portes.items() if passe is False)

    @property
    def portes_non_executees(self) -> list[str]:
        return sorted(nom for nom, passe in self.portes.items() if passe is None)

    @property
    def survit(self) -> bool:
        return self.issue == CONFIRMEE

    def texte(self) -> str:
        """Le verdict en clair, reserves comprises. Destine a etre lu, pas parse."""
        lignes = [f"{self.run.candidate.nom} ({self.run.id_experience}) : "
                  f"{self.issue.upper()}",
                  f"  run {self.run.id} — {self.run.split} — essai cumule "
                  f"n° {self.n_essais_cumules}"]
        for cle, valeur in self.metriques.items():
            lignes.append(f"  {cle} = {valeur:.4f}" if isinstance(valeur, float)
                          else f"  {cle} = {valeur}")
        etiquettes = {True: "ok", False: "ECHEC", None: "non executee"}
        for nom, passe in sorted(self.portes.items()):
            lignes.append(f"  [{etiquettes[passe]}] {nom}")
        for reserve in self.reserves:
            lignes.append(f"  reserve : {reserve}")
        return "\n".join(lignes)

    def dict(self) -> dict:
        return {**self.run.resume(), "issue": self.issue, "metriques": self.metriques,
                "portes": self.portes, "portes_echouees": self.portes_echouees,
                "portes_non_executees": self.portes_non_executees,
                "reserves": list(self.reserves),
                "n_essais_cumules": self.n_essais_cumules}
