"""Le registre d'experiences : rien ne se mesure sans avoir ete ecrit ici AVANT.

Ce module n'est pas un utilitaire de journalisation. C'est un VERROU, et il est place au
plus bas de la pile a dessein : tout ce qui mesure en depend, donc rien ne peut le
contourner sans que ca se voie dans les imports.

Deux raisons, toutes deux mesurees plutot que supposees :

1. **Sans preenregistrement, un resultat post-hoc est indiscernable d'une hypothese
   confirmee.** On ne peut pas savoir, deux mois plus tard, si le seuil de decision a ete
   choisi avant ou apres avoir vu les chiffres. La p-value ne veut alors plus rien dire.
2. **Sans compteur cumulatif, aucune correction de tests multiples n'est possible.** N doit
   compter TOUS les essais, y compris ceux qu'on n'a jamais rapportes parce qu'ils etaient
   mauvais — c'est le fleau principal. Le compteur de BETA part de **30** : la dette deja
   consommee sur les memes 8,5 ans avant l'ouverture du registre (ARIT, campagnes de
   juillet 2026). Il n'est jamais remis a zero.

Format : JSONL append-only. On ne modifie jamais une ligne existante ; on en ajoute une
nouvelle avec le meme `id` et un statut mis a jour, et c'est la derniere qui fait foi.
"""

from __future__ import annotations

import json
import logging
import pathlib
from datetime import UTC, datetime

from beta import config

log = logging.getLogger("beta.protocole")

REGISTRE = config.RACINE / "EXPERIMENTS.jsonl"

# Dette consommee avant l'ouverture du registre : ~40 politiques comparees sur les memes
# 123 episodes cote ARIT (research/pistes_2026-07-31/RAPPORT.md §1.3). Aucune p-value
# calculee sur cette periode n'est interpretable telle quelle.
ESSAIS_INITIAUX = 30

CHAMPS_REQUIS = ("id", "hypothese", "metrique_primaire", "regle_de_decision",
                 "split_autorise")

STATUTS = ("preenregistre", "mesure", "clos", "abandonne")


class ProtocoleError(RuntimeError):
    """Preenregistrement absent, incomplet, ou registre illisible."""


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
            raise ProtocoleError(f"{chemin.name} ligne {n} illisible : {exc}") from exc
    return entrees


def etat(chemin: pathlib.Path | None = None) -> dict[str, dict]:
    """L'etat courant de chaque experience : les lignes d'un meme id sont FUSIONNEES.

    La derniere ligne fait foi champ par champ, pas ligne entiere. La difference n'est pas
    theorique : une ligne de cloture ne porte que le verdict, donc l'ecrasement pur ferait
    disparaitre l'hypothese et la regle de decision du dossier. `exiger()` refuserait alors
    de remesurer une experience deja close — c'est-a-dire qu'on ne pourrait plus jamais
    reproduire un resultat publie, ce qui est exactement le contraire du but.
    """
    fusion: dict[str, dict] = {}
    for entree in _lignes(chemin):
        if "id" in entree:
            fusion[entree["id"]] = {**fusion.get(entree["id"], {}), **entree}
    return fusion


def exiger(id_exp: str, chemin: pathlib.Path | None = None) -> dict:
    """Le verrou. Retourne le preenregistrement, ou refuse de laisser mesurer.

    A appeler en PREMIERE ligne de tout code qui produit un chiffre destine a decider
    quelque chose. Ce n'est pas une formalite administrative : c'est ce qui distingue une
    mesure d'une peche aux resultats.
    """
    chemin = chemin or REGISTRE
    entree = etat(chemin).get(id_exp)
    if entree is None:
        raise ProtocoleError(
            f"experience '{id_exp}' non preenregistree dans {chemin}.\n"
            "Ecrire l'hypothese, la metrique primaire et la regle de decision AVANT de "
            "mesurer — sinon le resultat n'est pas interpretable.")
    manquants = [c for c in CHAMPS_REQUIS if not entree.get(c)]
    if manquants:
        raise ProtocoleError(f"preenregistrement '{id_exp}' incomplet : {manquants}")
    return entree


def compteur(chemin: pathlib.Path | None = None) -> int:
    """Le nombre d'essais cumules, dette initiale comprise. Jamais remis a zero."""
    return ESSAIS_INITIAUX + len({e["id"] for e in _lignes(chemin) if "id" in e})


def preenregistrer(id_exp: str, hypothese: str, metrique_primaire: str,
                   regle_de_decision: dict, *, split_autorise: str = "train",
                   issue_attendue: str = "", mde_attendu: float | None = None,
                   famille_taille: int | None = None, deja_connu: str = "",
                   chemin: pathlib.Path | None = None, **extra) -> dict:
    """Ajoute une experience au registre. Refuse d'ecraser un id deja preenregistre.

    `deja_connu` n'est pas decoratif : c'est la ou l'on ecrit ce qu'on avait DEJA regarde au
    moment de preenregistrer. Un preenregistrement redige apres avoir vu les resultats et
    qui ne le dit pas est pire que pas de preenregistrement du tout.
    """
    chemin = chemin or REGISTRE
    existant = etat(chemin).get(id_exp)
    if existant and existant.get("statut") == "preenregistre":
        raise ProtocoleError(f"'{id_exp}' est deja preenregistre — ne pas le reecrire. "
                             "Pour le clore, utiliser clore().")
    entree = {"id": id_exp, "date": datetime.now(UTC).date().isoformat(),
              "statut": "preenregistre", "hypothese": hypothese,
              "metrique_primaire": metrique_primaire,
              "regle_de_decision": regle_de_decision, "split_autorise": split_autorise,
              "issue_attendue": issue_attendue, "mde_attendu": mde_attendu,
              "famille_taille": famille_taille, "deja_connu": deja_connu,
              "n_essais_cumules": compteur(chemin) + (0 if existant else 1), **extra}
    _ajouter(entree, chemin)
    log.info("experience '%s' preenregistree (essai cumule n° %s)",
             id_exp, entree["n_essais_cumules"])
    return entree


def amender(id_exp: str, raison: str, chemin: pathlib.Path | None = None,
            **champs) -> dict:
    """Modifie un preenregistrement AVANT mesure, en laissant la trace du changement.

    Un preenregistrement qu'on ne peut pas amender est un preenregistrement qu'on
    contourne : quand la donnee necessaire manque, la tentation est d'ecrire un protocole
    different et de ne rien dire. On prefere donc un amendement DATE, MOTIVE, et conserve a
    cote de l'original — la ligne d'origine reste dans le fichier, et la comparaison des
    deux est justement ce qui permet de juger si l'amendement etait de bonne foi.

    Refuse d'amender une experience deja close : a ce moment-la, ce n'est plus un
    amendement, c'est une reecriture du resultat.
    """
    chemin = chemin or REGISTRE
    dernier = etat(chemin).get(id_exp)
    if dernier and dernier.get("statut") in ("clos", "abandonne"):
        raise ProtocoleError(f"'{id_exp}' est {dernier['statut']} : on n'amende pas "
                             "un preenregistrement apres avoir vu le resultat")
    origine = exiger(id_exp, chemin)
    entree = {**origine, **champs, "id": id_exp,
              "date": datetime.now(UTC).date().isoformat(), "statut": "preenregistre",
              "amendement": raison,
              "amende_depuis": origine.get("date")}
    _ajouter(entree, chemin)
    log.info("experience '%s' amendee : %s", id_exp, raison)
    return entree


def clore(id_exp: str, verdict: str, resultat: str, *, statut: str = "clos",
          chemin: pathlib.Path | None = None, **extra) -> dict:
    """Ferme une experience. Le preenregistrement d'origine reste dans le fichier."""
    chemin = chemin or REGISTRE
    if statut not in STATUTS:
        raise ProtocoleError(f"statut inconnu : {statut} (connus : {STATUTS})")
    origine = exiger(id_exp, chemin)
    entree = {"id": id_exp, "date": datetime.now(UTC).date().isoformat(), "statut": statut,
              "verdict": verdict, "resultat": resultat,
              "conforme_a_l_issue_attendue": verdict == origine.get("issue_attendue"),
              "n_essais_cumules": origine.get("n_essais_cumules"), **extra}
    _ajouter(entree, chemin)
    log.info("experience '%s' close : %s", id_exp, verdict)
    return entree


def _ajouter(entree: dict, chemin: pathlib.Path) -> None:
    try:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        with chemin.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entree, ensure_ascii=False) + "\n")
    except OSError as exc:
        raise ProtocoleError(f"ecriture du registre impossible : {exc}") from exc
