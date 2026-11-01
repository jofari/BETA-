"""T1C — complement ETH et SOL du Temps 1 (diagnostic, aucun essai), en ligne de commande.

    /root/venvs/beta/bin/python scripts/temps1_complement.py --campagne    # la mesure figee
    /root/venvs/beta/bin/python scripts/temps1_complement.py --rapport     # rapport regenere

`--campagne` verifie les modules de T1J (8afdbe7) et de T1F (590688e), le gel, sigma_SP_ref et les
copies figees de l'etape A, puis juge la SMA 200 d'ETH et de SOL et tire 1 000 signaux aleatoires
par actif et par test (graine 0). Il ecrit VC6_V1/temps1_complement_eth_sol/RAPPORT_COMPLEMENT.md,
ses CSV et RESUME_DISCORD.md. Aucun run n'est journalise. Sortie 3 si un actif est indecidable.
"""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta.temps1_complement import campagne as ca  # noqa: E402
from beta.temps1_complement import donnees as dc  # noqa: E402
from beta.temps1_complement import rapport  # noqa: E402

log = logging.getLogger("beta.temps1_complement")


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--campagne", action="store_true")
    g.add_argument("--rapport", action="store_true")
    p.add_argument("--recalculer", action="store_true")
    args = p.parse_args(argv)
    if args.rapport:
        fichiers = sorted(ca.DOSSIER.glob("campagne_T1C_*.json"), key=lambda f: f.stat().st_mtime)
        if not fichiers:
            log.error("aucune campagne calculee : lancer --campagne")
            return 1
        rapport.ecrire(json.loads(fichiers[-1].read_text(encoding="utf-8")))
        return 0
    try:
        s = ca.lancer(recalculer=args.recalculer)
    except (ca.ComplementError, dc.DonneesError) as exc:
        log.error("ARRET : %s", exc)
        return 2
    for actif, a in s["actifs"].items():
        p_j = (a.get("test_1") or {}).get("p_justesse")
        log.info("%s : %s (p_justesse test 1 : %s)", actif, a["statut"], p_j)
    return 3 if any(a["statut"] == ca.INDECIDABLE for a in s["actifs"].values()) else 0


if __name__ == "__main__":
    sys.exit(main())
