"""Lance PBOR (PBO du passe : 3 lots de septembre, variantes de la voie C du 22/09).

    ARIT_HOME=/root/ARIT2.0 /root/venvs/beta/bin/python scripts/pbo_passe.py

A lancer seulement apres le preenregistrement commite (scripts/preenregistrer_pbor.py).
"""

from __future__ import annotations

import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta.pbo_passe import campagne  # noqa: E402


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s  "
                                                   "%(message)s")
    try:
        campagne.lancer()
    except campagne.PBOError as e:
        logging.getLogger("beta.pbo_passe").error("arret : %s", e)
        return 3
    logging.getLogger("beta.pbo_passe").info("termine : rapport dans pbo_passe/RAPPORT_PBO.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
