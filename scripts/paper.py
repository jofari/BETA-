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

Sortie non nulle = unite « failed » :
    1  une voie n'a pas pu s'executer : marche illisible, ou consigne absente (suivi en
       panne). Les autres voies s'executent quand meme.
    4  voie C figee ou VC3 : un critere du dry-run est franchi — ecart de rendement cumule
       paper - suivi au-dela de +/-1 pt, ou cout moyen au carnet > 2x le slippage du modele.
       Le journal est ecrit quand meme ; c'est une alarme, la suite est une decision de Jonas.
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
from beta.strategies import voie_c_voltarget as vc  # noqa: E402

log = logging.getLogger("beta.paper")


# Criteres du dry-run juges ici (registre, regle « forward » du 07/10 ; ecart fixe par Jonas le
# 10/10, avant toute donnee qui le franchisse). VC2 est infirmee : informative, jamais jugee.
JUGEES = ("VOIE_C", "VC3", "VC4", "VC5")   # VC4, VC5 : memes criteres que VC3 (10/10)
ECART_MAX = 0.01                    # |paper - suivi au cours de cloture|, rendement cumule
FACTEUR_SLIPPAGE = 2.0              # cout reel au carnet <= 2x le slippage du modele
# La voie C figee ne suppose aucun slippage (2 x 0 ne jugerait rien) : sa reference est celle
# de sa propre variante severe.
SLIPPAGE_REFERENCE_PB = {"VOIE_C": vc.BPS_SLIPPAGE}


def mesures(voie: paper.Voie, repertoire: Path, suivis: Path) -> dict | None:
    """Le paper depuis son premier jour, et le suivi au cours de cloture sur les memes jours."""
    lignes = paper.lire_journal(paper.journal_paper(voie, repertoire))
    if not lignes:
        return None
    debut, fin = lignes[0]["date"], lignes[-1]["date"]
    # Cadence « instant » (VC4) : plusieurs executions par jour. Le modele est quotidien
    # (00:00 -> 00:00) : on le compare a la PREMIERE execution du dernier jour, celle de la
    # decision de 00:00, comme pour les voies quotidiennes.
    premiere_du_jour = next(l for l in lignes if l["date"] == fin)
    # La journee d du suivi = la detention entre les executions de d et de d+1.
    modele = [l["r_net"] for l in paper.lire_journal(suivis / voie.journal_modele)
              if debut <= l["date"] < fin]
    ordres = [o for l in lignes for o in l["ordres"]]
    notional = sum(o["notional"] for o in ordres)

    def moyenne(cle: str) -> float:
        return sum(o[cle] * o["notional"] for o in ordres) / notional if notional else math.nan

    return {"debut": debut, "fin": fin, "jours": len({l["date"] for l in lignes}),
            "equite": lignes[-1]["equite"],
            "rendement": premiere_du_jour["equite_avant"] / paper.CAPITAL_USDT - 1.0,
            "r_modele": math.prod(1.0 + r for r in modele) - 1.0, "jours_modele": len(modele),
            "frais": sum(l["frais"] for l in lignes),
            "funding": sum(sum(l["funding"].values()) for l in lignes),
            "ordres": len(ordres), "notional": notional,
            "carnet_pb": moyenne("cout_carnet_pb"), "ouverture_pb": moyenne("ecart_ouverture_pb"),
            "modele_pb": SLIPPAGE_REFERENCE_PB.get(voie.nom, moyenne("slippage_modele_pb"))}


def bilan(voie: paper.Voie, m: dict | None) -> str:
    if m is None:
        return f"{voie.nom} : aucun jour execute"
    return (f"{voie.nom} ({voie.instrument}) depuis le {m['debut']}, {m['jours']} j : equite "
            f"{m['equite']:,.2f} USDT ({m['rendement']:+.2%} a l'ouverture du {m['fin']}) | "
            f"suivi au cours de cloture {m['r_modele']:+.2%} sur {m['jours_modele']} j | frais "
            f"{m['frais']:.2f}, funding {m['funding']:+.2f} | {m['ordres']} ordres, "
            f"{m['notional']:,.0f} USDT : carnet {m['carnet_pb']:.1f} pb, ouverture "
            f"{m['ouverture_pb']:+.1f} pb (modele {m['modele_pb']:.1f} pb)")


def franchis(m: dict | None) -> list[str]:
    """Les criteres du dry-run franchis. Le slippage juge est le cout au carnet (vs milieu) :
    l'ecart a l'ouverture melange l'heure de decalage, il compte dans l'ecart au suivi."""
    if m is None:
        return []
    alertes = []
    ecart = m["rendement"] - m["r_modele"]
    if abs(ecart) > ECART_MAX:
        alertes.append(f"ecart paper - suivi {ecart:+.2%} (critere +/-{ECART_MAX:.0%})")
    if m["notional"] and m["carnet_pb"] > FACTEUR_SLIPPAGE * m["modele_pb"]:
        alertes.append(f"slippage au carnet {m['carnet_pb']:.1f} pb > "
                       f"{FACTEUR_SLIPPAGE:.0f} x {m['modele_pb']:.1f} pb du modele")
    return alertes


def main() -> int:
    toutes = paper.voies()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--voie", action="append", choices=sorted(toutes),
                    help="une voie (repetable) ; defaut : toutes")
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
        m = mesures(voie, args.repertoire, config.RACINE)
        log.info("%s", bilan(voie, m))
        if nom in JUGEES:
            for alerte in franchis(m):
                log.error("%s : CRITERE DU DRY-RUN FRANCHI : %s. La suite est une decision de "
                          "Jonas.", nom, alerte)
                code = code or 4
    return code


if __name__ == "__main__":
    sys.exit(main())
