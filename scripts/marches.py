"""Les vrais marches (S&P 500, Nasdaq-100, VIX, or LBMA, USD/JPY H.10) : collecter, decrire.

Usage :
  python scripts/marches.py                    met a jour toutes les series (incremental)
  python scripts/marches.py --construire       tout l'historique depuis les sources
  python scripts/marches.py --series SPX VIX   seulement celles-la
  python scripts/marches.py --etat             couverture, trous, retard, sans reseau

Sur le VPS, lance chaque jour par deploy/beta-marches.timer (23:10 UTC, apres la cloture de New
York). Sortie 1 = une serie en echec ou en retard : le timer passe en echec (alerte Discord).
Rien de ce qui tourne ne lit `data/marches/` : ce collecteur ne change aucune mesure existante.
"""

from __future__ import annotations

import argparse
import logging
import pathlib
import sys

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from beta.marches import collecte  # noqa: E402

for flux in (sys.stdout, sys.stderr):
    if hasattr(flux, "reconfigure"):
        flux.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)-22s %(message)s")


def afficher(etat: dict) -> int:
    if not etat:
        print("aucune serie : lancer python scripts/marches.py --construire")
        return 1
    print(f"{'serie':10s}{'statut':11s}{'debut':>12s}{'fin':>12s}{'obs':>8s}{'trous>5':>9s}"
          f"{'retard':>8s}  source")
    pire = 0
    for nom, e in etat.items():
        trous = e.get("trous_plus_de_5_seances", "—")
        print(f"{nom:10s}{e.get('statut', '?'):11s}{e.get('debut', '—'):>12s}"
              f"{e.get('fin', '—'):>12s}{e.get('n', 0):>8}{trous:>9}"
              f"{e.get('retard_j', '—'):>8}  {e.get('source')} {e.get('identifiant')}")
        if e.get("erreur"):
            print(f"{'':10s}erreur : {e['erreur']}")
        if e.get("alfred"):
            print(f"{'':10s}ALFRED : {e['alfred']}")
        if e.get("statut") != "ok":
            pire = 1
    return pire


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--construire", action="store_true")
    ap.add_argument("--series", nargs="*")
    ap.add_argument("--etat", action="store_true")
    a = ap.parse_args()
    etat = collecte.etat() if a.etat else collecte.tout_mettre_a_jour(a.series,
                                                                       construire=a.construire)
    if a.series:
        etat = {n: e for n, e in etat.items() if n in {s.upper() for s in a.series}}
    return afficher(etat)


if __name__ == "__main__":
    sys.exit(main())
