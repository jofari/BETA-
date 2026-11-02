"""« Paper de plomberie – VC6 V2 poche baissiere sous HAR » : le rejeu hebdomadaire du backtest.

    ARIT_HOME=/root/ARIT2.0 /root/venvs/beta/bin/python scripts/vc6_rejeu.py
        [--journal CHEMIN] [--repertoire DOSSIER] [--date AAAA-MM-JJ]

Chaque semaine (timer beta-vc6-rejeu) : rejoue le backtest sur les jours d'execution des 7 derniers
jours, explique tout ecart d'exposition de plus de 5 points, controle que le lake vivant redonne le
backtest fige, et ajoute une ligne a PAPER_VC6_REJEU.jsonl (`beta.vc6_v2.rejeu`).

Sortie non nulle = unite « failed » (alerte Discord) :
    2  gel rompu
    4  ecart non explique, backtest fige non reproduit, ou jour absent du journal (ligne ecrite)
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from beta.vc6_v2 import paper as pp  # noqa: E402
from beta.vc6_v2 import rejeu  # noqa: E402

log = logging.getLogger("beta.vc6_rejeu")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--journal", type=Path, default=None)
    ap.add_argument("--repertoire", type=Path, default=None,
                    help="ou ecrire PAPER_VC6_REJEU.jsonl (defaut : racine du depot)")
    ap.add_argument("--date", type=dt.date.fromisoformat, default=None)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    try:
        pp.verifier_gel()
    except Exception as exc:  # noqa: BLE001
        log.error("%s", exc)
        return 2
    aujourdhui = args.date or dt.datetime.now(dt.UTC).date()
    sortie = rejeu.rejouer(aujourdhui, args.journal or pp.chemin_journal())
    chemin = rejeu.ecrire(sortie, args.repertoire)
    for e in sortie["ecarts"]:
        log.info("%s %s : paper %.2f %% contre backtest %.2f %% (%+.2f points) : %s", e["jour"],
                 e["actif"], e["paper"] * 100, e["backtest"] * 100, e["ecart_points"],
                 e["explication"])
    c = sortie["controle_backtest_fige"]
    log.info("rejeu du %s : %d jour(s), %d ecart(s) > 5 points dont %d non explique(s) ; backtest "
             "fige reproduit : %s ; ligne ecrite dans %s", sortie["date"], sortie["jours"],
             len(sortie["ecarts"]), sortie["non_expliques"],
             "—" if c is None else ("oui" if c["identique"] else "NON"), chemin.name)
    alertes = rejeu.alerte(sortie)
    for a in alertes:
        log.error("%s", a)
    return 4 if alertes else 0


if __name__ == "__main__":
    sys.exit(main())
