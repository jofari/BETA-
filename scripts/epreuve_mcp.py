"""P5 — l'epreuve du pont MCP : un vrai sous-processus, un vrai JSON-RPC, sur stdio.

Pourquoi ce script existe alors que `tests/test_ponts.py` couvre deja P2 et P3 : ces
tests-la appellent `serveur.traiter()` **en direct, dans le processus de pytest**. Ils
prouvent que la logique des outils est juste. Ils ne prouvent RIEN du transport — ni que le
module se lance en `-m`, ni que sys.path est bon depuis un autre repertoire, ni qu'une
sortie non-ASCII passe la console cp1252, ni qu'une erreur d'outil revient en reponse
plutot qu'en mort du serveur. Or c'est exactement la ou un pont casse : pas dans sa logique,
dans son branchement.

    & C:\\Users\\jofar\\venvs\\arit\\Scripts\\python.exe scripts/epreuve_mcp.py

Sept epreuves, dont deux qui comptent plus que les autres :

- **le garde-fou P3 traverse le transport** : une candidate deposee par MCP, dont
  l'hypothese n'est pas preenregistree, doit recevoir un REFUS. Un agent qui contourne le
  protocole par le pont annule le protocole entier.
- **le serveur survit a ses propres erreurs** : apres un outil inconnu et un JSON casse, la
  requete suivante doit repondre. Un serveur MCP qui meurt sur une exception laisse l'agent
  sans reponse et sans moyen de comprendre.
"""

from __future__ import annotations

import json
import logging
import pathlib
import subprocess
import sys
import threading

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from beta import config  # noqa: E402

log = logging.getLogger("beta.epreuve_mcp")

# Au-dela, c'est que le serveur est bloque : on le tue plutot que d'attendre indefiniment
# une ligne qui ne viendra pas. Un backtest n'est pas cense tourner dans cette epreuve.
TIMEOUT_S = 90

# Candidate jetable deposee par le pont pour verifier P3. Le nom respecte le motif impose
# par `beta_submit_strategy` ; le fichier est retire dans le `finally`, et son absence est
# elle-meme verifiee a la fin.
MODULE_JETABLE = "epreuve_mcp_jetable"
HYPOTHESE_INEXISTANTE = "ZZ_inexistante"

CANDIDATE_JETABLE = '''"""Candidate jetable de l'epreuve MCP. Supprimee par le script."""

from __future__ import annotations

import pandas as pd

from beta.moteur.contrats import Candidate


def signaux(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"sens": pd.Series(0, index=df.index, dtype=int)})


def creer() -> Candidate:
    return Candidate(nom="epreuve_mcp", hypothese="__HYPOTHESE__", signaux=signaux,
                     description="jetable")
'''.replace("__HYPOTHESE__", HYPOTHESE_INEXISTANTE)


class EpreuveError(RuntimeError):
    """Une epreuve a echoue : le pont ne fait pas ce qu'il annonce."""


class Client:
    """Un client MCP minimal : ecrit une ligne JSON, lit une ligne JSON."""

    def __init__(self, processus: subprocess.Popen) -> None:
        self.processus = processus
        self.compteur = 0

    def envoyer(self, methode: str, params: dict | None = None,
                notification: bool = False) -> dict | None:
        requete: dict = {"jsonrpc": "2.0", "method": methode}
        if params is not None:
            requete["params"] = params
        if not notification:
            self.compteur += 1
            requete["id"] = self.compteur
        try:
            self.processus.stdin.write(json.dumps(requete, ensure_ascii=False) + "\n")
            self.processus.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise EpreuveError(f"le serveur n'accepte plus d'entree : {exc}") from exc
        if notification:
            return None
        ligne = self.processus.stdout.readline()
        if not ligne:
            raise EpreuveError(f"le serveur s'est tu apres `{methode}` — il est mort")
        try:
            return json.loads(ligne)
        except json.JSONDecodeError as exc:
            raise EpreuveError(f"reponse illisible apres `{methode}` : {ligne[:200]}") from exc

    def envoyer_brut(self, texte: str) -> dict:
        """Une ligne qui n'est pas du JSON. Le serveur doit repondre -32700, pas mourir."""
        self.processus.stdin.write(texte + "\n")
        self.processus.stdin.flush()
        ligne = self.processus.stdout.readline()
        if not ligne:
            raise EpreuveError("le serveur est mort sur un JSON casse")
        return json.loads(ligne)

    def appeler(self, outil: str, **arguments) -> dict:
        return self.envoyer("tools/call", {"name": outil, "arguments": arguments})


def charge(reponse: dict) -> dict:
    """Le contenu texte d'une reponse `tools/call`, re-decode. Leve si c'est une erreur."""
    if "error" in reponse:
        raise EpreuveError(f"erreur inattendue : {reponse['error'].get('message')}")
    texte = reponse["result"]["content"][0]["text"]
    return json.loads(texte)


def message_erreur(reponse: dict) -> str:
    if "error" not in reponse:
        raise EpreuveError(f"une erreur etait attendue, reponse recue : "
                           f"{json.dumps(reponse)[:300]}")
    return str(reponse["error"].get("message", ""))


# --- les epreuves -----------------------------------------------------------------------

def epreuve_poignee_de_main(client: Client) -> str:
    reponse = client.envoyer("initialize", {"protocolVersion": "2024-11-05",
                                            "capabilities": {},
                                            "clientInfo": {"name": "epreuve", "version": "0"}})
    info = reponse["result"]["serverInfo"]
    if info["name"] != "beta":
        raise EpreuveError(f"serverInfo.name = {info['name']!r}, attendu 'beta'")
    client.envoyer("notifications/initialized", {}, notification=True)
    return f"initialize -> {info['name']} {info['version']}"


def epreuve_inventaire(client: Client) -> str:
    outils = client.envoyer("tools/list")["result"]["tools"]
    noms = {o["name"] for o in outils}
    attendus = {"beta_data_catalog", "beta_load_ohlcv", "beta_results",
                "beta_register_edge", "beta_submit_strategy", "beta_run_backtest",
                "beta_publish"}
    if noms != attendus:
        raise EpreuveError(f"outils annonces {sorted(noms)}, attendus {sorted(attendus)}")
    sans_schema = [o["name"] for o in outils if o.get("inputSchema", {}).get("type") != "object"]
    if sans_schema:
        raise EpreuveError(f"outils sans schema exploitable : {sans_schema}")
    return f"tools/list -> {len(outils)} outils, tous avec schema"


def epreuve_lecture(client: Client) -> str:
    catalogue = charge(client.appeler("beta_data_catalog"))
    if not catalogue.get("n_series"):
        raise EpreuveError("catalogue vide — construire le lake avant l'epreuve")
    paire = catalogue["series"][0]["paire"]
    ohlcv = charge(client.appeler("beta_load_ohlcv", paire=paire, timeframe="1d", limite=5))
    if ohlcv["n_rendu"] != 5 or not ohlcv["lignes"]:
        raise EpreuveError(f"beta_load_ohlcv rend {ohlcv['n_rendu']} lignes, 5 attendues")
    if "close" not in ohlcv["lignes"][0]:
        raise EpreuveError(f"colonnes inattendues : {sorted(ohlcv['lignes'][0])}")
    return (f"lecture -> {catalogue['n_series']} series au catalogue, "
            f"{paire} 1d relu par le pont")


def epreuve_verrou_du_protocole(client: Client) -> str:
    """Le verrou d'experiences.exiger() doit revenir en ERREUR, pas en resultat vide."""
    reponse = client.appeler("beta_publish", id=HYPOTHESE_INEXISTANTE,
                             verdict="confirmee", resultat="tentative de contournement")
    message = message_erreur(reponse)
    if "preenregistr" not in message.lower():
        raise EpreuveError(f"refus attendu pour cause de preenregistrement, recu : {message}")
    return "beta_publish sur une experience inconnue -> refuse"


def epreuve_garde_fou_p3(client: Client) -> str:
    """LE point du pont : deposer une candidate ne suffit pas a pouvoir la mesurer."""
    depot = charge(client.appeler("beta_submit_strategy", module=MODULE_JETABLE,
                                  code=CANDIDATE_JETABLE, ecraser=True))
    if depot["hypothese"] != HYPOTHESE_INEXISTANTE:
        raise EpreuveError(f"depot inattendu : {depot}")
    reponse = client.appeler("beta_run_backtest", module=MODULE_JETABLE, paires=["BTC"],
                             timeframe="1d")
    message = message_erreur(reponse)
    if "preenregistr" not in message.lower():
        raise EpreuveError(f"le backtest aurait du etre refuse faute de preenregistrement, "
                           f"refus recu : {message!r}")
    return "candidate deposee puis backtest REFUSE faute de preenregistrement (P3)"


def epreuve_candidate_refusee(client: Client) -> str:
    """Une candidate qui ne respecte pas le contrat ne doit pas rester sur le disque."""
    reponse = client.appeler("beta_submit_strategy", module="epreuve_mcp_cassee",
                             code="def pas_creer():\n    return 42\n", ecraser=True)
    message_erreur(reponse)
    reste = config.RACINE / "beta" / "candidates" / "epreuve_mcp_cassee.py"
    if reste.exists():
        reste.unlink(missing_ok=True)
        raise EpreuveError("la candidate refusee est restee sur le disque")
    return "candidate sans creer() -> refusee ET fichier retire"


def epreuve_survie(client: Client) -> str:
    """Outil inconnu, JSON casse, puis une requete valide : le serveur doit repondre."""
    message_erreur(client.appeler("outil_qui_n_existe_pas"))
    casse = client.envoyer_brut("{ceci n'est pas du json")
    if casse.get("error", {}).get("code") != -32700:
        raise EpreuveError(f"code d'erreur attendu -32700, recu {casse}")
    apres = client.envoyer("tools/list")
    if "result" not in apres:
        raise EpreuveError("le serveur ne repond plus apres ses propres erreurs")
    return "outil inconnu + JSON casse -> erreurs rendues, serveur toujours debout"


EPREUVES = (epreuve_poignee_de_main, epreuve_inventaire, epreuve_lecture,
            epreuve_verrou_du_protocole, epreuve_garde_fou_p3,
            epreuve_candidate_refusee, epreuve_survie)


def _nettoyer() -> None:
    for module in (MODULE_JETABLE, "epreuve_mcp_cassee"):
        (config.RACINE / "beta" / "candidates" / f"{module}.py").unlink(missing_ok=True)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    _nettoyer()
    config.DATA.mkdir(parents=True, exist_ok=True)
    journal = config.DATA / "epreuve_mcp.err.log"

    # stderr dans un fichier plutot que dans un tube : un tube que personne ne vide finit
    # par se remplir, et le serveur se bloque en ecrivant son log au lieu de repondre.
    with journal.open("w", encoding="utf-8") as erreurs:
        processus = subprocess.Popen(                        # noqa: S603
            [sys.executable, "-m", "beta.mcp.serveur"],
            cwd=str(RACINE), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=erreurs, text=True, encoding="utf-8", bufsize=1)
        bourreau = threading.Timer(TIMEOUT_S, processus.kill)
        bourreau.daemon = True
        bourreau.start()

        client = Client(processus)
        echecs = []
        try:
            for epreuve in EPREUVES:
                nom = epreuve.__name__.replace("epreuve_", "")
                try:
                    log.info("[ok]     %-22s %s", nom, epreuve(client))
                except EpreuveError as exc:
                    log.error("[ECHEC]  %-22s %s", nom, exc)
                    echecs.append(nom)
        finally:
            bourreau.cancel()
            _nettoyer()
            try:
                processus.stdin.close()
                processus.wait(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                processus.kill()

    if processus.returncode not in (0, None):
        log.warning("le serveur est sorti en %s — voir %s", processus.returncode, journal)
    if echecs:
        log.error("%d epreuve(s) en echec : %s", len(echecs), ", ".join(echecs))
        return 1
    log.info("pont MCP : %d epreuves passees, transport compris", len(EPREUVES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
