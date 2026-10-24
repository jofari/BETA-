"""T1F — fiabilite du test de justesse (diagnostic, aucun essai), en ligne de commande.

    /root/venvs/beta/bin/python scripts/temps1_fiabilite.py --campagne    # la mesure figee
    /root/venvs/beta/bin/python scripts/temps1_fiabilite.py --rapport     # rapport regenere

`--campagne` verifie les modules de T1J (commit 8afdbe7), le gel, les donnees et les mesures
observees de T1J, tire 1 000 signaux aleatoires par couple et par test (graine 0), puis ecrit
temps1_fiabilite/RAPPORT_FIABILITE.md, ses CSV et RESUME_DISCORD.md. Aucun run n'est journalise.
"""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta.temps1_fiabilite import campagne as ca  # noqa: E402
from beta.temps1_fiabilite import rapport  # noqa: E402

log = logging.getLogger("beta.temps1_fiabilite")


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--campagne", action="store_true")
    g.add_argument("--rapport", action="store_true")
    p.add_argument("--recalculer", action="store_true")
    args = p.parse_args(argv)
    if args.rapport:
        fichiers = sorted(ca.DOSSIER.glob("campagne_T1F_*.json"), key=lambda f: f.stat().st_mtime)
        if not fichiers:
            log.error("aucune campagne calculee : lancer --campagne")
            return 1
        rapport.ecrire(json.loads(fichiers[-1].read_text(encoding="utf-8")))
        return 0
    try:
        s = ca.lancer(recalculer=args.recalculer)
    except ca.FiabiliteError as exc:
        log.error("ARRET : %s", exc)
        return 2
    for x, v in s["verdict"].items():
        log.info("%s : %s (p temoin %.3f, or %.3f)", x, v["verdict"], v["p_temoin"], v["p_or"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
