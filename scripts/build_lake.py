"""Point d'entree unique du lake : importer, telecharger, convertir, cataloguer.

Idempotent. Le relancer ne re-telecharge rien d'inutile et reconstruit un lake identique.

Usage :
  & C:\\Users\\jofar\\venvs\\arit\\Scripts\\python.exe scripts/build_lake.py
      [--sans-telechargement]   n'appelle pas le reseau : amorce depuis ARIT et convertit seulement

Sur le VPS, lance chaque jour par deploy/beta-maj.timer (00:20 UTC).
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

from beta import config  # noqa: E402
from beta.lake import catalogue, lecture, maj, telechargement, univers  # noqa: E402

# La console Windows est en cp1252 : un message d'erreur de freqtrade contenant un accent
# (ou un caractere de remplacement) fait planter le script SUR SON PROPRE RAPPORT D'ERREUR,
# ce qui masque la panne d'origine. Constate le 18/08.
for flux in (sys.stdout, sys.stderr):
    if hasattr(flux, "reconfigure"):
        flux.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)-14s %(message)s")
log = logging.getLogger("build_lake")


def _afficher_etat() -> int:
    etat = catalogue.etat()
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
        catalogue.purger()
        log.info("lake purge")
    config.preparer_dossiers()

    # 1-2. Les 6 paires et la macro : amorcage depuis ARIT (copie, lecture seule) des
    #      feathers absents, puis freqtrade COMPLETE chaque fichier, puis integration au
    #      lake, puis F&G + FRED. Depuis le 03/10 : avant, les 4 paires historiques, le
    #      funding et la macro restaient figes a la date des fichiers d'ARIT.
    echecs: list[str] = maj.mettre_a_jour(reseau=not args.sans_telechargement)
    for echec in echecs:
        log.error("%s", echec)

    # 3. Les indices quotidiens (yfinance) : reseau aussi, donc apres tout ce qui est gratuit.
    #    Le parquet et sa ligne de catalogue sortent directement de `telecharger_indices`.
    if not args.sans_telechargement:
        try:
            for base, etat in telechargement.telecharger_indices().items():
                if etat != "ok":
                    echecs.append(f"{base} 1d (yfinance) : {etat}")
        except telechargement.DownloadError as exc:
            echecs.append(f"indices (yfinance) : {exc}")
            log.error("indices : %s", exc)
    else:
        log.info("--sans-telechargement : indices non telecharges (%s)",
                 ", ".join(i.base for i in univers.INDICES))

    print()
    code = _afficher_etat()
    if not args.sans_telechargement:
        print("\nfraicheur :")
        for f in maj.fraicheur():
            derniere = f["derniere"].strftime("%Y-%m-%d %H:%M") if f["derniere"] is not None else "absente"
            print(f"  {'EN RETARD' if f['en_retard'] else 'ok':9s} {f['serie']:22s} {derniere}")
            if f["en_retard"]:
                echecs.append(f"{f['serie']} en retard (derniere : {derniere})")
    if echecs:
        print(f"\n{len(echecs)} probleme(s) :")
        for echec in echecs:
            print(f"  - {echec}")
        return 1
    # Verification de bout en bout : le lake doit etre LISIBLE, pas seulement ecrit.
    try:
        apercu = lecture.load(univers.PAIRES[0].base, "4h")
        print(f"\nlecture verifiee : {univers.PAIRES[0].base} 4h -> {len(apercu)} bougies")
    except lecture.DataError as exc:
        print(f"\nlake ecrit mais illisible : {exc}")
        return 1
    return code


if __name__ == "__main__":
    sys.exit(main())
