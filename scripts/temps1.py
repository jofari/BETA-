"""Temps 1, etape A (labo actions, T1A) — la campagne et son rapport, en ligne de commande.

    /root/venvs/beta/bin/python scripts/temps1.py --donnees     couverture + PIT, sans mesure
    /root/venvs/beta/bin/python scripts/temps1.py --campagne    14 couples (detecteur x actif),
                                                                 compteur +14 AVANT le calcul,
                                                                 puis temps1/RAPPORT_ETAPE_A.*
    /root/venvs/beta/bin/python scripts/temps1.py --rapport     rapport seul, depuis data/temps1

T1A doit etre preenregistree (`scripts/preenregistrer_t1a.py`) : rien ne se mesure sans elle.
Un couple deja calcule n'est ni recalcule ni recompte (`--recalculer` refait le calcul, sans
recompter). Donnees : `python scripts/marches.py` (collecteur des vrais marches).
"""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta.temps1 import campagne as ca  # noqa: E402
from beta.temps1 import donnees as dn  # noqa: E402
from beta.temps1 import rapport  # noqa: E402

for flux in (sys.stdout, sys.stderr):
    if hasattr(flux, "reconfigure"):
        flux.reconfigure(encoding="utf-8", errors="replace")

log = logging.getLogger("beta.temps1")


def ecarts(synthese: dict) -> list[str]:
    """Les ecarts au prompt, avec leur raison (section 7 du rapport). Faits, pas d'analyse."""
    pit = synthese["donnees"]["pit_dexjpus"]
    sortie = [
        "**Nasdaq = Nasdaq-100 `^NDX`.** Le prompt dit « Nasdaq » ; Jonas a choisi le Nasdaq-100 "
        "le 21/10 (question posée avant tout code).",
        "**Or = fixing LBMA de l'après-midi, via le World Gold Council, pas yfinance.** Yahoo n'a "
        "pas l'or comptant, seulement le contrat à terme GC=F, et seulement depuis 2000 : COUCHE1 "
        "aurait été incalculable sur 1991-2001. Choix de Jonas le 21/10. Le fixing a lieu à "
        "15:00 à Londres, ce n'est pas une clôture. Avant 2019, WGC remplit les fériés londoniens "
        "avec la valeur précédente, et ces jours comptent comme des fixings dans la SMA 200 de "
        "l'or.",
        "**Calendrier civil comblé.** C'est la seule façon de réutiliser le moteur TI1 sans le "
        "modifier : il annualise sur 365 jours et calcule ses captures sur des semaines de "
        "7 jours. Les rendements sont nuls les jours sans séance. Aux dates de séance, la courbe "
        "est celle d'un calcul séance par séance (vérifié par un test). Ulcer, retards, durées, "
        "faux signaux (60 jours) et décalage des nulls (≥ 90 jours) se comptent donc en jours "
        "civils.",
        "**κ = 10 pb par unité de |ΔE|** (moteur tel quel). Un passage 1,0 → 0,25 coûte 7,5 pb, "
        "un passage 1,0 → 0,7 coûte 3 pb.",
        "**Indices de prix, dividendes exclus ; liquidités rémunérées à 0 ; pas de coût "
        "d'entrée.** Ce sont les conventions du moteur TI1, inchangées.",
        "**VIX.** La clôture de 16:15 ET sert à une décision prise à la clôture des actions "
        "(16:00 ET). C'est la même idéalisation « décidé à la clôture » que le moteur.",
        "**Préchauffe.** Elle porte sur chaque série lue, pas seulement sur l'actif cible : "
        "252 observations avant la première décision, et au moins la fenêtre du détecteur.",
        "**Bande SMA126/168/210/252 sans portes.** Le prompt ne leur en donne pas ; les juger "
        "reviendrait à choisir une fenêtre (règle 2).",
    ]
    if pit["mode"] == "alfred":
        sortie.append("**DEXJPUS.** Toutes les observations ont leur date de publication "
                      "ALFRED.")
    else:
        sortie.append(
            f"**DEXJPUS, point-in-time en mode « {pit['mode']} ».** "
            f"{pit['repli_2_jours_ouvres']} observation(s) sur {pit['observations']} n'ont pas "
            "de date ALFRED informative : antérieures à l'archive, ou ALFRED indisponible. Elles "
            "reçoivent le décalage de 2 jours ouvrés US prévu par le prompt. ⚠️ Le H.10 est "
            "hebdomadaire (publié le lundi) : ce repli peut lire une valeur jusqu'à environ "
            "5 jours ouvrés avant sa publication réelle.")
    if synthese["verdict"]["verdict"] == "candidat retenu" and len(synthese["verdict"]
                                                                  ["retenus"]) == 2:
        sortie.append("**Deux candidats retenus.** Le prompt ne prévoit pas de départage ; les "
                      "deux sont déclarés, sans classement.")
    return sortie


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--donnees", action="store_true")
    ap.add_argument("--campagne", action="store_true")
    ap.add_argument("--rapport", action="store_true")
    ap.add_argument("--recalculer", action="store_true")
    ap.add_argument("--b", type=int, default=1000)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    if a.donnees:
        d = dn.charger()
        print(json.dumps({"fin": f"{d.fin:%Y-%m-%d}", "empreinte": d.empreinte,
                          "pit_dexjpus": d.pit_dexjpus, "couverture": d.couverture},
                         ensure_ascii=False, indent=1))
        return 0
    if a.campagne:
        if a.b != 1000:
            raise SystemExit("B = 1000 est preenregistre : --b ne sert qu'aux essais hors mesure")
        synthese = ca.lancer_campagne(dn.charger(), b=a.b, recalculer=a.recalculer)
    elif a.rapport:
        synthese = json.loads((ca.DOSSIER / f"campagne_{ca.ID_EXP}.json")
                              .read_text(encoding="utf-8"))
    else:
        ap.print_help()
        return 2
    chemin = rapport.ecrire(synthese, ecarts(synthese))
    print(f"rapport : {chemin}")
    print(f"verdict : {synthese['verdict']}")
    print(f"compteur : {synthese['compteur']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
