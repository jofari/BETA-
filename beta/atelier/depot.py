"""Deposer une candidate : le chemin unique entre un bout de code et `beta/candidates/`.

CLI, dashboard et modele local passent tous par ici. Un second chemin de depot serait un
second endroit ou oublier le sas — et il suffit d'un oubli pour qu'une candidate qui lit le
futur produise un verdict que plus rien ne distingue d'un vrai.

Le point de conception : **la validation tourne sur un fichier temporaire**, jamais sur la
cible. Ecrire d'abord et valider ensuite — ce que fait `beta_submit_strategy` en MCP —
detruit la candidate en place quand la nouvelle est mauvaise. Ici, `r7_breakout.py` n'est
touche que si le remplacant a passe le sas ET l'epreuve.

Le nom temporaire commence par `_` : `registre.toutes()` ignore ces modules, donc un essai
oublie apres un plantage n'entre jamais dans un criblage.
"""

from __future__ import annotations

import logging
import re

from beta import config
from beta.atelier import epreuve, sas

log = logging.getLogger("beta.atelier.depot")

DOSSIER = config.RACINE / "beta" / "candidates"
PREFIXE_ESSAI = "_essai_"

# Meme motif que `beta_submit_strategy` : le nom devient un module Python et un nom de
# fichier, deux endroits ou une fantaisie coute cher.
NOM_VALIDE = re.compile(r"[a-z][a-z0-9_]{2,48}")


class DepotError(RuntimeError):
    """Nom refuse, fichier deja present, ou ecriture impossible."""


def chemin(module: str):
    return DOSSIER / f"{module}.py"


def verifier_nom(module: str) -> None:
    if not NOM_VALIDE.fullmatch(module):
        raise DepotError(f"nom de module invalide : '{module}' — minuscules, chiffres et "
                         "souligne, de 3 a 49 caracteres")


def valider(code: str, module: str, timeout: int = epreuve.TIMEOUT_S) -> dict:
    """Sas statique puis epreuve dynamique, sur une copie temporaire. N'ecrit pas la cible.

    Rend un rapport unique : `{ok, refus, reserves, mesures, sas, epreuve}`. Les refus des
    deux etages sont fusionnes parce que l'appelant n'a aucune raison de savoir lequel a
    parle — ce qui l'interesse, c'est ce qu'il doit corriger.
    """
    verifier_nom(module)
    rapport_sas = sas.controler(code, module)
    if not rapport_sas.ok:
        # On n'ecrit rien : le sas existe precisement pour ne pas avoir a importer ca.
        return {"module": module, "ok": False, "refus": list(rapport_sas.refus),
                "reserves": list(rapport_sas.reserves), "mesures": rapport_sas.mesures,
                "sas": rapport_sas.dict(), "epreuve": None}

    essai = f"{PREFIXE_ESSAI}{module}"
    cible = chemin(essai)
    try:
        DOSSIER.mkdir(parents=True, exist_ok=True)
        cible.write_text(code, encoding="utf-8")
        rapport_epreuve = epreuve.lancer(essai, timeout=timeout)
    except OSError as exc:
        raise DepotError(f"ecriture de l'essai impossible : {exc}") from exc
    finally:
        cible.unlink(missing_ok=True)

    refus = list(rapport_sas.refus) + list(rapport_epreuve.get("refus") or [])
    reserves = list(rapport_sas.reserves) + list(rapport_epreuve.get("reserves") or [])
    reserves += reserves_de_protocole(code)
    return {"module": module, "ok": not refus, "refus": refus, "reserves": reserves,
            "mesures": rapport_epreuve.get("mesures") or {},
            "sas": rapport_sas.dict(), "epreuve": rapport_epreuve}


def reserves_de_protocole(code: str) -> list[str]:
    """Prevenir tot qu'une hypothese n'est pas preenregistree — sans en faire un verrou.

    Le verrou materiel est ailleurs, dans `contrats.Run`, et il refusera de MESURER. Le
    doubler ici empecherait d'ecrire une candidate avant d'avoir redige son
    preenregistrement, ce qui n'est pas l'interdit : l'interdit porte sur la mesure.
    """
    from beta.protocole import experiences

    id_exp = sas.hypothese_du_code(code)
    if not id_exp:
        return ["hypothese illisible dans creer() — le run la reclamera"]
    try:
        connues = experiences.etat()
    except experiences.ProtocoleError as exc:
        return [f"registre d'experiences illisible : {exc}"]
    if id_exp not in connues:
        return [f"'{id_exp}' n'est PAS preenregistree : la candidate se depose, mais "
                "aucun run ne tournera dessus tant que l'hypothese n'est pas ecrite "
                "(`beta_register_edge`, ou scripts/preenregistrer.py)"]
    return []


def deposer(code: str, module: str, ecraser: bool = False,
            timeout: int = epreuve.TIMEOUT_S) -> dict:
    """Valide puis pose le fichier. Rien n'est ecrit si la validation refuse."""
    verifier_nom(module)
    cible = chemin(module)
    if cible.exists() and not ecraser:
        raise DepotError(
            f"{module}.py existe deja. `--ecraser` pour le remplacer, en sachant que "
            "l'empreinte de la candidate changera : les verdicts deja rendus ne "
            "s'appliqueront plus a la nouvelle version, et c'est voulu.")

    rapport = valider(code, module, timeout=timeout)
    if not rapport["ok"]:
        rapport["depose"] = False
        return rapport

    try:
        cible.write_text(code, encoding="utf-8")
    except OSError as exc:
        raise DepotError(f"ecriture de {cible} impossible : {exc}") from exc
    log.info("candidate '%s' deposee (%s)", module, cible)
    return {**rapport, "depose": True, "chemin": str(cible)}


def nettoyer_essais() -> int:
    """Retire les essais oublies par un plantage. Rend le nombre de fichiers supprimes."""
    n = 0
    for fichier in DOSSIER.glob(f"{PREFIXE_ESSAI}*.py"):
        fichier.unlink(missing_ok=True)
        n += 1
    return n
