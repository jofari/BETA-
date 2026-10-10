"""Rafraichit les bougies 5 min des 6 paires dans le lake, avant une decision de session de VC4.

    ARIT_HOME=/root/ARIT2.0 /root/venvs/arit/bin/python scripts/rafraichir_5m.py

Sortie 1 si une paire n'a pas pu etre completee ou integree : la decision qui suit lirait un
lake en retard, et `c4_suivi.py` le verifie aussi de son cote (sortie 1).
"""

from __future__ import annotations

import logging
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta.lake import maj  # noqa: E402

log = logging.getLogger("beta.rafraichir_5m")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    debut = time.monotonic()
    problemes = maj.rafraichir_5m()
    for p in problemes:
        log.error("%s", p)
    log.info("bougies 5 min rafraichies en %.0f s (%d probleme(s))", time.monotonic() - debut,
             len(problemes))
    return 1 if problemes else 0


if __name__ == "__main__":
    sys.exit(main())
