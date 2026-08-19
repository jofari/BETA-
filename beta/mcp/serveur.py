"""P2/P3 — serveur MCP stdio de BETA, en JSON-RPC sur la bibliotheque standard.

Aucune dependance : le protocole MCP est du JSON-RPC 2.0 ligne par ligne sur stdin/stdout,
et l'ecrire a la main coute moins cher que d'ajouter un SDK au projet pour sept outils. Le
choix suit celui d'ALPHA, ou la meme decision a ete prise pour les memes raisons.

Sept outils, deux familles :

    lecture     beta_data_catalog, beta_load_ohlcv, beta_results
    ecriture    beta_register_edge, beta_submit_strategy, beta_run_backtest, beta_publish

**Le garde-fou P3 est le point du module.** `beta_run_backtest` passe par `contrats.Run`,
qui appelle `protocole.exiger()` : un agent qui demande un backtest sans avoir preenregistre
son hypothese recoit un refus, pas un resultat. Il n'existe volontairement aucun parametre
pour le contourner. Un agent capable de lancer mille backtests sans preenregistrement
produirait mille faux gagnants en une nuit, et le compteur d'essais — donc toute la batterie
statistique — ne vaudrait plus rien.

Lancement (a declarer dans la configuration MCP du client) :

    C:\\Users\\jofar\\venvs\\arit\\Scripts\\python.exe -m beta.mcp.serveur
"""

from __future__ import annotations

import json
import logging
import sys
import traceback
from typing import Any, Callable

from beta import config

log = logging.getLogger("beta.mcp")

VERSION_PROTOCOLE = "2024-11-05"
NOM = "beta"
VERSION = "1.0.0"

# Plafond de lignes rendues par un appel. Un agent qui demande cinq ans de 5m recevrait
# 500 000 lignes dans son contexte : le refus vaut mieux que la troncature silencieuse.
MAX_LIGNES = 2000

OUTILS: dict[str, dict] = {}


def outil(nom: str, description: str, schema: dict) -> Callable:
    """Declare un outil MCP. Le schema est ce que l'agent voit ; il doit etre exact."""
    def decorateur(fonction: Callable) -> Callable:
        OUTILS[nom] = {"nom": nom, "description": description, "schema": schema,
                       "fonction": fonction}
        return fonction
    return decorateur


# --- lecture --------------------------------------------------------------------------

@outil("beta_data_catalog",
       "Ce que contient le lake : paires, timeframes, couverture reelle, trous declares. "
       "A lire AVANT toute mesure — une serie marquee suspecte fausse silencieusement un "
       "backtest.",
       {"type": "object", "properties": {}})
def _catalogue(**_) -> dict:
    from beta.lake import catalogue
    table = catalogue.etat()
    return {"n_series": len(table), "series": table.to_dict("records")}


@outil("beta_load_ohlcv",
       "OHLCV d'une paire du lake, en UTC. Tout timeframe multiple de 5 min est derive a "
       "la volee. Bornes inclusives.",
       {"type": "object",
        "properties": {"paire": {"type": "string", "description": "BTC, ETH, SOL, BNB, LINK, XRP"},
                       "timeframe": {"type": "string", "description": "5m, 1h, 4h, 1d, ou tout multiple de 5m"},
                       "debut": {"type": "string"}, "fin": {"type": "string"},
                       "limite": {"type": "integer", "description": f"defaut {MAX_LIGNES}"}},
        "required": ["paire", "timeframe"]})
def _ohlcv(paire: str, timeframe: str, debut: str | None = None, fin: str | None = None,
           limite: int = MAX_LIGNES, **_) -> dict:
    from beta.lake import lecture
    df = lecture.load(paire, timeframe, debut=debut, fin=fin)
    limite = min(int(limite), MAX_LIGNES)
    tronque = len(df) > limite
    extrait = df.tail(limite) if tronque else df
    return {"paire": paire, "timeframe": timeframe, "n_total": len(df),
            "n_rendu": len(extrait), "tronque_aux_plus_recentes": tronque,
            "lignes": json.loads(extrait.to_json(orient="records", date_format="iso"))}


@outil("beta_results",
       "Les verdicts deja rendus : issue, portes franchies ou echouees, reserves. "
       "Sans argument, rend la liste ; avec run_id, le detail complet de la batterie.",
       {"type": "object", "properties": {"run_id": {"type": "string"}}})
def _resultats(run_id: str | None = None, **_) -> dict:
    from beta.moteur.pipeline import RESULTATS
    if not RESULTATS.exists():
        return {"runs": [], "note": "aucun run enregistre"}
    if run_id:
        dossier = RESULTATS / run_id
        if not dossier.exists():
            raise ValueError(f"run inconnu : {run_id}")
        return {"verdict": _json(dossier / "verdict.json"),
                "batterie": _json(dossier / "batterie.json")}
    runs = []
    for dossier in sorted(RESULTATS.iterdir()):
        verdict = _json(dossier / "verdict.json")
        if verdict:
            runs.append({cle: verdict.get(cle) for cle in
                         ("run_id", "experience", "candidate", "issue", "split",
                          "portes_echouees", "portes_non_executees")})
    return {"n": len(runs), "runs": runs}


def _json(chemin) -> dict:
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


# --- ecriture -------------------------------------------------------------------------

@outil("beta_register_edge",
       "Preenregistre une hypothese AVANT de la mesurer. Obligatoire : sans elle, "
       "beta_run_backtest refuse de tourner. Ecrire ce qu'on cherche, la metrique, la "
       "regle de decision, et ce qu'on savait deja.",
       {"type": "object",
        "properties": {"id": {"type": "string", "description": "identifiant court, ex: R7"},
                       "hypothese": {"type": "string"},
                       "metrique_primaire": {"type": "string"},
                       "regle_de_decision": {"type": "object",
                                             "description": "ce qui vaut confirmee / infirmee / indecidable"},
                       "issue_attendue": {"type": "string"},
                       "mde_attendu": {"type": "number"},
                       "famille_taille": {"type": "integer"},
                       "deja_connu": {"type": "string",
                                      "description": "ce qui a DEJA ete regarde sur ces donnees. "
                                                     "Ne pas le remplir rend le preenregistrement sans valeur."}},
        "required": ["id", "hypothese", "metrique_primaire", "regle_de_decision"]})
def _preenregistrer(id: str, hypothese: str, metrique_primaire: str,  # noqa: A002
                    regle_de_decision: dict, **extra) -> dict:
    from beta.protocole import experiences
    autorises = ("issue_attendue", "mde_attendu", "famille_taille", "deja_connu")
    return experiences.preenregistrer(
        id, hypothese, metrique_primaire, regle_de_decision,
        **{cle: extra[cle] for cle in autorises if cle in extra})


@outil("beta_submit_strategy",
       "Depose une candidate dans beta/candidates/. Le fichier doit exposer creer() -> "
       "Candidate et ne rien importer du moteur hors contrats. Une candidate par fichier : "
       "c'est ce qui empeche qu'en corriger une casse les verdicts deja rendus sur les autres.",
       {"type": "object",
        "properties": {"module": {"type": "string", "description": "nom de fichier sans .py"},
                       "code": {"type": "string", "description": "contenu Python complet"},
                       "ecraser": {"type": "boolean"}},
        "required": ["module", "code"]})
def _deposer(module: str, code: str, ecraser: bool = False, **_) -> dict:
    import re

    from beta.moteur import registre
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,48}", module):
        raise ValueError("nom de module invalide : minuscules, chiffres et _ seulement")
    chemin = config.RACINE / "beta" / "candidates" / f"{module}.py"
    if chemin.exists() and not ecraser:
        raise ValueError(f"{module}.py existe deja — passer ecraser=true pour le remplacer, "
                         "en sachant que l'empreinte de la candidate changera et que les "
                         "verdicts deja rendus ne s'appliqueront plus")
    chemin.write_text(code, encoding="utf-8")
    try:
        candidate = registre.charger(module)
    except Exception as exc:                              # noqa: BLE001
        chemin.unlink(missing_ok=True)
        raise ValueError(f"candidate refusee et fichier retire : {exc}") from exc
    return {"module": module, "nom": candidate.nom, "hypothese": candidate.hypothese,
            "empreinte": candidate.empreinte, "chemin": str(chemin)}


@outil("beta_run_backtest",
       "Crible une candidate : triple barriere en espace-R, puis la batterie S1-S9. "
       "REFUSE de tourner si l'hypothese de la candidate n'est pas preenregistree. "
       "Rend un verdict confirmee / infirmee / indecidable, avec ses reserves.",
       {"type": "object",
        "properties": {"module": {"type": "string"},
                       "paires": {"type": "array", "items": {"type": "string"}},
                       "timeframe": {"type": "string"},
                       "take_profit_r": {"type": "number"},
                       "stop_atr": {"type": "number"},
                       "horizon_bougies": {"type": "integer"},
                       "n_chemins_synthetiques": {"type": "integer"}},
        "required": ["module"]})
def _backtest(module: str, paires: list | None = None, timeframe: str = "4h",
              n_chemins_synthetiques: int = 100, **options) -> dict:
    from beta.moteur import pipeline, registre
    from beta.moteur.contrats import Run
    candidate = registre.charger(module)
    connus = ("take_profit_r", "stop_atr", "horizon_bougies")
    run = Run(candidate=candidate, paires=tuple(paires or ("BTC", "ETH", "SOL", "BNB")),
              timeframe=timeframe,
              **{cle: options[cle] for cle in connus if cle in options})
    verdict, _ = pipeline.executer(run, n_chemins=n_chemins_synthetiques)
    return verdict.dict()


@outil("beta_publish",
       "Clot une experience au registre avec son verdict. A appeler apres beta_run_backtest, "
       "y compris — surtout — quand le resultat est indecidable : une experience qu'on "
       "n'ecrit que si elle marche transforme le compteur d'essais en mensonge.",
       {"type": "object",
        "properties": {"id": {"type": "string"}, "verdict": {"type": "string"},
                       "resultat": {"type": "string"}},
        "required": ["id", "verdict", "resultat"]})
def _publier(id: str, verdict: str, resultat: str, **_) -> dict:  # noqa: A002
    from beta.protocole import experiences
    entree = experiences.clore(id, verdict, resultat)
    return {**entree, "n_essais_cumules_apres": experiences.compteur()}


# --- boucle JSON-RPC --------------------------------------------------------------------

def _repondre(id_requete: Any, resultat: dict | None = None,
              erreur: dict | None = None) -> None:
    message = {"jsonrpc": "2.0", "id": id_requete}
    message["error" if erreur else "result"] = erreur or resultat
    sys.stdout.write(json.dumps(message, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()


def _liste_outils() -> dict:
    return {"tools": [{"name": o["nom"], "description": o["description"],
                       "inputSchema": o["schema"]} for o in OUTILS.values()]}


def _appeler(params: dict) -> dict:
    nom = params.get("name")
    if nom not in OUTILS:
        raise ValueError(f"outil inconnu : {nom}")
    sortie = OUTILS[nom]["fonction"](**(params.get("arguments") or {}))
    return {"content": [{"type": "text",
                         "text": json.dumps(sortie, ensure_ascii=False, indent=2,
                                            default=str)}]}


def traiter(requete: dict) -> dict | None:
    """Une requete JSON-RPC. Rend la reponse, ou None pour une notification."""
    methode = requete.get("method")
    if methode == "initialize":
        return {"protocolVersion": VERSION_PROTOCOLE, "capabilities": {"tools": {}},
                "serverInfo": {"name": NOM, "version": VERSION}}
    if methode == "tools/list":
        return _liste_outils()
    if methode == "tools/call":
        return _appeler(requete.get("params") or {})
    if methode and methode.startswith("notifications/"):
        return None
    raise ValueError(f"methode non supportee : {methode}")


def servir(entree=None, sortie=None) -> int:
    """Boucle stdio. Une erreur d'outil est une reponse d'erreur, jamais un arret.

    Un serveur MCP qui meurt sur une exception laisse l'agent sans reponse et sans moyen de
    comprendre : le refus doit lui revenir sous forme de message, c'est ce qui lui permet de
    corriger — par exemple d'aller preenregistrer son hypothese avant de relancer.
    """
    entree = entree or sys.stdin
    logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                        format="%(levelname)-7s %(name)s %(message)s")
    for ligne in entree:
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            requete = json.loads(ligne)
        except json.JSONDecodeError as exc:
            _repondre(None, erreur={"code": -32700, "message": f"JSON invalide : {exc}"})
            continue
        id_requete = requete.get("id")
        try:
            resultat = traiter(requete)
        except Exception as exc:                          # noqa: BLE001
            log.debug("%s", traceback.format_exc())
            if id_requete is not None:
                _repondre(id_requete, erreur={"code": -32000, "message": str(exc)})
            continue
        if id_requete is not None:
            _repondre(id_requete, resultat=resultat or {})
    return 0


if __name__ == "__main__":
    raise SystemExit(servir())
