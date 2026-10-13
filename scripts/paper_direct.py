"""Paper en direct : une ligne par minute dans DIRECT_PAPER.jsonl (timer beta-paper-direct).

    ARIT_HOME=/root/ARIT2.0 /root/venvs/arit/bin/python scripts/paper_direct.py

Valorise le compte du dernier passage de chaque voie aux prix Binance de la minute, net du
funding regle depuis (`beta.paper_direct`). Aucun ordre, aucune cle, aucun journal du paper
touche. Binance illisible = sortie 1, la minute manque sur la courbe, rien d'autre.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from beta import config, paper, paper_direct  # noqa: E402


def main() -> int:
    maintenant = dt.datetime.now(dt.UTC).replace(microsecond=0)
    try:
        ligne = paper_direct.releve(config.RACINE, paper.MarcheBinance(), maintenant)
    except paper.PaperError as exc:
        print(f"paper direct : {exc}", file=sys.stderr)
        return 1
    paper_direct.ajouter(ligne)
    print(" · ".join(f"{k} {v:.2f}" for k, v in ligne["e"].items()) or "aucune voie")
    return 0


if __name__ == "__main__":
    sys.exit(main())
