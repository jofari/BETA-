"""Qui est cette candidate ? Le titre lisible d'un run, et de quoi il vient.

Le dashboard affichait `auto_r7_03`. C'est un nom de FICHIER : il dit d'ou vient le code,
pas ce que la regle fait. Comparer six candidates a l'ecran en lisant six identifiants
oblige a rouvrir six fichiers, et c'est precisement au moment de la comparaison qu'on ne
peut pas se le permettre.

Trois sources, dans cet ordre, et la source est TOUJOURS rendue avec le titre :

    verdict    le run porte son titre (mesure posterieure au 21/08) — la seule fiable
    registre   le fichier de la candidate existe encore et declare un titre
    aucune     ni l'un ni l'autre : on rend le module embelli, marque comme reconstitue

L'ordre n'est pas negociable. Un verdict est une mesure datee ; le code d'une candidate,
lui, peut avoir ete reecrit depuis. Preferer le registre reviendrait a changer
retroactivement le titre d'un resultat deja rendu — la meme classe de mensonge qu'un
tableau de bord qui comble ses trous.

La derniere source ne fabrique rien : elle remet des espaces la ou il y a des tirets bas et
le dit. Un titre reconstitue s'affiche comme reconstitue.
"""

from __future__ import annotations

import logging
import re
import time

log = logging.getLogger("beta.rapport.identite")

VERDICT, REGISTRE, AUCUNE = "verdict", "registre", "aucune"

# Prefixe pose par la boucle d'auto-recherche (`beta.recherche.auto.PREFIXE`), suivi de l'id
# d'hypothese et du rang : `auto_r7_03`. Il n'apporte rien a la lecture d'un titre — d'ou il
# vient est deja dit ailleurs — mais il ne doit pas etre PERDU, seulement deplace.
MOTIF_AUTO = re.compile(r"^auto_([a-z]+\d*)_(\d+)$")


def _embellir(module: str) -> str:
    """Le module rendu lisible, sans rien inventer sur ce que la regle fait."""
    trouve = MOTIF_AUTO.match(module or "")
    if trouve:
        return f"Variante {int(trouve.group(2))} de {trouve.group(1).upper()}"
    return (module or "candidate sans nom").replace("_", " ").strip().capitalize()


# Le registre IMPORTE chaque candidate pour l'inventorier. La liste des runs le consulte une
# fois par run : sans cache, afficher vingt runs relit et reimporte vingt fois les memes
# fichiers. Le cache est volontairement tres court — l'atelier depose une candidate et
# s'attend a la voir apparaitre — et ne sert donc qu'a couvrir UN chargement de page.
_TTL_CACHE = 3.0
_cache: tuple[float, list[dict]] = (0.0, [])


def _inventaire() -> list[dict]:
    """L'inventaire du registre, memorise quelques secondes. Ne leve jamais."""
    global _cache
    fige, lignes = _cache
    if time.monotonic() - fige < _TTL_CACHE:
        return lignes
    try:
        from beta.moteur import registre
        lignes = registre.inventaire()
    except Exception as exc:                          # noqa: BLE001 - decor, jamais fatal
        log.debug("registre illisible (%s)", exc)
        lignes = []
    _cache = (time.monotonic(), lignes)
    return lignes


def _du_registre(nom: str) -> dict:
    """Cherche la candidate dans `beta/candidates/`, par module OU par nom declare.

    Les deux clefs sont necessaires, et elles ne coincident pas toujours : la boucle
    automatique nomme la candidate comme son module (`auto_r7_03`), une candidate ecrite a
    la main non — `mean_reversion_z` vit dans `r2_mean_reversion.py`. Le verdict, lui, ne
    garde que le NOM. C'est pour cette raison que la resolution passe toujours par le
    registre, meme quand le titre vient du verdict : sans elle, on chercherait le code d'une
    candidate dans un fichier qui n'existe pas.
    """
    for ligne in _inventaire():
        if nom in (ligne.get("module"), ligne.get("nom")):
            return ligne
    return {}


def resoudre(verdict: dict) -> dict:
    """L'identite affichable d'un run. Ne leve jamais.

    Rend `module` (l'identifiant technique, qui reste affiche a cote du titre — il sert a
    retrouver le fichier), `titre`, `description`, et `source` parmi VERDICT/REGISTRE/AUCUNE.
    """
    verdict = verdict or {}
    nom = str(verdict.get("candidate") or "")

    # Toujours, meme quand le verdict se suffit : c'est le registre qui sait dans QUEL
    # fichier vit cette candidate, et le verdict ne porte que son nom.
    ligne = _du_registre(nom)
    module = str(ligne.get("module") or nom)
    description = (str(verdict.get("description") or "").strip()
                   or str(ligne.get("description") or "").strip())

    titre = str(verdict.get("titre") or "").strip()
    if titre and titre != nom:
        return {"module": module, "titre": titre, "description": description,
                "source": VERDICT}

    titre_registre = str(ligne.get("titre") or "").strip()
    if titre_registre and titre_registre not in (nom, module):
        return {"module": module, "titre": titre_registre, "description": description,
                "source": REGISTRE}

    return {"module": module, "titre": _embellir(nom), "description": description,
            "source": AUCUNE}
