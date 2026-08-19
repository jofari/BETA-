"""La boite a idees : l'etage qui manquait AVANT le preenregistrement.

Preenregistrer coute cher — chaque hypothese ecrite entre au compteur d'essais cumulatif,
donc durcit le seuil de toutes les autres, definitivement. C'est voulu, et c'est ce qui rend
le compteur honnete. Mais la consequence est qu'on ne peut pas preenregistrer chaque idee de
passage, et l'effet observe est pire que le probleme : faute d'endroit ou les mettre sans
payer, **les idees ne sont notees nulle part**. Elles vivent dans une conversation, puis
nulle part.

D'ou deux etages, et un seul point de bascule :

    IDEES.jsonl        gratuit, sans forme imposee, on y jette tout
        |
        | promouvoir()  <- LE moment ou ca coute : le compteur avance d'un cran
        v
    EXPERIMENTS.jsonl  hypothese falsifiable, metrique primaire, regle de decision

Ce que la promotion force a ecrire est exactement ce qui manque a une idee pour devenir
mesurable : **quelle metrique**, et **quelle regle de decision fixee AVANT**. Une idee qu'on
n'arrive pas a promouvoir n'est pas une mauvaise idee — c'est une idee qu'on n'a pas encore
su rendre falsifiable, et le dire est deja un resultat.

Trois etats : `nouvelle`, `promue` (elle a un id d'experience), `ecartee` (avec son motif).
Une idee ecartee ne disparait jamais du fichier : savoir ce qu'on a decide de ne pas tester,
et pourquoi, vaut autant que savoir ce qu'on a teste.
"""

from __future__ import annotations

import json
import logging
import pathlib
from datetime import UTC, datetime

from beta import config
from beta.protocole import experiences

log = logging.getLogger("beta.protocole.idees")

# A la racine, comme EXPERIMENTS.jsonl et RUNS.jsonl (invariant n° 10) : `data/` est jetable,
# et une idee perdue par un nettoyage est une idee qu'on n'aura pas deux fois.
REGISTRE = config.RACINE / "IDEES.jsonl"

NOUVELLE, PROMUE, ECARTEE = "nouvelle", "promue", "ecartee"
ETATS = (NOUVELLE, PROMUE, ECARTEE)


class IdeeError(RuntimeError):
    """Idee vide, inconnue, ou registre illisible."""


def _lignes(chemin: pathlib.Path | None = None) -> list[dict]:
    chemin = chemin or REGISTRE
    if not chemin.exists():
        return []
    entrees = []
    for n, ligne in enumerate(chemin.read_text(encoding="utf-8").splitlines(), 1):
        if not ligne.strip():
            continue
        try:
            entrees.append(json.loads(ligne))
        except json.JSONDecodeError as exc:
            raise IdeeError(f"{chemin.name} ligne {n} illisible : {exc}") from exc
    return entrees


def _ajouter(entree: dict, chemin: pathlib.Path) -> None:
    try:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        with chemin.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entree, ensure_ascii=False) + "\n")
    except OSError as exc:
        raise IdeeError(f"ecriture de {chemin.name} impossible : {exc}") from exc


def etat(chemin: pathlib.Path | None = None) -> dict[str, dict]:
    """L'etat courant de chaque idee. Les lignes d'un meme id sont FUSIONNEES.

    Meme regle que le registre d'experiences : la derniere ligne fait foi champ par champ,
    pas ligne entiere. Une ligne de promotion ne porte que l'id d'experience ; l'ecrasement
    pur ferait disparaitre le texte de l'idee, c'est-a-dire tout son interet.
    """
    fusion: dict[str, dict] = {}
    for entree in _lignes(chemin):
        if "id" in entree:
            fusion[entree["id"]] = {**fusion.get(entree["id"], {}), **entree}
    return fusion


def _prochain_id(connues: dict[str, dict]) -> str:
    numeros = [int(i[1:]) for i in connues if i.startswith("I") and i[1:].isdigit()]
    return f"I{max(numeros, default=0) + 1}"


def ajouter(texte: str, *, source: str = "", pourquoi: str = "",
            chemin: pathlib.Path | None = None, **extra) -> dict:
    """Note une idee. Gratuit : le compteur d'essais NE BOUGE PAS.

    Aucune forme imposee — pas de metrique, pas de seuil, pas de MDE. Exiger la rigueur au
    moment de la capture reviendrait a n'attraper que les idees deja mures, et celles-la ne
    sont pas celles qu'on oublie.

    `source` et `pourquoi` sont facultatifs mais valent cher plus tard : dans trois mois,
    « d'ou venait cette idee » et « qu'est-ce qui me faisait y croire » sont exactement ce
    qu'on ne retrouve plus, et ce qui permet de juger si le preenregistrement etait de
    bonne foi.
    """
    chemin = chemin or REGISTRE
    texte = (texte or "").strip()
    if len(texte) < 10:
        raise IdeeError("une idee de moins de dix caracteres ne se relira pas")
    connues = etat(chemin)
    entree = {"id": _prochain_id(connues), "date": datetime.now(UTC).date().isoformat(),
              "etat": NOUVELLE, "texte": texte, "source": source, "pourquoi": pourquoi,
              **extra}
    _ajouter(entree, chemin)
    log.info("idee %s notee (le compteur d'essais reste a %s)",
             entree["id"], experiences.compteur())
    return entree


def lister(etat_voulu: str = "", chemin: pathlib.Path | None = None) -> list[dict]:
    """Les idees, les plus recentes d'abord. `etat_voulu` filtre sur nouvelle/promue/ecartee."""
    idees = sorted(etat(chemin).values(), key=lambda i: int(i["id"][1:]), reverse=True)
    return [i for i in idees if not etat_voulu or i.get("etat") == etat_voulu]


def ecarter(id_idee: str, motif: str, chemin: pathlib.Path | None = None) -> dict:
    """Ecarte une idee SANS l'effacer. Savoir ce qu'on a refusé de tester vaut un resultat."""
    chemin = chemin or REGISTRE
    if not (motif or "").strip():
        raise IdeeError("ecarter une idee sans motif la rend impossible a rouvrir")
    if id_idee not in etat(chemin):
        raise IdeeError(f"idee inconnue : {id_idee}")
    entree = {"id": id_idee, "date": datetime.now(UTC).date().isoformat(),
              "etat": ECARTEE, "motif": motif}
    _ajouter(entree, chemin)
    return entree


def promouvoir(id_idee: str, id_experience: str, hypothese: str, metrique_primaire: str,
               regle_de_decision: dict, *, chemin: pathlib.Path | None = None,
               **preenregistrement) -> dict:
    """Transforme une idee en experience preenregistree. **C'EST ICI que le compteur avance.**

    L'ordre des deux ecritures n'est pas indifferent : le preenregistrement d'abord, la
    trace dans les idees ensuite. Si `preenregistrer()` refuse — id deja pris, champ
    manquant — l'idee reste `nouvelle`, et rien ne prétend qu'elle a ete promue. L'inverse
    laisserait une idee marquee promue sans experience derriere, c'est-a-dire un mensonge
    dans le seul fichier ou l'on va chercher ce qui reste a faire.
    """
    chemin = chemin or REGISTRE
    idee = etat(chemin).get(id_idee)
    if idee is None:
        raise IdeeError(f"idee inconnue : {id_idee}")
    if idee.get("etat") == PROMUE:
        raise IdeeError(f"{id_idee} est deja promue en '{idee.get('id_experience')}' — "
                        "la promouvoir deux fois compterait deux essais pour une hypothese")

    avant = experiences.compteur()
    experience = experiences.preenregistrer(
        id_experience, hypothese, metrique_primaire, regle_de_decision,
        **preenregistrement)
    _ajouter({"id": id_idee, "date": datetime.now(UTC).date().isoformat(),
              "etat": PROMUE, "id_experience": id_experience}, chemin)
    apres = experiences.compteur()
    log.info("idee %s promue en %s — compteur d'essais %d -> %d",
             id_idee, id_experience, avant, apres)
    return {**idee, "etat": PROMUE, "id_experience": id_experience,
            "experience": experience, "compteur_avant": avant, "compteur_apres": apres}


def resume(chemin: pathlib.Path | None = None) -> dict:
    """De quoi afficher la boite sans la parcourir : combien, dans quel etat."""
    idees = lister(chemin=chemin)
    par_etat = {e: sum(1 for i in idees if i.get("etat") == e) for e in ETATS}
    return {"n": len(idees), **par_etat,
            "compteur_essais": experiences.compteur(),
            "note": "noter une idee est gratuit ; la promouvoir avance le compteur d'un cran"}
