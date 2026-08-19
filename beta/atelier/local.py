"""Faire ecrire une candidate par un modele qui tourne SUR CETTE MACHINE.

Deux serveurs, un seul client : **Ollama** (11434) et **LM Studio** (1234). Rien d'autre —
et surtout rien qui sorte de la machine : une hypothese de trading est une idee de Jonas,
elle n'a pas a passer par un tiers pour devenir dix lignes de pandas.

Zero dependance : `urllib` de la bibliotheque standard suffit pour deux appels HTTP. Le
choix suit celui du serveur MCP et celui d'ALPHA — ajouter `requests` (et sa chaine de
sous-dependances) pour un POST JSON serait payer cher un confort d'ecriture.

**Ce que ce module ne fait pas, volontairement** : croire le modele. Rien de ce qu'il rend
n'est depose sans passer par `depot.valider()` — sas statique puis epreuve de causalite.
Un 7B ecrit spontanement `shift(-1)`, `center=True` et des normalisations sur la serie
entiere ; ce sont exactement les trois formes que l'atelier refuse. La boucle de reparation
lui RENVOIE le refus, ce qui suffit le plus souvent : le modele ne manque pas de
competence, il manque de la contrainte qu'on ne lui a pas dite.

> Une candidate ecrite par une machine est une source d'HYPOTHESES, jamais d'edge. Elle
> entre au banc par la meme porte que les autres : preenregistrement, compteur d'essais,
> batterie S1-S9. L'atelier abaisse le cout d'ecrire, jamais le seuil de confirmer.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request

from beta.atelier import depot, gabarit

log = logging.getLogger("beta.atelier.local")

# Les deux serveurs locaux, dans l'ordre d'essai de `detecter("auto")`. Ollama d'abord :
# c'est celui qui tourne en service sur ce poste.
BACKENDS = {
    "ollama": {
        "base": "http://127.0.0.1:11434",
        "modeles": "/api/tags",
        "chat": "/api/chat",
    },
    "lmstudio": {
        "base": "http://127.0.0.1:1234",
        "modeles": "/v1/models",
        "chat": "/v1/chat/completions",
    },
}

TIMEOUT_DETECTION_S = 3           # un serveur local repond en quelques millisecondes
TIMEOUT_GENERATION_S = 600        # un 7B sur portable met une a trois minutes par essai
TEMPERATURE = 0.2                 # on veut du code conforme, pas de l'invention
ESSAIS_PAR_DEFAUT = 3


class LocalError(RuntimeError):
    """Aucun serveur local, ou reponse inexploitable."""


# --- transport ---------------------------------------------------------------------------

def _http(url: str, charge: dict | None = None, timeout: float = TIMEOUT_DETECTION_S) -> dict:
    donnees = json.dumps(charge).encode("utf-8") if charge is not None else None
    requete = urllib.request.Request(                          # noqa: S310 - 127.0.0.1 en dur
        url, data=donnees, method="POST" if donnees else "GET",
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(requete, timeout=timeout) as reponse:  # noqa: S310
            return json.loads(reponse.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise LocalError(f"{url} a repondu {exc.code} : {detail}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise LocalError(f"{url} injoignable : {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LocalError(f"{url} n'a pas rendu du JSON : {exc}") from exc


def modeles(backend: str) -> list[str]:
    """Les modeles servis. Leve LocalError si le serveur ne repond pas."""
    conf = BACKENDS[backend]
    charge = _http(conf["base"] + conf["modeles"])
    if backend == "ollama":
        return [m["name"] for m in charge.get("models", [])]
    return [m["id"] for m in charge.get("data", [])]


def disponibles() -> list[dict]:
    """Ce qui repond, ici, maintenant. Ne leve pas : l'absence est une information."""
    trouves = []
    for backend in BACKENDS:
        try:
            noms = modeles(backend)
        except LocalError as exc:
            trouves.append({"backend": backend, "base": BACKENDS[backend]["base"],
                            "disponible": False, "modeles": [], "detail": str(exc)})
            continue
        trouves.append({"backend": backend, "base": BACKENDS[backend]["base"],
                        "disponible": True, "modeles": noms})
    return trouves


def detecter(backend: str = "auto") -> tuple[str, str]:
    """Rend (backend, modele) : le premier serveur qui repond, avec son premier modele."""
    candidats = list(BACKENDS) if backend == "auto" else [backend]
    echecs = []
    for nom in candidats:
        try:
            noms = modeles(nom)
        except LocalError as exc:
            echecs.append(f"{nom} : {exc}")
            continue
        if noms:
            return nom, noms[0]
        echecs.append(f"{nom} : aucun modele charge")
    raise LocalError(
        "aucun modele local joignable.\n  " + "\n  ".join(echecs) +
        "\n  Ollama : `ollama serve` puis `ollama pull qwen2.5:7b`"
        "\n  LM Studio : onglet Developer, `Start Server` (port 1234)")


def repondre(messages: list[dict], backend: str, modele: str,
             timeout: float = TIMEOUT_GENERATION_S) -> str:
    """Un aller-retour de conversation. Les deux API different, la sortie non."""
    conf = BACKENDS[backend]
    if backend == "ollama":
        charge = {"model": modele, "messages": messages, "stream": False,
                  "options": {"temperature": TEMPERATURE}}
        reponse = _http(conf["base"] + conf["chat"], charge, timeout)
        contenu = (reponse.get("message") or {}).get("content", "")
    else:
        charge = {"model": modele, "messages": messages, "stream": False,
                  "temperature": TEMPERATURE}
        reponse = _http(conf["base"] + conf["chat"], charge, timeout)
        choix = reponse.get("choices") or [{}]
        contenu = (choix[0].get("message") or {}).get("content", "")
    if not contenu.strip():
        raise LocalError(f"{backend}/{modele} a rendu une reponse vide")
    return contenu


# --- le prompt ---------------------------------------------------------------------------

CONSIGNE = """Tu ecris UN fichier Python complet : une candidate de strategie pour le banc \
d'essai BETA. Tu ne rends que du code, dans un seul bloc ```python. Aucune explication \
avant ou apres.

Le fichier doit exposer exactement deux fonctions au niveau du module :

  signaux(df: pd.DataFrame) -> pd.DataFrame
  creer() -> Candidate

`df` est un OHLCV en UTC, index temporel croissant, colonnes open/high/low/close/volume.
`signaux` rend un DataFrame de MEME LONGUEUR, aligne ligne a ligne, avec au moins la
colonne `sens` : +1 pour un long, -1 pour un short, 0 pour rien. Pas de NaN dans `sens`.

INTERDITS ABSOLUS, verifies automatiquement, un seul suffit a faire rejeter ton fichier :

1. Regarder apres la ligne qu'on decide. Donc : jamais `shift(-1)` ni aucun decalage
   negatif, jamais `center=True`, jamais `bfill`, et jamais une statistique calculee sur la
   serie ENTIERE (`close.max()`, `close.mean()`, `close.std()`, une normalisation min-max,
   un quantile global). Ces valeurs dependent du futur et le contaminent partout.
   Utilise des fenetres glissantes : `rolling(n)`, `ewm(span=n)`, `expanding()`.
2. Importer autre chose que `pandas`, `numpy`, `math` et `beta.moteur.contrats`.
   Interdits : os, sys, pathlib, subprocess, urllib, requests, random, datetime, time, et
   tout module `beta.lake` ou `beta.protocole`. La candidate RECOIT ses donnees.
3. Garder un etat entre deux appels (`global`), lire l'horloge, tirer au hasard sans
   graine. Deux appels sur le meme df doivent rendre exactement la meme chose.
4. Executer quoi que ce soit au niveau du module : uniquement des imports, des constantes
   et des `def`.

Ta regle doit etre NUE : une seule idee, deux ou trois lignes de calcul. Pas de filtre de
regime, pas de confirmation multi-indicateur, pas d'empilement de conditions. Une candidate
qui echoue avec six regles n'apprend rien a personne.

Voici un fichier conforme, dont tu reprends exactement la forme :

```python
{exemple}
```
"""

DEMANDE = """Ecris la candidate suivante.

  nom du module   : {module}
  nom             : {nom}
  hypothese (id)  : {hypothese}
  regle voulue    : {intention}

Rends le fichier complet dans un seul bloc ```python."""

REPARATION = """Ton fichier a ete REFUSE par le controle automatique. Motifs, mot pour mot :

{refus}

Corrige et rends le fichier COMPLET, en entier, dans un seul bloc ```python. Ne commente pas
la correction, ne rends pas un extrait."""


def extraire_code(reponse: str) -> str:
    """Le bloc ```python d'une reponse. Un modele local en ajoute presque toujours autour.

    Trois tentatives de moins en moins confiantes : le bloc etiquete python, un bloc nu,
    puis la reponse entiere si elle ressemble deja a du Python. La derniere existe parce
    qu'un modele qui a bien suivi la consigne « ne rends que du code » se retrouverait
    sinon puni pour l'avoir suivie.
    """
    for motif in (r"```python\s*\n(.*?)```", r"```\s*\n(.*?)```"):
        trouves = re.findall(motif, reponse, flags=re.DOTALL)
        if trouves:
            return max(trouves, key=len).strip() + "\n"
    nettoye = reponse.strip()
    if nettoye.startswith(("\"\"\"", "'''", "import ", "from ", "def ", "#")):
        return nettoye + "\n"
    raise LocalError("aucun bloc de code dans la reponse du modele "
                     f"(debut : {reponse.strip()[:160]!r})")


# --- la boucle ---------------------------------------------------------------------------

def ecrire_candidate(intention: str, module: str, hypothese: str, *,
                     backend: str = "auto", modele: str = "",
                     essais: int = ESSAIS_PAR_DEFAUT, nom: str = "") -> dict:
    """Genere, valide, et si besoin fait corriger. Rend un rapport, ne depose pas.

    Le depot reste a l'appelant (CLI ou dashboard) : c'est lui qui sait si l'on ecrase une
    candidate existante, et cette question ne doit pas se decider au fond d'une boucle de
    generation.
    """
    backend_choisi, modele_defaut = detecter(backend)
    modele = modele or modele_defaut
    log.info("modele local : %s / %s", backend_choisi, modele)

    messages = [
        {"role": "system", "content": CONSIGNE.format(exemple=gabarit.EXEMPLE.strip())},
        {"role": "user", "content": DEMANDE.format(
            module=module, nom=nom or module, hypothese=hypothese, intention=intention)},
    ]

    tentatives: list[dict] = []
    code = ""
    for numero in range(1, max(1, essais) + 1):
        reponse = repondre(messages, backend_choisi, modele)
        try:
            code = extraire_code(reponse)
        except LocalError as exc:
            tentatives.append({"essai": numero, "ok": False, "refus": [str(exc)]})
            messages += [{"role": "assistant", "content": reponse},
                         {"role": "user", "content": REPARATION.format(refus=str(exc))}]
            continue

        rapport = depot.valider(code, module)
        tentatives.append({"essai": numero, "ok": rapport["ok"],
                           "refus": rapport["refus"], "reserves": rapport["reserves"]})
        log.info("essai %d/%d : %s", numero, essais,
                 "PASSE" if rapport["ok"] else "; ".join(rapport["refus"]))
        if rapport["ok"]:
            return {**rapport, "code": code, "backend": backend_choisi,
                    "modele": modele, "tentatives": tentatives}
        if numero < essais:
            messages += [
                {"role": "assistant", "content": f"```python\n{code}```"},
                {"role": "user", "content": REPARATION.format(
                    refus="\n".join(f"- {r}" for r in rapport["refus"]))}]

    dernier = tentatives[-1] if tentatives else {"refus": ["aucune tentative"]}
    return {"module": module, "ok": False, "code": code,
            "refus": dernier.get("refus", []), "reserves": dernier.get("reserves", []),
            "mesures": {}, "backend": backend_choisi, "modele": modele,
            "tentatives": tentatives}
