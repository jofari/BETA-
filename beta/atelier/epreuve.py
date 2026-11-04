"""L'epreuve : ce qu'une candidate doit prouver en TOURNANT, avant d'entrer au banc.

Le sas lit le code. L'epreuve l'execute — sur de vraies bougies, dans un **sous-processus**
et avec un chronometre. Les deux moities sont ici : `lancer()` cote appelant, `main()` cote
enfant.

Pourquoi un sous-processus alors que le reste du projet importe tranquillement ses modules :
une candidate ecrite vite — et surtout une candidate ecrite par un modele local — contient
un jour ou l'autre une boucle qui ne finit pas. Importee dans le processus du dashboard,
elle gele l'onglet pour toujours, et la seule issue est de tuer BETA. Le sous-processus rend
la panne bornee : au pire, on perd le temps du chronometre.

Quatre epreuves, dont une qui vaut les trois autres :

1. **contrat** — `appliquer()` rend le bon nombre de lignes, `sens` dans {-1, 0, +1}.
2. **determinisme** — deux appels, meme sortie. Le contrat exige une fonction PURE ; une
   candidate qui garde un etat fabrique du look-ahead que rien ne rattrape ensuite.
3. **causalite** — `signaux(df[:t])` doit rendre EXACTEMENT `signaux(df)[:t]`. C'est le
   test qui compte : une fonction causale ne peut pas produire autre chose sur un prefixe,
   puisque chaque ligne ne depend que de son passe. Toute lecture du futur — `shift(-1)`,
   fenetre centree, maximum global, normalisation sur la serie entiere — deplace au moins
   une valeur du prefixe. Aucune liste de motifs interdits ne peut en dire autant : elle
   attrape ce qu'elle connait, celui-ci attrape ce qu'on n'avait pas prevu.
4. **non-degenerescence** — une candidate qui ne signale jamais rien n'est pas mesurable,
   et une candidate en position 99 % du temps n'est pas un signal, c'est un hold.

L'epreuve lit UNIQUEMENT du train : le hold-out est scelle, et le bruler pour valider la
syntaxe d'une candidate serait la facon la plus bete de le perdre.

**La serie reelle (04/11/2026, R13 et R14).** Sans `--actif`, l'epreuve tourne sur une serie
TEMOIN (BTC en 4h, ou BTC dans le timeframe demande) : elle valide le code, pas la candidate
sur ce qu'elle tradera — une regle ancree sur l'ouverture de New York etait refusee en 4h, et
validee sur BTC en 5m alors qu'elle visait l'or. Avec `--actif`, elle tourne sur CETTE serie,
chargee comme le moteur la charge (`pipeline.charger_series` : funding, macro, tick), sur toute
la periode demandee bornee au train, et ne se rabat sur AUCUNE autre si elle manque. Le nombre
de signaux qu'elle rend est alors celui de la periode : le comptage d'avant le
preenregistrement sort de BETA. Le moteur refait de toute facon la meme epreuve sur les series
du run avant de mesurer (`pipeline.eprouver_le_run`).

    python -m beta.atelier.epreuve <module>          # rend un rapport JSON sur stdout
    python -m beta.atelier.epreuve <module> --actif XAU_SPOT --timeframe 5m --debut 2023-06-21
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

from beta.moteur.causalite import COUPURES, TOLERANCE, comparer  # noqa: F401 - reexportes

log = logging.getLogger("beta.atelier.epreuve")

RACINE = Path(__file__).resolve().parents[2]

# Tranche d'epreuve. Assez longue pour qu'une moyenne mobile de 200 ait un sens, assez
# courte pour que l'epreuve tienne en quelques secondes : on valide une candidate, on ne la
# mesure pas.
PAIRE_TEMOIN = "BTC"
TIMEFRAME_TEMOIN = "4h"
BOUGIES_TEMOIN = 1500

# Une candidate INTRADAY est structurellement muette sur du 4h : une regle ancree sur
# 09:30-10:15 New York ne trouve aucune bougie 4h dans sa fenetre, donc ne signale rien, donc
# est refusee pour « aucun signal » alors qu'elle est juste. Le timeframe d'epreuve se choisit
# donc, et le defaut ne bouge pas.
#
# Le nombre de bougies suit : 1500 bougies 5m ne couvrent que cinq jours, ce qui rendrait une
# regle a un signal par jour indecidable pour une raison qui n'est pas la sienne. On vise
# partout le meme ORDRE DE GRANDEUR en temps couvert, pas en nombre de lignes.
BOUGIES_PAR_TIMEFRAME = {"5m": 20_000, "15m": 8_000, "1h": 4_000}

# Les coupures de l'epreuve de causalite (`COUPURES`) et la tolerance des colonnes
# auxiliaires (`TOLERANCE`) vivent dans `beta.moteur.causalite` depuis le 04/11 : le moteur
# refait la meme epreuve avant de mesurer, et deux copies finiraient par diverger.

# Au-dela, on considere que la candidate ne finira pas. Le chargement du parquet et l'import
# de pandas comptent dedans : le seuil est genereux a dessein, il vise la boucle infinie,
# pas la candidate lente.
TIMEOUT_S = 120
# Sur la serie reelle, l'epreuve lit toute la periode (des centaines de milliers de bougies en
# 5m) et joint funding et macro comme le moteur : le chronometre s'allonge d'autant. Il vise
# toujours la boucle sans fin, pas la candidate lente.
TIMEOUT_REEL_S = 600

MIN_SIGNAUX = 5
PART_EN_POSITION_MAX = 0.98


class EpreuveError(RuntimeError):
    """L'epreuve n'a pas pu tourner. A distinguer d'une epreuve qui a tourne et refuse."""


# --- cote appelant ----------------------------------------------------------------------

def lancer(module: str, timeout: int | None = None, timeframe: str = "", actif: str = "",
           debut: str = "", fin: str = "") -> dict:
    """Lance l'epreuve dans un sous-processus. Ne leve pas : un echec est un rapport.

    Le rapport a toujours la meme forme, quoi qu'il arrive — `{ok, refus, reserves,
    mesures}`. Un appelant (CLI, dashboard, boucle de reparation d'un modele local) n'a
    donc jamais deux chemins a ecrire. `actif` (avec `timeframe`, `debut`, `fin`) eprouve
    la candidate sur la serie qu'elle tradera ; sans lui, sur une serie temoin.
    """
    if timeout is None:
        timeout = TIMEOUT_REEL_S if actif else TIMEOUT_S
    options = [("--timeframe", timeframe), ("--actif", actif), ("--debut", debut),
               ("--fin", fin)]
    try:
        fini = subprocess.run(                                   # noqa: S603
            [sys.executable, "-m", "beta.atelier.epreuve", module]
            + [x for option, valeur in options if valeur for x in (option, valeur)],
            cwd=str(RACINE), capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {"module": module, "ok": False,
                "refus": [f"l'epreuve n'a pas rendu la main en {timeout} s — boucle sans "
                          "fin, ou candidate trop lente pour un banc qui doit en passer "
                          "des dizaines"],
                "reserves": [], "mesures": {}}
    except OSError as exc:
        return {"module": module, "ok": False,
                "refus": [f"epreuve impossible a lancer : {exc}"],
                "reserves": [], "mesures": {}}

    sortie = fini.stdout.decode("utf-8", errors="replace").strip()
    erreurs = fini.stderr.decode("utf-8", errors="replace").strip()
    try:
        return json.loads(sortie.splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        detail = erreurs.splitlines()[-1] if erreurs else "aucune sortie"
        return {"module": module, "ok": False,
                "refus": [f"l'epreuve est morte sans rendre de rapport : {detail}"],
                "reserves": [], "mesures": {}, "journal": erreurs[-2000:]}


# --- cote enfant ------------------------------------------------------------------------

def _serie_temoin(timeframe_voulu: str = ""):
    """Une tranche reelle de train. Jamais le hold-out : le regarder, c'est le bruler.

    `timeframe_voulu` place une serie en tete des essais sans retirer les autres : une
    candidate intraday demande du 5m, et si le lake ne l'a pas, mieux vaut une epreuve sur
    autre chose qu'une candidate non eprouvee.
    """
    from beta.lake import catalogue, lecture
    from beta.protocole import holdout

    coupure = holdout.borner_train()
    essais = [(PAIRE_TEMOIN, timeframe_voulu or TIMEFRAME_TEMOIN)]
    etat = catalogue.etat()
    if not etat.empty:
        essais += [(ligne["paire"], ligne["timeframe"])
                   for ligne in etat.to_dict("records")]
    for paire, timeframe in essais:
        try:
            df = lecture.load(paire, timeframe, fin=coupure)
        except Exception:                                  # noqa: BLE001 - on essaie la
            continue                                       # serie suivante, pas d'arret
        if len(df) >= 200:
            combien = BOUGIES_PAR_TIMEFRAME.get(timeframe, BOUGIES_TEMOIN)
            return df.tail(combien).copy(), f"{paire} {timeframe}"
    raise EpreuveError("aucune serie du lake ne permet d'eprouver une candidate — "
                       "construire le lake d'abord (`python beta.py lake`)")


def _serie_reelle(actif: str, timeframe: str, debut: str = "", fin: str = ""):
    """La serie que la candidate tradera, chargee comme le moteur la charge, train seulement.

    Aucun repli : si elle manque, l'epreuve s'arrete. Se rabattre en silence sur BTC rendrait
    un rapport « valide » qui ne dit rien de la serie mesuree — la panne du 04/11.
    """
    from beta.moteur import pipeline
    from beta.protocole import holdout

    timeframe = timeframe or TIMEFRAME_TEMOIN
    series = pipeline.charger_series((actif,), timeframe, debut=debut or None,
                                     fin=holdout.borner_train(fin or None))
    df = series.get(actif)
    if df is None or df.empty:
        raise EpreuveError(f"serie demandee indisponible : {actif} {timeframe} (train"
                           f"{', depuis ' + debut if debut else ''}) — l'epreuve ne se rabat "
                           "sur aucune autre serie")
    return df, f"{actif} {timeframe}"


# Ancien nom, garde pour les appelants d'avant le 04/11.
_comparer = comparer


def eprouver(module: str, timeframe: str = "", actif: str = "", debut: str = "",
             fin: str = "") -> dict:
    """L'epreuve complete, dans le processus courant. Appelee par `main()`.

    Avec `actif` : sur la serie reelle, toute la periode. Sans : sur une serie temoin, et le
    rapport le dit dans ses reserves.
    """
    from beta.moteur import causalite, registre

    mesures: dict = {}

    candidate = registre.charger(module)                   # leve si creer() est absent
    mesures["candidate"] = candidate.nom
    mesures["hypothese"] = candidate.hypothese
    mesures["empreinte"] = candidate.empreinte

    if actif:
        df, temoin = _serie_reelle(actif, timeframe, debut, fin)
    else:
        df, temoin = _serie_temoin(timeframe)
    mesures["temoin"] = f"{temoin}, {len(df)} bougies"
    mesures["serie_reelle"] = bool(actif)

    # 1 a 3. contrat, determinisme, causalite — le meme coeur que le moteur
    epreuve = causalite.eprouver_serie(candidate, df)
    refus: list[str] = list(epreuve["refus"])
    reserves: list[str] = list(epreuve["reserves"])
    if not actif:
        reserves.append(f"eprouvee sur une serie TEMOIN ({temoin}), pas sur celle que la "
                        "candidate tradera : `--actif` et `--timeframe` pour l'eprouver sur "
                        "la vraie (le moteur la reeprouve de toute facon sur les series du "
                        "run avant de mesurer)")

    # 4. non-degenerescence
    mesures.update(epreuve["mesures"])
    n_signaux = mesures["n_signaux"]
    if n_signaux == 0:
        refus.append(f"aucun signal sur {'la serie' if actif else 'la tranche temoin'} "
                     f"({temoin}) : il n'y a rien a mesurer")
    elif n_signaux < MIN_SIGNAUX:
        reserves.append(f"{n_signaux} signaux seulement sur {len(df)} bougies — la "
                        "candidate est peut-etre juste, mais elle sera INDECIDABLE faute "
                        "de puissance")
    if mesures["part_en_position"] > PART_EN_POSITION_MAX:
        reserves.append(f"en position {100 * mesures['part_en_position']:.1f} % du temps : "
                        "c'est un hold deguise, et S8 le comparera au hold")

    return {"module": module, "ok": not refus, "refus": refus, "reserves": reserves,
            "mesures": mesures}


def main(argv: list[str] | None = None) -> int:
    """Point d'entree du sous-processus. TOUT ce qui rate sort en rapport JSON, jamais en
    trace : l'appelant lit une seule ligne, il n'a pas a analyser un traceback."""
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr,
                        format="%(levelname)-7s %(name)s %(message)s")

    parseur = argparse.ArgumentParser(prog="beta.atelier.epreuve")
    parseur.add_argument("module")
    parseur.add_argument("--timeframe", default="",
                         help="unite de temps de la serie (defaut : 4h). "
                              "Une candidate intraday ne signale rien en 4h.")
    parseur.add_argument("--actif", default="",
                         help="la serie que la candidate tradera (ex : XAU_SPOT, NDX, BTC) ; "
                              "sans elle, l'epreuve tourne sur une serie temoin")
    parseur.add_argument("--debut", default="", help="debut de la periode (avec --actif)")
    parseur.add_argument("--fin", default="",
                         help="fin de la periode (avec --actif), bornee au train")
    arguments = parseur.parse_args(argv)

    try:
        rapport = eprouver(arguments.module, arguments.timeframe, arguments.actif,
                           arguments.debut, arguments.fin)
    except Exception as exc:                               # noqa: BLE001 - c'est le but
        rapport = {"module": arguments.module, "ok": False,
                   "refus": [f"{type(exc).__name__} : {exc}"], "reserves": [],
                   "mesures": {}}
    sys.stdout.write(json.dumps(rapport, ensure_ascii=False, default=str) + "\n")
    return 0 if rapport["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
