"""T1J — test de justesse des detecteurs de regime, en ligne de commande.

    /root/venvs/beta/bin/python scripts/temps1_justesse.py --compteur    # detail, rien n'est ecrit
    /root/venvs/beta/bin/python scripts/temps1_justesse.py --campagne    # la mesure preenregistree
    /root/venvs/beta/bin/python scripts/temps1_justesse.py --rapport     # rapport regenere

`--campagne` verifie le gel (regles et clarifications), affiche le detail du compteur, journalise
les 16 essais du verdict AVANT tout calcul, passe l'epreuve de causalite, calcule, puis ecrit
temps1_justesse/RAPPORT_JUSTESSE.md (clarifications recopiees en tete), ses CSV et
RESUME_DISCORD.md. Relancer sur les memes donnees ne recalcule ni ne recompte rien.
"""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta.temps1_justesse import campagne as ca  # noqa: E402
from beta.temps1_justesse import donnees as dn  # noqa: E402
from beta.temps1_justesse import rapport  # noqa: E402

log = logging.getLogger("beta.temps1_justesse")


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--compteur", action="store_true")
    g.add_argument("--campagne", action="store_true")
    g.add_argument("--rapport", action="store_true")
    p.add_argument("--recalculer", action="store_true",
                   help="refaire le calcul sur les memes donnees (sans recompter)")
    args = p.parse_args(argv)
    if args.compteur:
        ca.verifier_gel()
        d = dn.charger()
        for ligne in ca.lignes_detail(ca.detail_compteur(d.empreinte)):
            print(ligne)
        return 0
    if args.rapport:
        fichiers = sorted(ca.DOSSIER.glob(f"campagne_{ca.ID_EXP}_*.json"),
                          key=lambda f: f.stat().st_mtime)
        if not fichiers:
            log.error("aucune campagne calculee : lancer --campagne")
            return 1
        rapport.ecrire(json.loads(fichiers[-1].read_text(encoding="utf-8")))
        return 0
    s = ca.lancer(recalculer=args.recalculer)
    res = s["resultats"]
    if res is None:
        log.error("epreuve de causalite echouee : rapport d'arret ecrit")
        return 3
    if res["verdict"] is None:
        log.error("INDECIDABLE : %s", "; ".join(res["indecidable"]))
        return 2
    log.info("verdict : %s ; solide : %s", res["verdict"]["statut"], res["solide"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
