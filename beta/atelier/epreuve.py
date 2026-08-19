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

    python -m beta.atelier.epreuve <module>          # rend un rapport JSON sur stdout
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("beta.atelier.epreuve")

RACINE = Path(__file__).resolve().parents[2]

# Tranche d'epreuve. Assez longue pour qu'une moyenne mobile de 200 ait un sens, assez
# courte pour que l'epreuve tienne en quelques secondes : on valide une candidate, on ne la
# mesure pas.
PAIRE_TEMOIN = "BTC"
TIMEFRAME_TEMOIN = "4h"
BOUGIES_TEMOIN = 1500

# Coupures de l'epreuve de causalite, en fraction de la tranche. Trois suffisent : une
# fonction qui regarde le futur echoue a la premiere, et les deux autres ne servent qu'a
# distinguer un debordement d'une bougie d'une normalisation globale.
COUPURES = (0.40, 0.70, 0.95)

# Au-dela, on considere que la candidate ne finira pas. Le chargement du parquet et l'import
# de pandas comptent dedans : le seuil est genereux a dessein, il vise la boucle infinie,
# pas la candidate lente.
TIMEOUT_S = 120

TOLERANCE = 1e-9            # colonnes auxiliaires : un ecart flottant n'est pas une faute
MIN_SIGNAUX = 5
PART_EN_POSITION_MAX = 0.98


class EpreuveError(RuntimeError):
    """L'epreuve n'a pas pu tourner. A distinguer d'une epreuve qui a tourne et refuse."""


# --- cote appelant ----------------------------------------------------------------------

def lancer(module: str, timeout: int = TIMEOUT_S) -> dict:
    """Lance l'epreuve dans un sous-processus. Ne leve pas : un echec est un rapport.

    Le rapport a toujours la meme forme, quoi qu'il arrive — `{ok, refus, reserves,
    mesures}`. Un appelant (CLI, dashboard, boucle de reparation d'un modele local) n'a
    donc jamais deux chemins a ecrire.
    """
    try:
        fini = subprocess.run(                                   # noqa: S603
            [sys.executable, "-m", "beta.atelier.epreuve", module],
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

def _serie_temoin():
    """Une tranche reelle de train. Jamais le hold-out : le regarder, c'est le bruler."""
    from beta.lake import catalogue, lecture
    from beta.protocole import holdout

    coupure = holdout.DEBUT.date().isoformat()
    essais = [(PAIRE_TEMOIN, TIMEFRAME_TEMOIN)]
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
            return df.tail(BOUGIES_TEMOIN).copy(), f"{paire} {timeframe}"
    raise EpreuveError("aucune serie du lake ne permet d'eprouver une candidate — "
                       "construire le lake d'abord (`python beta.py lake`)")


def _comparer(reference, tronque) -> tuple[int, int | None, float]:
    """Compare un prefixe de signaux au meme prefixe calcule sur la serie tronquee.

    Rend (nombre de lignes ou `sens` differe, premiere de ces lignes, plus grand ecart sur
    les colonnes auxiliaires). `sens` se compare a l'identique — c'est un entier, et c'est
    la seule colonne dont le moteur se sert. Les colonnes auxiliaires (`force`,
    `stop_distance`) tolerent un ecart flottant : un chiffre qui bouge de 1e-16 n'est pas
    une lecture du futur, c'est de l'arithmetique.
    """
    import numpy as np

    a = reference["sens"].to_numpy()
    b = tronque["sens"].to_numpy()
    differences = np.flatnonzero(a != b)
    premiere = int(differences[0]) if differences.size else None

    ecart = 0.0
    for colonne in (set(reference.columns) & set(tronque.columns)) - {"sens"}:
        try:
            x = reference[colonne].to_numpy(dtype=float)
            y = tronque[colonne].to_numpy(dtype=float)
        except (TypeError, ValueError):
            continue                                       # colonne non numerique : ignoree
        fini = np.isfinite(x) & np.isfinite(y)
        if fini.any():
            ecart = max(ecart, float(np.max(np.abs(x[fini] - y[fini]))))
        if (np.isnan(x) != np.isnan(y)).any():
            ecart = max(ecart, float("inf"))
    return int(differences.size), premiere, ecart


def eprouver(module: str) -> dict:
    """L'epreuve complete, dans le processus courant. Appelee par `main()`."""
    from beta.moteur import registre

    refus: list[str] = []
    reserves: list[str] = []
    mesures: dict = {}

    candidate = registre.charger(module)                   # leve si creer() est absent
    mesures["candidate"] = candidate.nom
    mesures["hypothese"] = candidate.hypothese
    mesures["empreinte"] = candidate.empreinte

    df, temoin = _serie_temoin()
    mesures["temoin"] = f"{temoin}, {len(df)} bougies"

    signaux = candidate.appliquer(df)                      # contrat : leve si viole

    # 2. determinisme
    encore = candidate.appliquer(df)
    ecarts, premiere, _ = _comparer(signaux, encore)
    if ecarts:
        refus.append(f"deux appels sur le MEME DataFrame donnent des signaux differents "
                     f"({ecarts} lignes, la premiere en {premiere}) : la candidate garde "
                     "un etat, elle n'est pas une fonction pure")

    # 3. causalite — le test qui compte
    for fraction in COUPURES:
        coupe = max(50, int(len(df) * fraction))
        if coupe >= len(df):
            continue
        try:
            partiel = candidate.appliquer(df.iloc[:coupe])
        except Exception as exc:                           # noqa: BLE001
            refus.append(f"la candidate echoue sur une serie tronquee a {coupe} bougies "
                         f"({type(exc).__name__}: {exc}) — elle suppose une longueur "
                         "minimale qu'un run ne lui garantit pas")
            continue
        ecarts, premiere, ecart_aux = _comparer(signaux.iloc[:coupe], partiel)
        if ecarts:
            refus.append(
                f"CAUSALITE : coupee a {coupe} bougies, la candidate change {ecarts} "
                f"signaux du passe (le premier en {premiere}). Une fonction causale ne le "
                "peut pas : elle lit donc quelque chose apres la ligne qu'elle decide")
        elif ecart_aux > TOLERANCE:
            reserves.append(f"coupee a {coupe}, une colonne auxiliaire bouge de "
                            f"{ecart_aux:.2e} — sans effet sur `sens`, mais a savoir")

    # 4. non-degenerescence
    sens = signaux["sens"]
    n_signaux = int((sens != 0).sum())
    mesures.update({"n_bougies": len(df), "n_signaux": n_signaux,
                    "n_long": int((sens > 0).sum()), "n_short": int((sens < 0).sum()),
                    "part_en_position": round(n_signaux / max(len(df), 1), 4)})
    if n_signaux == 0:
        refus.append("aucun signal sur la tranche temoin : il n'y a rien a mesurer")
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
    arguments = parseur.parse_args(argv)

    try:
        rapport = eprouver(arguments.module)
    except Exception as exc:                               # noqa: BLE001 - c'est le but
        rapport = {"module": arguments.module, "ok": False,
                   "refus": [f"{type(exc).__name__} : {exc}"], "reserves": [],
                   "mesures": {}}
    sys.stdout.write(json.dumps(rapport, ensure_ascii=False, default=str) + "\n")
    return 0 if rapport["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
