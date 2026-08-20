"""L'auto-recherche : la boucle qui ecrit des candidates et les crible, sans surveillance.

C'est la piece la plus dangereuse du depot, et le module est ecrit en consequence. Un banc
d'essai branche sur un generateur de code est une machine a produire des faux gagnants : le
modele ecrit vingt candidates, on garde la meilleure, et le chiffre qu'on publie est le
maximum d'une distribution nulle. La litterature appelle ca le fleau des tests multiples ;
en pratique, ca ressemble a une decouverte.

Trois regles portees par le code, pas par la discipline de celui qui lance la commande :

1. **La boucle ne preenregistre JAMAIS.** Elle exige une hypothese deja ecrite, et refuse
   de demarrer sinon. Decider qu'une idee vaut un cran de compteur reste un geste de Jonas
   — c'est ce que le pont MCP separe deja en `beta_suggest_idea` (gratuit) et
   `beta_register_edge` (couteux), et il n'y a aucune raison que la boucle locale dispose
   d'un chemin que l'agent distant n'a pas.
2. **Le budget est declare AVANT de generer**, et il est borne par la `famille_taille` du
   preenregistrement. Le lot crible est exactement le lot ECRIT — pas toutes les candidates
   rattachees a l'hypothese — sans quoi le budget verifie et le lot mesure divergeraient
   des le deuxieme lot. Ecrire dix candidates puis declarer une famille de dix revient a ne
   pas corriger du tout : le m de Benjamini-Hochberg doit etre fixe avant de voir les
   p-values, sinon il s'ajuste tout seul a ce qui arrange.
3. **Le modele local ne choisit pas les hypotheses, il ecrit des variantes.** L'intention
   vient de Jonas ou d'une idee promue ; ce que la boucle automatise, c'est le passage de
   l'intention au code — la partie ou une machine est utile et ou elle ne decide rien.

Le mode `proposer` est l'etage gratuit : le modele note des idees dans `IDEES.jsonl`, le
compteur ne bouge pas, et rien n'est mesure. C'est la seule facon honnete de laisser une
machine elargir l'univers d'hypotheses.

Lancement :
    python beta.py auto proposer --sujet "regimes de volatilite" --combien 5
    python beta.py auto cribler --experience R7 --intentions intentions.txt
"""

from __future__ import annotations

import logging
import re

from beta.atelier import depot, local
from beta.moteur import pipeline, registre
from beta.protocole import experiences, holdout, idees

log = logging.getLogger("beta.recherche.auto")

# Prefixe des modules ecrits par la boucle : un coup d'oeil a `beta/candidates/` doit
# suffire pour savoir ce qu'une machine a ecrit et ce qu'un humain a ecrit.
PREFIXE = "auto"

# Plafond dur, quel que soit ce que declare le preenregistrement. Il n'est pas la pour
# proteger la statistique — `famille_taille` s'en charge — mais la machine : une boucle
# lancee sur 200 candidates tourne une nuit entiere, et personne ne relit 200 fichiers.
BUDGET_MAX = 20

# Une candidate refusee trois fois par le sas ne le sera pas moins la quatrieme : le modele
# tourne en rond bien avant. Le budget d'essais de reparation vit dans `local`.
ESSAIS_REPARATION = local.ESSAIS_PAR_DEFAUT

SUJET_LIBRE = "des edges possibles sur des perpetuels crypto en 4h"

PROMPT_IDEES = """Tu proposes des hypotheses de recherche pour un banc d'essai de strategies
de trading. Sujet : {sujet}.

Ecris exactement {combien} hypotheses, une par ligne, sans numerotation ni puce.
Chacune doit etre FALSIFIABLE : elle doit dire ce qu'on mesure et dans quel sens on
s'attend a se tromper. « le RSI marche bien » n'est pas une hypothese ; « apres trois
bougies 4h consecutives de meme sens, le retour a la moyenne sur la bougie suivante a un
R moyen positif » en est une.

N'ecris rien d'autre que les {combien} lignes."""

# Une ligne trop courte est un titre, une puce vide ou un reste de mise en forme, jamais
# une hypothese falsifiable.
LONGUEUR_MIN_IDEE = 20


class AutoError(RuntimeError):
    """La boucle refuse de demarrer. Toujours pour une raison de protocole, jamais technique."""


def _nom_module(id_experience: str, rang: int) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", id_experience.lower()).strip("_")
    return f"{PREFIXE}_{base}_{rang:02d}"


def proposer(sujet: str = SUJET_LIBRE, combien: int = 5, *, backend: str = "auto",
             modele: str = "") -> list[dict]:
    """Etage GRATUIT : le modele note des idees, le compteur d'essais ne bouge pas.

    Aucune de ces idees n'est mesuree, aucune n'est preenregistree. Elles attendent dans
    `IDEES.jsonl` qu'un humain en promeuve une — et c'est a ce moment-la seulement que le
    compteur avance, definitivement, pour tout le reste du projet.
    """
    backend_choisi, modele_defaut = local.detecter(backend)
    modele = modele or modele_defaut
    combien = max(1, int(combien))
    log.info("proposition de %d idees par %s / %s", combien, backend_choisi, modele)

    reponse = local.repondre(
        [{"role": "user", "content": PROMPT_IDEES.format(sujet=sujet, combien=combien)}],
        backend_choisi, modele)

    notees: list[dict] = []
    for ligne in reponse.splitlines():
        texte = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", ligne).strip()
        if len(texte) < LONGUEUR_MIN_IDEE:
            continue
        try:
            notees.append(idees.ajouter(
                texte, source=f"auto/{backend_choisi}:{modele}",
                pourquoi=f"proposee automatiquement sur le sujet « {sujet} »"))
        except idees.IdeeError as exc:
            log.warning("idee non notee : %s", exc)
        if len(notees) >= combien:
            break

    log.info("%d idee(s) notees — le compteur d'essais reste a %d",
             len(notees), experiences.compteur())
    return notees


def _verifier_le_protocole(id_experience: str, intentions: list[str],
                           split: str) -> tuple[dict, int]:
    """Le seul endroit ou la boucle peut refuser de demarrer. Elle le fait avant tout code.

    Rend (preenregistrement, budget effectif). Aucune generation n'a lieu si l'un des refus
    tombe : hypothese absente, hold-out demande, famille non declaree, budget trop grand.
    """
    preenr = experiences.exiger(id_experience)      # leve ProtocoleError si absent

    if split != holdout.TRAIN:
        raise AutoError(
            "l'auto-recherche ne tourne que sur le train. Le hold-out se regarde une fois, "
            "a la main, sur une candidate qui a deja survecu — pas au bout d'une boucle.")

    famille = preenr.get("famille_taille")
    if not famille:
        raise AutoError(
            f"'{id_experience}' ne declare pas de `famille_taille`. La boucle a besoin du m "
            "de Benjamini-Hochberg AVANT de generer : une famille declaree apres coup "
            "s'ajuste au resultat, donc ne corrige rien. Amender le preenregistrement.")

    budget = len(intentions)
    if budget > int(famille):
        raise AutoError(
            f"{budget} intentions pour une famille declaree de {famille}. Reduire le lot, "
            "ou amender le preenregistrement AVANT de mesurer — jamais apres.")
    if budget > BUDGET_MAX:
        raise AutoError(f"{budget} intentions : plafond de la boucle a {BUDGET_MAX}. "
                        "Au-dela, personne ne relit ce que le modele a ecrit.")
    return preenr, budget


def ecrire_le_lot(id_experience: str, intentions: list[str], *, backend: str = "auto",
                  modele: str = "", ecraser: bool = True) -> list[dict]:
    """Fait ecrire une candidate par intention, chacune passee au sas et a l'epreuve.

    Une intention qui echoue n'interrompt pas les autres : elle est journalisee et sa place
    dans la famille reste prise. C'est voulu — abandonner une intention en cours de route
    sans que le m en tienne compte relacherait le seuil des candidates qui, elles, ont
    abouti.
    """
    rapports: list[dict] = []
    for rang, intention in enumerate(intentions, 1):
        module = _nom_module(id_experience, rang)
        log.info("[%d/%d] %s : %s", rang, len(intentions), module, intention[:70])
        try:
            ecrit = local.ecrire_candidate(
                intention, module, id_experience, backend=backend, modele=modele,
                essais=ESSAIS_REPARATION)
        except local.LocalError as exc:
            log.error("%s : generation impossible (%s)", module, exc)
            rapports.append({"module": module, "intention": intention, "ok": False,
                             "refus": [str(exc)], "depose": False})
            continue

        if not ecrit["ok"]:
            log.error("%s refuse : %s", module, "; ".join(ecrit["refus"]))
            rapports.append({**ecrit, "intention": intention, "depose": False})
            continue

        try:
            pose = depot.deposer(ecrit["code"], module, ecraser=ecraser)
        except depot.DepotError as exc:
            log.error("%s non depose : %s", module, exc)
            rapports.append({**ecrit, "intention": intention, "depose": False,
                             "refus": [str(exc)]})
            continue
        rapports.append({**ecrit, **pose, "intention": intention})

    deposees = sum(1 for r in rapports if r.get("depose"))
    log.info("%d/%d candidate(s) deposees", deposees, len(intentions))
    return rapports


def _lot_ecrit(rapports: list[dict], id_experience: str) -> dict:
    """Les candidates de CE lot, chargees par leur module. Jamais celles des lots passes.

    Un filtre par hypothese rendrait toutes les candidates rattachees a celle-ci, y
    compris celles d'un lot precedent ou ecrites a la main. Le controle
    `budget <= famille_taille` porte, lui, sur les intentions de CE lot : les deux nombres
    divergeraient des le deuxieme lot, et le lot crible deborderait la famille declaree
    sans qu'aucun refus ne tombe. Le sens du debordement est conservateur — le m de BH
    remonte a la taille du lot, donc le seuil durcit — mais un verrou qui ne tient que par
    la direction de sa fuite n'est pas un verrou.

    Une candidate qui ne declare pas l'hypothese du lot est ECARTEE : le modele a le droit
    de se tromper de `hypothese=` dans le code qu'il ecrit, le banc n'a pas le droit de la
    mesurer sous une famille qui n'est pas la sienne.
    """
    lot: dict = {}
    for rapport in rapports:
        if not rapport.get("depose"):
            continue
        module = rapport["module"]
        try:
            candidate = registre.charger(module)
        except Exception as exc:                     # noqa: BLE001 - une candidate cassee
            log.error("%s deposee mais illisible, ecartee du criblage : %s", module, exc)
            continue
        if candidate.hypothese != id_experience:
            log.error("%s declare l'hypothese '%s' au lieu de '%s' : ecartee",
                      module, candidate.hypothese, id_experience)
            continue
        lot[module] = candidate
    return lot


def lancer(id_experience: str, intentions: list[str], paires: tuple[str, ...],
           timeframe: str, *, backend: str = "auto", modele: str = "",
           split: str = holdout.TRAIN, ecraser: bool = True, **options) -> dict:
    """La boucle complete : verifier le protocole, ecrire le lot, le cribler en UNE fois.

    Le criblage se fait sur le lot entier, jamais candidate par candidate. C'est ce qui
    permet a S1 (Benjamini-Hochberg), S7 (reality check) et S9 (correlation) d'exister :
    les trois portes comparent les candidates entre elles, et les lancer une par une
    donnerait a chacune l'illusion d'etre seule au monde — dans le sens flatteur.
    """
    intentions = [i.strip() for i in intentions if i and i.strip()]
    if not intentions:
        raise AutoError("aucune intention : la boucle n'invente pas ce qu'elle doit tester")

    preenr, budget = _verifier_le_protocole(id_experience, intentions, split)
    n_avant = experiences.compteur()
    log.info("hypothese '%s' : famille declaree %s, budget %d, compteur avant %d",
             id_experience, preenr.get("famille_taille"), budget, n_avant)

    rapports = ecrire_le_lot(id_experience, intentions, backend=backend, modele=modele,
                             ecraser=ecraser)

    lot = _lot_ecrit(rapports, id_experience)
    if not lot:
        return {"experience": id_experience, "ecriture": rapports, "verdicts": {},
                "compteur_avant": n_avant, "compteur_apres": experiences.compteur(),
                "famille_declaree": preenr.get("famille_taille"),
                "lot": [],
                "motif": "aucune candidate exploitable dans ce lot — rien n'a ete mesure, "
                         "donc le compteur n'a pas bouge"}

    verdicts = pipeline.cribler(lot, paires=paires, timeframe=timeframe, split=split,
                                **options)
    return {"experience": id_experience, "ecriture": rapports, "verdicts": verdicts,
            "lot": sorted(lot), "compteur_avant": n_avant,
            "compteur_apres": experiences.compteur(),
            "famille_declaree": preenr.get("famille_taille")}
