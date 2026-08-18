"""BETA — point d'entree unique en ligne de commande.

    python beta.py serve         le dashboard (et le navigateur qui s'ouvre)
    python beta.py lake          construit/actualise le lake OHLCV
    python beta.py strategie     importe les donnees de strategie depuis ARIT
    python beta.py etat          l'etat du lake, dans le terminal
    python beta.py doctor        ce qui est en place et ce qui manque

Doctrine et invariants : CLAUDE.md.
"""

from __future__ import annotations

import argparse
import logging
import pathlib
import subprocess
import sys

RACINE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(RACINE))


def preparer_console() -> None:
    """La console Windows est en cp1252 : sans ca, un accent tue le script sur un print."""
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8", errors="replace")


def preparer_logs(bavard: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if bavard else logging.INFO,
                        format="%(levelname)-7s %(name)-22s %(message)s")


def _script(nom: str, *args: str) -> int:
    """Delegue a un script de `scripts/`, dans le MEME interpreteur.

    Passer par `sys.executable` plutot que par `python` : le venv n'est pas forcement actif
    dans le shell qui lance BETA, et un mauvais interpreteur donnerait un « module
    introuvable » incomprehensible.
    """
    return subprocess.call([sys.executable, str(RACINE / "scripts" / nom), *args])


def cmd_serve(args) -> int:
    from beta.rapport import serveur
    return serveur.servir(hote=args.host, port=args.port, ouvrir=not args.no_browser)


def cmd_lake(args) -> int:
    extra = []
    if args.sans_telechargement:
        extra.append("--sans-telechargement")
    if args.purge:
        extra.append("--purge")
    return _script("build_lake.py", *extra)


def cmd_strategie(args) -> int:
    return _script("import_strategie.py", *(["--holdout"] if args.holdout else []))


def cmd_etat(_args) -> int:
    return _script("build_lake.py", "--etat")


def cmd_doctor(_args) -> int:
    from beta import config
    from beta.lake import catalogue, strategie
    from beta.protocole import experiences, holdout

    print(f"racine        {RACINE}")
    print(f"donnees       {config.DATA}")
    print(f"ARIT (lecture) {config.ARIT}"
          f"{'' if config.ARIT.exists() else '   <- INTROUVABLE'}")
    print(f"hold-out      scelle au {holdout.DEBUT.date()}")
    print(f"essais cumules {experiences.compteur()} "
          f"(dont {experiences.ESSAIS_INITIAUX} de dette initiale)")

    etat = catalogue.etat()
    if etat.empty:
        print("lake OHLCV    VIDE — lancer `python beta.py lake`")
    else:
        suspectes = int(etat["suspect"].sum())
        print(f"lake OHLCV    {len(etat)} series · {etat['paire'].nunique()} paires · "
              f"{int(etat['n_bougies'].sum()):,} bougies · {suspectes} suspecte(s)"
              .replace(",", " "))
        print(f"              borne commune : {str(etat['fin'].min())[:10]} "
              "(limite d'un run multi-paires)")

    manquantes = []
    for table in strategie.TABLES:
        chemin = strategie.chemin_table(table)
        if chemin.exists():
            try:
                print(f"{table:13s} {len(strategie.lire(table)):6d} lignes")
            except strategie.StrategieError as exc:
                print(f"{table:13s} ILLISIBLE : {exc}")
        else:
            manquantes.append(table)
    if manquantes:
        print(f"strategie     {', '.join(manquantes)} absente(s) — "
              "lancer `python beta.py strategie`")
    return 0


def parseur() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="beta", description=__doc__.splitlines()[0])
    p.add_argument("-v", "--verbose", action="store_true")
    subs = p.add_subparsers(dest="commande", required=True)

    from beta.rapport.serveur import HOTE, PORT
    serve = subs.add_parser("serve", help="dashboard web")
    serve.add_argument("--host", default=HOTE)
    serve.add_argument("--port", type=int, default=PORT)
    serve.add_argument("--no-browser", action="store_true")
    serve.set_defaults(fonction=cmd_serve)

    lake = subs.add_parser("lake", help="construit ou actualise le lake OHLCV")
    lake.add_argument("--sans-telechargement", action="store_true")
    lake.add_argument("--purge", action="store_true")
    lake.set_defaults(fonction=cmd_lake)

    strat = subs.add_parser("strategie", help="importe les donnees de strategie d'ARIT")
    strat.add_argument("--holdout", action="store_true",
                       help="inclut le hold-out dans le resume (EXCLU par defaut)")
    strat.set_defaults(fonction=cmd_strategie)

    subs.add_parser("etat", help="l'etat du lake").set_defaults(fonction=cmd_etat)
    subs.add_parser("doctor", help="ce qui est en place et ce qui manque"
                    ).set_defaults(fonction=cmd_doctor)
    return p


def main() -> int:
    preparer_console()
    args = parseur().parse_args()
    preparer_logs(args.verbose)
    return args.fonction(args)


if __name__ == "__main__":
    sys.exit(main())
