"""Point d'entree unique du lake : importer, telecharger, convertir, cataloguer.

Idempotent. Le relancer ne re-telecharge rien d'inutile et reconstruit un lake identique.

Usage :
  & C:\\Users\\jofar\\venvs\\arit\\Scripts\\python.exe scripts/build_lake.py
      [--sans-telechargement]   n'appelle pas le reseau : importe et convertit seulement
      [--purge]                 repart d'un lake vide (data/ est jetable)
      [--etat]                  affiche le catalogue et sort
"""

from __future__ import annotations

import argparse
import logging
import pathlib
import sys

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from beta import config, data, download, lake, univers  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)-14s %(message)s")
log = logging.getLogger("build_lake")


def _afficher_etat() -> int:
    etat = lake.etat()
    if etat.empty:
        print("lake vide — lancer scripts/build_lake.py")
        return 1
    with __import__("pandas").option_context("display.width", 200,
                                             "display.max_columns", None):
        print(etat.to_string(index=False))
    suspects = etat[etat["suspect"]]
    if len(suspects):
        print(f"\n{len(suspects)} serie(s) SUSPECTE(s) — couverture sous "
              f"{100 - config.TROUS_PCT_ALERTE} % :")
        for r in suspects.itertuples():
            print(f"  {r.paire} {r.timeframe} : {r.couverture_pct:.2f} % "
                  f"({r.bougies_manquantes} bougies manquantes, "
                  f"plus grand trou {r.plus_grand_trou_h:.1f} h)")
    else:
        print("\naucune serie suspecte.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sans-telechargement", action="store_true",
                    help="aucun appel reseau : import ARIT + conversion seulement")
    ap.add_argument("--purge", action="store_true", help="repart d'un lake vide")
    ap.add_argument("--etat", action="store_true", help="affiche le catalogue et sort")
    args = ap.parse_args()

    if args.etat:
        return _afficher_etat()
    if args.purge:
        lake.purger()
        log.info("lake purge")
    config.preparer_dossiers()

    # 1. Les paires qu'ARIT a deja : lecture seule, aucun reseau. C'est gratuit, donc
    #    d'abord — un echec reseau plus loin laisse quand meme un lake exploitable.
    echecs: list[str] = []
    for paire in univers.a_importer():
        for timeframe in univers.TIMEFRAMES:
            try:
                lake.importer_depuis_arit(paire, timeframe)
            except lake.LakeError as exc:
                echecs.append(f"{paire.base} {timeframe} (import ARIT) : {exc}")
                log.error("%s %s : %s", paire.base, timeframe, exc)

    # 2. Les paires nouvelles : telechargement parallele, puis conversion.
    manquantes = univers.a_telecharger()
    if manquantes and not args.sans_telechargement:
        resultats = download.telecharger(manquantes)
        for base, etat in resultats.items():
            if etat != "ok":
                echecs.append(f"{base} (telechargement) : {etat}")
    elif manquantes:
        log.info("--sans-telechargement : %s non telechargee(s)",
                 ", ".join(p.base for p in manquantes))

    for paire in manquantes:
        for timeframe in univers.TIMEFRAMES:
            source = config.chemin_feather_brut(paire.slug, timeframe)
            if not source.exists():
                if not args.sans_telechargement:
                    echecs.append(f"{paire.base} {timeframe} : feather absent apres "
                                  f"telechargement")
                continue
            try:
                lake.integrer_telechargement(paire, timeframe)
            except lake.LakeError as exc:
                echecs.append(f"{paire.base} {timeframe} (conversion) : {exc}")
                log.error("%s %s : %s", paire.base, timeframe, exc)

    print()
    code = _afficher_etat()
    if echecs:
        print(f"\n{len(echecs)} probleme(s) :")
        for echec in echecs:
            print(f"  - {echec}")
        return 1
    # Verification de bout en bout : le lake doit etre LISIBLE, pas seulement ecrit.
    try:
        apercu = data.load(univers.PAIRES[0].base, "4h")
        print(f"\nlecture verifiee : {univers.PAIRES[0].base} 4h -> {len(apercu)} bougies")
    except data.DataError as exc:
        print(f"\nlake ecrit mais illisible : {exc}")
        return 1
    return code


if __name__ == "__main__":
    sys.exit(main())
