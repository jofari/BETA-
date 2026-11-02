"""VC6 V2 : tests de coherence du moteur (etape C du prompt de Jonas du 02/11/2026).

    /root/venvs/beta/bin/python scripts/vc6_v2.py --coherence

Verifie le gel (preenregistrement, regles, texte, spec), lance les 4 tests (arret au premier qui
rate), ecrit data/vc6_v2/coherence.json et VC6_V2/coherence.md. Aucun run d'essai : les runs
attendent le GO de Jonas (deuxieme prompt). Sortie 1 si un test rate.
"""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta import config  # noqa: E402
from beta.protocole import experiences  # noqa: E402
from beta.vc6_v2 import coherence, gel, rapport  # noqa: E402
from beta.vc6_v2 import regles as R  # noqa: E402

log = logging.getLogger("beta.vc6_v2")
DOSSIER = config.DATA / "vc6_v2"


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s  %(message)s")
    a = argparse.ArgumentParser()
    a.add_argument("--coherence", action="store_true", help="les 4 tests de coherence")
    args = a.parse_args()
    if not args.coherence:
        log.error("seule l'option --coherence existe : les runs des essais attendent le GO de "
                  "Jonas")
        return 2
    gel.verifier()
    res = coherence.tous()
    compteurs = {"invest": experiences.compteur(famille="invest"),
                 "trading": experiences.compteur(), "global": experiences.compteur_total()}
    DOSSIER.mkdir(parents=True, exist_ok=True)
    (DOSSIER / "coherence.json").write_text(
        json.dumps({"resultats": res, "compteurs": compteurs, "regles": R.empreinte()},
                   indent=1, default=str), encoding="utf-8")
    chemin = rapport.ecrire_coherence(res, compteurs, R.empreinte())
    log.info("tests de coherence : %s ; rapport %s",
             "les 4 passent" if res["passe"] else f"ARRET au test {res.get('arret')}", chemin)
    return 0 if res["passe"] else 1


if __name__ == "__main__":
    sys.exit(main())
