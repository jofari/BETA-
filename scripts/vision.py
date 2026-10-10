"""Historique public Binance (metrics, bookDepth, aggTrades) : telecharger ce qui manque.

Idempotent : ne telecharge que les jours publies absents de `data/vision/etat.duckdb`.
Le premier passage rattrape tout l'historique (2-4 h, ~100 Go telecharges,
~2 Go stockes) ; ensuite, un jour par jeu et par paire.

Usage :
  python scripts/vision.py                     tout ce qui manque, 3 jeux x 6 paires
  python scripts/vision.py --jeux metrics --paires BTC ETH --limite 3
  python scripts/vision.py --etat              couverture par serie, sans reseau

Sur le VPS, lance chaque jour par deploy/beta-vision.timer (03:30 UTC).
Sortie 1 = au moins un probleme (jour illisible, serie en retard) : le timer passe en echec.
"""

from __future__ import annotations

import argparse
import logging
import pathlib
import sys

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from beta.lake import univers, vision  # noqa: E402

for flux in (sys.stdout, sys.stderr):
    if hasattr(flux, "reconfigure"):
        flux.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)-17s %(message)s")


def afficher_etat() -> int:
    etat = vision.etat()
    if etat.empty:
        print("aucune serie : lancer scripts/vision.py")
        return 1
    print(f"{'jeu':10s}{'paire':6s}{'debut':>12s}{'fin':>12s}{'jours':>7s}{'absents':>8s}"
          f"{'trou':>6s}{'couv %':>8s}  lignes")
    for r in etat.itertuples():
        print(f"{r.jeu:10s}{r.base:6s}{str(r.debut):>12s}{str(r.fin):>12s}"
              f"{r.jours_attendus:7d}{r.jours_absents:8d}{r.plus_grand_trou_j:6d}"
              f"{r.couverture_pct:8.2f}  {r.lignes:,}{'  SUSPECTE' if r.suspect else ''}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--jeux", nargs="+", choices=tuple(vision.JEUX), default=tuple(vision.JEUX))
    ap.add_argument("--paires", nargs="+", default=[p.base for p in univers.PAIRES])
    ap.add_argument("--limite", type=int, default=None,
                    help="au plus N jours par serie (essai) ; desactive l'alarme de retard")
    ap.add_argument("--etat", action="store_true", help="affiche la couverture et sort")
    args = ap.parse_args()
    if args.etat:
        return afficher_etat()
    paires = tuple(univers.par_base(b.upper()) for b in args.paires)
    problemes = vision.mettre_a_jour(tuple(args.jeux), paires, args.limite)
    print()
    afficher_etat()
    if problemes:
        print(f"\n{len(problemes)} probleme(s) :")
        for p in problemes:
            print(f"  - {p}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
