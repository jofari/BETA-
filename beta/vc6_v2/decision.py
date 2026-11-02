"""VC6 V2 : les regles de decision 1 et 2 de la spec (la regle 3 ne decide rien)."""

from __future__ import annotations

from beta.vc6_v2 import regles as R

AUCUNE = ("VC6 rejetée, aucune configuration retenue ; le paper ne sert qu'à roder "
          "l'exécution")


class DecisionError(RuntimeError):
    """Cas que la spec ne prevoit pas : arret."""


def utile(ulcer: float, ulcer_temoin: float, p_retenue: float | None) -> bool:
    """Regle 1 : Ulcer < celui de son temoin, avec p retenue < 0,05."""
    return bool(ulcer < ulcer_temoin and p_retenue is not None and p_retenue < R.SEUIL_P)


def configuration_retenue(essais: dict[str, dict]) -> dict:
    """Regle 2. `essais[cle]` = {"utile": bool, "ratio": rendement annualise / Ulcer}."""
    utiles = [k for k, v in essais.items() if v["utile"]]
    if not utiles:
        return {"retenue": None, "utiles": [], "conclusion": AUCUNE}
    if len(utiles) == 1:
        return {"retenue": utiles[0], "utiles": utiles,
                "conclusion": f"un seul essai utile : {R.ESSAIS[utiles[0]]['nom']}"}
    ratios = {k: essais[k]["ratio"] for k in utiles}
    meilleur = max(ratios.values())
    gagnants = [k for k, v in ratios.items() if v == meilleur]
    if len(gagnants) != 1:
        raise DecisionError(f"ratios rendement / Ulcer egaux : {ratios} (cas non prevu)")
    return {"retenue": gagnants[0], "utiles": utiles,
            "conclusion": f"les deux sont utiles : {R.ESSAIS[gagnants[0]]['nom']} a le ratio "
                          "rendement annualisé / Ulcer le plus haut"}
