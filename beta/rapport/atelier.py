"""L'atelier vu du dashboard : quatre gestes, une liste blanche, aucune commande.

Meme garde-fou que `actions.py` : le client envoie un NOM de geste pris dans `GESTES` et
des donnees, jamais une commande a executer. Le serveur decide de tout le reste.

Une nuance a ne pas maquiller, en revanche : ici le client envoie **du code Python**, qui
finira importe. Ce n'est pas une entorse au garde-fou, c'est le meme niveau de confiance
que celui deja accorde a l'outil MCP `beta_submit_strategy` — et que celui, plus simple
encore, d'ouvrir `beta/candidates/` dans un editeur. Ce qui compte est donc ailleurs :

1. le serveur n'ecoute que sur **127.0.0.1** ;
2. rien n'est importe dans le processus du dashboard — l'epreuve tourne dans un
   **sous-processus avec chronometre**, donc une candidate qui boucle ne gele pas BETA ;
3. rien n'est ecrit dans `beta/candidates/` avant que le sas ET l'epreuve aient passe.

Le geste `generer` peut prendre plusieurs minutes : un modele de 7 milliards de parametres
sur un portable ecrit une candidate en une a trois minutes, et la boucle de reparation en
demande jusqu'a `essais` fois. La requete est donc longue par nature, et l'interface le dit
plutot que de faire semblant.
"""

from __future__ import annotations

import logging

from beta.atelier import depot, gabarit, local
from beta.moteur import registre

log = logging.getLogger("beta.rapport.atelier")

GESTES = ("gabarit", "valider", "deposer", "generer")

# Un fichier de candidate depasse rarement 100 lignes ; au-dela, ce n'est plus une regle
# nue, c'est un programme — et ce n'est plus ce que le banc sait mesurer honnetement.
MAX_CODE = 40_000
MAX_ESSAIS = 5


class AtelierError(RuntimeError):
    """Geste refuse, ou donnees inexploitables."""


def inventaire() -> dict:
    """De quoi peupler l'onglet sans rien executer."""
    candidates = []
    for ligne in registre.inventaire():
        chemin = depot.chemin(ligne["module"])
        candidates.append({**ligne, "existe": chemin.exists()})
    return {"candidates": candidates, "modeles": local.disponibles(),
            "max_essais": MAX_ESSAIS}


def code_de(module: str) -> dict:
    depot.verifier_nom(module)
    chemin = depot.chemin(module)
    if not chemin.exists():
        raise AtelierError(f"{module}.py introuvable")
    try:
        return {"module": module, "code": chemin.read_text(encoding="utf-8")}
    except OSError as exc:
        raise AtelierError(f"lecture impossible : {exc}") from exc


def _code(charge: dict) -> str:
    code = str(charge.get("code") or "")
    if len(code) > MAX_CODE:
        raise AtelierError(f"code trop long ({len(code)} caracteres, maximum {MAX_CODE}) — "
                           "une candidate est une regle nue, pas un programme")
    return code


def executer(geste: str, charge: dict) -> dict:
    """Le seul point d'entree. Ne leve que des AtelierError et des DepotError."""
    if geste not in GESTES:
        raise AtelierError(f"geste refuse : {geste}")
    module = str(charge.get("module") or "")
    depot.verifier_nom(module)

    if geste == "gabarit":
        return {"ok": True, "module": module,
                "code": gabarit.ecrire(module, str(charge.get("hypothese") or "R?"),
                                       nom=str(charge.get("nom") or ""),
                                       intention=str(charge.get("intention") or ""))}

    if geste == "valider":
        return depot.valider(_code(charge), module)

    if geste == "deposer":
        return depot.deposer(_code(charge), module, ecraser=bool(charge.get("ecraser")))

    intention = str(charge.get("intention") or "").strip()
    if not intention:
        raise AtelierError("dire ce que la candidate doit faire, en une ou deux phrases")
    try:
        essais = max(1, min(MAX_ESSAIS, int(charge.get("essais") or 3)))
    except (TypeError, ValueError):
        essais = 3
    log.info("generation locale de '%s' (%d essais au plus)", module, essais)
    try:
        return local.ecrire_candidate(
            intention, module, str(charge.get("hypothese") or ""),
            backend=str(charge.get("backend") or "auto"),
            modele=str(charge.get("modele") or ""), essais=essais)
    except local.LocalError as exc:
        raise AtelierError(str(exc)) from exc
