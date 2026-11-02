"""« Paper de plomberie – VC6 V2 poche baissiere sous HAR » : un jour d'execution simulee.

    ARIT_HOME=/root/ARIT2.0 /root/venvs/beta/bin/python scripts/vc6_paper.py
        [--journal CHEMIN] [--date AAAA-MM-JJ]

Chaque jour (timer beta-vc6-paper, apres beta-maj) : decision a la cloture de la veille (barre 5 min
de 23:55) avec le code du backtest, execution simulee au comptant a l'ouverture de la bougie 1 min
de 00:00, + 10 pb, une ligne dans PAPER_VC6.jsonl (`beta.vc6_v2.paper`). Run non juge.
--date : jour d'execution (defaut : aujourd'hui UTC) ; --journal : autre fichier (essai).

Sortie non nulle = unite « failed » (alerte Discord) :
    1  marche Binance illisible : rien n'est ecrit (relance 5 min plus tard)
    2  gel rompu (ligne de diagnostic absente, regles V2 ou parametres du paper changes)
    3  la journee fictive change des journees deja jouees (causalite rompue)
    4  donnee manquante a la cloture : aucun nouvel ordre, ligne ecrite, alerte (pas de relance)
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from beta import paper as bp  # noqa: E402
from beta.vc6_v2 import paper as pp  # noqa: E402
from beta.vc6_v2 import vivant  # noqa: E402

log = logging.getLogger("beta.vc6_paper")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--journal", type=Path, default=None)
    ap.add_argument("--date", type=dt.date.fromisoformat, default=None)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    try:
        pp.verifier_gel()
    except Exception as exc:  # noqa: BLE001 - tout gel rompu arrete le run
        log.error("%s", exc)
        return 2
    maintenant = dt.datetime.now(dt.UTC)
    if args.date is not None:
        maintenant = dt.datetime.combine(args.date, maintenant.time(), dt.UTC)
    chemin = args.journal or pp.chemin_journal()
    try:
        ligne = pp.journee(maintenant, bp.MarcheBinance(), chemin)
    except pp.PaperError as exc:
        log.error("%s — rien n'est ecrit", exc)
        return 1
    except vivant.CausaliteError as exc:
        log.error("%s — rien n'est ecrit", exc)
        return 3
    if ligne is None:
        log.info("%s : jour %s deja execute (%s)", pp.NOM, maintenant.date(), chemin.name)
        return 0
    if ligne["statut"] == "donnee_manquante":
        log.error("DONNEE MANQUANTE a la cloture du %s : aucun nouvel ordre. %s",
                  ligne["decision"]["cloture"], ligne["manquant"])
        return 4
    dec = ligne["decision"]
    log.info("%s, %s : decision a la cloture du %s, mode %s%s ; %d ordre(s), frais %.4f USDT ; "
             "valeur %.2f USDT (%s)", pp.NOM, ligne["date"], dec["cloture"], dec["mode_btc"],
             " (rampe)" if dec["en_rampe"] else "", len(ligne["ordres"]), ligne["frais"],
             ligne["valeur"], chemin.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
