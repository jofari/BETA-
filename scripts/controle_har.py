"""Controle HAR (VC6 V1, phase 2) — test de mesure sans essai, en ligne de commande.

    /root/venvs/beta/bin/python scripts/controle_har.py --campagne    # la mesure figee
    /root/venvs/beta/bin/python scripts/controle_har.py --rapport     # rapport regenere
    /root/venvs/beta/bin/python scripts/controle_har.py --addendum    # sigma retenu -> spec

`--campagne` verifie le gel et les copies figees de l'etape A (SHA-256, cloture 1d = barre 5 min de
23:55), calcule la RV 5 min, l'ecart-type 30 jours et le HAR glissant de BTC, ETH et SOL, passe
l'epreuve de causalite, puis evalue les deux previsions en QLIKE et applique la regle 5. Il ecrit
VC6_V1/controle_har/RAPPORT_CONTROLE_HAR.md, son CSV et RESUME_DISCORD.md. Aucun run n'est
journalise. `--addendum` ajoute a VC6_V1/spec_figee.md l'addendum date « sigma retenu ».
"""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta.controle_har import campagne as ca  # noqa: E402
from beta.controle_har import donnees as dn  # noqa: E402
from beta.controle_har import rapport  # noqa: E402

log = logging.getLogger("beta.controle_har")


def _derniere_synthese() -> dict | None:
    fichiers = sorted(ca.DOSSIER.glob("campagne_*.json"), key=lambda f: f.stat().st_mtime)
    return json.loads(fichiers[-1].read_text(encoding="utf-8")) if fichiers else None


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--campagne", action="store_true")
    g.add_argument("--rapport", action="store_true")
    g.add_argument("--addendum", action="store_true")
    p.add_argument("--recalculer", action="store_true")
    args = p.parse_args(argv)
    if args.rapport or args.addendum:
        s = _derniere_synthese()
        if s is None:
            log.error("aucune campagne calculee : lancer --campagne")
            return 1
        if args.rapport:
            rapport.ecrire(s)
        else:
            rapport.ajouter_addendum(s)
        return 0
    try:
        s = ca.lancer(recalculer=args.recalculer)
    except (ca.ControleError, dn.DonneesError) as exc:
        log.error("ARRET : %s", exc)
        return 2
    for actif, a in s["actifs"].items():
        log.info("%s : QLIKE HAR %.4f, ecart-type 30 jours %.4f -> sigma = %s", actif,
                 a["qlike"]["har"], a["qlike"]["ecart_type"], a["sigma_retenu"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
