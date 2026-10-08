"""Paper trading des trois voies C — execution simulee contre le vrai carnet. Aucun ordre.

    ARIT_HOME=/root/ARIT2.0 /root/venvs/arit/bin/python scripts/paper.py [--voie VC3 ...]

Chaque jour (timer beta-paper, 01:00 UTC, apres les suivis de 00:45 et 00:50) : pour chaque
voie, lit la consigne du jour dans son suivi, l'execute en paper (`beta.paper`) et ajoute une
ligne a PAPER_<voie>.jsonl. Puis le bilan depuis le premier jour, a cote du suivi au cours de
cloture : meme strategie, mais execution supposee parfaite a 00:00 UTC. L'ecart entre les
deux, c'est ce que coute l'execution reelle.

Voies : VOIE_C (config figee du 03/10, perpetuels), VC2 (infirmee le 07/10, suivie pour
information, perpetuels), VC3 (dry-run depuis le 08/10, spot). Capital fictif de 10 000 USDT
chacune, la taille du canari.

Sortie 1 (unite « failed ») si une voie n'a pas pu s'executer : marche illisible, ou
consigne absente (suivi en panne). Les autres voies s'executent quand meme.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from beta import config, paper  # noqa: E402

log = logging.getLogger("beta.paper")


def bilan(voie: paper.Voie, repertoire: Path, suivis: Path) -> str:
    """Le paper depuis son premier jour, et le suivi au cours de cloture sur les memes jours."""
    lignes = paper.lire_journal(paper.journal_paper(voie, repertoire))
    if not lignes:
        return f"{voie.nom} : aucun jour execute"
    debut, fin = lignes[0]["date"], lignes[-1]["date"]
    rendement = lignes[-1]["equite_avant"] / paper.CAPITAL_USDT - 1.0
    # La journee d du suivi = la detention entre les executions de d et de d+1.
    modele = [l["r_net"] for l in paper.lire_journal(suivis / voie.suivi)
              if debut <= l["date"] < fin]
    r_modele = math.prod(1.0 + r for r in modele) - 1.0
    ordres = [o for l in lignes for o in l["ordres"]]
    notional = sum(o["notional"] for o in ordres)

    def moyenne(cle: str) -> float:
        return sum(o[cle] * o["notional"] for o in ordres) / notional if notional else math.nan

    return (f"{voie.nom} ({voie.instrument}) depuis le {debut}, {len(lignes)} j : equite "
            f"{lignes[-1]['equite']:,.2f} USDT ({rendement:+.2%} a l'ouverture du {fin}) | suivi "
            f"au cours de cloture {r_modele:+.2%} sur {len(modele)} j | frais "
            f"{sum(l['frais'] for l in lignes):.2f}, funding "
            f"{sum(sum(l['funding'].values()) for l in lignes):+.2f} | {len(ordres)} ordres, "
            f"{notional:,.0f} USDT : carnet {moyenne('cout_carnet_pb'):.1f} pb, ouverture "
            f"{moyenne('ecart_ouverture_pb'):+.1f} pb (modele {moyenne('slippage_modele_pb'):.1f}"
            f" pb)")


def main() -> int:
    toutes = paper.voies()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--voie", action="append", choices=sorted(toutes),
                    help="une voie (repetable) ; defaut : les trois")
    ap.add_argument("--repertoire", type=Path, default=config.RACINE,
                    help="ou ecrire les PAPER_<voie>.jsonl (defaut : racine du depot)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")

    marche = paper.MarcheBinance()
    code = 0
    for nom in args.voie or sorted(toutes):
        voie = toutes[nom]
        maintenant = dt.datetime.now(dt.UTC)
        try:
            ligne = paper.executer_voie(voie, marche, maintenant, args.repertoire)
        except paper.PaperError as exc:
            log.error("%s", exc)
            code = 1
            continue
        if ligne is None:
            log.info("%s : deja executee aujourd'hui", nom)
        else:
            log.info("%s : %d ordre(s), %d ignore(s), frais %.2f, funding %+.2f -> equite "
                     "%.2f USDT", nom, len(ligne["ordres"]), len(ligne["ignores"]),
                     ligne["frais"], sum(ligne["funding"].values()), ligne["equite"])
            for o in ligne["ordres"]:
                log.info("    %-4s %-6s %12.6f a %.6g | carnet %.1f pb, ouverture %+.1f pb "
                         "(modele %.0f pb)", o["paire"], o["sens"], o["qte"], o["prix"],
                         o["cout_carnet_pb"], o["ecart_ouverture_pb"], o["slippage_modele_pb"])
            for i in ligne["ignores"]:
                log.info("    %-4s ignore : %s", i["paire"], i["raison"])
        log.info("%s", bilan(voie, args.repertoire, config.RACINE))
    return code


if __name__ == "__main__":
    sys.exit(main())
