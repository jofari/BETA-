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
import logging
import pkgutil

from beta.moteur.contrats import Candidate, ContratError

log = logging.getLogger("beta.moteur.registre")

PAQUET = "beta.candidates"
FABRIQUE = "creer"


def _modules() -> list[str]:
    paquet = importlib.import_module(PAQUET)
    return sorted(m.name for m in pkgutil.iter_modules(paquet.__path__)
                  if not m.name.startswith("_"))


def charger(nom_module: str) -> Candidate:
    """Instancie UNE candidate. Les erreurs remontent : une candidate cassee doit se voir."""
    module = importlib.import_module(f"{PAQUET}.{nom_module}")
    fabrique = getattr(module, FABRIQUE, None)
    if fabrique is None:
        raise ContratError(f"{PAQUET}.{nom_module} n'expose pas de fonction {FABRIQUE}()")
    candidate = fabrique()
    if not isinstance(candidate, Candidate):
        raise ContratError(f"{nom_module}.{FABRIQUE}() rend {type(candidate).__name__}, "
                           "pas un Candidate")
    return candidate


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


def par_hypothese(id_experience: str) -> dict[str, Candidate]:
    """Les candidates rattachees a une hypothese preenregistree donnee (R1, R2, ...)."""
    return {nom: c for nom, c in toutes().items() if c.hypothese == id_experience}


def inventaire() -> list[dict]:
    """De quoi afficher le registre sans instancier de run."""
    return [{"module": nom, "nom": c.nom, "hypothese": c.hypothese,
             "empreinte": c.empreinte, "parametres": c.parametres,
             "description": c.description}
            for nom, c in sorted(toutes().items())]
