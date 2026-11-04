"""Le rapport d'une ou plusieurs experiences du moteur, ecrit par le programme.

    /root/venvs/arit/bin/python scripts/rapport_experience.py R13 R14
    /root/venvs/arit/bin/python scripts/rapport_experience.py R13 R14 --eprouver
    /root/venvs/arit/bin/python scripts/rapport_experience.py R13 --avis avis_claude.md

Ecrit `rapports/<ids>/RAPPORT.md` et `rapports/<ids>/RESUME_DISCORD.md` (et `EPREUVES.json`
avec `--eprouver`), puis affiche le resume. C'est ce resume, tel quel, qui part sur le salon
Discord BETA, avec RAPPORT.md en piece jointe (Jonas, 04/11/2026 : les chiffres et le verdict
sortent du programme, pas de Claude).

`--eprouver` relance l'epreuve de causalite de l'atelier sur la serie et la periode de chaque
run qui n'en a pas (runs mesures avant le 04/11/2026) ; le code eprouve est celui du jour, et
le rapport dit s'il a la meme empreinte que le run.

`--avis` recopie un fichier ecrit par Claude dans une section separee, marquee « ce n'est PAS
le programme ». Sans lui, le rapport ne contient que ce que le programme a lu ou recalcule.
"""
from __future__ import annotations

import argparse
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta.rapport import experience  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)-7s %(name)s %(message)s")
    parseur = argparse.ArgumentParser(prog="rapport_experience")
    parseur.add_argument("ids", nargs="+", help="identifiants du registre (R13 R14 ...)")
    parseur.add_argument("--sortie", type=pathlib.Path, default=None,
                         help="dossier de sortie (defaut : rapports/<ids>)")
    parseur.add_argument("--avis", type=pathlib.Path, default=None,
                         help="fichier d'avis de Claude, recopie dans une section separee")
    parseur.add_argument("--eprouver", action="store_true",
                         help="relancer l'epreuve de causalite des runs qui n'en ont pas")
    arguments = parseur.parse_args(argv)

    commande = " ".join(["scripts/rapport_experience.py", *arguments.ids]
                        + (["--eprouver"] if arguments.eprouver else [])
                        + ([f"--avis {arguments.avis.name}"] if arguments.avis else []))
    try:
        chemins = experience.ecrire(arguments.ids, sortie=arguments.sortie,
                                    avis=arguments.avis, eprouver=arguments.eprouver,
                                    commande=commande)
    except experience.RapportError as exc:
        print(f"rapport impossible : {exc}")
        return 1
    print(chemins["resume"].read_text(encoding="utf-8"))
    print(f"rapport : {chemins['rapport']}")
    print(f"resume  : {chemins['resume']}")
    if chemins["epreuves"]:
        print(f"epreuves relancees : {chemins['epreuves']}")
    # Code de sortie : 2 si un controle de coherence est en ecart (pastille rouge).
    return 2 if chemins["pastille"][0] == "🔴" else 0


if __name__ == "__main__":
    sys.exit(main())
