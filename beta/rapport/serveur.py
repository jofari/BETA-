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


ROUTES = {
    "/api/lake": lambda p: donnees_lake(),
    "/api/strategie": lambda p: donnees_strategie(bool(p.get("holdout"))),
    "/api/protocole": lambda p: donnees_protocole(),
}


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
