"""VC6 V1, Temps 2 : lance la campagne et ecrit le rapport (prompt de Jonas du 02/11/2026).

    /root/venvs/beta/bin/python scripts/vc6_temps2.py            # campagne + rapport
    /root/venvs/beta/bin/python scripts/vc6_temps2.py --rapport  # rapport depuis le dernier resultat

Les resultats bruts vont dans data/vc6_temps2/resultats.pkl (jetable, se recalcule a l'identique) ;
le rapport dans VC6_V1/rapport_temps2.md. Le registre est marque « mesure » (5 essais deja comptes).
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import pathlib
import pickle
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta.protocole import experiences  # noqa: E402
from beta.vc6 import campagne, regles as R  # noqa: E402

log = logging.getLogger("beta.vc6_temps2")
PKL = campagne.DOSSIER / "resultats.pkl"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s  %(message)s")
    a = argparse.ArgumentParser()
    a.add_argument("--rapport", action="store_true")
    args = a.parse_args()
    if not args.rapport:
        res = campagne.executer()
        campagne.DOSSIER.mkdir(parents=True, exist_ok=True)
        PKL.write_bytes(pickle.dumps(res))
        for cle, v in R.VARIANTES.items():
            rid = hashlib.sha256(f"{R.ID_EXP}:{cle}:{R.empreinte()}".encode()).hexdigest()[:12]
            experiences.marquer_mesuree(R.ID_EXP, rid, f"mesure {cle}")
        log.info("resultats ecrits : %s", PKL)
    from beta.vc6 import rapport
    res = pickle.loads(PKL.read_bytes())
    chemin = rapport.ecrire(res)
    log.info("rapport : %s", chemin)
    return 0


if __name__ == "__main__":
    sys.exit(main())
