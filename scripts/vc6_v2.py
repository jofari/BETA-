"""VC6 V2 : tests de coherence du moteur, puis les runs (prompts de Jonas du 02/11/2026).

    /root/venvs/beta/bin/python scripts/vc6_v2.py --coherence  # les 4 tests, aucun run d'essai
    /root/venvs/beta/bin/python scripts/vc6_v2.py --go         # GO de Jonas : runs + rapport
    /root/venvs/beta/bin/python scripts/vc6_v2.py --rapport    # rapport depuis le dernier resultat

--coherence : verifie le gel, lance les 4 tests (arret au premier qui rate), ecrit
data/vc6_v2/coherence.json et VC6_V2/coherence.md. Sortie 1 si un test rate.
--go : `campagne.executer()` (gel, compteur, tests de coherence, runs, nulls, regles), resultats
bruts dans data/vc6_v2/resultats.pkl (jetable, se recalcule a l'identique), registre marque
« mesure » (les 2 essais sont deja comptes), rapport VC6_V2/rapport_v2.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import pathlib
import pickle
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta import config  # noqa: E402
from beta.protocole import experiences  # noqa: E402
from beta.vc6_v2 import campagne, coherence, gel, rapport  # noqa: E402
from beta.vc6_v2 import regles as R  # noqa: E402

log = logging.getLogger("beta.vc6_v2")
DOSSIER = config.DATA / "vc6_v2"
PKL = DOSSIER / "resultats.pkl"


def run_id(cle: str) -> str:
    """Le meme que scripts/preenregistrer_vc6_v2.py : l'essai journalise avant calcul."""
    return hashlib.sha256(f"{R.ID_EXP}:{cle}:{R.empreinte()}".encode()).hexdigest()[:12]


def go() -> int:
    journalises = {e.get("run_id") for e in experiences.runs_journalises()}
    manquants = [k for k in R.ESSAIS if run_id(k) not in journalises]
    if manquants:
        log.error("essais non journalises avant calcul : %s", manquants)
        return 2
    res = campagne.executer()
    DOSSIER.mkdir(parents=True, exist_ok=True)
    PKL.write_bytes(pickle.dumps(res))
    for cle in R.ESSAIS:
        experiences.marquer_mesuree(R.ID_EXP, run_id(cle), f"mesure {cle}")
    log.info("resultats ecrits : %s ; rapport %s", PKL, rapport.ecrire(res))
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s  %(message)s")
    a = argparse.ArgumentParser()
    a.add_argument("--coherence", action="store_true", help="les 4 tests de coherence")
    a.add_argument("--go", action="store_true", help="les runs (GO de Jonas du 02/11/2026)")
    a.add_argument("--rapport", action="store_true", help="rapport depuis le dernier resultat")
    args = a.parse_args()
    if args.go:
        return go()
    if args.rapport:
        log.info("rapport : %s", rapport.ecrire(pickle.loads(PKL.read_bytes())))
        return 0
    if not args.coherence:
        log.error("choisir --coherence, --go ou --rapport")
        return 2
    gel.verifier()
    res = coherence.tous()
    compteurs = {"invest": experiences.compteur(famille="invest"),
                 "trading": experiences.compteur(), "global": experiences.compteur_total()}
    DOSSIER.mkdir(parents=True, exist_ok=True)
    (DOSSIER / "coherence.json").write_text(
        json.dumps({"resultats": res, "compteurs": compteurs, "regles": R.empreinte()},
                   indent=1, default=str), encoding="utf-8")
    chemin = rapport.ecrire_coherence(res, compteurs, R.empreinte())
    log.info("tests de coherence : %s ; rapport %s",
             "les 4 passent" if res["passe"] else f"ARRET au test {res.get('arret')}", chemin)
    return 0 if res["passe"] else 1


if __name__ == "__main__":
    sys.exit(main())
