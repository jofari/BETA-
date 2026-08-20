"""Le registre des candidates : une par fichier, aucune ne touchant au moteur.

Une candidate est un fichier de `beta/candidates/` qui expose une fonction `creer()` rendant
un `contrats.Candidate`. Rien d'autre. Le registre les decouvre par import, sans qu'aucune
liste centrale ne soit a tenir a jour.

Pourquoi l'isolement par fichier plutot qu'un module commun : une candidate est du code
jetable, ecrit vite, souvent faux. Si elles partagent un fichier, corriger la n° 12 fait
taire ou reveiller la n° 3 sans qu'on le sache, et les verdicts deja rendus deviennent des
mensonges. Un fichier par candidate rend la regression IMPOSSIBLE plutot qu'improbable.

L'empreinte de code (`Candidate.empreinte`) ferme la boucle : si le fichier change, le run
change d'identifiant, et l'ancien verdict ne peut plus etre confondu avec le nouveau.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import pathlib
import pkgutil
import sys

from beta.moteur.contrats import Candidate, ContratError

log = logging.getLogger("beta.moteur.registre")

PAQUET = "beta.candidates"
FABRIQUE = "creer"


def _modules() -> list[str]:
    paquet = importlib.import_module(PAQUET)
    return sorted(m.name for m in pkgutil.iter_modules(paquet.__path__)
                  if not m.name.startswith("_"))


def charger(nom_module: str) -> Candidate:
    """Instancie UNE candidate. Les erreurs remontent : une candidate cassee doit se voir.

    Le fichier est relu du disque a chaque appel, et ce n'est pas une precaution de style.
    L'atelier ecrit une candidate puis la crible dans la meme seconde, et deux caches de
    l'importeur mentent alors dans le meme sens :

        - un fichier fraichement pose n'existe pas encore pour le `FileFinder` du paquet,
          donc `import_module` leve `ModuleNotFoundError` sur une candidate bien presente ;
        - un module deja importe reste en memoire avec son ANCIEN code apres un depot
          `--ecraser`, donc le criblage mesurerait la version precedente en croyant mesurer
          la nouvelle — et l'empreinte publiee serait celle du code qui n'a pas tourne.

    Le second cas est le dangereux : il ne plante pas, il produit un verdict faux et
    signe. Cf. `beta/recherche/auto.py`, ou `ecraser=True` est le defaut.

    Le `.pyc` est supprime avant chaque chargement, et ce n'est pas de la ceinture et
    bretelles. Le cache de bytecode valide une entree sur (mtime en SECONDES, taille en
    octets) de la source : deux versions d'une candidate ecrites dans la meme seconde et
    de meme longueur — deux variantes generees a la chaine, exactement le cas de l'atelier
    — sont indiscernables pour lui, et l'ancien bytecode est reutilise. Un `reload` seul
    n'y change rien, et le piege survit meme a un redemarrage du processus.
    """
    chemin_module = f"{PAQUET}.{nom_module}"
    importlib.invalidate_caches()
    _oublier_le_bytecode(nom_module)
    deja = sys.modules.get(chemin_module)
    module = importlib.reload(deja) if deja else importlib.import_module(chemin_module)
    fabrique = getattr(module, FABRIQUE, None)
    if fabrique is None:
        raise ContratError(f"{PAQUET}.{nom_module} n'expose pas de fonction {FABRIQUE}()")
    candidate = fabrique()
    if not isinstance(candidate, Candidate):
        raise ContratError(f"{nom_module}.{FABRIQUE}() rend {type(candidate).__name__}, "
                           "pas un Candidate")
    return candidate


def _oublier_le_bytecode(nom_module: str) -> None:
    """Retire le .pyc d'une candidate. Silencieux : c'est un cache, pas une donnee."""
    try:
        paquet = importlib.import_module(PAQUET)
        source = pathlib.Path(paquet.__path__[0]) / f"{nom_module}.py"
        pathlib.Path(importlib.util.cache_from_source(str(source))).unlink(missing_ok=True)
    except (OSError, ImportError, IndexError, ValueError) as exc:
        log.debug("bytecode de '%s' non retire : %s", nom_module, exc)


def toutes() -> dict[str, Candidate]:
    """Toutes les candidates chargeables. Une candidate cassee est signalee, pas fatale.

    Le criblage doit pouvoir tourner la nuit sur 40 candidates sans qu'une faute de frappe
    dans la 7e annule les 33 autres. Mais l'echec est journalise en ERROR : il ne disparait
    pas, il ne bloque simplement pas les autres.
    """
    trouvees: dict[str, Candidate] = {}
    for nom in _modules():
        try:
            trouvees[nom] = charger(nom)
        except Exception as exc:                      # noqa: BLE001 - on isole, on journalise
            log.error("candidate '%s' illisible : %s", nom, exc)
    return trouvees


def inventaire() -> list[dict]:
    """De quoi afficher le registre sans instancier de run."""
    return [{"module": nom, "nom": c.nom, "hypothese": c.hypothese,
             "empreinte": c.empreinte, "parametres": c.parametres,
             "description": c.description}
            for nom, c in sorted(toutes().items())]
