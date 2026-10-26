"""Lance la campagne PBOC (PBO de la grille de la voie C) — apres le preenregistrement commite.

    ARIT_HOME=/root/ARIT2.0 /root/venvs/beta/bin/python scripts/pbo_voie_c.py
"""

from __future__ import annotations

import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta.pbo_voie_c import campagne  # noqa: E402


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s  "
                                                   "%(message)s")
    try:
        s = campagne.lancer()
    except campagne.PBOError as e:
        logging.getLogger("beta.pbo_voie_c").error("arret : %s", e)
        return 3
    logging.getLogger("beta.pbo_voie_c").info("termine : %s", s["arret"] if s["voie_c"] is None
                                              else f"verdict {s['verdict']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
