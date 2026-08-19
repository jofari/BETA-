"""Le dashboard de BETA : ce que contient le lake, et ce que les strategies ont donne.

Sert `web/` et une poignee d'endpoints JSON. Aucune donnee n'est calculee ici : le serveur
relit le lake et delegue a `stats.descriptif`. Il est donc jetable — le supprimer ne perd
rien, et c'est voulu.

Deux garde-fous repris d'ALPHA, tous deux payes par une panne reelle la-bas :

1. **`allow_reuse_address = False`.** Sous Windows, `SO_REUSEADDR` ne contourne pas
   seulement TIME_WAIT : il laisse un second processus se lier a un port DEJA ecoute. Deux
   serveurs tournaient alors en parallele sans que rien ne le signale.
2. **Le client ne demande jamais un chemin de fichier.** Il appelle des routes nommees ; le
   serveur choisit quoi lire. Le statique est confine a `web/` par `relative_to`.

Le hold-out est EXCLU par defaut de tout ce qui est affiche. On peut l'inclure
explicitement (`?holdout=1`), et l'interface le dit alors en clair — un hold-out qu'on
regarde sans le savoir est un hold-out brule.
"""

from __future__ import annotations

import http.server
import json
import logging
import math
import mimetypes
import pathlib
import socketserver
import threading
import webbrowser
from urllib.parse import parse_qs, urlparse

import pandas as pd

from beta.lake import catalogue, strategie
from beta.protocole import experiences, holdout
from beta.stats import descriptif

log = logging.getLogger("beta.rapport")

WEB = pathlib.Path(__file__).resolve().parent / "web"
HOTE, PORT = "127.0.0.1", 7474      # 7373 est pris par ALPHA


class ServeurExclusif(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """Refuse un port deja en ecoute (voir le docstring du module)."""

    allow_reuse_address = False
    daemon_threads = True


def _propre(valeur):
    """JSON ne connait ni NaN, ni Infinity, ni Timestamp. `null` plutot qu'un plantage."""
    if isinstance(valeur, float):
        return None if math.isnan(valeur) or math.isinf(valeur) else round(valeur, 6)
    if isinstance(valeur, pd.Timestamp):
        return valeur.isoformat()
    if valeur is None or valeur is pd.NaT:
        return None
    if isinstance(valeur, (bool, int, str)):
        return valeur
    return str(valeur)


def propre(charge):
    """`_propre` applique en profondeur : dicts, listes, et scalaires imbriques.

    La fiche d'un run est une structure a cinq niveaux venue de fichiers JSON et parquet.
    Un seul NaN au fond — un CAGR non calculable, par exemple — suffit a faire echouer
    `JSON.parse` dans le navigateur, et la page reste blanche sans rien dire. Nettoyer
    scalaire par scalaire a l'entree de chaque route est le seul endroit ou l'on est sur de
    ne rien oublier.
    """
    if isinstance(charge, dict):
        return {cle: propre(valeur) for cle, valeur in charge.items()}
    if isinstance(charge, (list, tuple)):
        return [propre(valeur) for valeur in charge]
    return _propre(charge)


def _table(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    return [{c: _propre(v) for c, v in ligne.items()}
            for ligne in df.to_dict(orient="records")]


# --- ce que chaque route repond -------------------------------------------------------

def donnees_lake() -> dict:
    etat = catalogue.etat()
    if etat.empty:
        return {"series": [], "resume": {}}
    return {
        "series": _table(etat),
        "resume": {
            "series": len(etat),
            "paires": int(etat["paire"].nunique()),
            "bougies": int(etat["n_bougies"].sum()),
            "suspectes": int(etat["suspect"].sum()),
            "debut": _propre(etat["debut"].min()),
            "fin": _propre(etat["fin"].max()),
            # Borne commune : un backtest multi-paires ne peut pas aller au-dela de la
            # serie qui s'arrete le plus tot. C'est ce chiffre-la qui contraint, pas le max.
            "fin_commune": _propre(etat["fin"].min()),
        },
    }


def donnees_strategie(inclure_holdout: bool = False) -> dict:
    try:
        trades = strategie.lire("trades", train_seulement=not inclure_holdout)
        evaluations = strategie.lire("evaluations", train_seulement=not inclure_holdout)
    except strategie.StrategieError as exc:
        return {"erreur": str(exc)}

    trades = trades.sort_values("ts_entree")
    r = trades["r"].fillna(0.0)
    return {
        "portee": "tout, hold-out compris" if inclure_holdout else "train seulement",
        "holdout_debut": str(holdout.DEBUT.date()),
        "resume": {c: _propre(v) for c, v in descriptif.resumer(trades).items()},
        "par_strategie": _table(descriptif.par(trades, "strategie")),
        "par_paire": _table(descriptif.par(trades, "paire")),
        "par_sens": _table(descriptif.par(trades, "sens")),
        "raisons_sortie": _table(descriptif.raisons_de_sortie(trades)),
        "raisons_rejet": _table(descriptif.raisons_de_rejet(evaluations)),
        # Courbe d'equity en R cumules : les trades sans stop retrouve comptent 0 plutot
        # que de trouer la courbe — leur nombre est visible dans `n` moins `n_avec_r`.
        "equity": [{"ts": _propre(t), "r_cumule": _propre(v)}
                   for t, v in zip(trades["ts_entree"], r.cumsum(), strict=True)],
        "distribution_r": [_propre(v) for v in trades["r"].dropna()],
        "n_evaluations": len(evaluations),
    }


def donnees_protocole() -> dict:
    try:
        etat = experiences.etat()
        compteur = experiences.compteur()
    except experiences.ProtocoleError as exc:
        return {"erreur": str(exc)}
    return {"compteur": compteur, "dette_initiale": experiences.ESSAIS_INITIAUX,
            "experiences": [{"id": i, "statut": e.get("statut"), "date": e.get("date"),
                             "hypothese": e.get("hypothese"), "verdict": e.get("verdict")}
                            for i, e in etat.items()]}


def donnees_runs() -> dict:
    from beta.rapport import runs
    return {"runs": runs.liste()}


def donnees_run(params: dict) -> dict:
    from beta.rapport import runs
    identifiant = (params.get("id") or [""])[0]
    if not identifiant:
        raise ValueError("parametre `id` manquant")
    return runs.fiche(identifiant)


def donnees_atelier() -> dict:
    from beta.rapport import atelier
    return atelier.inventaire()


def donnees_candidate(params: dict) -> dict:
    from beta.rapport import atelier
    module = (params.get("module") or [""])[0]
    if not module:
        raise ValueError("parametre `module` manquant")
    return atelier.code_de(module)


_ROUTES_BRUTES = {
    "/api/lake": lambda p: donnees_lake(),
    "/api/strategie": lambda p: donnees_strategie(bool(p.get("holdout"))),
    "/api/protocole": lambda p: donnees_protocole(),
    "/api/runs": lambda p: donnees_runs(),
    "/api/run": donnees_run,
    "/api/atelier": lambda p: donnees_atelier(),
    "/api/candidate": donnees_candidate,
}

# Toutes les routes passent par `propre` : aucune ne peut renvoyer de NaN au navigateur,
# et une nouvelle route ne peut pas oublier de le faire.
ROUTES = {chemin: (lambda p, f=fonction: propre(f(p)))
          for chemin, fonction in _ROUTES_BRUTES.items()}

# Corps maximal accepte en POST. Le client n'envoie qu'un nom d'action et un run_id :
# au-dela, c'est que quelque chose d'autre parle au serveur.
MAX_CORPS_POST = 4096

# L'atelier fait exception : il transporte le CODE d'une candidate. Le plafond reste bas —
# une candidate est une regle nue, pas un programme — mais il ne peut pas etre celui d'un
# nom d'action.
MAX_CORPS_ATELIER = 64 * 1024


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "BETA"

    def log_message(self, fmt: str, *args) -> None:      # noqa: A002
        log.debug("%s %s", self.address_string(), fmt % args)

    def _envoyer(self, code: int, corps: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(corps)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(corps)
        except (BrokenPipeError, ConnectionResetError):
            pass                      # onglet ferme pendant l'envoi : sans consequence

    def _json(self, charge, code: int = 200) -> None:
        self._envoyer(code, json.dumps(charge, ensure_ascii=False).encode("utf-8"),
                      "application/json; charset=utf-8")

    def _statique(self, relatif: str) -> None:
        cible = (WEB / relatif).resolve()
        try:
            cible.relative_to(WEB.resolve())      # confine a web/, quoi qu'on demande
        except ValueError:
            return self._json({"erreur": "chemin refuse"}, 403)
        if not cible.is_file():
            return self._json({"erreur": "introuvable"}, 404)
        ctype = mimetypes.guess_type(cible.name)[0] or "application/octet-stream"
        try:
            self._envoyer(200, cible.read_bytes(), ctype)
        except OSError as exc:
            self._json({"erreur": str(exc)}, 500)

    def do_GET(self) -> None:        # noqa: N802 — impose par BaseHTTPRequestHandler
        analyse = urlparse(self.path)
        route = analyse.path.rstrip("/") or "/"
        params = parse_qs(analyse.query)
        if route in ("/", "/index.html"):
            return self._statique("index.html")
        if route in ROUTES:
            try:
                return self._json(ROUTES[route](params))
            except Exception as exc:                     # noqa: BLE001
                log.exception("route %s", route)
                return self._json({"erreur": f"{type(exc).__name__}: {exc}"}, 500)
        return self._statique(route.lstrip("/"))

    def _corps(self, maximum: int):
        """Lit le corps d'un POST, borne. Rend None APRES avoir repondu, en cas de refus."""
        try:
            taille = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._json({"erreur": "longueur invalide"}, 400)
            return None
        if taille > maximum:
            self._json({"erreur": f"corps trop grand (maximum {maximum} octets)"}, 413)
            return None
        try:
            return json.loads(self.rfile.read(taille) or b"{}")
        except (json.JSONDecodeError, OSError) as exc:
            self._json({"erreur": f"corps illisible : {exc}"}, 400)
            return None

    def do_POST(self) -> None:       # noqa: N802 — impose par BaseHTTPRequestHandler
        """Deux routes, deux listes blanches, aucune commande venue du client.

        `/api/action` porte un nom d'action et un run_id. `/api/atelier` porte un nom de
        geste et le code d'une candidate — du CODE, donc, mais qui ne s'execute que dans le
        sous-processus de l'epreuve, et jamais avant que le sas ait lu ce qu'il contient.
        """
        route = urlparse(self.path).path.rstrip("/")
        if route == "/api/atelier":
            return self._post_atelier()
        if route != "/api/action":
            return self._json({"erreur": "route inconnue"}, 404)

        from beta.rapport import actions, runs
        charge = self._corps(MAX_CORPS_POST)
        if charge is None:
            return None

        action = str(charge.get("action") or "")
        run_id = str(charge.get("run_id") or "")
        try:
            verdict = runs.fiche(run_id)["verdict"]
            return self._json(actions.executer(action, verdict))
        except FileNotFoundError as exc:
            return self._json({"erreur": str(exc)}, 404)
        except actions.ActionError as exc:
            return self._json({"erreur": str(exc)}, 400)
        except Exception as exc:                         # noqa: BLE001
            log.exception("action %s", action)
            return self._json({"erreur": f"{type(exc).__name__}: {exc}"}, 500)

    def _post_atelier(self):
        from beta.atelier import depot
        from beta.rapport import atelier

        charge = self._corps(MAX_CORPS_ATELIER)
        if charge is None:
            return None
        geste = str(charge.get("geste") or "")
        try:
            return self._json(propre(atelier.executer(geste, charge)))
        except (atelier.AtelierError, depot.DepotError) as exc:
            return self._json({"erreur": str(exc)}, 400)
        except Exception as exc:                         # noqa: BLE001
            log.exception("geste d'atelier %s", geste)
            return self._json({"erreur": f"{type(exc).__name__}: {exc}"}, 500)


def servir(hote: str = HOTE, port: int = PORT, ouvrir: bool = True) -> int:
    try:
        serveur = ServeurExclusif((hote, port), Handler)
    except OSError as exc:
        log.error("port %d indisponible (%s) — un BETA tourne peut-etre deja", port, exc)
        return 1
    url = f"http://{hote}:{port}"
    log.info("BETA sur %s — Ctrl+C pour arreter", url)
    if ouvrir:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        log.info("arret")
    finally:
        serveur.server_close()
    return 0
